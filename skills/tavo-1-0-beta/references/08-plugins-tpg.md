# Plugins And TPG

This reference covers current Tavo plugin packaging, runtime entry points, Hooks, settings, TTS, and validation boundaries.

## Evidence Snapshot

- Official pages: `https://docs.tavoai.dev/cn/guides/plugins/` and `https://docs.tavoai.dev/cn/guides/plugin-development/`.
- `official-current`: complete 2026-07-26 snapshot in `assets/official-docs/text-20260726/`.
- `mcp-runtime`: Tavo `1.0.0` strict gate in `assets/evidence/1.0.0/20260807-gate.json`, including current `tavo://docs/plugins` and `tavo://docs/tavojs` readability.
- `live-verified`: the 1.0 minimal plugin-center lifecycle/action case in `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`.
- `prior-version`: the 0.93 zero-real plugin matrix remains the broader SemVer/localization/backup baseline, while `assets/evidence/0.92.0/20260717-live-matrix.json` remains the detailed entry/config/Hook/TTS baseline when newer overlays did not repeat the same atomic behavior.

Plugins are `.tpg` zip packages available since v0.91.0. Use a plugin when behavior should be reusable across characters or chats; use ordinary character/message TavoJS when behavior belongs to one card.

## Current Package Shape

Use this layout for new plugins:

```text
my-plugin/
  manifest.json
  entry.js
  ui/panel.html
  cover.png
```

- `manifest.json` is the package manifest and should be at the plugin root.
- `entry` is the current main JavaScript entry, normally root `entry.js`.
- `entry` is required when `contributes.inputActions` or `contributes.sidebar` is declared. It is also valid for a hook-only plugin with no UI contribution.
- A fragment/settings-only plugin may omit `entry` when it executes no plugin-level JavaScript.
- Legacy `scripts.actions` remains a compatibility alias. If both are present, current official and MCP docs declare that `entry` wins.
- `.tpg` is zip-based. The current MCP runtime doc also declares `.zip` accepted for development/import flows.

The official page says the manifest must be at package root. The current MCP runtime additionally declares a wrapper-folder import rule: a root manifest wins; otherwise exactly one nested manifest candidate is accepted and its parent becomes the plugin root; multiple nested candidates are rejected as ambiguous. The 0.92 phone matrix roundtripped a root `.tpg`, one-wrapper archive, and development `.zip`. Multiple-manifest ambiguity remains offline-validator/runtime-contract evidence rather than a live install claim.

## Manifest And Path Rules

Required root fields:

- `id`: stable lowercased plugin id using letters/digits and `.`, `_`, or `-` separators.
- `name`: display string for v1; v2 may use a string or exact `{ "$t": "key" }`.
- `version`: v2 requires valid SemVer; v1 keeps the prior non-empty-string compatibility.

Common optional fields:

- `specVersion`: use `2` for new plugins. Omitted or explicit `1` remains a compatibility path without plugin-package i18n.
- `entry`: package-relative entry script.
- `author`, `description`, `cover`.
- `minAppVersion`: optional valid SemVer for v2 and compared before installation; v1 does not apply the minimum-version gate.
- `localization`: required for v2 with `defaultLocale`; optional `resources` maps locale tags to package-relative JSON catalogs.
- `permissions`: declarative capability names such as `input`, `message`, `generate`, `variable`, `file`, `network`, and `tts`.
- `contributes`: settings, input actions, sidebar actions, and HTML fragments.

Resource paths are virtual paths relative to the selected plugin root:

- use `/` on every platform;
- reject absolute paths, Windows backslashes, URLs, and `..` traversal;
- require the declared `entry` and fragment sources to exist and decode correctly;
- do not assume files outside the selected plugin root are installed;
- do not assume symlinks that resolve outside the package are safe.

Absolute paths, traversal, backslashes, missing entry files, external symlinks, and multiple-manifest ambiguity all belong in the negative fixture set. Keep the local validator fail-closed. The 0.93 phone accepted several negative packages that strict authoring rejects, so live acceptance must never be used to weaken package-path safety.

## Spec 2 Internationalization

Manifest v2 uses package-local JSON catalogs for native labels and plugin-managed HTML/JavaScript:

