#!/usr/bin/env python3
"""Master plan and durable phase gate for the complete Tavo 0.93 epoch.

This file composes the versioned plugin and non-plugin catalogs. It does not
contain a live transport adapter: authorized execute/resume calls reserve a
durable blocked intent and make no ADB, MCP, provider, or model request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import run_phone_093_nonplugin_matrix as nonplugin
import run_phone_plugin_093_matrix as plugin
import tavo_093_runner_core as core
import tavo_093_full_catalog as full_catalog


KIND = "master-093"
DEFAULT_RUN_ID = "T093-MASTER-PLAN"
SCRIPT_PATH = Path(__file__).resolve()
CORE_PATH = Path(core.__file__).resolve()
PLUGIN_PATH = Path(plugin.__file__).resolve()
NONPLUGIN_PATH = Path(nonplugin.__file__).resolve()
FULL_CATALOG_PATH = Path(full_catalog.__file__).resolve()
ORCHESTRATION_PHASES = (
    {
        "phase": "00-offline",
        "purpose": "catalog, script hash, tests, and no-contact self-check",
        "stopOnFailure": True,
    },
    {
        "phase": "10-readiness-anchor-backup-a",
        "purpose": "strict ADB/MCP identity, dynamic protected chat, full state anchor, private Backup A",
        "stopOnFailure": True,
    },
    {
        "phase": "20-ui-readonly",
        "purpose": "fresh XML/PNG inventory without saving settings",
        "stopOnFailure": True,
    },
    {
        "phase": "30-ui-persistence",
        "purpose": "bounded save, reopen, independent readback, and immediate restoration",
        "stopOnFailure": True,
    },
    {
        "phase": "40-deterministic-request",
        "purpose": "one durable intent to one redacted fixture request",
        "stopOnFailure": True,
    },
    {
        "phase": "50-plugin-runtime",
        "purpose": "spec 2 staging then isolated runtime cases",
        "stopOnFailure": True,
    },
    {
        "phase": "60-real-provider-blocked",
        "purpose": "explicitly authorized real model, ASR, and human audio evidence",
        "blockedByDefault": True,
        "stopOnFailure": True,
    },
    {
        "phase": "70-backup-b-restore",
        "purpose": "late destructive native restore only after lower-risk gates pass",
        "stopOnFailure": True,
    },
    {
        "phase": "80-final-restoration-gate",
        "purpose": "exact state hashes plus fresh strict ADB/MCP gates",
        "stopOnFailure": True,
    },
)


def build_cases() -> list[core.CaseSpec]:
    # The two versioned sub-runners provide guarded phase-level cases.  The
    # fine-grained catalog comes first so every approved A-J row has its own
    # terminal result rather than inheriting a broad umbrella verdict.
    cases = [
        *full_catalog.build_cases(),
        *nonplugin.build_cases(),
        *plugin.build_cases(),
    ]
    cases.append(
        core.CaseSpec(
            "M93-99",
            "Master exact restoration and strict final gate",
            "final-restoration",
            "medium",
            ("restoration",),
            ("N93-12", "P93-11"),
            matrix_items=("J",),
        )
    )
    return cases


def code_hash() -> str:
    return core.runner_hash(
        (SCRIPT_PATH, CORE_PATH, PLUGIN_PATH, NONPLUGIN_PATH, FULL_CATALOG_PATH)
    )


def selected_cases(requested: str) -> list[core.CaseSpec]:
    return core.select_cases(build_cases(), requested)


def master_plan(run_id: str, cases: list[core.CaseSpec], digest: str) -> dict:
    plan = core.plan_record(KIND, run_id, cases, digest)
    plan_without_hash = {key: value for key, value in plan.items() if key != "planHash"}
    plan_without_hash["orchestrationPhases"] = list(ORCHESTRATION_PHASES)
    return {
        **plan_without_hash,
        "planHash": core.stable_hash(plan_without_hash),
    }


def prepare_master(
    artifact_dir: Path,
    run_id: str,
    cases: list[core.CaseSpec],
    digest: str,
) -> dict:
    result = core.prepare_bundle(
        artifact_dir,
        kind=KIND,
        run_id=run_id,
        cases=cases,
        code_hash=digest,
    )
    root = Path(result["artifactDir"])
    plan = master_plan(run_id, cases, digest)
    core.durable_json(root / "plan.json", plan)
    manifest = core.load_json(root / "run-manifest.json")
    manifest["planHash"] = plan["planHash"]
    manifest["orchestrationPhases"] = [row["phase"] for row in ORCHESTRATION_PHASES]
    core.durable_json(root / "run-manifest.json", manifest)
    result["manifest"] = manifest
    result["plan"] = plan
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tavo 0.93 full epoch master skeleton")
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
            result["orchestrationPhaseCount"] = len(ORCHESTRATION_PHASES)
        elif args.print_plan:
            core.validate_run_id(args.run_id)
            failures = core.validate_catalog(cases)
            if failures:
                raise RuntimeError(f"invalid case catalog: {failures}")
            result = master_plan(args.run_id, cases, digest)
        elif args.prepare:
            if not args.artifact_dir:
                raise RuntimeError("--prepare requires --artifact-dir")
            result = prepare_master(Path(args.artifact_dir), args.run_id, cases, digest)
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
                required_matrix_items=core.MATRIX_ITEMS,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if isinstance(result, dict) and result.get("status") == "blocked":
            return 3
        return 0 if result.get("ok", result.get("passed", True)) else 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
