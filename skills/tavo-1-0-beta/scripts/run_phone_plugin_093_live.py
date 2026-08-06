#!/usr/bin/env python3
"""Live Tavo 0.93 spec-2 plugin validation with retained, disabled fixtures.

Offline modes never contact MCP. Live execution uses a fresh artifact directory,
records every mutation intent before sending it, never retries an unresolved
intent, retains installed fixtures, and disables them before returning.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
import os
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT = "/tmp/tavo_mcp_endpoint.json"

sys.path.insert(0, str(ROOT / "scripts"))

from run_phone_import_kpi import response_payload  # noqa: E402
from run_phone_kpi_batch import TavoMcp, load_endpoint, ok_response, redact  # noqa: E402


REQUIRED_TOOLS = {
    "tavo_plugin_get",
    "tavo_plugin_get_runtime_contributions",
    "tavo_plugin_install",
    "tavo_plugin_package",
    "tavo_plugin_reset_config",
    "tavo_plugin_search",
    "tavo_plugin_set_config",
    "tavo_plugin_set_enabled",
    "tavo_plugin_validate_manifest",
}


@dataclass(frozen=True)
class ManifestCase:
    key: str
    manifest: dict[str, Any]
    expected_ok: bool


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def durable_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def response_ok(response: dict[str, Any]) -> bool:
    payload = response_payload(response)
    return ok_response(response) and isinstance(payload, dict) and payload.get("ok") is not False


def base_v2(plugin_id: str = "t093.20260726.r1.validation.probe") -> dict[str, Any]:
    return {
        "id": plugin_id,
        "name": {"$t": "plugin.name"},
        "version": "1.0.0",
        "specVersion": 2,
        "minAppVersion": "0.93.0",
        "description": {"$t": "plugin.description"},
        "localization": {"defaultLocale": "en"},
    }


def full_v2(plugin_id: str, version: str = "1.0.0") -> dict[str, Any]:
    manifest = base_v2(plugin_id)
    manifest.update(
        {
            "version": version,
            "entry": "entry.js",
            "permissions": ["input"],
            "localization": {
                "defaultLocale": "en",
                "resources": {
                    "en": "locales/en.json",
                    "zh-CN": "locales/zh-CN.json",
                },
            },
            "contributes": {
                "inputActions": [
                    {"id": "insert-marker", "label": {"$t": "actions.insertMarker"}},
                ],
                "sidebar": [
                    {"id": "sidebar-marker", "label": {"$t": "actions.sidebarMarker"}},
                ],
                "htmlFragments": [
                    {
                        "id": "chat-panel",
                        "src": "ui/panel.html",
                        "mount": "/chat/body/end",
                    },
                    {
                        "id": "message-panel",
                        "src": "ui/message.html",
                        "mount": "/messages/end?role=character&position=last",
                    },
                ],
                "settings": {
                    "schema": [
                        {"type": "info", "text": {"$t": "settings.info"}},
                        {
                            "key": "enabled",
                            "type": "switch",
                            "label": {"$t": "settings.enabled"},
                            "default": True,
                        },
                        {
                            "key": "mode",
                            "type": "select",
                            "label": {"$t": "settings.mode.label"},
                            "default": "brief",
                            "options": [
                                {"value": "brief", "label": {"$t": "settings.mode.brief"}},
                                {"value": "detailed", "label": {"$t": "settings.mode.detailed"}},
                            ],
                        },
                        {
                            "key": "template",
                            "type": "textarea",
                            "label": {"$t": "settings.template.label"},
                            "default": {"$t": "settings.template.default"},
                        },
                        {
                            "key": "single",
                            "type": "text",
                            "label": {"$t": "settings.single.label"},
                            "default": {"$t": "settings.single.default"},
                        },
                    ]
                },
            },
        }
    )
    return manifest


def manifest_cases() -> list[ManifestCase]:
    cases: list[ManifestCase] = []

    v1_omitted = {"id": "t093.20260726.r1.v1.omitted", "name": "T093 v1 omitted", "version": "legacy-version"}
    cases.append(ManifestCase("v1-omitted-compatible", v1_omitted, True))
    v1_explicit = dict(v1_omitted, id="t093.20260726.r1.v1.explicit", specVersion=1)
    cases.append(ManifestCase("v1-explicit-compatible", v1_explicit, True))

    for label, version in (
        ("stable", "1.2.3"),
        ("prerelease", "1.2.3-rc.1"),
        ("build", "1.2.3+build.7"),
    ):
        manifest = base_v2(f"t093.20260726.r1.semver.{label}")
        manifest["version"] = version
        cases.append(ManifestCase(f"semver-valid-{label}", manifest, True))

    for label, version in (
        ("v-prefix", "v1.2.3"),
        ("short", "1.2"),
        ("leading-zero", "01.2.3"),
        ("bad-prerelease", "1.2.3-rc_1"),
    ):
        manifest = base_v2(f"t093.20260726.r1.semver.bad.{label}")
        manifest["version"] = version
        cases.append(ManifestCase(f"semver-invalid-{label}", manifest, False))

    for label, minimum in (
        ("lower", "0.92.0"),
        ("equal", "0.93.0"),
        ("higher-syntax", "0.94.0"),
        ("prerelease", "0.93.0-rc.1"),
        ("build", "0.93.0+build.7"),
    ):
        manifest = base_v2(f"t093.20260726.r1.min.{label}")
        manifest["minAppVersion"] = minimum
        cases.append(ManifestCase(f"min-app-{label}", manifest, True))

    spec3 = base_v2("t093.20260726.r1.spec3")
    spec3["specVersion"] = 3
    cases.append(ManifestCase("spec-version-3-rejected", spec3, False))
    missing_localization = base_v2("t093.20260726.r1.missing.localization")
    del missing_localization["localization"]
    cases.append(ManifestCase("v2-missing-localization-rejected", missing_localization, False))

    zh_cn = base_v2("t093.20260726.r1.locale.bad")
    zh_cn["localization"] = {"defaultLocale": "zh_CN"}
    cases.append(ManifestCase("locale-underscore-rejected", zh_cn, False))
    zh_hyphen = base_v2("t093.20260726.r1.locale.good")
    zh_hyphen["localization"] = {"defaultLocale": "zh-CN"}
    cases.append(ManifestCase("locale-hyphen-accepted", zh_hyphen, True))

    valid_t = full_v2("t093.20260726.r1.t.valid")
    cases.append(ManifestCase("t-object-valid-positions", valid_t, True))
    empty_t = base_v2("t093.20260726.r1.t.empty")
    empty_t["name"] = {"$t": ""}
    cases.append(ManifestCase("t-object-empty-key-rejected", empty_t, False))
    extra_t = base_v2("t093.20260726.r1.t.extra")
    extra_t["name"] = {"$t": "plugin.name", "extra": True}
    cases.append(ManifestCase("t-object-extra-field-rejected", extra_t, False))
    unsupported_t = base_v2("t093.20260726.r1.t.unsupported")
    unsupported_t["author"] = {"$t": "plugin.author"}
    cases.append(ManifestCase("t-object-unsupported-position-rejected", unsupported_t, False))

    for label, entry in (
        ("backslash", "folder\\entry.js"),
        ("absolute", "/entry.js"),
        ("traversal", "../entry.js"),
    ):
        manifest = base_v2(f"t093.20260726.r1.path.{label}")
        manifest["entry"] = entry
        cases.append(ManifestCase(f"path-{label}-rejected", manifest, False))

    return cases


def locale_catalog(locale: str) -> dict[str, str]:
    if locale == "zh-CN":
        return {
            "plugin.name": "T093 规范二验证插件",
            "plugin.description": "T093 插件国际化实机验证。",
            "actions.insertMarker": "T093 插入本地化标记",
            "actions.sidebarMarker": "T093 侧栏本地化标记",
            "settings.info": "T093 国际化设置",
            "settings.enabled": "启用",
            "settings.mode.label": "模式",
            "settings.mode.brief": "简短",
            "settings.mode.detailed": "详细",
            "settings.template.label": "模板",
            "settings.template.default": "记住：",
            "settings.single.label": "单行",
            "settings.single.default": "本地化默认值",
            "runtime.input": "T093_20260726_R1_I18N_INPUT",
            "runtime.sidebar": "T093_20260726_R1_I18N_SIDEBAR",
            "runtime.panel": "T093 插件面板",
        }
    return {
        "plugin.name": "T093 Spec 2 Validation Plugin",
        "plugin.description": "T093 on-device plugin internationalization validation.",
        "actions.insertMarker": "T093 Insert Localized Marker",
        "actions.sidebarMarker": "T093 Sidebar Localized Marker",
        "settings.info": "T093 localized settings",
        "settings.enabled": "Enabled",
        "settings.mode.label": "Mode",
        "settings.mode.brief": "Brief",
        "settings.mode.detailed": "Detailed",
        "settings.template.label": "Template",
        "settings.template.default": "Remember:",
        "settings.single.label": "Single line",
        "settings.single.default": "Localized default",
        "runtime.input": "T093_20260726_R1_I18N_INPUT",
        "runtime.sidebar": "T093_20260726_R1_I18N_SIDEBAR",
        "runtime.panel": "T093 plugin panel",
    }


def entry_js() -> str:
    return """\
