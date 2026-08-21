#!/usr/bin/env python3
"""Privacy and file-safety tests for the bundled MCP client."""

from __future__ import annotations

import contextlib
import io
import json
import os
import socketserver
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import tavo_mcp_client as client


class RedirectSinkHandler(BaseHTTPRequestHandler):
    authorizations: list[str | None] = []

    def _record(self) -> None:
        self.__class__.authorizations.append(self.headers.get("Authorization"))
        body = b'{"jsonrpc":"2.0","id":1,"result":{}}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _record
    do_POST = _record

    def log_message(self, format: str, *args: object) -> None:
        return


class RedirectSourceHandler(BaseHTTPRequestHandler):
    location = ""
    status = 302
    authorizations: list[str | None] = []

    def do_POST(self) -> None:
        self.__class__.authorizations.append(self.headers.get("Authorization"))
        self.send_response(self.__class__.status)
        self.send_header("Location", self.__class__.location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class MalformedHttpHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.recv(4096)
        self.request.sendall(b"NOT-HTTP\r\n\r\n")


class LifecycleHandler(BaseHTTPRequestHandler):
    calls: list[dict[str, object]] = []
    session_id = "example-session-id"
    echo_authorization = False
    negotiated_protocol = client.DEFAULT_PROTOCOL_VERSION
    capabilities: dict[str, object] = {"tools": {}}
    server_info: object = {"name": "example", "version": "1.0"}
    initialize_error: dict[str, object] | None = None
    initialize_content_type = "application/json"
    notification_status = 204
    tool_nested_depth = 0

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.calls.append(
            {
                "payload": payload,
                "authorization": self.headers.get("Authorization"),
                "protocol": self.headers.get("MCP-Protocol-Version"),
                "session": self.headers.get("Mcp-Session-Id"),
            }
        )
        method = payload.get("method")
        if method == "notifications/initialized":
            self.send_response(self.__class__.notification_status)
            self.end_headers()
            return
        if method == "initialize":
            if self.__class__.initialize_error is not None:
                result = {"jsonrpc": "2.0", "id": payload["id"], "error": self.__class__.initialize_error}
            else:
                result = {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": self.__class__.negotiated_protocol,
                        "capabilities": self.__class__.capabilities,
                        "serverInfo": self.__class__.server_info,
                    },
                }
            session_header = self.__class__.session_id
        else:
            tool_result: dict[str, object] = {"ok": True}
            if self.__class__.tool_nested_depth:
                nested: object = "leaf"
                for _ in range(self.__class__.tool_nested_depth):
                    nested = [nested]
                tool_result["nested"] = nested
            if self.__class__.echo_authorization:
                tool_result["message"] = (
                    f"echo {self.headers.get('Authorization', '')} "
                    f"session {self.headers.get('Mcp-Session-Id', '')}"
                )
            result = {"jsonrpc": "2.0", "id": payload["id"], "result": tool_result}
            session_header = ""
        body = json.dumps(result).encode("utf-8")
        self.send_response(200)
        if self.__class__.initialize_content_type:
            self.send_header("Content-Type", self.__class__.initialize_content_type)
        self.send_header("Content-Length", str(len(body)))
        if session_header:
            self.send_header("Mcp-Session-Id", session_header)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def reset_lifecycle_handler() -> None:
    LifecycleHandler.calls = []
    LifecycleHandler.echo_authorization = False
    LifecycleHandler.negotiated_protocol = client.DEFAULT_PROTOCOL_VERSION
    LifecycleHandler.capabilities = {"tools": {}}
    LifecycleHandler.server_info = {"name": "example", "version": "1.0"}
    LifecycleHandler.initialize_error = None
    LifecycleHandler.initialize_content_type = "application/json"
    LifecycleHandler.notification_status = 204
    LifecycleHandler.tool_nested_depth = 0


