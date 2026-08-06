#!/usr/bin/env python3
"""Compare two redacted raw Tavo MCP surface dumps.

The inputs are the ``mcp_surface.json`` files emitted by dump_mcp_surface.py.
Only public discovery data is compared; endpoint and authorization fields are
never copied into the report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


COLLECTIONS = {
    "tools": ("tools/list", "tools", "name"),
    "resources": ("resources/list", "resources", "uri"),
    "resourceTemplates": (
        "resources/templates/list",
        "resourceTemplates",
        "uriTemplate",
    ),
    "prompts": ("prompts/list", "prompts", "name"),
}

TOOL_COMPARE_FIELDS = (
    "title",
    "description",
    "inputSchema",
    "outputSchema",
    "annotations",
)


class SurfaceError(ValueError):
    """Raised when a dump does not contain the expected discovery shape."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SurfaceError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SurfaceError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SurfaceError(f"surface root must be an object: {path}")
    return payload


def extract_collection(
    payload: dict[str, Any], call_name: str, result_name: str, identity: str
) -> dict[str, dict[str, Any]]:
    calls = payload.get("calls")
    if not isinstance(calls, dict):
        raise SurfaceError("missing object: calls")
    response = calls.get(call_name)
    if not isinstance(response, dict):
        raise SurfaceError(f"missing response: calls.{call_name}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise SurfaceError(f"missing result object: calls.{call_name}.result")
    rows = result.get(result_name)
    if not isinstance(rows, list):
        raise SurfaceError(
            f"missing list: calls.{call_name}.result.{result_name}"
        )

    indexed: dict[str, dict[str, Any]] = {}
    for offset, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SurfaceError(f"{result_name}[{offset}] must be an object")
        key = row.get(identity)
        if not isinstance(key, str) or not key:
            if result_name == "resourceTemplates":
                key = row.get("name")
            if not isinstance(key, str) or not key:
                raise SurfaceError(
                    f"{result_name}[{offset}] lacks non-empty {identity}"
                )
        if key in indexed:
            raise SurfaceError(f"duplicate {result_name} identity: {key}")
        indexed[key] = row
    return indexed


def surface_index(payload: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        label: extract_collection(payload, call_name, result_name, identity)
        for label, (call_name, result_name, identity) in COLLECTIONS.items()
    }


def changed_tool_fields(
    before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    return [field for field in TOOL_COMPARE_FIELDS if before.get(field) != after.get(field)]


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old = surface_index(before)
    new = surface_index(after)
    collections: dict[str, Any] = {}

    for label in COLLECTIONS:
        old_keys = set(old[label])
        new_keys = set(new[label])
        collections[label] = {
            "beforeCount": len(old_keys),
            "afterCount": len(new_keys),
            "added": sorted(new_keys - old_keys),
            "removed": sorted(old_keys - new_keys),
        }

    changed_tools = []
    for name in sorted(set(old["tools"]) & set(new["tools"])):
        fields = changed_tool_fields(old["tools"][name], new["tools"][name])
        if fields:
            changed_tools.append({"name": name, "changedFields": fields})

    old_summary = before.get("summary") if isinstance(before.get("summary"), dict) else {}
    new_summary = after.get("summary") if isinstance(after.get("summary"), dict) else {}
    return {
        "schemaVersion": 1,
        "before": {
            "serverInfo": old_summary.get("serverInfo"),
            "requestedProtocolVersion": old_summary.get("requestedProtocolVersion"),
            "negotiatedProtocolVersion": old_summary.get("negotiatedProtocolVersion"),
        },
        "after": {
            "serverInfo": new_summary.get("serverInfo"),
            "requestedProtocolVersion": new_summary.get("requestedProtocolVersion"),
            "negotiatedProtocolVersion": new_summary.get("negotiatedProtocolVersion"),
        },
        "collections": collections,
        "changedCommonTools": changed_tools,
        "changedCommonToolCount": len(changed_tools),
    }


def text_report(report: dict[str, Any]) -> str:
    lines = []
    for side in ("before", "after"):
        meta = report[side]
        server = meta.get("serverInfo") or {}
        version = server.get("version") if isinstance(server, dict) else None
        lines.append(
            f"{side}: version={version or 'unknown'} "
            f"protocol={meta.get('negotiatedProtocolVersion') or 'unknown'}"
        )
    for label, row in report["collections"].items():
        lines.append(f"{label}: {row['beforeCount']} -> {row['afterCount']}")
        if row["added"]:
            lines.append("  added: " + ", ".join(row["added"]))
        if row["removed"]:
            lines.append("  removed: " + ", ".join(row["removed"]))
    lines.append(
        f"changed common tools: {report['changedCommonToolCount']}"
    )
    for row in report["changedCommonTools"]:
        lines.append(f"  {row['name']}: {', '.join(row['changedFields'])}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="older raw mcp_surface.json")
    parser.add_argument("after", type=Path, help="newer raw mcp_surface.json")
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", dest="output_format"
    )
    parser.add_argument("--output", type=Path, help="write report to this path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        report = compare(load_json(args.before), load_json(args.after))
    except SurfaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output_format == "json":
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = text_report(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
