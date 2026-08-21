# Plugins And TPG

This reference covers Tavo plugin packaging, runtime entry points, Hooks, settings, TTS, and safety boundaries.

Plugins are `.tpg` zip packages available since v0.91.0. Use a plugin for behavior reusable across characters or chats; use ordinary character/message TavoJS when behavior belongs to one card.

## Package Shape

Use this layout for a new plugin:

```text
my-plugin/
  manifest.json
  entry.js
  ui/panel.html
  cover.png
```

- `manifest.json` belongs at the plugin root.
- `entry` normally points to root `entry.js`.
- `entry` is required for input actions or sidebar contributions and can also power a Hook-only plugin.
- A fragment/settings-only plugin may omit `entry` when it has no plugin-level JavaScript.
- Legacy `scripts.actions` is a compatibility alias; `entry` wins when both exist.
- `.tpg` is zip-based; development/import flows can also accept `.zip`.
- A root manifest wins. If no root manifest exists, exactly one nested manifest may define a wrapper-folder root; multiple candidates are ambiguous and should be rejected.

## Manifest And Path Rules

Required root fields:

- `id`: stable lowercase letters/digits with `.`, `_`, or `-` separators;
- `name`: display string for spec 1; spec 2 also accepts exact `{ "$t": "key" }`;
- `version`: valid SemVer for spec 2; a non-empty compatibility string for spec 1.

Common optional fields:

- `specVersion`: use `2` for new plugins; omitted or `1` is compatibility mode;
- `entry`, `author`, `description`, `cover`;
- `minAppVersion`: valid SemVer for spec 2 and checked before installation;
- `localization`: spec-2 locale configuration;
- `permissions`: author-declared capabilities such as `input`, `message`, `generate`, `variable`, `file`, `network`, and `tts`;
- `contributes`: settings, input actions, sidebar actions, and HTML fragments.

All package resources use virtual paths relative to the selected plugin root:

- use `/` on every platform;
- reject absolute paths, backslashes, URLs, and `..` traversal;
- require declared entry and fragment files to exist and decode correctly;
- do not include files outside the selected root;
- reject symlinks that escape the package.

Keep local validation fail-closed even if a particular app build happens to accept an unsafe archive.

## Spec 2 Internationalization

- `localization.defaultLocale` is required.
- `localization.resources` maps hyphenated locale tags such as `en` and `zh-CN` to package-relative UTF-8 JSON catalogs; underscore tags such as `zh_CN` are invalid.
- Catalogs contain non-empty string keys and string values.
- Translation references use the exact object `{ "$t": "key" }`; extra fields or empty keys are invalid.
- Supported positions include name, description, action labels, supported settings labels/info, select labels, and text/textarea defaults.
- Select `value` remains stable and non-localized; only its `label` changes.
- Resolution checks compatible locale variants, English, `defaultLocale`, then the key itself.
- Localized text/textarea defaults follow locale only until the user saves an override; reset returns to the current locale default.

Plugin runtime exposes `tavo.plugin.i18n` with live `locale` and `defaultLocale`, a defensive `supportedLocales` copy, synchronous `t(key, params?)`, and `onChange(handler)` returning an unsubscribe function. Native labels can update automatically, but arbitrary plugin DOM must listen for locale changes and rerender itself. Locale changes do not rerun `entry`.

## Entry Runtime And Config

Use the lexical `tavo` binding in `entry`, `/chat` fragments, and `/messages` fragments. Do not rely on `window.tavo` or `globalThis.tavo` as the plugin-scoped contract.

`tavo.plugin.config` is synchronous and read-only:

```js
const enabled = tavo.plugin.config.get('enabled')
const config = tavo.plugin.config.all()
```

- `get(key)` returns a saved value, then the schema default, then `null`.
- `all()` returns a shallow copy of effective values.
- Mutating that copy does not persist configuration.
- Runtime code cannot write settings through this API; users edit settings through Tavo's plugin settings surface.
- Config and i18n bindings are scoped to the current plugin.

## Contributions

- `contributes.inputActions`: native actions in the composer `+` menu.
- `contributes.sidebar`: native actions in the right sidebar.
- `contributes.htmlFragments`: local UTF-8 HTML mounted in chat/message locations.
- `contributes.settings.schema`: flat forms using `switch`, `select`, `slider`, `text`, `textarea`, `info`, `divider`, and `break`.

Fragment mounts include `/chat`, `/chat/head/start`, `/chat/head/end`, `/chat/body/start`, `/chat/body/end`, `/messages/start`, and `/messages/end`, with role/position filters for message mounts.

