#!/usr/bin/env python3
"""Comprehensive, self-contained audit for the community Tavo skill."""

from __future__ import annotations

import argparse
import ast
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from validate_tavo_artifact import validate as validate_artifact
from validate_tpg_package import validate_package


REQUIRED_REFERENCES = {
    "references/00-capability-boundaries.md",
    *{f"references/{number:02d}-{name}.md" for number, name in [
        (2, "capabilities-overview"),
        (3, "characters-cards-personas"),
        (4, "chat-workflows"),
        (5, "prompt-authoring"),
        (6, "macros-ejs"),
        (7, "rendering-tavojs"),
        (8, "plugins-tpg"),
        (9, "media-voice-image"),
        (10, "app-settings-data"),
        (11, "mcp-runtime"),
        (13, "creation-craft-workflows"),
        (16, "capability-answer-playbook"),
        (17, "authoring-blueprints"),
        (18, "ar-tavojs-plugin-patterns"),
        (19, "debugging-pitfalls"),
        (21, "worldbook-entry-semantics"),
        (22, "preset-prompt-injection"),
        (23, "regex-execution-pipeline"),
        (24, "character-opening-and-examples"),
        (25, "ejs-tavojs-plugin-boundaries"),
        (27, "prompt-lab"),
        (29, "creation-intake-interview"),
        (30, "prose-detone"),
        (31, "prose-detone-catalog"),
        (32, "prose-detone-narrative"),
        (33, "quick-card-funnel"),
    ]},
}

REQUIRED_SCRIPTS = {
    f"scripts/{name}"
    for name in [
        "audit_skill_skeleton.py",
        "audit_tavo_skill.py",
        "compare_roundtrip_export.py",
        "embed_st_card_png.mjs",
        "extract_st_card_png.mjs",
        "generate_from_template.py",
        "png-card-lib.mjs",
        "run_regex_fixtures.py",
        "scan_deprecated_tavojs.py",
        "tavo_ejs_worker.mjs",
        "tavo_mcp_client.py",
        "tavo_prompt_lab.py",
        "tavo_request_capture_gateway.py",
        "tavo_virtual_provider.py",
        "test_tavo_prompt_lab.py",
        "test_tavo_mcp_client.py",
        "test_tavo_request_capture_gateway.py",
        "test_tavo_virtual_provider.py",
        "test_validate_tpg_package.py",
        "tpg_spec2.py",
        "validate_tavo_artifact.py",
        "validate_tpg_package.py",
        "worldbook_to_character_book.mjs",
    ]
}

REQUIRED_ASSETS = {
    "assets/fixtures/minimal-card.json",
    "assets/fixtures/plugin-ambiguous/one/manifest.json",
    "assets/fixtures/plugin-ambiguous/two/manifest.json",
    "assets/fixtures/plugin-dangerous-path/manifest.json",
    "assets/fixtures/plugin-dual/entry.js",
    "assets/fixtures/plugin-dual/manifest.json",
    "assets/fixtures/plugin-hook-only/entry.js",
    "assets/fixtures/plugin-hook-only/manifest.json",
    "assets/fixtures/plugin-legacy/legacy-actions.js",
    "assets/fixtures/plugin-legacy/manifest.json",
    "assets/fixtures/plugin-minimal/entry.js",
    "assets/fixtures/plugin-minimal/manifest.json",
    "assets/fixtures/plugin-minimal/ui/panel.html",
    "assets/fixtures/plugin-missing-entry/manifest.json",
    "assets/fixtures/plugin-nested/wrapper/entry.js",
    "assets/fixtures/plugin-nested/wrapper/manifest.json",
    "assets/fixtures/regex-cleanup-fixture.json",
    "assets/fixtures/worldbook-basic.json",
    "assets/schemas/character-book.schema.json",
    "assets/schemas/regex-fixture.schema.json",
    "assets/schemas/st-card-v2.schema.json",
    "assets/schemas/tpg-manifest.schema.json",
    "assets/schemas/worldbook.schema.json",
    "assets/templates/character-card-minimal.json",
    "assets/templates/advanced-rendering-marker.html",
    "assets/templates/worldbook-minimal.json",
    "assets/templates/regex-fixture.json",
    "assets/templates/prompt-lab-case.json",
    "assets/templates/prompt-lab-session-case.json",
    "assets/templates/plugin-minimal/entry.js",
    "assets/templates/plugin-minimal/locales/en.json",
    "assets/templates/plugin-minimal/locales/zh-CN.json",
    "assets/templates/plugin-minimal/manifest.json",
    "assets/templates/plugin-minimal/ui/panel.html",
}