- `localization.defaultLocale` is required.
- Optional `localization.resources` maps hyphenated locale tags such as `en` and `zh-CN` to package-relative catalog files; underscore tags such as `zh_CN` are invalid.
- Catalogs must be UTF-8 JSON objects with non-empty string keys and string values.
- The exact object `{ "$t": "key" }` is the translation reference. Extra fields, empty keys, and unsupported manifest positions are invalid for strict authoring.
- Supported locations include v2 `name`, optional `description`, input/sidebar labels, supported settings labels/info text, structured select labels, and text/textarea defaults.
- Structured select `value` remains stable and non-localized; only its `label` may vary.
- Resolution checks compatible locale variants, then English, then `defaultLocale`, then displays the key.
- Localized text/textarea defaults follow locale only while no user override exists. Reset deletes the override and resumes the current locale default.

Localized plugin runtime exposes `tavo.plugin.i18n` in entry/actions and plugin fragments:

- live `locale` and `defaultLocale` getters;
- a defensive `supportedLocales` array copy;
- synchronous `t(key, params?)` with `{name}`-style interpolation and key fallback;
- `onChange(handler)` returning an unsubscribe function.

Native plugin labels update after locale changes. Tavo does not rewrite arbitrary plugin DOM; HTML/JavaScript must listen for `onChange` and rerender itself. Entry does not rerun merely because locale changed.

## Entry Runtime And Config

Plugin code should use the unqualified lexical `tavo` binding in `entry`, `/chat` fragments, and `/messages` fragments. Do not use `window.tavo` or `globalThis.tavo` as the plugin-scoped contract.

`tavo.plugin.config` is synchronous and read-only:

```js
const enabled = tavo.plugin.config.get('enabled')
const config = tavo.plugin.config.all()
```

- `get(key)` returns the saved value, falling back to the schema `default`; it returns `null` when neither exists.
- `all()` returns a shallow copy of effective values, including defaults and user overrides.
- Mutating the returned object does not save or change plugin configuration.
- The API does not expose the raw schema and has no runtime write method; users edit values through Tavo's plugin settings page.
- The binding is scoped to the current plugin and is available in entry/action/fragment contexts.

The 0.92 config fixture live-verified default merging, a saved override, effective `all()` values, and non-persistence after mutating the returned copy. This does not add a runtime write API; settings still persist through Tavo's settings/MCP configuration surface.

## Contributions

Current contribution types:

- `contributes.inputActions`: native actions in the input `+` menu.
- `contributes.sidebar`: native actions grouped in the right sidebar.
- `contributes.htmlFragments`: local UTF-8 HTML mounted in chat/message locations.
- `contributes.settings.schema`: a flat settings form with `switch`, `select`, `slider`, `text`, `textarea`, `info`, `divider`, and `break` elements.

Documented fragment mounts include `/chat`, `/chat/head/start`, `/chat/head/end`, `/chat/body/start`, `/chat/body/end`, `/messages/start`, `/messages/end`, and role/position filters for message mounts.

Use `tavo.plugin.onInputAction(id, handler)` and `onSidebarAction(id, handler)` for new actions. The lower-level forms `plugin.on('inputActions:<id>', handler)` and `plugin.on('sidebar:<id>', handler)` remain supported. IDs must match the manifest exactly.

## Chat And Message Notification Hooks

An installed plugin `entry` can register current-chat notifications with `tavo.plugin.on(type, handler)`:

- `chat:opened`, `chat:closed`, `chat:updated`;
- `chat:changed` is a compatibility alias for `chat:updated`, and handlers receive `event.type === 'chat:updated'`;
- `message:added`, `message:updated`, `message:deleted`;
- `message:changed` fires after the specific message event.

Current contract details:

- events contain `type`, `pluginId`, ISO `at`, and the relevant `chatId` plus lightweight `chat`/`message` data;
- `message:added` is for a persistent message, not loading, transient draft, or streaming-token intermediate state;
- a failing handler does not block other plugin handlers or chat operation;
- events are not queued while the runtime is unloaded; a late registration receives one catch-up `chat:opened` when a chat is already open.

The 0.92 F05 case is `mixed`: observed chat-open field shape, specific message event before `message:changed`, one persistent assistant add after streaming, and handler isolation all passed. A controlled chat update did not deliver `chat:updated` to a `chat:changed` compatibility handler. Do not claim the alias or the whole notification family as reliable on this build.

