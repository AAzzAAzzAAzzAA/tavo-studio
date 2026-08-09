# Capabilities Overview

Use this file first for broad or unusual questions such as “Tavo 能干嘛” or “能不能让某个按钮悬浮在对话框里”.

## Capability Map

| Area | Current capability | Read |
| --- | --- | --- |
| API and models | Provider connections, model selection, OpenAI-compatible custom endpoints, model parameters, and common error handling. | `references/10-app-settings-data.md` |
| Characters | Native character fields, personas, URL/file card import, JSON/PNG card workflows, and TavoJS character/persona operations. | `references/03-characters-cards-personas.md` |
| Chat | One-to-one chat, group chat, chat actions, history import/export, translation, and per-chat prompt settings. | `references/04-chat-workflows.md` |
| Prompt authoring | Presets, worldbooks, regex, long memory, macros, and EJS templates. | `references/05-prompt-authoring.md`, `references/06-macros-ejs.md` |
| Rendering and scripting | Advanced Rendering for HTML/CSS in chat bubbles and TavoJS APIs for exposed app objects and actions. | `references/07-rendering-tavojs.md` |
| Native Agent Loop | Since 1.0, compatible models can call Tavo's built-in tools during chat; tools may be loaded dynamically or as a full catalog. | `references/10-app-settings-data.md` |
| Plugins | Since v0.91.0, `.tpg` packages can contribute settings, actions, fragments, Hooks, TTS behavior, and localized labels. New packages should use `specVersion: 2`. | `references/08-plugins-tpg.md` |
| Media | Voice providers and bindings, TTS, image providers and generation, image sending, and native speech-input configuration where available. | `references/09-media-voice-image.md` |
| App data | Themes, backup/restore, storage cleanup, custom shortcuts, and quick group speech. | `references/10-app-settings-data.md` |
| External MCP | Since v0.91.0, the built-in MCP server lets external agents read runtime documentation and operate the app objects it exposes. | `references/11-mcp-runtime.md` |

## Product Boundaries

- The external MCP server and the in-chat Agent Loop are different surfaces. External MCP tools do not become tools available to the roleplaying model.
- The Agent Loop tool catalog belongs to Tavo. Character cards and plugins cannot currently register new model tools.
- MCP exposes only its documented objects and mutations. A native UI feature is not automatically controllable through MCP.
- Advanced Rendering is a chat WebView surface, not unrestricted access to native app chrome.
- TavoJS is broad but not a general app-admin API. Provider credentials, backup/restore, and storage cleanup should not be assumed scriptable.
- A supported import format does not guarantee that every third-party file preserves every extension or binding.
- Native speech input may exist without a matching external MCP or TavoJS operation.

## Answering “Can It Do X?”

1. Classify the request by layer: built-in UI, prompt system, Advanced Rendering, TavoJS, plugin, Agent Loop, external MCP, or provider integration.
2. Identify the minimum Tavo version required.
3. Separate the desired effect from its implementation. For example, a status panel may be static HTML, macro-generated text, TavoJS interaction, or a reusable plugin.
4. State the boundary explicitly: supported, supported only in a narrower surface, plausible but needs validation, or unsupported.
5. When behavior depends on rendering, import conversion, provider protocol, model tool use, or state persistence, propose a small reversible test before promising delivery.

## Creation And Validation Method

- Split work into prompt, data/import, rendering, scripting/plugin, media, and app-settings layers.
- Keep product guarantees separate from authoring craft. Tavo supporting a field does not by itself make a good card, worldbook, regex, or plugin.
- Treat a roleplay package as a group of independently testable objects: card, persona, worldbook, preset, regex, memory plan, rendering, plugin, and media.
- Start with the smallest object set that can produce the user's intended experience.
- Validate prompt-only behavior in Prompt Lab before testing UI or provider integrations.
- Validate imports with a disposable object and export/readback before using important user data.
- Validate rendering with visible markers, state changes, or app readback; a generated HTML/JS string alone does not prove execution.
- Validate provider features separately at configuration, request, response, persistence, and human-quality layers.
- Back up user data before destructive or restore-related tests.

## First-Pass Creation Priority

- coherent character cards with strong description, scenario, examples, greeting, and creator notes;
- worldbooks that inject focused facts without drowning the context;
- regexes that transform text without corrupting intended content;
- readable, escapable, testable macros and EJS;
- Android-friendly Advanced Rendering and TavoJS interactions;
- reusable plugins with strict local package validation;
- explicit capability and non-capability statements in every delivery.
