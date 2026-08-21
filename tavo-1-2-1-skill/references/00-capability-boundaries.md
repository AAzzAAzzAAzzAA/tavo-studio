# Community Capability Boundaries

This file defines what the community package may promise. It contains conclusions and version boundaries only; it intentionally omits private provenance, machine paths, run identifiers, credentials, and collection history.

## Packaged Version Baseline

- Tavo `1.2.1` on macOS is the baseline for app identity, external MCP, native Agent Loop, variables, files, themes, input behavior, text generation, image generation, TTS, Web Fetch, and Ask/Cross-chat facts.
- Tavo `1.0` remains the baseline for memory operations and other exact behaviors that were not repeated on `1.2.1`.
- Tavo `0.93` and earlier statements remain version-limited where no newer fact replaces that exact axis.
- Character-card, worldbook, preset, regex, EJS, Advanced Rendering, TavoJS, and plugin statements keep the version label in their topic reference; the `1.2.1` label does not automatically upgrade them.
- A feature working in one version or platform does not automatically prove it in another.
- A later product update may change names, schemas, defaults, UI paths, permissions, or reliability. Inspect the installed runtime when the answer depends on its exact build.

## Supported Result Families

- Character cards and personas: creation, field-level revision, common SillyTavern-compatible structures, greetings/examples, JSON validation, and PNG payload utilities.
- Presets and worldbooks: native prompt entries, marker handling, relative/absolute placement, keyword logic, role/depth/order controls, and common compatibility mappings.
- Regex: authored rule validation plus the supported send/display/receive/lorebook subset described in the regex reference.
- Prompt Lab: deterministic text assembly, worldbook trigger reporting, supported regex stages, macros, prompt-field EJS, provider/display/persistence views, model calls, and adaptive multi-turn state.
- EJS: prompt-oriented templating in the documented variables/state subset. It is not TavoJS, DOM, a plugin runtime, or a general Node environment.
- Advanced Rendering and TavoJS: authoring patterns and API boundaries are included, but visual/WebView effects require the target app.
- TPG plugins: package structure, path safety, spec-2 localization, entry/config/contribution patterns, and local validators.
- Agent Loop and MCP: the two tool surfaces are separate. On the packaged `1.2.1` Mac baseline, external MCP includes variables, files, themes, text generation, image generation, and TTS, while Dynamic Agent mode begins with discovery, user-dialog, and Web Fetch tools.
- Themes: custom-theme create/read/update/delete plus import/export and chat binding are supported through external MCP within the documented object fields.
- Media: the packaged image and TTS results establish bounded OpenAI-compatible request/response integration only. They do not establish real-provider compatibility, image quality, audible quality, or speaker identity.

## Non-Substitution Rules

- A valid JSON shape does not prove that Tavo imports and preserves every field.
- A successful import does not prove exact roundtrip preservation.
- A compiled prompt does not prove the app's DOM, WebView, TavoJS bridge, plugin lifecycle, persistent state, or visual output.
- A virtual-provider reply does not prove real-provider compatibility or model semantics.
- A real-model reply proves only the request and behavior tested; it does not validate unrelated Tavo features.
- A screenshot proves visible state, not hidden request order or persistence after restart.
- A runtime schema proves availability, not permission, reliability, or side effects.

## Answer Policy

For a capability question:

1. State the result first.
2. Name the applicable version or configuration when it matters.
3. State the narrowest meaningful limitation.
4. Use `not-established` when the packaged result does not cover the requested axis.
5. Do not describe private provenance or include raw identifiers.

For authoring advice, distinguish product behavior from craft preference. A strong writing recommendation remains `creative-guidance` unless it is also a required data contract.

## Update Policy

When a current runtime contradicts this package, prefer the narrower result for that installation and mark the packaged statement as version-limited. Update the community text with the conclusion and boundary only; keep endpoint details, device/chat identifiers, credentials, and diagnostic records outside the distributable directory.
