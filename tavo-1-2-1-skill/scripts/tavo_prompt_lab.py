#!/usr/bin/env python3
"""Compile Tavo text assets and optionally call an OpenAI-compatible model.

The lab is intentionally text-only. It implements the packaged prompt-assembly
rules, including isolated prompt-field EJS before macros, and reports known
approximations instead of claiming full app equivalence.
"""

from __future__ import annotations

import argparse
import copy
import datetime as datetime_module
import errno
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


FORMAT = "tavo-prompt-lab-result/v2.3"
STATE_FORMAT = "tavo-prompt-lab-state/v2.3"
CASE_SCHEMA_VERSION = "2.3"
LEGACY_CASE_SCHEMA_VERSIONS = frozenset({"2.1", "2.2"})
DEFAULT_KEY_ENV = "TAVO_PROMPT_LAB_API_KEY"
DEFAULT_BASE_URL_ENV = "TAVO_PROMPT_LAB_BASE_URL"
DEFAULT_MODEL_ENV = "TAVO_PROMPT_LAB_MODEL"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 32 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_WORLD_BOOKS = 128
MAX_ENTRIES = 10_000
MAX_HISTORY_MESSAGES = 10_000
MAX_SESSION_TURNS = 64
MAX_SESSION_BUDGET_BYTES = 64 * 1024 * 1024
MAX_EJS_STATE_BYTES = 4 * 1024 * 1024
MAX_EJS_TRACE_ITEMS = 10_000
MAX_EJS_FIELDS = 512
MAX_EJS_WALL_SECONDS = 30.0
MAX_REGEX_GROUPS = 128
DEFAULT_EJS_TIMEOUT_MS = 500
MAX_EJS_TIMEOUT_MS = 2_000
ROLES = frozenset({"system", "user", "assistant"})
REGEX_PLACEMENTS = frozenset({"user", "char", "reasoning", "lorebook"})
REGEX_TIMINGS = frozenset({"display", "send", "sendAndDisplay", "receive", "editAndReceive"})
REGEX_SUBSTITUTIONS = frozenset({"none", "raw", "escaped"})
RESERVED_PARAMETERS = frozenset({"model", "messages", "stream"})
SENSITIVE_PARAMETER_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "client_secret",
        "cookie",
        "headers",
        "password",
        "proxy_authorization",
        "refresh_token",
        "secret",
        "token",
        "x_api_key",
    }
)
NORMALIZED_SENSITIVE_PARAMETER_KEYS = frozenset(
    re.sub(r"[^a-z0-9]", "", key.lower()) for key in SENSITIVE_PARAMETER_KEYS
)
WORLD_POSITIONS = frozenset(
    {
        "lorebookBefore",
        "lorebookAfter",
        "topOfExampleMessages",
        "bottomOfExampleMessages",
        "atDepth",
    }
)
SECONDARY_STRATEGIES = frozenset({"none", "andAny", "andAll", "notAny", "notAll"})
MACRO_RE = re.compile(r"{{([\s\S]*?)}}")
ANY_MACRO_RE = re.compile(r"{{.*?}}", re.DOTALL)
ESCAPED_MACRO_RE = re.compile(r"\\\{\\\{([\s\S]*?)\\\}\\\}")
EJS_RE = re.compile(r"<%(?:[-=_#%])?")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NUMBER_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$")
LEGACY_BUILTIN_IDENTIFIERS = frozenset(
    {"main", "enhanceDefinitions", "nsfw", "jailbreak"}
)


class LabError(ValueError):
    """A stable, user-facing compilation or runner error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ProviderResponseError(LabError):
    """A provider failure with bounded, redacted response diagnostics."""

    def __init__(self, code: str, message: str, diagnostic: dict[str, Any]) -> None:
        super().__init__(code, message)
        self.diagnostic = diagnostic


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep credentials on the explicitly configured origin."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


@dataclass
class WarningItem:
    code: str
    message: str
    source: str | None = None

    def as_dict(self) -> dict[str, str]:
        value = {"code": self.code, "message": self.message}
        if self.source:
            value["source"] = self.source
        return value


@dataclass
class AbsoluteInjection:
    source: str
    identifier: str
    content: str
    role: str
    depth: int
    merge_into_anchor: bool = False


@dataclass
class AssemblyBudget:
    limit: int = MAX_REQUEST_BYTES
    used: int = 0

    def add(self, content: str, source: str) -> None:
        size = len(content.encode("utf-8")) + 2
        if self.used + size > self.limit:
            raise LabError(
                "request_too_large", f"assembled text exceeds {self.limit} bytes at {source}"
            )
        self.used += size


_MISSING = object()


def reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def strict_json_loads(value: str | bytes) -> Any:
    return json.loads(value, parse_constant=reject_nonfinite_json)


def strict_json_dumps(value: Any, **kwargs: Any) -> str:
    try:
        return json.dumps(value, allow_nan=False, **kwargs)
    except (TypeError, ValueError) as error:
        raise LabError("invalid_json_value", "value must contain only finite JSON data") from error


def normalized_security_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def error_payload(error: LabError) -> dict[str, Any]:
    value: dict[str, Any] = {"code": error.code, "message": str(error)}
    if isinstance(error, ProviderResponseError):
        value["diagnostic"] = copy.deepcopy(error.diagnostic)
    return value


def case_schema_warnings(case: dict[str, Any]) -> list[WarningItem]:
    version = case.get("schemaVersion")
    if version is None:
        return []
    if not isinstance(version, str):
        raise LabError("invalid_schema_version", "case.schemaVersion must be a string")
    if version == CASE_SCHEMA_VERSION:
        return []
    if version in LEGACY_CASE_SCHEMA_VERSIONS:
        return [
            WarningItem(
                "legacy_case_schema",
                f"case.schemaVersion {version} is accepted for compatibility; outputs and new state files use {CASE_SCHEMA_VERSION}.",
                "case.schemaVersion",
            )
        ]
    raise LabError(
        "unsupported_schema_version",
        f"case.schemaVersion {version!r} is unsupported; expected {CASE_SCHEMA_VERSION}",
    )


def json_clone(value: Any, label: str) -> Any:
    try:
        encoded = strict_json_dumps(value, ensure_ascii=False)
        return strict_json_loads(encoded)
    except (LabError, TypeError, ValueError) as error:
        raise LabError("invalid_ejs_state", f"{label} must contain only finite JSON values") from error


def variable_path_parts(path: Any) -> list[str]:
    value = re.sub(r"\[(\d+)\]", r".\1", str(path if path is not None else ""))
    parts = [part for part in value.split(".") if part]
    if not parts or any(part in {"__proto__", "prototype", "constructor"} for part in parts):
        raise LabError("invalid_variable_path", "variable paths cannot be empty or use prototype keys")
    return parts


def variable_lookup(root: Any, path: Any) -> Any:
    current = root
    for part in variable_path_parts(path):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def variable_set(root: dict[str, Any], path: Any, value: Any) -> None:
    parts = variable_path_parts(path)
    current: Any = root
    for index, part in enumerate(parts[:-1]):
        next_is_index = parts[index + 1].isdigit()
        if isinstance(current, dict):
            child = current.get(part)
            if not isinstance(child, (dict, list)):
                child = [] if next_is_index else {}
                current[part] = child
            current = child
        elif isinstance(current, list) and part.isdigit():
            item_index = int(part)
            while len(current) <= item_index:
                current.append(None)
            child = current[item_index]
            if not isinstance(child, (dict, list)):
                child = [] if next_is_index else {}
                current[item_index] = child
            current = child
        else:
            raise LabError("invalid_variable_path", "variable path crosses a scalar value")
    leaf = parts[-1]
    cloned = json_clone(value, "variable value")
    if isinstance(current, dict):
        current[leaf] = cloned
    elif isinstance(current, list) and leaf.isdigit():
        item_index = int(leaf)
        while len(current) <= item_index:
            current.append(None)
        current[item_index] = cloned
    else:
        raise LabError("invalid_variable_path", "variable path cannot be assigned")


def variable_delete(root: dict[str, Any], path: Any) -> bool:
    parts = variable_path_parts(path)
    current: Any = root
    for part in parts[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False
    leaf = parts[-1]
    if isinstance(current, dict) and leaf in current:
        del current[leaf]
        return True
    if isinstance(current, list) and leaf.isdigit() and int(leaf) < len(current):
        current[int(leaf)] = None
        return True
    return False


def macro_value_text(value: Any) -> str:
    if value is _MISSING or value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return strict_json_dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def parse_macro_value(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return ""
    if NUMBER_RE.fullmatch(stripped):
        try:
            return int(stripped)
        except ValueError:
            return float(stripped)
    if stripped[0] in '[{"' or stripped in {"true", "false", "null"}:
        try:
            return strict_json_loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
    return stripped


class EjsRenderer:
    """Render authored prompt fields in a short-lived, permission-limited Node VM."""

    def __init__(
        self,
        config: Any,
        *,
        character: dict[str, Any],
        persona: dict[str, Any],
        history: list[dict[str, str]],
        user_input: str,
    ) -> None:
        if config is None:
            config = {}
        if isinstance(config, bool):
            config = {"mode": "sandboxed" if config else "off"}
        if not isinstance(config, dict):
            raise LabError("invalid_ejs_config", "case.ejs must be a boolean or object")
        mode = config.get("mode", "sandboxed")
        if mode not in {"sandboxed", "off"}:
            raise LabError("invalid_ejs_config", "case.ejs.mode must be sandboxed or off")
        timeout_ms = config.get("timeoutMs", DEFAULT_EJS_TIMEOUT_MS)
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 1 <= timeout_ms <= MAX_EJS_TIMEOUT_MS:
            raise LabError(
                "invalid_ejs_config",
                f"case.ejs.timeoutMs must be an integer from 1 to {MAX_EJS_TIMEOUT_MS}",
            )
        variables = config.get("variables", {})
        if not isinstance(variables, dict):
            raise LabError("invalid_ejs_state", "case.ejs.variables must be an object")
        state = {
            "chat": variables.get("chat", {}),
            "global": variables.get("global", {}),
        }
        if not isinstance(state["chat"], dict) or not isinstance(state["global"], dict):
            raise LabError("invalid_ejs_state", "case.ejs.variables.chat/global must be objects")
        state = json_clone(state, "case.ejs.variables")
        if json_size(state) > MAX_EJS_STATE_BYTES:
            raise LabError("ejs_state_too_large", f"EJS state exceeds {MAX_EJS_STATE_BYTES} bytes")
        last_assistant = next(
            (item["content"] for item in reversed(history) if item["role"] == "assistant"), ""
        )
        character_id = config.get(
            "characterId", character.get("id", character.get("characterId", ""))
        )
        if not isinstance(character_id, (str, int, float)) or isinstance(character_id, bool):
            raise LabError("invalid_ejs_config", "case.ejs.characterId must be a string or number")
        self.mode = mode
        self.timeout_ms = timeout_ms
        self.state: dict[str, dict[str, Any]] = state
        self.initial_state = copy.deepcopy(state)
        self.constants = {
            "charName": str(character.get("name", "")),
            "userName": str(persona.get("name", "User")),
            "lastUserMessage": user_input,
            "lastCharMessage": last_assistant,
            "characterId": character_id,
        }
        self.trace: list[dict[str, Any]] = []
        self.macro_variable_trace: list[dict[str, Any]] = []
        self.unresolved_sources: set[str] = set()
        self.fields_detected = 0
        self.fields_rendered = 0
        self.fields_fallback = 0
        self.fields_disabled = 0
        self.ejs_operation_count = 0
        self.started_at = time.monotonic()

    def _record_field(
        self,
        source: str,
        status: str,
        source_text: str,
        rendered_text: str,
        operations: list[dict[str, Any]] | None = None,
        error_kind: str | None = None,
    ) -> None:
        item: dict[str, Any] = {
            "source": source,
            "status": status,
            "sourceBytes": len(source_text.encode("utf-8")),
            "renderedBytes": len(rendered_text.encode("utf-8")),
            "sourceSha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "renderedSha256": hashlib.sha256(rendered_text.encode("utf-8")).hexdigest(),
            "variableOperations": operations or [],
        }
        if error_kind:
            item["errorKind"] = error_kind
        self.trace.append(item)

    def _fallback(
        self,
        text: str,
        warnings: list[WarningItem],
        source: str,
        *,
        code: str,
        message: str,
        kind: str,
    ) -> tuple[str, bool]:
        self.fields_fallback += 1
        self.unresolved_sources.add(source)
        warnings.append(WarningItem(code, message, source))
        self._record_field(source, "fallback-original", text, text, error_kind=kind)
        # Tavo 1.0 keeps the whole authored field when EJS fails, rolls back
        # that field's state mutations, and still runs the ordinary macro pass
        # over the retained text.  The raw EJS source therefore remains visible
        # while macros outside (or inside) it can still expand.
        return text, True

    def render_ejs(
        self, text: str, warnings: list[WarningItem], source: str
    ) -> tuple[str, bool]:
        self.fields_detected += 1
        if self.mode == "off":
            self.fields_disabled += 1
            self.unresolved_sources.add(source)
            warnings.append(
                WarningItem(
                    "ejs_not_executed",
                    "EJS execution is disabled by case.ejs.mode=off; the complete field remains original and receives no macro pass.",
                    source,
                )
            )
            self._record_field(source, "disabled-original", text, text)
            return text, False
        if (
            self.fields_detected > MAX_EJS_FIELDS
            or time.monotonic() - self.started_at > MAX_EJS_WALL_SECONDS
        ):
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_budget_exhausted_fallback",
                message="The per-case EJS field/time budget was exhausted; the complete field fell back to its original text and the ordinary macro pass continues.",
                kind="limit",
            )

        node = shutil.which("node")
        worker = Path(__file__).with_name("tavo_ejs_worker.mjs").resolve()
        if not node or not worker.is_file():
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_runtime_unavailable",
                message="Sandboxed EJS requires Node.js and the bundled worker; the complete field fell back to its original text and the ordinary macro pass continues.",
                kind="unavailable",
            )
        request = {
            "template": text,
            "state": self.state,
            "constants": self.constants,
            "timeoutMs": self.timeout_ms,
            "maxOutputChars": MAX_TEXT_BYTES,
            "maxTraceItems": MAX_EJS_TRACE_ITEMS,
        }
        command = [
            str(Path(node).resolve()),
            "--no-warnings",
            "--permission",
            f"--allow-fs-read={worker}",
            "--disable-proto=throw",
            "--max-old-space-size=64",
            str(worker),
        ]
        if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file():
            command = [
                "/usr/bin/sandbox-exec",
                "-p",
                "(version 1) (allow default) (deny network*) (deny file-write*)",
                *command,
            ]
        environment = {
            "PATH": str(Path(node).resolve().parent),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        try:
            with tempfile.TemporaryDirectory(prefix="tavo-prompt-lab-ejs-") as working:
                completed = subprocess.run(
                    command,
                    input=strict_json_dumps(request, ensure_ascii=False),
                    text=True,
                    capture_output=True,
                    cwd=working,
                    env=environment,
                    timeout=max(2.0, self.timeout_ms / 1000.0 + 1.5),
                    check=False,
                )
        except subprocess.TimeoutExpired:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_timeout_fallback",
                message="Sandboxed EJS exceeded its wall-clock limit; the complete field fell back to its original text, state changes were rolled back, and the ordinary macro pass continues.",
                kind="timeout",
            )
        except OSError as error:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message=f"Sandboxed EJS could not start ({error.__class__.__name__}); the complete field fell back to its original text and the ordinary macro pass continues.",
                kind="worker",
            )
        if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > MAX_RESPONSE_BYTES:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message="Sandboxed EJS ended without a bounded result; the complete field fell back to its original text and the ordinary macro pass continues.",
                kind="worker",
            )
        try:
            response = strict_json_loads(completed.stdout)
        except (json.JSONDecodeError, ValueError):
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message="Sandboxed EJS returned invalid JSON; the complete field fell back to its original text and the ordinary macro pass continues.",
                kind="worker",
            )
        if not isinstance(response, dict) or response.get("ok") is not True:
            error = response.get("error", {}) if isinstance(response, dict) else {}
            kind = str(error.get("kind", "runtime"))
            detail = str(error.get("message", "EJS render failed"))[:512]
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_render_error_fallback",
                message=f"Sandboxed EJS {kind} error; Tavo-style whole-field fallback was applied, state changes were rolled back, and the ordinary macro pass continues: {detail}",
                kind=kind,
            )
        output = response.get("output")
        state = response.get("state")
        operations = response.get("trace")
        if (
            not isinstance(output, str)
            or not isinstance(state, dict)
            or not isinstance(state.get("chat"), dict)
            or not isinstance(state.get("global"), dict)
            or not isinstance(operations, list)
        ):
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message="Sandboxed EJS returned an invalid result shape; the complete field fell back to its original text and the ordinary macro pass continues.",
                kind="worker",
            )
        try:
            ensure_text_budget(output, source)
            state = json_clone(state, "EJS worker state")
        except LabError:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_result_limit_fallback",
                message="Sandboxed EJS produced an invalid or excessive result; the complete field fell back, state changes were rolled back, and the ordinary macro pass continues.",
                kind="limit",
            )
        if json_size(state) > MAX_EJS_STATE_BYTES:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_state_too_large_fallback",
                message="Sandboxed EJS produced excessive variable state; the complete field fell back, state changes were rolled back, and the ordinary macro pass continues.",
                kind="limit",
            )
        if self.ejs_operation_count + len(operations) > MAX_EJS_TRACE_ITEMS:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_trace_limit_fallback",
                message="Sandboxed EJS exceeded the per-case variable trace limit; the complete field fell back, state changes were rolled back, and the ordinary macro pass continues.",
                kind="limit",
            )
        self.state = state
        self.ejs_operation_count += len(operations)
        self.fields_rendered += 1
        self._record_field(source, "rendered", text, output, operations)
        if not self.constants["characterId"] and re.search(r"\bcharacterId\b", text):
            warnings.append(
                WarningItem(
                    "ejs_character_id_missing",
                    "This field reads characterId, but the case/card supplied no stable character id; Prompt Lab used an empty string.",
                    source,
                )
            )
        return output, True

    def _scope(self, scope: str | None) -> str | None:
        if scope in {None, "", "cache"}:
            return None
        if scope == "global":
            return "global"
        if scope in {"chat", "local", "message", "initial"}:
            return "chat"
        raise LabError("invalid_variable_scope", f"unsupported variable scope: {scope}")

    def _record_macro_variable(self, item: dict[str, Any]) -> None:
        if len(self.macro_variable_trace) >= MAX_EJS_TRACE_ITEMS:
            raise LabError(
                "too_many_macro_operations",
                f"macro variable operations exceed {MAX_EJS_TRACE_ITEMS} items",
            )
        self.macro_variable_trace.append(item)

    def _check_state_budget(self) -> None:
        if json_size(self.state) > MAX_EJS_STATE_BYTES:
            raise LabError(
                "ejs_state_too_large",
                f"combined EJS/macro variable state exceeds {MAX_EJS_STATE_BYTES} bytes",
            )

    def get_variable(self, key: str, scope: str | None = None) -> Any:
        normalized = self._scope(scope)
        scopes = [normalized] if normalized else ["chat", "global"]
        for candidate in scopes:
            value = variable_lookup(self.state[candidate], key)
            if value is not _MISSING:
                self._record_macro_variable(
                    {"channel": "macro", "op": "get", "key": key, "scope": candidate, "found": True}
                )
                return value
        self._record_macro_variable(
            {"channel": "macro", "op": "get", "key": key, "scope": normalized, "found": False}
        )
        return _MISSING

    def set_variable(self, key: str, value: Any, scope: str = "chat") -> None:
        normalized = self._scope(scope) or "chat"
        self._record_macro_variable(
            {"channel": "macro", "op": "set", "key": key, "scope": normalized}
        )
        variable_set(self.state[normalized], key, value)
        self._check_state_budget()

    def add_variable(self, key: str, value: Any, scope: str = "chat") -> None:
        normalized = self._scope(scope) or "chat"
        current = variable_lookup(self.state[normalized], key)
        if current is _MISSING:
            if isinstance(value, list):
                updated: Any = list(value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                updated = value
            else:
                updated = macro_value_text(value)
        elif isinstance(current, list):
            updated = [*current, *value] if isinstance(value, list) else [*current, value]
        elif (
            isinstance(current, (int, float))
            and not isinstance(current, bool)
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            updated = current + value
        else:
            updated = macro_value_text(current) + macro_value_text(value)
        self._record_macro_variable(
            {"channel": "macro", "op": "add", "key": key, "scope": normalized}
        )
        variable_set(self.state[normalized], key, updated)
        self._check_state_budget()

    def increment_variable(self, key: str, amount: float, scope: str = "chat") -> None:
        normalized = self._scope(scope) or "chat"
        current = variable_lookup(self.state[normalized], key)
        try:
            number = float(current) if current is not _MISSING else 0.0
        except (TypeError, ValueError):
            number = 0.0
        updated: int | float = number + amount
        if float(updated).is_integer():
            updated = int(updated)
        self._record_macro_variable(
            {"channel": "macro", "op": "inc" if amount >= 0 else "dec", "key": key, "scope": normalized}
        )
        variable_set(self.state[normalized], key, updated)
        self._check_state_budget()

    def report(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "engine": "isolated-node-vm-tavo-prompt-subset" if self.mode == "sandboxed" else "disabled",
            "securityBoundary": "short-lived process; Node permission model; VM string/Wasm code generation disabled; macOS network/file-write sandbox when available",
            "fieldErrorPolicy": "whole-field original fallback with local state rollback",
            "fieldsDetected": self.fields_detected,
            "fieldsRendered": self.fields_rendered,
            "fieldsFallback": self.fields_fallback,
            "fieldsDisabled": self.fields_disabled,
            "variableOperationCount": self.ejs_operation_count + len(self.macro_variable_trace),
            "unresolvedSources": sorted(self.unresolved_sources),
            "variables": {
                "initial": self.initial_state,
                "final": self.state,
            },
            "fieldTrace": self.trace,
            "macroVariableTrace": self.macro_variable_trace,
        }


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LabError("invalid_object", f"{label} must be a JSON object")
    return value


def bounded_json(path: Path, *, require_private: bool = False) -> Any:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as error:
        raise LabError("missing_input", f"JSON input does not exist: {path}") from error
    except OSError as error:
        if error.errno == errno.ELOOP or path.is_symlink():
            raise LabError("symlink_input", f"JSON input cannot be a symlink: {path}") from error
        raise
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise LabError("invalid_input", f"JSON input is not a regular file: {path}")
        if require_private and metadata.st_mode & 0o077:
            raise LabError(
                "insecure_private_file",
                f"private JSON input must have mode 0600: {path}",
            )
        if metadata.st_size > MAX_JSON_BYTES:
            raise LabError("input_too_large", f"JSON input exceeds {MAX_JSON_BYTES} bytes: {path}")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            raw = handle.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise LabError("input_too_large", f"JSON input exceeds {MAX_JSON_BYTES} bytes: {path}")
        return strict_json_loads(raw.decode("utf-8"))
    except LabError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise LabError("invalid_json", f"Cannot parse JSON input {path}: {error}") from error
    finally:
        if fd >= 0:
            os.close(fd)


def resolve_json(value: Any, base_dir: Path, label: str) -> dict[str, Any]:
    if isinstance(value, str):
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        return require_dict(bounded_json(candidate.absolute()), label)
    return require_dict(value, label)


def unwrap_mcp_text(value: dict[str, Any]) -> dict[str, Any]:
    """Accept direct assets and common MCP readback envelopes."""
    current = value
    for _ in range(4):
        result = current.get("result")
        if isinstance(result, dict) and isinstance(result.get("content"), list):
            text_blocks = [
                item.get("text")
                for item in result["content"]
                if isinstance(item, dict)
                and item.get("type") == "text"
                and isinstance(item.get("text"), str)
            ]
            if len(text_blocks) == 1:
                try:
                    parsed = strict_json_loads(text_blocks[0])
                except (json.JSONDecodeError, ValueError):
                    break
                if isinstance(parsed, dict):
                    current = parsed
                    continue
        break
    return current


def normalize_prompt_order_preset(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize the bounded Tavo-exported prompts/prompt_order subset.

    This adapter intentionally accepts only one unambiguous order and relative
    entries. In the supported Tavo 0.93 compatibility mapping, exported
    ``system_prompt: false`` entries become user prompt components even when the
    compatibility ``role`` field says system.
    """

    prompts = value.get("prompts")
    prompt_orders = value.get("prompt_order")
    if not isinstance(prompts, list) or not isinstance(prompt_orders, list):
        raise LabError(
            "invalid_prompt_order_preset",
            "prompts and prompt_order must both be arrays",
        )
    if len(prompts) > MAX_ENTRIES:
        raise LabError("too_many_entries", f"preset.prompts exceeds {MAX_ENTRIES} items")
    if len(prompt_orders) != 1:
        raise LabError(
            "ambiguous_prompt_order",
            "Prompt Lab can normalize a prompts + prompt_order preset only when it contains exactly one order",
        )
    order_envelope = prompt_orders[0]
    if not isinstance(order_envelope, dict) or not isinstance(order_envelope.get("order"), list):
        raise LabError(
            "invalid_prompt_order_preset",
            "preset.prompt_order[0].order must be an array",
        )
    raw_order = order_envelope["order"]
    if len(raw_order) > MAX_ENTRIES:
        raise LabError("too_many_entries", f"preset prompt order exceeds {MAX_ENTRIES} items")

    prompts_by_identifier: dict[str, dict[str, Any]] = {}
    for index, prompt in enumerate(prompts):
        if not isinstance(prompt, dict):
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset.prompts[{index}] must be an object",
            )
        identifier = prompt.get("identifier")
        if not isinstance(identifier, str) or not identifier:
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset.prompts[{index}].identifier must be a non-empty string",
            )
        if identifier in prompts_by_identifier:
            raise LabError(
                "duplicate_preset_identifier",
                f"preset contains duplicate prompt identifier: {identifier}",
            )
        prompts_by_identifier[identifier] = prompt

    entries: list[dict[str, Any]] = []
    ordered_identifiers: set[str] = set()
    for index, order_item in enumerate(raw_order):
        if not isinstance(order_item, dict):
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset.prompt_order[0].order[{index}] must be an object",
            )
        identifier = order_item.get("identifier")
        if not isinstance(identifier, str) or not identifier:
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset.prompt_order[0].order[{index}].identifier must be a non-empty string",
            )
        if identifier in ordered_identifiers:
            raise LabError(
                "duplicate_prompt_order_identifier",
                f"prompt_order contains duplicate identifier: {identifier}",
            )
        ordered_identifiers.add(identifier)
        prompt = prompts_by_identifier.get(identifier)
        if prompt is None:
            raise LabError(
                "missing_ordered_prompt",
                f"prompt_order references missing prompt: {identifier}",
            )

        enabled = order_item.get("enabled", prompt.get("enabled", True))
        marker = prompt.get("marker", False)
        system_prompt = prompt.get("system_prompt", True)
        forbid_overrides = prompt.get("forbid_overrides", False)
        for label, item in (
            ("enabled", enabled),
            ("marker", marker),
            ("system_prompt", system_prompt),
            ("forbid_overrides", forbid_overrides),
        ):
            if not isinstance(item, bool):
                raise LabError(
                    "invalid_prompt_order_preset",
                    f"preset prompt {identifier}.{label} must be a boolean",
                )

        injection_position = prompt.get("injection_position", 0)
        if isinstance(injection_position, bool) or injection_position != 0:
            raise LabError(
                "unsupported_prompt_order_injection",
                f"Tavo-exported prompt {identifier} uses an unsupported non-relative injection_position",
            )
        injection_depth = prompt.get("injection_depth", 0)
        if isinstance(injection_depth, bool) or not isinstance(injection_depth, int) or injection_depth < 0:
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset prompt {identifier}.injection_depth must be a non-negative integer",
            )

        raw_role = prompt.get("role", "system")
        if raw_role not in ROLES:
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset prompt {identifier}.role must be system/user/assistant",
            )
        if marker:
            role = "system"
            entry_type = "marker"
        else:
            role = "user" if raw_role == "system" and not system_prompt else raw_role
            entry_type = "builtin" if identifier in LEGACY_BUILTIN_IDENTIFIERS else "custom"

        content = prompt.get("content", "")
        name = prompt.get("name", identifier)
        if not isinstance(content, str) or not isinstance(name, str):
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset prompt {identifier} name and content must be strings",
            )
        entries.append(
            {
                "identifier": identifier,
                "name": name,
                "content": content,
                "enabled": enabled,
                "active": True,
                "role": role,
                "type": entry_type,
                "injectionPosition": "relative",
                "injectionDepth": injection_depth,
                "forbidOverrides": forbid_overrides,
            }
        )

    def text_field(key: str, default: str) -> str:
        field = value.get(key, default)
        if not isinstance(field, str):
            raise LabError(
                "invalid_prompt_order_preset",
                f"preset.{key} must be a string",
            )
        return field

    basic = {
        "persona": "{{persona}}",
        "description": "{{description}}",
        "personality": text_field("personality_format", "{{personality}}"),
        "scenario": text_field("scenario_format", "{{scenario}}"),
        "exampleMessageStart": text_field("new_example_chat_prompt", "[Example Chat]"),
        "chatStart": text_field("new_chat_prompt", "[Start a new Chat]"),
        "groupChatStart": text_field("new_group_chat_prompt", ""),
        "groupNudge": text_field("group_nudge_prompt", ""),
        "continueNudge": text_field("continue_nudge_prompt", ""),
        "impersonation": text_field("impersonation_prompt", ""),
        "lorebook": text_field("wi_format", "{0}"),
    }
    return {
        "name": value.get("name", "Tavo exported preset"),
        "basicPrompts": basic,
        "entries": entries,
        "_promptLabPresetInput": "tavo-exported-prompts-prompt_order-relative-v1",
    }


