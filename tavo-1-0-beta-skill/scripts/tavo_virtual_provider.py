#!/usr/bin/env python3
"""Deterministic, capture-first virtual model provider for offline Tavo tests.

This process serves only static, locally generated protocol fixtures and
contains no outbound network client. It records privacy-preserving request
projections so protocol and prompt-assembly behavior can be asserted without
a real model request.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import io
import ipaddress
import json
import math
import os
import re
import signal
import stat
import struct
import threading
import time
import urllib.parse
import uuid
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_TEXT_FIELD_BYTES = 256 * 1024
DEFAULT_OVERSIZED_RESPONSE_BYTES = 2 * 1024 * 1024
JSON_POST_PATHS = frozenset(
    {
        "/chat/completions",
        "/completions",
        "/messages",
        "/responses",
        "/v1/chat/completions",
        "/v1/completions",
        "/v1/images/generations",
        "/v1/messages",
        "/v1/responses",
        "/v1/audio/speech",
        "/images/generations",
        "/audio/speech",
    }
)
ASR_POST_PATHS = frozenset({"/audio/transcriptions", "/v1/audio/transcriptions"})
MODELS_PATHS = frozenset({"/models", "/v1/models"})
ASSET_PATH = "/fixture/assets/fixture-1x1.png"
SCENARIOS = frozenset(
    {
        "normal",
        "slow",
        "slow_stream",
        "slow_stream_before_first",
        "slow_stream_after_first",
        "http400",
        "http401",
        "http429",
        "http500",
        "malformed",
        "wrong_content_type",
        "abrupt_eof",
        "no_done",
        "timeout",
        "empty",
        "oversized",
    }
)
HTTP_ERROR_SCENARIOS = {
    "http400": 400,
    "http401": 401,
    "http429": 429,
    "http500": 500,
}
SCENARIO_PATTERN = re.compile(r"\[TAVO_FIXTURE_SCENARIO:([a-z0-9_-]+)\]")
SAFE_CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
SAFE_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.:[\]-]+$")
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(?:\b(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}\b|"
    r"\btavo-(?:cap|fixture)-[A-Za-z0-9_-]{8,}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "bearer",
        "client_secret",
        "cookie",
        "key",
        "password",
        "private_key",
        "proxy_authorization",
        "refresh_token",
        "secret",
        "token",
        "x_api_key",
    }
)
MEDIA_CONTAINER_KEYS = frozenset(
    {
        "audio",
        "b64_json",
        "file",
        "image",
        "image_url",
        "input_audio",
        "input_image",
        "url",
    }
)
MEDIA_TYPES = frozenset(
    {
        "audio",
        "image",
        "image_url",
        "input_audio",
        "input_image",
    }
)
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class RequestError(ValueError):
    """A bounded client request error with an HTTP status and stable code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def secure_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Private directory cannot be a symlink: {path}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"Private directory path is not a directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9_]", "_", key.lower()).strip("_")
    return bool(
        normalized in SENSITIVE_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
        or normalized.endswith("_credential")
    )


def redact_text(value: str) -> str:
    if re.match(r"^(?:bearer|basic)\s+", value, re.IGNORECASE):
        return value.split(" ", 1)[0] + " <redacted>"
    return SECRET_VALUE_PATTERN.sub("<redacted-secret>", value)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>" if sensitive_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def atomic_json(path: Path, value: Any) -> None:
    secure_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(redact(value), ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_secret_file(path: Path, *, delete_after_read: bool = False) -> str:
    if path.is_symlink():
        raise ValueError(f"Secret file cannot be a symlink: {path}")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"Secret path must be a regular file: {path}")
    if metadata.st_mode & 0o077:
        raise ValueError(f"Secret file must not be readable or writable by group/other: {path}")
    value = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not value or "\n" in value or "\r" in value or len(value) > 8192:
        raise ValueError(f"Secret file must contain exactly one bounded line: {path}")
    if delete_after_read:
        path.unlink()
    return value


def validate_allowed_clients(values: list[str]) -> tuple[ipaddress._BaseNetwork, ...]:
    networks: list[ipaddress._BaseNetwork] = []
    for value in values:
        try:
            if "/" in value:
                network = ipaddress.ip_network(value, strict=False)
            else:
                address = ipaddress.ip_address(value)
                network = ipaddress.ip_network(
                    f"{address}/{address.max_prefixlen}",
                    strict=False,
                )
        except ValueError as error:
            raise ValueError(f"Invalid allowed client IP or CIDR: {value}") from error
        networks.append(network)
    return tuple(networks)


