#!/usr/bin/env python3
"""Locate and tap Android UIAutomator nodes with structured JSON output."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REMOTE_XML_PATH = "/sdcard/window.xml"
BOUNDS_RE = re.compile(r"^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$")
MATCH_FIELDS = {
    "text": "text",
    "content_desc": "content-desc",
    "hint": "hint",
    "node_class": "class",
    "bounds": "bounds",
}
POSTCONDITION_FIELDS = {
    "postcondition_text": "text",
    "postcondition_content_desc": "content-desc",
    "postcondition_hint": "hint",
    "postcondition_node_class": "class",
}


class CliFailure(Exception):
    """A user-facing failure with a stable JSON error code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 3,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliFailure("invalid_arguments", message, exit_code=2)


@dataclass(frozen=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int
    raw: str

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center_x(self) -> int:
        return (self.left + self.right) // 2

    @property
    def center_y(self) -> int:
        return (self.top + self.bottom) // 2

    def as_json(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
            "center": {"x": self.center_x, "y": self.center_y},
        }


@dataclass(frozen=True)
class UiNode:
    order: int
    path: str
    depth: int
    attributes: dict[str, str]
    bounds: Bounds

    def boolean(self, name: str) -> bool | None:
        value = self.attributes.get(name)
        if value is None:
            return None
        if value == "true":
            return True
        if value == "false":
            return False
        raise CliFailure(
            "invalid_xml_attribute",
            f"Node {self.path} has invalid boolean attribute {name!r}: {value!r}",
        )

    def as_json(self) -> dict[str, Any]:
        index_value: int | str = self.attributes.get("index", "")
        try:
            index_value = int(index_value)
        except ValueError:
            pass

        result: dict[str, Any] = {
            "order": self.order,
            "path": self.path,
            "depth": self.depth,
            "index": index_value,
            "text": self.attributes.get("text", ""),
            "content-desc": self.attributes.get("content-desc", ""),
            "hint": self.attributes.get("hint", ""),
            "class": self.attributes.get("class", ""),
            "resource-id": self.attributes.get("resource-id", ""),
            "package": self.attributes.get("package", ""),
            "bounds": self.bounds.as_json(),
        }
        for name in (
            "clickable",
            "enabled",
            "focusable",
            "focused",
            "scrollable",
            "long-clickable",
            "checkable",
            "checked",
            "selected",
            "password",
        ):
            result[name] = self.boolean(name)
        return result


@dataclass(frozen=True)
class UiDocument:
    rotation: int | str
    nodes: tuple[UiNode, ...]


def emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def shorten(value: bytes, limit: int = 2000) -> str:
    text = value.decode("utf-8", errors="replace").strip()
    return text if len(text) <= limit else f"{text[:limit]}...<truncated>"


def adb_command(device: str, arguments: Iterable[str]) -> list[str]:
    command = ["adb"]
    if device:
        command.extend(["-s", device])
    command.extend(arguments)
    return command


def side_effect_may_have_occurred(arguments: list[str]) -> bool:
    return arguments[:3] in (
        ["shell", "input", "tap"],
        ["shell", "input", "swipe"],
    )


def run_adb_raw(
    device: str,
    arguments: list[str],
    timeout: float,
) -> subprocess.CompletedProcess[bytes]:
    command = adb_command(device, arguments)
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CliFailure("adb_not_found", "adb was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise CliFailure(
            "adb_timeout",
            f"ADB command exceeded the {timeout:g}s timeout",
            details={
                "argv": command,
                "sideEffectMayHaveOccurred": side_effect_may_have_occurred(arguments),
            },
        ) from exc


def run_adb(
    device: str,
    arguments: list[str],
    timeout: float,
) -> subprocess.CompletedProcess[bytes]:
    command = adb_command(device, arguments)
    may_have_side_effect = side_effect_may_have_occurred(arguments)
    result = run_adb_raw(device, arguments, timeout)

    if result.returncode != 0:
        raise CliFailure(
            "adb_failed",
            f"ADB command failed with exit code {result.returncode}",
            details={
                "argv": command,
                "stdout": shorten(result.stdout),
                "stderr": shorten(result.stderr),
                "sideEffectMayHaveOccurred": may_have_side_effect,
            },
        )
    return result


def capture_xml(device: str, timeout: float) -> tuple[bytes, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        run_adb_raw(device, ["shell", "rm", "-f", REMOTE_XML_PATH], timeout)
        dump_result = run_adb_raw(
            device,
            ["shell", "uiautomator", "dump", REMOTE_XML_PATH],
            timeout,
        )
        read_result = run_adb_raw(
            device,
            ["exec-out", "cat", REMOTE_XML_PATH],
            timeout,
        )
        data = read_result.stdout
        valid = bool(
            read_result.returncode == 0
            and data.startswith(b"<?xml")
            and b"<hierarchy" in data
            and b"</hierarchy>" in data
        )
        attempt_record = {
            "attempt": attempt,
            "dumpReturncode": dump_result.returncode,
            "dumpOutput": shorten(dump_result.stdout or dump_result.stderr),
            "readReturncode": read_result.returncode,
            "readOutput": shorten(read_result.stderr),
            "bytes": len(data),
            "validCompleteXml": valid,
        }
        attempts.append(attempt_record)
        if valid:
            return data, {
                "type": "adb",
                "device": device or None,
                "remotePath": REMOTE_XML_PATH,
                "dumpOutput": attempt_record["dumpOutput"],
                "dumpReturncode": dump_result.returncode,
                "acceptedAttempt": attempt,
                "attempts": attempts,
            }
        time.sleep(attempt)
    raise CliFailure(
        "ui_dump_failed",
        "UIAutomator did not produce a complete fresh XML hierarchy after three attempts",
        details={"attempts": attempts},
    )


def read_xml(path: Path) -> tuple[bytes, dict[str, Any]]:
    resolved = path.expanduser().resolve()
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise CliFailure(
            "xml_read_failed",
            f"Could not read XML file: {resolved}",
            details={"reason": str(exc)},
        ) from exc
    if not data.strip():
        raise CliFailure("empty_xml", f"XML file is empty: {resolved}")
    return data, {"type": "file", "path": str(resolved)}


def parse_bounds(raw: str, path: str) -> Bounds:
    match = BOUNDS_RE.fullmatch(raw)
    if not match:
        raise CliFailure(
            "invalid_bounds",
            f"Node {path} has malformed bounds: {raw!r}",
        )
    left, top, right, bottom = (int(value) for value in match.groups())
    if right < left or bottom < top:
        raise CliFailure(
            "invalid_bounds",
            f"Node {path} has inverted bounds: {raw!r}",
        )
    return Bounds(left, top, right, bottom, raw)


def parse_document(data: bytes) -> UiDocument:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise CliFailure(
            "invalid_xml",
            "Could not parse UIAutomator XML",
            details={"reason": str(exc)},
        ) from exc
    if root.tag != "hierarchy":
        raise CliFailure(
            "invalid_xml_root",
            f"Expected <hierarchy> root, found <{root.tag}>",
        )

    rotation_raw = root.attrib.get("rotation", "")
    try:
        rotation: int | str = int(rotation_raw)
    except ValueError:
        rotation = rotation_raw

    parsed: list[UiNode] = []

    def visit(parent: ET.Element, parent_path: str, depth: int) -> None:
        for position, child in enumerate(parent):
            path = f"{parent_path}/{position}" if parent_path else str(position)
            if child.tag != "node":
                raise CliFailure(
                    "invalid_xml_node",
                    f"Unexpected <{child.tag}> element at {path}",
                )
            attributes = dict(child.attrib)
            if "bounds" not in attributes:
                raise CliFailure("missing_bounds", f"Node {path} has no bounds attribute")
            parsed.append(
                UiNode(
                    order=len(parsed),
                    path=path,
                    depth=depth,
                    attributes=attributes,
                    bounds=parse_bounds(attributes["bounds"], path),
                )
            )
            visit(child, path, depth + 1)

    visit(root, "", 0)
    if not parsed:
        raise CliFailure("empty_hierarchy", "UIAutomator XML contains no nodes")
    return UiDocument(rotation=rotation, nodes=tuple(parsed))


def selectors_from_args(args: argparse.Namespace) -> dict[str, str]:
    selectors: dict[str, str] = {}
    for argument_name, attribute_name in MATCH_FIELDS.items():
        value = getattr(args, argument_name, None)
        if value is None:
            continue
        if value == "":
            raise CliFailure(
                "empty_selector",
                f"--{attribute_name} must not be empty",
                exit_code=2,
            )
        if attribute_name == "bounds" and BOUNDS_RE.fullmatch(value) is None:
            raise CliFailure(
                "invalid_bounds_selector",
                "--bounds must use the exact UIAutomator form [left,top][right,bottom]",
                exit_code=2,
            )
        selectors[attribute_name] = value
    if not selectors:
        raise CliFailure(
            "missing_selector",
            "At least one of --text, --content-desc, --hint, --class, or --bounds is required",
            exit_code=2,
        )
    return selectors


def postcondition_selectors_from_args(args: argparse.Namespace) -> dict[str, str]:
    selectors: dict[str, str] = {}
    for argument_name, attribute_name in POSTCONDITION_FIELDS.items():
        value = getattr(args, argument_name, None)
        if value is None:
            continue
        if value == "":
            raise CliFailure(
                "empty_postcondition_selector",
                f"--postcondition-{attribute_name} must not be empty",
                exit_code=2,
            )
        selectors[attribute_name] = value
    if not selectors:
        raise CliFailure(
            "missing_postcondition",
            "A gesture requires at least one explicit --postcondition-* selector",
            exit_code=2,
        )
    return selectors


def find_nodes(
    document: UiDocument,
    selectors: dict[str, str],
    *,
    contains: bool,
) -> list[UiNode]:
    def matches(node: UiNode) -> bool:
        for attribute, expected in selectors.items():
            actual = node.attributes.get(attribute, "")
            if contains:
                if expected not in actual:
                    return False
            elif actual != expected:
                return False
        return True

    return [node for node in document.nodes if matches(node)]


def select_unique_target(
    document: UiDocument,
    source: dict[str, Any],
    selectors: dict[str, str],
    *,
    contains: bool,
    action: str,
) -> UiNode:
    matches = find_nodes(document, selectors, contains=contains)
    if not matches:
        raise CliFailure(
            "no_matches",
            f"{action} refused because no UI node matched all selectors",
            exit_code=4,
            details={
                "source": source,
                "matchMode": "contains" if contains else "exact",
                "selectors": selectors,
            },
        )
    if len(matches) != 1:
        raise CliFailure(
            "ambiguous_match",
            f"{action} refused because the selectors matched more than one UI node",
            exit_code=5,
            details={
                "source": source,
                "matchMode": "contains" if contains else "exact",
                "selectors": selectors,
                "matchCount": len(matches),
                "matches": [node.as_json() for node in matches],
            },
        )
    return matches[0]


def validate_target(
    document: UiDocument,
    target: UiNode,
    *,
    action: str,
    required_boolean: str | None,
) -> None:
    if target.boolean("enabled") is not True:
        raise CliFailure(
            "target_disabled",
            f"{action} refused because the matched node is not enabled",
            exit_code=6,
            details={"target": target.as_json()},
        )
    if required_boolean and target.boolean(required_boolean) is not True:
        raise CliFailure(
            f"target_not_{required_boolean.replace('-', '_')}",
            f"{action} refused because the matched node is not marked {required_boolean}",
            exit_code=6,
            details={"target": target.as_json()},
        )
    if target.bounds.width <= 0 or target.bounds.height <= 0:
        raise CliFailure(
            "empty_target_bounds",
            f"{action} refused because the matched node has empty bounds",
            exit_code=6,
            details={"target": target.as_json()},
        )
    require_point_on_screen(document, target.bounds.center_x, target.bounds.center_y, target, action)


def require_point_on_screen(
    document: UiDocument,
    x: int,
    y: int,
    target: UiNode,
    action: str,
) -> None:
    top_level_bounds = [node.bounds for node in document.nodes if node.depth == 0]
    if not any(bounds.left <= x < bounds.right and bounds.top <= y < bounds.bottom for bounds in top_level_bounds):
        raise CliFailure(
            "offscreen_target",
            f"{action} refused because a gesture point is outside the top-level UI bounds",
            exit_code=6,
            details={
                "target": target.as_json(),
                "point": {"x": x, "y": y},
                "topLevelBounds": [bounds.as_json() for bounds in top_level_bounds],
            },
        )


def validate_duration(duration_ms: int, *, minimum: int, maximum: int, action: str) -> None:
    if duration_ms < minimum or duration_ms > maximum:
        raise CliFailure(
            "invalid_duration",
            f"{action} duration must be between {minimum} and {maximum} milliseconds",
            exit_code=2,
            details={"durationMs": duration_ms, "minimum": minimum, "maximum": maximum},
        )


def validate_postcondition_options(args: argparse.Namespace) -> dict[str, str]:
    selectors = postcondition_selectors_from_args(args)
    if args.postcondition_count < 0:
        raise CliFailure(
            "invalid_postcondition_count",
            "--postcondition-count must be zero or greater",
            exit_code=2,
        )
    if not math.isfinite(args.postcondition_timeout) or args.postcondition_timeout <= 0:
        raise CliFailure(
            "invalid_postcondition_timeout",
            "--postcondition-timeout must be greater than zero",
            exit_code=2,
        )
    if not math.isfinite(args.postcondition_poll_interval) or args.postcondition_poll_interval <= 0:
        raise CliFailure(
            "invalid_postcondition_poll_interval",
            "--postcondition-poll-interval must be greater than zero",
            exit_code=2,
        )
    return selectors


def wait_for_postcondition(args: argparse.Namespace) -> dict[str, Any]:
    selectors = validate_postcondition_options(args)
    expected_count = args.postcondition_count

    deadline = time.monotonic() + args.postcondition_timeout
    attempts: list[dict[str, Any]] = []
    while True:
        data, source = capture_xml(args.device, args.timeout)
        document = parse_document(data)
        matches = find_nodes(document, selectors, contains=args.postcondition_contains)
        attempts.append(
            {
                "source": source,
                "matchCount": len(matches),
                "nodeCount": len(document.nodes),
            }
        )
        if len(matches) == expected_count:
            return {
                "selectors": selectors,
                "matchMode": "contains" if args.postcondition_contains else "exact",
                "expectedCount": expected_count,
                "matchCount": len(matches),
                "matches": [node.as_json() for node in matches],
                "attempts": attempts,
            }
        if time.monotonic() >= deadline:
            raise CliFailure(
                "postcondition_failed",
                "Gesture may have occurred, but its explicit postcondition was not observed",
                exit_code=7,
                details={
                    "sideEffectMayHaveOccurred": True,
                    "selectors": selectors,
                    "matchMode": "contains" if args.postcondition_contains else "exact",
                    "expectedCount": expected_count,
                    "lastMatchCount": len(matches),
                    "attempts": attempts,
                },
            )
        time.sleep(min(args.postcondition_poll_interval, max(0.0, deadline - time.monotonic())))


def load_for_query(args: argparse.Namespace) -> tuple[UiDocument, dict[str, Any], bytes]:
    if getattr(args, "xml", None) is not None:
        if args.device:
            raise CliFailure(
                "invalid_arguments",
                "--device cannot be combined with --xml",
                exit_code=2,
            )
        data, source = read_xml(args.xml)
    else:
        data, source = capture_xml(args.device, args.timeout)
    return parse_document(data), source, data


def command_dump(args: argparse.Namespace) -> dict[str, Any]:
    data, source = capture_xml(args.device, args.timeout)
    document = parse_document(data)
    output_path: str | None = None
    if args.output is not None:
        resolved = args.output.expanduser().resolve()
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_bytes(data)
        except OSError as exc:
            raise CliFailure(
                "xml_write_failed",
                f"Could not write XML file: {resolved}",
                details={"reason": str(exc)},
            ) from exc
        output_path = str(resolved)

    return {
        "ok": True,
        "command": "dump",
        "source": source,
        "xmlOutput": output_path,
        "rotation": document.rotation,
        "nodeCount": len(document.nodes),
        "nodes": [node.as_json() for node in document.nodes],
    }


def query_payload(
    command: str,
    document: UiDocument,
    source: dict[str, Any],
    selectors: dict[str, str],
    contains: bool,
    matches: list[UiNode],
) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "source": source,
        "matchMode": "contains" if contains else "exact",
        "selectors": selectors,
        "rotation": document.rotation,
        "nodeCount": len(document.nodes),
        "matchCount": len(matches),
        "matches": [node.as_json() for node in matches],
    }


def command_find(args: argparse.Namespace) -> dict[str, Any]:
    selectors = selectors_from_args(args)
    document, source, _ = load_for_query(args)
    matches = find_nodes(document, selectors, contains=args.contains)
    if not matches:
        raise CliFailure(
            "no_matches",
            "No UI node matched all selectors",
            exit_code=4,
            details={
                "source": source,
                "matchMode": "contains" if args.contains else "exact",
                "selectors": selectors,
                "nodeCount": len(document.nodes),
            },
        )
    return query_payload("find", document, source, selectors, args.contains, matches)


def command_tap(args: argparse.Namespace) -> dict[str, Any]:
    selectors = selectors_from_args(args)
    data, source = capture_xml(args.device, args.timeout)
    document = parse_document(data)
    target = select_unique_target(document, source, selectors, contains=args.contains, action="Tap")
    validate_target(document, target, action="Tap", required_boolean="clickable")

    tap_result = run_adb(
        args.device,
        [
            "shell",
            "input",
            "tap",
            str(target.bounds.center_x),
            str(target.bounds.center_y),
        ],
        args.timeout,
    )
    return {
        "ok": True,
        "command": "tap",
        "source": source,
        "matchMode": "contains" if args.contains else "exact",
        "selectors": selectors,
        "target": target.as_json(),
        "tap": {"x": target.bounds.center_x, "y": target.bounds.center_y},
        "adbOutput": shorten(tap_result.stdout or tap_result.stderr),
    }


def command_long_press(args: argparse.Namespace) -> dict[str, Any]:
    selectors = selectors_from_args(args)
    validate_duration(args.duration_ms, minimum=200, maximum=10000, action="Long-press")
    validate_postcondition_options(args)
    data, source = capture_xml(args.device, args.timeout)
    document = parse_document(data)
    target = select_unique_target(document, source, selectors, contains=args.contains, action="Long-press")
    allow_clickable_fallback = bool(getattr(args, "allow_clickable_fallback", False))
    allow_semantic_fallback = bool(getattr(args, "allow_semantic_fallback", False))
    if allow_clickable_fallback and allow_semantic_fallback:
        raise CliFailure(
            "conflicting_long_press_fallbacks",
            "Choose at most one long-press fallback mode",
            exit_code=2,
        )
    if (allow_clickable_fallback or allow_semantic_fallback) and "bounds" not in selectors:
        raise CliFailure(
            "long_press_fallback_requires_bounds",
            "Long-press fallback requires an exact --bounds selector",
            exit_code=2,
            details={"selectors": selectors},
        )
    if allow_semantic_fallback and not any(
        selector in selectors for selector in ("text", "content-desc", "hint")
    ):
        raise CliFailure(
            "semantic_fallback_requires_label",
            "Long-press semantic fallback requires --text, --content-desc, or --hint",
            exit_code=2,
            details={"selectors": selectors},
        )
    if allow_semantic_fallback:
        required_boolean = None
        required_capability = "enabled-semantic-label-exact-bounds"
    elif allow_clickable_fallback:
        required_boolean = "clickable"
        required_capability = "clickable"
    else:
        required_boolean = "long-clickable"
        required_capability = "long-clickable"
    validate_target(document, target, action="Long-press", required_boolean=required_boolean)
    gesture = [
        "shell",
        "input",
        "swipe",
        str(target.bounds.center_x),
        str(target.bounds.center_y),
        str(target.bounds.center_x),
        str(target.bounds.center_y),
        str(args.duration_ms),
    ]
    result = run_adb(args.device, gesture, args.timeout)
    postcondition = wait_for_postcondition(args)
    return {
        "ok": True,
        "command": "long-press",
        "source": source,
        "matchMode": "contains" if args.contains else "exact",
        "selectors": selectors,
        "target": target.as_json(),
        "targetCapability": {
            "required": required_capability,
            "clickableFallback": allow_clickable_fallback,
            "semanticFallback": allow_semantic_fallback,
        },
        "gesture": {
            "start": {"x": target.bounds.center_x, "y": target.bounds.center_y},
            "end": {"x": target.bounds.center_x, "y": target.bounds.center_y},
            "durationMs": args.duration_ms,
        },
        "sideEffectMayHaveOccurred": True,
        "adbOutput": shorten(result.stdout or result.stderr),
        "postcondition": postcondition,
    }


def command_swipe(args: argparse.Namespace) -> dict[str, Any]:
    selectors = selectors_from_args(args)
    validate_duration(args.duration_ms, minimum=50, maximum=10000, action="Swipe")
    validate_postcondition_options(args)
    data, source = capture_xml(args.device, args.timeout)
    document = parse_document(data)
    target = select_unique_target(document, source, selectors, contains=args.contains, action="Swipe")
    validate_target(document, target, action="Swipe", required_boolean="scrollable")
    end_x = target.bounds.center_x + args.delta_x
    end_y = target.bounds.center_y + args.delta_y
    if args.delta_x == 0 and args.delta_y == 0:
        raise CliFailure(
            "empty_swipe",
            "Swipe refused because both deltas are zero; use long-press for a stationary gesture",
            exit_code=2,
        )
    if not (
        target.bounds.left <= end_x < target.bounds.right
        and target.bounds.top <= end_y < target.bounds.bottom
    ):
        raise CliFailure(
            "swipe_end_outside_target",
            "Swipe refused because the end point leaves the uniquely matched target bounds",
            exit_code=6,
            details={
                "target": target.as_json(),
                "end": {"x": end_x, "y": end_y},
            },
        )
    require_point_on_screen(document, end_x, end_y, target, "Swipe")
    gesture = [
        "shell",
        "input",
        "swipe",
        str(target.bounds.center_x),
        str(target.bounds.center_y),
        str(end_x),
        str(end_y),
        str(args.duration_ms),
    ]
    result = run_adb(args.device, gesture, args.timeout)
    postcondition = wait_for_postcondition(args)
    return {
        "ok": True,
        "command": "swipe",
        "source": source,
        "matchMode": "contains" if args.contains else "exact",
        "selectors": selectors,
        "target": target.as_json(),
        "gesture": {
            "start": {"x": target.bounds.center_x, "y": target.bounds.center_y},
            "end": {"x": end_x, "y": end_y},
            "delta": {"x": args.delta_x, "y": args.delta_y},
            "durationMs": args.duration_ms,
        },
        "sideEffectMayHaveOccurred": True,
        "adbOutput": shorten(result.stdout or result.stderr),
        "postcondition": postcondition,
    }


def add_live_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", default=None, help="Optional adb device serial")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-command ADB timeout in seconds (default: 30)",
    )


