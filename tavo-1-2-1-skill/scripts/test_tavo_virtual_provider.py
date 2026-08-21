#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import wave
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import tavo_virtual_provider as provider  # noqa: E402


CLIENT_KEY = "tavo-fixture-client-secret"


class VirtualProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        config = provider.VirtualProviderConfig(
            capture_dir=self.root / "captures",
            client_key=CLIENT_KEY,
            model="tavo-virtual-test",
            allowed_clients=provider.validate_allowed_clients(["127.0.0.1"]),
            slow_seconds=0.05,
            timeout_seconds=0.12,
            oversized_response_bytes=4096,
        )
        self.server = provider.VirtualProviderServer(("127.0.0.1", 0), config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(
        self,
        path: str,
        payload: dict | bytes | None = None,
        *,
        key: str = CLIENT_KEY,
        content_type: str = "application/json",
        extra_headers: dict[str, str] | None = None,
        timeout: float = 3,
    ):
        headers = {"Authorization": f"Bearer {key}"}
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if isinstance(payload, dict):
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = content_type
        elif isinstance(payload, bytes):
            data = payload
            headers["Content-Type"] = content_type
        return urllib.request.urlopen(
            urllib.request.Request(self.base + path, data=data, headers=headers),
            timeout=timeout,
        )

    def captures(self) -> list[dict]:
        capture_dir = self.root / "captures"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(capture_dir.glob("*.json"))
        ]

    def test_health_models_bearer_allowlist_and_private_capture_permissions(self) -> None:
        with urllib.request.urlopen(self.base + "/health", timeout=3) as response:
            health = json.load(response)
        self.assertTrue(health["ok"])
        self.assertEqual(health["providerMode"], "virtual")
        self.assertEqual(health["realModelRequestsSent"], 0)

        with self.request("/v1/models") as response:
            models = json.load(response)
        self.assertEqual(models["data"][0]["id"], "tavo-virtual-test")

        with self.assertRaises(urllib.error.HTTPError) as unauthorized:
            self.request("/v1/models", key="wrong")
        self.assertEqual(unauthorized.exception.code, 401)
        unauthorized.exception.close()

        anthropic_request = urllib.request.Request(
            self.base + "/v1/messages",
            data=json.dumps(
                {
                    "model": "claude-fable-5",
                    "max_tokens": 32,
                    "messages": [{"role": "user", "content": "anthropic auth check"}],
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLIENT_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(anthropic_request, timeout=3) as response:
            anthropic_body = json.load(response)
        self.assertEqual(anthropic_body["type"], "message")
        anthropic_capture = self.captures()[0]
        self.assertEqual(
            anthropic_capture["request"]["headers"]["X-Api-Key"],
            "<redacted>",
        )

        denied = provider.VirtualProviderServer(
            ("127.0.0.1", 0),
            provider.VirtualProviderConfig(
                capture_dir=self.root / "denied",
                client_key=CLIENT_KEY,
                allowed_clients=provider.validate_allowed_clients(["192.0.2.0/24"]),
            ),
        )
        denied_thread = threading.Thread(target=denied.serve_forever, daemon=True)
        denied_thread.start()
        try:
            url = f"http://127.0.0.1:{denied.server_address[1]}/health"
            with self.assertRaises(urllib.error.HTTPError) as denied_error:
                urllib.request.urlopen(url, timeout=3)
            self.assertEqual(denied_error.exception.code, 403)
            denied_error.exception.close()
        finally:
            denied.shutdown()
            denied.server_close()
            denied_thread.join(timeout=2)

        payload = {
            "model": "alias",
            "messages": [{"role": "user", "content": "permission check"}],
        }
        with self.request("/v1/chat/completions", payload):
            pass
        capture_dir = self.root / "captures"
        self.assertEqual(stat.S_IMODE(capture_dir.stat().st_mode), 0o700)
        capture_path = next(capture_dir.glob("*.json"))
        self.assertEqual(stat.S_IMODE(capture_path.stat().st_mode), 0o600)

    def test_chat_json_openrouter_audio_capture_is_correlated_and_redacted(self) -> None:
        audio = b"not-real-audio-but-deterministic"
        audio_b64 = base64.b64encode(audio).decode("ascii")
        # Construct the fake credential marker at runtime so repository secret
        # scanners do not mistake the test fixture for a real static key.
        secret = "sk-" + "fixture" + "0123456789abcdefghijkl"
        payload = {
            "model": "openrouter/fixture",
            "fixtureNonce": "case.audio-1",
            "fixtureIntent": "openrouter-asr",
            "stream": False,
            "api_key": "body-secret",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"transcribe {secret}"},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_b64, "format": "wav"},
                        },
                    ],
                }
            ],
        }
        with self.request("/v1/chat/completions", payload) as response:
            body = json.load(response)
        self.assertTrue(
            body["choices"][0]["message"]["content"].startswith("TAVO_VIRTUAL_ASR_OK::")
        )

        capture = self.captures()[0]
        self.assertEqual(capture["provider"], "tavo-virtual")
        self.assertEqual(capture["protocol"], "openrouter-audio-chat")
        self.assertEqual(capture["nonce"], "case.audio-1")
        self.assertEqual(capture["intent"], "openrouter-asr")
        self.assertEqual(capture["request"]["headers"]["Authorization"], "<redacted>")
        projected_audio = capture["request"]["body"]["messages"][0]["content"][1][
            "input_audio"
        ]["data"]["_fixtureMedia"]
        self.assertEqual(projected_audio["sha256"], hashlib.sha256(audio).hexdigest())
        self.assertEqual(projected_audio["sizeBytes"], len(audio))
        serialized = json.dumps(capture)
        self.assertNotIn(audio_b64, serialized)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("body-secret", serialized)
        self.assertNotIn(CLIENT_KEY, serialized)

    def test_chat_and_responses_sse_include_terminal_events_and_slow_window(self) -> None:
        start = time.monotonic()
        chat_payload = {
            "model": "x",
            "stream": True,
            "fixtureScenario": "slow_stream_before_first",
            "fixtureNonce": "chat-stream",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/v1/chat/completions", chat_payload) as response:
            chat_text = response.read().decode("utf-8")
        self.assertGreaterEqual(time.monotonic() - start, 0.035)
        self.assertIn("chat.completion.chunk", chat_text)
        self.assertIn("data: [DONE]", chat_text)

        responses_payload = {
            "model": "x",
            "stream": True,
            "fixtureNonce": "responses-stream",
            "input": "hello",
        }
        with self.request("/v1/responses", responses_payload) as response:
            responses_text = response.read().decode("utf-8")
        self.assertIn("event: response.created", responses_text)
        self.assertIn("event: response.output_text.delta", responses_text)
        self.assertIn("event: response.completed", responses_text)

        captures = self.captures()
        self.assertEqual(captures[0]["response"]["format"], "sse")
        self.assertTrue(captures[0]["response"]["completed"])
        self.assertTrue(captures[0]["response"]["doneSent"])
        self.assertTrue(captures[0]["response"]["terminalSent"])
        self.assertEqual(captures[1]["response"]["terminalEvent"], "response.completed")
        self.assertTrue(captures[1]["response"]["terminalSent"])

    def test_completions_responses_and_messages_json_protocol_shapes(self) -> None:
        cases = [
            (
                "/v1/completions",
                {"model": "x", "prompt": "hello", "fixtureNonce": "completion"},
                lambda body: body["choices"][0]["text"],
                "completions",
            ),
            (
                "/responses",
                {"model": "x", "input": "hello", "fixtureNonce": "responses"},
                lambda body: body["output"][0]["content"][0]["text"],
                "responses",
            ),
            (
                "/v1/messages",
                {
                    "model": "x",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hello"}],
                    "fixtureNonce": "messages",
                },
                lambda body: body["content"][0]["text"],
                "messages",
            ),
        ]
        for path, payload, text_getter, _protocol in cases:
            with self.subTest(path=path):
                with self.request(path, payload) as response:
                    body = json.load(response)
                self.assertTrue(text_getter(body).startswith("TAVO_VIRTUAL_OK::"))
        self.assertEqual(
            [item["protocol"] for item in self.captures()],
            [case[3] for case in cases],
        )

    def test_completions_and_messages_sse_protocol_shapes(self) -> None:
        completion_payload = {
            "model": "x",
            "stream": True,
            "fixtureNonce": "completions-sse",
            "prompt": "hello",
        }
        with self.request("/completions", completion_payload) as response:
            completion_text = response.read().decode("utf-8")
        self.assertIn("text_completion", completion_text)
        self.assertIn("data: [DONE]", completion_text)

        payload = {
            "model": "x",
            "stream": True,
            "fixtureNonce": "messages-sse",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/messages", payload) as response:
            text = response.read().decode("utf-8")
        self.assertIn("event: message_start", text)
        self.assertIn("event: content_block_delta", text)
        self.assertIn("event: message_stop", text)
        captures = self.captures()
        self.assertEqual(
            [item["protocol"] for item in captures],
            ["completions", "messages"],
        )
        self.assertTrue(captures[0]["response"]["doneSent"])
        self.assertTrue(captures[1]["response"]["terminalSent"])

    def test_image_b64_url_and_asset_roundtrip(self) -> None:
        b64_payload = {
            "model": "image-fixture",
            "prompt": "one dot",
            "response_format": "b64_json",
            "fixtureNonce": "image-b64",
        }
        with self.request("/v1/images/generations", b64_payload) as response:
            b64_body = json.load(response)
        self.assertEqual(
            base64.b64decode(b64_body["data"][0]["b64_json"]),
            provider.PNG_BYTES,
        )

        url_payload = {
            "model": "image-fixture",
            "prompt": "one dot",
            "response_format": "url",
            "fixtureNonce": "image-url",
        }
        with self.request("/images/generations", url_payload) as response:
            url = json.load(response)["data"][0]["url"]
        with urllib.request.urlopen(url, timeout=3) as response:
            self.assertEqual(response.headers.get_content_type(), "image/png")
            self.assertEqual(response.read(), provider.PNG_BYTES)

        captures = self.captures()
        self.assertEqual(
            [item["protocol"] for item in captures],
            ["images", "images", "image-asset"],
        )
        self.assertEqual(captures[1]["nonce"], "image-url")
        self.assertEqual(captures[2]["nonce"], "image-url")
        self.assertEqual(
            captures[2]["response"]["media"]["sha256"],
            hashlib.sha256(provider.PNG_BYTES).hexdigest(),
        )

    def test_tts_returns_valid_wav_and_captures_parameters(self) -> None:
        payload = {
            "model": "tts-fixture",
            "input": "hello",
            "voice": "fixture",
            "speed": 1.15,
            "response_format": "wav",
            "fixtureNonce": "tts-1",
            "fixtureIntent": "voice-playback",
        }
        with self.request("/v1/audio/speech", payload) as response:
            self.assertEqual(response.headers.get_content_type(), "audio/wav")
            wav_bytes = response.read()
        with wave.open(io.BytesIO(wav_bytes), "rb") as parsed:
            self.assertEqual(parsed.getnchannels(), 1)
            self.assertEqual(parsed.getframerate(), 16000)
            self.assertGreater(parsed.getnframes(), 0)
        capture = self.captures()[0]
        self.assertEqual(capture["protocol"], "tts")
        self.assertEqual(capture["intent"], "voice-playback")
        self.assertEqual(capture["request"]["body"]["voice"], "fixture")
        self.assertEqual(
            capture["response"]["media"]["sha256"],
            hashlib.sha256(wav_bytes).hexdigest(),
        )

    @staticmethod
    def multipart_body(
        fields: dict[str, str],
        *,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> tuple[bytes, str]:
        boundary = "TavoFixtureBoundary7MA4YWxk"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    (
                        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    ).encode(),
                    value.encode(),
                    b"\r\n",
                ]
            )
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    'Content-Disposition: form-data; name="file"; '
                    f'filename="{filename}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                file_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    def test_multipart_asr_hashes_audio_and_preserves_parameters(self) -> None:
        audio = provider.WAV_BYTES
        raw, content_type = self.multipart_body(
            {
                "model": "whisper-fixture",
                "language": "zh",
                "prompt": "names",
                "response_format": "verbose_json",
                "temperature": "0.2",
                "fixtureNonce": "asr-1",
                "fixtureIntent": "long-press-asr",
            },
            filename="sample.wav",
            content_type="audio/wav",
            file_bytes=audio,
        )
        with self.request(
            "/v1/audio/transcriptions",
            raw,
            content_type=content_type,
        ) as response:
            body = json.load(response)
        self.assertTrue(body["text"].startswith("TAVO_VIRTUAL_TRANSCRIPT::"))
        self.assertEqual(body["language"], "zh")

        capture = self.captures()[0]
        self.assertEqual(capture["protocol"], "asr")
        self.assertEqual(capture["nonce"], "asr-1")
        fields = capture["request"]["body"]["fields"]
        self.assertEqual(fields["temperature"], "0.2")
        media = fields["file"]["_fixtureMedia"]
        self.assertEqual(media["sha256"], hashlib.sha256(audio).hexdigest())
        self.assertEqual(media["sizeBytes"], len(audio))
        serialized = json.dumps(capture)
        self.assertNotIn(base64.b64encode(audio).decode("ascii"), serialized)

    def test_http_malformed_abrupt_and_unknown_501_are_captured(self) -> None:
        for scenario, status in (("http429", 429), ("http500", 500)):
            with self.subTest(scenario=scenario):
                payload = {
                    "model": "x",
                    "fixtureScenario": scenario,
                    "fixtureNonce": scenario,
                    "messages": [{"role": "user", "content": "hello"}],
                }
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.request("/v1/chat/completions", payload)
                self.assertEqual(caught.exception.code, status)
                caught.exception.close()

        malformed = {
            "model": "x",
            "fixtureScenario": "malformed",
            "fixtureNonce": "malformed",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/v1/chat/completions", malformed) as response:
            self.assertEqual(response.read(), b'{"fixtureMalformed":')

        abrupt = {
            "model": "x",
            "stream": True,
            "fixtureScenario": "abrupt_eof",
            "fixtureNonce": "abrupt",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/v1/chat/completions", abrupt) as response:
            stream = response.read().decode("utf-8")
        self.assertNotIn("[DONE]", stream)

        with self.assertRaises(urllib.error.HTTPError) as unknown:
            self.request(
                "/v1/embeddings",
                {"model": "x", "fixtureNonce": "unknown-route", "input": "hello"},
            )
        self.assertEqual(unknown.exception.code, 501)
        unknown_body = json.load(unknown.exception)
        unknown.exception.close()
        self.assertEqual(unknown_body["error"]["code"], "fixture_not_implemented")

        captures = self.captures()
        self.assertEqual([item["response"]["status"] for item in captures[:2]], [429, 500])
        self.assertEqual(captures[2]["response"]["format"], "malformed-json")
        self.assertFalse(captures[3]["response"]["completed"])
        self.assertFalse(captures[3]["response"]["doneSent"])
        self.assertEqual(captures[4]["protocol"], "unknown")
        self.assertEqual(captures[4]["response"]["status"], 501)

        with self.assertRaises(urllib.error.HTTPError) as unknown_get:
            self.request("/v1/unknown-get")
        self.assertEqual(unknown_get.exception.code, 501)
        unknown_get.exception.close()
        get_capture = self.captures()[5]
        self.assertEqual(get_capture["method"], "GET")
        self.assertEqual(get_capture["protocol"], "unknown")
        self.assertEqual(get_capture["response"]["status"], 501)

    def test_no_done_timeout_empty_and_oversized_protocol_faults(self) -> None:
        no_done = {
            "model": "x",
            "stream": True,
            "fixtureScenario": "no_done",
            "fixtureNonce": "no-done",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/v1/chat/completions", no_done) as response:
            no_done_text = response.read().decode("utf-8")
        self.assertIn("chat.completion.chunk", no_done_text)
        self.assertNotIn("[DONE]", no_done_text)

        empty = {
            "model": "x",
            "fixtureScenario": "empty",
            "fixtureNonce": "empty",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/v1/chat/completions", empty) as response:
            self.assertEqual(response.read(), b"")

        oversized = {
            "model": "x",
            "fixtureScenario": "oversized",
            "fixtureNonce": "oversized",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.request("/v1/chat/completions", oversized) as response:
            oversized_body = response.read()
        self.assertGreater(len(oversized_body), 4096)

        timeout_payload = {
            "model": "x",
            "fixtureScenario": "timeout",
            "fixtureNonce": "timeout",
            "messages": [{"role": "user", "content": "hello"}],
        }
        with self.assertRaises((TimeoutError, socket.timeout)):
            self.request("/v1/chat/completions", timeout_payload, timeout=0.02)
        time.sleep(0.16)

        captures = self.captures()
        by_nonce = {item["nonce"]: item for item in captures}
        self.assertTrue(by_nonce["no-done"]["response"]["completed"])
        self.assertFalse(by_nonce["no-done"]["response"]["doneSent"])
        self.assertFalse(by_nonce["no-done"]["response"]["terminalSent"])
        self.assertEqual(by_nonce["empty"]["response"]["format"], "empty")
        self.assertEqual(by_nonce["empty"]["response"]["bodyBytes"], 0)
        self.assertEqual(by_nonce["oversized"]["response"]["format"], "oversized-json")
        self.assertGreater(by_nonce["oversized"]["response"]["bodyBytes"], 4096)
        self.assertEqual(by_nonce["timeout"]["response"]["timeoutSeconds"], 0.12)

    def test_invalid_json_is_hash_captured_without_raw_body(self) -> None:
        raw = b'{"api_key":"fake","broken":'
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/v1/chat/completions", raw)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        capture = self.captures()[0]
        self.assertEqual(capture["scenario"], "invalid-request")
        self.assertEqual(
            capture["request"]["body"]["_fixtureRaw"]["sha256"],
            hashlib.sha256(raw).hexdigest(),
        )
        self.assertNotIn('"fake"', json.dumps(capture))

    def test_secret_file_and_non_loopback_configuration_guards(self) -> None:
        secret = self.root / "secret"
        secret.write_text("private-value\n", encoding="utf-8")
        secret.chmod(0o600)
        self.assertEqual(provider.read_secret_file(secret), "private-value")
        secret.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "group/other"):
            provider.read_secret_file(secret)

        args = type(
            "Args",
            (),
            {
                "port": 0,
                "slow_seconds": 0.1,
                "allowed_client": [],
                "bind": "0.0.0.0",
                "capture_dir": self.root / "cli-captures",
                "client_key_file": secret,
                "delete_client_key_file": False,
                "model": "fixture",
                "asset_base_url": None,
                "timeout_seconds": 0.5,
                "oversized_response_bytes": 2048,
            },
        )()
        secret.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "Non-loopback"):
            provider.build_config(args)
        self.assertEqual(
            str(provider.validate_allowed_clients(["192.0.2.0/24"])[0]),
            "192.0.2.0/24",
        )


if __name__ == "__main__":
    unittest.main()
