# Phone Validation Runbook

This runbook fixes the real Android test method for Tavo. Do not rediscover the phone workflow from scratch unless the device, app, or MCP server changes in a way that invalidates this evidence.

## Current 1.0 Gate And User-State Anchor

`live-verified` redacted gate: `assets/evidence/1.0.0/20260807-gate.json`. Current incremental behavior summary: `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`.

- One authorized Android device and package `app.bitbear.tav`, versionName `1.0.0`.
- MCP 72 tools, 19 resources, 7 templates, 0 prompts; five top-level reads, all dynamically discovered docs/schema reads, and `tavo_status` passed.
- Requested and negotiated protocol were `2025-06-18`.
- Capture the actual current chat payload, input, API, preset, persona, theme, voice/ASR/bindings, tool switches, permissions, plugin hashes/enabled states, PID, and resource baseline dynamically. Reusable Skill evidence must not hardcode private chat identity, LAN endpoint, authorization value, provider key, or device serial.
- The 1.0 gate is transport/readiness evidence only. Promote behavior only from the incremental matrix and keep broad unrerun claims on their prior-version evidence.

The 0.93 gate and 216-case matrix remain the latest broad zero-real baseline: `assets/evidence/0.93.0/20260726-gate.json`, `assets/evidence/0.93.0/20260726-zero-real-matrix.json`, and `assets/evidence/0.93.0/20260726-case-outcomes.json`.

## Prior 0.92 And 0.91 Method Baseline

The detailed 0.92 Hook/media/plugin method remains in `assets/evidence/0.92.0/20260717-live-matrix.json`. Reuse it only when the current app still exposes the same contract and neither the 0.93 nor 1.0 overlay retested that exact behavior.

- Device serial: private and omitted from public evidence.
- Device model: `24129PN74C`.
- Android version: `16`.
- Screen: `1200x2670`, density `520`.
- Package: `app.bitbear.tav`.
- App version during that smoke: `0.91.0`; use only as a prior-version regression control.
- UI framework: Flutter UI readable through UIAutomator for chat title, messages, input hint, focus state, and button bounds.
- MCP surface during smoke: `70` tools, `18` resources, `7` resource templates, `0` prompts. Versions 0.92 and 0.93 happened to match; 1.0 changed to 72/19/7/0, so capability content must always come from the versioned gate/docs.
- Accessibility service: not enabled during smoke. Record as blocked and use UI-tree bounds plus ADB tap.

## Required Preflight

Run these before any live validation case:

```bash
adb devices -l
adb -s <authorized-serial> shell dumpsys package app.bitbear.tav
adb -s <authorized-serial> shell dumpsys window
adb -s <authorized-serial> shell uiautomator dump /sdcard/window.xml
adb -s <authorized-serial> exec-out screencap -p > screen-before.png
python3 scripts/dump_mcp_surface.py --strict --output <artifact-dir>
```

The strict gate must include `initialize`, `tools/list`, `resources/list`, `resources/templates/list`, `prompts/list`, all dynamically discovered docs/schema/capabilities/runtime reads, and one `tools/call -> tavo_status`. Save requested and negotiated protocol versions separately.

If the phone was asleep, recheck ICMP/TCP reachability and rerun MCP initialize after the screen wakes. Never reuse an old endpoint/token without rereading the current phone state.

## Operation Priority

1. MCP for state, dry-run, import, readback, binding, current-chat switching, and message send/read.
2. Ask the user to perform the smallest necessary GUI action when a native picker, provider/model choice, permission prompt, tool switch, or visual confirmation has no MCP path.
3. Use MCP again immediately after the user action for sends, state reads, semantic assertions, and cleanup.
4. Use UIAutomator/ADB only when the user explicitly requests screen inspection or when a separately authorized automated-UI case requires it.
5. Screenshot only for visual proof: Advanced Rendering, CSS, JS, plugin UI, layout, visible markers, and greeting selector.

## Efficient 1.0 Agent Loop Collaboration

For Agent Loop tests, prepare/import fixtures through external MCP, let the user attach/select them in the phone UI only when required, then send/read through MCP while the user watches and answers native dialogs. Do not stop before every ordinary message send. Stop only for a GUI state change that cannot be performed or verified through MCP.

Capture provider requests through a credential-redacting LAN gateway when the test concerns model-visible tool schemas or tool-loop order. Keep provider/gateway failures distinct from Tavo tool failures. If the user taps **Retry**, record whether the new request is a fresh initial round or contains prior tool results; do not call it automatic or seamless resume without direct evidence.

At the end, restore the user's tool-loading mode, composer, bindings, test memory, and plugin enabled state. The 2026-08-07 epoch finished with dynamic loading on, the composer empty, the minimal test plugin disabled, and disposable state removed or restored.