def normalize_preset(value: dict[str, Any]) -> dict[str, Any]:
    value = unwrap_mcp_text(value)
    for key in ("preset", "data"):
        candidate = value.get(key)
        if isinstance(candidate, dict) and isinstance(candidate.get("entries"), list):
            value = candidate
            break
    if "entries" not in value and ("prompts" in value or "prompt_order" in value):
        value = normalize_prompt_order_preset(value)
    if not isinstance(value.get("entries"), list):
        raise LabError("invalid_preset", "preset.entries must be an array")
    if len(value["entries"]) > MAX_ENTRIES:
        raise LabError("too_many_entries", f"preset.entries exceeds {MAX_ENTRIES} items")
    basic = value.get("basicPrompts", {})
    if basic is None:
        basic = {}
    if not isinstance(basic, dict):
        raise LabError("invalid_preset", "preset.basicPrompts must be an object")
    return value


def normalize_character(value: dict[str, Any]) -> dict[str, Any]:
    value = unwrap_mcp_text(value)
    if isinstance(value.get("character"), dict):
        value = value["character"]
    if isinstance(value.get("card"), dict):
        value = value["card"]
    if isinstance(value.get("data"), dict):
        value = value["data"]
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        raise LabError("invalid_character", "character name is required")
    aliases = {
        "first_mes": ("firstMes", "firstMessage"),
        "alternate_greetings": ("alternateGreetings",),
        "mes_example": ("mesExample", "messageExample"),
        "system_prompt": ("systemPrompt",),
        "post_history_instructions": ("postHistoryInstructions",),
        "character_book": ("characterBook",),
        "group_only_greetings": ("groupOnlyGreetings",),
    }
    value = dict(value)
    for canonical, candidates in aliases.items():
        if canonical not in value:
            for candidate in candidates:
                if candidate in value:
                    value[canonical] = value[candidate]
                    break
    nickname = value.get("nickname")
    if nickname is not None and not isinstance(nickname, str):
        raise LabError("invalid_character", "character nickname must be a string when present")
    group_greetings = value.get("group_only_greetings")
    if group_greetings is not None and (
        not isinstance(group_greetings, list)
        or any(not isinstance(item, str) for item in group_greetings)
    ):
        raise LabError(
            "invalid_character", "character group_only_greetings must be a string array when present"
        )
    return value


