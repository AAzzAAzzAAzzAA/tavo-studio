#!/usr/bin/env python3
"""Offline checks for the Tavo 0.93 live plugin matrix."""

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

import run_phone_plugin_093_live as runner  # noqa: E402


class Plugin093LiveOfflineTests(unittest.TestCase):
    def test_offline_modes_never_execute(self) -> None:
        for arguments in (
            ["runner", "--self-check", "--run-id", "T093_TEST"],
            ["runner", "--print-plan", "--run-id", "T093_TEST"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(runner, "execute", side_effect=AssertionError("live executor reached")) as execute,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(runner.main(), 0)
                self.assertTrue(json.loads(output.getvalue()))
                execute.assert_not_called()

    def test_manifest_matrix_has_positive_and_negative_semver_and_i18n_cases(self) -> None:
        cases = runner.manifest_cases()
        keys = {case.key for case in cases}
        self.assertEqual(len(keys), len(cases))
        self.assertIn("semver-valid-prerelease", keys)
        self.assertIn("semver-invalid-leading-zero", keys)
        self.assertIn("locale-underscore-rejected", keys)
        self.assertIn("t-object-valid-positions", keys)
        self.assertTrue(any(case.expected_ok for case in cases))
        self.assertTrue(any(not case.expected_ok for case in cases))

    def test_full_v2_covers_localized_native_positions(self) -> None:
        manifest = runner.full_v2("t093.test.full")
        self.assertEqual(manifest["specVersion"], 2)
        self.assertEqual(manifest["localization"]["defaultLocale"], "en")
        self.assertEqual(manifest["name"], {"$t": "plugin.name"})
        schema = manifest["contributes"]["settings"]["schema"]
        self.assertTrue(any(item.get("type") == "textarea" and isinstance(item.get("default"), dict) for item in schema))
        self.assertTrue(any(item.get("type") == "select" and isinstance(item["options"][0]["label"], dict) for item in schema))

    def test_package_cases_are_real_zip_archives(self) -> None:
        cases = runner.package_cases()
        self.assertGreaterEqual(len(cases), 10)
        for key, data, _ in cases:
            with self.subTest(key=key), zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertTrue(archive.namelist())

    def test_self_check_is_deterministic(self) -> None:
        first = runner.self_check("T093_TEST")
        second = runner.self_check("T093_TEST")
        self.assertEqual(first["planHash"], second["planHash"])
        self.assertEqual(first["plan"], second["plan"])


if __name__ == "__main__":
    unittest.main()