## Input Send Hooks

Only plugin `entry` scripts register `input:beforeSend` and `input:afterSend`. Declare `permissions: ["input"]` as author intent.

`input:beforeSend` intercepts all three documented sources:

- native send button/return key (`source: ui`);
- `tavo.input.send()` (`source: tavojs`);
- MCP `tavo_input_send` (`source: mcp`).

The handler runs before macros and slash-command parsing. `type`, `pluginId`, `chatId`, `source`, and `at` are read-only; `text` is the only mutable field and must remain a string. Return values are ignored; cancellation must call `event.cancel(reason?)`.

Handlers run serially in stable plugin/registration order with a five-second limit. A throw, timeout, or non-string draft rolls back only that handler and fails open. Explicit cancellation stops later handlers, retains the latest committed text and attachments, and does not add another toast. `input:afterSend` is a non-blocking notification after accepted/trimmed input and does not wait for generation.

The Hooks require the current chat Advanced Rendering WebView runtime. If unavailable, current runtime docs say they are bypassed without queueing or blocking the send. The 0.92 matrix observed all three sources, committed rewrite, explicit cancellation with input retained, handler-local fail-open for throw/non-string/timeout, and `afterSend` acceptance timing. Attachment preservation was not exposed and is not a passed assertion.

## Generation Lifecycle Hooks

Only installed plugin `entry` scripts can register these Hooks; HTML fragments and pure character/message TavoJS cannot. Declare `permissions: ["generate"]`.

- `generation:prepare`: serial interceptor before request construction. Mutable `event.text` is only the latest user text for the transient model request; it may be empty and does not alter the saved user message.
- `generation:success`: serial interceptor after generation/extensions and before character-message save. Mutable final text must remain non-empty; empty output is discarded.
- `generation:error`: non-blocking terminal notification with sanitized `error.code` and `error.message` only.
- `generation:cancelled`: non-blocking terminal notification with boolean `partial`; `true` saves the partial character message then emits `message:added`, while `false` saves no message.

Supported `source` values are `reply`, `groupReply`, `continuation`, `othersContinuation`, and `regeneration`. Image, speech, summary, independent, and pure TavoJS/JSAPI generation paths are excluded by current docs.

Prepare/success handlers run in stable registration order, each with a five-second limit. Throws, timeouts, invalid text, and empty success text fail open for that handler only. They cannot cancel generation. The 0.92 provider-fixture matrix live-verified transient prepare rewrite without changing the saved user message, steady multi-plugin order, success-before-save mutation, fail-open empty/throw/timeout, sanitized errors, partial/empty cancellation persistence, and one terminal event. Source behavior is `mixed`: reply, regeneration, and continuation were observed, while the controlled `othersContinuation` path emitted neither the Hook nor a persisted message; auxiliary-path exclusion stayed blocked.

## Plugin TTS

Plugin runtime exposes `tavo.tts.play(text, options)` and `tavo.tts.stop()`:

- declare `permissions: ["tts"]`;
- plugin code must explicitly pass exactly one character or persona id/object in `voice`;
- `queue` and `applyPlaybackRules` default to `false`;
- `stop()` stops the current chat's shared TTS queue, including UI, ordinary TavoJS, and other-plugin work.

The API shape is `official-current`/`mcp-runtime`. With a deterministic OpenAI-compatible provider and a working character binding, one character call and two queued calls were accepted and produced speech requests; missing voice and dual character+persona selection were rejected. Persona acceptance was not retested with a working binding. Speaker correctness, audio quality, and audible queue clearing require human listening and must not be marked passed from UI or gateway state alone.

## Advanced Rendering Boundary

- Plugin entry/actions/fragments require the current chat Advanced Rendering WebView runtime.
- Installed fragment code is separate from the JavaScript mode for character cards/model-output bubbles; that mode does not disable enabled plugin code.
- `/messages` fragments have current-message context; entry, native actions, sidebar actions, and `/chat` fragments do not.
- Current MCP docs describe `permissions` as author-intent declarations, not enforced runtime gates. That is a runtime-doc contract, not permission-bypass approval.

## 1.0 Plugin Center Live Finding

A minimal localized spec-2 package was validated locally, packaged, dry-run/imported through MCP, installed, enabled, and read back. Its native input action rendered the localized Chinese label and, when the user tapped it, wrote the exact marker into the composer. Disabling the plugin removed the runtime action; re-enabling restored it; cleanup left the plugin installed but disabled with no active contribution.

