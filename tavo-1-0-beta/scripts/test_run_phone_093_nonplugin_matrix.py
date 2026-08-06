#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import run_phone_093_nonplugin_matrix as runner  # noqa: E402
import tavo_093_runner_core as core  # noqa: E402


class Phone093NonPluginMatrixTests(unittest.TestCase):
    def test_catalog_covers_release_surface_and_real_provider_boundary(self) -> None:
        cases = runner.build_cases()
        self.assertEqual([case.key for case in cases], [f"N93-{index:02d}" for index in range(1, 13)])
        self.assertEqual(core.validate_catalog(cases), [])
        titles = " ".join(case.title for case in cases)
        for marker in (
            "Fable 5",
            "Mythos 5",
            "OpenRouter ASR",
            "long-press",
            "Voice binding selector",
            "Italic",
            "Theme",
            "Right sidebar",
        ):
            self.assertIn(marker, titles)
        self.assertEqual([case.key for case in cases if case.requires_real_model], ["N93-11"])
        self.assertTrue(next(case for case in cases if case.key == "N93-07").manual)
        self.assertEqual(
            sorted({item for case in cases for item in case.matrix_items}),
            ["A", "B", "C", "D", "F", "J"],
        )

    def test_final_restoration_dependency_closure_keeps_real_provider_explicit(self) -> None:
        selected = runner.selected_cases("N93-12")
        keys = [case.key for case in selected]
        self.assertIn("N93-11", keys)
        self.assertEqual(keys[-1], "N93-12")
        self.assertEqual(keys[:2], ["N93-01", "N93-02"])

    def test_offline_cli_modes_never_read_endpoint_or_enter_live_phase(self) -> None:
        for arguments in (
            ["runner", "--self-check", "--run-id", "RUN-NONPLUGIN"],
            ["runner", "--print-plan", "--run-id", "RUN-NONPLUGIN"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute_phase", side_effect=AssertionError("offline reached live phase")) as live,
                mock.patch.object(core, "read_private_endpoint", side_effect=AssertionError("offline read endpoint")),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertEqual(runner.main(), 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["appVersion"], "0.93.0")
                live.assert_not_called()

    def test_prepare_cli_writes_plan_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "nonplugin"
            arguments = [
                "runner",
                "--prepare",
                "--run-id",
                "RUN-NONPLUGIN",
                "--artifact-dir",
                str(artifact),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute_phase", side_effect=AssertionError("prepare reached live")) as live,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(runner.main(), 0)
                live.assert_not_called()
            manifest = core.load_json(artifact / "run-manifest.json")
            self.assertEqual(manifest["status"], "prepared")
            self.assertEqual(manifest["liveAdapter"], "not-wired")
            contract = core.load_json(
                artifact / "cases" / "N93-11" / "case.json"
            )["resultContract"]
            for field in (
                "realProviderRequestsAttempted",
                "realProviderRequestsCompleted",
                "realModelCallsAttempted",
                "realModelCallsCompleted",
                "realCredentialsUsed",
            ):
                self.assertIn(field, contract["requiredFields"])

    def test_resume_requires_same_identity_and_is_no_resend(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact"
            endpoint = root / "endpoint.json"
            endpoint.write_text('{"url":"http://127.0.0.1:9/mcp","auth":"Bearer hidden"}', encoding="utf-8")
            endpoint.chmod(0o600)
            core.prepare_bundle(
                artifact,
                kind=runner.KIND,
                run_id="RUN-NONPLUGIN",
                cases=runner.build_cases(),
                code_hash=runner.code_hash(),
            )
            args = argparse.Namespace(
                run_id="RUN-NONPLUGIN",
                artifact_dir=str(artifact),
                device="offline-device",
                endpoint_json=str(endpoint),
                confirm=core.CONFIRMATION,
                isolated_chat_id=900001,
                protected_chat_id=42,
            )
            self.assertEqual(runner.execute_phase(args, "execute")["status"], "blocked")

            changed = argparse.Namespace(**{**vars(args), "device": "different-device"})
            with self.assertRaisesRegex(RuntimeError, "identity"):
                runner.execute_phase(changed, "resume")

            self.assertEqual(runner.execute_phase(args, "resume")["status"], "blocked")
            with self.assertRaises(FileExistsError):
                runner.execute_phase(args, "resume")

    def test_endpoint_file_must_be_private_regular_and_not_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            endpoint = root / "endpoint.json"
            endpoint.write_text('{"url":"http://127.0.0.1/mcp","auth":"Bearer hidden"}', encoding="utf-8")
            endpoint.chmod(0o600)
            self.assertEqual(core.read_private_endpoint(endpoint)["url"], "http://127.0.0.1/mcp")
            endpoint.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, "mode-0600"):
                core.read_private_endpoint(endpoint)
            endpoint.chmod(0o600)
            link = root / "endpoint-link.json"
            link.symlink_to(endpoint)
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                core.read_private_endpoint(link)


if __name__ == "__main__":
    unittest.main()
