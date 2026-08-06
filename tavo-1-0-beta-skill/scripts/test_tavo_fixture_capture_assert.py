#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import tavo_fixture_capture_assert as capture_assert  # noqa: E402


def make_capture(
    request_id: str,
    *,
    nonce: str,
    intent: str,
    path: str = "/v1/chat/completions",
    body: dict | None = None,
    completed: bool = True,
    disconnected: bool = False,
) -> dict:
    return {
        "schemaVersion": 1,
        "provider": "tavo-virtual",
        "requestId": request_id,
        "nonce": nonce,
        "intent": intent,
        "method": "POST",
        "path": path,
        "protocol": "chat-completions",
        "scenario": "normal",
        "request": {
            "headers": {
                "Authorization": "<redacted>",
                "Content-Type": "application/json",
            },
            "body": body
            or {
                "model": "fixture",
                "messages": [
                    {"role": "system", "content": "ALPHA"},
                    {"role": "user", "content": "BETA"},
                ],
            },
        },
        "response": {
            "status": 200,
            "format": "json",
            "completed": completed,
            "clientDisconnected": disconnected,
        },
    }


class CaptureAssertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_passes_pointer_subset_order_and_provenance_assertions(self) -> None:
        captures = [make_capture("req-1", nonce="case-1", intent="prompt-assembly")]
        spec = {
            "schemaVersion": 1,
            "providerMode": "virtual",
            "realModelRequestsSent": 0,
            "countsTowardKpi": False,
            "rejectUnexpected": True,
            "expectations": [
                {
                    "id": "assembled-request",
                    "nonce": "case-1",
                    "intent": "prompt-assembly",
                    "path": "/v1/chat/completions",
                    "expectedRequestCount": 1,
                    "retryCount": 0,
                    "clientDisconnectCount": 0,
                    "completedCount": 1,
                    "requestPointers": {
                        "/body/model": "fixture",
                        "/body/messages/0/role": "system",
                    },
                    "requestBodySubset": {
                        "messages": [
                            {"role": "system", "content": "ALPHA"},
                            {"role": "user", "content": "BETA"},
                        ]
                    },
                    "bodyContains": ["ALPHA", "BETA"],
                    "bodyNotContains": ["FORBIDDEN"],
                    "orderedBodyText": ["ALPHA", "BETA"],
                    "responseStatus": 200,
                    "responseCompleted": True,
                    "responsePointers": {"/format": "json"},
                    "capturePointers": {"/provider": "tavo-virtual"},
                }
            ],
        }
        report = capture_assert.evaluate_expectations(captures, spec)
        self.assertTrue(report["ok"])
        self.assertEqual(report["providerMode"], "virtual")
        self.assertEqual(report["realModelRequestsSent"], 0)
        self.assertFalse(report["countsTowardKpi"])
        self.assertEqual(report["results"][0]["retryCount"], 0)
        self.assertEqual(report["failures"], [])

    def test_per_intent_request_retry_disconnect_and_completion_counts(self) -> None:
        captures = [
            make_capture(
                "req-first",
                nonce="retry-case",
                intent="generation-retry",
                completed=False,
                disconnected=True,
            ),
            make_capture(
                "req-retry",
                nonce="retry-case",
                intent="generation-retry",
                completed=True,
                disconnected=False,
            ),
        ]
        spec = {
            "expectations": [
                {
                    "id": "retry-lifecycle",
                    "nonce": "retry-case",
                    "intent": "generation-retry",
                    "expectedRequestCount": 2,
                    "retryCount": 1,
                    "clientDisconnectCount": 1,
                    "completedCount": 1,
                }
            ]
        }
        report = capture_assert.evaluate_expectations(captures, spec)
        self.assertTrue(report["ok"])
        result = report["results"][0]
        self.assertEqual(result["actualCount"], 2)
        self.assertEqual(result["retryCount"], 1)
        self.assertEqual(result["clientDisconnectCount"], 1)
        self.assertEqual(result["completedCount"], 1)

        bad_spec = json.loads(json.dumps(spec))
        bad_spec["expectations"][0]["retryCount"] = 0
        failed = capture_assert.evaluate_expectations(captures, bad_spec)
        self.assertFalse(failed["ok"])
        self.assertIn("expected retryCount=0, got 1", "\n".join(failed["failures"]))

    def test_reports_marker_pointer_order_status_and_unexpected_failures(self) -> None:
        captures = [
            make_capture("req-1", nonce="case-1", intent="prompt"),
            make_capture("req-extra", nonce="extra", intent="extra"),
        ]
        spec = {
            "rejectUnexpected": True,
            "expectations": [
                {
                    "id": "bad",
                    "nonce": "case-1",
                    "intent": "prompt",
                    "bodyContains": ["MISSING"],
                    "bodyNotContains": ["ALPHA"],
                    "orderedBodyText": ["BETA", "ALPHA"],
                    "requestPointers": {"/body/missing": True},
                    "responseStatus": 500,
                    "responseCompleted": False,
                }
            ],
        }
        report = capture_assert.evaluate_expectations(captures, spec)
        self.assertFalse(report["ok"])
        failures = "\n".join(report["failures"])
        self.assertIn("missing request pointer", failures)
        self.assertIn("missing marker", failures)
        self.assertIn("forbidden marker", failures)
        self.assertIn("required order", failures)
        self.assertIn("response status", failures)
        self.assertIn("response completed", failures)
        self.assertIn("unexpected captures", failures)

    def test_zero_count_can_forbid_an_auxiliary_route_for_a_nonce(self) -> None:
        captures = [make_capture("req-1", nonce="case-1", intent="chat")]
        spec = {
            "expectations": [
                {
                    "id": "no-unexpected-tts",
                    "nonce": "case-1",
                    "path": "/v1/audio/speech",
                    "count": 0,
                }
            ]
        }
        report = capture_assert.evaluate_expectations(captures, spec)
        self.assertTrue(report["ok"])
        self.assertEqual(report["results"][0]["actualCount"], 0)

    def test_rejects_uncorrelated_or_kpi_counting_specs(self) -> None:
        with self.assertRaisesRegex(capture_assert.AssertionSpecError, "nonce or requestId"):
            capture_assert.validate_spec(
                {"expectations": [{"id": "uncorrelated", "intent": "chat"}]}
            )
        with self.assertRaisesRegex(capture_assert.AssertionSpecError, "cannot count"):
            capture_assert.validate_spec(
                {
                    "countsTowardKpi": True,
                    "expectations": [
                        {"id": "bad-kpi", "nonce": "case-1", "count": 0}
                    ],
                }
            )
        with self.assertRaisesRegex(capture_assert.AssertionSpecError, "select intent"):
            capture_assert.validate_spec(
                {
                    "expectations": [
                        {
                            "id": "missing-intent",
                            "nonce": "case-1",
                            "expectedRequestCount": 2,
                        }
                    ]
                }
            )

    def test_non_virtual_capture_fails_closed(self) -> None:
        capture = make_capture("req-1", nonce="case-1", intent="chat")
        capture["provider"] = "capture-gateway"
        report = capture_assert.evaluate_expectations(
            [capture],
            {
                "expectations": [
                    {"id": "virtual-only", "nonce": "case-1", "count": 1}
                ]
            },
        )
        self.assertFalse(report["ok"])
        self.assertIn("not from tavo-virtual", "\n".join(report["failures"]))

    def test_json_pointer_unescapes_tokens(self) -> None:
        value = {"a/b": {"~key": [10]}}
        self.assertEqual(capture_assert.json_pointer(value, "/a~1b/~0key/0"), 10)
        with self.assertRaises(KeyError):
            capture_assert.json_pointer(value, "/missing")
        with self.assertRaises(capture_assert.AssertionSpecError):
            capture_assert.json_pointer(value, "missing-slash")

    def test_load_and_cli_output_use_private_files(self) -> None:
        capture_dir = self.root / "captures"
        capture_dir.mkdir()
        capture_dir.chmod(0o700)
        capture_path = capture_dir / "000001-req-1.json"
        capture_path.write_text(
            json.dumps(make_capture("req-1", nonce="case-1", intent="chat")),
            encoding="utf-8",
        )
        capture_path.chmod(0o600)
        spec_path = self.root / "expectations.json"
        spec_path.write_text(
            json.dumps(
                {
                    "rejectUnexpected": True,
                    "expectations": [
                        {
                            "id": "chat",
                            "nonce": "case-1",
                            "intent": "chat",
                            "expectedRequestCount": 1,
                            "retryCount": 0,
                            "clientDisconnectCount": 0,
                            "completedCount": 1,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        output_path = self.root / "private-report" / "report.json"
        stdout = io.StringIO()
        with mock.patch.object(
            sys,
            "argv",
            [
                "tavo_fixture_capture_assert.py",
                "--capture-dir",
                str(capture_dir),
                "--expectations",
                str(spec_path),
                "--output",
                str(output_path),
            ],
        ), contextlib.redirect_stdout(stdout):
            code = capture_assert.main()
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])
        self.assertTrue(json.loads(output_path.read_text(encoding="utf-8"))["ok"])
        self.assertEqual(stat.S_IMODE(output_path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(output_path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
