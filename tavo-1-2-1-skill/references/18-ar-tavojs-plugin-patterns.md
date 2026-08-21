# Advanced Rendering, TavoJS, And Plugin Patterns

This reference contains implementation patterns for UI-like behavior in Tavo. Treat each pattern as version-bounded and validate the exact host, mount point, selector, API, and visual target used by the user's artifact.

## Applicable Versions

- Tavo 1.0 supports a localized spec-2 plugin input action and the current Agent Loop/tool surface.
- Detailed plugin entry, configuration, input-hook, generation-hook, and TTS behavior remains version-bounded to Tavo 0.92 unless rechecked on a newer version.
- Advanced Rendering message panels, delegated clicks, chat-scope `tavo.set/get`, and `tavo.input.set/append` patterns are established on Tavo 0.91 but should be rechecked after WebView or renderer changes.
- No current capability supports a persistent app-level floating control outside Tavo's chat WebView.

## Rendering Model

Treat Advanced Rendering as HTML/CSS/JS rendered inside an app-controlled WebView or chat surface, not as a normal browser page. Browser APIs, inline handlers, CSS positioning, clipping, sanitization, script lifecycle, storage, and app bridges can differ from desktop Chrome.

Keep rendering concerns separate:

- HTML/CSS source validity;
- DOM mount and event execution;
- native input or data side effects;
- visible mobile layout;
- persistence after reload, chat switch, or app restart.

Passing one layer does not prove the others.

## Safer Interactive Button Pattern

Prefer delegated listeners and `data-*` attributes over inline `onclick`:

```html
<div class="tavo-card-actions" data-tavo-widget="example">
  <button type="button" data-action="append" data-text="继续调查线索">继续调查线索</button>
  <button type="button" data-action="append" data-text="查看角色状态">查看角色状态</button>
</div>
<script>
(() => {
  const script = document.currentScript;
  const root = script?.closest('[data-tavo-widget="example"]') || document;
  root.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action="append"]');
    if (!button) return;
    const text = button.getAttribute('data-text') || '';
    if (window.tavo?.input?.append) {
      await window.tavo.input.append(text);
    }
  });
})();
</script>
```

For repeated message widgets, scope selectors to the current widget and avoid global IDs. Make actions idempotent or disable the button while an asynchronous write is in flight.

## Floating And Overlay Targets

Distinguish four different requests:

| Target | Recommended route | Boundary |
| --- | --- | --- |
| Floating inside one rendered message | Advanced Rendering with a bounded relative container and an absolute child | Can be clipped by the message container. |
| Overlaying the chat viewport | Advanced Rendering experiment | WebView and message clipping can prevent a true viewport overlay. |
| Native action in the input `+` menu | TPG `inputActions` | Requires an installed plugin and Advanced Rendering for handler execution. |
| Persistent app-level floating action | Not currently exposed | Do not promise this without a new app/plugin API. |

For a floating layout, verify narrow width, long content, scrolling, keyboard open/close, chat switching, safe-area insets, and overlap with native controls.

## TavoJS Host Boundary

Use `window.tavo` in ordinary rendered-message TavoJS. Avoid internal bridges such as `window.tav`.

Before shipping a rendered interaction:

1. reduce it to the smallest HTML/JS case;
2. confirm the required TavoJS method exists on the target version;
3. trigger exactly one action;
4. read back the intended state or input value;
5. inspect the rendered result on the target viewport;
6. reload and switch chats if persistence is part of the requirement.

`tavo.tts.play/stop` and structured `tavo.input.send()` results are TavoJS capabilities, but audio identity and every failure reason still require target-version checks. Generation and input lifecycle hooks are plugin-entry features; they are not ordinary message-script APIs.

## Plugin Package Boundary

For new packages:

- use `specVersion: 2`;
- use valid SemVer;
- set `localization.defaultLocale`;
- place `manifest.json` at package root;
- use root `entry.js` through `entry: "entry.js"` when plugin-level JavaScript runs;
- keep `scripts.actions` only for legacy compatibility;
- allow hook-only plugins to use `entry` without UI contributions;
- allow fragment/settings-only packages to omit `entry` when no plugin-level JavaScript runs.

Plugin entry scripts, action handlers, and fragments use the unqualified lexical `tavo` binding:

```js
tavo.plugin.on('chat:opened', async (event) => {
  const enabled = tavo.plugin.config.get('enabled');
  if (enabled) await tavo.utils.toast(`chat=${event.chatId}`);
});
```

Do not rewrite plugin-scope code as `window.tavo` or `globalThis.tavo`. Plugin scope and rendered-message scope are different hosts; success in one does not prove the other.

## Hook And TTS Boundaries

For Tavo 0.92-style plugin entries:

- chat/message notifications observe state and cannot cancel a chat or generation;
- `input:beforeSend` can rewrite or cancel supported sends;
- `input:afterSend` means the input was accepted, not that generation completed;
- handler errors, timeouts, or invalid rewrites should fail open unless an explicit cancel is returned;
- generation prepare/success handlers can transform transient request or response data;
- generation error/cancelled are terminal notifications;
- HTML fragments cannot register generation hooks;
- TTS must resolve an explicit character or persona speaker and uses the shared current-chat queue;
- audible voice identity must be checked by listening, not inferred from a successful call.

Generation-source coverage, persona TTS, busy-state behavior, and every notification alias remain version- and path-dependent.

## Pattern Boundaries

| Pattern | Usable scope | Remaining boundary |
| --- | --- | --- |
| Native plugin input action | Tavo 1.0 minimal localized action | Does not prove sidebar, fragment button, or arbitrary action sets. |
| Delegated AR click with input set/append | Tavo 0.91 message panels | Recheck selectors, mounts, and renderer settings. |
| Responsive HTML/CSS panel | Tavo 0.91 message panel | Recheck screen sizes, clipping, sticky/fixed behavior, and sanitation. |
| Spec-2 manifest and root entry | Tavo 1.0 minimal plugin | Locale change and fragment rerender are separate cases. |
| Root entry, legacy alias, entry precedence | Tavo 0.92 | Do not infer all later versions without a compatibility check. |
| Input lifecycle hooks | Tavo 0.92 tested paths | Attachments and every send source are not guaranteed. |
| Generation lifecycle hooks | Tavo 0.92 partial | Some generation sources remain path-dependent. |
| Plugin TTS | Tavo 0.92 partial | Persona selection and audible output require manual validation. |
| HTML fragment registration | Supported plugin pattern | Registration does not prove pixel layout or button execution. |
| App-level persistent floating control | Unsupported/unexposed | Requires a future native or plugin API. |
| Inline `onclick` | Compatibility risk | Prefer delegated listeners. |
| Internal `window.tav` | Unsupported contract | Use only documented public bindings. |

## User-Facing Validation

A community artifact should include a small validation card or disposable plugin that proves only its own behavior:

1. show an unmistakable render marker;
2. click one control and change a visible state marker;
3. set or append a unique input string;
4. read the input back before sending;
5. verify the layout after scroll, keyboard open/close, and chat switch;
6. separately test any persistence or audio requirement;
7. remove or disable the disposable artifact after validation.

A visible panel does not prove its button executed. A changed composer does not prove a message was sent. A registered plugin contribution does not prove its UI mounted. A screenshot proves visible pixels at that moment, not stored data or future compatibility.
