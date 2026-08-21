#!/usr/bin/env python3
"""Small, privacy-first JSON-RPC client for an authorized Tavo MCP server."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import math
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


MAX_ENDPOINT_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 128
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = {DEFAULT_PROTOCOL_VERSION}
SUPPORTED_METHODS = {"initialize", "ping", "tools/list", "tools/call"}
SENSITIVE_KEYS = {
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "clientsecret",
    "cookie",
    "credential",
    "idtoken",
    "key",
    "mcpsessionid",
    "password",
    "privatekey",
    "proxyauthorization",
    "refreshtoken",
    "secret",
    "sessionid",
    "setcookie",
    "token",
    "xapikey",
    "xauthtoken",
    "accesstoken",
}
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b|"
    r"\btavo-cap-[A-Za-z0-9_-]{10,}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
URL_OCCURRENCE_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
EMBEDDED_AUTH_RE = re.compile(
    r"\b(?P<scheme>Bearer|Basic)\s+(?P<secret>[A-Za-z0-9._~+/=-]{4,})",
    re.IGNORECASE,
)
CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?P<quote>['\"]?)(?P<key>api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|id[_-]?token|client[_-]?secret|private[_-]?key|password|"
    r"proxy[_-]?authorization|authorization|(?:mcp[_-]?)?session[_-]?id|"
    r"set[_-]?cookie|cookie|secret|token)(?P=quote)"
    r"(?P<before>\s*)(?P<separator>[:=])(?P<after>\s*)"
    r"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;&]+(?:\s+[^\s,;&]+)?)",
    re.IGNORECASE,
)


def normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def sensitive_key(value: str) -> bool:
    normalized = normalized_key(value)
    return normalized in SENSITIVE_KEYS or normalized.endswith(
        ("token", "secret", "password", "credential", "privatekey", "apikey")
    )


def expand_secret_values(values: tuple[str, ...]) -> tuple[str, ...]:
    expanded: set[str] = set()
    for value in values:
        if not value:
            continue
        expanded.add(value)
        expanded.add(urllib.parse.quote(value, safe=""))
        expanded.add(urllib.parse.quote_plus(value, safe=""))
    return tuple(sorted(expanded, key=len, reverse=True))


def authentication_secrets(auth: str) -> tuple[str, ...]:
    values = {auth.strip()} if auth.strip() else set()
    parts = auth.strip().split(None, 1)
    if len(parts) == 2 and parts[0].lower() in {"bearer", "basic"}:
        values.add(parts[1])
    return expand_secret_values(tuple(item for item in values if item))


def normalize_authorization(auth: str) -> str:
    value = auth.strip()
    if not value:
        return ""
    if len(value) > 8192 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("authorization value contains invalid characters or is too long")
    parts = value.split(None, 1)
    if len(parts) == 2:
        if parts[0].lower() != "bearer":
            raise ValueError("authorization must use the bearer scheme")
        token = parts[1]
    else:
        token = value
    if not token or any(character.isspace() for character in token):
        raise ValueError("Bearer token is invalid")
    return f"Bearer {token}"


def redact_url_occurrence(match: re.Match[str]) -> str:
    value = match.group(0)
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        return "<redacted-url>"
    if not hostname:
        return "<redacted-url>"
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    try:
        query = [
            (key, "<redacted>" if sensitive_key(key) else SECRET_VALUE_RE.sub("<redacted-secret>", item))
            for key, item in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        ]
    except ValueError:
        return "<redacted-url>"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, urllib.parse.urlencode(query), ""))


def redact_credential_assignment(match: re.Match[str]) -> str:
    quote = match.group("quote")
    return (
        f"{quote}{match.group('key')}{quote}{match.group('before')}"
        f"{match.group('separator')}{match.group('after')}<redacted>"
    )


def redact_text(value: str, secret_values: tuple[str, ...] = ()) -> str:
    for secret in secret_values:
        value = value.replace(secret, "<redacted-secret>")
    value = EMBEDDED_AUTH_RE.sub(lambda match: f"{match.group('scheme')} <redacted>", value)
    value = CREDENTIAL_ASSIGNMENT_RE.sub(redact_credential_assignment, value)
    value = URL_OCCURRENCE_RE.sub(redact_url_occurrence, value)
    return SECRET_VALUE_RE.sub("<redacted-secret>", value)


def redact(value: Any, secret_values: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            original_key = str(key)
            safe_key = redact_text(original_key, secret_values)
            redacted[safe_key] = "<redacted>" if sensitive_key(original_key) else redact(item, secret_values)
        return redacted
    if isinstance(value, list):
        return [redact(item, secret_values) for item in value]
    if isinstance(value, str):
        return redact_text(value, secret_values)
    return value


def read_private_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("endpoint file cannot be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("endpoint file must be a regular file")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ValueError("endpoint file must have mode 0600")
        if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
            raise ValueError("endpoint file must be owned by the current user")
        if metadata.st_size > MAX_ENDPOINT_BYTES:
            raise ValueError(f"endpoint file exceeds {MAX_ENDPOINT_BYTES} bytes")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            data = json.load(
                handle,
                object_pairs_hook=reject_duplicate_object,
                parse_constant=reject_json_constant,
                parse_float=parse_finite_float,
            )
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(data, dict):
        raise ValueError("endpoint file must contain a JSON object")
    enforce_json_depth(data)
    return data


def load_endpoint(raw_path: str) -> dict[str, str]:
    if not raw_path:
        return {}
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError("endpoint file does not exist")
    data = read_private_json(path)
    return {
        "url": str(data.get("url") or data.get("lan_url") or data.get("local_url") or ""),
        "auth": str(data.get("auth") or data.get("authorization") or data.get("token") or ""),
    }


def select_connection(raw_path: str, environment_url: str, environment_auth: str) -> tuple[str, str]:
    if raw_path:
        endpoint = load_endpoint(raw_path)
        url = endpoint.get("url", "")
        auth = endpoint.get("auth", "")
        if not url or not auth:
            raise ValueError("endpoint file must contain both URL and authorization")
        return url, auth
    if bool(environment_url) != bool(environment_auth):
        raise ValueError("TAVO_MCP_URL and TAVO_MCP_AUTH must be set together")
    if not environment_url:
        raise ValueError("provide a mode-0600 endpoint file or both MCP environment variables")
    return environment_url, environment_auth


def reject_output_input_collision(endpoint_path: str, output_path: str) -> None:
    if not endpoint_path or not output_path:
        return
    endpoint = Path(endpoint_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if endpoint == output:
        raise ValueError("output path cannot overwrite the endpoint file")
    try:
        if endpoint.exists() and output.exists() and os.path.samefile(endpoint, output):
            raise ValueError("output path cannot overwrite the endpoint file")
    except OSError as exc:
        raise ValueError("could not safely compare endpoint and output paths") from exc


def atomic_private_text(path: Path, value: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("output path cannot be a symlink")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(value)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass


def is_loopback_host(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_endpoint_url(url: str, allow_insecure_http: bool = False) -> str:
    if not url or "\\" in url or any(character.isspace() or ord(character) < 32 for character in url):
        raise ValueError("endpoint URL must be a non-empty absolute URL without whitespace")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("endpoint URL is invalid") from exc
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("endpoint URL must use HTTPS or HTTP and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint URL cannot include user information")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint URL cannot include query parameters or a fragment")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("endpoint URL port is invalid")
    if parsed.scheme == "http" and not is_loopback_host(parsed.hostname) and not allow_insecure_http:
        raise ValueError("non-loopback HTTP requires --allow-insecure-http")
    return url


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


class McpHttpError(Exception):
    def __init__(self, status: int):
        super().__init__(f"MCP request failed with HTTP status {status}")
        self.status = status


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid command line")


def build_direct_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler())


def validate_header_value(value: str, label: str) -> str:
    if not value or len(value) > 4096 or any(not 0x21 <= ord(character) <= 0x7E for character in value):
        raise ValueError(f"{label} header is invalid")
    return value


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key is not allowed")
        result[key] = value
    return result


def parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number is not allowed")
    return parsed


def enforce_json_depth(value: Any, maximum: int = MAX_JSON_DEPTH) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > maximum:
            raise ValueError(f"MCP JSON nesting exceeds {maximum} levels")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def decode_mcp_json(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(
            body.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_object,
            parse_constant=reject_json_constant,
            parse_float=parse_finite_float,
        )
    except RecursionError as exc:
        raise ValueError("MCP JSON nesting exceeds the parser limit") from exc
    if not isinstance(data, dict):
        raise ValueError("MCP response must be a JSON object")
    enforce_json_depth(data)
    return data


def exchange(
    url: str,
    auth: str,
    method: str,
    params: dict[str, Any],
    request_id: int | None,
    *,
    allow_insecure_http: bool = False,
    protocol_version: str = "",
    session_id: str = "",
    expect_empty: bool = False,
) -> tuple[dict[str, Any] | None, str]:
    validate_endpoint_url(url, allow_insecure_http=allow_insecure_http)
    normalized_auth = normalize_authorization(auth)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if normalized_auth:
        headers["Authorization"] = normalized_auth
    if protocol_version:
        headers["MCP-Protocol-Version"] = validate_header_value(protocol_version, "protocol version")
    if session_id:
        headers["Mcp-Session-Id"] = validate_header_value(session_id, "session ID")
    envelope: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
    if request_id is not None:
        envelope["id"] = request_id
    payload = json.dumps(envelope, allow_nan=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    opener = build_direct_opener()
    try:
        with opener.open(request, timeout=30) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type == "text/event-stream":
                raise ValueError("SSE responses are not supported by this client")
            response_session = response.headers.get("Mcp-Session-Id", "")
            if response_session:
                validate_header_value(response_session, "session ID")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise McpHttpError(status) from None
    except http.client.HTTPException:
        raise ValueError("MCP server returned an invalid HTTP response") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("MCP response exceeds the size limit")
    if expect_empty:
        if status not in {202, 204}:
            raise ValueError("MCP notification response must use HTTP 202 or 204")
        if body:
            raise ValueError("MCP notification response must be empty")
        return None, response_session
    if status != 200:
        raise ValueError("MCP JSON response must use HTTP 200")
    if content_type != "application/json":
        raise ValueError("MCP JSON response must use application/json")
    if not body:
        raise ValueError("MCP response body is empty")
    data = decode_mcp_json(body)
    return data, response_session


def validate_jsonrpc_response(response: dict[str, Any], request_id: int) -> None:
    if response.get("jsonrpc") != "2.0":
        raise ValueError("MCP response has an invalid JSON-RPC version")
    response_id = response.get("id")
    if type(response_id) is not type(request_id) or response_id != request_id:
        raise ValueError("MCP response ID does not match the request")
    if ("result" in response) == ("error" in response):
        raise ValueError("MCP response must contain exactly one of result or error")


def rpc(
    url: str,
    auth: str,
    method: str,
    params: dict[str, Any],
    request_id: int = 1,
    *,
    allow_insecure_http: bool = False,
    protocol_version: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    response, _ = exchange(
        url,
        auth,
        method,
        params,
        request_id,
        allow_insecure_http=allow_insecure_http,
        protocol_version=protocol_version,
        session_id=session_id,
    )
    if response is None:
        raise ValueError("MCP request returned no response")
    validate_jsonrpc_response(response, request_id)
    return response


def validate_negotiated_protocol(response: dict[str, Any], requested: str) -> str:
    if "error" in response:
        return ""
    result = response.get("result")
    negotiated = result.get("protocolVersion") if isinstance(result, dict) else None
    if not isinstance(negotiated, str) or not negotiated:
        raise ValueError("initialize response did not declare a protocol version")
    if negotiated != requested or negotiated not in SUPPORTED_PROTOCOL_VERSIONS:
        raise ValueError("server negotiated an unsupported protocol version")
    return negotiated


def validate_initialize_result(response: dict[str, Any]) -> None:
    if "error" in response:
        return
    result = response.get("result")
    if not isinstance(result, dict):
        raise ValueError("initialize result must be an object")
    if not isinstance(result.get("capabilities"), dict):
        raise ValueError("initialize result must declare capabilities")
    server_info = result.get("serverInfo")
    if not isinstance(server_info, dict):
        raise ValueError("initialize result must declare serverInfo")
    for field in ("name", "version"):
        value = server_info.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"initialize serverInfo.{field} must be a non-empty string")


def require_advertised_capability(initialize_response: dict[str, Any], method: str) -> None:
    if method not in SUPPORTED_METHODS:
        raise ValueError("this client supports only initialize, ping, tools/list, and tools/call")
    family = "tools" if method.startswith("tools/") else ""
    if not family:
        return
    result = initialize_response.get("result")
    capabilities = result.get("capabilities") if isinstance(result, dict) else None
    if not isinstance(capabilities, dict) or not isinstance(capabilities.get(family), dict):
        raise ValueError(f"server did not advertise the {family} capability")


def run_mcp_operation(
    url: str,
    auth: str,
    method: str,
    params: dict[str, Any],
    *,
    allow_insecure_http: bool = False,
) -> tuple[dict[str, Any], str]:
    if method not in SUPPORTED_METHODS:
        raise ValueError("this client supports only initialize, ping, tools/list, and tools/call")
    initialize_params = {
        "protocolVersion": DEFAULT_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "tavo-skill-mcp-client", "version": "1.2.1"},
    }
    initialize_response, session_id = exchange(
        url,
        auth,
        "initialize",
        initialize_params,
        1,
        allow_insecure_http=allow_insecure_http,
    )
    if initialize_response is None:
        raise ValueError("initialize returned no response")
    validate_jsonrpc_response(initialize_response, 1)
    if "error" in initialize_response:
        return initialize_response, session_id
    validate_initialize_result(initialize_response)
    negotiated = validate_negotiated_protocol(initialize_response, DEFAULT_PROTOCOL_VERSION)
    require_advertised_capability(initialize_response, method)
    exchange(
        url,
        auth,
        "notifications/initialized",
        {},
        None,
        allow_insecure_http=allow_insecure_http,
        protocol_version=negotiated,
        session_id=session_id,
        expect_empty=True,
    )
    if method == "initialize":
        return initialize_response, session_id
    result = rpc(
        url,
        auth,
        method,
        params,
        request_id=2,
        allow_insecure_http=allow_insecure_http,
        protocol_version=negotiated,
        session_id=session_id,
    )
    return result, session_id


def main() -> int:
    parser = SafeArgumentParser(description="Call an authorized Tavo MCP JSON-RPC endpoint.")
    parser.add_argument("--endpoint-json", default="", help="Explicit mode-0600 JSON file containing URL/auth")
    parser.add_argument(
        "--allow-insecure-http",
        action="store_true",
        help="Explicitly allow unencrypted HTTP for a non-loopback endpoint.",
    )
    parser.add_argument("--method", default="initialize")
    parser.add_argument("--params-json", default="")
    parser.add_argument("--tool", default="", help="Call a Tavo tool through JSON-RPC tools/call.")
    parser.add_argument("--arguments-json", default="{}", help="Arguments for --tool.")
    parser.add_argument("--output", default="")
    try:
        args = parser.parse_args()
        reject_output_input_collision(args.endpoint_json, args.output)
        url, raw_auth = select_connection(
            args.endpoint_json,
            os.environ.get("TAVO_MCP_URL", ""),
            os.environ.get("TAVO_MCP_AUTH", ""),
        )
        auth = normalize_authorization(raw_auth)
        validate_endpoint_url(url, allow_insecure_http=args.allow_insecure_http)
        if args.tool:
            method = "tools/call"
            params = {"name": args.tool, "arguments": json.loads(args.arguments_json)}
        else:
            method = args.method
            params = json.loads(args.params_json) if args.params_json else {}
            if method == "initialize" and args.params_json:
                raise ValueError("initialize parameters are fixed by this Tavo 1.2.1 client")
        if not isinstance(params, dict):
            raise ValueError("JSON-RPC params must be an object")
        result, session_id = run_mcp_operation(
            url,
            auth,
            method,
            params,
            allow_insecure_http=args.allow_insecure_http,
        )
        secret_values = authentication_secrets(auth)
        if session_id:
            secret_values = expand_secret_values((*secret_values, session_id))
        output = redact(result, secret_values)
        text = json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            atomic_private_text(Path(args.output), text)
        print(text, end="")
        return 0 if "error" not in result else 1
    except McpHttpError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        print(f"MCP request failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
