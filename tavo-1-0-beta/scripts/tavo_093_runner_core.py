#!/usr/bin/env python3
"""Offline-safe primitives shared by the Tavo 0.93 runner skeletons."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


APP_VERSION = "0.93.0"
CONFIRMATION = "TAVO_093_ISOLATED_EXECUTION"
FINAL_CONFIRMATION = "TAVO_093_FINAL_GATE"
RUN_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,63}$")
CASE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9-]{2,31}$")
STAGES = (
    "readiness",
    "anchor-backup",
    "ui-readonly",
    "ui-persistence",
    "deterministic-request",
    "plugin-runtime",
    "real-provider",
    "backup-restore",
    "final-restoration",
)
PROOF_AXES = frozenset(
    {
        "schema",
        "ui",
        "persistence",
        "request",
        "roundtrip",
        "semantic",
        "manual",
        "restoration",
    }
)
RESTORATION_ASSERTIONS = (
    "protectedChatUntouched",
    "inputRestored",
    "apiRestored",
    "themeRestored",
    "voiceRestored",
    "asrRestored",
    "pluginRestored",
    "presetRestored",
    "bindingsRestored",
    "permissionsRestored",
    "fixturesStopped",
)
MATRIX_ITEMS = tuple("ABCDEFGHIJ")
TERMINAL_STATUSES = (
    "passed",
    "failed",
    "mixed",
    "blocked",
    "not-applicable",
)
RESULT_EVIDENCE_LEVELS = (
    "none",
    "offline",
    "deterministic-fixture",
    "device-local",
    "real-provider",
    "manual",
)
RESULT_COUNTER_FIELDS = (
    "realProviderRequestsAttempted",
    "realProviderRequestsCompleted",
    "realModelCallsAttempted",
    "realModelCallsCompleted",
    "manualHumanChecksCompleted",
)
RESULT_BOOLEAN_FIELDS = (
    "realCredentialsUsed",
    "deviceOrMcpContacted",
)
PROVIDER_MODES = (
    "virtual",
    "not-applicable",
    "blocked",
)
REQUEST_AXIS_STATUSES = (
    "passed",
    "failed",
    "blocked",
    "not-applicable",
    "not-evaluated",
)
MODEL_AXIS_STATUS = "not-evaluated"


@dataclass(frozen=True)
class CaseSpec:
    key: str
    title: str
    stage: str
    risk: str
    proof_axes: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    requires_real_model: bool = False
    manual: bool = False
    destructive: bool = False
    notes: str = ""
    matrix_items: tuple[str, ...] = ()

    def record(self) -> dict[str, Any]:
        record = asdict(self)
        return {
            "key": record["key"],
            "title": record["title"],
            "stage": record["stage"],
            "risk": record["risk"],
            "proofAxes": list(record["proof_axes"]),
            "dependencies": list(record["dependencies"]),
            "requiresRealModel": record["requires_real_model"],
            "manual": record["manual"],
            "destructive": record["destructive"],
            "notes": record["notes"],
            "matrixItems": list(record["matrix_items"]),
        }


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_run_id(run_id: str) -> None:
    if not RUN_ID_RE.fullmatch(run_id):
        raise RuntimeError("run id must be 3-64 uppercase ASCII letters, digits, dot, underscore, or dash")


def validate_catalog(cases: Iterable[CaseSpec]) -> list[str]:
    records = list(cases)
    errors: list[str] = []
    keys = [case.key for case in records]
    if len(keys) != len(set(keys)):
        errors.append("case keys must be unique")
    key_set = set(keys)
    positions = {key: index for index, key in enumerate(keys)}
    for case in records:
        if not CASE_KEY_RE.fullmatch(case.key):
            errors.append(f"{case.key}: invalid key")
        if case.stage not in STAGES:
            errors.append(f"{case.key}: unknown stage {case.stage}")
        if case.risk not in {"read-only", "low", "medium", "high"}:
            errors.append(f"{case.key}: unknown risk {case.risk}")
        if not case.proof_axes:
            errors.append(f"{case.key}: proof axes are required")
        unknown_axes = set(case.proof_axes) - PROOF_AXES
        if unknown_axes:
            errors.append(f"{case.key}: unknown proof axes {sorted(unknown_axes)}")
        if len(case.dependencies) != len(set(case.dependencies)):
            errors.append(f"{case.key}: duplicate dependency")
        if not case.matrix_items:
            errors.append(f"{case.key}: matrix items are required")
        if len(case.matrix_items) != len(set(case.matrix_items)):
            errors.append(f"{case.key}: duplicate matrix item")
        unknown_items = set(case.matrix_items) - set(MATRIX_ITEMS)
        if unknown_items:
            errors.append(f"{case.key}: unknown matrix items {sorted(unknown_items)}")
        for dependency in case.dependencies:
            if dependency not in key_set:
                errors.append(f"{case.key}: unknown dependency {dependency}")
            elif positions[dependency] >= positions[case.key]:
                errors.append(f"{case.key}: dependency {dependency} must appear earlier")
        if case.destructive and case.stage != "backup-restore":
            errors.append(f"{case.key}: destructive cases must remain in backup-restore")
    return errors


def select_cases(cases: Iterable[CaseSpec], requested: str) -> list[CaseSpec]:
    catalog = list(cases)
    if not requested:
        return catalog
    keys = [item.strip() for item in requested.split(",") if item.strip()]
    if len(keys) != len(set(keys)):
        raise RuntimeError("case selection contains duplicates")
    by_key = {case.key: case for case in catalog}
    unknown = [key for key in keys if key not in by_key]
    if unknown:
        raise RuntimeError(f"unknown case keys: {', '.join(unknown)}")
    closure = set(keys)
    changed = True
    while changed:
        changed = False
        for key in tuple(closure):
            for dependency in by_key[key].dependencies:
                if dependency not in closure:
                    closure.add(dependency)
                    changed = True
    return [case for case in catalog if case.key in closure]


def ensure_private_directory(path: Path, *, must_be_empty: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists() and (resolved.is_symlink() or not resolved.is_dir()):
        raise RuntimeError(f"artifact path must be a real directory: {resolved}")
    if resolved.exists() and must_be_empty and any(resolved.iterdir()):
        raise RuntimeError("artifact directory must be absent or empty")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved.chmod(0o700)
    return resolved


def durable_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    if exclusive:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON artifact must contain an object: {path}")
    return value


def runner_hash(paths: Iterable[Path]) -> str:
    records = [
        {"name": path.name, "sha256": file_sha256(path)}
        for path in sorted((item.resolve() for item in paths), key=lambda item: item.name)
    ]
    return stable_hash(records)


def plan_record(kind: str, run_id: str, cases: Iterable[CaseSpec], code_hash: str) -> dict[str, Any]:
    records = [case.record() for case in cases]
    plan = {
        "schemaVersion": "1.0.0",
        "appVersion": APP_VERSION,
        "kind": kind,
        "runId": run_id,
        "runnerHash": code_hash,
        "cases": records,
        "safety": {
            "providerMode": "virtual",
            "realModelRequestsSent": 0,
            "countsTowardKpi": False,
            "realProviderCredentialsUsed": False,
            "offlineModesContactDevice": False,
            "executeRequiresExplicitDevice": True,
            "executeRequiresPrivateEndpoint": True,
            "executeRequiresConfirmation": CONFIRMATION,
            "protectedChatMustDifferFromIsolatedChat": True,
            "missingLiveAdapterClassification": "blocked",
            "oneDurableIntentPerPhase": True,
            "finalGateNeverInfersMissingEvidence": True,
            "terminalCaseStatuses": list(TERMINAL_STATUSES),
            "completeWithFindingsIsAllowed": True,
            "liveAdapter": "not-wired",
        },
    }
    return {**plan, "planHash": stable_hash(plan)}


def result_contract() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "terminalStatuses": list(TERMINAL_STATUSES),
        "requiredFields": [
            "case",
            "matrixItems",
            "terminal",
            "status",
            "evidenceLevel",
            "providerMode",
            "realModelRequestsSent",
            "countsTowardKpi",
            "requestAssembly",
            "fixtureRoundtrip",
            "modelFormat",
            "modelSemantic",
            "realProviderCredentialsUsed",
            *RESULT_COUNTER_FIELDS,
            *RESULT_BOOLEAN_FIELDS,
        ],
        "counterFieldsAreNonNegativeIntegers": True,
        "completedCountersCannotExceedAttemptedCounters": True,
        "missingOrNonterminalResultBlocksCompletion": True,
        "terminalFindingsDoNotBlockCompletion": True,
    }


def validate_case_result(case: CaseSpec, result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("case") != case.key:
        errors.append(f"{case.key}: result case identity mismatch")
    if result.get("matrixItems") != list(case.matrix_items):
        errors.append(f"{case.key}: result matrix item identity mismatch")
    if result.get("terminal") is not True:
        errors.append(f"{case.key}: terminal must be true")
    status = result.get("status")
    if status not in TERMINAL_STATUSES:
        errors.append(f"{case.key}: status {status!r} is not terminal")
    if result.get("evidenceLevel") not in RESULT_EVIDENCE_LEVELS:
        errors.append(f"{case.key}: invalid evidenceLevel")
    if result.get("providerMode") not in PROVIDER_MODES:
        errors.append(f"{case.key}: invalid providerMode")
    if result.get("requestAssembly") not in REQUEST_AXIS_STATUSES:
        errors.append(f"{case.key}: invalid requestAssembly")
    if result.get("fixtureRoundtrip") not in REQUEST_AXIS_STATUSES:
        errors.append(f"{case.key}: invalid fixtureRoundtrip")
    if result.get("modelFormat") != MODEL_AXIS_STATUS:
        errors.append(f"{case.key}: modelFormat must be not-evaluated")
    if result.get("modelSemantic") != MODEL_AXIS_STATUS:
        errors.append(f"{case.key}: modelSemantic must be not-evaluated")
    if result.get("countsTowardKpi") is not False:
        errors.append(f"{case.key}: zero-real-model cases cannot count toward KPI")
    if result.get("realProviderCredentialsUsed") is not False:
        errors.append(f"{case.key}: real provider credentials are forbidden")
    real_model_requests_sent = result.get("realModelRequestsSent")
    if (
        isinstance(real_model_requests_sent, bool)
        or not isinstance(real_model_requests_sent, int)
        or real_model_requests_sent != 0
    ):
        errors.append(f"{case.key}: realModelRequestsSent must equal zero")
    for field in RESULT_COUNTER_FIELDS:
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"{case.key}: {field} must be a non-negative integer")
    for field in RESULT_BOOLEAN_FIELDS:
        if not isinstance(result.get(field), bool):
            errors.append(f"{case.key}: {field} must be a boolean")

    provider_attempted = result.get("realProviderRequestsAttempted")
    provider_completed = result.get("realProviderRequestsCompleted")
    model_attempted = result.get("realModelCallsAttempted")
    model_completed = result.get("realModelCallsCompleted")
    if (
        isinstance(provider_attempted, int)
        and not isinstance(provider_attempted, bool)
        and isinstance(provider_completed, int)
        and not isinstance(provider_completed, bool)
        and provider_completed > provider_attempted
    ):
        errors.append(f"{case.key}: completed provider requests exceed attempts")
    if (
        isinstance(model_attempted, int)
        and not isinstance(model_attempted, bool)
        and isinstance(model_completed, int)
        and not isinstance(model_completed, bool)
        and model_completed > model_attempted
    ):
        errors.append(f"{case.key}: completed model calls exceed attempts")
    if result.get("realCredentialsUsed") is True and provider_attempted == 0:
        errors.append(f"{case.key}: real credentials cannot be used with zero provider attempts")
    if any(
        result.get(field) != 0
        for field in (
            "realProviderRequestsAttempted",
            "realProviderRequestsCompleted",
            "realModelCallsAttempted",
            "realModelCallsCompleted",
        )
    ):
        errors.append(f"{case.key}: zero-real-model epoch recorded a real request or call")
    if result.get("realCredentialsUsed") is not False:
        errors.append(f"{case.key}: zero-real-model epoch recorded real credentials")
    if case.requires_real_model and status == "passed":
        errors.append(f"{case.key}: real-model-required case cannot pass in zero-real-model mode")
    return errors


def case_result_record(
    case: CaseSpec,
    status: str,
    *,
    evidence_level: str,
    real_provider_requests_attempted: int = 0,
    real_provider_requests_completed: int = 0,
    real_model_calls_attempted: int = 0,
    real_model_calls_completed: int = 0,
    manual_human_checks_completed: int = 0,
    real_credentials_used: bool = False,
    device_or_mcp_contacted: bool = False,
    provider_mode: str = "not-applicable",
    request_assembly: str = "not-applicable",
    fixture_roundtrip: str = "not-applicable",
    notes: str = "",
) -> dict[str, Any]:
    record = {
        "schemaVersion": "1.0.0",
        "case": case.key,
        "matrixItems": list(case.matrix_items),
        "terminal": status in TERMINAL_STATUSES,
        "status": status,
        "evidenceLevel": evidence_level,
        "providerMode": provider_mode,
        "realModelRequestsSent": 0,
        "countsTowardKpi": False,
        "requestAssembly": request_assembly,
        "fixtureRoundtrip": fixture_roundtrip,
        "modelFormat": MODEL_AXIS_STATUS,
        "modelSemantic": MODEL_AXIS_STATUS,
        "realProviderCredentialsUsed": False,
        "realProviderRequestsAttempted": real_provider_requests_attempted,
        "realProviderRequestsCompleted": real_provider_requests_completed,
        "realModelCallsAttempted": real_model_calls_attempted,
        "realModelCallsCompleted": real_model_calls_completed,
        "manualHumanChecksCompleted": manual_human_checks_completed,
        "realCredentialsUsed": real_credentials_used,
        "deviceOrMcpContacted": device_or_mcp_contacted,
        "notes": notes,
    }
    errors = validate_case_result(case, record)
    if errors:
        raise RuntimeError(f"invalid terminal case result: {errors}")
    return record


def prepare_bundle(
    output: Path,
    *,
    kind: str,
    run_id: str,
    cases: Iterable[CaseSpec],
    code_hash: str,
) -> dict[str, Any]:
    validate_run_id(run_id)
    selected = list(cases)
    errors = validate_catalog(selected)
    if errors:
        raise RuntimeError(f"invalid case catalog: {errors}")
    root = ensure_private_directory(output, must_be_empty=True)
    plan = plan_record(kind, run_id, selected, code_hash)
    durable_json(root / "plan.json", plan)
    for case in selected:
        case_dir = ensure_private_directory(root / "cases" / case.key)
        durable_json(
            case_dir / "case.json",
            {
                "case": case.record(),
                "status": "planned",
                "countsTowardPass": False,
                "resultContract": result_contract(),
            },
        )
    manifest = {
        "schemaVersion": "1.0.0",
        "kind": kind,
        "runId": run_id,
        "appVersion": APP_VERSION,
        "runnerHash": code_hash,
        "planHash": plan["planHash"],
        "status": "prepared",
        "createdAt": now_utc(),
        "selectedCases": [case.key for case in selected],
        "providerMode": "virtual",
        "realModelRequestsSent": 0,
        "realProviderCredentialsUsed": False,
        "countsTowardPass": False,
        "countsTowardKpi": False,
        "liveAdapter": "not-wired",
    }
    durable_json(root / "run-manifest.json", manifest)
    return {"artifactDir": str(root), "manifest": manifest, "plan": plan}


def read_private_endpoint(path: Path) -> dict[str, str]:
    if not path.is_absolute():
        raise RuntimeError("endpoint JSON path must be explicit and absolute")
    if path.is_symlink():
        raise RuntimeError("endpoint JSON must not be a symlink")
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise RuntimeError(f"endpoint JSON is unavailable: {path}") from exc
    if not path.is_file() or mode != 0o600:
        raise RuntimeError("endpoint JSON must be a regular mode-0600 file")
    value = load_json(path)
    url = str(value.get("url") or "")
    auth = str(value.get("auth") or "")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("endpoint JSON must contain an absolute HTTP(S) URL")
    if not auth:
        raise RuntimeError("endpoint JSON must contain a non-empty auth value")
    return {"url": url, "auth": auth}


def load_prepared_manifest(
    artifact_dir: Path,
    *,
    kind: str,
    run_id: str,
    code_hash: str,
) -> tuple[Path, dict[str, Any]]:
    root = artifact_dir.expanduser().resolve()
    manifest = load_json(root / "run-manifest.json")
    expected = {
        "kind": kind,
        "runId": run_id,
        "appVersion": APP_VERSION,
        "runnerHash": code_hash,
    }
    mismatches = {
        key: {"expected": value, "actual": manifest.get(key)}
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"prepared manifest identity mismatch: {mismatches}")
    return root, manifest


def authorize_live_phase(
    args: Any,
    *,
    kind: str,
    code_hash: str,
    final_gate: bool = False,
) -> tuple[Path, dict[str, Any], dict[str, str], str]:
    expected_confirmation = FINAL_CONFIRMATION if final_gate else CONFIRMATION
    if args.confirm != expected_confirmation:
        raise RuntimeError(f"live phase requires --confirm {expected_confirmation}")
    if not str(args.device or "").strip():
        raise RuntimeError("live phase requires an explicit --device")
    if not str(args.endpoint_json or "").strip():
        raise RuntimeError("live phase requires an explicit --endpoint-json")
    if int(args.isolated_chat_id or 0) < 1:
        raise RuntimeError("live phase requires a positive --isolated-chat-id")
    if int(args.protected_chat_id or 0) < 1:
        raise RuntimeError("live phase requires a positive --protected-chat-id")
    if int(args.isolated_chat_id) == int(args.protected_chat_id):
        raise RuntimeError("isolated chat must differ from the protected user chat")
    root, manifest = load_prepared_manifest(
        Path(args.artifact_dir),
        kind=kind,
        run_id=args.run_id,
        code_hash=code_hash,
    )
    endpoint = read_private_endpoint(Path(args.endpoint_json))
    identity = {
        "kind": kind,
        "runId": args.run_id,
        "device": str(args.device),
        "endpointUrl": endpoint["url"],
        "isolatedChatId": int(args.isolated_chat_id),
        "protectedChatId": int(args.protected_chat_id),
        "runnerHash": code_hash,
    }
    return root, manifest, endpoint, stable_hash(identity)


def reserve_intent(
    path: Path,
    *,
    run_id: str,
    phase: str,
    identity_hash: str,
    case_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_payload = payload or {}
    record = {
        "schemaVersion": "1.0.0",
        "intentId": stable_hash(
            {
                "runId": run_id,
                "phase": phase,
                "caseKey": case_key,
                "identityHash": identity_hash,
                "payload": safe_payload,
            }
        ),
        "runId": run_id,
        "phase": phase,
        "caseKey": case_key,
        "identityHash": identity_hash,
        "payloadHash": stable_hash(safe_payload),
        "status": "reserved",
        "createdAt": now_utc(),
    }
    durable_json(path, record, exclusive=True)
    return record


def stage_unwired_live_phase(
    args: Any,
    *,
    kind: str,
    code_hash: str,
    phase: str,
) -> dict[str, Any]:
    root, manifest, _endpoint, identity_hash = authorize_live_phase(
        args,
        kind=kind,
        code_hash=code_hash,
    )
    if phase == "execute" and manifest.get("status") != "prepared":
        raise RuntimeError("execute requires a prepared manifest and cannot resend an existing epoch")
    if phase == "resume":
        if manifest.get("status") not in {
            "execution-pending-adapter",
            "running",
            "paused-restored",
            "recovery-required",
        }:
            raise RuntimeError("resume requires a resumable prepared epoch")
        execute_intent = root / "intents" / "execute.json"
        if not execute_intent.exists():
            raise RuntimeError("resume requires the durable execute intent")
        prior = load_json(execute_intent)
        if prior.get("identityHash") != identity_hash:
            raise RuntimeError("resume identity does not match the durable execute intent")
    intent_path = root / "intents" / f"{phase}.json"
    intent = reserve_intent(
        intent_path,
        run_id=args.run_id,
        phase=phase,
        identity_hash=identity_hash,
        payload={"selectedCases": manifest.get("selectedCases", [])},
    )
    blocked = {
        "status": "blocked",
        "reason": "live-adapter-not-wired",
        "phase": phase,
        "intentId": intent["intentId"],
        "providerMode": "blocked",
        "realModelRequestsSent": 0,
        "realProviderCredentialsUsed": False,
        "countsTowardKpi": False,
        "countsTowardPass": False,
        "deviceOrMcpContacted": False,
        "recordedAt": now_utc(),
    }
    durable_json(root / "phases" / f"{phase}.json", blocked)
    manifest.update(
        {
            "status": "execution-pending-adapter",
            "lastPhase": phase,
            "lastIntentId": intent["intentId"],
            "countsTowardPass": False,
            "updatedAt": now_utc(),
        }
    )
    durable_json(root / "run-manifest.json", manifest)
    return blocked


def evaluate_final_gate(
    artifact_dir: Path,
    cases: Iterable[CaseSpec],
    *,
    required_matrix_items: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = artifact_dir.expanduser().resolve()
    errors: list[str] = []
    coverage_errors: list[str] = []
    findings: list[dict[str, str]] = []
    terminal_counts = {status: 0 for status in TERMINAL_STATUSES}
    catalog = list(cases)
    expected_matrix_items = (
        tuple(required_matrix_items)
        if required_matrix_items is not None
        else tuple(
            item
            for item in MATRIX_ITEMS
            if any(item in case.matrix_items for case in catalog)
        )
    )
    unknown_required_items = set(expected_matrix_items) - set(MATRIX_ITEMS)
    if unknown_required_items:
        errors.append(f"unknown required matrix items: {sorted(unknown_required_items)}")
        coverage_errors.append(errors[-1])
    matrix_members = {
        item: [case.key for case in catalog if item in case.matrix_items]
        for item in expected_matrix_items
        if item in MATRIX_ITEMS
    }
    matrix_terminal_cases = {item: [] for item in matrix_members}
    for case in catalog:
        result_path = root / "cases" / case.key / "result.json"
        if not result_path.exists():
            message = f"{case.key}: missing result.json"
            errors.append(message)
            coverage_errors.append(message)
            continue
        result = load_json(result_path)
        result_errors = validate_case_result(case, result)
        errors.extend(result_errors)
        coverage_errors.extend(result_errors)
        status = result.get("status")
        if not result_errors and status in TERMINAL_STATUSES:
            terminal_counts[status] += 1
            for item in case.matrix_items:
                matrix_terminal_cases[item].append(case.key)
            if status != "passed":
                findings.append({"case": case.key, "status": status})

    matrix_coverage: dict[str, dict[str, Any]] = {}
    for item, members in matrix_members.items():
        terminal_members = matrix_terminal_cases[item]
        complete = bool(members) and sorted(terminal_members) == sorted(members)
        matrix_coverage[item] = {
            "terminal": complete,
            "caseCount": len(members),
            "terminalCaseCount": len(terminal_members),
            "cases": members,
        }
        if not complete:
            message = f"matrix item {item}: terminal coverage incomplete"
            if message not in errors:
                errors.append(message)
            coverage_errors.append(message)

    restoration_path = root / "restoration" / "result.json"
    if not restoration_path.exists():
        errors.append("missing restoration/result.json")
    else:
        restoration = load_json(restoration_path)
        if restoration.get("passed") is not True:
            errors.append("restoration did not pass")
        for assertion in RESTORATION_ASSERTIONS:
            if restoration.get(assertion) is not True:
                errors.append(f"restoration assertion failed: {assertion}")

    required_gate_files = {
        "adb": ("status", "passed"),
        "mcp": ("status", "passed"),
        "state": ("status", "passed"),
    }
    gate_records: dict[str, dict[str, Any]] = {}
    for name, (field, expected) in required_gate_files.items():
        path = root / "final-gate" / f"{name}.json"
        if not path.exists():
            errors.append(f"missing final-gate/{name}.json")
            continue
        record = load_json(path)
        gate_records[name] = record
        if record.get(field) != expected:
            errors.append(f"final {name} gate did not pass")
    adb = gate_records.get("adb", {})
    if adb and (
        adb.get("appVersion") != APP_VERSION
        or adb.get("deviceIdentityMatches") is not True
    ):
        errors.append("final ADB identity/version mismatch")
    mcp = gate_records.get("mcp", {})
    if mcp and (
        mcp.get("strict") is not True
        or mcp.get("identityMatches") is not True
        or mcp.get("surfaceReviewed") is not True
    ):
        errors.append("final MCP strict/identity/surface gate incomplete")
    state = gate_records.get("state", {})
    if state and (
        state.get("anchorHashMatches") is not True
        or state.get("protectedChatUntouched") is not True
    ):
        errors.append("final state anchor mismatch")

    all_terminal_passed = (
        not coverage_errors
        and terminal_counts["passed"] == len(catalog)
    )
    complete = not errors
    return {
        "status": "complete" if complete else "incomplete",
        "verdict": (
            "passed"
            if complete and all_terminal_passed
            else "complete-with-findings"
            if complete
            else "incomplete"
        ),
        "ok": complete,
        "passed": complete and all_terminal_passed,
        "errors": errors,
        "findings": findings,
        "terminalCoverageComplete": not coverage_errors,
        "terminalCounts": terminal_counts,
        "matrixCoverage": matrix_coverage,
        "realModelPolicy": {
            "mode": "zero-real-model",
            "realModelRequestsSent": 0,
            "realProviderCredentialsUsed": False,
            "countsTowardKpi": False,
            "deferredIsTerminal": False,
            "zeroRealCallsAllowedFor": [
                "failed",
                "mixed",
                "blocked",
                "not-applicable",
            ],
            "passedRequiresCompletedRealEvidence": True,
        },
        "checkedAt": now_utc(),
    }


def run_final_gate(
    args: Any,
    *,
    kind: str,
    code_hash: str,
    cases: Iterable[CaseSpec],
    required_matrix_items: Iterable[str] | None = None,
) -> dict[str, Any]:
    root, manifest, _endpoint, identity_hash = authorize_live_phase(
        args,
        kind=kind,
        code_hash=code_hash,
        final_gate=True,
    )
    evaluation = evaluate_final_gate(
        root,
        cases,
        required_matrix_items=required_matrix_items,
    )
    if not evaluation["ok"]:
        raise RuntimeError(f"final gate refused: {evaluation['errors']}")
    intent = reserve_intent(
        root / "intents" / "final-gate.json",
        run_id=args.run_id,
        phase="final-gate",
        identity_hash=identity_hash,
        payload={
            "terminalCoverageComplete": evaluation["terminalCoverageComplete"],
            "verdict": evaluation["verdict"],
        },
    )
    evaluation["intentId"] = intent["intentId"]
    durable_json(root / "final-gate" / "evaluation.json", evaluation)
    manifest.update(
        {
            "status": "complete",
            "verdict": evaluation["verdict"],
            "finishedAt": now_utc(),
            "providerMode": "virtual",
            "realModelRequestsSent": 0,
            "realProviderCredentialsUsed": False,
            "countsTowardKpi": False,
            "countsTowardPass": evaluation["passed"],
            "terminalCoverageComplete": evaluation["terminalCoverageComplete"],
            "finalGateIntentId": intent["intentId"],
        }
    )
    durable_json(root / "run-manifest.json", manifest)
    return evaluation


def self_check(kind: str, run_id: str, cases: Iterable[CaseSpec], code_hash: str) -> dict[str, Any]:
    validate_run_id(run_id)
    catalog = list(cases)
    errors = validate_catalog(catalog)
    plan = plan_record(kind, run_id, catalog, code_hash)
    return {
        "ok": not errors,
        "kind": kind,
        "appVersion": APP_VERSION,
        "caseCount": len(catalog),
        "realModelCaseCount": sum(case.requires_real_model for case in catalog),
        "manualCaseCount": sum(case.manual for case in catalog),
        "destructiveCaseCount": sum(case.destructive for case in catalog),
        "matrixItems": sorted({item for case in catalog for item in case.matrix_items}),
        "terminalStatuses": list(TERMINAL_STATUSES),
        "liveAdapter": "not-wired",
        "planHash": plan["planHash"],
        "failures": errors,
        "deviceOrMcpContacted": False,
    }
