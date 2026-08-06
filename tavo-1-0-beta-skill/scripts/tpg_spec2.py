#!/usr/bin/env python3
"""Shared stdlib-only validation for Tavo plugin manifest specs 1 and 2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
URI_OR_DRIVE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
LOCALE_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*|0|[1-9][0-9]*)"
    r"(?:\.(?:[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*|0|[1-9][0-9]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
SETTING_TYPES = {"switch", "select", "slider", "text", "textarea", "info", "divider", "break"}


@dataclass(frozen=True)
class ManifestAnalysis:
    """Normalized manifest pieces needed by package-level file checks."""

    spec_version: int | None
    contributes: dict[str, Any]
    input_actions: list[Any]
    sidebar_actions: list[Any]
    html_fragments: list[Any]
    localization_resources: tuple[tuple[str, str], ...]


def is_safe_package_path(value: Any) -> bool:
    """Return whether *value* is a canonical package-relative virtual path."""

    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if "\\" in value or "\x00" in value or value.startswith("/") or URI_OR_DRIVE.match(value):
        return False
    return all(segment not in {"", ".", ".."} for segment in value.split("/"))


def is_semver(value: Any) -> bool:
    return isinstance(value, str) and SEMVER.fullmatch(value) is not None


def compare_semver(left: str, right: str) -> int:
    """Compare two valid SemVer strings, ignoring build metadata."""

    if not is_semver(left) or not is_semver(right):
        raise ValueError("compare_semver requires two valid SemVer strings")

    def split(value: str) -> tuple[tuple[int, int, int], tuple[str, ...] | None]:
        precedence = value.split("+", 1)[0]
        core, separator, prerelease = precedence.partition("-")
        major, minor, patch = (int(part) for part in core.split("."))
        return (major, minor, patch), tuple(prerelease.split(".")) if separator else None

    left_core, left_pre = split(left)
    right_core, right_pre = split(right)
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    if left_pre is None or right_pre is None:
        if left_pre is right_pre:
            return 0
        return 1 if left_pre is None else -1

    for left_item, right_item in zip(left_pre, right_pre):
        if left_item == right_item:
            continue
        left_numeric = left_item.isdigit()
        right_numeric = right_item.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_item) < int(right_item) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_item < right_item else 1
    if len(left_pre) == len(right_pre):
        return 0
    return -1 if len(left_pre) < len(right_pre) else 1


def is_locale_tag(value: Any) -> bool:
    return isinstance(value, str) and LOCALE_TAG.fullmatch(value) is not None


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _localized_string(
    value: Any,
    field: str,
    spec_version: int | None,
    errors: list[str],
    handled_t_objects: set[int],
    *,
    allow_empty_literal: bool = False,
) -> None:
    if isinstance(value, str):
        if not allow_empty_literal and not value.strip():
            errors.append(f"{field} must be a non-empty string or strict $t object")
        return
    if isinstance(value, dict):
        handled_t_objects.add(id(value))
        if spec_version != 2:
            errors.append(f"{field} uses $t localization but specVersion is not 2")
            return
        if set(value) != {"$t"}:
            errors.append(f"{field} must use the strict object form {{\"$t\": \"key\"}}")
            return
        if not _nonempty_string(value.get("$t")):
            errors.append(f"{field} $t key must be a non-empty string")
        return
    errors.append(f"{field} must be a string or strict $t object")


def _scan_unsupported_t_objects(
    value: Any,
    path: str,
    handled_t_objects: set[int],
    errors: list[str],
) -> None:
    if isinstance(value, dict):
        if "$t" in value and id(value) not in handled_t_objects:
            errors.append(f"{path} uses $t in an unsupported manifest position")
        for key, child in value.items():
            _scan_unsupported_t_objects(child, f"{path}.{key}", handled_t_objects, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_unsupported_t_objects(child, f"{path}[{index}]", handled_t_objects, errors)


def _validate_settings(
    contributes: dict[str, Any],
    spec_version: int | None,
    errors: list[str],
    handled_t_objects: set[int],
) -> None:
    if "settings" not in contributes:
        return
    settings = contributes.get("settings")
    if not isinstance(settings, dict):
        errors.append("manifest contributes.settings must be an object")
        return
    schema = settings.get("schema")
    if not isinstance(schema, list):
        errors.append("manifest contributes.settings.schema must be an array")
        return

    for index, setting in enumerate(schema):
        field = f"manifest contributes.settings.schema[{index}]"
        if not isinstance(setting, dict):
            errors.append(f"{field} must be an object")
            continue
        setting_type = setting.get("type")
        if setting_type not in SETTING_TYPES:
            errors.append(f"{field}.type must be one of {', '.join(sorted(SETTING_TYPES))}")
            continue

        if setting_type in {"switch", "select", "slider", "text", "textarea"}:
            if not _nonempty_string(setting.get("key")):
                errors.append(f"{field}.key must be a non-empty string")
            if "label" not in setting:
                errors.append(f"{field}.label is required")
            else:
                _localized_string(
                    setting.get("label"),
                    f"{field}.label",
                    spec_version,
                    errors,
                    handled_t_objects,
                )

        if setting_type == "switch" and "default" in setting and not isinstance(setting.get("default"), bool):
            errors.append(f"{field}.default must be a boolean")

        if setting_type == "select":
            options = setting.get("options")
            if not isinstance(options, list) or not options:
                errors.append(f"{field}.options must be a non-empty array")
            else:
                for option_index, option in enumerate(options):
                    option_field = f"{field}.options[{option_index}]"
                    if isinstance(option, str):
                        if not option:
                            errors.append(f"{option_field} must be a non-empty string")
                        continue
                    if not isinstance(option, dict):
                        errors.append(f"{option_field} must be a string or structured option object")
                        continue
                    if spec_version != 2:
                        errors.append(f"{option_field} structured options require specVersion 2")
                    if set(option) != {"value", "label"}:
                        errors.append(f"{option_field} must contain exactly value and label")
                    if not _nonempty_string(option.get("value")):
                        errors.append(f"{option_field}.value must be a non-empty, non-localized string")
                    if "label" in option:
                        _localized_string(
                            option.get("label"),
                            f"{option_field}.label",
                            spec_version,
                            errors,
                            handled_t_objects,
                        )
            if "default" in setting and not _nonempty_string(setting.get("default")):
                errors.append(f"{field}.default must be a non-empty option value string")

        if setting_type == "slider":
            minimum = setting.get("min")
            maximum = setting.get("max")
            if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
                errors.append(f"{field}.min must be a number")
            if not isinstance(maximum, (int, float)) or isinstance(maximum, bool):
                errors.append(f"{field}.max must be a number")
            if (
                isinstance(minimum, (int, float))
                and not isinstance(minimum, bool)
                and isinstance(maximum, (int, float))
                and not isinstance(maximum, bool)
                and maximum <= minimum
            ):
                errors.append(f"{field}.max must be greater than min")
            if "step" in setting and (
                not isinstance(setting.get("step"), (int, float))
                or isinstance(setting.get("step"), bool)
                or setting["step"] <= 0
            ):
                errors.append(f"{field}.step must be a number greater than 0")
            if "default" in setting and (
                not isinstance(setting.get("default"), (int, float)) or isinstance(setting.get("default"), bool)
            ):
                errors.append(f"{field}.default must be a number")

        if setting_type in {"text", "textarea"} and "default" in setting:
            _localized_string(
                setting.get("default"),
                f"{field}.default",
                spec_version,
                errors,
                handled_t_objects,
                allow_empty_literal=True,
            )

        if setting_type == "info":
            if "text" not in setting:
                errors.append(f"{field}.text is required")
            else:
                _localized_string(
                    setting.get("text"),
                    f"{field}.text",
                    spec_version,
                    errors,
                    handled_t_objects,
                )
            if "icon" in setting and setting.get("icon") not in {"info", "warning"}:
                errors.append(f"{field}.icon must be info or warning")


def validate_manifest_semantics(data: dict[str, Any], errors: list[str]) -> ManifestAnalysis:
    """Validate manifest structure shared by standalone and package validators."""

    plugin_id = data.get("id")
    if not isinstance(plugin_id, str) or SAFE_ID.fullmatch(plugin_id) is None:
        errors.append("manifest id must be a lowercase dotted/kebab identifier")

    raw_spec = data.get("specVersion", 1)
    if isinstance(raw_spec, bool) or not isinstance(raw_spec, int) or raw_spec not in {1, 2}:
        errors.append("manifest specVersion must be 1 or 2")
        spec_version: int | None = None
    else:
        spec_version = raw_spec

    handled_t_objects: set[int] = set()
    if "name" not in data:
        errors.append("manifest name is required")
    else:
        _localized_string(data.get("name"), "manifest name", spec_version, errors, handled_t_objects)

    version = data.get("version")
    if spec_version == 2:
        if not is_semver(version):
            errors.append("manifest version must be valid SemVer for specVersion 2")
    elif not _nonempty_string(version):
        errors.append("manifest version must be a non-empty string")

    if "minAppVersion" in data:
        minimum = data.get("minAppVersion")
        if spec_version == 2:
            if not is_semver(minimum):
                errors.append("manifest minAppVersion must be valid SemVer for specVersion 2")
        elif not _nonempty_string(minimum):
            errors.append("manifest minAppVersion must be a non-empty string")

    if "description" in data:
        _localized_string(
            data.get("description"),
            "manifest description",
            spec_version,
            errors,
            handled_t_objects,
            allow_empty_literal=True,
        )

    for field in ("entry", "cover"):
        if field in data and not is_safe_package_path(data.get(field)):
            errors.append(f"manifest {field} must be a safe package-relative path using forward slashes")
    scripts = data.get("scripts")
    if scripts is not None:
        if not isinstance(scripts, dict):
            errors.append("manifest scripts must be an object")
        elif "actions" in scripts and not is_safe_package_path(scripts.get("actions")):
            errors.append("manifest scripts.actions must be a safe package-relative path using forward slashes")

    localization_resources: list[tuple[str, str]] = []
    if spec_version == 2:
        localization = data.get("localization")
        if not isinstance(localization, dict):
            errors.append("manifest localization must be an object for specVersion 2")
        else:
            if not is_locale_tag(localization.get("defaultLocale")):
                errors.append("manifest localization.defaultLocale must be a valid hyphenated locale tag")
            resources = localization.get("resources", {})
            if not isinstance(resources, dict):
                errors.append("manifest localization.resources must be an object")
            else:
                for locale, resource in resources.items():
                    if not is_locale_tag(locale):
                        errors.append(f"manifest localization.resources locale is invalid: {locale!r}")
                    if not is_safe_package_path(resource):
                        errors.append(
                            f"manifest localization.resources[{locale!r}] must be a safe package-relative path "
                            "using forward slashes"
                        )
                    elif is_locale_tag(locale):
                        localization_resources.append((locale, resource))
    elif "localization" in data:
        errors.append("manifest localization requires specVersion 2")

    permissions = data.get("permissions")
    if permissions is not None and (
        not isinstance(permissions, list) or any(not _nonempty_string(item) for item in permissions)
    ):
        errors.append("manifest permissions must be an array of non-empty strings")

    contributes_value = data.get("contributes", {})
    if not isinstance(contributes_value, dict):
        errors.append("manifest contributes must be an object")
        contributes: dict[str, Any] = {}
    else:
        contributes = contributes_value

    contribution_lists: dict[str, list[Any]] = {}
    for key in ("inputActions", "sidebar", "htmlFragments"):
        raw_value = contributes.get(key, [])
        if not isinstance(raw_value, list):
            errors.append(f"manifest contributes.{key} must be an array")
            contribution_lists[key] = []
        else:
            contribution_lists[key] = raw_value

    for key in ("inputActions", "sidebar"):
        for index, action in enumerate(contribution_lists[key]):
            field = f"manifest contributes.{key}[{index}]"
            if not isinstance(action, dict):
                errors.append(f"{field} must be an object")
                continue
            if not _nonempty_string(action.get("id")):
                errors.append(f"{field}.id must be a non-empty string")
            if "label" not in action:
                errors.append(f"{field}.label is required")
            else:
                _localized_string(
                    action.get("label"),
                    f"{field}.label",
                    spec_version,
                    errors,
                    handled_t_objects,
                )
            if key == "inputActions" and "icon" in action and not is_safe_package_path(action.get("icon")):
                errors.append(f"{field}.icon must be a safe package-relative path using forward slashes")

    for index, fragment in enumerate(contribution_lists["htmlFragments"]):
        field = f"manifest contributes.htmlFragments[{index}]"
        if not isinstance(fragment, dict):
            errors.append(f"{field} must be an object")
        elif not is_safe_package_path(fragment.get("src")):
            errors.append(f"{field}.src must be a safe package-relative path using forward slashes")

    _validate_settings(contributes, spec_version, errors, handled_t_objects)
    _scan_unsupported_t_objects(data, "manifest", handled_t_objects, errors)

    return ManifestAnalysis(
        spec_version=spec_version,
        contributes=contributes,
        input_actions=contribution_lists["inputActions"],
        sidebar_actions=contribution_lists["sidebar"],
        html_fragments=contribution_lists["htmlFragments"],
        localization_resources=tuple(localization_resources),
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def validate_localization_catalogs(
    plugin_root: Path,
    analysis: ManifestAnalysis,
    errors: list[str],
) -> None:
    """Validate every declared spec-2 locale catalog relative to *plugin_root*."""

    for locale, resource in analysis.localization_resources:
        label = f"localization catalog {locale!r}"
        candidate = plugin_root.joinpath(*resource.split("/"))
        if not _is_within(candidate, plugin_root):
            errors.append(f"{label} resolves outside the selected plugin root: {resource}")
            continue
        if not candidate.exists():
            errors.append(f"{label} file does not exist: {resource}")
            continue
        if not candidate.is_file():
            errors.append(f"{label} must reference a regular file: {resource}")
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{label} must be valid UTF-8: {resource}")
            continue
        except OSError as exc:
            errors.append(f"{label} could not be read: {resource}: {exc}")
            continue
        try:
            catalog = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"{label} must contain valid JSON: {resource}: {exc.msg}")
            continue
        if not isinstance(catalog, dict):
            errors.append(f"{label} must contain a flat JSON object: {resource}")
            continue
        for key, value in catalog.items():
            if not isinstance(key, str) or not key:
                errors.append(f"{label} keys must be non-empty strings: {resource}")
            if not isinstance(value, str):
                errors.append(f"{label} values must be strings (catalogs are flat): {resource}")