## Prior 0.93 Isolation And Backup Order

Before any write:

1. Capture the full protected state listed in the current gate section, including stable content hashes and plugin/runtime hashes.
2. Create full Backup A in a permission-restricted directory. Ordinary evidence records only filename alias, size, and SHA-256; never open or print backup contents.
3. Create one run namespace such as `T093_<run-id>` and unique fixture model IDs, nonces, and intent hashes. Never write to the protected chat.
4. Write a durable intent before every mutation. On interruption, reconcile effect/readback before any resend.
5. For request cases, prove one local Provider binding, disable load balancing/backup/fallback, and refuse to send when local-only routing cannot be demonstrated.
6. Run lower-risk plugin/input/generation/theme/media cases first.
7. Run Backup B restore only after other cases stabilize. Any restore anomaly immediately stops later writes and triggers Backup A rollback.

Retained fixtures may remain as evidence but test plugins must finish disabled, the test theme and primary chat API must not remain active, local services must stop, and every protected user-state hash must match the anchor. If the only retained provider has no UI unset action, record that narrow finding rather than deleting a configuration the user asked to retain.

## Prior 0.93 Live Procedure Findings

- Use `scripts/tavo_virtual_provider.py` for zero-real Chat Completions, Responses, legacy Completions, Messages, image, TTS, multipart ASR, and OpenRouter audio-chat fixtures. It has no upstream/forwarding path and returns 501 for unknown routes.
- Store capture directories as mode `0700` and files as `0600`. Replace audio, images, and base64 with MIME/size/SHA-256 metadata; never save raw recordings.
- Correlate every request with case nonce, fixture model ID, intent hash, request count, retry count, and client disconnect state.
- Virtual responses count only for protocol, request assembly, UI, persistence, or direct runtime handling. Permanently report `realModelRequestsSent=0`, `realProviderCredentialsUsed=false`, and `countsTowardKpi=false`.
- Use `scripts/tavo_ui_tree.py` for fail-closed tap/swipe/long-press. Require fresh unique bounds, record down/hold/release coordinates and duration, and verify a target-specific postcondition.
- ADB input should use direct text/accessibility insertion or a safe helper for Chinese; do not automate Chinese through Pinyin key simulation. Restore the original IME after the case.
- Native Backup B may restart Tavo. Compare stable object hashes and full protected state after restart; do not require same PID across restore.
- The 0.93 run retained 52 redacted virtual-provider captures, restored protected state, disabled all retained test plugins, stopped the provider, and reran the strict final gate.

## Prior 0.92 Live Procedure Findings

- Runtime reload can produce a catch-up `chat:opened`; do not miscount it as the original transition or infer the missing `chat:updated` alias event from reload timing.
- Verify input and generation Hooks by source and by persisted message/provider capture. F06 proved UI/TavoJS/MCP input sources, while F09 showed that one generation source can regress independently of terminal semantics.
- Use a deterministic OpenAI-compatible fake gateway when real media credentials are unavailable. Record bounded request metadata and hashes, never audio/image bodies or credentials. A fake gateway proves protocol/integration only; human speech accuracy and audible TTS behavior remain manual.
- Native Backup B restore can restart Tavo. Compare complete pre/post state after the restart; require plugin id/version/config/enabled/runtime equality before disabling the restored fixture. Do not use same-PID continuity as a backup-restore acceptance condition.
- Live negative-package tests should stop once the required rejection boundary is proved. Keep ambiguous, missing-entry, backslash, and symlink fixtures in the offline validator unless a separate live test is explicitly needed.

## MCP Rules Learned From Smoke

- Use JSON-RPC method `tools/call` to invoke Tavo tools.
- Keep `mcp-direct-method-failed.json` as a negative regression case: direct tool-name RPC returned method-not-found behavior.
- Use dry-run before actual writes when the tool supports it.
- dryRun acceptance is not field preservation. Actual import plus readback/export comparison is required.
- `tavo_chat_update` with `expectedRevision` returned a false stale error during smoke. For smoke binding tests, read current state, dry-run without `expectedRevision`, actual update without it, read back, then restore.
- `tavo_input_get` can be UI-bound; if there is no active chat input, treat failure as active-screen state rather than permission failure.

## UI Rules Learned From Smoke

