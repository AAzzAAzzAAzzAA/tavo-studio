# Community Capability Boundaries

This file defines what the community package may promise. It contains conclusions and version boundaries only; it intentionally omits private provenance, machine paths, run identifiers, credentials, and collection history.

## Packaged Version Baseline

- Tavo `1.0` behavior is the baseline for Agent Loop, MCP, memory/message tools, plugin-center behavior, and the current prompt/regex pipeline described in the topic references.
- Unless a topic reference explicitly names another version, its `current` or `supported` product statements use the packaged Tavo `1.0` baseline.
- Tavo `0.93` and earlier behavior is retained only where a newer result did not replace that exact axis. Every such statement must keep its version label.
- A feature working in one version does not automatically prove it in later or earlier versions.
- A product update after this package may change names, schemas, defaults, UI paths, permissions, or reliability. Treat a current-runtime check as a separate task when accuracy depends on the installed build.

## Supported Result Families

- Character cards and personas: creation, field-level revision, common SillyTavern-compatible structures, greetings/examples, JSON validation, and PNG payload utilities.
- Presets and worldbooks: native prompt entries, marker handling, relative/absolute placement, keyword logic, role/depth/order controls, and common compatibility mappings.
- Regex: authored rule validation plus the supported send/display/receive/lorebook subset described in the regex reference.
- Prompt Lab: deterministic text assembly, worldbook trigger reporting, supported regex stages, macros, prompt-field EJS, provider/display/persistence views, model calls, and adaptive multi-turn state.
- EJS: prompt-oriented templating in the documented variables/state subset. It is not TavoJS, DOM, a plugin runtime, or a general Node environment.
- Advanced Rendering and TavoJS: authoring patterns and API boundaries are included, but visual/WebView effects require the target app.
- TPG plugins: package structure, path safety, spec-2 localization, entry/config/contribution patterns, and local validators.
- Agent Loop and MCP: the two tool surfaces are separate. Tool visibility, permissions, loop limits, persistence, and app effects must be scoped to the exact surface described in the relevant reference.
- Media: provider/request configuration can be reasoned about separately from audible voice quality, ASR accuracy, image quality, and UI rendering.

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

When a current runtime contradicts this package, prefer the narrower current result for that installation and mark the packaged statement as version-limited. Update the community text with the new conclusion and boundary only; keep private captures, endpoint details, device/chat identifiers, and discovery logs outside the distributable directory.