tavo.plugin.onInputAction("insert-marker", async () => {
  await tavo.input.append(tavo.plugin.i18n.t("runtime.input"));
});
tavo.plugin.onSidebarAction("sidebar-marker", async () => {
  await tavo.input.append(tavo.plugin.i18n.t("runtime.sidebar"));
});
"""


def panel_html(message_scope: bool = False) -> str:
    current = (
        "const current = await tavo.message.current(); root.dataset.messageId = String(current && current.id || 'none');"
        if message_scope
        else ""
    )
    return f"""\
<div data-t093-plugin-panel="true"><span></span><button type="button">T093</button>
<script>(async () => {{
  const root = document.currentScript.closest('[data-t093-plugin-panel="true"]');
  const render = () => root.querySelector('span').textContent = tavo.plugin.i18n.t('runtime.panel');
  render(); tavo.plugin.i18n.onChange(render); {current}
}})();</script></div>
"""


def full_files(plugin_id: str, version: str = "1.0.0") -> dict[str, bytes]:
    manifest = full_v2(plugin_id, version)
    return {
        "manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        "entry.js": entry_js().encode(),
        "locales/en.json": (json.dumps(locale_catalog("en"), ensure_ascii=False, indent=2) + "\n").encode(),
        "locales/zh-CN.json": (json.dumps(locale_catalog("zh-CN"), ensure_ascii=False, indent=2) + "\n").encode(),
        "ui/panel.html": panel_html(False).encode(),
        "ui/message.html": panel_html(True).encode(),
    }


def zip_bytes(files: dict[str, bytes], *, symlink: tuple[str, str] | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 7, 26, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, files[name])
        if symlink is not None:
            name, target = symlink
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 7, 26, 0, 0, 0)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, target)
    return output.getvalue()


def package_cases() -> list[tuple[str, bytes, bool]]:
    cases: list[tuple[str, bytes, bool]] = []

    higher = full_files("t093.20260726.r1.package.min.high")
    high_manifest = json.loads(higher["manifest.json"])
    high_manifest["minAppVersion"] = "0.94.0"
    higher["manifest.json"] = (json.dumps(high_manifest) + "\n").encode()
    cases.append(("min-app-higher-install-rejected", zip_bytes(higher), False))

    missing_entry = full_files("t093.20260726.r1.package.missing.entry")
    del missing_entry["entry.js"]
    cases.append(("missing-entry-rejected", zip_bytes(missing_entry), False))

    missing_catalog = full_files("t093.20260726.r1.package.missing.catalog")
    del missing_catalog["locales/zh-CN.json"]
    cases.append(("missing-catalog-rejected", zip_bytes(missing_catalog), False))

    catalog_variants: list[tuple[str, bytes]] = [
        ("catalog-bad-utf8", b"\xff\xfe"),
        ("catalog-bad-json", b"{"),
        ("catalog-non-object", b"[]"),
        ("catalog-nested-value", b'{"bad":{"nested":"value"}}'),
        ("catalog-empty-key", b'{"":"value"}'),
        ("catalog-non-string-value", b'{"bad":7}'),
    ]
    for label, catalog in catalog_variants:
        files = full_files(f"t093.20260726.r1.package.{label}")
        files["locales/zh-CN.json"] = catalog
        cases.append((f"{label}-rejected", zip_bytes(files), False))

    wrapper_files = {f"wrapper/{path}": data for path, data in full_files("t093.20260726.r1.package.wrapper").items()}
    cases.append(("single-wrapper-accepted", zip_bytes(wrapper_files), True))

    ambiguous: dict[str, bytes] = {}
    for prefix in ("one", "two"):
        for path, data in full_files(f"t093.20260726.r1.package.ambiguous.{prefix}").items():
            ambiguous[f"{prefix}/{path}"] = data
    cases.append(("ambiguous-wrapper-rejected", zip_bytes(ambiguous), False))

    symlink_files = full_files("t093.20260726.r1.package.symlink")
    cases.append(("external-symlink-rejected", zip_bytes(symlink_files, symlink=("escape", "../../outside")), False))

    root_canary = full_files("t093.20260726.r1.package.root")
    root_canary["outside/ignored.txt"] = b"outside selected plugin root"
    cases.append(("root-package-accepted", zip_bytes(root_canary), True))
    return cases


def call_tool(client: TavoMcp, path: Path, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = client.tool(name, arguments, timeout=120)
    durable_json(path, response)
    return response


def write_intent(path: Path, operation: str, target: str, arguments_hash: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to reuse mutation intent: {path}")
    durable_json(
        path,
        {
            "status": "durable-intent",
            "operation": operation,
            "target": target,
            "argumentsSha256": arguments_hash,
            "retryPolicy": "never-silent",
        },
    )


def package_with_tool(client: TavoMcp, root: Path, files: dict[str, bytes]) -> str:
    payload_files = [
        {"path": path, "text": data.decode("utf-8")}
        for path, data in sorted(files.items())
    ]
    dry = call_tool(
        client,
        root / "package-dry-run.json",
        "tavo_plugin_package",
        {"files": payload_files, "includeZipBase64": True, "dryRun": True},
    )
    if not response_ok(dry):
        raise RuntimeError("plugin package dry-run failed")
    arguments = {"files": payload_files, "includeZipBase64": True, "dryRun": False}
    write_intent(root / "package-intent.json", "plugin-package", "in-memory-files", stable_hash(arguments))
    actual = client.tool("tavo_plugin_package", arguments, timeout=120)
    payload = response_payload(actual)
    zip_base64 = payload.get("zipBase64") if isinstance(payload, dict) else None
    durable_json(
        root / "package-actual-metadata.json",
        {
            "ok": response_ok(actual),
            "zipBase64Length": len(zip_base64) if isinstance(zip_base64, str) else 0,
            "zipSha256": hashlib.sha256(base64.b64decode(zip_base64)).hexdigest() if isinstance(zip_base64, str) else None,
        },
    )
    if not response_ok(actual) or not isinstance(zip_base64, str):
        raise RuntimeError("plugin package did not return zipBase64")
    return zip_base64


def exact_search(client: TavoMcp, root: Path, plugin_id: str) -> list[dict[str, Any]]:
    response = call_tool(
        client,
        root,
        "tavo_plugin_search",
        {"query": plugin_id, "match": "exact", "limit": 10, "cursor": 0},
    )
    payload = response_payload(response)
    items = payload.get("items") if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict) and item.get("pluginId") == plugin_id]


def install_actual(client: TavoMcp, root: Path, plugin_id: str, zip_base64: str) -> dict[str, Any]:
    if exact_search(client, root / "search-before.json", plugin_id):
        raise RuntimeError(f"plugin id collision: {plugin_id}")
    dry_args = {"zipBase64": zip_base64, "dryRun": True}
    dry = call_tool(client, root / "install-dry-run.json", "tavo_plugin_install", dry_args)
    if not response_ok(dry) or exact_search(client, root / "search-after-dry.json", plugin_id):
        raise RuntimeError("plugin install dry-run failed or changed inventory")
    actual_args = {"zipBase64": zip_base64, "dryRun": False}
    write_intent(root / "install-intent.json", "plugin-install", plugin_id, stable_hash(actual_args))
    actual = call_tool(client, root / "install-actual.json", "tavo_plugin_install", actual_args)
    if not response_ok(actual):
        raise RuntimeError(f"plugin install failed: {plugin_id}")
    readback = call_tool(client, root / "readback.json", "tavo_plugin_get", {"pluginId": plugin_id})
    payload = response_payload(readback)
    if not isinstance(payload, dict) or payload.get("pluginId") != plugin_id:
        raise RuntimeError(f"plugin readback mismatch: {plugin_id}")
    return payload


def set_enabled(client: TavoMcp, root: Path, plugin_id: str, enabled: bool) -> dict[str, Any]:
    dry_args = {"pluginId": plugin_id, "enabled": enabled, "dryRun": True}
    dry = call_tool(client, root / "dry-run.json", "tavo_plugin_set_enabled", dry_args)
    if not response_ok(dry):
        raise RuntimeError("plugin enabled dry-run failed")
    actual_args = {"pluginId": plugin_id, "enabled": enabled, "dryRun": False}
    write_intent(root / "intent.json", "plugin-set-enabled", plugin_id, stable_hash(actual_args))
    actual = call_tool(client, root / "actual.json", "tavo_plugin_set_enabled", actual_args)
    readback = call_tool(client, root / "readback.json", "tavo_plugin_get", {"pluginId": plugin_id})
    payload = response_payload(readback)
    if not response_ok(actual) or not isinstance(payload, dict) or payload.get("enabled") is not enabled:
        raise RuntimeError("plugin enabled readback mismatch")
    return payload


def set_config(client: TavoMcp, root: Path, plugin_id: str, key: str, value: Any) -> dict[str, Any]:
    dry_args = {"pluginId": plugin_id, "key": key, "value": value, "dryRun": True}
    dry = call_tool(client, root / "dry-run.json", "tavo_plugin_set_config", dry_args)
    if not response_ok(dry):
        raise RuntimeError("plugin config dry-run failed")
    actual_args = {"pluginId": plugin_id, "key": key, "value": value, "dryRun": False}
    write_intent(root / "intent.json", "plugin-set-config", plugin_id, stable_hash(actual_args))
    actual = call_tool(client, root / "actual.json", "tavo_plugin_set_config", actual_args)
    readback = call_tool(client, root / "readback.json", "tavo_plugin_get", {"pluginId": plugin_id})
    payload = response_payload(readback)
    config = payload.get("config") if isinstance(payload, dict) else None
    if not response_ok(actual) or not isinstance(config, dict) or config.get(key) != value:
        raise RuntimeError("plugin config readback mismatch")
    return payload


def reset_config(client: TavoMcp, root: Path, plugin_id: str) -> dict[str, Any]:
    dry_args = {"pluginId": plugin_id, "dryRun": True}
    dry = call_tool(client, root / "dry-run.json", "tavo_plugin_reset_config", dry_args)
    if not response_ok(dry):
        raise RuntimeError("plugin reset dry-run failed")
    actual_args = {"pluginId": plugin_id, "dryRun": False}
    write_intent(root / "intent.json", "plugin-reset-config", plugin_id, stable_hash(actual_args))
    actual = call_tool(client, root / "actual.json", "tavo_plugin_reset_config", actual_args)
    readback = call_tool(client, root / "readback.json", "tavo_plugin_get", {"pluginId": plugin_id})
    if not response_ok(actual):
        raise RuntimeError("plugin reset failed")
    return response_payload(readback)


def legacy_files(plugin_id: str) -> dict[str, bytes]:
    manifest = {
        "id": plugin_id,
        "name": "T093_20260726_R1_PLUGIN_MIGRATION",
        "version": "legacy-version",
        "specVersion": 1,
        "entry": "entry.js",
        "permissions": ["input"],
        "features": ["settings"],
        "settingsSchema": [
            {"key": "mode", "type": "text", "label": "Mode", "default": "legacy-default"}
        ],
    }
    return {
        "manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        "entry.js": b"// retained v1 compatibility fixture\n",
    }


def plan_record(run_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "runId": run_id,
        "realModelRequestsSent": 0,
        "countsTowardKpi": False,
        "manifestCases": [
            {"key": case.key, "expectedOk": case.expected_ok, "manifestSha256": stable_hash(case.manifest)}
            for case in manifest_cases()
        ],
        "packageCases": [
            {"key": key, "expectedOk": expected, "zipBytes": len(data), "zipSha256": hashlib.sha256(data).hexdigest()}
            for key, data, expected in package_cases()
        ],
        "retainedPlugins": [
            "t093.20260726.r1.spec2.main",
            "t093.20260726.r1.migration",
        ],
    }


def self_check(run_id: str) -> dict[str, Any]:
    plan = plan_record(run_id)
    if len({item["key"] for item in plan["manifestCases"]}) != len(plan["manifestCases"]):
        raise RuntimeError("duplicate manifest case key")
    if len({item["key"] for item in plan["packageCases"]}) != len(plan["packageCases"]):
        raise RuntimeError("duplicate package case key")
    for _, data, _ in package_cases():
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if not archive.namelist():
                raise RuntimeError("empty package case")
    return {"ok": True, "planHash": stable_hash(plan), "plan": plan}


def execute(args: argparse.Namespace) -> int:
    run_id = args.run_id
    if not run_id.startswith("T093_"):
        raise RuntimeError("--run-id must start with T093_")
    artifact = Path(args.artifact_dir).expanduser().resolve()
    if artifact.exists() and any(artifact.iterdir()):
        raise RuntimeError("artifact directory must be fresh and empty")
    artifact.mkdir(parents=True, exist_ok=True, mode=0o700)
    artifact.chmod(0o700)
    plan = plan_record(run_id)
    durable_json(artifact / "plan.json", plan)
    endpoint = load_endpoint(args.endpoint_json)
    url = args.url or str(endpoint.get("url") or "")
    auth = args.auth or str(endpoint.get("auth") or "")
    if not url:
        raise RuntimeError("missing MCP endpoint")
    client = TavoMcp(url, auth)
    tools = client.rpc("tools/list", {})
    durable_json(artifact / "gate" / "tools-list.json", tools)
    direct = tools.get("result") if isinstance(tools, dict) else {}
    tool_names = {
        item.get("name")
        for item in direct.get("tools", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    missing = sorted(REQUIRED_TOOLS - tool_names)
    initialize = client.rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "t093-plugin-live", "version": "1.0.0"},
        },
    )
    durable_json(artifact / "gate" / "initialize.json", initialize)
    server_version = ((initialize.get("result") or {}).get("serverInfo") or {}).get("version")
    if missing or server_version != "0.93.0":
        raise RuntimeError(f"strict gate failed: missing={missing}, serverVersion={server_version}")

    results: list[dict[str, Any]] = []
    for case in manifest_cases():
        response = call_tool(
            client,
            artifact / "manifest-cases" / case.key / "response.json",
            "tavo_plugin_validate_manifest",
            {"manifest": case.manifest},
        )
        actual = response_ok(response)
        result = {
            "key": case.key,
            "expectedOk": case.expected_ok,
            "actualOk": actual,
            "passed": actual is case.expected_ok,
            "manifestSha256": stable_hash(case.manifest),
        }
        durable_json(artifact / "manifest-cases" / case.key / "result.json", result)
        results.append(result)

    package_results: list[dict[str, Any]] = []
    for key, data, expected in package_cases():
        zip_base64 = base64.b64encode(data).decode("ascii")
        response = call_tool(
            client,
            artifact / "package-cases" / key / "install-dry-run.json",
            "tavo_plugin_install",
            {"zipBase64": zip_base64, "dryRun": True},
        )
        actual = response_ok(response)
        result = {
            "key": key,
            "expectedOk": expected,
            "actualOk": actual,
            "passed": actual is expected,
            "zipBytes": len(data),
            "zipSha256": hashlib.sha256(data).hexdigest(),
        }
        durable_json(artifact / "package-cases" / key / "result.json", result)
        package_results.append(result)

    main_id = "t093.20260726.r1.spec2.main"
    main_root = artifact / "installed" / "spec2-main"
    main_zip = package_with_tool(client, main_root / "package", full_files(main_id))
    main_readback = install_actual(client, main_root / "install", main_id, main_zip)
    if int((main_readback.get("manifest") or {}).get("specVersion") or 0) != 2:
        raise RuntimeError("spec2 plugin readback lost specVersion")
    set_enabled(client, main_root / "enable", main_id, True)
    runtime = call_tool(
        client,
        main_root / "runtime-enabled.json",
        "tavo_plugin_get_runtime_contributions",
        {},
    )
    runtime_text = json.dumps(response_payload(runtime), ensure_ascii=False)
    if main_id not in runtime_text:
        raise RuntimeError("enabled spec2 plugin missing runtime contributions")
    set_config(client, main_root / "config-sentinel", main_id, "mode", "detailed")
    reset = reset_config(client, main_root / "config-reset", main_id)
    resolved = reset.get("resolvedConfig") if isinstance(reset, dict) else {}
    if not isinstance(resolved, dict) or resolved.get("mode") != "brief":
        raise RuntimeError("spec2 config reset did not restore default")
    set_enabled(client, main_root / "disable-final", main_id, False)

    migration_id = "t093.20260726.r1.migration"
    migration_root = artifact / "installed" / "migration"
    v1_zip = package_with_tool(client, migration_root / "v1-package", legacy_files(migration_id))
    install_actual(client, migration_root / "v1-install", migration_id, v1_zip)
    set_config(client, migration_root / "v1-config", migration_id, "mode", "T093_SENTINEL")
    set_enabled(client, migration_root / "v1-enable", migration_id, True)
    v2_zip = package_with_tool(client, migration_root / "v2-package", full_files(migration_id, "1.0.0"))
    update_args = {"zipBase64": v2_zip, "dryRun": True}
    update_dry = call_tool(client, migration_root / "v2-install-dry-run.json", "tavo_plugin_install", update_args)
    if not response_ok(update_dry):
        raise RuntimeError("v1 to v2 update dry-run failed")
    update_actual_args = {"zipBase64": v2_zip, "dryRun": False}
    write_intent(
        migration_root / "v2-install-intent.json",
        "plugin-update-v1-to-v2",
        migration_id,
        stable_hash(update_actual_args),
    )
    update_actual = call_tool(
        client,
        migration_root / "v2-install-actual.json",
        "tavo_plugin_install",
        update_actual_args,
    )
    if not response_ok(update_actual):
        raise RuntimeError("v1 to v2 update failed")
    migration_readback_response = call_tool(
        client,
        migration_root / "v2-readback.json",
        "tavo_plugin_get",
        {"pluginId": migration_id},
    )
    migration_readback = response_payload(migration_readback_response)
    preserved = {
        "specVersion": (migration_readback.get("manifest") or {}).get("specVersion"),
        "enabled": migration_readback.get("enabled"),
        "mode": (migration_readback.get("config") or {}).get("mode"),
    }
    durable_json(migration_root / "preservation-result.json", preserved)
    if preserved != {"specVersion": 2, "enabled": True, "mode": "T093_SENTINEL"}:
        raise RuntimeError(f"v1 to v2 preservation mismatch: {preserved}")
    set_enabled(client, migration_root / "disable-final", migration_id, False)

    final_main = call_tool(client, artifact / "final" / "main.json", "tavo_plugin_get", {"pluginId": main_id})
    final_migration = call_tool(
        client,
        artifact / "final" / "migration.json",
        "tavo_plugin_get",
        {"pluginId": migration_id},
    )
    final_runtime = call_tool(
        client,
        artifact / "final" / "runtime.json",
        "tavo_plugin_get_runtime_contributions",
        {},
    )
    final_payloads = [response_payload(final_main), response_payload(final_migration)]
    final_disabled = all(isinstance(item, dict) and item.get("enabled") is False for item in final_payloads)
    final_runtime_text = json.dumps(response_payload(final_runtime), ensure_ascii=False)
    final_absent = main_id not in final_runtime_text and migration_id not in final_runtime_text

    summary = {
        "status": "passed"
        if all(item["passed"] for item in results + package_results) and final_disabled and final_absent
        else "failed",
        "manifestCases": {
            "total": len(results),
            "passed": sum(bool(item["passed"]) for item in results),
            "failed": [item["key"] for item in results if not item["passed"]],
        },
        "packageCases": {
            "total": len(package_results),
            "passed": sum(bool(item["passed"]) for item in package_results),
            "failed": [item["key"] for item in package_results if not item["passed"]],
        },
        "mainSpec2Installed": True,
        "migrationPreserved": preserved,
        "fixturesRetained": [main_id, migration_id],
        "fixturesDisabled": final_disabled,
        "runtimeContributionsAbsentFinal": final_absent,
        "realModelRequestsSent": 0,
        "realProviderCredentialsUsed": False,
        "countsTowardKpi": False,
        "modelFormat": "not-evaluated",
        "modelSemantic": "not-evaluated",
    }
    durable_json(artifact / "run-manifest.json", {"planHash": stable_hash(plan), "summary": summary})
    for directory, _, filenames in os.walk(artifact):
        Path(directory).chmod(0o700)
        for filename in filenames:
            Path(directory, filename).chmod(0o600)
    print(json.dumps({"artifactDir": str(artifact), "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "passed" else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run the Tavo 0.93 live plugin matrix.")
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--print-plan", action="store_true")
    modes.add_argument("--execute", action="store_true")
    result.add_argument("--run-id", default="T093_20260726_R1_PLUGIN")
    result.add_argument("--artifact-dir", default="")
    result.add_argument("--endpoint-json", default=DEFAULT_ENDPOINT)
    result.add_argument("--url", default="")
    result.add_argument("--auth", default="")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.self_check:
        print(json.dumps(self_check(args.run_id), ensure_ascii=False, indent=2))
        return 0
    if args.print_plan:
        print(json.dumps(plan_record(args.run_id), ensure_ascii=False, indent=2))
        return 0
    if not args.artifact_dir:
        raise RuntimeError("--execute requires --artifact-dir")
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
