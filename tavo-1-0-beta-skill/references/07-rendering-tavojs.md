# Rendering And TavoJS

This reference covers Advanced Rendering, CSS/JavaScript behavior, TavoJS, and Android-oriented validation.

## Advanced Rendering

Advanced Rendering lets chat messages render HTML and CSS in a WebView. It supports page-like message presentation such as colored text, typography, images, panels, and responsive layouts.

The main Advanced Rendering switch and JavaScript support are separate settings. Enabling JavaScript may require acknowledging a security warning. Plugin fragments and character/model-output JavaScript also have different runtime boundaries.

Do not assume a full unrestricted browser environment. Sanitization, iframe behavior, URL schemes, event timing, persistence, and complex CSS such as fixed/sticky positioning must be checked in the target app version.

## TavoJS Surface

TavoJS is available since v0.75.0 and continues to evolve. Current broad namespaces include:

- Variables: `tavo.get`, `tavo.set`, `tavo.update`, `tavo.unset`.
- Messages: `tavo.message.find`, `tavo.message.get`, `tavo.message.current`, `tavo.message.update`, `tavo.message.count`, `tavo.message.append`, `tavo.message.delete`.
- Chat: `tavo.chat.current`, `tavo.chat.update`.
- Characters: `tavo.character.all`, `get`, `find`, `create`, `update`, `import`, `delete`.
- Personas: `tavo.persona.all`, `get`, `find`, `create`, `update`, `delete`.
- Presets: `tavo.preset.all`, `get`, `find`, `import`, `create`, `update`, `delete`.
- Lorebooks: `tavo.lorebook.all`, `get`, `find`, `import`, `create`, `update`, `delete`.
- Regexes: `tavo.regex.all`, `get`, `find`, `import`, `create`, `update`, `delete`.
- Memory: `tavo.memory.current`, `tavo.memory.update`.
- Generation and images: `tavo.generate`, `tavo.image.generate`.
- TTS: `tavo.tts.play`, `tavo.tts.stop`.
- Files: `tavo.file.save`, `load`, `url`, `delete`, `exists`.
- Input: `tavo.input.get`, `set`, `append`, `clear`, `send`.
- Utilities/app: `tavo.utils.export`, `preview`, `toast`, `openUrl`, `select`, plus `tavo.app.version` and `versionNumber`.

Older code may use compatibility names such as `tavo.v1.get`. Prefer the current `tavo.*` namespace for new work.

## Important Contracts

### TTS

- `tavo.tts.play(text, options)` uses an existing character/persona voice binding.
- Plugin code must provide exactly one `character` or `persona` target in `voice`; ordinary message TavoJS may inherit the host speaker.
- `queue` and `applyPlaybackRules` default to `false`.
- `play()` returns `true` when playback starts or is queued and `false` for empty text, a missing target, or an unusable binding.
- `tavo.tts.stop()` stops the current chat's shared playback and clears its queue.
- The public contract does not expose direct `voiceId` or endpoint-id playback.

### Input

- `await tavo.input.send()` resolves when Tavo accepts or rejects the current input, not when generation completes.
- Success has the shape `{ok: true, text}`.
- Failure has `{ok: false, reason, text}` with reasons such as `cancelled`, `busy`, or `rejected`; plugin cancellation may add `cancelledBy` and `message`.

### Generation And Images

- `tavo.generate(prompt, options)` returns a complete text result rather than a stream and uses the current chat-bound API connection.
- Conversation context is not implicit: `context` defaults to `false`; set `context: true` only when the current conversation should be included.
- `preset` and model `settings` are optional per-call overrides. Omit them when the user's active chat configuration should remain authoritative.
- `tavo.image.generate(prompt, options)` can return a data URL or a saved virtual path with `saveAs`. Options can include size, aspect ratio, negative prompt, reference images, extra body values, save target, and scope.

### Files, Chat, And Utilities

- File APIs operate on Tavo virtual files. Reject slash, backslash, colon, traversal, and other unsafe filename forms.
- Chat-scoped files follow chat lifecycle; global files require intentional cleanup.
- `tavo.chat.update` can change title, character list, persona, and conversation background. Visual precedence still depends on the target runtime.
- Utility APIs provide toast, URL opening, export, preview, selection UI, and compatibility command triggering.

## Plugin Lifecycle Boundary

`generation:prepare/success/error/cancelled` and `input:beforeSend/afterSend` are plugin-entry Hooks, not ordinary character/message TavoJS events. HTML fragments cannot register generation lifecycle Hooks. Use a plugin when behavior must intercept sending or generation across chats.

## Programming Boundaries

- Treat non-variable operations as asynchronous unless the exact API says otherwise.
- Chat, global, and message scopes are separate stores; do not treat one as overriding another.
- Do not call undocumented `window.tav` internals.
- Do not assume TavoJS can edit API providers, TTS endpoints, backup/restore, or storage cleanup.
- Confirm import/create/update object shapes before generating files for direct import.
- Use the current `tavo.update` signature; do not copy old callback/updater patterns without checking compatibility.
- Plugin code should use its lexical `tavo` binding instead of assuming `window.tavo` or `globalThis.tavo`.

## Android WebView Receiver Rule

On v0.91 Android WebView, detaching a native method such as `window.fetch` and later calling it with the wrong receiver can throw an “Illegal invocation” error.

- Preserve the receiver: for fetch, prefer `globalThis.fetch.bind(globalThis)`.
- Node or DOM mocks that accept any receiver are not enough; add a receiver/brand-checking test.
- Keep this rule scoped to WebView-native methods and the affected runtime rather than generalizing it to every JavaScript function.

## Supported Responsive-Panel Pattern

On the v0.91 chat WebView, a card-local panel can use:

- scoped `<style>` rules;
- bounded width, padding, borders, background, and typography;
- grid or single-column responsive actions;
- delegated `data-action` click handling;
- chat-scope `tavo.set/get`;
- `tavo.input.set` or `tavo.input.append` to prepare a user action.

This pattern does not establish support for `position: fixed`, sticky overlays, cross-bubble UI, iframes, arbitrary browser APIs, desktop layouts, restart persistence, or controls outside the chat WebView.

## Capability Decision Example

For “can I float a button inside a dialogue box?”:

1. A button inside an Advanced Rendering message or plugin fragment is plausible.
2. A button floating over native app chrome is not supported by the message WebView surface.
3. Click behavior can call app state only when TavoJS or plugin APIs expose the required operation.
4. Prefer a static in-bubble button first; add JavaScript only for an interaction the user actually needs.

## Validation Method

1. Confirm the Advanced Rendering switch and JavaScript mode before testing code.
2. Begin with static HTML/CSS and a visible unique label.
3. Add one click handler and one observable effect: status text, variable change, composer change, or appended message.
4. Test narrow and wide layouts for overflow, wrapping, touch size, and readability.
5. Recheck after message rerender, chat switch, and app restart when persistence matters.
6. Test sanitizer-sensitive tags, attributes, and URL schemes with harmless fixtures.
7. Confirm async error shapes and permission boundaries for every TavoJS operation used.
8. Keep important user state out of the test chat and provide a no-JavaScript fallback where practical.
