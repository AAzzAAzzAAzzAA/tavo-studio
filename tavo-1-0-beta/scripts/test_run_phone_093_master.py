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

import run_phone_093_master as runner  # noqa: E402
import tavo_093_runner_core as core  # noqa: E402


class Phone093MasterTests(unittest.TestCase):
    def test_master_catalog_and_phase_graph_are_complete(self) -> None:
        cases = runner.build_cases()
        self.assertEqual(len(cases), 216)
        self.assertEqual(core.validate_catalog(cases), [])
        self.assertEqual(cases[0].key, "D93-A01")
        self.assertEqual(cases[191].key, "D93-J06")
        self.assertEqual(cases[-1].key, "M93-99")
        self.assertEqual(cases[-1].dependencies, ("N93-12", "P93-11"))
        self.assertEqual(len(runner.ORCHESTRATION_PHASES), 9)
        blocked = [row for row in runner.ORCHESTRATION_PHASES if row.get("blockedByDefault")]
        self.assertEqual([row["phase"] for row in blocked], ["60-real-provider-blocked"])
        self.assertEqual(
            sorted({item for case in cases for item in case.matrix_items}),
            list(core.MATRIX_ITEMS),
        )

    def test_offline_modes_never_enter_execute_or_endpoint_reader(self) -> None:
        for arguments in (
            ["runner", "--self-check", "--run-id", "RUN-MASTER"],
            ["runner", "--print-plan", "--run-id", "RUN-MASTER"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute_phase", side_effect=AssertionError("offline reached live")) as live,
                mock.patch.object(core, "read_private_endpoint", side_effect=AssertionError("offline read endpoint")),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertEqual(runner.main(), 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["appVersion"], "0.93.0")
                live.assert_not_called()

    def test_prepare_master_records_orchestration_and_private_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "master"
            result = runner.prepare_master(
                artifact,
                "RUN-MASTER",
                runner.build_cases(),
                runner.code_hash(),
            )
            self.assertEqual(
                result["manifest"]["orchestrationPhases"],
                [row["phase"] for row in runner.ORCHESTRATION_PHASES],
            )
            self.assertEqual(
                result["plan"]["planHash"],
                core.load_json(artifact / "run-manifest.json")["planHash"],
            )
            self.assertTrue((artifact / "cases" / "N93-01" / "case.json").exists())
            self.assertTrue((artifact / "cases" / "D93-HPE34" / "case.json").exists())
            self.assertTrue((artifact / "cases" / "D93-HCF35" / "case.json").exists())
            self.assertTrue((artifact / "cases" / "P93-11" / "case.json").exists())
            self.assertTrue((artifact / "cases" / "M93-99" / "case.json").exists())

    def test_final_gate_fails_closed_on_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary)
            evaluation = core.evaluate_final_gate(
                artifact,
                runner.build_cases(),
                required_matrix_items=core.MATRIX_ITEMS,
            )
            self.assertFalse(evaluation["passed"])
            self.assertTrue(any("missing result.json" in error for error in evaluation["errors"]))
            self.assertIn("missing restoration/result.json", evaluation["errors"])

    def test_complete_local_final_gate_allows_terminal_findings_and_zero_real_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "master"
            endpoint = root / "endpoint.json"
            endpoint.write_text('{"url":"http://127.0.0.1:9/mcp","auth":"Bearer hidden"}', encoding="utf-8")
            endpoint.chmod(0o600)
            cases = runner.build_cases()
            runner.prepare_master(artifact, "RUN-MASTER", cases, runner.code_hash())

            terminal_findings = {
                "D93-C14": "blocked",
                "D93-D10": "blocked",
                "D93-E11": "blocked",
                "N93-11": "blocked",
                "P93-03": "failed",
                "P93-05": "mixed",
                "P93-07": "not-applicable",
            }
            for case in cases:
                status = terminal_findings.get(case.key, "passed")
                core.durable_json(
                    artifact / "cases" / case.key / "result.json",
                    core.case_result_record(
                        case,
                        status,
                        evidence_level="offline",
                        notes="Live provider adapter remains explicitly unwired."
                        if case.key == "N93-11"
                        else "",
                    ),
                )
            restoration = {"passed": True}
            restoration.update({key: True for key in core.RESTORATION_ASSERTIONS})
            core.durable_json(artifact / "restoration" / "result.json", restoration)
            core.durable_json(
                artifact / "final-gate" / "adb.json",
                {
                    "status": "passed",
                    "appVersion": core.APP_VERSION,
                    "deviceIdentityMatches": True,
                },
            )
            core.durable_json(
                artifact / "final-gate" / "mcp.json",
                {
                    "status": "passed",
                    "strict": True,
                    "identityMatches": True,
                    "surfaceReviewed": True,
                },
            )
            core.durable_json(
                artifact / "final-gate" / "state.json",
                {
                    "status": "passed",
                    "anchorHashMatches": True,
                    "protectedChatUntouched": True,
                },
            )

            local = core.evaluate_final_gate(
                artifact,
                cases,
                required_matrix_items=core.MATRIX_ITEMS,
            )
            self.assertTrue(local["ok"], local["errors"])
            self.assertFalse(local["passed"])
            self.assertEqual(local["status"], "complete")
            self.assertEqual(local["verdict"], "complete-with-findings")
            self.assertEqual(local["terminalCounts"]["blocked"], 4)
            self.assertEqual(local["terminalCounts"]["failed"], 1)
            self.assertEqual(local["terminalCounts"]["mixed"], 1)
            self.assertEqual(local["terminalCounts"]["not-applicable"], 1)
            self.assertEqual(
                local["findings"],
                [
                    {"case": "D93-C14", "status": "blocked"},
                    {"case": "D93-D10", "status": "blocked"},
                    {"case": "D93-E11", "status": "blocked"},
                    {"case": "N93-11", "status": "blocked"},
                    {"case": "P93-03", "status": "failed"},
                    {"case": "P93-05", "status": "mixed"},
                    {"case": "P93-07", "status": "not-applicable"},
                ],
            )
            self.assertTrue(all(row["terminal"] for row in local["matrixCoverage"].values()))
            self.assertEqual(sorted(local["matrixCoverage"]), list(core.MATRIX_ITEMS))

            args = argparse.Namespace(
                run_id="RUN-MASTER",
                artifact_dir=str(artifact),
                device="offline-device",
                endpoint_json=str(endpoint),
                confirm=core.FINAL_CONFIRMATION,
                isolated_chat_id=900001,
                protected_chat_id=42,
            )
            result = core.run_final_gate(
                args,
                kind=runner.KIND,
                code_hash=runner.code_hash(),
                cases=cases,
                required_matrix_items=core.MATRIX_ITEMS,
            )
            self.assertTrue(result["ok"], result["errors"])
            self.assertFalse(result["passed"])
            self.assertEqual(result["verdict"], "complete-with-findings")
            manifest = core.load_json(artifact / "run-manifest.json")
            self.assertEqual(manifest["status"], "complete")
            self.assertFalse(manifest["countsTowardPass"])
            self.assertTrue(manifest["terminalCoverageComplete"])

    def test_deferred_and_false_passed_real_model_results_are_rejected(self) -> None:
        cases = runner.build_cases()
        real_case = next(case for case in cases if case.key == "N93-11")
        with self.assertRaisesRegex(RuntimeError, "not terminal"):
            core.case_result_record(real_case, "deferred", evidence_level="offline")
        with self.assertRaisesRegex(RuntimeError, "cannot pass"):
            core.case_result_record(real_case, "passed", evidence_level="offline")

    def test_master_gate_requires_all_a_to_j_items_even_for_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            evaluation = core.evaluate_final_gate(
                Path(temporary),
                runner.selected_cases("N93-03"),
                required_matrix_items=core.MATRIX_ITEMS,
            )
            self.assertFalse(evaluation["terminalCoverageComplete"])
            self.assertFalse(evaluation["matrixCoverage"]["I"]["terminal"])
            self.assertEqual(evaluation["matrixCoverage"]["I"]["caseCount"], 0)

    def test_execute_cli_refuses_missing_live_identity_before_adapter(self) -> None:
        arguments = [
            "runner",
            "--execute",
            "--run-id",
            "RUN-MASTER",
            "--artifact-dir",
            "/tmp/not-used-master-093",
        ]
        with (
            mock.patch.object(sys, "argv", arguments),
            mock.patch.object(core, "read_private_endpoint", side_effect=AssertionError("missing gates reached endpoint")),
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            self.assertEqual(runner.main(), 2)
            self.assertIn("confirm", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