def is_loopback_bind(value: str) -> bool:
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def normalized_asset_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "http" or not parsed.netloc:
        raise ValueError("--asset-base-url must be an absolute HTTP URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("--asset-base-url cannot contain credentials, a query, or a fragment")
    return urllib.parse.urlunsplit(("http", parsed.netloc, parsed.path.rstrip("/"), "", ""))


def make_wav_bytes() -> bytes:
    sample_rate = 16000
    duration_seconds = 0.20
    samples = int(sample_rate * duration_seconds)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for index in range(samples):
            amplitude = int(2400 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", amplitude))
        wav.writeframes(bytes(frames))
    return output.getvalue()


WAV_BYTES = make_wav_bytes()


def media_projection(data: bytes, *, media_type: str | None, encoding: str) -> dict[str, Any]:
    return {
        "_fixtureMedia": {
            "encoding": encoding,
            "mediaType": media_type or "application/octet-stream",
            "sizeBytes": len(data),
            "sha256": sha256_bytes(data),
        }
    }


def project_media_text(
    value: str,
    *,
    media_type: str | None,
    assume_base64: bool,
) -> dict[str, Any] | None:
    if value.startswith("data:"):
        header, separator, encoded = value.partition(",")
        if not separator:
            return media_projection(
                value.encode("utf-8"),
                media_type="text/plain",
                encoding="invalid-data-url",
            )
        metadata = header[5:]
        mime = metadata.split(";", 1)[0] or media_type
        if ";base64" in metadata.lower():
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                return media_projection(
                    value.encode("utf-8"),
                    media_type=mime,
                    encoding="invalid-base64-data-url",
                )
            return media_projection(decoded, media_type=mime, encoding="base64-data-url")
        decoded = urllib.parse.unquote_to_bytes(encoded)
        return media_projection(decoded, media_type=mime, encoding="percent-data-url")
    if assume_base64:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            return media_projection(
                value.encode("utf-8"),
                media_type=media_type,
                encoding="invalid-base64",
            )
        return media_projection(decoded, media_type=media_type, encoding="base64")
    return None


def project_capture(
    value: Any,
    *,
    key: str = "",
    parent_key: str = "",
    parent_type: str = "",
    media_type_hint: str | None = None,
) -> Any:
    if isinstance(value, dict):
        own_type = str(value.get("type", parent_type))
        own_media_type = str(
            value.get("media_type")
            or value.get("mime_type")
            or value.get("content_type")
            or media_type_hint
            or ""
        )
        output: dict[str, Any] = {}
        for child_key, item in value.items():
            string_key = str(child_key)
            if sensitive_key(string_key):
                output[string_key] = "<redacted>"
                continue
            output[string_key] = project_capture(
                item,
                key=string_key,
                parent_key=key,
                parent_type=own_type,
                media_type_hint=own_media_type or None,
            )
        return output
    if isinstance(value, list):
        return [
            project_capture(
                item,
                key=key,
                parent_key=parent_key,
                parent_type=parent_type,
                media_type_hint=media_type_hint,
            )
            for item in value
        ]
    if isinstance(value, str):
        media_context = bool(
            key in {"b64_json", "data", "url"}
            and (
                key == "b64_json"
                or parent_key in MEDIA_CONTAINER_KEYS
                or parent_type in MEDIA_TYPES
            )
        )
        projected = project_media_text(
            value,
            media_type=media_type_hint,
            assume_base64=media_context and not value.startswith(("http://", "https://")),
        )
        if projected is not None:
            return projected
        return redact_text(value)
    return value


def iter_fixture_text(value: Any, *, parent_key: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            string_key = str(key)
            if sensitive_key(string_key) or string_key in {"b64_json", "data"}:
                continue
            yield from iter_fixture_text(item, parent_key=string_key)
    elif isinstance(value, list):
        for item in value:
            yield from iter_fixture_text(item, parent_key=parent_key)
    elif isinstance(value, str) and parent_key not in MEDIA_CONTAINER_KEYS:
        yield value


def find_named_value(value: Any, names: frozenset[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in names and isinstance(item, str):
                return item
        for key, item in value.items():
            if str(key) not in {"b64_json", "data"}:
                found = find_named_value(item, names)
                if found is not None:
                    return found
    elif isinstance(value, list):
        for item in value:
            found = find_named_value(item, names)
            if found is not None:
                return found
    return None


def validated_correlation(value: str | None, label: str) -> str | None:
    if value is None or value == "":
        return None
    if not SAFE_CORRELATION_PATTERN.fullmatch(value):
        raise RequestError(400, f"fixture_invalid_{label}", f"invalid fixture {label}")
    return value


def extract_scenario(payload: Any, headers: Any) -> str:
    candidates: set[str] = set()
    header_value = headers.get("X-Tavo-Fixture-Scenario")
    if header_value:
        candidates.add(header_value)
    named = find_named_value(payload, frozenset({"fixturescenario"}))
    if named:
        candidates.add(named)
    if isinstance(payload, dict) and isinstance(payload.get("model"), str):
        model = payload["model"]
        for prefix in ("fixture-", "tavo-virtual-"):
            if model.startswith(prefix):
                suffix = model[len(prefix) :]
                if suffix in SCENARIOS:
                    candidates.add(suffix)
    for text in iter_fixture_text(payload):
        candidates.update(SCENARIO_PATTERN.findall(text))
    unknown = sorted(candidates - SCENARIOS)
    if unknown:
        raise RequestError(400, "fixture_unknown_scenario", f"unknown fixture scenario: {unknown[0]}")
    if len(candidates) > 1:
        raise RequestError(
            400,
            "fixture_scenario_conflict",
            "exactly zero or one fixture scenario is allowed",
        )
    return next(iter(candidates), "normal")


def extract_nonce(payload: Any, headers: Any) -> str | None:
    return validated_correlation(
        headers.get("X-Tavo-Fixture-Nonce")
        or find_named_value(payload, frozenset({"fixturenonce"})),
        "nonce",
    )


def extract_intent(payload: Any, headers: Any, protocol: str) -> str:
    return (
        validated_correlation(
            headers.get("X-Tavo-Fixture-Intent")
            or find_named_value(payload, frozenset({"fixtureintent"})),
            "intent",
        )
        or protocol
    )


def contains_input_audio(value: Any, *, parent_key: str = "") -> bool:
    if isinstance(value, dict):
        own_type = str(value.get("type", "")).lower()
        if own_type in {"audio", "input_audio"} or "input_audio" in value:
            return True
        return any(
            contains_input_audio(item, parent_key=str(key))
            for key, item in value.items()
            if str(key) not in {"b64_json", "data"}
        )
    if isinstance(value, list):
        return any(contains_input_audio(item, parent_key=parent_key) for item in value)
    return parent_key == "input_audio"


def protocol_for_path(path: str, payload: Any) -> str:
    if path.endswith("/chat/completions"):
        return "openrouter-audio-chat" if contains_input_audio(payload) else "chat-completions"
    if path.endswith("/responses"):
        return "responses"
    if path.endswith("/completions"):
        return "completions"
    if path.endswith("/messages"):
        return "messages"
    if path.endswith("/images/generations"):
        return "images"
    if path.endswith("/audio/speech"):
        return "tts"
    if path.endswith("/audio/transcriptions"):
        return "asr"
    return "unknown"


def multipart_projection(
    raw_body: bytes,
    content_type: str,
) -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    if "boundary=" not in content_type.lower():
        raise RequestError(400, "fixture_invalid_multipart", "multipart boundary is required")
    message = BytesParser(policy=policy.default).parsebytes(
        (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8")
        + raw_body
    )
    if not message.is_multipart():
        raise RequestError(400, "fixture_invalid_multipart", "request is not valid multipart data")
    projected_fields: dict[str, Any] = {}
    plain_fields: dict[str, str] = {}
    files: list[dict[str, Any]] = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is not None:
            item = {
                "_fixtureMedia": {
                    "encoding": "multipart",
                    "field": redact_text(name),
                    "filename": redact_text(filename),
                    "mediaType": part.get_content_type(),
                    "sizeBytes": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            }
            files.append(item["_fixtureMedia"])
            captured: Any = item
        else:
            if len(payload) > MAX_TEXT_FIELD_BYTES:
                raise RequestError(
                    413,
                    "fixture_multipart_field_size",
                    f"multipart text field is too large: {name}",
                )
            try:
                text = payload.decode(part.get_content_charset() or "utf-8")
            except (LookupError, UnicodeDecodeError) as error:
                raise RequestError(
                    400,
                    "fixture_invalid_multipart_text",
                    f"multipart text field is invalid: {name}",
                ) from error
            plain_fields[name] = text
            captured = "<redacted>" if sensitive_key(name) else redact_text(text)
        if name in projected_fields:
            existing = projected_fields[name]
            projected_fields[name] = existing + [captured] if isinstance(existing, list) else [existing, captured]
        else:
            projected_fields[name] = captured
    return (
        {"kind": "multipart/form-data", "fields": projected_fields},
        plain_fields,
        files,
    )


@dataclass(frozen=True)
class VirtualProviderConfig:
    capture_dir: Path
    client_key: str
    model: str = "tavo-virtual"
    allowed_clients: tuple[ipaddress._BaseNetwork, ...] = ()
    slow_seconds: float = 0.10
    timeout_seconds: float = 0.50
    oversized_response_bytes: int = DEFAULT_OVERSIZED_RESPONSE_BYTES
    asset_base_url: str | None = None


class CaptureStore:
    def __init__(self, root: Path) -> None:
        secure_directory(root)
        self.root = root
        self._lock = threading.Lock()
        self._sequence = 0

    def begin(self, record: dict[str, Any]) -> Path:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        path = self.root / f"{sequence:06d}-{record['requestId']}.json"
        atomic_json(path, record)
        return path

    def update(self, path: Path, record: dict[str, Any]) -> None:
        with self._lock:
            atomic_json(path, record)


class VirtualProviderServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], config: VirtualProviderConfig) -> None:
        self.config = config
        self.store = CaptureStore(config.capture_dir)
        super().__init__(address, VirtualProviderHandler)


class VirtualProviderHandler(BaseHTTPRequestHandler):
    server: VirtualProviderServer
    protocol_version = "HTTP/1.1"
    server_version = "TavoVirtualProvider/1.0"

    def log_message(self, _fmt: str, *_args: object) -> None:
        return

    def _parsed_url(self) -> urllib.parse.SplitResult:
        return urllib.parse.urlsplit(self.path)

    def _allowed_client(self) -> bool:
        try:
            address = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return any(
            address.version == network.version and address in network
            for network in self.server.config.allowed_clients
        )

    def _authorized(self) -> bool:
        client_key = self.server.config.client_key
        if not client_key:
            return False
        bearer_value = self.headers.get("Authorization", "")
        expected_bearer = f"Bearer {client_key}"
        if hmac.compare_digest(
            bearer_value.encode("utf-8"),
            expected_bearer.encode("utf-8"),
        ):
            return True
        anthropic_value = self.headers.get("x-api-key", "")
        return hmac.compare_digest(
            anthropic_value.encode("utf-8"),
            client_key.encode("utf-8"),
        )

    def _send_uncaptured_json(self, status: int, payload: Any) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(encoded)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True

    def _reject_if_needed(self, *, require_auth: bool) -> bool:
        if not self._allowed_client():
            self._send_uncaptured_json(
                403,
                {"error": {"code": "fixture_client_denied", "message": "client denied"}},
            )
            return True
        if require_auth and not self._authorized():
            self._send_uncaptured_json(
                401,
                {"error": {"code": "fixture_unauthorized", "message": "unauthorized"}},
            )
            return True
        return False

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError as error:
            raise RequestError(411, "fixture_content_length", "invalid Content-Length") from error
        if length < 0:
            raise RequestError(411, "fixture_content_length", "Content-Length is required")
        if length > MAX_REQUEST_BYTES:
            raise RequestError(413, "fixture_body_size", "request body is too large")
        return self.rfile.read(length)

    def _request_record(
        self,
        *,
        path: str,
        protocol: str,
        scenario: str,
        nonce: str | None,
        intent: str,
        raw_body: bytes,
        body_projection: Any,
        method: str = "POST",
    ) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "provider": "tavo-virtual",
            "requestId": uuid.uuid4().hex,
            "receivedAt": utc_now(),
            "client": self.client_address[0],
            "method": method,
            "path": path,
            "protocol": protocol,
            "scenario": scenario,
            "nonce": nonce,
            "intent": intent,
            "requestHash": sha256_bytes(raw_body),
            "request": {
                "headers": {
                    "Authorization": (
                        "<redacted>" if self.headers.get("Authorization") else None
                    ),
                    "X-Api-Key": (
                        "<redacted>" if self.headers.get("x-api-key") else None
                    ),
                    "Content-Type": self.headers.get("Content-Type"),
                    "User-Agent": redact_text(self.headers.get("User-Agent", "")),
                },
                "rawBodyBytes": len(raw_body),
                "rawBodySha256": sha256_bytes(raw_body),
                "body": body_projection,
            },
        }

    def _send_captured_bytes(
        self,
        record: dict[str, Any],
        capture_path: Path,
        *,
        status: int,
        body: bytes,
        content_type: str,
        response_format: str,
        extra: dict[str, Any] | None = None,
        delay: bool = False,
        delay_seconds: float | None = None,
    ) -> None:
        response = {
            "status": status,
            "format": response_format,
            "contentType": content_type,
            "bodyBytes": len(body),
            "bodySha256": sha256_bytes(body),
            "startedAt": utc_now(),
            "completed": False,
            "clientDisconnected": False,
        }
        if extra:
            response.update(extra)
        record["response"] = response
        self.server.store.update(capture_path, record)
        effective_delay = (
            delay_seconds
            if delay_seconds is not None
            else (self.server.config.slow_seconds if delay else 0)
        )
        if effective_delay:
            time.sleep(effective_delay)
        disconnected = False
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            disconnected = True
        response["completed"] = not disconnected
        response["clientDisconnected"] = disconnected
        response["finishedAt"] = utc_now()
        self.server.store.update(capture_path, record)
        self.close_connection = True

    def _send_captured_json(
        self,
        record: dict[str, Any],
        capture_path: Path,
        *,
        status: int,
        payload: Any,
        extra: dict[str, Any] | None = None,
        delay: bool = False,
        delay_seconds: float | None = None,
    ) -> None:
        self._send_captured_bytes(
            record,
            capture_path,
            status=status,
            body=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            content_type="application/json; charset=utf-8",
            response_format="json",
            extra=extra,
            delay=delay,
            delay_seconds=delay_seconds,
        )

    @staticmethod
    def _sse_bytes(event_name: str | None, data: Any) -> bytes:
        output = bytearray()
        if event_name:
            output.extend(f"event: {event_name}\n".encode("utf-8"))
        encoded = data if isinstance(data, str) else json.dumps(data, separators=(",", ":"))
        for line in encoded.splitlines() or [""]:
            output.extend(f"data: {line}\n".encode("utf-8"))
        output.extend(b"\n")
        return bytes(output)

    def _send_sse(
        self,
        record: dict[str, Any],
        capture_path: Path,
        events: list[tuple[str | None, Any]],
        *,
        scenario: str,
        terminal_event: str,
    ) -> None:
        response = {
            "status": 200,
            "format": "sse",
            "contentType": "text/event-stream; charset=utf-8",
            "startedAt": utc_now(),
            "completed": False,
            "clientDisconnected": False,
            "eventsWritten": 0,
            "bytesWritten": 0,
            "terminalEvent": terminal_event,
            "terminalSent": False,
            "doneSent": False,
            "scenario": scenario,
        }
        record["response"] = response
        self.server.store.update(capture_path, record)
        disconnected = False
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            if scenario in {"slow", "slow_stream", "slow_stream_before_first"}:
                time.sleep(self.server.config.slow_seconds)
            if scenario == "malformed":
                chunks = [(None, '{"fixtureMalformed":')]
            elif scenario == "no_done":
                chunks = [
                    (event_name, data)
                    for event_name, data in events
                    if data != "[DONE]" and event_name != terminal_event
                ]
            else:
                chunks = events[:1] if scenario == "abrupt_eof" else events
            for index, (event_name, data) in enumerate(chunks):
                encoded = self._sse_bytes(event_name, data)
                self.wfile.write(encoded)
                self.wfile.flush()
                response["eventsWritten"] += 1
                response["bytesWritten"] += len(encoded)
                if data == "[DONE]":
                    response["doneSent"] = True
                if event_name == terminal_event or data == terminal_event:
                    response["terminalSent"] = True
                self.server.store.update(capture_path, record)
                if (
                    scenario in {"slow", "slow_stream"}
                    or (scenario == "slow_stream_after_first" and index == 0)
                ):
                    time.sleep(self.server.config.slow_seconds)
        except (BrokenPipeError, ConnectionResetError):
            disconnected = True
        response["completed"] = not disconnected and scenario != "abrupt_eof"
        response["clientDisconnected"] = disconnected
        response["finishedAt"] = utc_now()
        self.server.store.update(capture_path, record)
        self.close_connection = True

    def _error_response(
        self,
        record: dict[str, Any],
        capture_path: Path,
        *,
        status: int,
        code: str,
        message: str,
    ) -> None:
        self._send_captured_json(
            record,
            capture_path,
            status=status,
            payload={"error": {"code": code, "type": "fixture_error", "message": message}},
        )

    def _response_text(self, record: dict[str, Any]) -> str:
        prefix = (
            "TAVO_VIRTUAL_ASR_OK"
            if record["protocol"] == "openrouter-audio-chat"
            else "TAVO_VIRTUAL_OK"
        )
        return f"{prefix}::{record['requestHash'][:20]}"

    def _chat_events(self, record: dict[str, Any], text: str) -> list[tuple[str | None, Any]]:
        request_id = record["requestId"]
        midpoint = max(1, len(text) // 2)
        chunks = [text[:midpoint], text[midpoint:]]
        events: list[tuple[str | None, Any]] = []
        for chunk in chunks:
            if not chunk:
                continue
            events.append(
                (
                    None,
                    {
                        "id": f"chatcmpl-{request_id}",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": self.server.config.model,
                        "choices": [
                            {"index": 0, "delta": {"content": chunk}, "finish_reason": None}
                        ],
                    },
                )
            )
        events.append(
            (
                None,
                {
                    "id": f"chatcmpl-{request_id}",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": self.server.config.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            )
        )
        events.append((None, "[DONE]"))
        return events

    def _completion_events(
        self,
        record: dict[str, Any],
        text: str,
    ) -> list[tuple[str | None, Any]]:
        request_id = record["requestId"]
        return [
            (
                None,
                {
                    "id": f"cmpl-{request_id}",
                    "object": "text_completion",
                    "created": 0,
                    "model": self.server.config.model,
                    "choices": [{"index": 0, "text": text, "finish_reason": None}],
                },
            ),
            (
                None,
                {
                    "id": f"cmpl-{request_id}",
                    "object": "text_completion",
                    "created": 0,
                    "model": self.server.config.model,
                    "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
                },
            ),
            (None, "[DONE]"),
        ]

    def _responses_events(
        self,
        record: dict[str, Any],
        text: str,
    ) -> list[tuple[str | None, Any]]:
        response_id = f"resp-{record['requestId']}"
        created = {
            "type": "response.created",
            "response": {
                "id": response_id,
                "object": "response",
                "status": "in_progress",
                "model": self.server.config.model,
            },
        }
        delta = {
            "type": "response.output_text.delta",
            "response_id": response_id,
            "item_id": f"msg-{record['requestId']}",
            "output_index": 0,
            "content_index": 0,
            "delta": text,
        }
        completed = {
            "type": "response.completed",
            "response": self._responses_json(record, text),
        }
        return [
            ("response.created", created),
            ("response.output_text.delta", delta),
            ("response.completed", completed),
        ]

    def _messages_events(
        self,
        record: dict[str, Any],
        text: str,
    ) -> list[tuple[str | None, Any]]:
        request_id = record["requestId"]
        return [
            (
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": f"msg_{request_id}",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": self.server.config.model,
                        "stop_reason": None,
                        "usage": {"input_tokens": 1, "output_tokens": 0},
                    },
                },
            ),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                },
            ),
            (
                "content_block_stop",
                {"type": "content_block_stop", "index": 0},
            ),
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 1},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]

    def _chat_json(self, record: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "id": f"chatcmpl-{record['requestId']}",
            "object": "chat.completion",
            "created": 0,
            "model": self.server.config.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def _completion_json(self, record: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "id": f"cmpl-{record['requestId']}",
            "object": "text_completion",
            "created": 0,
            "model": self.server.config.model,
            "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def _responses_json(self, record: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "id": f"resp-{record['requestId']}",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": self.server.config.model,
            "output": [
                {
                    "id": f"msg-{record['requestId']}",
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}],
                }
            ],
            "output_text": text,
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }

    def _messages_json(self, record: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "id": f"msg_{record['requestId']}",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "model": self.server.config.model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    def _serve_language_protocol(
        self,
        record: dict[str, Any],
        capture_path: Path,
        payload: dict[str, Any],
    ) -> None:
        scenario = record["scenario"]
        text = self._response_text(record)
        stream = bool(payload.get("stream"))
        protocol = record["protocol"]
        if protocol in {"chat-completions", "openrouter-audio-chat"}:
            json_payload = self._chat_json(record, text)
            events = self._chat_events(record, text)
            terminal = "[DONE]"
        elif protocol == "completions":
            json_payload = self._completion_json(record, text)
            events = self._completion_events(record, text)
            terminal = "[DONE]"
        elif protocol == "responses":
            json_payload = self._responses_json(record, text)
            events = self._responses_events(record, text)
            terminal = "response.completed"
        elif protocol == "messages":
            json_payload = self._messages_json(record, text)
            events = self._messages_events(record, text)
            terminal = "message_stop"
        else:
            raise AssertionError(f"unexpected language protocol: {protocol}")
        if stream:
            self._send_sse(
                record,
                capture_path,
                events,
                scenario=scenario,
                terminal_event=terminal,
            )
            return
        self._send_captured_json(
            record,
            capture_path,
            status=200,
            payload=json_payload,
            delay=scenario in {"slow", "slow_stream", "slow_stream_before_first"},
        )

    def _asset_origin(self) -> str:
        configured = self.server.config.asset_base_url
        if configured:
            return configured
        host = self.headers.get("Host", "")
        if host and SAFE_HOST_PATTERN.fullmatch(host):
            return f"http://{host}"
        server_host, server_port = self.server.server_address[:2]
        if ":" in str(server_host) and not str(server_host).startswith("["):
            server_host = f"[{server_host}]"
        return f"http://{server_host}:{server_port}"

    def _serve_image(
        self,
        record: dict[str, Any],
        capture_path: Path,
        payload: dict[str, Any],
    ) -> None:
        response_format = str(payload.get("response_format", "b64_json"))
        image_meta = {
            "mediaType": "image/png",
            "sizeBytes": len(PNG_BYTES),
            "sha256": sha256_bytes(PNG_BYTES),
        }
        if response_format == "url":
            query = ""
            if record["nonce"]:
                query = "?" + urllib.parse.urlencode({"nonce": record["nonce"]})
            item = {"url": self._asset_origin() + ASSET_PATH + query}
        elif response_format == "b64_json":
            item = {"b64_json": base64.b64encode(PNG_BYTES).decode("ascii")}
        else:
            self._error_response(
                record,
                capture_path,
                status=400,
                code="fixture_image_response_format",
                message="response_format must be b64_json or url",
            )
            return
        self._send_captured_json(
            record,
            capture_path,
            status=200,
            payload={"created": 0, "data": [item]},
            extra={"media": image_meta, "responseFormat": response_format},
            delay=record["scenario"] == "slow",
        )

    def _serve_tts(
        self,
        record: dict[str, Any],
        capture_path: Path,
    ) -> None:
        self._send_captured_bytes(
            record,
            capture_path,
            status=200,
            body=WAV_BYTES,
            content_type="audio/wav",
            response_format="audio",
            extra={
                "media": {
                    "mediaType": "audio/wav",
                    "sizeBytes": len(WAV_BYTES),
                    "sha256": sha256_bytes(WAV_BYTES),
                }
            },
            delay=record["scenario"] == "slow",
        )

    def _serve_asr(
        self,
        record: dict[str, Any],
        capture_path: Path,
        fields: dict[str, str],
        files: list[dict[str, Any]],
    ) -> None:
        if not files:
            self._error_response(
                record,
                capture_path,
                status=400,
                code="fixture_asr_file_required",
                message="an audio file is required",
            )
            return
        audio_hash = files[0]["sha256"]
        transcript = f"TAVO_VIRTUAL_TRANSCRIPT::{audio_hash[:20]}"
        response_format = fields.get("response_format", "json")
        if response_format == "text":
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=transcript.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
                response_format="text",
                delay=record["scenario"] == "slow",
            )
            return
        payload: dict[str, Any] = {"text": transcript}
        if response_format == "verbose_json":
            payload.update(
                {
                    "task": "transcribe",
                    "language": fields.get("language", "en"),
                    "duration": 0.2,
                    "segments": [],
                }
            )
        self._send_captured_json(
            record,
            capture_path,
            status=200,
            payload=payload,
            delay=record["scenario"] == "slow",
        )

    def _handle_fault_scenario(
        self,
        record: dict[str, Any],
        capture_path: Path,
        payload: dict[str, Any],
    ) -> bool:
        scenario = record["scenario"]
        if scenario in HTTP_ERROR_SCENARIOS:
            status = HTTP_ERROR_SCENARIOS[scenario]
            self._error_response(
                record,
                capture_path,
                status=status,
                code=f"fixture_http_{status}",
                message=f"fixture HTTP {status}",
            )
            return True
        if scenario == "malformed" and not bool(payload.get("stream")):
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=b'{"fixtureMalformed":',
                content_type="application/json; charset=utf-8",
                response_format="malformed-json",
            )
            return True
        if scenario == "wrong_content_type":
            body = json.dumps(
                {"fixtureWrongContentType": True, "requestId": record["requestId"]},
                separators=(",", ":"),
            ).encode("utf-8")
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=body,
                content_type="text/plain; charset=utf-8",
                response_format="wrong-content-type",
            )
            return True
        if scenario == "timeout":
            self._send_captured_json(
                record,
                capture_path,
                status=200,
                payload={
                    "fixtureTimeout": True,
                    "requestId": record["requestId"],
                },
                extra={"timeoutSeconds": self.server.config.timeout_seconds},
                delay_seconds=self.server.config.timeout_seconds,
            )
            return True
        if scenario == "empty":
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=b"",
                content_type="application/json; charset=utf-8",
                response_format="empty",
            )
            return True
        if scenario == "oversized":
            body = json.dumps(
                {
                    "fixtureOversized": True,
                    "padding": "X" * self.server.config.oversized_response_bytes,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=body,
                content_type="application/json; charset=utf-8",
                response_format="oversized-json",
                extra={"configuredPaddingBytes": self.server.config.oversized_response_bytes},
            )
            return True
        if scenario == "abrupt_eof" and not bool(payload.get("stream")):
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=b'{"fixtureAbrupt":',
                content_type="application/json; charset=utf-8",
                response_format="abrupt-json-eof",
            )
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = self._parsed_url()
        path = parsed.path
        if path == "/health":
            if self._reject_if_needed(require_auth=False):
                return
            self._send_uncaptured_json(
                200,
                {
                    "ok": True,
                    "providerMode": "virtual",
                    "realModelRequestsSent": 0,
                    "model": self.server.config.model,
                },
            )
            return
        if path in MODELS_PATHS:
            if self._reject_if_needed(require_auth=True):
                return
            self._send_uncaptured_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": self.server.config.model,
                            "object": "model",
                            "owned_by": "tavo-virtual",
                        }
                    ],
                },
            )
            return
        if path == ASSET_PATH:
            if self._reject_if_needed(require_auth=False):
                return
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            try:
                nonce = validated_correlation((query.get("nonce") or [None])[0], "nonce")
            except RequestError as error:
                self._send_uncaptured_json(
                    error.status,
                    {"error": {"code": error.code, "message": str(error)}},
                )
                return
            record = self._request_record(
                path=path,
                protocol="image-asset",
                scenario="normal",
                nonce=nonce,
                intent="image-asset",
                raw_body=b"",
                body_projection=None,
                method="GET",
            )
            capture_path = self.server.store.begin(record)
            self._send_captured_bytes(
                record,
                capture_path,
                status=200,
                body=PNG_BYTES,
                content_type="image/png",
                response_format="binary",
                extra={
                    "media": {
                        "mediaType": "image/png",
                        "sizeBytes": len(PNG_BYTES),
                        "sha256": sha256_bytes(PNG_BYTES),
                    }
                },
            )
            return
        if self._reject_if_needed(require_auth=True):
            return
        record = self._request_record(
            path=path,
            protocol="unknown",
            scenario="normal",
            nonce=None,
            intent="unknown-get",
            raw_body=b"",
            body_projection={
                "_fixtureRaw": {
                    "queryPresent": bool(parsed.query),
                    "sizeBytes": 0,
                    "sha256": sha256_bytes(b""),
                }
            },
            method="GET",
        )
        capture_path = self.server.store.begin(record)
        self._error_response(
            record,
            capture_path,
            status=501,
            code="fixture_not_implemented",
            message=f"virtual route is not implemented: {path}",
        )

    def do_POST(self) -> None:  # noqa: N802
        parsed = self._parsed_url()
        path = parsed.path
        if self._reject_if_needed(require_auth=True):
            return
        try:
            raw_body = self._read_body()
        except RequestError as error:
            self._send_uncaptured_json(
                error.status,
                {"error": {"code": error.code, "message": str(error)}},
            )
            return

        content_type = self.headers.get("Content-Type", "")
        payload: Any = {}
        fields: dict[str, str] = {}
        files: list[dict[str, Any]] = []
        body_projection: Any
        supported = path in JSON_POST_PATHS or path in ASR_POST_PATHS
        try:
            if path in ASR_POST_PATHS:
                if not content_type.lower().startswith("multipart/form-data"):
                    raise RequestError(
                        415,
                        "fixture_content_type",
                        "ASR requests must use multipart/form-data",
                    )
                body_projection, fields, files = multipart_projection(raw_body, content_type)
                payload = fields
            elif content_type.lower().startswith("application/json"):
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise RequestError(
                        400,
                        "fixture_invalid_json",
                        "request body must be valid UTF-8 JSON",
                    ) from error
                if not isinstance(payload, dict):
                    raise RequestError(
                        400,
                        "fixture_invalid_json",
                        "request JSON must be an object",
                    )
                body_projection = project_capture(payload)
            elif supported:
                raise RequestError(
                    415,
                    "fixture_content_type",
                    "request must use application/json",
                )
            else:
                body_projection = {
                    "_fixtureRaw": {
                        "contentType": content_type or None,
                        "sizeBytes": len(raw_body),
                        "sha256": sha256_bytes(raw_body),
                    }
                }
            protocol = protocol_for_path(path, payload)
            scenario = extract_scenario(payload, self.headers)
            nonce = extract_nonce(payload, self.headers)
            intent = extract_intent(payload, self.headers, protocol)
        except RequestError as error:
            body_projection = {
                "_fixtureRaw": {
                    "contentType": content_type or None,
                    "sizeBytes": len(raw_body),
                    "sha256": sha256_bytes(raw_body),
                }
            }
            record = self._request_record(
                path=path,
                protocol=protocol_for_path(path, {}),
                scenario="invalid-request",
                nonce=None,
                intent="invalid-request",
                raw_body=raw_body,
                body_projection=body_projection,
            )
            capture_path = self.server.store.begin(record)
            self._error_response(
                record,
                capture_path,
                status=error.status,
                code=error.code,
                message=str(error),
            )
            return

        record = self._request_record(
            path=path,
            protocol=protocol,
            scenario=scenario,
            nonce=nonce,
            intent=intent,
            raw_body=raw_body,
            body_projection=body_projection,
        )
        capture_path = self.server.store.begin(record)
        if not supported:
            self._error_response(
                record,
                capture_path,
                status=501,
                code="fixture_not_implemented",
                message=f"virtual route is not implemented: {path}",
            )
            return
        if self._handle_fault_scenario(record, capture_path, payload):
            return
        if protocol in {
            "chat-completions",
            "openrouter-audio-chat",
            "completions",
            "responses",
            "messages",
        }:
            self._serve_language_protocol(record, capture_path, payload)
            return
        if protocol == "images":
            self._serve_image(record, capture_path, payload)
            return
        if protocol == "tts":
            self._serve_tts(record, capture_path)
            return
        if protocol == "asr":
            self._serve_asr(record, capture_path, fields, files)
            return
        self._error_response(
            record,
            capture_path,
            status=501,
            code="fixture_not_implemented",
            message=f"virtual protocol is not implemented: {protocol}",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Listen port; 0 selects an ephemeral port.")
    parser.add_argument("--model", default="tavo-virtual")
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--client-key-file", type=Path, required=True)
    parser.add_argument("--delete-client-key-file", action="store_true")
    parser.add_argument("--allowed-client", action="append", default=[])
    parser.add_argument("--slow-seconds", type=float, default=0.10)
    parser.add_argument("--timeout-seconds", type=float, default=0.50)
    parser.add_argument(
        "--oversized-response-bytes",
        type=int,
        default=DEFAULT_OVERSIZED_RESPONSE_BYTES,
    )
    parser.add_argument("--asset-base-url")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> VirtualProviderConfig:
    if not (0 <= args.port <= 65535):
        raise ValueError("--port must be between 0 and 65535")
    if not (0 <= args.slow_seconds <= 10):
        raise ValueError("--slow-seconds must be between 0 and 10")
    if not (0 <= args.timeout_seconds <= 60):
        raise ValueError("--timeout-seconds must be between 0 and 60")
    if not (1024 <= args.oversized_response_bytes <= 64 * 1024 * 1024):
        raise ValueError("--oversized-response-bytes must be between 1024 and 67108864")
    allowed_values = list(args.allowed_client)
    if not allowed_values and is_loopback_bind(args.bind):
        allowed_values = [args.bind if args.bind != "localhost" else "127.0.0.1", "::1"]
    if not allowed_values:
        raise ValueError("Non-loopback bind requires at least one --allowed-client")
    return VirtualProviderConfig(
        capture_dir=args.capture_dir.expanduser().resolve(),
        client_key=read_secret_file(
            args.client_key_file.expanduser().resolve(),
            delete_after_read=args.delete_client_key_file,
        ),
        model=args.model,
        allowed_clients=validate_allowed_clients(allowed_values),
        slow_seconds=args.slow_seconds,
        timeout_seconds=args.timeout_seconds,
        oversized_response_bytes=args.oversized_response_bytes,
        asset_base_url=normalized_asset_base_url(args.asset_base_url),
    )


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    server = VirtualProviderServer((args.bind, args.port), config)
    stopping = threading.Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        if not stopping.is_set():
            stopping.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    host, port = server.server_address[:2]
    print(
        json.dumps(
            {
                "ok": True,
                "providerMode": "virtual",
                "realModelRequestsSent": 0,
                "baseUrl": f"http://{host}:{port}/v1",
                "model": config.model,
                "captureDir": str(config.capture_dir),
                "allowedClients": [str(item) for item in config.allowed_clients],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
