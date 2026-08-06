# Tavo 0.93 Live Evidence

Read this file whenever a current-product answer may depend on Tavo `0.93.0`. It is the current Android reliability overlay for the feature references. Older 0.91/0.92 evidence remains useful only for behavior that was not retested here and must keep its version label.

## Evidence Set

- Official docs: complete 83-page crawl from 2026-07-26 in `assets/official-docs/text-20260726/` and `assets/official-docs/official_manifest-20260726.json`.
- Strict redacted gate: `assets/evidence/0.93.0/20260726-gate.json`.
- Reusable live summary: `assets/evidence/0.93.0/20260726-zero-real-matrix.json`.
- Complete 216-case terminal map: `assets/evidence/0.93.0/20260726-case-outcomes.json`.
- Private source run: `artifacts/tavo-validation/20260726-t093-zero-real-r1/`.

The source run finished `complete-with-findings`: 74 passed, 8 failed, 38 mixed, 92 blocked, and 4 Android-not-applicable. Every case has a terminal status. Failed cases are retained in the machine map but are not promoted into positive capability claims.

## Zero-Real-Model Boundary

The run used a deterministic Mac provider with no upstream URL, no forwarding path, no real provider credential, and no real model request:

```json
{
  "providerMode": "virtual",
  "realModelRequestsSent": 0,
  "realProviderCredentialsUsed": false,
  "countsTowardKpi": false,
  "modelFormat": "not-evaluated",
  "modelSemantic": "not-evaluated"
}
```

Promote only protocol, request assembly, UI, persistence, import/export, backup, and direct runtime effects that have matching evidence. Never call a virtual response `semantic-pass`, model-format proof, real-provider compatibility, human ASR accuracy, audible TTS quality, or image-quality proof.

## Current Runtime Gate

On the authorized Android device, package `app.bitbear.tav` reported versionName `0.93.0` and versionCode `930`. The strict MCP gate passed:

- requested and negotiated protocol `2025-06-18`;
- 70 tools, 18 resources, 7 resource templates, 0 prompts;
- all five top-level discovery calls passed;
- every dynamically discovered docs/schema resource read passed;
- `tools/call -> tavo_status` passed;
- final server identity, surface counts, and surface hash matched the pre-write anchor.

Reusable evidence omits the device serial, private chat identity, endpoint, authentication value, backup contents, and provider credentials.

## Feature Overlay