PERSONAL_PATTERNS = {
    "personal macOS path": re.compile(re.escape("/" + "Users/") + r"[^/\s`\"']+"),
    "personal Linux path": re.compile(
        re.escape("/" + "home/") + r"(?!user\b|example\b)[^/\s`\"']+"
    ),
    "messaging-account identifier": re.compile(
        r"\b" + re.escape("wx" + "id") + r"[_-][A-Za-z0-9_-]+", re.IGNORECASE
    ),
}

RESULT_ONLY_SECTION_RE = re.compile(
    r"^#{1,3}\s+(?:"
    + "Official" + r"\s+(?:Pages?|URL\s+Map)|"
    + "Evidence" + r"\s+(?:Snapshot|Set|Ledger)|"
    + "Source" + r"\s+And\s+Behavior\s+Order|"
    + "Refresh" + r"\s+Commands|"
    + "证据" + r"(?:快照|索引))\s*$",
    re.IGNORECASE | re.MULTILINE,
)
DISCOVERY_PROCESS_RE = re.compile(
    r"(?:"
    + "retained" + r"\s+(?:(?:phone|provider|wire|Tavo)\s+)?captures?|"
    + r"\b" + "phone" + r"\s+captures?|"
    + r"\b" + "provider" + r"\s+captures?|"
    + r"\b" + "wire" + r"\s+(?:captures?|oracle)|"
    + "live" + r"[- ]calibrated|"
    + "evidence" + r"[- ]bounded|"
    + "fresh" + r"\s+(?:crawl|fetch)|"
    + "official" + r"\s+(?:docs?|surfaces?)\s+(?:crawl|conflict)|"
    + "抓" + "取" + r"|" + "取" + "证" + r")",
    re.IGNORECASE,
)
LEGACY_SOURCE_WORDING_RE = re.compile(
    r"\bthe\s+" + "old" + r"\s+[A-Za-z0-9_-]*(?:\s+[A-Za-z0-9_-]+){0,3}\s+"
    + "skill" + r"\s+(?:used|said|documented)\b",
    re.IGNORECASE,
)
PRIVATE_BUNDLE_PATH_RE = re.compile(
    r"(?:^|[`'\"\s])(?:artifact|evidence|capture)s?/[A-Za-z0-9_.-]",
    re.IGNORECASE,
)
HTTP_URL_RE = re.compile(r"https?://[^\s)`>\"]+")
LEGACY_TRIGGER_RE = re.compile(re.escape("$" + "tavo") + r"(?!-skill)\b")
DEFAULT_PROMPT_TRIGGER_RE = re.compile(
    r"^\s+default_prompt:\s*[^\n]*" + re.escape("$tavo-skill") + r"[^\n]*$", re.MULTILINE
)
IPV4_RE = re.compile(r"(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9.])")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SECRET_RE = re.compile(
    r"(?:Bearer\s+(?!(?:requires|token|authentication)\b)[A-Za-z0-9._~+/=-]{12,}|sk-[A-Za-z0-9_-]{16,}|"
    r"AIza[0-9A-Za-z_-]{20,})",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".js", ".mjs", ".html"}
ALLOWED_URL_HOSTS = {
    "127.0.0.1",
    "example.invalid",
    "json-schema.org",
    "localhost",
    "provider.example",
    "replace-with-provider.example",
}
ALLOWED_TEST_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("127.0.0.0/8", "::1/128", "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
)
FULL_TEST_COMMAND = "python3 -B -W error::ResourceWarning -m unittest discover -s scripts -p 'test_*.py'"

REQUIRED_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    *REQUIRED_REFERENCES,
    *REQUIRED_SCRIPTS,
    *REQUIRED_ASSETS,
}
REQUIRED_DIRECTORIES = {
    parent.as_posix()
    for relative in REQUIRED_FILES
    for parent in Path(relative).parents
    if parent.as_posix() != "."
}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def package_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def package_entries(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if ".git" not in path.relative_to(root).parts
    )


def is_allowed_placeholder_secret(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("EXAMPLE", "TEST", "REDACTED", "PLACEHOLDER", "HIDDEN")) or "<" in value


def check_private_ipv4(text: str) -> list[str]:
    findings: list[str] = []
    for raw in IPV4_RE.findall(text):
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if raw == "0.0.0.0" or any(address in network for network in ALLOWED_TEST_NETWORKS):
            continue
        if address.is_private or address.is_link_local:
            findings.append(raw)
    return findings