def add_selector_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--text", help="Match the node text attribute")
    parser.add_argument("--content-desc", dest="content_desc", help="Match content-desc")
    parser.add_argument("--hint", help="Match the node hint attribute")
    parser.add_argument("--class", dest="node_class", help="Match the Android class")
    parser.add_argument(
        "--bounds",
        help="Match exact live UIAutomator bounds in [left,top][right,bottom] form",
    )
    parser.add_argument(
        "--contains",
        action="store_true",
        help="Use case-sensitive substring matching instead of exact matching",
    )


def add_postcondition_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--postcondition-text", help="Require this text after the gesture")
    parser.add_argument(
        "--postcondition-content-desc",
        dest="postcondition_content_desc",
        help="Require this content-desc after the gesture",
    )
    parser.add_argument("--postcondition-hint", help="Require this hint after the gesture")
    parser.add_argument(
        "--postcondition-class",
        dest="postcondition_node_class",
        help="Require this Android class after the gesture",
    )
    parser.add_argument(
        "--postcondition-contains",
        action="store_true",
        help="Use substring matching for postcondition selectors",
    )
    parser.add_argument(
        "--postcondition-count",
        type=int,
        default=1,
        help="Require exactly this many postcondition matches (default: 1; use 0 for absence)",
    )
    parser.add_argument("--postcondition-timeout", type=float, default=10.0)
    parser.add_argument("--postcondition-poll-interval", type=float, default=0.25)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="Dump, find, and safely tap Android UIAutomator nodes.",
    )
    parser.add_argument(
        "--device",
        dest="global_device",
        default=None,
        help="Optional adb device serial; accepted before or after the subcommand",
    )
    parser.add_argument(
        "--timeout",
        dest="global_timeout",
        type=float,
        default=None,
        help="Per-command ADB timeout; accepted before or after the subcommand",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dump_parser = subparsers.add_parser("dump", help="Capture the live UI tree as JSON")
    add_live_options(dump_parser)
    dump_parser.add_argument("--output", type=Path, help="Also save the raw XML locally")

    find_parser = subparsers.add_parser("find", help="Find nodes in a file or live UI tree")
    add_live_options(find_parser)
    find_parser.add_argument("--xml", type=Path, help="Read saved XML instead of using ADB")
    add_selector_options(find_parser)

    tap_parser = subparsers.add_parser(
        "tap",
        help="Capture the live tree and tap one unique enabled, clickable match",
    )
    add_live_options(tap_parser)
    add_selector_options(tap_parser)

    long_press_parser = subparsers.add_parser(
        "long-press",
        help="Long-press one unique enabled, long-clickable target and verify a postcondition",
    )
    add_live_options(long_press_parser)
    add_selector_options(long_press_parser)
    add_postcondition_options(long_press_parser)
    long_press_parser.add_argument("--duration-ms", type=int, default=800)
    long_press_parser.add_argument(
        "--allow-clickable-fallback",
        action="store_true",
        help=(
            "Allow an enabled clickable target when Flutter omits long-clickable; "
            "requires an exact --bounds selector"
        ),
    )
    long_press_parser.add_argument(
        "--allow-semantic-fallback",
        action="store_true",
        help=(
            "Allow an enabled semantic label when Flutter exposes no gesture capability; "
            "requires an exact --bounds plus --text, --content-desc, or --hint"
        ),
    )

    swipe_parser = subparsers.add_parser(
        "swipe",
        help="Swipe inside one unique enabled, scrollable target and verify a postcondition",
    )
    add_live_options(swipe_parser)
    add_selector_options(swipe_parser)
    add_postcondition_options(swipe_parser)
    swipe_parser.add_argument("--delta-x", type=int, required=True)
    swipe_parser.add_argument("--delta-y", type=int, required=True)
    swipe_parser.add_argument("--duration-ms", type=int, default=300)
    return parser


def normalize_runtime_args(args: argparse.Namespace) -> None:
    local_device = getattr(args, "device", None)
    if (
        args.global_device is not None
        and local_device is not None
        and args.global_device != local_device
    ):
        raise CliFailure(
            "conflicting_device",
            "Conflicting --device values were provided",
            exit_code=2,
        )
    args.device = local_device if local_device is not None else (args.global_device or "")

    local_timeout = getattr(args, "timeout", None)
    if (
        args.global_timeout is not None
        and local_timeout is not None
        and args.global_timeout != local_timeout
    ):
        raise CliFailure(
            "conflicting_timeout",
            "Conflicting --timeout values were provided",
            exit_code=2,
        )
    if local_timeout is not None:
        args.timeout = local_timeout
    elif args.global_timeout is not None:
        args.timeout = args.global_timeout
    else:
        args.timeout = 30.0
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise CliFailure(
            "invalid_timeout",
            "--timeout must be greater than zero",
            exit_code=2,
        )


def main() -> int:
    command = None
    try:
        args = build_parser().parse_args()
        command = args.command
        normalize_runtime_args(args)
        handlers = {
            "dump": command_dump,
            "find": command_find,
            "tap": command_tap,
            "long-press": command_long_press,
            "swipe": command_swipe,
        }
        emit(handlers[args.command](args))
        return 0
    except CliFailure as exc:
        payload: dict[str, Any] = {
            "ok": False,
            "command": command,
            "error": {"code": exc.code, "message": exc.message},
        }
        if exc.details:
            payload["error"]["details"] = exc.details
        emit(payload)
        return exc.exit_code
    except KeyboardInterrupt:
        emit(
            {
                "ok": False,
                "command": command,
                "error": {
                    "code": "interrupted",
                    "message": "Operation interrupted before completion",
                },
            }
        )
        return 130
    except BrokenPipeError:
        return 0
    except Exception as exc:  # Keep unexpected failures machine-readable and nonzero.
        emit(
            {
                "ok": False,
                "command": command,
                "error": {
                    "code": "internal_error",
                    "message": "Unexpected failure; no successful result can be assumed",
                    "details": {"type": type(exc).__name__, "reason": str(exc)},
                },
            }
        )
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