This proves the bounded online-center-era package lifecycle and one native input action on Android 1.0. It does not prove upload/download catalog behavior, arbitrary plugin trustworthiness, fragment rerendering, every permission, or model-tool registration. In the tested release, plugins cannot register Agent Loop tools.

## Prior 0.93 Live Findings

The zero-real Android matrix promoted these current assertions:

- a minimal spec 2 plugin installed, read back, executed its root entry, and finished retained but disabled;
- completed stable/prerelease/build SemVer positives and v-prefix/short/leading-zero/illegal-prerelease negatives behaved as expected in the manifest path;
- a localized v2 plugin with package catalogs, structured select labels/values, and localized text defaults installed and rendered within the completed scope;
- same-run Backup B restored a deliberately mutated spec-2 plugin to its exact saved config, disabled state, and zero runtime contributions;
- final restoration matched all original plugin hashes and original enabled states, while all retained test plugins finished disabled.

Use the complete case map for rejection reliability. The actual package matrix did not reject every unsafe catalog/path canary, so current live acceptance is not an authoring recommendation. Locale fallback, `tavo.plugin.i18n` getter/change semantics, action/sidebar click coverage, and fragment rerendering were not promoted as blanket 0.93 live passes.

## Prior-Version Live Evidence

Retained Tavo `0.92.0` atomic evidence in `assets/evidence/0.92.0/20260717-live-matrix.json` remains the detailed entry/config/input/generation/TTS baseline when its exact behavior was not rerun on 0.93.

Retained Tavo `0.91.0` artifacts prove the older package/install/action/fragment route and remain visual regression controls:

- `artifacts/tavo-validation/20260710-plugin-package-install/`
- `artifacts/tavo-validation/20260710-plugin-ui-action/`
- `artifacts/tavo-validation/20260710-203300-semantic-model-kpi-v23/model-calls/plugin-action-panel/`
- `artifacts/tavo-validation/20260711-020000-cross-feature-matrix-v11-partial-34-35/model-calls/plugin-tavojs-lorebook/`

They do not substitute for the 1.0 overlay, and the narrow 1.0 plugin action does not substitute for their detailed older Hook/TTS axes. Preserve every version label and mixed/manual boundary.

## Prior 0.92 Findings And Remaining Queue

The 2026-07-17 run completed the core F01-F11 matrix, positive root/wrapper/zip imports, same-id update preservation, and a native Backup B uninstall/restore roundtrip. Use only atomic assertions from the retained summary; F05, F09, and F11 remain mixed.

Remaining discriminating work:

1. retest `chat:changed` alias delivery without conflating runtime reload/catch-up;
2. isolate `othersContinuation` and the declared auxiliary-path exclusions;
3. test persona TTS with a working binding and perform human listening for identity, quality, and queue stop;
4. keep ambiguous/missing/backslash/symlink negative packages offline unless a separately authorized live rejection test is necessary;
5. rerun current gate and exact user-state restoration after future app/runtime changes.

## Validation Tooling

- `scripts/tpg_spec2.py`, `scripts/validate_tpg_package.py`, and `scripts/test_validate_tpg_package.py` implement the strict local spec 1/2, SemVer, min-app, i18n/catalog, translation-placement, package-root, unsafe-path, missing-file, and symlink contract.
- `scripts/run_phone_plugin_093_live.py` executes the guarded manifest/runtime matrix with durable intents and retained disabled fixtures; `scripts/test_run_phone_plugin_093_live.py` proves its offline/no-contact contract.
- `scripts/run_phone_plugin_093_package_actual.py` exercises the actual package-selection/rejection path; `scripts/test_run_phone_plugin_093_package_actual.py` validates its catalog offline.
- `scripts/tavo_generation_hook_fixture.py` is a deterministic LAN OpenAI-compatible endpoint for JSON, SSE, slow-stream, HTTP 500, and malformed-protocol generation cases. It allowlists clients and writes redacted mode-0600 captures under a mode-0700 directory.
- `scripts/test_tavo_generation_hook_fixture.py` verifies that fixture's auth, allowlist, JSON/SSE/fault modes, secret-file handling, and nested credential redaction offline.