def check_package_shape(root: Path, errors: list[str]) -> tuple[list[Path], list[Path], list[Path]]:
    for required in sorted(REQUIRED_FILES):
        if not (root / required).is_file():
            errors.append(f"missing required file: {required}")

    for path in package_entries(root):
        relative = rel(path, root)
        parts = path.relative_to(root).parts
        if path.is_symlink():
            errors.append(f"symlinks are not allowed in the package: {relative}")
            continue
        if any(part.startswith(".") for part in parts):
            errors.append(f"hidden package entry is not allowed: {relative}")
        if path.is_file() and relative not in REQUIRED_FILES:
            errors.append(f"unindexed community file: {relative}")
        if path.is_dir() and relative not in REQUIRED_DIRECTORIES:
            errors.append(f"unindexed community directory: {relative}")

    refs = sorted((root / "references").rglob("*.md"))
    scripts = sorted(path for path in (root / "scripts").iterdir() if path.is_file())
    assets = sorted(path for path in (root / "assets").rglob("*") if path.is_file())
    actual_refs = {rel(path, root) for path in refs}
    actual_scripts = {rel(path, root) for path in scripts}
    actual_assets = {rel(path, root) for path in assets}
    if actual_refs != REQUIRED_REFERENCES:
        for item in sorted(actual_refs - REQUIRED_REFERENCES):
            errors.append(f"unindexed community reference: {item}")
        for item in sorted(REQUIRED_REFERENCES - actual_refs):
            errors.append(f"required community reference absent: {item}")
    if actual_scripts != REQUIRED_SCRIPTS:
        for item in sorted(actual_scripts - REQUIRED_SCRIPTS):
            errors.append(f"unindexed community script: {item}")
        for item in sorted(REQUIRED_SCRIPTS - actual_scripts):
            errors.append(f"required community script absent: {item}")
    if actual_assets != REQUIRED_ASSETS:
        for item in sorted(actual_assets - REQUIRED_ASSETS):
            errors.append(f"unindexed community asset: {item}")
        for item in sorted(REQUIRED_ASSETS - actual_assets):
            errors.append(f"required community asset absent: {item}")
    return refs, scripts, assets


def check_text(root: Path, files: list[Path], refs: list[Path], errors: list[str]) -> None:
    for path in files:
        relative = rel(path, root)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            errors.append(f"unexpected non-text distributable file: {relative}")
            continue
        text = read_text(path)
        for label, pattern in PERSONAL_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{label} found in {relative}")
        if LEGACY_TRIGGER_RE.search(text):
            errors.append(f"legacy trigger found in {relative}")
        if RESULT_ONLY_SECTION_RE.search(text):
            errors.append(f"source/provenance section found in {relative}")
        if DISCOVERY_PROCESS_RE.search(text):
            errors.append(f"discovery-process wording found in {relative}")
        if LEGACY_SOURCE_WORDING_RE.search(text):
            errors.append(f"legacy source wording found in {relative}")
        if PRIVATE_BUNDLE_PATH_RE.search(text):
            errors.append(f"private bundle path found in {relative}")
        for match in SECRET_RE.finditer(text):
            if not is_allowed_placeholder_secret(match.group(0)):
                errors.append(f"credential-like value found in {relative}")
                break
        for email in EMAIL_RE.findall(text):
            if not email.lower().endswith(("@example.com", "@example.invalid")):
                errors.append(f"email address found in {relative}")
                break
        private_ips = check_private_ipv4(text)
        if private_ips:
            errors.append(f"private network address found in {relative}: {private_ips[0]}")
        for url in HTTP_URL_RE.findall(text):
            if "{" in url:
                host_match = re.match(r"https?://(?:\{[^}]+\}|(?P<host>\[[^]]+\]|[^/:]+))", url)
                if not host_match or host_match.group("host") is None:
                    continue
                host = host_match.group("host").strip("[]").lower()
            else:
                try:
                    host = (urlsplit(url).hostname or "").lower()
                except ValueError:
                    errors.append(f"invalid URL literal found in {relative}")
                    break
            allowed_test_address = False
            try:
                address = ipaddress.ip_address(host)
                allowed_test_address = any(address in network for network in ALLOWED_TEST_NETWORKS)
            except ValueError:
                pass
            if host not in ALLOWED_URL_HOSTS and not allowed_test_address:
                errors.append(f"non-placeholder URL found in {relative}")
                break


