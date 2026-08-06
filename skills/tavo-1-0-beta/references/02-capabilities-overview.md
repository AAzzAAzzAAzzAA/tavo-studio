# Capabilities Overview

Use this file first when the user asks broad or unusual questions such as "Tavo 能干嘛" or "能不能让某个按钮悬浮在对话框里".

Evidence baseline for this draft:

- `official-current`: 83 fetched pages from `assets/official-docs/text-20260726/` and `assets/official-docs/url_map-20260726.json`. This crawl predates the connected 1.0 build and does not document its Agent Loop delta.
- `release-announcement`: Tavo 1.0 announces native tool calling, plugin center, UI/performance work, `memory.append`, and targeted fixes. Treat those bullets as test leads until docs/runtime/live evidence resolves the contract.
- `mcp-runtime`: Tavo `1.0.0`, protocol `2025-06-18`, 72 tools, 19 resources, 7 resource templates, 0 prompts, and successful strict dynamic docs/schema reads in `assets/evidence/1.0.0/20260807-gate.json`.
- `live-verified`: the 2026-08-07 1.0 Agent Loop/MCP overlay in `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`. It promotes only the tested tool-loop, memory, message, and plugin-center axes.
- `prior-version`: the 0.93 broad zero-real overlay, 0.92 plugin/Hook matrix, and 0.91 semantic/AR artifacts remain versioned controls where 1.0 did not execute the same proof axis.
- `historical-derived`: reusable creative guidance from the old `tavo-studio` skill that does not conflict with official docs, kept as guidance until live verification.

## Official-Current Capability Map

| Area | What the official docs currently expose | Read |
| --- | --- | --- |
| API and models | API setup, provider key pages, OpenAI-compatible custom protocol, common API errors, model selection. | `references/10-app-settings-data.md` |
| Characters | Native character creation fields, persona/user identity, URL import from supported sites, file import from supported sites. | `references/03-characters-cards-personas.md` |
| Chat | Start chat, chat actions, advanced chat settings, group chat, history import/export, translation. | `references/04-chat-workflows.md` |
| Prompt authoring | Presets, worldbooks, regex, long memory, macros, EJS templates. | `references/05-prompt-authoring.md`, `references/06-macros-ejs.md` |
| Rendering and scripting | Advanced Rendering for HTML/CSS in chat bubbles; TavoJS API for variables, messages, chats, assets, memory, generation, images, TTS, files, input, app version, and utilities. | `references/07-rendering-tavojs.md` |
| Native Agent Loop | In-chat model tool calling for Tavo objects, user dialogs, and web fetch; dynamic three-tool discovery or direct full-catalog loading. | `references/28-tavo-100-live-evidence.md`, `references/10-app-settings-data.md` |
| Plugins | `.tpg` plugin packages since v0.91.0; current `specVersion: 2`, SemVer/min-app validation, package i18n, root `entry.js`, settings/config/i18n reads, actions, fragments, Hooks, TTS, and declarative permissions. | `references/08-plugins-tpg.md` |
| Media | Voice provider setup, voice API settings/binding/TTS, image provider/generation/sending, plus 0.93 native ASR UI with OpenRouter and configurable parameters. | `references/09-media-voice-image.md` |
| App data | Theme, backup/restore, storage cleanup, custom shortcuts, quick group speech. | `references/10-app-settings-data.md` |
| MCP | Built-in MCP Server since v0.91.0 for agents to read runtime docs and operate exposed app objects. | `references/11-mcp-runtime.md` |

Current exclusions are equally important: the 1.0 MCP delta added memory tools and removed middle-message insertion; it did not turn the external MCP server into the in-chat Agent Loop. The Agent Loop's 58-tool built-in catalog belongs to Tavo, not to the active rolecard, and current rolecards/plugins cannot register new model tools. The retained 0.93 surface contained no ASR/STT tool, resource, template, or runtime-doc entry; ASR was not rerun in the 1.0 overlay, so keep the 0.93 native-UI finding versioned rather than claiming a new MCP capability.

Fable 5 and Mythos 5 dedicated controls plus restart persistence were observed on 0.93. Their proprietary wire fields and real endpoint behavior were not promoted because no safely redirected request reached the local fixture. Read `references/28-tavo-100-live-evidence.md` for 1.0 changes and `references/26-tavo-093-live-evidence.md` for unchanged broad-runtime claims.

## Answering "Can It Do X?"

1. Classify the request by layer: built-in UI, prompt system, Advanced Rendering, TavoJS, plugin, MCP automation, or external provider.
2. Check `references/01-official-url-map.md` and the topic reference for `official-current` coverage.
3. Check MCP docs or schemas when the answer involves current writable objects, import formats, or runtime APIs.
4. If X depends on visual layout, JavaScript, CSS, plugin behavior, import persistence, or WebView quirks, add or reuse a row in `references/12-validation-matrix.md`.
5. Answer in one of four classes:
   - supported by current official docs;
   - likely possible but needs MCP/runtime verification;
   - possible only as a workaround or creative composition;
   - not supported by current evidence.

## Inference Boundaries

- Do not assume browser-standard CSS/JS behavior in Advanced Rendering until Android WebView evidence exists.
- Do not assume a TavoJS function exists because an old skill used it; check current official docs or live MCP runtime docs.
- Do not assume a plugin can mutate app state unless current plugin docs or MCP runtime exposes that write path.
- Do not assume imports persist until an import flow, dry-run, or app-state readback has been verified.
- Do not treat API provider/model configuration as scriptable unless current MCP or TavoJS docs expose it. Official docs mostly describe UI configuration here.

## Reusable Old-Skill Guidance

These are safe to use as creative guidance because they do not conflict with current docs:

- Split Tavo work into prompt layer, data/import layer, rendering layer, scripting layer, and app settings layer.
- For creation work, separate product guarantees from authoring craft: "what Tavo supports" is not the same as "what makes a good card/worldbook/regex/plugin".
- Treat roleplay packages as multi-object systems: card, persona, worldbook, preset, regex, memory plan, rendering, plugin, and media can cooperate but must be validated separately.
- Prefer evidence labels in answers: `official-current`, `mcp-runtime`, `live-verified`, `historical-derived`, `needs-live-verify`, `deprecated`.

## First-Pass Creation Priority

For this encyclopedia skill, the most important creation paths are:

- strong character cards with coherent persona, scenario, examples, greetings, and creator notes;
- worldbooks that inject the right facts at the right time without drowning context;
- regexes that clean or transform model output without corrupting intended text;
- EJS/macros that are readable, escapable, and testable;
- TavoJS/Advanced Rendering snippets that render visually in the Android app;
- plugins that package reusable behavior and include validation steps;
- MCP-assisted validation that proves imports and runtime behavior instead of relying on format guesses.