| Area | Promoted 0.93 evidence | Boundary |
| --- | --- | --- |
| Plugin spec 2 | A minimal v2 plugin installed, read back, executed root `entry`, and finished disabled. Stable, prerelease, and build SemVer positives plus completed invalid-version negatives behaved as recorded. Localized manifest/catalog structures installed and rendered in the completed scope. | Do not infer that every unsafe package or localization negative is rejected. Use the exact case map for negative behavior. |
| Plugin persistence | A discriminating Backup B mutation restored the spec-2 plugin's exact config, disabled state, and zero runtime contributions. | This proves the tested plugin state, not every data family or downgrade restore. |
| Provider/request path | Local Chat Completions paths and bounded generation requests reached the deterministic provider with nonce/intent correlation and redacted metadata. | Responses, legacy Completions, all fault modes, and real providers were not all completed through app UI. |
| Fable 5 / Mythos 5 | Dedicated controls appeared and sentinel values survived reopen and app restart. | Proprietary wire fields and real endpoint behavior were not promoted. |
| ASR | OpenRouter appeared in the selector; OpenRouter/custom configurations persisted. Custom OpenAI multipart ASR captured model, language, prompt, response format, temperature, and WAV MIME/size/hash. A normal automated long press completed. | OpenRouter audio-chat wire, human accuracy, full gesture/fault matrix, and real provider compatibility remain unproved. |
| TTS | Provider configuration and test-key redaction persisted. One bounded role-target request captured model, voice, input, speed, and format against a fixed WAV. | Persona, rule matrix, queue-stop scheduling, speaker identity, sound quality, and audible stop are not blanket passes. |
| Image | Provider configuration persisted. Both `b64_json` and local-URL fixed PNG results completed through the tested imagine path. | Other entry points, multimodal attachment ordering, error matrix, quality, and real-provider compatibility remain separate. |
| Chat/UI fixes | Italic markdown followed by one space preserved that space in persistence, UI, reopen, and restart. A copied theme with a visibly non-default font survived save/reopen/restart, then the original theme was restored. | Do not generalize to every Markdown or font combination without a case. |
| Assets | Persona create/update/active/export/import/binding roundtrip completed. PNG embed/extract completed. | Character `character_book` preservation and the complete PNG import readback are not promoted. |
| Prompt/cross-feature | Thirty-four 0.93 cross-feature request-assembly/direct-runtime rows completed under the virtual-provider boundary. | The 34 prompt-edge rows and Advanced Rendering/TavoJS backlog did not gain semantic or visual proof from virtual responses. |
| Backup/restoration | Native Backup A and Backup B were created without opening their contents. Backup B and the separate spec-2 restore completed. Protected chat payload, input, primary API, preset, persona, theme, permissions, original plugin hashes, and original enabled states matched the anchor. | The sole retained test image-provider config could not be unset without deleting it; the primary chat API and all other protected state were restored. |
| Stability/privacy | The final process showed no retained crash, ANR, OOM, too-many-files, or HyperSentinel signal. Captures stored media metadata/hash only; the local service stopped and exact temporary targets were cleaned. | One run and one device do not prove multi-device or long-duration stability. |

## Plugin Spec 2 Authoring Contract

Use `specVersion: 2` for new plugins:

- `version` must be SemVer with `major.minor.patch`; prerelease and build metadata are supported.
- Optional `minAppVersion` must also be SemVer and is compared before installation.
- `localization.defaultLocale` is required for v2; `localization.resources` maps hyphenated locale tags to package-relative JSON catalogs.
- Omitted `specVersion` or explicit `1` remains a compatibility path but has no plugin-package i18n namespace.
- v2 `name`, optional `description`, contribution labels, supported setting labels/info text, structured select labels, and text/textarea defaults may use an exact `{ "$t": "key" }` object where the official contract allows it.
- Structured select options keep a stable non-localized `value` and may localize only `label`.
- Localized text/textarea defaults follow locale only while no user override exists; reset removes the override.
- `tavo.plugin.i18n` exposes live locale/default-locale getters, a defensive `supportedLocales` copy, synchronous `t(key, params?)`, and `onChange` for plugin-managed rerendering.

Use `assets/schemas/tpg-manifest.schema.json`, `scripts/tpg_spec2.py`, and `scripts/validate_tpg_package.py` for strict local authoring. Local validation is intentionally stricter than the current app in several recorded negative cases; do not weaken the validator to reproduce an unsafe live acceptance.

## 0.93 Validation Workflow

Use this order for another zero-real epoch:

1. Run all offline tests and both Skill audits.
2. Strictly identify one Android device, Tavo package/version, MCP identity, dynamic resources, and current protected state.
3. Create Backup A before any write.
4. Write a durable intent before every mutation; on resume, reconcile before sending again.
5. Bind each request case to one local fixture ID with real fallback disabled.
6. Correlate nonce, intent hash, request count, retries, disconnects, and stable chat/message IDs.
7. Keep raw audio, image bodies, base64, secrets, and backup contents out of reusable evidence.
8. Create Backup B only after lower-risk cases stabilize.
9. Restore and compare protected state, stop local services, clean exact temporary targets, and rerun the strict ADB/MCP gate.

The reusable runners are `scripts/run_phone_093_master.py`, `scripts/run_phone_plugin_093_live.py`, `scripts/run_phone_plugin_093_package_actual.py`, `scripts/tavo_virtual_provider.py`, and `scripts/tavo_fixture_capture_assert.py`.
