#!/usr/bin/env python3
"""Exercise Tavo 0.93 package rejection/selection on the actual install path."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import run_phone_plugin_093_live as shared  # noqa: E402
from run_phone_import_kpi import response_payload  # noqa: E402
from run_phone_kpi_batch import TavoMcp, load_endpoint  # noqa: E402


@dataclass(frozen=True)
class PackageCase:
    key: str
    data: bytes
    expected_ok: bool
    expected_plugin_id: str | None


def unsafe_entry_case(label: str, entry_name: str) -> PackageCase:
    plugin_id = f"t093.20260726.r1.package.zip.{label}"
    files = shared.full_files(plugin_id)
    files[entry_name] = b"T093 unsafe path canary"
    return PackageCase(f"zip-entry-{label}-rejected", shared.zip_bytes(files), False, None)


def cases() -> list[PackageCase]:
    result: list[PackageCase] = []
    positive_ids = {
        "single-wrapper-accepted": "t093.20260726.r1.package.wrapper",
        "root-package-accepted": "t093.20260726.r1.package.root",
    }
    for key, data, expected in shared.package_cases():
        result.append(PackageCase(key, data, expected, positive_ids.get(key)))
    result.extend(
        [
            unsafe_entry_case("traversal", "../escape.txt"),
            unsafe_entry_case("absolute", "/absolute.txt"),
            unsafe_entry_case("backslash", "folder\\file.txt"),
        ]
    )
    no_manifest_id = "t093.20260726.r1.package.no.manifest"
    result.append(
        PackageCase(
            "missing-manifest-rejected",
            shared.zip_bytes({"entry.js": b"// no manifest", "marker.txt": no_manifest_id.encode()}),
            False,
            None,
        )
    )
    sibling_id = "t093.20260726.r1.package.wrapper.sibling"
    sibling_files = {
        f"wrapper/{path}": data for path, data in shared.full_files(sibling_id).items()
    }
    sibling_files["outside-sibling.txt"] = b"must not be installed with selected wrapper root"
    result.append(
        PackageCase(
            "single-wrapper-with-sibling-accepted",
            shared.zip_bytes(sibling_files),
            True,
            sibling_id,
        )
    )
    return result


def manifest_ids(data: bytes) -> list[str]:
    found: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.replace("\\", "/").split("/")[-1] != "manifest.json":
                continue
            try:
                manifest = json.loads(archive.read(name).decode("utf-8"))
            except Exception:
                continue
            plugin_id = manifest.get("id") if isinstance(manifest, dict) else None
            if isinstance(plugin_id, str):
                found.append(plugin_id)
    return sorted(set(found))


def plan(run_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "runId": run_id,
        "cases": [
            {
                "key": case.key,
                "expectedOk": case.expected_ok,
                "expectedPluginId": case.expected_plugin_id,
                "candidatePluginIds": manifest_ids(case.data),
                "zipBytes": len(case.data),
                "zipSha256": hashlib.sha256(case.data).hexdigest(),
            }
            for case in cases()
        ],
        "onUnexpectedInstall": "disable-and-retain",
        "realModelRequestsSent": 0,
        "countsTowardKpi": False,
    }


def exact_search(client: TavoMcp, root: Path, plugin_id: str) -> list[dict[str, Any]]:
    return shared.exact_search(client, root, plugin_id)


def execute(args: argparse.Namespace) -> int:
    if not args.run_id.startswith("T093_"):
        raise RuntimeError("--run-id must start with T093_")
    artifact = Path(args.artifact_dir).expanduser().resolve()
    if artifact.exists() and any(artifact.iterdir()):
        raise RuntimeError("artifact directory must be fresh and empty")
    artifact.mkdir(parents=True, exist_ok=True, mode=0o700)
    artifact.chmod(0o700)
    record = plan(args.run_id)
    shared.durable_json(artifact / "plan.json", record)
    endpoint = load_endpoint(args.endpoint_json)
    url = args.url or str(endpoint.get("url") or "")
    auth = args.auth or str(endpoint.get("auth") or "")
    if not url:
        raise RuntimeError("missing MCP endpoint")
    client = TavoMcp(url, auth)
    initialize = client.rpc(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "t093-package-actual", "version": "1.0.0"},
        },
    )
    shared.durable_json(artifact / "gate" / "initialize.json", initialize)
    server_version = ((initialize.get("result") or {}).get("serverInfo") or {}).get("version")
    if server_version != "0.93.0":
        raise RuntimeError(f"server version drift: {server_version}")

    results: list[dict[str, Any]] = []
    retained: set[str] = set()
    for case in cases():
        root = artifact / "cases" / case.key
        candidates = manifest_ids(case.data)
        collisions: list[str] = []
        for plugin_id in candidates:
            if exact_search(client, root / "search-before" / f"{shared.stable_hash(plugin_id)[:12]}.json", plugin_id):
                collisions.append(plugin_id)
        if collisions:
            raise RuntimeError(f"plugin id collisions for {case.key}: {collisions}")

        encoded = base64.b64encode(case.data).decode("ascii")
        dry = shared.call_tool(
            client,
            root / "install-dry-run.json",
            "tavo_plugin_install",
            {"zipBase64": encoded, "dryRun": True},
        )
        dry_payload = response_payload(dry)
        dry_warnings = dry_payload.get("warnings") if isinstance(dry_payload, dict) else None

        actual_args = {"zipBase64": encoded, "dryRun": False}
        shared.write_intent(
            root / "install-intent.json",
            "plugin-install-actual-validation",
            case.key,
            shared.stable_hash(
                {
                    "zipSha256": hashlib.sha256(case.data).hexdigest(),
                    "dryRun": False,
                }
            ),
        )
        actual = shared.call_tool(
            client,
            root / "install-actual.json",
            "tavo_plugin_install",
            actual_args,
        )
        actual_ok = shared.response_ok(actual)

        installed_ids: list[str] = []
        response = response_payload(actual)
        response_id = response.get("pluginId") if isinstance(response, dict) else None
        ids_to_check = list(candidates)
        if isinstance(response_id, str) and response_id not in ids_to_check:
            ids_to_check.append(response_id)
        for plugin_id in ids_to_check:
            matches = exact_search(
                client,
                root / "search-after" / f"{shared.stable_hash(plugin_id)[:12]}.json",
                plugin_id,
            )
            if matches:
                installed_ids.append(plugin_id)
                retained.add(plugin_id)
                readback = shared.call_tool(
                    client,
                    root / "readback" / f"{shared.stable_hash(plugin_id)[:12]}.json",
                    "tavo_plugin_get",
                    {"pluginId": plugin_id},
                )
                readback_payload = response_payload(readback)
                if isinstance(readback_payload, dict) and readback_payload.get("enabled") is True:
                    shared.set_enabled(
                        client,
                        root / "disable-final" / f"{shared.stable_hash(plugin_id)[:12]}",
                        plugin_id,
                        False,
                    )

        expected_inventory = (
            [case.expected_plugin_id]
            if case.expected_ok and case.expected_plugin_id is not None
            else []
        )
        passed = actual_ok is case.expected_ok and sorted(installed_ids) == sorted(expected_inventory)
        result = {
            "key": case.key,
            "expectedOk": case.expected_ok,
            "actualOk": actual_ok,
            "expectedInstalledPluginIds": expected_inventory,
            "installedPluginIds": sorted(installed_ids),
            "dryRunWarnings": dry_warnings,
            "passed": passed,
            "zipBytes": len(case.data),
            "zipSha256": hashlib.sha256(case.data).hexdigest(),
        }
        shared.durable_json(root / "result.json", result)
        results.append(result)

    final_readbacks: list[dict[str, Any]] = []
    all_disabled = True
    for plugin_id in sorted(retained):
        response = shared.call_tool(
            client,
            artifact / "final" / "plugins" / f"{shared.stable_hash(plugin_id)[:12]}.json",
            "tavo_plugin_get",
            {"pluginId": plugin_id},
        )
        payload = response_payload(response)
        final_readbacks.append(
            {
                "pluginId": plugin_id,
                "enabled": payload.get("enabled") if isinstance(payload, dict) else None,
            }
        )
        all_disabled = all_disabled and isinstance(payload, dict) and payload.get("enabled") is False

    summary = {
        "status": "passed" if all(item["passed"] for item in results) and all_disabled else "failed",
        "total": len(results),
        "passed": sum(bool(item["passed"]) for item in results),
        "failed": [item["key"] for item in results if not item["passed"]],
        "retainedPlugins": final_readbacks,
        "retainedPluginsDisabled": all_disabled,
        "dryRunLimitationObserved": all(
            "Install dryRun validates input bytes only." in (item.get("dryRunWarnings") or [])
            for item in results
        ),
        "realModelRequestsSent": 0,
        "realProviderCredentialsUsed": False,
        "countsTowardKpi": False,
    }
    shared.durable_json(artifact / "run-manifest.json", {"planHash": shared.stable_hash(record), "results": results, "summary": summary})
    print(json.dumps({"artifactDir": str(artifact), "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "passed" else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run actual Tavo 0.93 package validation.")
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--print-plan", action="store_true")
    modes.add_argument("--execute", action="store_true")
    result.add_argument("--run-id", default="T093_20260726_R1_PLUGIN_PACKAGE")
    result.add_argument("--artifact-dir", default="")
    result.add_argument("--endpoint-json", default="/tmp/tavo_mcp_endpoint.json")
    result.add_argument("--url", default="")
    result.add_argument("--auth", default="")
    return result


def main() -> int:
    args = parser().parse_args()
    record = plan(args.run_id)
    if args.self_check:
        keys = [case["key"] for case in record["cases"]]
        if len(keys) != len(set(keys)):
            raise RuntimeError("duplicate package case")
        print(json.dumps({"ok": True, "planHash": shared.stable_hash(record), "plan": record}, ensure_ascii=False, indent=2))
        return 0
    if args.print_plan:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    if not args.artifact_dir:
        raise RuntimeError("--execute requires --artifact-dir")
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
