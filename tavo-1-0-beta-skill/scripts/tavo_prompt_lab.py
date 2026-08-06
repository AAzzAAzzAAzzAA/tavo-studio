#!/usr/bin/env python3
"""Compile Tavo text assets and optionally call an OpenAI-compatible model.

The lab is intentionally text-only.  It reproduces the prompt-assembly behavior
supported by retained Tavo evidence, including isolated prompt-field EJS before
macros, and reports known approximations instead of claiming full app equivalence.
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


FORMAT = "tavo-prompt-lab-result/v2"
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
MAX_EJS_STATE_BYTES = 4 * 1024 * 1024
MAX_EJS_TRACE_ITEMS = 10_000
MAX_EJS_FIELDS = 512
MAX_EJS_WALL_SECONDS = 30.0
DEFAULT_EJS_TIMEOUT_MS = 500
MAX_EJS_TIMEOUT_MS = 2_000
ROLES = frozenset({"system", "user", "assistant"})
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


def json_clone(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return json.loads(encoded)
    except (TypeError, ValueError) as error:
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
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
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
            return json.loads(stripped)
        except json.JSONDecodeError:
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
        return text, False

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
                message="The per-case EJS field/time budget was exhausted; the complete field fell back to its original text.",
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
                message="Sandboxed EJS requires Node.js and the bundled worker; the complete field fell back to its original text.",
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
                    input=json.dumps(request, ensure_ascii=False),
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
                message="Sandboxed EJS exceeded its wall-clock limit; the complete field fell back to its original text and state changes were rolled back.",
                kind="timeout",
            )
        except OSError as error:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message=f"Sandboxed EJS could not start ({error.__class__.__name__}); the complete field fell back to its original text.",
                kind="worker",
            )
        if completed.returncode != 0 or len(completed.stdout.encode("utf-8")) > MAX_RESPONSE_BYTES:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message="Sandboxed EJS ended without a bounded result; the complete field fell back to its original text.",
                kind="worker",
            )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_worker_failure_fallback",
                message="Sandboxed EJS returned invalid JSON; the complete field fell back to its original text.",
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
                message=f"Sandboxed EJS {kind} error; Tavo-style whole-field fallback was applied and state changes were rolled back: {detail}",
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
                message="Sandboxed EJS returned an invalid result shape; the complete field fell back to its original text.",
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
                message="Sandboxed EJS produced an invalid or excessive result; the complete field fell back and state changes were rolled back.",
                kind="limit",
            )
        if json_size(state) > MAX_EJS_STATE_BYTES:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_state_too_large_fallback",
                message="Sandboxed EJS produced excessive variable state; the complete field fell back and state changes were rolled back.",
                kind="limit",
            )
        if self.ejs_operation_count + len(operations) > MAX_EJS_TRACE_ITEMS:
            return self._fallback(
                text,
                warnings,
                source,
                code="ejs_trace_limit_fallback",
                message="Sandboxed EJS exceeded the per-case variable trace limit; the complete field fell back and state changes were rolled back.",
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


def bounded_json(path: Path) -> Any:
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
        if metadata.st_size > MAX_JSON_BYTES:
            raise LabError("input_too_large", f"JSON input exceeds {MAX_JSON_BYTES} bytes: {path}")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            raw = handle.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise LabError("input_too_large", f"JSON input exceeds {MAX_JSON_BYTES} bytes: {path}")
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
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
                    parsed = json.loads(text_blocks[0])
                except json.JSONDecodeError:
                    break
                if isinstance(parsed, dict):
                    current = parsed
                    continue
        break
    return current


def normalize_prompt_order_preset(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize the bounded Tavo-exported prompts/prompt_order subset.

    This adapter intentionally accepts only one unambiguous order and relative
    entries.  The role mapping is backed by the retained Tavo 0.93 Whisper
    provider capture: exported ``system_prompt: false`` entries become user
    prompt components even when the compatibility ``role`` field says system.
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
                f"Tavo-exported prompt {identifier} uses an unverified non-relative injection_position",
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
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def ensure_text_budget(value: str, source: str) -> None:
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise LabError("text_too_large", f"text exceeds {MAX_TEXT_BYTES} bytes: {source}")


def find_sensitive_parameter_paths(value: Any, path: str = "model.parameters") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in SENSITIVE_PARAMETER_KEYS:
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
            scan_messages = history[-scan_depth:] if scan_depth else []
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
                        "Prompt Lab v2 scans the current input plus scanDepth prior messages; Tavo has not published every counting edge case.",
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
                "basicPrompts.lorebook has no {0}; v2 appends the lorebook content after it.",
                source,
            )
        )
        return f"{wrapper}\n{content}"
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
) -> None:
    if not content:
        return
    if budget is not None:
        budget.add(content, source)
    if messages and messages[-1]["role"] == role:
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


def compile_case(case: dict[str, Any], base_dir: Path, *, model_override: str | None = None) -> dict[str, Any]:
    warnings: list[WarningItem] = []
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
                "A single-order Tavo-exported prompts + prompt_order preset was normalized with the retained 0.93 relative-role mapping; non-relative and ambiguous orders remain fail-closed.",
                "preset",
            )
        )
    character = normalize_character(resolve_json(case["character"], base_dir, "character"))
    nickname = character.get("nickname")
    if isinstance(nickname, str) and nickname.strip():
        warnings.append(
            WarningItem(
                "nickname_single_chat_not_applied",
                "Current official surfaces conflict on nickname scope; Prompt Lab v2 is single-chat and preserves character.name for {{char}} until a retained single-chat wire capture resolves it.",
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
    total_input_bytes = json_size(preset) + json_size(character) + json_size(persona)
    total_entries = len(preset["entries"])
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
            return wrap_lorebook(
                "\n\n".join(buckets[bucket]),
                wrapper,
                warnings,
                f"marker:{identifier}",
            )
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
                        "Retained 0.93 captures merge preset absolute text into the target history slot, whose provider role wins over the configured entry role.",
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
                    "The card main-prompt override follows the preset identifier/forbidOverrides contract but lacks a retained 0.93 wire oracle.",
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
                    "The card post-history override follows the preset identifier/forbidOverrides contract but lacks a retained 0.93 wire oracle.",
                    source,
                )
            )
        else:
            content = str(raw_entry.get("content", ""))
        if not marker_rendered:
            content = render_text(content, context, renderer, warnings, source)
        if content:
            add_chunk(target, role, content, assembly_budget, source)
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
    conversation = [*rendered_history, {"role": "user", "content": rendered_input}]
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
    messages = merge_adjacent([*pre, *conversation, *post])

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
    request_size = len(json.dumps(request, ensure_ascii=False).encode("utf-8"))
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
            "target": "evidence-bounded Tavo-shaped v2 simulation",
            "evidence": "retained provider captures plus current skill references",
            "ejs": "sandboxed prompt-only subset; EJS first, macros second",
            "ejsFieldOrder": "persona and core card fields, selected greeting, worldbook scan/content, then active preset order",
            "dynamicTimeMacros": "one local-process clock snapshot; macroValues may override formatting",
            "statefulWorldbookTiming": "current-trigger approximation",
            "scanPolicy": "current input plus previous scanDepth visible messages",
            "absoluteOverflow": "omit with warning",
            "absoluteTieBreak": "source order",
            "adjacentRoleMessages": "merged with two newlines",
            "advancedFrontend": "out-of-scope",
            "presetInput": preset_input,
        },
        "selectedGreeting": selected_greeting,
        "triggeredWorldbooks": triggered,
        "worldbookDecisions": decisions,
        "assemblyTrace": trace,
        "ejs": ejs_report,
        "request": request,
        "warnings": unique_warnings,
    }


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
            normalized = re.sub(r"[^a-z0-9_]", "_", key_text.lower()).strip("_")
            if normalized in SENSITIVE_PARAMETER_KEYS:
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


def call_model(
    request_body: dict[str, Any],
    *,
    base_url: str,
    api_key: str | None,
    timeout: float,
    allow_insecure_http: bool,
) -> tuple[dict[str, Any], str | None, str]:
    url = endpoint_url(base_url, allow_insecure_http)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        api_key = validate_api_key(api_key, "API key")
        headers["Authorization"] = f"Bearer {api_key}"
    payload = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    try:
        opener = urllib.request.build_opener(NoRedirectHandler())
        with opener.open(
            urllib.request.Request(url, data=payload, headers=headers, method="POST"),
            timeout=timeout,
        ) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as error:
        try:
            raw = error.read(8192)
        except OSError:
            raw = b""
        message = raw.decode("utf-8", errors="replace")
        if api_key:
            message = message.replace(api_key, "<redacted>")
        message = re.sub(r"(?i)bearer\s+\S+", "Bearer <redacted>", message)[:2048]
        raise LabError("provider_http_error", f"provider returned HTTP {error.code}: {message}") from error
    except urllib.error.URLError as error:
        raise LabError("provider_connection_error", f"provider request failed: {error.reason}") from error
    except ValueError as error:
        raise LabError("provider_request_error", "provider request could not be constructed") from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise LabError("provider_response_too_large", f"provider response exceeds {MAX_RESPONSE_BYTES} bytes")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LabError("invalid_provider_response", "provider did not return valid JSON") from error
    if not isinstance(body, dict):
        raise LabError("invalid_provider_response", "provider JSON response must be an object")
    content: str | None = None
    try:
        candidate = body["choices"][0]["message"]["content"]
        if isinstance(candidate, str):
            content = candidate
    except (KeyError, IndexError, TypeError):
        pass
    body = redact_provider_value(body, api_key)
    if content is not None:
        content = redact_provider_value(content, api_key)
    return body, content, f"HTTP {status}"


def atomic_output(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
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
        print(json.dumps(value, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subcommands = root.add_subparsers(dest="command", required=True)
    for name in ("compile", "run"):
        command = subcommands.add_parser(name)
        command.add_argument("--case", required=True, help="Prompt Lab case JSON")
        command.add_argument("--model", help="Override model id")
        command.add_argument("--output", help="Write private JSON output (mode 0600)")
        if name == "run":
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
                help="Explicitly send retained EJS source instead of refusing run",
            )
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        case_path = Path(args.case).expanduser().absolute()
        case = require_dict(bounded_json(case_path), "case")
        protected_paths = case_input_paths(case, case_path)
        if args.command == "run" and args.api_key_file:
            protected_paths.append(Path(args.api_key_file).expanduser().absolute())
        ensure_output_safe(args.output, protected_paths)
        model_config = case.get("model", {})
        if isinstance(model_config, str):
            model_config = {"id": model_config}
        if not isinstance(model_config, dict):
            raise LabError("invalid_model", "case.model must be a string or object")
        configured_model = args.model or model_config.get("id") or os.environ.get(DEFAULT_MODEL_ENV)
        if args.command == "run" and not configured_model:
            raise LabError(
                "missing_model",
                f"run requires --model, case.model.id, or ${DEFAULT_MODEL_ENV}",
            )
        result = compile_case(case, case_path.parent, model_override=args.model)
        if args.command == "run":
            if not args.allow_unrendered_ejs and result["ejs"]["unresolvedSources"]:
                raise LabError(
                    "unrendered_ejs",
                    "run refuses EJS fields that fell back or were disabled; inspect ejs.unresolvedSources or pass --allow-unrendered-ejs knowingly",
                )
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
            response, response_text, status = call_model(
                result["request"],
                base_url=base_url,
                api_key=api_key,
                timeout=args.timeout,
                allow_insecure_http=args.allow_insecure_http,
            )
            result["mode"] = "run"
            result["provider"] = {"endpoint": endpoint_url(base_url, args.allow_insecure_http), "status": status}
            result["response"] = response
            result["responseText"] = response_text
        emit(result, args.output)
        return 0
    except (LabError, OSError) as error:
        code = error.code if isinstance(error, LabError) else "io_error"
        print(json.dumps({"format": FORMAT, "error": {"code": code, "message": str(error)}}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