class RedactionTests(unittest.TestCase):
    def test_sensitive_key_variants_are_redacted(self) -> None:
        payload = {
            "access_token": "alpha",
            "refreshToken": "beta",
            "client-secret": "gamma",
            "password": "delta",
            "x-api-key": "epsilon",
            "proxy-authorization": "zeta",
            "nested": {"ordinary": "kept"},
        }

        result = client.redact(payload)

        for key in payload:
            if key != "nested":
                self.assertEqual(result[key], "<redacted>")
        self.assertEqual(result["nested"]["ordinary"], "kept")

    def test_secret_values_and_url_query_are_redacted(self) -> None:
        secret = "sk-" + "EXAMPLEPLACEHOLDER" * 2
        self.assertEqual(client.redact_text("Bearer " + secret), "Bearer <redacted>")
        self.assertEqual(client.redact_text(secret), "<redacted-secret>")

        value = "https://example.invalid/rpc?access_token=" + secret + "&mode=safe"
        redacted = client.redact_text(value)
        self.assertIn("access_token=%3Credacted%3E", redacted)
        self.assertIn("mode=safe", redacted)
        self.assertNotIn(secret, redacted)

    def test_embedded_and_uppercase_url_credentials_are_redacted(self) -> None:
        opaque = "opaque-" + "EXAMPLEVALUE" * 2
        values = (
            "HTTPS://example.invalid/callback?access_token=" + opaque,
            "prefix https://example.invalid/callback?api_key=" + opaque + " suffix",
            "prefix http://[::1]/callback?refresh_token=" + opaque + " suffix",
        )
        for value in values:
            with self.subTest(value=value):
                redacted = client.redact_text(value)
                self.assertNotIn(opaque, redacted)
                self.assertIn("redacted", redacted.lower())

    def test_embedded_auth_and_credential_assignments_are_redacted(self) -> None:
        opaque = "opaque-" + "EXAMPLEVALUE" * 2
        values = (
            "debug Authorization: Bearer " + opaque,
            "debug Basic " + opaque,
            "api_key=" + opaque,
            "access_token: " + opaque,
            "mcp-session-id=" + opaque,
            "password='" + opaque + "'",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertNotIn(opaque, client.redact_text(value))

    def test_current_auth_is_removed_from_embedded_response_text(self) -> None:
        token = "token-" + "EXAMPLEPLACEHOLDER" * 2
        auth = "Bearer " + token
        payload = {"result": {"message": f"prefix {auth} middle {token} suffix"}}

        result = client.redact(payload, client.authentication_secrets(auth))
        serialized = json.dumps(result)

        self.assertNotIn(auth, serialized)
        self.assertNotIn(token, serialized)

    def test_current_auth_is_removed_from_object_keys(self) -> None:
        token = "opaque-" + "EXAMPLEPLACEHOLDER" * 2
        auth = "Bearer " + token
        payload = {token: "bare key", auth: "authorization key"}

        serialized = json.dumps(client.redact(payload, client.authentication_secrets(auth)))

        self.assertNotIn(auth, serialized)
        self.assertNotIn(token, serialized)

    def test_authorization_is_normalized_and_control_characters_are_rejected(self) -> None:
        self.assertEqual(client.normalize_authorization("example-token"), "Bearer example-token")
        self.assertEqual(client.normalize_authorization("bearer example-token"), "Bearer example-token")
        with self.assertRaises(ValueError):
            client.normalize_authorization("Basic example-token")
        with self.assertRaises(ValueError):
            client.normalize_authorization("example\ntoken")


class TransportSafetyTests(unittest.TestCase):
    def test_direct_opener_disables_environment_proxies(self) -> None:
        with mock.patch.dict(os.environ, {"HTTP_PROXY": "http://192.0.2.10:8080"}, clear=False):
            opener = client.build_direct_opener()
        proxy_handlers = [handler for handler in opener.handlers if isinstance(handler, client.urllib.request.ProxyHandler)]
        self.assertEqual(proxy_handlers, [])

    def test_endpoint_url_policy(self) -> None:
        secure = "https://example.invalid/mcp"
        loopback = "http://127.0.0.1:8080/mcp"
        ipv6_loopback = "http://[::1]:8080/mcp"
        non_loopback = "http://192.0.2.10/mcp"
        self.assertEqual(client.validate_endpoint_url(secure), secure)
        self.assertEqual(client.validate_endpoint_url(loopback), loopback)
        self.assertEqual(client.validate_endpoint_url(ipv6_loopback), ipv6_loopback)
        with self.assertRaisesRegex(ValueError, "allow-insecure-http"):
            client.validate_endpoint_url(non_loopback)
        self.assertEqual(client.validate_endpoint_url(non_loopback, True), non_loopback)

        invalid = (
            "https://user:pass@example.invalid/mcp",
            "https://example.invalid/mcp?token=value",
            "https://example.invalid/mcp#fragment",
            "https://example.invalid" + "\\mcp",
            "ftp://example.invalid/mcp",
            "/mcp",
            "http://" + "localhost" + ".evil/mcp",
            "https://example.invalid:0/mcp",
            "https://example.invalid:65536/mcp",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                client.validate_endpoint_url(value)

    def test_redirect_is_not_followed_and_auth_never_reaches_sink(self) -> None:
        RedirectSinkHandler.authorizations = []
        RedirectSourceHandler.authorizations = []
        sink = ThreadingHTTPServer(("127.0.0.1", 0), RedirectSinkHandler)
        source = ThreadingHTTPServer(("127.0.0.1", 0), RedirectSourceHandler)
        RedirectSourceHandler.location = f"http://127.0.0.1:{sink.server_address[1]}/sink"
        threads = [
            threading.Thread(target=sink.serve_forever, daemon=True),
            threading.Thread(target=source.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            url = f"http://127.0.0.1:{source.server_address[1]}/mcp"
            for status in (301, 302, 303, 307, 308):
                with self.subTest(status=status):
                    RedirectSourceHandler.status = status
                    with self.assertRaises(client.McpHttpError) as raised:
                        client.rpc(url, "Bearer example-auth", "initialize", {})
                    self.assertEqual(raised.exception.status, status)
                    self.assertNotIn(RedirectSourceHandler.location, str(raised.exception))
            self.assertEqual(RedirectSinkHandler.authorizations, [])
            self.assertEqual(RedirectSourceHandler.authorizations, ["Bearer example-auth"] * 5)
        finally:
            source.shutdown()
            sink.shutdown()
            source.server_close()
            sink.server_close()
            for thread in threads:
                thread.join(timeout=2)

    def test_full_lifecycle_carries_protocol_and_session_headers(self) -> None:
        reset_lifecycle_handler()
        server = ThreadingHTTPServer(("127.0.0.1", 0), LifecycleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
            result, session_id = client.run_mcp_operation(
                url,
                "Bearer example-auth",
                "tools/call",
                {"name": "example-tool", "arguments": {}},
            )
            self.assertEqual(result["result"], {"ok": True})
            self.assertEqual(session_id, LifecycleHandler.session_id)
            self.assertEqual(
                [call["payload"]["method"] for call in LifecycleHandler.calls],
                ["initialize", "notifications/initialized", "tools/call"],
            )
            first, initialized, tool = LifecycleHandler.calls
            self.assertIsNone(first["protocol"])
            self.assertIsNone(first["session"])
            for call in (initialized, tool):
                self.assertEqual(call["protocol"], client.DEFAULT_PROTOCOL_VERSION)
                self.assertEqual(call["session"], LifecycleHandler.session_id)
                self.assertEqual(call["authorization"], "Bearer example-auth")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_lifecycle_failures_stop_before_tool_call(self) -> None:
        reset_lifecycle_handler()
        server = ThreadingHTTPServer(("127.0.0.1", 0), LifecycleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
        try:
            cases = [
                ("missing capability", {"capabilities": {}}, "advertise the tools capability"),
                ("malformed capabilities", {"capabilities": None}, "declare capabilities"),
                ("missing server info", {"server_info": None}, "declare serverInfo"),
                (
                    "empty server name",
                    {"server_info": {"name": "", "version": "1.0"}},
                    "serverInfo.name",
                ),
                ("protocol mismatch", {"negotiated_protocol": "2025-03-26"}, "unsupported protocol"),
                ("wrong MIME", {"initialize_content_type": "text/plain"}, "application/json"),
                ("SSE", {"initialize_content_type": "text/event-stream"}, "SSE responses"),
            ]
            for label, changes, expected in cases:
                with self.subTest(label=label):
                    reset_lifecycle_handler()
                    for name, value in changes.items():
                        setattr(LifecycleHandler, name, value)
                    with self.assertRaisesRegex(ValueError, expected):
                        client.run_mcp_operation(url, "Bearer example-auth", "tools/call", {})
                    self.assertEqual(
                        [call["payload"]["method"] for call in LifecycleHandler.calls],
                        ["initialize"],
                    )

            reset_lifecycle_handler()
            LifecycleHandler.notification_status = 200
            with self.assertRaisesRegex(ValueError, "HTTP 202 or 204"):
                client.run_mcp_operation(url, "Bearer example-auth", "tools/call", {})
            self.assertEqual(
                [call["payload"]["method"] for call in LifecycleHandler.calls],
                ["initialize", "notifications/initialized"],
            )

            reset_lifecycle_handler()
            LifecycleHandler.initialize_error = {"code": -32000, "message": "example error"}
            result, _ = client.run_mcp_operation(url, "Bearer example-auth", "tools/call", {})
            self.assertIn("error", result)
            self.assertEqual(
                [call["payload"]["method"] for call in LifecycleHandler.calls],
                ["initialize"],
            )

            reset_lifecycle_handler()
            with mock.patch.object(client, "MAX_RESPONSE_BYTES", 16):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    client.run_mcp_operation(url, "Bearer example-auth", "tools/call", {})
            self.assertEqual(
                [call["payload"]["method"] for call in LifecycleHandler.calls],
                ["initialize"],
            )

            reset_lifecycle_handler()
            with self.assertRaisesRegex(ValueError, "supports only"):
                client.run_mcp_operation(url, "Bearer example-auth", "logging/setLevel", {})
            self.assertEqual(LifecycleHandler.calls, [])
        finally:
            reset_lifecycle_handler()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_standard_202_initialized_response_is_accepted(self) -> None:
        reset_lifecycle_handler()
        LifecycleHandler.notification_status = 202
        server = ThreadingHTTPServer(("127.0.0.1", 0), LifecycleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
            result, _ = client.run_mcp_operation(url, "Bearer example-auth", "tools/call", {})
            self.assertEqual(result["result"], {"ok": True})
        finally:
            reset_lifecycle_handler()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_cli_scrubs_auth_echo_from_stdout_and_private_output(self) -> None:
        reset_lifecycle_handler()
        LifecycleHandler.echo_authorization = True
        server = ThreadingHTTPServer(("127.0.0.1", 0), LifecycleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        token = "opaque-" + "EXAMPLEPLACEHOLDER" * 2
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "result.json"
                url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
                stdout = io.StringIO()
                stderr = io.StringIO()
                argv = ["tavo_mcp_client.py", "--tool", "example-tool", "--output", str(output)]
                with (
                    mock.patch.object(sys, "argv", argv),
                    mock.patch.dict(
                        os.environ,
                        {"TAVO_MCP_URL": url, "TAVO_MCP_AUTH": token},
                        clear=False,
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    result = client.main()
                self.assertEqual(result, 0)
                self.assertNotIn(token, stdout.getvalue())
                self.assertNotIn(token, stderr.getvalue())
                self.assertNotIn(token, output.read_text(encoding="utf-8"))
                self.assertNotIn(LifecycleHandler.session_id, stdout.getvalue())
                self.assertNotIn(LifecycleHandler.session_id, output.read_text(encoding="utf-8"))
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        finally:
            reset_lifecycle_handler()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_invalid_cli_does_not_echo_unknown_argument_value(self) -> None:
        token = "opaque-" + "EXAMPLEPLACEHOLDER" * 2
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["tavo_mcp_client.py", "--auth", token]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = client.main()
        self.assertEqual(result, 1)
        self.assertNotIn(token, stdout.getvalue())
        self.assertNotIn(token, stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_malformed_http_response_fails_without_traceback_or_secret_echo(self) -> None:
        server = socketserver.TCPServer(("127.0.0.1", 0), MalformedHttpHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        token = "opaque-" + "EXAMPLEPLACEHOLDER" * 2
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(sys, "argv", ["tavo_mcp_client.py"]),
                mock.patch.dict(
                    os.environ,
                    {"TAVO_MCP_URL": url, "TAVO_MCP_AUTH": token},
                    clear=False,
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = client.main()
            self.assertEqual(result, 1)
            self.assertNotIn(token, stdout.getvalue())
            self.assertNotIn(token, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_deep_json_fails_without_traceback_or_secret_echo(self) -> None:
        reset_lifecycle_handler()
        LifecycleHandler.tool_nested_depth = client.MAX_JSON_DEPTH + 2
        server = ThreadingHTTPServer(("127.0.0.1", 0), LifecycleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        token = "opaque-" + "EXAMPLEPLACEHOLDER" * 2
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
            stdout = io.StringIO()
            stderr = io.StringIO()
            argv = ["tavo_mcp_client.py", "--tool", "example-tool"]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(
                    os.environ,
                    {"TAVO_MCP_URL": url, "TAVO_MCP_AUTH": token},
                    clear=False,
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = client.main()
            self.assertEqual(result, 1)
            self.assertNotIn(token, stdout.getvalue())
            self.assertNotIn(token, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
        finally:
            reset_lifecycle_handler()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class ProtocolTests(unittest.TestCase):
    def test_default_protocol_matches_tavo_1_2_1(self) -> None:
        self.assertEqual(client.DEFAULT_PROTOCOL_VERSION, "2025-06-18")

    def test_negotiated_protocol_is_checked(self) -> None:
        matching = {"result": {"protocolVersion": client.DEFAULT_PROTOCOL_VERSION}}
        different = {"result": {"protocolVersion": "2025-03-26"}}
        self.assertEqual(
            client.validate_negotiated_protocol(matching, client.DEFAULT_PROTOCOL_VERSION),
            client.DEFAULT_PROTOCOL_VERSION,
        )
        with self.assertRaisesRegex(ValueError, "unsupported protocol"):
            client.validate_negotiated_protocol(different, client.DEFAULT_PROTOCOL_VERSION)

    def test_header_values_are_visible_ascii_only(self) -> None:
        self.assertEqual(client.validate_header_value("example-session", "session"), "example-session")
        for value in ("", "unicode-会话", "contains space"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                client.validate_header_value(value, "session")

    def test_jsonrpc_response_shape_is_checked(self) -> None:
        valid = {"jsonrpc": "2.0", "id": 1, "result": {}}
        client.validate_jsonrpc_response(valid, 1)
        invalid = (
            {"jsonrpc": "1.0", "id": 1, "result": {}},
            {"jsonrpc": "2.0", "id": True, "result": {}},
            {"jsonrpc": "2.0", "id": 2, "result": {}},
            {"jsonrpc": "2.0", "id": 1},
            {"jsonrpc": "2.0", "id": 1, "result": {}, "error": {}},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                client.validate_jsonrpc_response(value, 1)

    def test_non_finite_numbers_and_excessive_depth_are_rejected(self) -> None:
        for literal in ("NaN", "Infinity", "-Infinity", "1e999"):
            body = ('{"jsonrpc":"2.0","id":1,"result":{"value":' + literal + "}}").encode()
            with self.subTest(literal=literal), self.assertRaises(ValueError):
                client.decode_mcp_json(body)

        duplicate = b'{"jsonrpc":"2.0","id":1,"id":1,"result":{}}'
        with self.assertRaisesRegex(ValueError, "duplicate"):
            client.decode_mcp_json(duplicate)

        nested: object = "leaf"
        for _ in range(client.MAX_JSON_DEPTH + 2):
            nested = [nested]
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": nested}).encode()
        with self.assertRaisesRegex(ValueError, "nesting"):
            client.decode_mcp_json(body)


class PrivateFileTests(unittest.TestCase):
    def test_endpoint_file_requires_private_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint = root / "endpoint.json"
            endpoint.write_text(
                json.dumps({"url": "https://example.invalid/rpc", "authorization": "Bearer example"}),
                encoding="utf-8",
            )
            endpoint.chmod(0o600)
            self.assertEqual(client.load_endpoint(str(endpoint))["url"], "https://example.invalid/rpc")

            endpoint.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "mode 0600"):
                client.load_endpoint(str(endpoint))

    def test_endpoint_file_is_an_indivisible_connection_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / "endpoint.json"
            endpoint.write_text(
                json.dumps({"url": "https://example.invalid/file", "authorization": "Bearer EXAMPLE_FILE_TOKEN"}),
                encoding="utf-8",
            )
            endpoint.chmod(0o600)
            selected = client.select_connection(
                str(endpoint),
                "https://example.invalid/environment",
                "Bearer EXAMPLE_ENVIRONMENT_TOKEN",
            )
            self.assertEqual(selected, ("https://example.invalid/file", "Bearer EXAMPLE_FILE_TOKEN"))

    def test_environment_connection_requires_url_and_auth_together(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be set together"):
            client.select_connection("", "https://example.invalid/mcp", "")
        with self.assertRaisesRegex(ValueError, "must be set together"):
            client.select_connection("", "", "Bearer EXAMPLE_ENVIRONMENT_TOKEN")

    def test_output_cannot_overwrite_endpoint_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / "endpoint.json"
            endpoint.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot overwrite"):
                client.reject_output_input_collision(str(endpoint), str(endpoint))

            hardlink = Path(directory) / "endpoint-hardlink.json"
            os.link(endpoint, hardlink)
            with self.assertRaisesRegex(ValueError, "cannot overwrite"):
                client.reject_output_input_collision(str(endpoint), str(hardlink))

            case_alias = Path(directory) / "ENDPOINT.JSON"
            if case_alias.exists():
                with self.assertRaisesRegex(ValueError, "cannot overwrite"):
                    client.reject_output_input_collision(str(endpoint), str(case_alias))

    def test_endpoint_file_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            target.chmod(0o600)
            link = root / "endpoint.json"
            link.symlink_to(target)

            with self.assertRaisesRegex(ValueError, "symlink"):
                client.load_endpoint(str(link))

    def test_atomic_output_is_private_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "result.json"
            client.atomic_private_text(output, "{}\n")
            self.assertEqual(output.read_text(encoding="utf-8"), "{}\n")
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

            target = root / "target.json"
            target.write_text("unchanged", encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                client.atomic_private_text(link, "replacement")
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