- The chat input was located by `android.widget.EditText` and bounds.
- ADB tap at the center of input bounds focused the field when accessibility click was unavailable.
- UI XML should be saved before and after each meaningful step.
- Screenshots should be paired with UI XML when the UI state matters.
- After an asynchronous import, dialog close, panel open/close, chat switch, or WebView rerender, capture fresh UI XML and a fresh screenshot. Do not reuse bounds from the previous state: stale or currently occluded nodes can remain in the accessibility tree briefly.
- Before tapping, require a positive-area target that is visible in the current screenshot and not covered by a dialog, panel, keyboard, or native composer. `clickable=true`, non-empty bounds, or an ADB return code of `0` does not prove the intended control received the touch.
- After tapping, verify the intended effect through a state change, input readback, message readback, or another target-specific signal.
- When a WebView or plugin control is close to Tavo's native composer or send control, run an actual touch A/B and verify which state changed. Do not infer the native hit region from the visible icon alone.
- Main chat UI may not visibly show chat-level lorebook binding; use MCP readback for that state.
- Switching to a newly created character chat can display a greeting selector. Capture the selector, confirm one greeting only when the test expects it, then capture the final chat screen.

## Composer Draft Lifecycle Boundary

Scoped observation on one Android device with Tavo `0.91.0`: clearing the composer and immediately reading an empty value did not guarantee that it stayed empty after chat navigation; the native draft-restoration layer could reload the earlier text.

- Treat immediate clear/readback as an atomic effect, not a persistence guarantee.
- After a chat switch, WebView reload, fragment remount, or app resume, clear sensitive or test text again and verify both composer readback and the current screenshot.
- Keep this as a version- and device-scoped validation boundary until a retained multi-device or newer-version test proves broader behavior.

## TavoJS Native-Bridge Resource Gate

Use this gate for plugins that make repeated TavoJS calls on Android, especially while validating Tavo `0.91.0`:

1. Record the Tavo PID before the first round and fail the comparison if the PID changes.
2. Record `FDSize` from `/proc/<pid>/status` and, when permitted, the actual entry count under `/proc/<pid>/fd` before and after each round.
3. Run at least three complete rounds in the same PID and include a 3–5 second idle window after each round to detect background polling.
4. Add a control using the native Tavo send path with the plugin disabled or inactive.
5. Search logcat for `HyperSentinel`, held-FD warnings, `too many open files`, ANR, fatal, and crash signals.
6. Report blocked `/proc` access honestly; do not substitute `FDSize` for the actual held-FD count.

Do not accept one successful round as stability proof. A resource regression can be cumulative while the first visible result still succeeds.

If the same UI/runtime blocker repeats twice, stop blind retries. Classify it as `blocked` or turn it into a precise manual step with the expected success marker.

## Artifact Layout

Each live run writes:

```text
artifacts/tavo-validation/YYYYMMDD-<case>/
  run-manifest.json
  device.txt
  adb-devices.txt
  mcp_surface.json
  mcp-requests-redacted.jsonl
  mcp-responses-redacted.jsonl
  ui-before.xml
  ui-after.xml
  screen-before.png
  screen-after.png
  readback.json
  notes.md
```

Optional files: `screen-mid.png`, `ui-mid.xml`, `screen.webm`, per-step JSON files, exported artifacts, diff reports, and cleanup proof only for explicit cleanup/restore tests.

## Retention And Cleanup Policy

The general preference is effect-first validation with durable evidence. For the 0.93 epoch, retain isolated fixture source/evidence and installed fixtures only when the plan calls for it, leave retained plugins disabled, and restore all protected user-facing state. Do not delete historical evidence objects merely to make a newer run look clean.

Every actual write must still be registered:

- object type;
- object id;
- object name;
- creation tool;
- retention decision: `leave-in-place`, `restore-binding`, or `cleanup-case`;
- cleanup tool or restore route when cleanup is explicitly part of the test;
- readback proof;
- final proof that the retained object/file exists or that the requested restore happened.

For binding/switch cases, restore the user's active binding only when the test temporarily changed it and the restore is part of preserving the working test environment. Retain the imported disposable objects unless cleanup is explicitly requested.

If an explicit cleanup case is run, delete or restore in reverse dependency order: messages/chats, then characters/personas/lorebooks/regexes/presets/plugins. Verify cleanup with readback proof, not just a successful delete response.

Known smoke leftovers to account for before future destructive cleanup planning:

- lorebook id `2`, name `Codex Method Smoke Lorebook 20260709-220900`;
- character id `3`, name `Codex Method Smoke Character 20260709-221256`;
- chat id `3`, linked to character id `3`.

Do not delete these automatically. Treat them as retained validation evidence unless the user asks for cleanup.

## First Repeatable Cases

Prioritize these because they exercise the proven method:

