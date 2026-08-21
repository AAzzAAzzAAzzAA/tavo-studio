#!/usr/bin/env python3
"""Validate community Tavo artifacts with deterministic stdlib checks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tpg_spec2 import (
    is_safe_package_path as _shared_safe_package_path,
    validate_localization_catalogs,
    validate_manifest_semantics,
)


SECRET_RE = re.compile(
    r"(?:Bearer\s+(?!<(?:redacted|token)>)[A-Za-z0-9._~+/=-]{8,}|"
    r"sk-(?!EXAMPLE|TEST|REDACTED)[A-Za-z0-9_-]{16,}|"
    r"AIza[0-9A-Za-z_-]{20,}|"
    r"api[_-]?key['\"]?\s*[:=]\s*['\"](?!<(?:redacted|secret)>)[^'\"]{8,})",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_character_book(data: Any, errors: list[str]) -> None:
    require(isinstance(data, dict), "character_book must be an object", errors)
    if not isinstance(data, dict):
        return
    entries = data.get("entries")
    require(isinstance(entries, list), "character_book.entries must be an array", errors)
    if not isinstance(entries, list):
        return
    for index, entry in enumerate(entries):
        require(isinstance(entry, dict), f"character_book.entries[{index}] must be an object", errors)
        if isinstance(entry, dict):
            require(
                isinstance(entry.get("content"), str) and bool(entry["content"].strip()),
                f"character_book.entries[{index}].content must be non-empty",
                errors,
            )


def validate_card(data: dict[str, Any], errors: list[str]) -> None:
    require(data.get("spec") == "chara_card_v2", "card spec must be chara_card_v2", errors)
    require(str(data.get("spec_version", "")).startswith("2."), "card spec_version must start with 2.", errors)
    card = data.get("data")
    require(isinstance(card, dict), "card data must be an object", errors)
    if not isinstance(card, dict):
        return
    for key in ("name", "description", "first_mes"):
        require(
            isinstance(card.get(key), str) and bool(card[key].strip()),
            f"card data.{key} must be a non-empty string",
            errors,
        )
    if "character_book" in card:
        validate_character_book(card["character_book"], errors)


def validate_worldbook(data: dict[str, Any], errors: list[str]) -> None:
    require(isinstance(data.get("name"), str) and bool(data["name"].strip()), "worldbook name must be non-empty", errors)
    entries = data.get("entries")
    require(isinstance(entries, (list, dict)), "worldbook entries must be an array or object", errors)
    iterable = entries if isinstance(entries, list) else list(entries.values()) if isinstance(entries, dict) else []
    require(bool(iterable), "worldbook must contain at least one entry", errors)
    for index, entry in enumerate(iterable):
        require(isinstance(entry, dict), f"worldbook entry {index} must be an object", errors)
        if isinstance(entry, dict):
            require(
                isinstance(entry.get("content"), str) and bool(entry["content"].strip()),
                f"worldbook entry {index} content must be non-empty",
                errors,
            )


def validate_regex_fixture(data: dict[str, Any], errors: list[str]) -> None:
    rules = data.get("rules")
    cases = data.get("cases")
    require(isinstance(rules, list) and bool(rules), "regex fixture rules must be a non-empty array", errors)
    require(isinstance(cases, list) and bool(cases), "regex fixture cases must be a non-empty array", errors)
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict):
            errors.append("regex rule must be an object")
            continue
        rule_id = rule.get("id", "<unknown>")
        require(isinstance(rule.get("id"), str) and bool(rule["id"]), "regex rule id is required", errors)
        require(isinstance(rule.get("pattern"), str), f"regex rule {rule_id} pattern must be a string", errors)
        try:
            re.compile(rule.get("pattern", ""))
        except re.error as exc:
            errors.append(f"regex rule {rule_id} does not compile in the fixture runner: {exc}")


def is_safe_package_path(value: Any) -> bool:
    return _shared_safe_package_path(value)


def resolve_tpg_entry(data: dict[str, Any]) -> tuple[str | None, Any]:
    if "entry" in data:
        return "entry", data.get("entry")
    scripts = data.get("scripts")
    if isinstance(scripts, dict) and "actions" in scripts:
        return "scripts.actions", scripts.get("actions")
    return None, None


def validate_tpg_manifest(data: dict[str, Any], errors: list[str], *, plugin_root: Path | None = None) -> None:
    analysis = validate_manifest_semantics(data, errors)
    source, _ = resolve_tpg_entry(data)
    if analysis.input_actions or analysis.sidebar_actions:
        require(
            source is not None,
            "plugin entry is required for inputActions/sidebar (legacy scripts.actions is accepted)",
            errors,
        )
    if plugin_root is not None:
        validate_localization_catalogs(plugin_root, analysis, errors)


def scan_secret_text(path: Path, errors: list[str]) -> None:
    if SECRET_RE.search(path.read_text(encoding="utf-8", errors="replace")):
        errors.append(f"possible secret found in {path}")


def infer_kind(path: Path, data: Any) -> str:
    name = path.name.lower()
    if "regex" in name:
        return "regex-fixture"
    if "worldbook" in name or "lorebook" in name:
        return "worldbook"
    if name in {"tavo-plugin.json", "plugin.json", "manifest.json"}:
        return "tpg-manifest"
    if isinstance(data, dict) and data.get("spec") == "chara_card_v2":
        return "card"
    return "json"


def validate(path: Path, kind: str | None) -> list[str]:
    errors: list[str] = []
    scan_secret_text(path, errors)
    data = load_json(path)
    selected = kind or infer_kind(path, data)
    require(isinstance(data, dict), f"{selected} must be a JSON object", errors)
    if not isinstance(data, dict):
        return errors
    if selected == "card":
        validate_card(data, errors)
    elif selected == "worldbook":
        validate_worldbook(data, errors)
    elif selected == "regex-fixture":
        validate_regex_fixture(data, errors)
    elif selected == "tpg-manifest":
        require(path.name == "manifest.json", "Tavo plugin manifest filename must be manifest.json", errors)
        validate_tpg_manifest(data, errors, plugin_root=path.parent)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local Tavo artifacts.")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--kind", choices=["card", "worldbook", "regex-fixture", "tpg-manifest", "json"])
    args = parser.parse_args()

    failures = 0
    for raw in args.paths:
        path = Path(raw).expanduser()
        try:
            errors = validate(path, args.kind)
        except Exception as exc:  # noqa: BLE001 - report malformed inputs as validation failures
            errors = [str(exc)]
        if errors:
            failures += 1
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
