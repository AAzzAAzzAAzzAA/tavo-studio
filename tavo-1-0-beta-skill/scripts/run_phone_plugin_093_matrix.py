#!/usr/bin/env python3
"""Plan and stage the versioned Tavo 0.93 plugin matrix.

All offline modes are device/network free. The live CLI is an intentionally
blocked skeleton: it validates explicit identity and authorization, reserves a
durable no-resend intent, and never contacts ADB or MCP until a reviewed live
adapter is implemented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tavo_093_runner_core as core


KIND = "plugin-093"
DEFAULT_RUN_ID = "T093-PLUGIN-PLAN"
SCRIPT_PATH = Path(__file__).resolve()
CORE_PATH = Path(core.__file__).resolve()


def build_cases() -> list[core.CaseSpec]:
    return [
        core.CaseSpec(
            "P93-01",
            "Strict 0.93 readiness and isolated-chat anchor",
            "readiness",
            "read-only",
            ("schema", "restoration"),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-02",
            "Spec 2 root manifest and entry package",
            "plugin-runtime",
            "medium",
            ("schema", "roundtrip"),
            ("P93-01",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-03",
            "SemVer acceptance and rejection matrix",
            "plugin-runtime",
            "medium",
            ("schema", "roundtrip"),
            ("P93-02",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-04",
            "minAppVersion boundary and exact readback",
            "plugin-runtime",
            "medium",
            ("schema", "roundtrip"),
            ("P93-02",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-05",
            "Plugin internationalization locale and fallback matrix",
            "plugin-runtime",
            "medium",
            ("schema", "ui", "persistence"),
            ("P93-02",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-06",
            "Spec 1 compatibility and migration boundary",
            "plugin-runtime",
            "medium",
            ("schema", "roundtrip"),
            ("P93-02",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-07",
            "Root wrapper and development archive imports",
            "plugin-runtime",
            "medium",
            ("roundtrip",),
            ("P93-02",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-08",
            "Version update preserves config enabled state and contributions",
            "plugin-runtime",
            "medium",
            ("persistence", "roundtrip"),
            ("P93-03", "P93-05"),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-09",
            "Hooks input generation and TTS deterministic regression",
            "deterministic-request",
            "medium",
            ("request", "persistence"),
            ("P93-08",),
            matrix_items=("A",),
        ),
        core.CaseSpec(
            "P93-10",
            "Backup B restores spec 2 i18n config and runtime",
            "backup-restore",
            "high",
            ("roundtrip", "restoration"),
            ("P93-08", "P93-09"),
            destructive=True,
            notes="Run last; native restore may restart Tavo.",
            matrix_items=("J",),
        ),
        core.CaseSpec(
            "P93-11",
            "Exact plugin and protected-user-state restoration",
            "final-restoration",
            "medium",
            ("restoration",),
            ("P93-10",),
            matrix_items=("J",),
        ),
    ]


def code_hash() -> str:
    return core.runner_hash((SCRIPT_PATH, CORE_PATH))


def selected_cases(requested: str) -> list[core.CaseSpec]:
    return core.select_cases(build_cases(), requested)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tavo 0.93 plugin matrix skeleton")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--self-check", action="store_true")
    actions.add_argument("--print-plan", action="store_true")
    actions.add_argument("--prepare", action="store_true")
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--resume", action="store_true")
    actions.add_argument("--final-gate", action="store_true")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--case-keys", default="")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--device", default="")
    parser.add_argument("--endpoint-json", default="")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--isolated-chat-id", type=int, default=0)
    parser.add_argument("--protected-chat-id", type=int, default=0)
    return parser


def execute_phase(args: argparse.Namespace, phase: str) -> dict:
    return core.stage_unwired_live_phase(
        args,
        kind=KIND,
        code_hash=code_hash(),
        phase=phase,
    )


def main() -> int:
    args = build_parser().parse_args()
    try:
        cases = selected_cases(args.case_keys)
        digest = code_hash()
        if args.self_check:
            result = core.self_check(KIND, args.run_id, cases, digest)
        elif args.print_plan:
            core.validate_run_id(args.run_id)
            failures = core.validate_catalog(cases)
            if failures:
                raise RuntimeError(f"invalid case catalog: {failures}")
            result = core.plan_record(KIND, args.run_id, cases, digest)
        elif args.prepare:
            if not args.artifact_dir:
                raise RuntimeError("--prepare requires --artifact-dir")
            result = core.prepare_bundle(
                Path(args.artifact_dir),
                kind=KIND,
                run_id=args.run_id,
                cases=cases,
                code_hash=digest,
            )
        elif args.execute:
            result = execute_phase(args, "execute")
        elif args.resume:
            result = execute_phase(args, "resume")
        else:
            result = core.run_final_gate(
                args,
                kind=KIND,
                code_hash=digest,
                cases=cases,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if isinstance(result, dict) and result.get("status") == "blocked":
            return 3
        return 0 if result.get("ok", result.get("passed", True)) else 1
    except Exception as exc:  # noqa: BLE001 - fail closed with one stable error
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
