#!/usr/bin/env python3
"""Offline regression tests for the Tavo 0.93 plugin package validators."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
FIXTURES = SKILL_ROOT / "assets" / "fixtures"
TEMPLATES = SKILL_ROOT / "assets" / "templates"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_tavo_artifact import (  # noqa: E402
    is_safe_package_path as artifact_path_is_safe,
    resolve_tpg_entry,
    validate as validate_artifact,
)
from validate_tpg_package import is_safe_relative, validate_package  # noqa: E402
from tpg_spec2 import compare_semver, is_locale_tag, is_semver  # noqa: E402


def write_manifest(root: Path, payload: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def valid_v2_manifest() -> dict[str, object]:
    return {
        "id": "community.spec2.test",
        "name": "Spec 2 Test",
        "version": "1.0.0",
        "specVersion": 2,
        "minAppVersion": "0.93.0",
        "localization": {"defaultLocale": "en"},
    }


def errors_from_both(root: Path) -> tuple[str, str]:
    return (
        "\n".join(validate_package(root).errors),
        "\n".join(validate_artifact(root / "manifest.json", "tpg-manifest")),
    )


class TpgPackageFixtureTests(unittest.TestCase):
    def test_current_entry_template_and_fixture_pass(self) -> None:
        for root in (TEMPLATES / "plugin-minimal", FIXTURES / "plugin-minimal"):
            with self.subTest(root=root):
                result = validate_package(root)
                self.assertEqual((), result.errors)
                self.assertEqual("entry", result.entry_source)
                self.assertEqual("entry.js", result.entry_path)
                self.assertTrue((root / "entry.js").is_file())
                self.assertFalse((root / "actions.js").exists())

    def test_legacy_alias_is_accepted_only_as_fallback(self) -> None:
        result = validate_package(FIXTURES / "plugin-legacy")
        self.assertEqual((), result.errors)
        self.assertEqual("scripts.actions", result.entry_source)
        self.assertEqual("legacy-actions.js", result.entry_path)
        manifest = json.loads((FIXTURES / "plugin-legacy" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(("scripts.actions", "legacy-actions.js"), resolve_tpg_entry(manifest))

    def test_root_entry_wins_and_ignored_legacy_file_may_be_absent(self) -> None:
        result = validate_package(FIXTURES / "plugin-dual")
        self.assertEqual((), result.errors)
        self.assertEqual("entry", result.entry_source)
        self.assertEqual("entry.js", result.entry_path)
        self.assertFalse((FIXTURES / "plugin-dual" / "ignored-missing-legacy.js").exists())
        manifest = json.loads((FIXTURES / "plugin-dual" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(("entry", "entry.js"), resolve_tpg_entry(manifest))

    def test_hook_only_entry_needs_no_contributions(self) -> None:
        root = FIXTURES / "plugin-hook-only"
        result = validate_package(root)
        self.assertEqual((), result.errors)
        manifest_errors = validate_artifact(root / "manifest.json", "tpg-manifest")
        self.assertEqual([], manifest_errors)

    def test_single_wrapping_folder_is_selected_as_plugin_root(self) -> None:
        result = validate_package(FIXTURES / "plugin-nested")
        self.assertEqual((), result.errors)
        self.assertEqual((FIXTURES / "plugin-nested" / "wrapper").resolve(), result.plugin_root)
        self.assertEqual(result.plugin_root / "manifest.json", result.manifest_path)

    def test_multiple_nested_manifests_are_rejected_as_ambiguous(self) -> None:
        result = validate_package(FIXTURES / "plugin-ambiguous")
        self.assertTrue(any("multiple nested manifest.json" in error for error in result.errors))
        self.assertIsNone(result.plugin_root)

    def test_root_manifest_wins_over_multiple_nested_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, {"id": "community.root-wins", "name": "Root Wins", "version": "0.92.0"})
            write_manifest(root / "one", {"id": "community.one", "name": "One", "version": "0.92.0"})
            write_manifest(root / "two", {"id": "community.two", "name": "Two", "version": "0.92.0"})
            result = validate_package(root)
            self.assertEqual((), result.errors)
            self.assertEqual(root.resolve(), result.plugin_root)

    def test_dangerous_manifest_paths_are_rejected_by_both_validators(self) -> None:
        root = FIXTURES / "plugin-dangerous-path"
        package_errors = "\n".join(validate_package(root).errors)
        for label in (
            "entry",
            "cover",
            "scripts.actions",
            "contributes.inputActions[0].icon",
            "contributes.htmlFragments[0].src",
        ):
            with self.subTest(label=label):
                self.assertIn(label, package_errors)
        artifact_errors = validate_artifact(root / "manifest.json", "tpg-manifest")
        self.assertGreaterEqual(len(artifact_errors), 5)

    def test_missing_effective_entry_file_is_rejected(self) -> None:
        result = validate_package(FIXTURES / "plugin-missing-entry")
        self.assertTrue(any("entry file does not exist" in error for error in result.errors))

    def test_actions_require_an_entry_or_legacy_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(
                root,
                {
                    "id": "community.no-entry",
                    "name": "No Entry",
                    "version": "0.92.0",
                    "contributes": {"inputActions": [{"id": "x", "label": "X"}]},
                },
            )
            result = validate_package(root)
            self.assertTrue(any("entry is required" in error for error in result.errors))
            artifact_errors = validate_artifact(root / "manifest.json", "tpg-manifest")
            self.assertTrue(any("entry is required" in error for error in artifact_errors))

    def test_external_symlink_entry_is_rejected_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "plugin"
            write_manifest(
                root,
                {"id": "community.external-link", "name": "External Link", "version": "0.92.0", "entry": "entry.js"},
            )
            outside = base / "outside.js"
            outside.write_text("external marker\n", encoding="utf-8")
            (root / "entry.js").symlink_to(outside)
            errors = "\n".join(validate_package(root).errors)
            self.assertIn("outside the selected plugin root", errors)
            self.assertIn("external symlink", errors)

    def test_old_manifest_filename_is_not_a_manifest_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_manifest = root / "tavo-plugin.json"
            old_manifest.write_text(
                json.dumps({"id": "community.old-name", "name": "Old Name", "version": "0.91.0"}),
                encoding="utf-8",
            )
            self.assertTrue(any("missing manifest.json" in error for error in validate_package(root).errors))
            self.assertTrue(
                any("filename must be manifest.json" in error for error in validate_artifact(old_manifest, "tpg-manifest"))
            )

    def test_empty_manifest_is_not_treated_as_an_unparsed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, {})
            errors = "\n".join(validate_package(root).errors)
            self.assertIn("manifest id", errors)
            self.assertIn("manifest name", errors)
            self.assertIn("manifest version", errors)

    def test_path_predicates_reject_all_documented_unsafe_forms(self) -> None:
        unsafe = [
            "",
            " entry.js",
            "entry.js ",
            "/entry.js",
            "../entry.js",
            "ui/../entry.js",
            "ui\\entry.js",
            "https://example.invalid/entry.js",
            "C:/entry.js",
            "./entry.js",
            "ui//entry.js",
        ]
        for value in unsafe:
            with self.subTest(value=value):
                self.assertFalse(is_safe_relative(value))
                self.assertFalse(artifact_path_is_safe(value))
        for value in ("entry.js", "runtime/entry.js", "icons/menu icon.png"):
            with self.subTest(value=value):
                self.assertTrue(is_safe_relative(value))
                self.assertTrue(artifact_path_is_safe(value))

    def test_spec1_compatibility_keeps_legacy_version_strings(self) -> None:
        for spec in ("omitted", 1):
            with self.subTest(spec=spec), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest: dict[str, object] = {
                    "id": "community.spec1.compat",
                    "name": "$ remains literal in v1",
                    "version": "release-candidate",
                    "minAppVersion": "any-old-version",
                }
                if spec == 1:
                    manifest["specVersion"] = 1
                write_manifest(root, manifest)
                self.assertEqual(("", ""), errors_from_both(root))

    def test_spec_version_is_limited_to_one_or_two(self) -> None:
        for spec in (0, 3, "2", True, 2.0):
            with self.subTest(spec=spec), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest["specVersion"] = spec
                write_manifest(root, manifest)
                for errors in errors_from_both(root):
                    self.assertIn("specVersion must be 1 or 2", errors)

    def test_spec2_semver_accepts_prerelease_and_build_metadata(self) -> None:
        for version in ("0.0.0", "1.2.3", "1.0.0-beta.1", "2.3.4-rc.2+build.7"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest["version"] = version
                manifest["minAppVersion"] = version
                write_manifest(root, manifest)
                self.assertTrue(is_semver(version))
                self.assertEqual(("", ""), errors_from_both(root))

    def test_spec2_semver_rejects_documented_and_numeric_identifier_errors(self) -> None:
        for version in (
            "v1.2.3",
            "1.2",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.0.0-01",
            "1.0.0-",
            "1.0.0-rc_1",
            "1.2.3\u0661",
        ):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest["version"] = version
                write_manifest(root, manifest)
                self.assertFalse(is_semver(version))
                for errors in errors_from_both(root):
                    self.assertIn("version must be valid SemVer", errors)

    def test_spec2_min_app_version_is_semver_when_declared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = valid_v2_manifest()
            manifest["minAppVersion"] = "0.93"
            write_manifest(root, manifest)
            for errors in errors_from_both(root):
                self.assertIn("minAppVersion must be valid SemVer", errors)

    def test_min_app_versions_accept_lower_equal_higher_and_semver_precedence(self) -> None:
        for minimum in ("0.92.9", "0.93.0", "0.94.0", "0.93.0-rc.1", "0.93.0+build.7"):
            with self.subTest(minimum=minimum), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest["minAppVersion"] = minimum
                write_manifest(root, manifest)
                self.assertEqual(("", ""), errors_from_both(root))

        self.assertLess(compare_semver("0.92.9", "0.93.0"), 0)
        self.assertEqual(compare_semver("0.93.0", "0.93.0"), 0)
        self.assertGreater(compare_semver("0.94.0", "0.93.0"), 0)
        self.assertLess(compare_semver("0.93.0-rc.1", "0.93.0"), 0)
        self.assertLess(compare_semver("0.93.0-rc.1", "0.93.0-rc.2"), 0)
        self.assertEqual(compare_semver("0.93.0+build.1", "0.93.0+build.7"), 0)

    def test_spec2_requires_localization_and_hyphenated_default_locale(self) -> None:
        cases = (
            ({}, "localization must be an object"),
            ({"localization": {"defaultLocale": "zh_CN"}}, "defaultLocale"),
            ({"localization": {"defaultLocale": "zh-CN"}}, ""),
            ({"localization": {"defaultLocale": "zh-Hans"}}, ""),
        )
        for patch, expected in cases:
            with self.subTest(patch=patch), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest.update(patch)
                if not patch:
                    manifest.pop("localization")
                write_manifest(root, manifest)
                package_errors, artifact_errors = errors_from_both(root)
                if expected:
                    self.assertIn(expected, package_errors)
                    self.assertIn(expected, artifact_errors)
                else:
                    self.assertEqual(("", ""), (package_errors, artifact_errors))
        self.assertTrue(is_locale_tag("zh-CN"))
        self.assertFalse(is_locale_tag("zh_CN"))

    def test_spec1_rejects_spec2_localization_and_translation_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(
                root,
                {
                    "id": "community.spec1.i18n",
                    "name": {"$t": "plugin.name"},
                    "version": "legacy",
                    "specVersion": 1,
                    "localization": {"defaultLocale": "en"},
                },
            )
            for errors in errors_from_both(root):
                self.assertIn("uses $t localization but specVersion is not 2", errors)
                self.assertIn("localization requires specVersion 2", errors)

    def test_resources_are_optional_and_need_not_include_default_locale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = valid_v2_manifest()
            manifest["localization"] = {
                "defaultLocale": "en",
                "resources": {"zh-CN": "locales/zh-CN.json"},
            }
            write_manifest(root, manifest)
            (root / "locales").mkdir()
            (root / "locales" / "zh-CN.json").write_text('{"plugin.name":"名称"}\n', encoding="utf-8")
            self.assertEqual(("", ""), errors_from_both(root))

    def test_resource_locale_and_path_rules_are_enforced_by_both_validators(self) -> None:
        cases = (
            ({"zh_CN": "locales/zh-CN.json"}, "locale is invalid"),
            ({"en": "../outside.json"}, "safe package-relative path"),
            ({"en": "https://example.invalid/en.json"}, "safe package-relative path"),
            ({"en": "locales\\en.json"}, "safe package-relative path"),
            ({"en": "./locales/en.json"}, "safe package-relative path"),
        )
        for resources, expected in cases:
            with self.subTest(resources=resources), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest["localization"] = {"defaultLocale": "en", "resources": resources}
                write_manifest(root, manifest)
                for errors in errors_from_both(root):
                    self.assertIn(expected, errors)

    def test_missing_catalog_and_external_catalog_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "plugin"
            manifest = valid_v2_manifest()
            manifest["localization"] = {"defaultLocale": "en", "resources": {"en": "locales/en.json"}}
            write_manifest(root, manifest)
            for errors in errors_from_both(root):
                self.assertIn("catalog 'en' file does not exist", errors)

            (root / "locales").mkdir()
            outside = base / "outside.json"
            outside.write_text('{"plugin.name":"outside"}\n', encoding="utf-8")
            (root / "locales" / "en.json").symlink_to(outside)
            package_errors, artifact_errors = errors_from_both(root)
            self.assertIn("catalog 'en' resolves outside", package_errors)
            self.assertIn("external symlink", package_errors)
            self.assertIn("catalog 'en' resolves outside", artifact_errors)

    def test_catalog_must_be_utf8_json_object_with_flat_string_values(self) -> None:
        cases: tuple[tuple[str, bytes, str], ...] = (
            ("invalid-utf8", b'{"key":"\\xff"}\xff', "valid UTF-8"),
            ("invalid-json", b"{", "valid JSON"),
            ("array", b"[]", "flat JSON object"),
            ("empty-key", b'{"":"value"}', "keys must be non-empty"),
            ("nested", b'{"key":{"nested":"value"}}', "values must be strings"),
            ("number", b'{"key":1}', "values must be strings"),
        )
        for name, content, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest["localization"] = {"defaultLocale": "en", "resources": {"en": "locales/en.json"}}
                write_manifest(root, manifest)
                (root / "locales").mkdir()
                (root / "locales" / "en.json").write_bytes(content)
                for errors in errors_from_both(root):
                    self.assertIn(expected, errors)

    def test_all_documented_translation_positions_and_structured_select_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = valid_v2_manifest()
            manifest.update(
                {
                    "name": {"$t": "plugin.name"},
                    "description": {"$t": "plugin.description"},
                    "entry": "entry.js",
                    "contributes": {
                        "inputActions": [{"id": "input", "label": {"$t": "actions.input"}}],
                        "sidebar": [{"id": "sidebar", "label": {"$t": "actions.sidebar"}}],
                        "settings": {
                            "schema": [
                                {
                                    "key": "enabled",
                                    "type": "switch",
                                    "label": {"$t": "settings.enabled"},
                                    "default": True,
                                },
                                {
                                    "key": "mode",
                                    "type": "select",
                                    "label": {"$t": "settings.mode"},
                                    "default": "short",
                                    "options": [
                                        "legacy",
                                        {"value": "short", "label": {"$t": "settings.mode.short"}},
                                    ],
                                },
                                {
                                    "key": "strength",
                                    "type": "slider",
                                    "label": {"$t": "settings.strength"},
                                    "min": 0,
                                    "max": 1,
                                },
                                {
                                    "key": "text",
                                    "type": "text",
                                    "label": {"$t": "settings.text"},
                                    "default": {"$t": "settings.text.default"},
                                },
                                {
                                    "key": "textarea",
                                    "type": "textarea",
                                    "label": {"$t": "settings.textarea"},
                                    "default": {"$t": "settings.textarea.default"},
                                },
                                {"type": "info", "text": {"$t": "settings.info"}},
                            ]
                        },
                    },
                }
            )
            write_manifest(root, manifest)
            (root / "entry.js").write_text("// spec 2 fixture\n", encoding="utf-8")
            self.assertEqual(("", ""), errors_from_both(root))

    def test_translation_object_is_strict_and_rejected_in_unsupported_positions(self) -> None:
        cases = (
            (
                {"name": {"$t": "plugin.name", "extra": "not allowed"}},
                "strict object form",
            ),
            (
                {"name": {"$t": ""}},
                "$t key must be a non-empty string",
            ),
            (
                {"author": {"$t": "plugin.author"}},
                "unsupported manifest position",
            ),
        )
        for patch, expected in cases:
            with self.subTest(patch=patch), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = valid_v2_manifest()
                manifest.update(patch)
                write_manifest(root, manifest)
                for errors in errors_from_both(root):
                    self.assertIn(expected, errors)

    def test_strings_starting_with_dollar_are_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = valid_v2_manifest()
            manifest["name"] = "$literal plugin name"
            manifest["description"] = "$t is not special in a string"
            write_manifest(root, manifest)
            self.assertEqual(("", ""), errors_from_both(root))

    def test_structured_select_is_v2_only_and_has_strict_shape(self) -> None:
        base_setting = {
            "key": "mode",
            "type": "select",
            "label": "Mode",
            "options": [{"value": "short", "label": "Short"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(
                root,
                {
                    "id": "community.spec1.structured-select",
                    "name": "Legacy",
                    "version": "legacy",
                    "specVersion": 1,
                    "contributes": {"settings": {"schema": [base_setting]}},
                },
            )
            for errors in errors_from_both(root):
                self.assertIn("structured options require specVersion 2", errors)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = valid_v2_manifest()
            invalid_setting = dict(base_setting)
            invalid_setting["options"] = [{"value": "short", "label": "Short", "extra": True}]
            manifest["contributes"] = {"settings": {"schema": [invalid_setting]}}
            write_manifest(root, manifest)
            for errors in errors_from_both(root):
                self.assertIn("must contain exactly value and label", errors)

    def test_schema_declares_spec2_i18n_entry_precedence_and_legacy_deprecation(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "assets" / "schemas" / "tpg-manifest.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("Tavo Plugin Manifest 0.93", schema["title"])
        self.assertEqual([1, 2], schema["properties"]["specVersion"]["enum"])
        self.assertIn("semver", schema["$defs"])
        self.assertIn("localization", schema["$defs"])
        self.assertFalse(schema["$defs"]["translationRef"]["additionalProperties"])
        self.assertIn("entry", schema["properties"])
        self.assertTrue(schema["properties"]["scripts"]["properties"]["actions"]["deprecated"])


if __name__ == "__main__":
    unittest.main()