def normalize_persona(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {"name": "User", "description": ""}
    value = unwrap_mcp_text(value)
    if isinstance(value.get("persona"), dict):
        value = value["persona"]
    name = value.get("name", "User")
    description = value.get("description", "")
    if not isinstance(name, str) or not isinstance(description, str):
        raise LabError("invalid_persona", "persona name and description must be strings")
    return {**value, "name": name or "User", "description": description}


def normalize_history(value: Any, warnings: list[WarningItem] | None = None) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise LabError("invalid_history", "history must be an array")
    if len(value) > MAX_HISTORY_MESSAGES:
        raise LabError("too_many_history_messages", f"history exceeds {MAX_HISTORY_MESSAGES} messages")
    result: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise LabError("invalid_history", f"history[{index}] must be an object")
        if "hidden" in item and not isinstance(item["hidden"], bool):
            raise LabError("invalid_history", f"history[{index}].hidden must be a boolean")
        if item.get("hidden") is True:
            if warnings is not None:
                warnings.append(
                    WarningItem(
                        "hidden_history_omitted",
                        "A hidden history message was excluded from the provider request.",
                        f"history:{index}",
                    )
                )
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ROLES or not isinstance(content, str):
            raise LabError(
                "invalid_history",
                f"history[{index}] needs role system/user/assistant and string content",
            )
        if content:
            result.append({"role": role, "content": content})
    return result


def choose_greeting(
    character: dict[str, Any], history: list[dict[str, str]], setting: Any
) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    if setting is False or setting is None and history:
        return history, None
    if setting is None or setting is True or setting == "first":
        source, index = "first", 0
    elif isinstance(setting, str) and setting == "none":
        return history, None
    elif isinstance(setting, dict):
        source = setting.get("source", "first")
        index = setting.get("index", 0)
    else:
        raise LabError("invalid_greeting", "greeting must be false, 'first', 'none', or an object")
    if source == "first":
        content = character.get("first_mes", character.get("firstMessage", ""))
    elif source == "alternate":
        greetings = character.get("alternate_greetings", character.get("alternateGreetings", []))
        if not isinstance(greetings, list) or not isinstance(index, int) or index < 0 or index >= len(greetings):
            raise LabError("invalid_greeting", "alternate greeting index is out of range")
        content = greetings[index]
    else:
        raise LabError("invalid_greeting", "greeting.source must be 'first' or 'alternate'")
    if not isinstance(content, str) or not content:
        return history, None
    selected = {"source": source, "index": index, "content": content}
    return [{"role": "assistant", "content": content}, *history], selected


def list_of_strings(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise LabError("invalid_worldbook", f"{label} must be a string array")
    return [item for item in value if item]


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise LabError("invalid_boolean", f"{label} must be a JSON boolean")
    return value


def normalize_worldbook(value: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    value = unwrap_mcp_text(value)
    if isinstance(value.get("worldbook"), dict):
        value = value["worldbook"]
    if isinstance(value.get("character_book"), dict):
        value = value["character_book"]
    entries = value.get("entries")
    if isinstance(entries, dict):
        raw_entries = list(entries.values())
    elif isinstance(entries, list):
        raw_entries = entries
    else:
        raise LabError("invalid_worldbook", f"{fallback_name}.entries must be an array or object")
    if len(raw_entries) > MAX_ENTRIES:
        raise LabError("too_many_entries", f"{fallback_name}.entries exceeds {MAX_ENTRIES} items")
    name = value.get("name", fallback_name)
    if not isinstance(name, str):
        name = fallback_name
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise LabError("invalid_worldbook", f"{name}.entries[{index}] must be an object")
        identifier = raw.get("identifier", raw.get("uid", str(index)))
        strategy = raw.get("strategy")
        if strategy is None:
            constant_value = require_bool(raw["constant"], f"{name}:{identifier}.constant") if "constant" in raw else False
            strategy = "constant" if constant_value else "keyword"
        if strategy not in {"constant", "keyword"}:
            raise LabError("invalid_worldbook", f"{name}:{identifier} has invalid strategy")
        secondary_strategy = raw.get("secondaryKeywordStrategy")
        if secondary_strategy is None:
            selective_value = require_bool(raw["selective"], f"{name}:{identifier}.selective") if "selective" in raw else False
            secondary_strategy = "andAny" if selective_value else "none"
        if secondary_strategy not in SECONDARY_STRATEGIES:
            raise LabError(
                "invalid_worldbook", f"{name}:{identifier} has invalid secondaryKeywordStrategy"
            )
        position = raw.get("injectionPosition", raw.get("position", "lorebookAfter"))
        position = {"before_char": "lorebookBefore", "after_char": "lorebookAfter"}.get(
            position, position
        )
        position_fallback = position not in WORLD_POSITIONS
        if "enabled" in raw:
            enabled = require_bool(raw["enabled"], f"{name}:{identifier}.enabled")
        elif "disable" in raw:
            enabled = not require_bool(raw["disable"], f"{name}:{identifier}.disable")
        else:
            enabled = True
        case_sensitive_raw = raw.get("caseSensitive", raw.get("case_sensitive", False))
        whole_word_raw = raw.get("matchWholeWord", raw.get("matchWholeWords", True))
        case_sensitive = require_bool(case_sensitive_raw, f"{name}:{identifier}.caseSensitive")
        whole_word = require_bool(whole_word_raw, f"{name}:{identifier}.matchWholeWord")
        content = raw.get("content", "")
        role = raw.get("injectionRole", "system")
        if not isinstance(content, str) or role not in ROLES:
            raise LabError("invalid_worldbook", f"{name}:{identifier} has invalid content or role")
        if position_fallback:
            position = "lorebookAfter"
        normalized.append(
            {
                **raw,
                "identifier": str(identifier),
                "name": str(raw.get("name", raw.get("comment", identifier))),
                "content": content,
                "enabled": enabled,
                "strategy": strategy,
                "keywords": list_of_strings(raw.get("keywords", raw.get("keys", raw.get("key"))), f"{name}:{identifier}.keywords"),
                "secondaryKeywords": list_of_strings(
                    raw.get("secondaryKeywords", raw.get("secondary_keys", raw.get("keysecondary"))),
                    f"{name}:{identifier}.secondaryKeywords",
                ),
                "secondaryKeywordStrategy": secondary_strategy,
                "scanDepth": raw.get(
                    "scanDepth",
                    raw.get("scan_depth", value.get("scanDepth", value.get("scan_depth", 2))),
                ),
                "caseSensitive": case_sensitive,
                "matchWholeWord": whole_word,
                "injectionPosition": position,
                "_positionFallback": position_fallback,
                "injectionDepth": raw.get("injectionDepth", raw.get("depth", 4)),
                "injectionRole": role,
                "probability": raw.get("probability", 100),
                "sticky": raw.get("sticky", 0),
                "cooldown": raw.get("cooldown", 0),
                "delay": raw.get("delay", 0),
            }
        )
    return {**value, "name": name, "entries": normalized}


def validate_int(value: Any, label: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LabError("invalid_number", f"{label} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise LabError("invalid_number", f"{label} must be <= {maximum}")
    return value


def json_size(value: Any) -> int:
    return len(strict_json_dumps(value, ensure_ascii=False).encode("utf-8"))


def ensure_text_budget(value: str, source: str) -> None:
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise LabError("text_too_large", f"text exceeds {MAX_TEXT_BYTES} bytes: {source}")


def find_sensitive_parameter_paths(value: Any, path: str = "model.parameters") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if normalized_security_key(key) in NORMALIZED_SENSITIVE_PARAMETER_KEYS:
                found.append(child_path)
            found.extend(find_sensitive_parameter_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_sensitive_parameter_paths(child, f"{path}[{index}]"))
    return found


def keyword_hit(text: str, keyword: str, *, case_sensitive: bool, whole_word: bool) -> bool:
    flags = 0 if case_sensitive else re.IGNORECASE
    escaped = re.escape(keyword)
    pattern = rf"(?<!\w){escaped}(?!\w)" if whole_word else escaped
    return re.search(pattern, text, flags) is not None


def deterministic_roll(seed: Any, book_index: int, identifier: str) -> float:
    digest = hashlib.sha256(f"{seed!r}:{book_index}:{identifier}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64 * 100.0


def evaluate_worldbooks(
    books: list[dict[str, Any]],
    history: list[dict[str, str]],
    user_input: str,
    seed: Any,
    context: dict[str, str],
    renderer: EjsRenderer,
    warnings: list[WarningItem],
) -> tuple[
    dict[str, list[str]],
    list[AbsoluteInjection],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    buckets = {
        "lorebookBefore": [],
        "lorebookAfter": [],
        "topOfExampleMessages": [],
        "bottomOfExampleMessages": [],
    }
    absolute: list[AbsoluteInjection] = []
    triggered: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for book_index, book in enumerate(books):
        for entry_index, entry in enumerate(book["entries"]):
            source = f"worldbook:{book['name']}:{entry['identifier']}"
            decision: dict[str, Any] = {
                "worldbook": book["name"],
                "entry": entry["identifier"],
                "entryName": entry["name"],
                "entryIndex": entry_index,
            }
            if not entry["enabled"]:
                decisions.append({**decision, "status": "disabled"})
                continue
            if not entry["content"]:
                decisions.append({**decision, "status": "empty_content"})
                continue
            scan_depth = validate_int(entry["scanDepth"], f"{source}.scanDepth", 0, 1000)
            probability = validate_int(entry["probability"], f"{source}.probability", 0, 100)
            depth = validate_int(entry["injectionDepth"], f"{source}.injectionDepth", 0)
            timing = {
                name: validate_int(entry[name], f"{source}.{name}", 0)
                for name in ("sticky", "cooldown", "delay")
            }
            if entry["_positionFallback"]:
                warnings.append(
                    WarningItem(
                        "unsupported_worldbook_position",
                        "An unknown or numeric worldbook position was mapped to lorebookAfter; import/read back through Tavo for an authoritative conversion.",
                        source,
                    )
                )
            unsupported_features: list[str] = []
            if entry.get("useRegex"):
                unsupported_features.append("useRegex")
            if entry.get("excludeRecursion") or entry.get("preventRecursion"):
                unsupported_features.append("recursion controls")
            if entry.get("delayUntilRecursion"):
                unsupported_features.append("delayUntilRecursion")
            if entry.get("groupName") or entry.get("groupOverride") or entry.get("useGroupScoring"):
                unsupported_features.append("group scoring")
            if unsupported_features:
                warnings.append(
                    WarningItem(
                        "worldbook_feature_not_simulated",
                        "Prompt Lab v2 does not simulate: " + ", ".join(unsupported_features) + ".",
                        source,
                    )
                )
            # In the supported Tavo 1.0 scanDepth=2 behavior, current input
            # consumes one depth slot and the immediately preceding visible
            # message consumes the other. Depth=0 remains a current-input-only
            # Prompt Lab approximation.
            prior_message_count = max(0, scan_depth - 1) if scan_depth else 0
            scan_messages = history[-prior_message_count:] if prior_message_count else []
            corpus = "\n".join([*(item["content"] for item in scan_messages), user_input])
            if entry["strategy"] == "keyword":
                rendered_keywords = [
                    render_text(
                        keyword,
                        context,
                        renderer,
                        warnings,
                        f"{source}.keywords[{keyword_index}]",
                    )
                    for keyword_index, keyword in enumerate(entry["keywords"])
                ]
                rendered_secondary = [
                    render_text(
                        keyword,
                        context,
                        renderer,
                        warnings,
                        f"{source}.secondaryKeywords[{keyword_index}]",
                    )
                    for keyword_index, keyword in enumerate(entry["secondaryKeywords"])
                ]
            else:
                rendered_keywords = []
                rendered_secondary = []
            primary_matches = [
                keyword
                for keyword in rendered_keywords
                if keyword
                if keyword_hit(
                    corpus,
                    keyword,
                    case_sensitive=entry["caseSensitive"],
                    whole_word=entry["matchWholeWord"],
                )
            ]
            secondary_matches = [
                keyword
                for keyword in rendered_secondary
                if keyword
                if keyword_hit(
                    corpus,
                    keyword,
                    case_sensitive=entry["caseSensitive"],
                    whole_word=entry["matchWholeWord"],
                )
            ]
            if entry["strategy"] == "constant":
                condition = True
                failure_status = "triggered"
            else:
                primary_condition = bool(primary_matches)
                condition = primary_condition
                failure_status = "keyword_miss" if not primary_condition else "triggered"
                secondary = rendered_secondary
                secondary_strategy = entry["secondaryKeywordStrategy"]
                warnings.append(
                    WarningItem(
                        "scan_depth_policy",
                        "Prompt Lab v2.3 counts the current input as one scanDepth slot and scans up to scanDepth-1 prior visible messages; scanDepth=0 still scans the current input as an explicit approximation.",
                        source,
                    )
                )
                if entry["matchWholeWord"] and any(not keyword.isascii() for keyword in rendered_keywords):
                    warnings.append(
                        WarningItem(
                            "cjk_whole_word_approximation",
                            "Whole-word matching for non-ASCII keywords uses Python Unicode word boundaries and may differ from Tavo.",
                            source,
                        )
                    )
                if secondary_strategy != "none" and not secondary:
                    warnings.append(
                        WarningItem(
                            "empty_secondary_keywords",
                            "A non-none secondary strategy with no secondary keywords is undefined in Tavo; v2 does not trigger it.",
                            source,
                        )
                    )
                    condition = False
                    failure_status = "secondary_undefined"
                elif secondary_strategy == "andAny":
                    condition = condition and bool(secondary_matches)
                    if primary_condition and not condition:
                        failure_status = "secondary_miss"
                elif secondary_strategy == "andAll":
                    condition = condition and len(secondary_matches) == len(secondary)
                    if primary_condition and not condition:
                        failure_status = "secondary_miss"
                elif secondary_strategy == "notAny":
                    condition = condition and not secondary_matches
                    if primary_condition and not condition:
                        failure_status = "secondary_excluded"
                elif secondary_strategy == "notAll":
                    condition = condition and len(secondary_matches) < len(secondary)
                    if primary_condition and not condition:
                        failure_status = "secondary_excluded"
            roll = deterministic_roll(seed, book_index, entry["identifier"])
            passed_probability = probability == 100 or probability > 0 and roll < probability
            if 0 < probability < 100:
                warnings.append(
                    WarningItem(
                        "probability_simulated",
                        "A deterministic Prompt Lab seed roll was used; it does not reproduce Tavo's private random draw.",
                        source,
                    )
                )
            if any(timing.values()):
                warnings.append(
                    WarningItem(
                        "stateful_timing_approximated",
                        "sticky/cooldown/delay state is not simulated; v2 evaluates the current trigger only.",
                        source,
                    )
                )
            if "priority" in entry or "order" in entry or "insertion_order" in entry:
                warnings.append(
                    WarningItem(
                        "worldbook_order_policy",
                        "Prompt Lab v2 preserves worldbook and entry array order; it does not re-sort competing entries by priority/order.",
                        source,
                    )
                )
            decision.update(
                {
                    "strategy": entry["strategy"],
                    "matchedKeywords": primary_matches,
                    "matchedSecondaryKeywords": secondary_matches,
                    "probability": probability,
                    "probabilityRoll": round(roll, 6),
                }
            )
            if not condition:
                decisions.append({**decision, "status": failure_status})
                continue
            if not passed_probability:
                decisions.append({**decision, "status": "probability_miss"})
                continue
            rendered = render_text(entry["content"], context, renderer, warnings, source)
            position = entry["injectionPosition"]
            if position == "atDepth":
                absolute.append(
                    AbsoluteInjection(
                        source=source,
                        identifier=entry["identifier"],
                        content=rendered,
                        role=entry["injectionRole"],
                        depth=depth,
                    )
                )
            else:
                buckets[position].append(rendered)
            triggered.append(
                {
                    "worldbook": book["name"],
                    "entry": entry["identifier"],
                    "entryName": entry["name"],
                    "strategy": entry["strategy"],
                    "matchedKeywords": primary_matches,
                    "matchedSecondaryKeywords": secondary_matches,
                    "probability": probability,
                    "probabilityRoll": round(roll, 6),
                    "injectionPosition": position,
                    "injectionDepth": depth if position == "atDepth" else None,
                    "injectionRole": entry["injectionRole"],
                    "entryIndex": entry_index,
                }
            )
            decisions.append({**decision, "status": "triggered"})
    return buckets, absolute, triggered, decisions


def macro_context(
    character: dict[str, Any], persona: dict[str, Any], history: list[dict[str, str]], user_input: str
) -> dict[str, str]:
    last_assistant = next(
        (item["content"] for item in reversed(history) if item["role"] == "assistant"), ""
    )
    description = str(character.get("description", ""))
    personality = str(character.get("personality", ""))
    scenario = str(character.get("scenario", ""))
    examples = str(character.get("mes_example", character.get("messageExample", "")))
    main_prompt = str(character.get("system_prompt", ""))
    post_history = str(character.get("post_history_instructions", ""))
    return {
        "char": str(character.get("name", "")),
        "user": str(persona.get("name", "User")),
        "charifnotgroup": str(character.get("name", "")),
        "persona": str(persona.get("description", "")),
        "chardescription": description,
        "description": description,
        "charpersonality": personality,
        "personality": personality,
        "charscenario": scenario,
        "scenario": scenario,
        "charprompt": main_prompt,
        "charinstruction": post_history,
        "charjailbreak": post_history,
        "mesexamples": examples,
        "mesexamplesraw": examples,
        "charversion": str(character.get("character_version", character.get("version", ""))),
        "charcreatornotes": str(character.get("creator_notes", "")),
        "creatornotes": str(character.get("creator_notes", "")),
        "input": user_input,
        "lastmessage": history[-1]["content"] if history else user_input,
        "lastusermessage": user_input,
        "lastcharmessage": last_assistant,
    }


def render_macros(
    text: str,
    context: dict[str, str],
    renderer: EjsRenderer,
    warnings: list[WarningItem],
    source: str,
) -> str:
    protected: dict[str, str] = {}

    def protect(match: re.Match[str]) -> str:
        index = len(protected)
        marker = f"\ue100TAVO_MACRO_LITERAL_{index}\ue101"
        while marker in text or marker in protected:
            index += 1
            marker = f"\ue100TAVO_MACRO_LITERAL_{index}\ue101"
        protected[marker] = "{{" + match.group(1) + "}}"
        return marker

    rendered = ESCAPED_MACRO_RE.sub(protect, text)
    unknown: set[str] = set()
    trim_requested = False

    def bounded_count(value: str, name: str) -> int | None:
        if not value:
            return 1
        try:
            count = int(value)
        except ValueError:
            unknown.add(f"{{{{{name}::{value}}}}}")
            return None
        if not 0 <= count <= 10_000:
            unknown.add(f"{{{{{name}::{value}}}}}")
            return None
        return count

    for _ in range(8):
        pass_changed = False

        def replace(match: re.Match[str]) -> str:
            nonlocal pass_changed, trim_requested
            raw = match.group(1)
            stripped = raw.strip()
            if stripped.startswith("//"):
                pass_changed = True
                return ""
            parts = raw.split("::")
            name = parts[0].strip().lower()
            args = parts[1:]
            if name in context and not args:
                pass_changed = True
                return context[name]
            if name == "newline" and len(args) <= 1:
                count = bounded_count(args[0].strip() if args else "", name)
                if count is not None:
                    pass_changed = True
                    return "\n" * count
            elif name == "space" and len(args) <= 1:
                count = bounded_count(args[0].strip() if args else "", name)
                if count is not None:
                    pass_changed = True
                    return " " * count
            elif name == "trim" and not args:
                trim_requested = True
                pass_changed = True
                return ""
            elif name == "noop" and not args:
                pass_changed = True
                return ""
            elif name in {
                "setvar",
                "addvar",
                "incvar",
                "decvar",
                "getvar",
                "setglobalvar",
                "addglobalvar",
                "incglobalvar",
                "decglobalvar",
                "getglobalvar",
            }:
                scope = "global" if "global" in name else "chat"
                operation = name.replace("global", "")
                if not args or not args[0].strip():
                    unknown.add(match.group(0))
                    return match.group(0)
                key = args[0].strip()
                if operation in {"setvar", "addvar"}:
                    if len(args) < 2:
                        unknown.add(match.group(0))
                        return match.group(0)
                    value = parse_macro_value("::".join(args[1:]))
                    if operation == "setvar":
                        renderer.set_variable(key, value, scope)
                    else:
                        renderer.add_variable(key, value, scope)
                    pass_changed = True
                    return ""
                if operation in {"incvar", "decvar"} and len(args) == 1:
                    renderer.increment_variable(key, 1 if operation == "incvar" else -1, scope)
                    pass_changed = True
                    return ""
                if operation == "getvar" and len(args) == 1:
                    pass_changed = True
                    return macro_value_text(renderer.get_variable(key, scope))
            unknown.add(match.group(0))
            return match.group(0)

        next_value = MACRO_RE.sub(replace, rendered)
        ensure_text_budget(next_value, source)
        rendered = next_value
        if not pass_changed:
            break
    leftovers = {match.group(0) for match in ANY_MACRO_RE.finditer(rendered)}
    if leftovers:
        unknown.update(leftovers)
    for marker, literal in protected.items():
        rendered = rendered.replace(marker, literal)
    if trim_requested:
        rendered = rendered.strip()
    if unknown:
        unknown_items = sorted(unknown)
        preview = ", ".join(item[:160] for item in unknown_items[:20])
        if len(unknown_items) > 20:
            preview += f", ... ({len(unknown_items) - 20} more)"
        warnings.append(
            WarningItem(
                "unresolved_macros",
                "Unsupported or unavailable macros were retained: " + preview,
                source,
            )
        )
    return rendered


def render_text(
    text: str,
    context: dict[str, str],
    renderer: EjsRenderer,
    warnings: list[WarningItem],
    source: str,
    *,
    allow_ejs: bool = True,
) -> str:
    if not text:
        return ""
    ensure_text_budget(text, source)
    if EJS_RE.search(text):
        if allow_ejs:
            text, macro_allowed = renderer.render_ejs(text, warnings, source)
            if not macro_allowed:
                return text
        else:
            warnings.append(
                WarningItem(
                    "runtime_ejs_literal",
                    "EJS-like text in an existing chat message or current user input is treated as literal text; only authored card, persona, preset, worldbook, and selected greeting fields execute EJS.",
                    source,
                )
            )
    return render_macros(text, context, renderer, warnings, source)


def wrap_lorebook(content: str, wrapper: Any, warnings: list[WarningItem], source: str) -> str:
    if not content:
        return ""
    if not isinstance(wrapper, str) or not wrapper:
        return content
    if "{0}" not in wrapper:
        warnings.append(
            WarningItem(
                "lorebook_wrapper_missing_slot",
                "basicPrompts.lorebook has no {0}; live Tavo 1.0 renders the wrapper but drops the activated lorebook content.",
                source,
            )
        )
        return wrapper
    return wrapper.replace("{0}", content)


def dialogue_examples(character: dict[str, Any], basic: dict[str, Any]) -> str:
    raw = character.get("mes_example", character.get("messageExample", ""))
    if not isinstance(raw, str) or not raw.strip():
        return ""
    blocks = [part.strip() for part in re.split(r"(?m)^\s*<START>\s*$", raw) if part.strip()]
    heading = basic.get("exampleMessageStart", "[Example dialogue]")
    if not isinstance(heading, str):
        heading = "[Example dialogue]"
    formatted_blocks = [re.sub(r"\r?\n+", "\n\n", block) for block in blocks]
    return "\n\n".join(
        f"{heading}\n\n{block}" if heading else block for block in formatted_blocks
    )


def worldbook_example_entries(
    contents: list[str], basic: dict[str, Any], character_name: str
) -> str:
    heading = basic.get("exampleMessageStart", "[Example dialogue]")
    if not isinstance(heading, str):
        heading = "[Example dialogue]"
    return "\n\n".join(
        f"{heading}\n\n{character_name}: {content}" if heading else f"{character_name}: {content}"
        for content in contents
    )


def add_chunk(
    messages: list[dict[str, str]],
    role: str,
    content: str,
    budget: AssemblyBudget | None = None,
    source: str = "prompt",
    *,
    merge: bool = True,
) -> None:
    if not content:
        return
    if budget is not None:
        budget.add(content, source)
    if merge and messages and messages[-1]["role"] == role:
        messages[-1]["content"] += "\n\n" + content
    else:
        messages.append({"role": role, "content": content})


def apply_absolute(
    conversation: list[dict[str, str]],
    injections: list[AbsoluteInjection],
    warnings: list[WarningItem],
) -> tuple[list[dict[str, str]], list[AbsoluteInjection], list[AbsoluteInjection]]:
    buckets: dict[int, list[AbsoluteInjection]] = {}
    applied: list[AbsoluteInjection] = []
    omitted: list[AbsoluteInjection] = []
    length = len(conversation)
    for item in injections:
        if item.depth > length:
            warnings.append(
                WarningItem(
                    "absolute_depth_out_of_range",
                    "The injection depth exceeds available history and was omitted; Tavo fallback behavior is not proven.",
                    item.source,
                )
            )
            omitted.append(item)
            continue
        anchor = length - item.depth
        buckets.setdefault(anchor, []).append(item)
        applied.append(item)
    for anchor, items in buckets.items():
        if len(items) > 1:
            warnings.append(
                WarningItem(
                    "absolute_depth_collision",
                    "Multiple injections share one depth; Prompt Lab preserves source order, but Tavo tie-breaking is unproved.",
                    f"depth:{length - anchor}",
                )
            )
    result: list[dict[str, str]] = []
    for index in range(length + 1):
        anchor_items = buckets.get(index, [])
        merged_items = [item for item in anchor_items if item.merge_into_anchor]
        separate_items = [item for item in anchor_items if not item.merge_into_anchor]
        if index < length:
            for item in separate_items:
                result.append({"role": item.role, "content": item.content})
            current = dict(conversation[index])
            if merged_items:
                current["content"] = "\n\n".join(
                    [*(item.content for item in merged_items), current["content"]]
                )
            result.append(current)
        else:
            if merged_items and result:
                result[-1]["content"] += "\n\n" + "\n\n".join(item.content for item in merged_items)
            for item in separate_items:
                result.append({"role": item.role, "content": item.content})
    return result, applied, omitted


def merge_adjacent(messages: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in messages:
        add_chunk(result, item["role"], item["content"])
    return result


def apply_tavo_openai_role_adapter(
    messages: Iterable[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Apply the supported Tavo 1.0 OpenAI-compatible role policy.

    Keep the first leading system chunk as system, coerce later logical system
    chunks to user, and then merge adjacent equal roles with two newlines. This
    is limited to native Tavo presets; exported prompts+prompt_order uses its
    separate Tavo 0.93 compatibility path.
    """

    normalized: list[dict[str, str]] = []
    trace: list[dict[str, Any]] = []
    for index, item in enumerate(messages):
        source_role = item["role"]
        adapter_role = source_role
        if source_role == "system" and normalized:
            adapter_role = "user"
        trace.append(
            {
                "logicalIndex": index,
                "sourceRole": source_role,
                "adapterRole": adapter_role,
                "coerced": adapter_role != source_role,
            }
        )
        add_chunk(normalized, adapter_role, item["content"])
    return normalized, trace


def normalize_regex_groups(value: Any, base_dir: Path) -> list[dict[str, Any]]:
    """Normalize the supported Tavo native regex shape."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise LabError("invalid_regexes", "case.regexes must be an array")
    if len(value) > MAX_REGEX_GROUPS:
        raise LabError("too_many_regexes", f"case.regexes exceeds {MAX_REGEX_GROUPS} groups")
    groups: list[dict[str, Any]] = []
    entry_count = 0
    for group_index, source in enumerate(value):
        group = unwrap_mcp_text(resolve_json(source, base_dir, f"regexes[{group_index}]"))
        if isinstance(group.get("regex"), dict):
            group = group["regex"]
        name = group.get("name")
        entries = group.get("entries", [])
        if not isinstance(name, str) or not name:
            raise LabError("invalid_regex", f"regexes[{group_index}].name must be a non-empty string")
        if not isinstance(entries, list):
            raise LabError("invalid_regex", f"regexes[{group_index}].entries must be an array")
        entry_count += len(entries)
        if entry_count > MAX_ENTRIES:
            raise LabError("too_many_entries", f"combined regex entries exceed {MAX_ENTRIES}")
        normalized_entries: list[dict[str, Any]] = []
        for entry_index, raw in enumerate(entries):
            label = f"regexes[{group_index}].entries[{entry_index}]"
            if not isinstance(raw, dict):
                raise LabError("invalid_regex", f"{label} must be an object")
            identifier = raw.get("identifier")
            entry_name = raw.get("name")
            find_regex = raw.get("findRegex")
            replace_string = raw.get("replaceString")
            trim_strings = raw.get("trimStrings", [])
            placements = raw.get("placements")
            timing = raw.get("timing")
            substitution = raw.get("substitution")
            enabled = raw.get("enabled", True)
            if not isinstance(identifier, str) or not identifier:
                raise LabError("invalid_regex", f"{label}.identifier must be a non-empty string")
            if not isinstance(entry_name, str):
                raise LabError("invalid_regex", f"{label}.name must be a string")
            if not isinstance(find_regex, str) or not find_regex:
                raise LabError("invalid_regex", f"{label}.findRegex must be a non-empty string")
            if not isinstance(replace_string, str):
                raise LabError("invalid_regex", f"{label}.replaceString must be a string")
            if not isinstance(trim_strings, list) or any(not isinstance(item, str) for item in trim_strings):
                raise LabError("invalid_regex", f"{label}.trimStrings must be a string array")
            if not isinstance(placements, list) or not placements or any(item not in REGEX_PLACEMENTS for item in placements):
                raise LabError(
                    "invalid_regex",
                    f"{label}.placements must be a non-empty array of user/char/reasoning/lorebook",
                )
            if timing not in REGEX_TIMINGS:
                raise LabError("invalid_regex", f"{label}.timing is unsupported")
            if substitution not in REGEX_SUBSTITUTIONS:
                raise LabError("invalid_regex", f"{label}.substitution is unsupported")
            if not isinstance(enabled, bool):
                raise LabError("invalid_regex", f"{label}.enabled must be a boolean")
            minimum = raw.get("minDepth")
            maximum = raw.get("maxDepth")
            for depth_name, depth_value in (("minDepth", minimum), ("maxDepth", maximum)):
                if depth_value is not None and (
                    isinstance(depth_value, bool) or not isinstance(depth_value, int) or depth_value < 0
                ):
                    raise LabError("invalid_regex", f"{label}.{depth_name} must be null or an integer >= 0")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise LabError("invalid_regex", f"{label}.minDepth cannot exceed maxDepth")
            if trim_strings:
                raise LabError(
                    "unsupported_regex_trim_strings",
                    f"{label}.trimStrings is non-empty; its byte-level Tavo ordering is not supported by Prompt Lab",
                )
            if substitution == "escaped":
                raise LabError(
                    "unsupported_regex_escaped_substitution",
                    f"{label} uses escaped substitution, whose byte-level Tavo escaping is not supported by Prompt Lab",
                )
            if "reasoning" in placements:
                raise LabError(
                    "unsupported_regex_reasoning",
                    f"{label} targets reasoning, which is outside the current Prompt Lab support boundary",
                )
            if "lorebook" in placements and (minimum is not None or maximum is not None):
                raise LabError(
                    "unsupported_regex_lorebook_depth",
                    f"{label} combines lorebook placement with depth bounds, whose counting domain is not supported by Prompt Lab",
                )
            normalized_entries.append(
                {
                    "identifier": identifier,
                    "name": entry_name,
                    "findRegex": find_regex,
                    "replaceString": replace_string,
                    "trimStrings": list(trim_strings),
                    "placements": list(placements),
                    "timing": timing,
                    "substitution": substitution,
                    "minDepth": minimum,
                    "maxDepth": maximum,
                    "enabled": enabled,
                }
            )
        groups.append({"name": name, "entries": normalized_entries})
    return groups


def render_regex_groups(
    groups: list[dict[str, Any]],
    context: dict[str, str],
    renderer: EjsRenderer,
    warnings: list[WarningItem],
) -> list[dict[str, Any]]:
    """Render regex fields as Tavo does: EJS first, then optional raw macros."""

    rendered_groups: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups):
        rendered_entries: list[dict[str, Any]] = []
        for entry_index, entry in enumerate(group["entries"]):
            rendered_entry = copy.deepcopy(entry)
            substitution = entry["substitution"]
            for field in ("findRegex", "replaceString"):
                source = f"regex:{group_index}:{entry['identifier']}.{field}"
                text = entry[field]
                ensure_text_budget(text, source)
                macro_allowed = True
                if EJS_RE.search(text):
                    text, macro_allowed = renderer.render_ejs(text, warnings, source)
                if macro_allowed and substitution == "raw":
                    text = render_macros(text, context, renderer, warnings, source)
                ensure_text_budget(text, source)
                rendered_entry[field] = text
            rendered_entries.append(rendered_entry)
        rendered_groups.append({"name": group["name"], "entries": rendered_entries})
    return rendered_groups


def parse_regex_pattern(value: str, source: str) -> tuple[re.Pattern[str], bool]:
    pattern = value
    flags_text = "g"
    if value.startswith("/"):
        closing = None
        for index in range(len(value) - 1, 0, -1):
            if value[index] != "/":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and value[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                closing = index
                break
        if closing is None:
            raise LabError("invalid_regex_pattern", f"{source} has no closing slash")
        pattern = value[1:closing].replace(r"\/", "/")
        flags_text = value[closing + 1 :]
    unsupported = set(flags_text).difference("gimsu")
    if unsupported:
        raise LabError(
            "unsupported_regex_flags",
            f"{source} uses unsupported flags: {''.join(sorted(unsupported))}",
        )
    python_flags = 0
    if "i" in flags_text:
        python_flags |= re.IGNORECASE
    if "m" in flags_text:
        python_flags |= re.MULTILINE
    if "s" in flags_text:
        python_flags |= re.DOTALL
    # JavaScript named captures use (?<name>...), while Python uses
    # (?P<name>...). Translate only identifier-shaped captures; lookbehind
    # prefixes (?<=...) and (?<!...) do not match this expression.
    pattern = re.sub(
        r"\(\?<([A-Za-z_][A-Za-z0-9_]*)>",
        r"(?P<\1>",
        pattern,
    )
    try:
        return re.compile(pattern, python_flags), "g" in flags_text
    except re.error as error:
        raise LabError(
            "unsupported_regex_pattern",
            f"{source} cannot be represented by the bounded Python regex adapter: {error}",
        ) from error


def javascript_replacement(match: re.Match[str], replacement: str) -> str:
    """Apply the JavaScript String.replace replacement-token subset exactly.

    The supported surface covers every standard replacement token: ``$$``,
    ``$&``, the prefix/suffix tokens, ``$1``..``$99``, and ``$<name>``.
    A malformed or unknown named capture fails closed instead of silently
    producing a Python-specific approximation.
    """

    replacement = replacement.replace("{{match}}", match.group(0))
    result: list[str] = []
    index = 0
    while index < len(replacement):
        if replacement[index] != "$" or index + 1 >= len(replacement):
            result.append(replacement[index])
            index += 1
            continue
        next_value = replacement[index + 1]
        if next_value == "$":
            result.append("$")
            index += 2
            continue
        if next_value == "&":
            result.append(match.group(0))
            index += 2
            continue
        if next_value == "`":
            result.append(match.string[: match.start()])
            index += 2
            continue
        if next_value == "'":
            result.append(match.string[match.end() :])
            index += 2
            continue
        if next_value == "<":
            closing = replacement.find(">", index + 2)
            if closing < 0:
                raise LabError(
                    "unsupported_regex_replacement",
                    "regex replacement contains an unterminated $<name> token",
                )
            name = replacement[index + 2 : closing]
            if not name or name not in match.re.groupindex:
                raise LabError(
                    "unsupported_regex_replacement",
                    f"regex replacement references unavailable named capture: {name or '<empty>'}",
                )
            result.append(match.groupdict().get(name) or "")
            index = closing + 1
            continue
        if next_value.isdigit() and next_value != "0":
            digits = next_value
            if index + 2 < len(replacement) and replacement[index + 2].isdigit():
                candidate = digits + replacement[index + 2]
                if int(candidate) <= (match.re.groups or 0):
                    digits = candidate
            group_index = int(digits)
            if group_index <= (match.re.groups or 0):
                result.append(match.group(group_index) or "")
                index += 1 + len(digits)
                continue
        result.append("$")
        index += 1
    return "".join(result)


def regex_surface_timings(surface: str) -> frozenset[str]:
    if surface == "send":
        return frozenset({"send", "sendAndDisplay"})
    if surface == "display":
        return frozenset({"display", "sendAndDisplay"})
    if surface == "receive":
        return frozenset({"receive", "editAndReceive"})
    raise LabError("invalid_regex_surface", f"unknown regex surface: {surface}")


def regex_depth_applies(entry: dict[str, Any], depth: int) -> bool:
    minimum = entry.get("minDepth")
    maximum = entry.get("maxDepth")
    return (minimum is None or depth >= minimum) and (maximum is None or depth <= maximum)


def apply_regex_value(
    value: str,
    groups: list[dict[str, Any]],
    *,
    placement: str,
    surface: str,
    depth: int,
    location: str,
) -> tuple[str, list[dict[str, Any]]]:
    result = value
    trace: list[dict[str, Any]] = []
    allowed_timings = regex_surface_timings(surface)
    for group_index, group in enumerate(groups):
        for entry_index, entry in enumerate(group["entries"]):
            if (
                not entry["enabled"]
                or placement not in entry["placements"]
                or entry["timing"] not in allowed_timings
                or not regex_depth_applies(entry, depth)
            ):
                continue
            source = f"regex:{group_index}:{entry['identifier']}"
            pattern, global_replace = parse_regex_pattern(entry["findRegex"], source)
            before = result
            match_count = 0

            def replace(match: re.Match[str]) -> str:
                nonlocal match_count
                match_count += 1
                return javascript_replacement(match, entry["replaceString"])

            result = pattern.sub(replace, result, count=0 if global_replace else 1)
            ensure_text_budget(result, f"{source}:{surface}:{location}")
            if match_count:
                trace.append(
                    {
                        "groupIndex": group_index,
                        "group": group["name"],
                        "entryIndex": entry_index,
                        "entry": entry["identifier"],
                        "surface": surface,
                        "placement": placement,
                        "location": location,
                        "depth": depth,
                        "matchCount": match_count,
                        "changed": result != before,
                        "beforeSha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
                        "afterSha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
                    }
                )
    return result, trace


def apply_regex_messages(
    messages: list[dict[str, str]],
    groups: list[dict[str, Any]],
    *,
    surface: str,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    result = copy.deepcopy(messages)
    trace: list[dict[str, Any]] = []
    total = len(result)
    for index, item in enumerate(result):
        placement = "user" if item["role"] == "user" else "char" if item["role"] == "assistant" else None
        if placement is None:
            continue
        depth = total - 1 - index
        item["content"], item_trace = apply_regex_value(
            item["content"],
            groups,
            placement=placement,
            surface=surface,
            depth=depth,
            location=f"message:{index}",
        )
        trace.extend(item_trace)
    return result, trace


def apply_regex_lorebook_buckets(
    buckets: dict[str, list[str]], groups: list[dict[str, Any]]
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    result = copy.deepcopy(buckets)
    trace: list[dict[str, Any]] = []
    for bucket, values in result.items():
        for index, value in enumerate(values):
            values[index], item_trace = apply_regex_value(
                value,
                groups,
                placement="lorebook",
                surface="send",
                depth=0,
                location=f"lorebook:{bucket}:{index}",
            )
            trace.extend(item_trace)
    return result, trace


def regex_response_surfaces(
    compiled: dict[str, Any], response: str
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]]]:
    groups = compiled.get("regex", {}).get("groups", [])
    persistent, receive_trace = apply_regex_value(
        response,
        groups,
        placement="char",
        surface="receive",
        depth=0,
        location="assistantResponse",
    )
    visible, display_trace = apply_regex_value(
        persistent,
        groups,
        placement="char",
        surface="display",
        depth=0,
        location="assistantResponse",
    )
    return persistent, visible, receive_trace, display_trace


def compile_case(case: dict[str, Any], base_dir: Path, *, model_override: str | None = None) -> dict[str, Any]:
    warnings: list[WarningItem] = case_schema_warnings(case)
    assembly_budget = AssemblyBudget()
    if "preset" not in case or "character" not in case:
        raise LabError("missing_asset", "case requires preset and character")
    preset = normalize_preset(resolve_json(case["preset"], base_dir, "preset"))
    if "active" in preset:
        preset_active = require_bool(preset["active"], "preset.active")
        if not preset_active:
            warnings.append(
                WarningItem(
                    "inactive_preset_explicitly_compiled",
                    "The supplied preset has active=false, but compile explicitly assembles it; activate and bind it separately in Tavo before a live comparison.",
                    "preset.active",
                )
            )
    preset_input = str(preset.get("_promptLabPresetInput", "tavo-native-basicPrompts-entries"))
    if preset_input == "tavo-exported-prompts-prompt_order-relative-v1":
        warnings.append(
            WarningItem(
                "tavo_exported_preset_normalized",
                "A single-order Tavo-exported prompts + prompt_order preset was normalized with the Tavo 0.93 relative-role compatibility mapping; non-relative and ambiguous orders remain fail-closed.",
                "preset",
            )
        )
    character = normalize_character(resolve_json(case["character"], base_dir, "character"))
    nickname = character.get("nickname")
    if isinstance(nickname, str) and nickname.strip():
        warnings.append(
            WarningItem(
                "nickname_single_chat_not_applied",
                "Single-chat nickname scope is not established in this Prompt Lab version, so {{char}} uses character.name and a non-empty nickname produces this warning.",
                "character.nickname",
            )
        )
    if character.get("group_only_greetings"):
        warnings.append(
            WarningItem(
                "group_greetings_not_consumed",
                "group_only_greetings is retained in the card but is not consumed by this single-chat compile.",
                "character.group_only_greetings",
            )
        )
    persona_value = case.get("persona")
    persona = normalize_persona(
        resolve_json(persona_value, base_dir, "persona") if persona_value is not None else None
    )
    regex_groups = normalize_regex_groups(case.get("regexes"), base_dir)
    history = normalize_history(case.get("history"), warnings)
    history, selected_greeting = choose_greeting(character, history, case.get("greeting"))
    user_input = case.get("userInput", case.get("input"))
    if not isinstance(user_input, str) or not user_input:
        raise LabError("invalid_input", "case.userInput must be a non-empty string")

    renderer = EjsRenderer(
        case.get("ejs"),
        character=character,
        persona=persona,
        history=history,
        user_input=user_input,
    )
    macro_values = case.get("macroValues", {})
    if not isinstance(macro_values, dict):
        raise LabError("invalid_macro_values", "case.macroValues must be an object")
    compile_clock = datetime_module.datetime.now().astimezone()
    clock_values = {
        "time": compile_clock.strftime("%H:%M"),
        "date": compile_clock.date().isoformat(),
        "weekday": compile_clock.strftime("%A"),
        "isotime": compile_clock.strftime("%H:%M"),
        "isodate": compile_clock.date().isoformat(),
    }

    def add_macro_values(target: dict[str, str]) -> None:
        target.update(clock_values)
        for key, value in macro_values.items():
            if not isinstance(key, str) or not isinstance(value, (str, int, float, bool)):
                raise LabError(
                    "invalid_macro_values",
                    "macroValues keys must be strings and values must be scalar",
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise LabError(
                    "invalid_macro_values",
                    "macroValues numbers must be finite",
                )
            target[key.lower()] = str(value)

    context = macro_context(character, persona, history, user_input)
    add_macro_values(context)
    persona["description"] = render_text(
        str(persona.get("description", "")),
        context,
        renderer,
        warnings,
        "persona.description",
    )
    for field in ("description", "personality", "scenario", "mes_example"):
        if field in character and isinstance(character[field], str):
            character[field] = render_text(
                character[field],
                context,
                renderer,
                warnings,
                f"character.{field}",
            )
            context = macro_context(character, persona, history, user_input)
            add_macro_values(context)
    if selected_greeting is not None:
        history[0]["content"] = render_text(
            history[0]["content"],
            context,
            renderer,
            warnings,
            "character.greeting",
        )
        renderer.constants["lastCharMessage"] = next(
            (item["content"] for item in reversed(history) if item["role"] == "assistant"), ""
        )
    context = macro_context(character, persona, history, user_input)
    add_macro_values(context)

    include_character_book = require_bool(
        case.get("includeCharacterBook", True), "case.includeCharacterBook"
    )
    books: list[dict[str, Any]] = []
    total_input_bytes = (
        json_size(preset) + json_size(character) + json_size(persona) + json_size(regex_groups)
    )
    total_entries = len(preset["entries"]) + sum(
        len(group["entries"]) for group in regex_groups
    )
    if include_character_book and isinstance(character.get("character_book"), dict):
        character_book = character["character_book"]
        unused_character_book_fields = [
            field
            for field in ("token_budget", "recursive_scanning")
            if field in character_book
        ]
        if unused_character_book_fields:
            warnings.append(
                WarningItem(
                    "character_book_budget_recursion_not_simulated",
                    "Prompt Lab v2 does not simulate character_book fields: "
                    + ", ".join(unused_character_book_fields)
                    + ".",
                    "character.character_book",
                )
            )
        books.append(normalize_worldbook(character["character_book"], f"{character['name']} character_book"))
        total_input_bytes += json_size(books[-1])
        total_entries += len(books[-1]["entries"])
    raw_books = case.get("worldbooks", [])
    if not isinstance(raw_books, list):
        raise LabError("invalid_worldbook", "case.worldbooks must be an array")
    if len(raw_books) + (1 if books else 0) > MAX_WORLD_BOOKS:
        raise LabError("too_many_worldbooks", f"worldbooks exceeds {MAX_WORLD_BOOKS} items")
    for index, raw_book in enumerate(raw_books):
        books.append(
            normalize_worldbook(resolve_json(raw_book, base_dir, f"worldbooks[{index}]"), f"Worldbook {index + 1}")
        )
        total_input_bytes += json_size(books[-1])
        total_entries += len(books[-1]["entries"])
        if total_input_bytes > MAX_TOTAL_INPUT_BYTES:
            raise LabError(
                "inputs_too_large",
                f"combined normalized assets exceed {MAX_TOTAL_INPUT_BYTES} bytes",
            )
        if total_entries > MAX_ENTRIES:
            raise LabError("too_many_entries", f"combined entries exceeds {MAX_ENTRIES} items")
    if total_input_bytes > MAX_TOTAL_INPUT_BYTES:
        raise LabError(
            "inputs_too_large", f"combined normalized assets exceed {MAX_TOTAL_INPUT_BYTES} bytes"
        )
    if total_entries > MAX_ENTRIES:
        raise LabError("too_many_entries", f"combined entries exceeds {MAX_ENTRIES} items")

    buckets, world_absolute, triggered, decisions = evaluate_worldbooks(
        books,
        history,
        user_input,
        case.get("seed", 0),
        context,
        renderer,
        warnings,
    )
    rendered_regex_groups = render_regex_groups(regex_groups, context, renderer, warnings)
    if len(rendered_regex_groups) > 1:
        warnings.append(
            WarningItem(
                "regex_group_order_bound_to_case",
                "Multiple regex groups execute in case.regexes order; entry order within a group is supported, while cross-group binding order is not established.",
                "regexes",
            )
        )
    buckets, regex_lorebook_trace = apply_regex_lorebook_buckets(
        buckets, rendered_regex_groups
    )
    basic = preset.get("basicPrompts", {})
    unused_single_chat_templates = [
        field
        for field in ("groupChatStart", "groupNudge", "continueNudge", "impersonation")
        if basic.get(field)
    ]
    if unused_single_chat_templates:
        warnings.append(
            WarningItem(
                "single_chat_templates_not_consumed",
                "This ordinary single-chat compile retains but does not consume basicPrompts fields: "
                + ", ".join(unused_single_chat_templates)
                + ".",
                "preset.basicPrompts",
            )
        )
    def marker_value(identifier: str) -> str | None:
        if identifier in {"worldInfoBefore", "worldInfoAfter"}:
            bucket = "lorebookBefore" if identifier == "worldInfoBefore" else "lorebookAfter"
            if not buckets[bucket]:
                return ""
            wrapper = render_text(
                str(basic.get("lorebook", "{0}")),
                context,
                renderer,
                warnings,
                f"basicPrompts.lorebook:{identifier}",
            )
            wrapped = wrap_lorebook(
                "\n\n".join(buckets[bucket]),
                wrapper,
                warnings,
                f"marker:{identifier}",
            )
            # Tavo 1.0 native worldbook markers keep one trailing newline before
            # normal adjacent-role merging. The exported 0.93 compatibility
            # path remains unchanged.
            if (
                preset_input == "tavo-native-basicPrompts-entries"
                and wrapped
                and not wrapped.endswith("\n")
            ):
                wrapped += "\n"
            return wrapped
        simple = {
            "personaDescription": ("persona", "{{persona}}"),
            "charDescription": ("description", "{{description}}"),
            "charPersonality": ("personality", "{{personality}}"),
            "scenario": ("scenario", "{{scenario}}"),
        }
        if identifier in simple:
            field, fallback = simple[identifier]
            return render_text(
                str(basic.get(field, fallback)),
                context,
                renderer,
                warnings,
                f"basicPrompts.{field}",
            )
        if identifier == "dialogueExamples":
            has_examples = bool(
                character.get("mes_example", character.get("messageExample", ""))
                or buckets["topOfExampleMessages"]
                or buckets["bottomOfExampleMessages"]
            )
            if not has_examples:
                return ""
            heading = render_text(
                str(basic.get("exampleMessageStart", "[Example dialogue]")),
                context,
                renderer,
                warnings,
                "basicPrompts.exampleMessageStart",
            )
            rendered_basic = {**basic, "exampleMessageStart": heading}
            return "\n\n".join(
                item
                for item in (
                    worldbook_example_entries(
                        buckets["topOfExampleMessages"],
                        rendered_basic,
                        str(character["name"]),
                    ),
                    dialogue_examples(character, rendered_basic),
                    worldbook_example_entries(
                        buckets["bottomOfExampleMessages"],
                        rendered_basic,
                        str(character["name"]),
                    ),
                )
                if item
            )
        return None
    pre: list[dict[str, str]] = []
    post: list[dict[str, str]] = []
    target = pre
    trace: list[dict[str, Any]] = []
    absolute = list(world_absolute)
    inserted_history = False
    active_identifiers: set[str] = set()

    for index, raw_entry in enumerate(preset["entries"]):
        if not isinstance(raw_entry, dict):
            raise LabError("invalid_preset", f"preset.entries[{index}] must be an object")
        identifier = str(raw_entry.get("identifier", f"entry-{index}"))
        source = f"preset:{identifier}"
        enabled = require_bool(raw_entry.get("enabled", True), f"{source}.enabled")
        active = require_bool(raw_entry.get("active", True), f"{source}.active")
        forbid_overrides = require_bool(
            raw_entry.get("forbidOverrides", False), f"{source}.forbidOverrides"
        )
        if not enabled or not active:
            trace.append({"source": source, "status": "disabled", "entryIndex": index})
            continue
        active_identifiers.add(identifier)
        role = raw_entry.get("role", "system")
        if role not in ROLES:
            raise LabError("invalid_preset", f"{source}.role must be system/user/assistant")
        entry_type = raw_entry.get("type", "custom")
        if entry_type not in {"builtin", "marker", "custom"}:
            raise LabError("invalid_preset", f"{source}.type must be builtin, marker, or custom")
        position = raw_entry.get("injectionPosition", "relative")
        if position == "absolute":
            depth = validate_int(raw_entry.get("injectionDepth", 0), f"{source}.injectionDepth", 0)
            content = render_text(
                str(raw_entry.get("content", "")), context, renderer, warnings, source
            )
            if content:
                assembly_budget.add(content, source)
                absolute.append(
                    AbsoluteInjection(source, identifier, content, role, depth, merge_into_anchor=True)
                )
                warnings.append(
                    WarningItem(
                        "preset_absolute_adapter_merge",
                        "In the Tavo 0.93 compatibility mapping, preset absolute text merges into the target history slot and the target slot role wins over the configured entry role.",
                        source,
                    )
                )
                trace.append(
                    {
                        "source": source,
                        "status": "absolute-staged",
                        "role": role,
                        "depth": depth,
                        "entryIndex": index,
                    }
                )
            continue
        if position != "relative":
            raise LabError("invalid_preset", f"{source}.injectionPosition must be relative or absolute")

        if identifier == "chatHistory" and entry_type == "marker":
            if inserted_history:
                warnings.append(WarningItem("duplicate_chat_history", "Only the first chatHistory marker is used.", source))
            else:
                chat_start = basic.get("chatStart", "[Start of current chat]")
                if isinstance(chat_start, str):
                    chat_start = render_text(
                        chat_start,
                        context,
                        renderer,
                        warnings,
                        "basicPrompts.chatStart",
                    )
                    add_chunk(
                        target,
                        role,
                        chat_start,
                        assembly_budget,
                        "basicPrompts.chatStart",
                        merge=False,
                    )
                inserted_history = True
                target = post
            trace.append({"source": source, "status": "history-boundary", "entryIndex": index})
            continue

        marker_rendered = False
        if entry_type == "marker":
            prepared_marker = marker_value(identifier)
            if prepared_marker is None:
                content = str(raw_entry.get("content", ""))
            else:
                content = prepared_marker
                marker_rendered = True
        elif identifier == "main" and character.get("system_prompt") and not forbid_overrides:
            content = str(character["system_prompt"]).replace("{{original}}", str(raw_entry.get("content", "")))
            warnings.append(
                WarningItem(
                    "card_prompt_override_approximation",
                    "The card main-prompt override follows the preset identifier/forbidOverrides contract, but exact provider placement is not supported by this compatibility path.",
                    source,
                )
            )
        elif identifier == "jailbreak" and character.get("post_history_instructions") and not forbid_overrides:
            content = str(character["post_history_instructions"]).replace(
                "{{original}}", str(raw_entry.get("content", ""))
            )
            warnings.append(
                WarningItem(
                    "card_prompt_override_approximation",
                    "The card post-history override follows the preset identifier/forbidOverrides contract, but exact provider placement is not supported by this compatibility path.",
                    source,
                )
            )
        else:
            content = str(raw_entry.get("content", ""))
        if not marker_rendered:
            content = render_text(content, context, renderer, warnings, source)
        if content:
            add_chunk(target, role, content, assembly_budget, source, merge=False)
            trace.append(
                {
                    "source": source,
                    "status": "relative-pre" if target is pre else "relative-post",
                    "role": role,
                    "entryIndex": index,
                }
            )
        else:
            trace.append({"source": source, "status": "empty", "entryIndex": index})

    if not inserted_history:
        warnings.append(
            WarningItem(
                "missing_chat_history_marker",
                "No active chatHistory marker exists; v2 appends history after all relative preset entries.",
                "preset",
            )
        )
    dynamic_marker_content = {
        "worldInfoBefore": bool(buckets["lorebookBefore"]),
        "personaDescription": bool(persona.get("description")),
        "charDescription": bool(character.get("description")),
        "charPersonality": bool(character.get("personality")),
        "scenario": bool(character.get("scenario")),
        "worldInfoAfter": bool(buckets["lorebookAfter"]),
        "dialogueExamples": bool(
            character.get("mes_example", character.get("messageExample", ""))
            or buckets["topOfExampleMessages"]
            or buckets["bottomOfExampleMessages"]
        ),
    }
    for marker, has_content in dynamic_marker_content.items():
        if has_content and marker not in active_identifiers:
            warnings.append(
                WarningItem(
                    "missing_preset_marker",
                    f"Dynamic content was omitted because preset marker {marker} is inactive or missing.",
                    f"marker:{marker}",
                )
            )

    rendered_history: list[dict[str, str]] = []
    for index, item in enumerate(history):
        source = f"history:{index}"
        if selected_greeting is not None and index == 0:
            content = item["content"]
        else:
            content = render_text(
                item["content"],
                context,
                renderer,
                warnings,
                source,
                allow_ejs=False,
            )
        assembly_budget.add(content, source)
        rendered_history.append({"role": item["role"], "content": content})
    rendered_input = render_text(
        user_input,
        context,
        renderer,
        warnings,
        "userInput",
        allow_ejs=False,
    )
    assembly_budget.add(rendered_input, "userInput")
    persistent_conversation = [
        *rendered_history,
        {"role": "user", "content": rendered_input},
    ]
    visible_conversation, regex_display_trace = apply_regex_messages(
        persistent_conversation,
        rendered_regex_groups,
        surface="display",
    )
    provider_conversation, regex_send_trace = apply_regex_messages(
        persistent_conversation,
        rendered_regex_groups,
        surface="send",
    )
    visible_history = visible_conversation[:-1]
    visible_input = visible_conversation[-1]["content"]
    conversation = provider_conversation
    rendered_absolute: list[AbsoluteInjection] = []
    for item in absolute:
        content = item.content
        if not item.merge_into_anchor:
            assembly_budget.add(content, item.source)
        rendered_absolute.append(
            AbsoluteInjection(
                item.source,
                item.identifier,
                content,
                item.role,
                item.depth,
                item.merge_into_anchor,
            )
        )
    conversation, applied_absolute, omitted_absolute = apply_absolute(
        conversation, rendered_absolute, warnings
    )
    logical_messages = [*pre, *conversation, *post]
    if preset_input == "tavo-native-basicPrompts-entries":
        messages, adapter_trace = apply_tavo_openai_role_adapter(logical_messages)
        adapter_policy = (
            "Tavo 1.0 OpenAI-compatible policy: keep the first leading system chunk, "
            "coerce later system chunks to user, then merge adjacent equal roles with two newlines"
        )
    else:
        messages = merge_adjacent(logical_messages)
        adapter_trace = [
            {
                "logicalIndex": index,
                "sourceRole": item["role"],
                "adapterRole": item["role"],
                "coerced": False,
            }
            for index, item in enumerate(logical_messages)
        ]
        adapter_policy = "Tavo 0.93 exported-preset compatibility role mapping, then adjacent-role merge"

    model_config = case.get("model", {})
    if isinstance(model_config, str):
        model_config = {"id": model_config}
    if not isinstance(model_config, dict):
        raise LabError("invalid_model", "case.model must be a string or object")
    model = model_override or model_config.get("id") or os.environ.get(DEFAULT_MODEL_ENV) or "tavo-prompt-lab-model"
    if not isinstance(model, str) or not model:
        raise LabError("invalid_model", "model id must be a non-empty string")
    parameters = model_config.get("parameters", case.get("parameters", {}))
    if not isinstance(parameters, dict):
        raise LabError("invalid_model", "model.parameters must be an object")
    collisions = RESERVED_PARAMETERS.intersection(parameters)
    if collisions:
        raise LabError("reserved_parameter", "model.parameters cannot override: " + ", ".join(sorted(collisions)))
    sensitive_paths = find_sensitive_parameter_paths(parameters)
    if sensitive_paths:
        raise LabError(
            "sensitive_parameter",
            "credentials and headers cannot be stored in model.parameters: "
            + ", ".join(sorted(sensitive_paths)),
        )
    request = {"model": model, "messages": messages, "stream": False, **parameters}
    request_size = len(strict_json_dumps(request, ensure_ascii=False).encode("utf-8"))
    if request_size > MAX_REQUEST_BYTES:
        raise LabError("request_too_large", f"compiled request exceeds {MAX_REQUEST_BYTES} bytes")

    for item in applied_absolute:
        trace.append(
            {
                "source": item.source,
                "status": "absolute-applied",
                "role": item.role,
                "depth": item.depth,
            }
        )
    for item in omitted_absolute:
        trace.append(
            {
                "source": item.source,
                "status": "absolute-omitted",
                "role": item.role,
                "depth": item.depth,
            }
        )
    if selected_greeting is not None:
        source_content = selected_greeting.pop("content")
        selected_greeting["sourceContent"] = source_content
        selected_greeting["renderedContent"] = rendered_history[0]["content"]
    unique_warnings: list[dict[str, str]] = []
    seen_warnings: set[tuple[str, str, str | None]] = set()
    for warning in warnings:
        key = (warning.code, warning.message, warning.source)
        if key not in seen_warnings:
            seen_warnings.add(key)
            unique_warnings.append(warning.as_dict())
    ejs_report = renderer.report()
    return {
        "format": FORMAT,
        "mode": "compile",
        "compatibility": {
            "target": "Tavo-shaped v2 text simulation",
            "ejs": "sandboxed prompt-only subset; EJS first, macros second",
            "ejsFieldOrder": "persona and core card fields, selected greeting, worldbook scan/content, regex group/entry fields, then active preset order",
            "dynamicTimeMacros": "one local-process clock snapshot; macroValues may override formatting",
            "statefulWorldbookTiming": "current-trigger approximation",
            "scanPolicy": "current input counts as one slot plus up to scanDepth-1 previous visible messages; depth 0 keeps the current-input approximation",
            "absoluteOverflow": "omit with warning",
            "absoluteTieBreak": "source order",
            "adapterRolePolicy": adapter_policy,
            "adjacentRoleMessages": "merged with two newlines after adapter role mapping",
            "nativeLorebookMarkerTrailingNewline": (
                "preserved before adjacent-role merging for Tavo 1.0 native presets"
                if preset_input == "tavo-native-basicPrompts-entries"
                else "not applied to the exported-preset compatibility mode"
            ),
            "multiTurn": "session mode carries persistent user/assistant history and chat/global EJS state between turns",
            "regex": "Tavo 1.0 supported send/receive/display/lorebook/order/depth subset; persistent, visible, and provider surfaces remain separate",
            "regexDepth": "inclusive; depth 0 is the latest outgoing user message and increments backward by persisted chat message",
            "regexUnsupported": "reasoning placement, non-empty trimStrings, escaped substitution, and lorebook depth fail closed",
            "advancedFrontend": "out-of-scope",
            "presetInput": preset_input,
        },
        "persistentHistory": rendered_history,
        "visibleHistory": visible_history,
        "renderedUserInput": rendered_input,
        "persistentUserInput": rendered_input,
        "visibleUserInput": visible_input,
        "selectedGreeting": selected_greeting,
        "triggeredWorldbooks": triggered,
        "worldbookDecisions": decisions,
        "assemblyTrace": trace,
        "adapterTrace": adapter_trace,
        "ejs": ejs_report,
        "regex": {
            "enabled": bool(rendered_regex_groups),
            "groupCount": len(rendered_regex_groups),
            "entryCount": sum(len(group["entries"]) for group in rendered_regex_groups),
            "depthPolicy": "inclusive newest-first message depth: latest outgoing user=0",
            "groupOrder": "case.regexes order",
            "groups": rendered_regex_groups,
            "sendTrace": regex_send_trace,
            "displayTrace": regex_display_trace,
            "lorebookSendTrace": regex_lorebook_trace,
            "receiveTrace": [],
            "responseDisplayTrace": [],
        },
        "request": request,
        "warnings": unique_warnings,
    }


def normalize_turns(case: dict[str, Any]) -> list[dict[str, Any]] | None:
    if "turns" not in case:
        return None
    if "userInput" in case or "input" in case:
        raise LabError(
            "conflicting_input_modes",
            "case.turns cannot be combined with top-level userInput/input",
        )
    value = case["turns"]
    if not isinstance(value, list) or not value:
        raise LabError("invalid_turns", "case.turns must be a non-empty array")
    if len(value) > MAX_SESSION_TURNS:
        raise LabError(
            "too_many_turns", f"case.turns exceeds {MAX_SESSION_TURNS} turns"
        )
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise LabError("invalid_turn", f"case.turns[{index}] must be an object")
        user_input = item.get("userInput", item.get("input"))
        if not isinstance(user_input, str) or not user_input:
            raise LabError(
                "invalid_turn", f"case.turns[{index}].userInput must be a non-empty string"
            )
        label = item.get("label")
        if label is not None and (not isinstance(label, str) or not label):
            raise LabError(
                "invalid_turn", f"case.turns[{index}].label must be a non-empty string"
            )
        assistant_response = item.get("assistantResponse", _MISSING)
        if assistant_response is not _MISSING and not isinstance(assistant_response, str):
            raise LabError(
                "invalid_turn",
                f"case.turns[{index}].assistantResponse must be a string when supplied",
            )
        normalized.append(
            {
                "label": label,
                "userInput": user_input,
                "assistantResponse": assistant_response,
            }
        )
    return normalized


def session_budget_limit(case: dict[str, Any]) -> int:
    value = case.get("sessionBudgetBytes", MAX_SESSION_BUDGET_BYTES)
    if isinstance(value, bool) or not isinstance(value, int):
        raise LabError("invalid_session_budget", "case.sessionBudgetBytes must be an integer")
    if value < 1024 or value > MAX_SESSION_BUDGET_BYTES:
        raise LabError(
            "invalid_session_budget",
            f"case.sessionBudgetBytes must be from 1024 through {MAX_SESSION_BUDGET_BYTES}",
        )
    return value


def ensure_session_budget(used: int, additional: int, limit: int, source: str) -> None:
    if additional < 0 or used + additional > limit:
        raise LabError(
            "session_budget_exceeded",
            f"session byte budget {limit} would be exceeded at {source}",
        )


def case_for_session_turn(
    case: dict[str, Any],
    turn: dict[str, Any],
    *,
    turn_index: int,
    history: list[dict[str, str]],
    ejs_state: dict[str, Any] | None,
) -> dict[str, Any]:
    turn_case = copy.deepcopy(case)
    turn_case.pop("turns", None)
    turn_case.pop("input", None)
    turn_case["userInput"] = turn["userInput"]
    turn_case["history"] = copy.deepcopy(history)
    if turn_index > 1:
        turn_case["greeting"] = False
    if ejs_state is not None:
        config = turn_case.get("ejs")
        if config is None or config is True:
            config = {}
        elif config is False:
            config = {"mode": "off"}
        elif not isinstance(config, dict):
            raise LabError("invalid_ejs_config", "case.ejs must be a boolean or object")
        else:
            config = copy.deepcopy(config)
        config["variables"] = json_clone(ejs_state, "session EJS state")
        turn_case["ejs"] = config
    return turn_case


def session_turn_record(
    compiled: dict[str, Any],
    turn: dict[str, Any],
    *,
    turn_index: int,
    assistant_source: str,
    assistant_response: str | None,
) -> dict[str, Any]:
    record = copy.deepcopy(compiled)
    record["mode"] = "compile-turn"
    return {
        "turnIndex": turn_index,
        "label": turn.get("label"),
        "userInput": turn["userInput"],
        "assistantSource": assistant_source,
        "assistantResponse": assistant_response,
        **record,
    }


def next_session_history(
    compiled: dict[str, Any], assistant_response: str | None
) -> list[dict[str, str]]:
    history = [
        *copy.deepcopy(compiled.get("persistentHistory", compiled["visibleHistory"])),
        {
            "role": "user",
            "content": compiled.get("persistentUserInput", compiled["renderedUserInput"]),
        },
    ]
    if assistant_response is not None:
        history.append({"role": "assistant", "content": assistant_response})
    if len(history) > MAX_HISTORY_MESSAGES:
        raise LabError(
            "too_many_history_messages",
            f"session history exceeds {MAX_HISTORY_MESSAGES} messages",
        )
    return history


def aggregate_session_warnings(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for turn in turns:
        for warning in turn.get("warnings", []):
            warnings.append({"turnIndex": turn["turnIndex"], **warning})
    return warnings


def compile_session(
    case: dict[str, Any], base_dir: Path, *, model_override: str | None = None
) -> dict[str, Any]:
    turns = normalize_turns(case)
    if turns is None:
        raise LabError("missing_turns", "multi-turn compile requires case.turns")
    for index, turn in enumerate(turns[:-1]):
        response = turn["assistantResponse"]
        if response is _MISSING or not response:
            raise LabError(
                "missing_assistant_response",
                f"compile needs case.turns[{index}].assistantResponse to build the next request",
            )

    history: list[dict[str, str]] = copy.deepcopy(case.get("history", []))
    ejs_state: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    budget_limit = session_budget_limit(case)
    budget_used = 0
    for turn_index, turn in enumerate(turns, start=1):
        turn_case = case_for_session_turn(
            case,
            turn,
            turn_index=turn_index,
            history=history,
            ejs_state=ejs_state,
        )
        compiled = compile_case(turn_case, base_dir, model_override=model_override)
        request_bytes = json_size(compiled["request"])
        ensure_session_budget(
            budget_used, request_bytes, budget_limit, f"compile turn {turn_index} request"
        )
        budget_used += request_bytes
        response_value = turn["assistantResponse"]
        assistant_response = None if response_value is _MISSING else response_value
        persistent_response = assistant_response
        visible_response = assistant_response
        if assistant_response is not None:
            persistent_response, visible_response, receive_trace, response_display_trace = (
                regex_response_surfaces(compiled, assistant_response)
            )
            compiled["regex"]["receiveTrace"] = receive_trace
            compiled["regex"]["responseDisplayTrace"] = response_display_trace
        record = session_turn_record(
            compiled,
            turn,
            turn_index=turn_index,
            assistant_source="provided" if assistant_response is not None else "not-provided",
            assistant_response=assistant_response,
        )
        record["persistentAssistantResponse"] = persistent_response
        record["visibleAssistantResponse"] = visible_response
        records.append(record)
        ejs_state = copy.deepcopy(compiled["ejs"]["variables"]["final"])
        history = next_session_history(compiled, persistent_response)

    return {
        "format": FORMAT,
        "mode": "compile-session",
        "status": "compiled",
        "session": {
            "turnCount": len(records),
            "assistantPolicy": "provided assistantResponse is carried into the next request; all non-final turns require it",
            "historyPolicy": "persistent ordered history plus each persistent user message and receive-transformed supplied assistant response",
            "statePolicy": "chat/global EJS variables are carried turn-to-turn in memory only",
            "retryPolicy": "no automatic retries",
            "budget": {
                "limitBytes": budget_limit,
                "usedBytes": budget_used,
                "remainingBytes": budget_limit - budget_used,
            },
        },
        "turns": records,
        "finalHistory": history,
        "finalEjsVariables": ejs_state,
        "warnings": aggregate_session_warnings(records),
    }


def resolved_case_fingerprint(case: dict[str, Any], base_dir: Path) -> str:
    """Hash stable assets/config while excluding per-turn history, input, and state."""

    value = copy.deepcopy(case)
    for key in ("userInput", "input", "turns", "history"):
        value.pop(key, None)
    ejs = value.get("ejs")
    if isinstance(ejs, dict):
        ejs.pop("variables", None)

    def resolve_asset(source: Any) -> Any:
        if not isinstance(source, str):
            return source
        path = Path(source).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        return bounded_json(path.absolute())

    for key in ("preset", "character", "persona"):
        if key in value:
            value[key] = resolve_asset(value[key])
    for key in ("worldbooks", "regexes"):
        if isinstance(value.get(key), list):
            value[key] = [resolve_asset(item) for item in value[key]]
    encoded = strict_json_dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_state_credentials(value: Any) -> None:
    found = find_sensitive_parameter_paths(value, "state")
    if found:
        raise LabError(
            "state_contains_sensitive_field",
            "Prompt Lab state cannot contain credential-like fields: "
            + ", ".join(sorted(found)),
        )


def load_turn_state(path: Path, case_fingerprint: str) -> dict[str, Any]:
    state = require_dict(bounded_json(path, require_private=True), "state")
    validate_state_credentials(state)
    if state.get("format") != STATE_FORMAT or state.get("schemaVersion") != CASE_SCHEMA_VERSION:
        raise LabError(
            "invalid_state_schema",
            f"state must use format {STATE_FORMAT} and schemaVersion {CASE_SCHEMA_VERSION}",
        )
    if state.get("caseFingerprint") != case_fingerprint:
        raise LabError(
            "state_case_mismatch",
            "state was created for different Prompt Lab assets or stable configuration",
        )
    turn_index = state.get("turnIndex")
    if isinstance(turn_index, bool) or not isinstance(turn_index, int) or turn_index < 0:
        raise LabError("invalid_state", "state.turnIndex must be an integer >= 0")
    history = normalize_history(state.get("history"))
    variables = state.get("ejsVariables", {"chat": {}, "global": {}})
    if (
        not isinstance(variables, dict)
        or not isinstance(variables.get("chat"), dict)
        or not isinstance(variables.get("global"), dict)
    ):
        raise LabError("invalid_state", "state.ejsVariables must contain chat/global objects")
    variables = json_clone(variables, "state.ejsVariables")
    budget = state.get("budget")
    if not isinstance(budget, dict):
        raise LabError("invalid_state", "state.budget must be an object")
    limit = budget.get("limitBytes")
    used = budget.get("usedBytes")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1024 <= limit <= MAX_SESSION_BUDGET_BYTES
        or isinstance(used, bool)
        or not isinstance(used, int)
        or not 0 <= used <= limit
    ):
        raise LabError("invalid_state", "state budget values are invalid")
    normalized = {
        "format": STATE_FORMAT,
        "schemaVersion": CASE_SCHEMA_VERSION,
        "caseFingerprint": case_fingerprint,
        "turnIndex": turn_index,
        "history": history,
        "ejsVariables": variables,
        "budget": {"limitBytes": limit, "usedBytes": used},
    }
    return normalized


def make_turn_state(
    *,
    case_fingerprint: str,
    turn_index: int,
    history: list[dict[str, str]],
    ejs_variables: dict[str, Any],
    budget_limit: int,
    budget_used: int,
) -> dict[str, Any]:
    state = {
        "format": STATE_FORMAT,
        "schemaVersion": CASE_SCHEMA_VERSION,
        "caseFingerprint": case_fingerprint,
        "turnIndex": turn_index,
        "history": copy.deepcopy(history),
        "ejsVariables": json_clone(ejs_variables, "state EJS variables"),
        "budget": {
            "limitBytes": budget_limit,
            "usedBytes": budget_used,
            "remainingBytes": budget_limit - budget_used,
        },
    }
    validate_state_credentials(state["ejsVariables"])
    return state


def endpoint_url(base_url: str, allow_insecure_http: bool) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in base_url):
        raise LabError("invalid_base_url", "base URL cannot contain control characters")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LabError("invalid_base_url", "base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LabError("invalid_base_url", "base URL cannot contain credentials, query, or fragment")
    hostname = (parsed.hostname or "").lower()
    loopback = hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and not loopback and not allow_insecure_http:
        raise LabError("insecure_base_url", "plain HTTP is limited to loopback; pass --allow-insecure-http explicitly")
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        endpoint_path = path
    elif path.endswith("/v1"):
        endpoint_path = path + "/chat/completions"
    else:
        endpoint_path = path + "/v1/chat/completions"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, endpoint_path, "", ""))


def validate_api_key(value: str, source: str) -> str:
    if not value or len(value) > 8192:
        raise LabError("invalid_api_key", f"{source} must contain a bounded non-empty value")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise LabError("invalid_api_key", f"{source} cannot contain control characters")
    return value


def read_secret_file(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP or path.is_symlink():
            raise LabError("insecure_key_file", "API key file cannot be a symlink") from error
        raise
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise LabError("insecure_key_file", "API key file must be regular and mode 0600")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            raw = handle.read(8194)
        if len(raw) > 8193:
            raise LabError("invalid_key_file", "API key file must contain one bounded line")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise LabError("invalid_key_file", "API key file must be UTF-8 text") from error
        if text.endswith("\n"):
            text = text[:-1]
            if text.endswith("\r"):
                text = text[:-1]
        try:
            return validate_api_key(text, "API key file")
        except LabError as error:
            raise LabError("invalid_key_file", str(error)) from error
    finally:
        if fd >= 0:
            os.close(fd)


def redact_provider_value(value: Any, api_key: str | None) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if api_key:
                key_text = key_text.replace(api_key, "<redacted-key>")
            key_text = re.sub(r"(?i)bearer\s+\S+", "Bearer <redacted>", key_text)
            normalized = normalized_security_key(key_text)
            if normalized in NORMALIZED_SENSITIVE_PARAMETER_KEYS:
                result[key_text] = "<redacted>"
            else:
                result[key_text] = redact_provider_value(item, api_key)
        return result
    if isinstance(value, list):
        return [redact_provider_value(item, api_key) for item in value]
    if isinstance(value, str):
        redacted = value.replace(api_key, "<redacted>") if api_key else value
        return re.sub(r"(?i)bearer\s+\S+", "Bearer <redacted>", redacted)
    return value


def redact_provider_text(value: str, api_key: str | None) -> str:
    redacted = value.replace(api_key, "<redacted>") if api_key else value
    return re.sub(r"(?i)bearer\s+\S+", "Bearer <redacted>", redacted)


def provider_preview(raw: bytes, api_key: str | None) -> str:
    """Return a bounded structural preview without exposing arbitrary text."""

    decoded = raw.decode("utf-8", errors="replace")
    try:
        parsed = strict_json_loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return "<non-JSON response body omitted>"
    if not isinstance(parsed, (dict, list)):
        return "<JSON scalar response body omitted>"
    redacted = redact_provider_value(parsed, api_key)
    return strict_json_dumps(
        redacted, ensure_ascii=False, separators=(",", ":")
    )[:2048]


def provider_diagnostic(
    *, status: int, content_type: str, raw: bytes, api_key: str | None
) -> dict[str, Any]:
    return {
        "httpStatus": status,
        "contentType": content_type or "unknown",
        "responseBytes": len(raw),
        "responseSha256": hashlib.sha256(raw).hexdigest(),
        "preview": provider_preview(raw, api_key),
    }


def looks_like_html(value: str, content_type: str) -> bool:
    lowered_type = content_type.lower()
    stripped = value.lstrip().lower()
    return "text/html" in lowered_type or stripped.startswith(("<!doctype html", "<html", "<head", "<body"))


def tool_call_present(body: dict[str, Any]) -> bool:
    choices = body.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict) and (
                isinstance(message.get("tool_calls"), list) and bool(message["tool_calls"])
                or isinstance(message.get("function_call"), dict)
            ):
                return True
            if choice.get("finish_reason") in {"tool_calls", "function_call"}:
                return True
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {
                "function_call",
                "custom_tool_call",
                "tool_call",
                "mcp_call",
                "computer_call",
            }:
                return True
            content = item.get("content")
            if isinstance(content, list) and any(
                isinstance(block, dict)
                and block.get("type") in {"tool_use", "server_tool_use", "tool_call"}
                for block in content
            ):
                return True
    content = body.get("content")
    if isinstance(content, list) and any(
        isinstance(block, dict)
        and block.get("type") in {"tool_use", "server_tool_use", "tool_call"}
        for block in content
    ):
        return True
    return body.get("stop_reason") == "tool_use"


def content_text(value: Any) -> tuple[str | None, bool]:
    """Extract explicit text blocks and report whether a text field was seen."""

    if isinstance(value, str):
        return (value if value.strip() else None), True
    if not isinstance(value, list):
        return None, False
    pieces: list[str] = []
    seen = False
    for block in value:
        if isinstance(block, str):
            seen = True
            if block.strip():
                pieces.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        for key in ("text", "output_text"):
            candidate = block.get(key)
            if isinstance(candidate, str):
                seen = True
                if candidate.strip():
                    pieces.append(candidate)
                break
            if isinstance(candidate, dict) and isinstance(candidate.get("value"), str):
                seen = True
                if candidate["value"].strip():
                    pieces.append(candidate["value"])
                break
        else:
            if block_type in {"text", "output_text"} and "content" in block:
                candidate = block.get("content")
                if isinstance(candidate, str):
                    seen = True
                    if candidate.strip():
                        pieces.append(candidate)
    return ("".join(pieces) if pieces else None), seen


def extract_json_response_text(body: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    """Return text, extraction source, and whether an explicit text field existed."""

    seen = False
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict) and "content" in message:
                text, item_seen = content_text(message.get("content"))
                seen = seen or item_seen
                if text is not None:
                    return text, "choices[0].message.content", True
            if "text" in choice:
                text, item_seen = content_text(choice.get("text"))
                seen = seen or item_seen
                if text is not None:
                    return text, "choices[0].text", True

    if "output_text" in body:
        text, item_seen = content_text(body.get("output_text"))
        seen = seen or item_seen
        if text is not None:
            return text, "output_text", True

    output = body.get("output")
    if isinstance(output, list):
        pieces: list[str] = []
        for index, item in enumerate(output):
            if not isinstance(item, dict) or "content" not in item:
                continue
            text, item_seen = content_text(item.get("content"))
            seen = seen or item_seen
            if text is not None:
                pieces.append(text)
        if pieces:
            return "".join(pieces), "output[].content", True

    if "content" in body:
        text, item_seen = content_text(body.get("content"))
        seen = seen or item_seen
        if text is not None:
            return text, "content[]", True
    return None, None, seen


def extract_sse_response_text(raw_text: str) -> tuple[str | None, int, bool, bool]:
    pieces: list[str] = []
    event_count = 0
    text_field_seen = False
    error_event_seen = False
    event_name = ""
    for line in raw_text.splitlines():
        if not line.strip():
            event_name = ""
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip().lower()
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].lstrip()
        if not payload or payload == "[DONE]":
            continue
        event_count += 1
        if event_name == "error":
            error_event_seen = True
            continue
        try:
            event = strict_json_loads(payload)
        except (json.JSONDecodeError, ValueError):
            stripped = payload.strip()
            if (
                stripped
                and not stripped.startswith(("{", "["))
                and not looks_like_html(stripped, "text/event-stream")
            ):
                pieces.append(payload)
                text_field_seen = True
            continue
        if isinstance(event, str):
            text_field_seen = True
            if event.strip():
                pieces.append(event)
            continue
        if not isinstance(event, dict):
            continue
        if (
            event.get("error") not in (None, {}, [])
            or event.get("type") in {"error", "response.error"}
        ):
            error_event_seen = True
            continue
        event_pieces: list[str] = []
        choices = event.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if isinstance(delta, dict) and "content" in delta:
                    text, seen = content_text(delta.get("content"))
                    text_field_seen = text_field_seen or seen
                    if text is not None:
                        event_pieces.append(text)
                if "text" in choice:
                    text, seen = content_text(choice.get("text"))
                    text_field_seen = text_field_seen or seen
                    if text is not None:
                        event_pieces.append(text)
        if isinstance(event.get("delta"), str):
            text_field_seen = True
            if event["delta"].strip():
                event_pieces.append(event["delta"])
        elif isinstance(event.get("delta"), dict) and isinstance(event["delta"].get("text"), str):
            text_field_seen = True
            if event["delta"]["text"].strip():
                event_pieces.append(event["delta"]["text"])
        text, _source, seen = extract_json_response_text(event)
        text_field_seen = text_field_seen or seen
        if text is not None and not event_pieces:
            event_pieces.append(text)
        pieces.extend(event_pieces)
    return (
        "".join(pieces) if pieces else None,
        event_count,
        text_field_seen,
        error_event_seen,
    )


JSON_STRING_SOURCE = r'("(?:\\.|[^"\\])*")'
MALFORMED_CHAT_CONTENT_RE = re.compile(
    r'^\s*\{\s*"choices"\s*:\s*\[\s*\{\s*"message"\s*:\s*\{\s*'
    r'"content"\s*:\s*' + JSON_STRING_SOURCE
)
MALFORMED_TOP_LEVEL_OUTPUT_TEXT_RE = re.compile(
    r'^\s*\{\s*"output_text"\s*:\s*' + JSON_STRING_SOURCE
)


def extract_malformed_json_text(raw_text: str) -> str | None:
    """Recover only structurally anchored model-text fields from malformed JSON."""

    if re.search(r'"error"\s*:', raw_text, re.IGNORECASE):
        return None
    for pattern in (MALFORMED_CHAT_CONTENT_RE, MALFORMED_TOP_LEVEL_OUTPUT_TEXT_RE):
        match = pattern.search(raw_text)
        if match is None:
            continue
        try:
            candidate = strict_json_loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def call_model(
    request_body: dict[str, Any],
    *,
    base_url: str,
    api_key: str | None,
    timeout: float,
    allow_insecure_http: bool,
    response_byte_limit: int = MAX_RESPONSE_BYTES,
) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    url = endpoint_url(base_url, allow_insecure_http)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream, text/plain",
    }
    if api_key:
        api_key = validate_api_key(api_key, "API key")
        headers["Authorization"] = f"Bearer {api_key}"
    payload = strict_json_dumps(request_body, ensure_ascii=False).encode("utf-8")
    if response_byte_limit <= 0:
        raise LabError("session_budget_exceeded", "no session budget remains for a provider response")
    response_byte_limit = min(response_byte_limit, MAX_RESPONSE_BYTES)
    try:
        opener = urllib.request.build_opener(NoRedirectHandler())
        with opener.open(
            urllib.request.Request(url, data=payload, headers=headers, method="POST"),
            timeout=timeout,
        ) as response:
            raw = response.read(response_byte_limit + 1)
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        status = error.code
        content_type = error.headers.get("Content-Type", "") if error.headers else ""
        try:
            raw = error.read(8192)
        except OSError:
            raw = b""
        finally:
            error.close()
        raise ProviderResponseError(
            "provider_http_error",
            f"provider returned HTTP {status}",
            provider_diagnostic(
                status=status,
                content_type=content_type,
                raw=raw,
                api_key=api_key,
            ),
        ) from error
    except urllib.error.URLError as error:
        raise LabError("provider_connection_error", f"provider request failed: {error.reason}") from error
    except ValueError as error:
        raise LabError("provider_request_error", "provider request could not be constructed") from error
    if len(raw) > response_byte_limit:
        code = (
            "session_budget_exceeded"
            if response_byte_limit < MAX_RESPONSE_BYTES
            else "provider_response_too_large"
        )
        raise ProviderResponseError(
            code,
            f"provider response exceeds the remaining {response_byte_limit}-byte limit",
            provider_diagnostic(
                status=status,
                content_type=content_type,
                raw=raw[:response_byte_limit],
                api_key=api_key,
            ),
        )
    diagnostic = provider_diagnostic(
        status=status, content_type=content_type, raw=raw, api_key=api_key
    )
    try:
        raw_text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProviderResponseError(
            "invalid_provider_response",
            "provider response is not valid UTF-8 text",
            diagnostic,
        ) from error
    if not raw_text.strip():
        raise ProviderResponseError(
            "empty_provider_response",
            "provider returned HTTP success with an empty response body",
            diagnostic,
        )
    if looks_like_html(raw_text, content_type):
        raise ProviderResponseError(
            "provider_error_document",
            "provider returned an HTML document instead of model output",
            diagnostic,
        )

    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "text/event-stream" or raw_text.lstrip().startswith("data:"):
        content, event_count, text_seen, error_event_seen = extract_sse_response_text(raw_text)
        if error_event_seen:
            raise ProviderResponseError(
                "provider_error_body",
                "provider SSE stream contained an error event",
                {**diagnostic, "eventCount": event_count},
            )
        if content is None:
            code = "empty_provider_response" if text_seen else "unsupported_provider_response_shape"
            raise ProviderResponseError(
                code,
                "provider SSE response contained no non-empty model text",
                {**diagnostic, "eventCount": event_count},
            )
        content = redact_provider_text(content, api_key)
        return (
            {
                "nonstandardResponse": {
                    "kind": "sse",
                    "eventCount": event_count,
                    "responseSha256": diagnostic["responseSha256"],
                }
            },
            content,
            f"HTTP {status}",
            {
                "source": "sse.data",
                "contentType": media_type or "text/event-stream",
                "responseBytes": len(raw),
                "warnings": [],
            },
        )

    try:
        body = strict_json_loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        if media_type == "text/plain":
            content = raw_text.strip()
            if not content:
                raise ProviderResponseError(
                    "empty_provider_response",
                    "provider returned an empty text/plain response",
                    diagnostic,
                )
            content = redact_provider_text(content, api_key)
            return (
                {"nonstandardResponse": {"kind": "text/plain"}},
                content,
                f"HTTP {status}",
                {
                    "source": "text/plain",
                    "contentType": media_type,
                    "responseBytes": len(raw),
                    "warnings": [],
                },
            )
        recovered = extract_malformed_json_text(raw_text)
        if recovered is None:
            raise ProviderResponseError(
                "unsupported_provider_response_shape",
                "provider returned malformed JSON without an unambiguous model-text field",
                diagnostic,
            )
        recovered = redact_provider_text(recovered, api_key)
        return (
            {
                "nonstandardResponse": {
                    "kind": "malformed-json-recovery",
                    "responseSha256": diagnostic["responseSha256"],
                }
            },
            recovered,
            f"HTTP {status}",
            {
                "source": "malformed-json-explicit-text-field",
                "contentType": media_type or "unknown",
                "responseBytes": len(raw),
                "warnings": [
                    {
                        "code": "nonstandard_provider_response",
                        "message": "Provider JSON was malformed; Prompt Lab recovered only complete, explicitly named model-text fields.",
                        "source": "provider.response",
                    }
                ],
            },
        )
    if not isinstance(body, dict):
        raise ProviderResponseError(
            "unsupported_provider_response_shape",
            "provider JSON response must be an object containing a supported model-text field",
            diagnostic,
        )
    if body.get("error") not in (None, {}, []):
        raise ProviderResponseError(
            "provider_error_body",
            "provider returned an error object with HTTP 200",
            diagnostic,
        )
    content, source, text_seen = extract_json_response_text(body)
    if content is None:
        if tool_call_present(body):
            code = "tool_call_only_response"
            message = "provider returned tool calls but no assistant text"
        elif text_seen:
            code = "empty_provider_response"
            message = "provider returned an explicit text field with no non-empty text"
        else:
            code = "unsupported_provider_response_shape"
            message = "provider JSON has no supported model-text field"
        raise ProviderResponseError(code, message, diagnostic)
    body = redact_provider_value(body, api_key)
    content = redact_provider_text(content, api_key)
    return (
        body,
        content,
        f"HTTP {status}",
        {
            "source": source,
            "contentType": media_type or "application/json",
            "responseBytes": len(raw),
            "warnings": [],
        },
    )


def run_one_turn(
    case: dict[str, Any],
    base_dir: Path,
    *,
    model_override: str | None,
    base_url: str,
    api_key: str | None,
    timeout: float,
    allow_insecure_http: bool,
    allow_unrendered_ejs: bool,
    state: dict[str, Any] | None,
    user_input_override: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if normalize_turns(case) is not None:
        raise LabError(
            "turns_not_allowed",
            "run-turn executes exactly one Agent-reviewed turn; remove case.turns",
        )
    fingerprint = resolved_case_fingerprint(case, base_dir)
    if state is not None and user_input_override is None:
        raise LabError(
            "missing_turn_input",
            "continued run-turn requires an explicit non-empty --user-input",
        )
    turn_index = 1 if state is None else state["turnIndex"] + 1
    budget_limit = session_budget_limit(case) if state is None else state["budget"]["limitBytes"]
    budget_used = 0 if state is None else state["budget"]["usedBytes"]
    turn_case = copy.deepcopy(case)
    if user_input_override is not None:
        if not user_input_override:
            raise LabError("invalid_input", "--user-input must be non-empty")
        turn_case["userInput"] = user_input_override
        turn_case.pop("input", None)
    if state is not None:
        turn_case["history"] = copy.deepcopy(state["history"])
        turn_case["greeting"] = False
        config = turn_case.get("ejs")
        if config is None or config is True:
            config = {}
        elif config is False:
            config = {"mode": "off"}
        elif not isinstance(config, dict):
            raise LabError("invalid_ejs_config", "case.ejs must be a boolean or object")
        else:
            config = copy.deepcopy(config)
        config["variables"] = copy.deepcopy(state["ejsVariables"])
        turn_case["ejs"] = config
    compiled = compile_case(turn_case, base_dir, model_override=model_override)
    compiled["mode"] = "run-turn"
    compiled["turnIndex"] = turn_index
    compiled["status"] = "prepared"
    compiled["stateCommitted"] = False
    provider_endpoint = endpoint_url(base_url, allow_insecure_http)
    if not allow_unrendered_ejs and compiled["ejs"]["unresolvedSources"]:
        error = LabError(
            "unrendered_ejs",
            "run-turn refuses unresolved EJS; inspect ejs.unresolvedSources or explicitly allow the deviation",
        )
        compiled["status"] = "blocked-before-provider"
        compiled["error"] = error_payload(error)
        return compiled, None
    request_bytes = json_size(compiled["request"])
    try:
        ensure_session_budget(
            budget_used, request_bytes + 1, budget_limit, f"turn {turn_index} request"
        )
        attempted_used = budget_used + request_bytes
        response, response_text, status, extraction = call_model(
            compiled["request"],
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            allow_insecure_http=allow_insecure_http,
            response_byte_limit=budget_limit - attempted_used,
        )
        attempted_used += extraction["responseBytes"]
    except LabError as error:
        attempted_used = budget_used + request_bytes
        if isinstance(error, ProviderResponseError):
            attempted_used = min(
                budget_limit,
                attempted_used + int(error.diagnostic.get("responseBytes", 0)),
            )
        compiled["status"] = "provider-failed"
        compiled["provider"] = {"endpoint": provider_endpoint, "status": "failed"}
        compiled["error"] = error_payload(error)
        compiled["budget"] = {
            "limitBytes": budget_limit,
            "committedUsedBytes": budget_used,
            "attemptedUsedBytes": attempted_used,
            "remainingCommittedBytes": budget_limit - budget_used,
        }
        return compiled, None

    compiled["status"] = "completed"
    compiled["provider"] = {"endpoint": provider_endpoint, "status": status}
    compiled["responseExtraction"] = extraction
    compiled["warnings"].extend(extraction.get("warnings", []))
    compiled["response"] = response
    compiled["responseText"] = response_text
    persistent, visible, receive_trace, display_trace = regex_response_surfaces(
        compiled, response_text
    )
    compiled["regex"]["receiveTrace"] = receive_trace
    compiled["regex"]["responseDisplayTrace"] = display_trace
    compiled["persistentResponseText"] = persistent
    compiled["visibleResponseText"] = visible
    next_history = next_session_history(compiled, persistent)
    next_state = make_turn_state(
        case_fingerprint=fingerprint,
        turn_index=turn_index,
        history=next_history,
        ejs_variables=compiled["ejs"]["variables"]["final"],
        budget_limit=budget_limit,
        budget_used=attempted_used,
    )
    compiled["stateCommitted"] = True
    compiled["nextState"] = {
        "format": STATE_FORMAT,
        "turnIndex": turn_index,
        "historyMessages": len(next_history),
        "caseFingerprint": fingerprint,
        "budget": copy.deepcopy(next_state["budget"]),
    }
    return compiled, next_state


def failed_session_result(
    records: list[dict[str, Any]],
    *,
    turn_count: int,
    failed_turn: int,
    history: list[dict[str, str]],
    ejs_state: dict[str, Any] | None,
    error: LabError,
    budget_used: int = 0,
    budget_limit: int = MAX_SESSION_BUDGET_BYTES,
) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "mode": "run-session",
        "status": "failed",
        "session": {
            "turnCount": turn_count,
            "completedTurns": sum(1 for item in records if item.get("responseText") is not None),
            "failedTurn": failed_turn,
            "assistantPolicy": "each successful provider responseText is carried into the next request",
            "historyPolicy": "persistent ordered history plus each persistent user message and receive-transformed real assistant response",
            "statePolicy": "chat/global EJS variables are carried turn-to-turn in memory only",
            "retryPolicy": "no automatic retries; inspect the failed turn before an explicit rerun",
            "budget": {
                "limitBytes": budget_limit,
                "usedBytes": budget_used,
                "remainingBytes": max(0, budget_limit - budget_used),
            },
        },
        "turns": records,
        "finalHistory": history,
        "finalEjsVariables": ejs_state,
        "warnings": aggregate_session_warnings(records),
        "error": error_payload(error),
    }


def run_session(
    case: dict[str, Any],
    base_dir: Path,
    *,
    model_override: str | None,
    base_url: str,
    api_key: str | None,
    timeout: float,
    allow_insecure_http: bool,
    allow_unrendered_ejs: bool,
) -> dict[str, Any]:
    turns = normalize_turns(case)
    if turns is None:
        raise LabError("missing_turns", "multi-turn run requires case.turns")
    for index, turn in enumerate(turns):
        if turn["assistantResponse"] is not _MISSING:
            raise LabError(
                "assistant_response_not_allowed_in_run",
                f"run calls the real provider for every turn; remove case.turns[{index}].assistantResponse",
            )

    history: list[dict[str, str]] = copy.deepcopy(case.get("history", []))
    ejs_state: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    provider_endpoint = endpoint_url(base_url, allow_insecure_http)
    budget_limit = session_budget_limit(case)
    budget_used = 0
    for turn_index, turn in enumerate(turns, start=1):
        try:
            turn_case = case_for_session_turn(
                case,
                turn,
                turn_index=turn_index,
                history=history,
                ejs_state=ejs_state,
            )
            compiled = compile_case(turn_case, base_dir, model_override=model_override)
        except LabError as error:
            records.append(
                {
                    "turnIndex": turn_index,
                    "label": turn.get("label"),
                    "userInput": turn["userInput"],
                    "mode": "run-turn",
                    "status": "compile-failed",
                    "error": {"code": error.code, "message": str(error)},
                }
            )
            return failed_session_result(
                records,
                turn_count=len(turns),
                failed_turn=turn_index,
                history=history,
                ejs_state=ejs_state,
                error=error,
                budget_used=budget_used,
                budget_limit=budget_limit,
            )

        if not allow_unrendered_ejs and compiled["ejs"]["unresolvedSources"]:
            error = LabError(
                "unrendered_ejs",
                "run refuses EJS fields that fell back or were disabled; inspect this turn's ejs.unresolvedSources or pass --allow-unrendered-ejs knowingly",
            )
            record = session_turn_record(
                compiled,
                turn,
                turn_index=turn_index,
                assistant_source="not-produced",
                assistant_response=None,
            )
            record["mode"] = "run-turn"
            record["status"] = "blocked-before-provider"
            record["error"] = error_payload(error)
            records.append(record)
            return failed_session_result(
                records,
                turn_count=len(turns),
                failed_turn=turn_index,
                history=history,
                ejs_state=ejs_state,
                error=error,
                budget_used=budget_used,
                budget_limit=budget_limit,
            )

        try:
            request_bytes = json_size(compiled["request"])
            ensure_session_budget(
                budget_used, request_bytes + 1, budget_limit, f"turn {turn_index} request"
            )
            budget_used += request_bytes
            response, response_text, status, extraction = call_model(
                compiled["request"],
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                allow_insecure_http=allow_insecure_http,
                response_byte_limit=budget_limit - budget_used,
            )
            budget_used += extraction["responseBytes"]
        except LabError as error:
            if isinstance(error, ProviderResponseError):
                budget_used = min(
                    budget_limit,
                    budget_used + int(error.diagnostic.get("responseBytes", 0)),
                )
            record = session_turn_record(
                compiled,
                turn,
                turn_index=turn_index,
                assistant_source="not-produced",
                assistant_response=None,
            )
            record["mode"] = "run-turn"
            record["status"] = "provider-failed"
            record["provider"] = {"endpoint": provider_endpoint, "status": "failed"}
            record["error"] = error_payload(error)
            records.append(record)
            return failed_session_result(
                records,
                turn_count=len(turns),
                failed_turn=turn_index,
                history=history,
                ejs_state=ejs_state,
                error=error,
                budget_used=budget_used,
                budget_limit=budget_limit,
            )

        record = session_turn_record(
            compiled,
            turn,
            turn_index=turn_index,
            assistant_source="provider",
            assistant_response=response_text,
        )
        record["mode"] = "run-turn"
        record["status"] = "completed"
        record["provider"] = {"endpoint": provider_endpoint, "status": status}
        record["responseExtraction"] = extraction
        record["warnings"].extend(extraction.get("warnings", []))
        record["response"] = response
        record["responseText"] = response_text
        persistent_response, visible_response, receive_trace, response_display_trace = (
            regex_response_surfaces(compiled, response_text)
        )
        compiled["regex"]["receiveTrace"] = receive_trace
        compiled["regex"]["responseDisplayTrace"] = response_display_trace
        record["regex"] = copy.deepcopy(compiled["regex"])
        record["persistentResponseText"] = persistent_response
        record["visibleResponseText"] = visible_response
        records.append(record)
        ejs_state = copy.deepcopy(compiled["ejs"]["variables"]["final"])
        history = next_session_history(compiled, persistent_response)

    return {
        "format": FORMAT,
        "mode": "run-session",
        "status": "completed",
        "session": {
            "turnCount": len(records),
            "completedTurns": len(records),
            "assistantPolicy": "each real provider responseText is carried into the next request",
            "historyPolicy": "persistent ordered history plus each persistent user message and receive-transformed real assistant response",
            "statePolicy": "chat/global EJS variables are carried turn-to-turn in memory only",
            "retryPolicy": "no automatic retries",
            "budget": {
                "limitBytes": budget_limit,
                "usedBytes": budget_used,
                "remainingBytes": budget_limit - budget_used,
            },
        },
        "turns": records,
        "finalHistory": history,
        "finalEjsVariables": ejs_state,
        "warnings": aggregate_session_warnings(records),
    }


def atomic_output(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(strict_json_dumps(value, ensure_ascii=False, indent=2))
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def case_input_paths(case: dict[str, Any], case_path: Path) -> list[Path]:
    paths = [case_path]
    for key in ("preset", "character", "persona"):
        value = case.get(key)
        if isinstance(value, str):
            candidate = Path(value).expanduser()
            paths.append((case_path.parent / candidate if not candidate.is_absolute() else candidate).absolute())
    worldbooks = case.get("worldbooks", [])
    if isinstance(worldbooks, list):
        for value in worldbooks:
            if isinstance(value, str):
                candidate = Path(value).expanduser()
                paths.append(
                    (case_path.parent / candidate if not candidate.is_absolute() else candidate).absolute()
                )
    regexes = case.get("regexes", [])
    if isinstance(regexes, list):
        for value in regexes:
            if isinstance(value, str):
                candidate = Path(value).expanduser()
                paths.append(
                    (case_path.parent / candidate if not candidate.is_absolute() else candidate).absolute()
                )
    return paths


def ensure_output_safe(output: str | None, protected_paths: Iterable[Path]) -> None:
    if not output:
        return
    destination = Path(output).expanduser().absolute()
    for protected in protected_paths:
        if destination == protected:
            raise LabError("output_overwrites_input", f"output cannot overwrite input: {protected}")
        try:
            if destination.exists() and protected.exists() and os.path.samefile(destination, protected):
                raise LabError("output_overwrites_input", f"output cannot alias input: {protected}")
        except OSError:
            continue


def emit(value: Any, output: str | None) -> None:
    if output:
        atomic_output(Path(output).expanduser().absolute(), value)
    else:
        print(strict_json_dumps(value, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subcommands = root.add_subparsers(dest="command", required=True)
    for name in ("compile", "run", "run-turn"):
        command = subcommands.add_parser(name)
        command.add_argument("--case", required=True, help="Prompt Lab case JSON")
        command.add_argument("--model", help="Override model id")
        command.add_argument("--output", help="Write private JSON output (mode 0600)")
        if name in {"run", "run-turn"}:
            command.add_argument("--base-url", help=f"Provider base URL (or ${DEFAULT_BASE_URL_ENV})")
            command.add_argument("--api-key-env", default=DEFAULT_KEY_ENV, help="Environment variable containing the API key")
            command.add_argument("--api-key-file", help="Mode-0600 file containing the API key")
            command.add_argument("--no-auth", action="store_true", help="Send no Authorization header")
            command.add_argument("--timeout", type=float, default=120.0)
            command.add_argument("--allow-insecure-http", action="store_true")
            command.add_argument(
                "--trust-case-base-url",
                action="store_true",
                help="Explicitly trust case.model.baseUrl as the request destination",
            )
            command.add_argument(
                "--allow-unrendered-ejs",
                action="store_true",
                help="Explicitly send unrendered EJS source instead of refusing run",
            )
        if name == "run-turn":
            command.add_argument("--state-in", help="Prior Prompt Lab state JSON (mode 0600)")
            command.add_argument("--state-out", required=True, help="New private state JSON (mode 0600)")
            command.add_argument("--user-input", help="Override case.userInput for exactly this turn")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        case_path = Path(args.case).expanduser().absolute()
        case = require_dict(bounded_json(case_path), "case")
        protected_paths = case_input_paths(case, case_path)
        if args.command in {"run", "run-turn"} and args.api_key_file:
            protected_paths.append(Path(args.api_key_file).expanduser().absolute())
        if args.command == "run-turn" and args.state_in:
            protected_paths.append(Path(args.state_in).expanduser().absolute())
        ensure_output_safe(args.output, protected_paths)
        if args.command == "run-turn":
            ensure_output_safe(args.state_out, protected_paths)
            if args.output and Path(args.output).expanduser().absolute() == Path(args.state_out).expanduser().absolute():
                raise LabError("output_overwrites_state", "--output and --state-out must be different files")
        model_config = case.get("model", {})
        if isinstance(model_config, str):
            model_config = {"id": model_config}
        if not isinstance(model_config, dict):
            raise LabError("invalid_model", "case.model must be a string or object")
        configured_model = args.model or model_config.get("id") or os.environ.get(DEFAULT_MODEL_ENV)
        if args.command in {"run", "run-turn"} and not configured_model:
            raise LabError(
                "missing_model",
                f"run requires --model, case.model.id, or ${DEFAULT_MODEL_ENV}",
            )
        session_turns = normalize_turns(case)
        if args.command == "compile":
            result = (
                compile_session(case, case_path.parent, model_override=args.model)
                if session_turns is not None
                else compile_case(case, case_path.parent, model_override=args.model)
            )
            emit(result, args.output)
            return 0

        if args.command in {"run", "run-turn"}:
            case_base_url = model_config.get("baseUrl")
            if case_base_url is not None and not isinstance(case_base_url, str):
                raise LabError("invalid_base_url", "case.model.baseUrl must be a string")
            base_url = args.base_url or os.environ.get(DEFAULT_BASE_URL_ENV)
            if not base_url and case_base_url:
                if not args.trust_case_base_url:
                    raise LabError(
                        "untrusted_case_base_url",
                        "case.model.baseUrl requires --trust-case-base-url; prefer --base-url or the base URL environment variable",
                    )
                base_url = case_base_url
            if not base_url:
                raise LabError(
                    "missing_base_url",
                    f"run requires --base-url, ${DEFAULT_BASE_URL_ENV}, or an explicitly trusted case.model.baseUrl",
                )
            if args.no_auth and args.api_key_file:
                raise LabError("conflicting_auth", "--no-auth and --api-key-file cannot be combined")
            if args.no_auth:
                api_key = None
            elif args.api_key_file:
                api_key = read_secret_file(Path(args.api_key_file).expanduser().absolute())
            else:
                if not ENV_NAME_RE.fullmatch(args.api_key_env):
                    raise LabError("invalid_env_name", "--api-key-env must be a valid environment variable name")
                api_key = os.environ.get(args.api_key_env)
                if not api_key:
                    raise LabError("missing_api_key", f"API key environment variable is empty: {args.api_key_env}")
                api_key = validate_api_key(api_key, f"environment variable {args.api_key_env}")
            if not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 600:
                raise LabError("invalid_timeout", "timeout must be > 0 and <= 600 seconds")

            if args.command == "run-turn":
                if Path(args.state_out).expanduser().absolute().exists():
                    raise LabError(
                        "state_output_exists",
                        "--state-out must be a new path so a failed turn cannot leave a stale advanced state",
                    )
                fingerprint = resolved_case_fingerprint(case, case_path.parent)
                state = (
                    load_turn_state(Path(args.state_in).expanduser().absolute(), fingerprint)
                    if args.state_in
                    else None
                )
                result, next_state = run_one_turn(
                    case,
                    case_path.parent,
                    model_override=args.model,
                    base_url=base_url,
                    api_key=api_key,
                    timeout=args.timeout,
                    allow_insecure_http=args.allow_insecure_http,
                    allow_unrendered_ejs=args.allow_unrendered_ejs,
                    state=state,
                    user_input_override=args.user_input,
                )
                if next_state is not None:
                    atomic_output(Path(args.state_out).expanduser().absolute(), next_state)
                    result["nextState"]["written"] = True
                emit(result, args.output)
                return 0 if result["status"] == "completed" else 2

            if session_turns is not None:
                result = run_session(
                    case,
                    case_path.parent,
                    model_override=args.model,
                    base_url=base_url,
                    api_key=api_key,
                    timeout=args.timeout,
                    allow_insecure_http=args.allow_insecure_http,
                    allow_unrendered_ejs=args.allow_unrendered_ejs,
                )
                emit(result, args.output)
                return 0 if result["status"] == "completed" else 2

            result = compile_case(case, case_path.parent, model_override=args.model)
            if not args.allow_unrendered_ejs and result["ejs"]["unresolvedSources"]:
                raise LabError(
                    "unrendered_ejs",
                    "run refuses EJS fields that fell back or were disabled; inspect ejs.unresolvedSources or pass --allow-unrendered-ejs knowingly",
                )
            result["mode"] = "run"
            result["status"] = "prepared"
            try:
                response, response_text, status, extraction = call_model(
                    result["request"],
                    base_url=base_url,
                    api_key=api_key,
                    timeout=args.timeout,
                    allow_insecure_http=args.allow_insecure_http,
                )
            except LabError as error:
                result["status"] = "provider-failed"
                result["provider"] = {
                    "endpoint": endpoint_url(base_url, args.allow_insecure_http),
                    "status": "failed",
                }
                result["error"] = error_payload(error)
                emit(result, args.output)
                return 2
            result["status"] = "completed"
            result["provider"] = {"endpoint": endpoint_url(base_url, args.allow_insecure_http), "status": status}
            result["responseExtraction"] = extraction
            result["warnings"].extend(extraction.get("warnings", []))
            result["response"] = response
            result["responseText"] = response_text
            persistent_response, visible_response, receive_trace, response_display_trace = (
                regex_response_surfaces(result, response_text)
            )
            result["regex"]["receiveTrace"] = receive_trace
            result["regex"]["responseDisplayTrace"] = response_display_trace
            result["persistentResponseText"] = persistent_response
            result["visibleResponseText"] = visible_response
            emit(result, args.output)
            return 0
        raise LabError("invalid_command", f"unsupported command: {args.command}")
    except (LabError, OSError) as error:
        code = error.code if isinstance(error, LabError) else "io_error"
        payload = error_payload(error) if isinstance(error, LabError) else {"code": code, "message": str(error)}
        print(strict_json_dumps({"format": FORMAT, "error": payload}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