1. `phone-preflight`: device/app/MCP/UI/screenshot.
2. `mcp-message-send-read`: MCP input set/get/send plus message readback.
3. `lorebook-import-switch`: dryRun, actual import, bind, readback, restore.
4. `character-import-chat-switch`: card dryRun, actual import, chat create, current-chat switch, greeting selector handling.
5. `ar-visible-marker`: import/render a harmless marker and prove with screenshot.
6. `plugin-minimal-package`: validate/package/import a minimal plugin and prove registration or documented failure.

For retained 0.93 regression work, use `scripts/run_phone_093_master.py` with the reviewed live helpers. For current 1.0 incremental work, start from the strict surface diff and `references/28-tavo-100-live-evidence.md`, then run only changed/high-risk cases in an isolated chat. Offline modes must not contact ADB/MCP; live execution requires durable intents, explicit controlled provider routing for request cases, retained disabled plugins, and `blocked` rather than synthetic passes when an adapter or proof axis is missing.

The older `scripts/run_phone_plugin_092_matrix.py` remains a prior-version control for the detailed 0.92 plugin/Hook catalog.

## KPI Batch Rule

When the user asks for effect-first exhaustive validation, use `scripts/run_phone_kpi_batch.py` instead of hand-assembling repeated MCP calls. The current stress KPI is:

- import at least `50` retained test assets/files into the real phone;
- send at least `50` real chat messages through Tavo so the app uses its configured model API;
- retain the imported assets, test chats, plugin files, screenshots, MCP request/response JSON, and model-message evidence;
- write `run-manifest.json` with `successfulImports`, `modelApiCallsAttempted`, and `modelApiCallsCompleted`.

The KPI batch does not replace targeted semantic tests. It proves volume, MCP write/read stability, and real model-call path health; worldbook trigger semantics, regex transformations, EJS expansion, AR layout, and TavoJS lifecycle still need dedicated matrix rows.

## Exact Provider-Request Capture

Use `scripts/tavo_request_capture_gateway.py` only when the unresolved question is about the final provider payload: EJS/macro expansion, message roles, prompt order, escaping, option forwarding, or raw-tag leakage. Do not route ordinary documented-fact tests through it.

Operational rules:

1. Bind to the Mac LAN address, require a temporary client key, and allow only the phone and local test source IPs.
2. Read the upstream and client keys from mode-`0600` files; let the gateway unlink them after startup. Never put keys in commands, Skill files, captures, or notes.
3. Configure Tavo manually with the LAN `/v1` base, temporary gateway key, and exact upstream model ID. Do not let automation rewrite the user's provider settings.
4. Prove `/v1/models` from the phone once, then send the smallest normal chat case that resolves the payload question.
5. Inspect the redacted capture body, pair it with stable message readback, restore the previous chat, stop the gateway, and retain the capture directory.

The gateway blocks upstream redirects, relays SSE incrementally, caps bodies, redacts common credential fields and values, and writes private capture files. Its offline contract is covered by `scripts/test_tavo_request_capture_gateway.py`.

## ASR Last-Step Rule

ASR is absent from the current official crawl and 0.93 MCP surface even though the native 0.93 UI exposes OpenRouter and custom ASR settings. Inspect UI, Android microphone/nearby-device permission, provider schema, and redacted logs without a real key first. A deterministic local provider is acceptable for multipart request, transcript, cancel/fill/edit, and controlled failure-path integration tests. If a real-provider key is required, pause for the user to enter a temporary revocable key directly on the phone. Never transmit it through chat, ADB, CLI, screenshots, logs, or Skill files.

Run speech input last because it may require human voice and permission changes. Use one fixed harmless phrase, then classify recognition, cancel, permission denial, network failure, and edit-before-send separately. Human audio/voice judgments remain manual and must not be reported as automated passes.

The iOS immersive-mode quick-scroll repair is `not-applicable` on this Android run.

## Final Restoration Gate

Before declaring the epoch complete:

- return to the dynamically anchored protected chat and verify its exact full payload hash, stable messages, and original input;
- restore the original primary API, preset, persona, theme, voice/ASR/bindings, IME, Android permissions, and every pre-existing plugin hash/enabled state;
- disable retained test plugins, ensure test theme/general API are inactive, and stop the local provider fixture;
- retain requested test configurations; if a sole provider cannot be unset without deletion, record it explicitly instead of violating retention;
- capture fresh UI XML/screenshot and MCP readback after restoration;
- confirm the Tavo PID did not change unexpectedly across the core three-round loop; allow and re-anchor documented native backup restart;
- rerun the ADB/MCP strict gate and compare counts/version/current state with the pre-write anchor;
- keep passed, failed, mixed, blocked, manual/deferred, and Android-not-applicable results in separate evidence classes;
- stop only after every catalog case has a terminal status and the reusable evidence contains no secret, private identity, backup content, or raw recording.
