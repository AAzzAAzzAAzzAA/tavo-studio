#!/usr/bin/env python3
"""Offline checks for actual Tavo 0.93 package validation."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import run_phone_plugin_093_package_actual as runner  # noqa: E402


class Plugin093PackageActualTests(unittest.TestCase):
    def test_offline_modes_do_not_execute(self) -> None:
        for arguments in (
            ["runner", "--self-check", "--run-id", "T093_TEST"],
            ["runner", "--print-plan", "--run-id", "T093_TEST"],
        ):
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute", side_effect=AssertionError("execute reached")) as execute,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(runner.main(), 0)
                self.assertTrue(json.loads(output.getvalue()))
                execute.assert_not_called()

    def test_matrix_includes_path_and_wrapper_canaries(self) -> None:
        cases = runner.cases()
        keys = {case.key for case in cases}
        self.assertEqual(len(keys), len(cases))
        self.assertIn("zip-entry-traversal-rejected", keys)
        self.assertIn("zip-entry-absolute-rejected", keys)
        self.assertIn("zip-entry-backslash-rejected", keys)
        self.assertIn("single-wrapper-with-sibling-accepted", keys)
        self.assertIn("missing-manifest-rejected", keys)

    def test_all_payloads_are_zip_files(self) -> None:
        for case in runner.cases():
            with self.subTest(case=case.key), zipfile.ZipFile(io.BytesIO(case.data)) as archive:
                self.assertTrue(archive.namelist())

    def test_manifest_id_discovery_handles_wrappers(self) -> None:
        wrapper = next(case for case in runner.cases() if case.key == "single-wrapper-accepted")
        self.assertEqual(runner.manifest_ids(wrapper.data), ["t093.20260726.r1.package.wrapper"])


if __name__ == "__main__":
    unittest.main()