Use `tavo.plugin.onInputAction(id, handler)` and `onSidebarAction(id, handler)`. Lower-level `plugin.on('inputActions:<id>', handler)` and `plugin.on('sidebar:<id>', handler)` remain compatibility forms. IDs must match the manifest.

## Chat And Message Hooks

An installed `entry` can subscribe with `tavo.plugin.on(type, handler)`:

- `chat:opened`, `chat:closed`, `chat:updated`;
- `chat:changed` as a compatibility alias for `chat:updated`;
- `message:added`, `message:updated`, `message:deleted`;
- `message:changed` after the specific message event.

Events contain the type, plugin ID, event time, relevant chat ID, and lightweight chat/message data. `message:added` represents a persistent message, not loading, drafts, or intermediate streaming tokens. One failing handler must not block other handlers or the chat operation. Events are not queued while the runtime is unloaded; late registration may receive a catch-up `chat:opened` for the active chat.

## Input Send Hooks

Only plugin `entry` scripts register `input:beforeSend` and `input:afterSend`. Declare `permissions: ["input"]`.

`input:beforeSend` can intercept native UI sends, `tavo.input.send()`, and external MCP input sends. It runs before macro and slash-command parsing. Metadata is read-only; `text` is the mutable string field. Return values are ignored; cancellation uses `event.cancel(reason?)`.

Handlers run serially in stable plugin/registration order with a per-handler timeout. Throws, timeouts, or non-string drafts roll back that handler and fail open. Explicit cancellation stops later handlers, keeps the latest committed text and attachments, and prevents the send. `input:afterSend` is a non-blocking notification after input acceptance and does not wait for generation.

These Hooks require the current chat's Advanced Rendering WebView runtime. When unavailable, they can be bypassed rather than queued.

## Generation Lifecycle Hooks

Only installed plugin `entry` scripts register these Hooks; fragments and ordinary character/message TavoJS cannot. Declare `permissions: ["generate"]`.

- `generation:prepare`: serial interceptor before request construction. Mutable `event.text` affects only the transient latest-user text and does not rewrite the saved user message.
- `generation:success`: serial interceptor before the final character message is saved. Final text must remain non-empty.
- `generation:error`: non-blocking terminal notification with sanitized error code/message.
- `generation:cancelled`: terminal notification with `partial`; a partial result may be saved, while an empty cancellation saves no character message.

Supported sources include `reply`, `groupReply`, `continuation`, `othersContinuation`, and `regeneration`. Image, speech, summary, independent, and pure TavoJS generation are outside this Hook family.

Prepare/success handlers run in stable order with a per-handler timeout. Throws, timeouts, invalid text, and empty success text fail open for the affected handler. These handlers cannot cancel generation.

## Plugin TTS

- Declare `permissions: ["tts"]`.
- Pass exactly one character or persona ID/object in `voice`.
- `queue` and `applyPlaybackRules` default to `false`.
- `tavo.tts.stop()` stops the current chat's shared queue, including UI, ordinary TavoJS, and other-plugin playback.
- Provider acceptance does not prove speaker identity, audio quality, or audible queue clearing; those require listening.

## Runtime And Agent Boundaries

- Plugin entry/actions/fragments require the current chat's Advanced Rendering WebView runtime.
- Plugin fragments are separate from the JavaScript mode for character cards and model-output bubbles.
- `/messages` fragments have current-message context; entry, native actions, sidebar actions, and `/chat` fragments do not.
- `permissions` are declarative author intent and must not be treated as authorization to bypass user safety.
- Tavo 1.0's plugin center can install, enable, disable, configure, and localize plugins.
- Plugins cannot currently register tools into the in-chat Agent Loop.

## Creation And Validation Method

1. Start with one contribution and the minimum permissions.
2. Validate source files locally with `scripts/tpg_spec2.py` and `scripts/validate_tpg_package.py`; run `scripts/test_validate_tpg_package.py` after validator changes.
3. Test SemVer, `minAppVersion`, catalogs, translation placement, package root selection, missing files, unsafe paths, and escaping symlinks.
4. Install only a harmless disposable package first and keep it disabled until its manifest and settings are readable.
5. Test default config, a saved override, reset behavior, and locale change independently.
6. Test action, fragment, input Hook, generation Hook, and TTS as separate capabilities.
7. Confirm fail-open/fail-closed behavior intentionally: runtime handlers should isolate failures, while package validation should reject unsafe input.
8. Disable or uninstall the test plugin and confirm its actions, fragments, and Hooks no longer run.
