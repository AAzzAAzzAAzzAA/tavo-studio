#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

import run_phone_plugin_093_matrix as runner  # noqa: E402
import tavo_093_runner_core as core  # noqa: E402


class PhonePlugin093MatrixTests(unittest.TestCase):
    def test_catalog_is_versioned_complete_and_well_formed(self) -> None:
        cases = runner.build_cases()
        self.assertEqual([case.key for case in cases], [f"P93-{index:02d}" for index in range(1, 12)])
        self.assertEqual(core.validate_catalog(cases), [])
        titles = " ".join(case.title for case in cases)
        for marker in ("Spec 2", "SemVer", "minAppVersion", "internationalization"):
            self.assertIn(marker, titles)
        self.assertEqual([case.key for case in cases if case.destructive], ["P93-10"])
        self.assertEqual(
            sorted({item for case in cases for item in case.matrix_items}),
            ["A", "J"],
        )

    def test_subset_expands_dependencies_in_canonical_order(self) -> None:
        selected = runner.selected_cases("P93-10")
        keys = [case.key for case in selected]
        self.assertEqual(keys, ["P93-01", "P93-02", "P93-03", "P93-05", "P93-08", "P93-09", "P93-10"])
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            runner.selected_cases("P93-99")
        with self.assertRaisesRegex(RuntimeError, "duplicates"):
            runner.selected_cases("P93-01,P93-01")

    def test_self_check_and_print_plan_are_offline(self) -> None:
        for arguments in (
            ["runner", "--self-check", "--run-id", "RUN-PLUGIN"],
            ["runner", "--print-plan", "--run-id", "RUN-PLUGIN"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute_phase", side_effect=AssertionError("offline reached live phase")) as live,
                mock.patch.object(core, "read_private_endpoint", side_effect=AssertionError("offline read endpoint")),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertEqual(runner.main(), 0)
                self.assertIsInstance(json.loads(stdout.getvalue()), dict)
                live.assert_not_called()

    def test_prepare_is_private_deterministic_and_never_live(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "plugin-093"
            with mock.patch.object(runner, "execute_phase", side_effect=AssertionError("prepare reached live")):
                result = core.prepare_bundle(
                    output,
                    kind=runner.KIND,
                    run_id="RUN-PLUGIN",
                    cases=runner.build_cases(),
                    code_hash=runner.code_hash(),
                )
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((output / "plan.json").stat().st_mode), 0o600)
            self.assertEqual(result["manifest"]["status"], "prepared")
            self.assertEqual(result["plan"]["appVersion"], "0.93.0")
            case_file = core.load_json(output / "cases" / "P93-01" / "case.json")
            self.assertEqual(
                case_file["resultContract"]["terminalStatuses"],
                list(core.TERMINAL_STATUSES),
            )
            self.assertTrue(
                case_file["resultContract"]["terminalFindingsDoNotBlockCompletion"]
            )
            with self.assertRaisesRegex(RuntimeError, "absent or empty"):
                core.prepare_bundle(
                    output,
                    kind=runner.KIND,
                    run_id="RUN-PLUGIN",
                    cases=runner.build_cases(),
                    code_hash=runner.code_hash(),
                )

    def test_execute_requires_confirmation_device_endpoint_and_isolation_first(self) -> None:
        base = {
            "run_id": "RUN-PLUGIN",
            "artifact_dir": "/tmp/not-used-plugin-093",
            "device": "",
            "endpoint_json": "",
            "confirm": "",
            "isolated_chat_id": 0,
            "protected_chat_id": 0,
        }
        with (
            mock.patch.object(core, "read_private_endpoint", side_effect=AssertionError("invalid args reached endpoint")),
            self.assertRaisesRegex(RuntimeError, "confirm"),
        ):
            runner.execute_phase(argparse.Namespace(**base), "execute")

        base["confirm"] = core.CONFIRMATION
        with (
            mock.patch.object(core, "read_private_endpoint", side_effect=AssertionError("missing device reached endpoint")),
            self.assertRaisesRegex(RuntimeError, "device"),
        ):
            runner.execute_phase(argparse.Namespace(**base), "execute")

    def test_authorized_skeleton_reserves_once_and_never_contacts_live_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact"
            endpoint = root / "endpoint.json"
            endpoint.write_text('{"url":"http://127.0.0.1:9/mcp","auth":"Bearer hidden"}', encoding="utf-8")
            endpoint.chmod(0o600)
            core.prepare_bundle(
                artifact,
                kind=runner.KIND,
                run_id="RUN-PLUGIN",
                cases=runner.build_cases(),
                code_hash=runner.code_hash(),
            )
            args = argparse.Namespace(
                run_id="RUN-PLUGIN",
                artifact_dir=str(artifact),
                device="offline-device",
                endpoint_json=str(endpoint),
                confirm=core.CONFIRMATION,
                isolated_chat_id=900001,
                protected_chat_id=42,
            )
            result = runner.execute_phase(args, "execute")
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["deviceOrMcpContacted"])
            intent = core.load_json(artifact / "intents" / "execute.json")
            self.assertEqual(intent["status"], "reserved")
            with self.assertRaisesRegex(RuntimeError, "cannot resend"):
                runner.execute_phase(args, "execute")


if __name__ == "__main__":
    unittest.main()