def check_syntax(root: Path, scripts: list[Path], assets: list[Path], errors: list[str]) -> None:
    if sys.version_info < (3, 10):
        errors.append("Python 3.10 or newer is required")
    for path in scripts:
        if path.suffix == ".py":
            try:
                ast.parse(read_text(path), filename=rel(path, root))
            except SyntaxError as exc:
                errors.append(f"Python syntax error in {rel(path, root)}: {exc}")

    node = shutil.which("node")
    if not node:
        errors.append("Node.js is required to check bundled JavaScript")
        return
    node_help = subprocess.run([node, "--help"], capture_output=True, text=True, check=False)
    help_text = f"{node_help.stdout}\n{node_help.stderr}"
    if node_help.returncode or "--permission" not in help_text or "--allow-fs-read" not in help_text:
        errors.append("Node.js must support --permission and --allow-fs-read")
    for path in [*scripts, *assets]:
        if path.suffix not in {".js", ".mjs"}:
            continue
        completed = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, check=False)
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            errors.append(f"JavaScript syntax error in {rel(path, root)}: {detail[-1] if detail else 'node --check failed'}")


def check_prompt_lab_templates(root: Path, errors: list[str]) -> None:
    script = root / "scripts/tavo_prompt_lab.py"
    for relative in (
        "assets/templates/prompt-lab-case.json",
        "assets/templates/prompt-lab-session-case.json",
    ):
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-B", str(script), "compile", "--case", str(root / relative)],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if completed.returncode:
            errors.append(f"Prompt Lab template compile failed: {relative}")
            continue
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            errors.append(f"Prompt Lab template returned invalid JSON: {relative}")
            continue
        if result.get("mode") == "compile-session":
            turns = result.get("turns")
            compiled_results = turns if isinstance(turns, list) and turns else []
        else:
            compiled_results = [result]
        if not compiled_results:
            errors.append(f"Prompt Lab template compiled without turns: {relative}")
            continue
        for index, compiled in enumerate(compiled_results, start=1):
            request = compiled.get("request") if isinstance(compiled, dict) else None
            messages = request.get("messages") if isinstance(request, dict) else None
            ejs = compiled.get("ejs") if isinstance(compiled, dict) else None
            unresolved = ejs.get("unresolvedSources") if isinstance(ejs, dict) else None
            if not isinstance(messages, list) or not messages:
                errors.append(f"Prompt Lab template turn {index} has no request messages: {relative}")
            if unresolved != []:
                errors.append(f"Prompt Lab template turn {index} has unresolved EJS: {relative}")


def check_json_and_artifacts(root: Path, assets: list[Path], errors: list[str]) -> None:
    for path in assets:
        if path.suffix != ".json":
            continue
        try:
            json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {rel(path, root)}: {exc}")

    cases = [
        ("assets/fixtures/minimal-card.json", "card"),
        ("assets/templates/character-card-minimal.json", "card"),
        ("assets/fixtures/worldbook-basic.json", "worldbook"),
        ("assets/templates/worldbook-minimal.json", "worldbook"),
        ("assets/fixtures/regex-cleanup-fixture.json", "regex-fixture"),
        ("assets/templates/regex-fixture.json", "regex-fixture"),
    ]
    for relative, kind in cases:
        for problem in validate_artifact(root / relative, kind):
            errors.append(f"{relative}: {problem}")

    for relative in ("assets/fixtures/plugin-minimal", "assets/templates/plugin-minimal"):
        result = validate_package(root / relative)
        for problem in result.errors:
            errors.append(f"{relative}: {problem}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the self-contained community Tavo skill.")
    parser.add_argument("skill_dir", nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = Path(args.skill_dir).expanduser().resolve()
    errors: list[str] = []

    refs, scripts, assets = check_package_shape(root, errors)
    files = package_files(root)
    check_text(root, files, refs, errors)
    check_syntax(root, scripts, assets, errors)
    check_json_and_artifacts(root, assets, errors)
    check_prompt_lab_templates(root, errors)

    skill_text = read_text(root / "SKILL.md") if (root / "SKILL.md").is_file() else ""
    if not re.search(r"^name:\s*tavo-skill\s*$", skill_text, re.MULTILINE):
        errors.append("SKILL.md frontmatter name must be tavo-skill")
    if FULL_TEST_COMMAND not in skill_text:
        errors.append("SKILL.md must retain the ResourceWarning-strict full test command")
    agent_text = read_text(root / "agents/openai.yaml") if (root / "agents/openai.yaml").is_file() else ""
    if not DEFAULT_PROMPT_TRIGGER_RE.search(agent_text):
        errors.append("agents/openai.yaml must invoke $tavo-skill")

    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("audit_tavo_skill_ok")
    print(f"references={len(refs)}")
    print(f"scripts={len(scripts)}")
    print(f"assets={len(assets)}")
    print(f"required_assets={len(REQUIRED_ASSETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
