#!/usr/bin/env python3
"""Audit the self-contained community Tavo skill skeleton."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*([^\s]+)\s*$", re.MULTILINE)
RELATIVE_LINK_RE = re.compile(r"`((?:references|scripts|assets)/[^`]+)`")
LEGACY_TRIGGER_RE = re.compile(re.escape("$" + "tavo") + r"(?!-skill)\b")
DEFAULT_PROMPT_TRIGGER_RE = re.compile(
    r"^\s+default_prompt:\s*[^\n]*" + re.escape("$tavo-skill") + r"[^\n]*$", re.MULTILINE
)
INITIALIZATION_REMNANT_RE = re.compile(r"^\s*(?:TODO|TBD)(?:\s|:|$)|\[TODO\]", re.IGNORECASE | re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def distributable_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def distributable_entries(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if ".git" not in path.relative_to(root).parts
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the community Tavo skill skeleton.")
    parser.add_argument("skill_dir", nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = Path(args.skill_dir).expanduser().resolve()

    errors: list[str] = []
    skill_md = root / "SKILL.md"
    agent_yaml = root / "agents/openai.yaml"
    refs_dir = root / "references"
    scripts_dir = root / "scripts"
    assets_dir = root / "assets"

    for required in (skill_md, agent_yaml, refs_dir, scripts_dir, assets_dir):
        if not required.exists():
            errors.append(f"missing required path: {relative(required, root)}")

    skill_text = read_text(skill_md) if skill_md.is_file() else ""
    frontmatter = FRONTMATTER_RE.search(skill_text)
    if not frontmatter:
        errors.append("SKILL.md must begin with YAML frontmatter")
    else:
        name_match = NAME_RE.search(frontmatter.group(1))
        if not name_match or name_match.group(1) != "tavo-skill":
            errors.append("SKILL.md frontmatter name must be tavo-skill")

    agent_text = read_text(agent_yaml) if agent_yaml.is_file() else ""
    if not DEFAULT_PROMPT_TRIGGER_RE.search(agent_text):
        errors.append("agents/openai.yaml default_prompt must include $tavo-skill")

    all_entries = distributable_entries(root) if root.exists() else []
    for path in all_entries:
        if path.is_symlink():
            errors.append(f"symlinks are not allowed in the package: {relative(path, root)}")

    all_files = distributable_files(root) if root.exists() else []
    for path in all_files:
        text = read_text(path) if path.suffix.lower() in {".md", ".yaml", ".yml", ".py", ".js", ".mjs", ".json", ".html"} else ""
        rel_path = relative(path, root)
        if text and LEGACY_TRIGGER_RE.search(text):
            errors.append(f"legacy trigger found: {rel_path}")
        if path.suffix.lower() in {".md", ".yaml", ".yml"} and INITIALIZATION_REMNANT_RE.search(text):
            errors.append(f"initialization remnant found: {rel_path}")

    indexed_text = skill_text
    reference_files = sorted(refs_dir.rglob("*.md")) if refs_dir.is_dir() else []
    for path in reference_files:
        rel = relative(path, root)
        if rel not in indexed_text:
            errors.append(f"reference not indexed by SKILL.md: {rel}")

    reference_text = "\n".join(read_text(path) for path in reference_files)
    script_files = sorted(path for path in scripts_dir.iterdir() if path.is_file()) if scripts_dir.is_dir() else []
    for path in script_files:
        rel = relative(path, root)
        if rel not in skill_text and rel not in reference_text:
            errors.append(f"script not explained by SKILL.md or references: {rel}")

    for owner in [skill_md, *reference_files]:
        if not owner.is_file():
            continue
        for linked in RELATIVE_LINK_RE.findall(read_text(owner)):
            clean = linked.split("#", 1)[0]
            if any(token in clean for token in ("<", ">", "*")):
                continue
            target = root / clean
            if not target.exists():
                errors.append(f"broken relative path in {relative(owner, root)}: {clean}")

    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("audit_skill_skeleton_ok")
    print(f"references={len(reference_files)}")
    print(f"scripts={len(script_files)}")
    print(f"assets={len([path for path in assets_dir.rglob('*') if path.is_file()])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
