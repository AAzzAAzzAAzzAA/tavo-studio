---
name: tavo-1-0-beta
description: Beta Tavo 1.0 encyclopedia, creation, and prompt-simulation workflow skill. Use when Codex is explicitly asked to work with Tavo 1.0 beta, native Agent Loop/tool calling, MCP 1.0, memory.append, the 1.0 plugin center, or to create, audit, validate, and test Tavo or SillyTavern cards, worldbooks, presets, personas, regexes, EJS, TavoJS, Advanced Rendering, plugins, media, app settings, and model-visible prompt behavior against the versioned 1.0 evidence overlay.
---

# Tavo 1.0 Beta

Use this skill as the single entry point for Tavo capability answers and Tavo creation workflows. It is intentionally reference-heavy: load only the reference files required by the user's task, then cite the evidence tier used for any current-product claim.

For any claim introduced or changed by Tavo `1.0.0`, read the feature-specific reference and then `references/28-tavo-100-live-evidence.md`. The 1.0 overlay promotes only the tested Agent Loop, MCP, memory, message, and plugin-center axes. It does not silently upgrade unrerun 0.93/0.92/0.91 evidence. Virtual-provider responses never count as model semantics or real-provider compatibility, and a real-provider response never proves an unrelated app capability.

## Evidence Priority

Use two separate judgments instead of one flat ranking:

1. **Declared surface:** fresh official documentation, then the current MCP runtime surface and schemas, then historical material.
2. **Observed reliability:** fresh Android/MCP experiments on the current app version. A reproducible live failure or mixed result controls any claim that a documented feature works reliably; official support text must not erase a current runtime regression.

Do not treat old skill references as current Tavo facts. When current sources conflict, report the conflict and its exact scope. Use `mixed` or `blocked` for reliability instead of selecting whichever source is more convenient.

## Evidence Labels

- `official-current`: Found in the latest official docs crawl.
- `release-announcement`: Stated in the current release notice but not yet backed by updated feature documentation; use it to choose tests, not as schema or reliability proof.
- `mcp-runtime`: Found through the current MCP server surface or runtime docs.
- `live-verified`: Proved on the connected Android app during this run.
- `historical`: Useful material from older skills that still needs current confirmation.
- `deprecated`: Old claim known to be removed, unsafe, or contradicted by newer evidence.
- `creative-guidance`: Authoring advice that improves cards, worldbooks, regexes, prompts, plugins, or rendering, but is not itself a product API guarantee.
- `historical-derived`: Non-conflicting reusable material from old skills, kept with a validation boundary until current docs/MCP/live tests support stronger claims.

Use validation levels separately from source labels: `schema-seen`, `dry-run-pass`, `roundtrip-pass`, `semantic-pass`, `semantic-pass-observation`, `ui-pass`, `live-verified`, `live-verified-regression`, and `semantic-mixed`. Semantic, visual, persistence, and import proof are orthogonal; never promote one into another without the matching evidence.

## Task Routing

| User task | Read first | Then read |
| --- | --- | --- |
| "Tavo 能干嘛", feature comparison, unusual capability questions | `references/02-capabilities-overview.md`, `references/16-capability-answer-playbook.md` | `references/00-source-of-truth.md`, `references/14-evidence-registry.md`, `references/01-official-url-map.md` |
| Character cards, personas, greetings, examples, PNG cards, SillyTavern compatibility | `references/03-characters-cards-personas.md`, `references/24-character-opening-and-examples.md`, `references/17-authoring-blueprints.md` | `scripts/validate_tavo_artifact.py`, `scripts/embed_st_card_png.mjs`, `scripts/extract_st_card_png.mjs`, `scripts/worldbook_to_character_book.mjs` |
| Card/worldbook creative quality, role design, gameplay-mode planning | `references/13-creation-craft-workflows.md`, `references/17-authoring-blueprints.md` | `references/03-characters-cards-personas.md`, `references/05-prompt-authoring.md` |
| Chat pages, group chat, shortcuts, translation, history workflows | `references/04-chat-workflows.md` | `references/11-mcp-runtime.md` when automation or import/export is involved |
| Presets and prompt injection depth/order | `references/22-preset-prompt-injection.md`, `references/05-prompt-authoring.md` | `references/12-validation-matrix.md` |
| Worldbooks, keywords, secondary logic, depth, probability, timing | `references/21-worldbook-entry-semantics.md`, `references/05-prompt-authoring.md` | `references/12-validation-matrix.md` |
| Compile a preset + card + persona + worldbooks into the final text request, inspect triggers, or test a real model response without a phone | `references/27-prompt-lab.md`, `scripts/tavo_prompt_lab.py` | `references/22-preset-prompt-injection.md`, `references/21-worldbook-entry-semantics.md`, `references/24-character-opening-and-examples.md` |
| Regex timing, scope, substitution, display/send/persistence pipeline | `references/23-regex-execution-pipeline.md`, `references/05-prompt-authoring.md` | `references/12-validation-matrix.md`, `scripts/run_regex_fixtures.py` |
| Macros and EJS authoring | `references/06-macros-ejs.md`, `references/25-ejs-tavojs-plugin-boundaries.md` | `references/12-validation-matrix.md` |
| Advanced Rendering, CSS/JS, TavoJS, WebView behavior | `references/07-rendering-tavojs.md`, `references/18-ar-tavojs-plugin-patterns.md`, `references/25-ejs-tavojs-plugin-boundaries.md` | `references/12-validation-matrix.md`, `references/15-phone-validation-runbook.md` |
| TPG plugins, plugin packaging, plugin UI/actions | `references/08-plugins-tpg.md`, `references/18-ar-tavojs-plugin-patterns.md`, `references/25-ejs-tavojs-plugin-boundaries.md` | `references/11-mcp-runtime.md`, `scripts/validate_tpg_package.py` |
| Image sending, image generation, voice, TTS/STT | `references/09-media-voice-image.md` | `references/10-app-settings-data.md` |
| App settings, API keys, model providers, Agent Loop switches, backup/storage/data | `references/10-app-settings-data.md` | `references/28-tavo-100-live-evidence.md`, `references/01-official-url-map.md` |
| MCP operation, Agent Loop/tool calling, read-only inspection, import validation | `references/11-mcp-runtime.md`, `references/28-tavo-100-live-evidence.md`, `references/15-phone-validation-runbook.md` | `scripts/dump_mcp_surface.py`, `scripts/compare_mcp_surfaces.py`, `scripts/tavo_mcp_client.py` |
| Proving "can this be done?" or designing new experiments | `references/16-capability-answer-playbook.md`, `references/12-validation-matrix.md` | `references/14-evidence-registry.md`, `references/15-phone-validation-runbook.md`, the feature-specific reference above |
| Reconciling old skills or suspicious old APIs | `references/historical/deprecated-claims.md`, `references/19-debugging-pitfalls.md` | `references/00-source-of-truth.md` |
| Forward-testing this skill with subagents | `references/20-forward-testing.md` | `references/14-evidence-registry.md` |

## Subagent Rules

Use subagents for independent review when expanding or validating this skill:

- Official docs agent: refresh the current official information architecture and URL list from the live docs site.
- Historical audit agent: inspect old Tavo-family skills and report only recyclable material, deprecated claims, and migration risks.
- Skill engineering agent: check `SKILL.md`, `agents/openai.yaml`, reference routing, script indexing, and skill-creator compliance.
- Creation coverage agent: look for gaps in cards, worldbooks, regexes, EJS, TavoJS, Advanced Rendering, and plugins.
- Runtime validation agent: review the Android/MCP test matrix before live writes or UI experiments.

Keep delegated work bounded. Subagents should not move, delete, or edit old Tavo skills during the skeleton phase.

## Scripts

- `scripts/fetch_official_docs.py`: crawl the current official docs site into a timestamped local evidence folder and emit `url_map.json`.
- `scripts/normalize_official_docs.py`: turn a docs crawl into a durable manifest with topic, hash, line count, and reference routing metadata.
- `scripts/dump_mcp_surface.py`: read/list the connected Tavo MCP server surface and redact authorization values in saved output.
- `scripts/compare_mcp_surfaces.py`: compare two raw redacted MCP surface dumps and report added/removed tools, resources, templates, prompts, plus changed common tool schemas/descriptions.
- `scripts/test_dump_mcp_surface.py`: verify the strict MCP gate requires all five top-level reads, every selected runtime document, and a successful read-only `tavo_status` call.
- `scripts/normalize_mcp_surface.py`: turn a redacted MCP dump into a compact tools/resources/templates index with risk labels.
- `scripts/tavo_mcp_client.py`: call Tavo MCP JSON-RPC methods and tools through the correct `tools/call` path with redacted output by default.
- `scripts/tavo_phone_capture.py`: capture ADB device state, Tavo package/window state, UIAutomator XML, and screenshot evidence.
- `scripts/tavo_phone_validate.py`: create validation artifact directories and run repeatable phone/MCP cases while retaining real-phone evidence by default.
- `scripts/run_phone_kpi_batch.py`: execute large retained real-phone validation batches, including at least 50 imported test assets and at least 50 real model API sends when required.
- `scripts/run_phone_semantic_kpi.py`: run the strict ten-family, 50-primary-call semantic epoch with retained attempts, negative controls, runtime isolation, screenshots, and exact restoration.
- `scripts/run_phone_semantic_ui_preflight.py`: prove all AR, TavoJS, plugin, and EJS UI actions on the real phone without consuming model-call KPI credit.
- `scripts/run_phone_cross_feature_matrix.py`: run the retained cross-feature matrix for lorebook, regex, preset, character, message, input, TavoJS, and plugin interactions.
- `scripts/aggregate_cross_feature_matrix.py`: select one strongest retained result per canonical cross-feature case and emit a coverage-complete stitched evidence manifest without pretending it was one green epoch.
- `scripts/run_phone_prompt_edge_matrix.py`: run gap-driven prompt edge cases for worldbook activation, preset role/depth/order, and regex placement/timing; do not use it to repeat already-settled baseline facts.
- `scripts/test_run_phone_prompt_edge_matrix.py`: validate the prompt-edge case catalog, dependency graph, fail-closed state, and offline result classification without touching the phone.
- `scripts/run_phone_asset_roundtrip_matrix.py`: run retained native/CCv2/CCv3/PNG character and persona import/export/readback cases when exact asset compatibility needs current proof.
- `scripts/test_run_phone_asset_roundtrip_matrix.py`: validate asset-roundtrip case ownership, resume behavior, and structured blocked outcomes offline.
- `scripts/run_phone_media_provider_matrix.py`: enumerate and test only currently exposed media/provider paths, requiring concrete readback/audio/transcript semantics and emitting structured blocked evidence for deferred or UI-only surfaces.
- `scripts/test_run_phone_media_provider_matrix.py`: validate the media matrix, semantic result assertions, and fail-closed unsupported-surface behavior offline.
- `scripts/run_phone_plugin_092_matrix.py`: prepare the F01-F11 Tavo 0.92 plugin matrix, build deterministic fixtures, evaluate retained assertions, and safely stage disabled fixtures only in an explicitly isolated test chat.
- `scripts/test_run_phone_plugin_092_matrix.py`: verify the 0.92 matrix catalog, dependency closure, deterministic packages, protected-chat refusal, redaction, evidence evaluation, and no-send staging contract offline.
- `scripts/tavo_093_runner_core.py`: shared 0.93 zero-real-model plan, private-artifact, durable-intent, terminal-result, A-J coverage, and final-restoration gates; its live adapter is deliberately fail-closed until a reviewed executor is attached.
- `scripts/tavo_093_full_catalog.py`: expand the approved 0.93 A-J plan into 192 independently terminal cases, including every retained 34-case prompt-edge and 35-case cross-feature row.
- `scripts/test_tavo_093_full_catalog.py`: verify the fine-grained A-J counts and prevent real-model/manual rows from being reported as zero-call passes.
- `scripts/run_phone_plugin_093_matrix.py`: prepare the coarse spec 2/plugin phase graph and reserve one durable blocked intent when no reviewed live adapter is present.
- `scripts/test_run_phone_plugin_093_matrix.py`: verify plugin-093 catalog/dependency safety, private preparation, explicit live authorization, and no-contact blocked staging.
- `scripts/run_phone_plugin_093_live.py`: execute the isolated spec 2 manifest/runtime matrix with fresh artifacts, pre-send durable intents, collision checks, retained disabled fixtures, and exact readback.
- `scripts/test_run_phone_plugin_093_live.py`: verify the 0.93 live plugin catalog, package construction, offline planning, privacy modes, and no-contact behavior.
- `scripts/run_phone_plugin_093_package_actual.py`: exercise actual Tavo package-root selection and path-rejection cases with dry-run, durable actual intent, collision checks, and disable-and-retain handling for unexpected installs.
- `scripts/test_run_phone_plugin_093_package_actual.py`: verify the actual-package case catalog and fail-closed offline plan without contacting the phone.
- `scripts/run_phone_093_nonplugin_matrix.py`: prepare the 0.93 UI/model/ASR/voice/fix/restoration phase graph with the real-provider phase blocked in this epoch.
- `scripts/test_run_phone_093_nonplugin_matrix.py`: verify non-plugin release coverage, endpoint-file privacy, identity-stable resume, and no live contact from offline modes.
- `scripts/run_phone_093_master.py`: compose the 192-row detailed catalog with coarse plugin/non-plugin/meta rows into the 216-case terminal run, enforcing A-J coverage, zero-real policy, and exact restoration.
- `scripts/test_run_phone_093_master.py`: verify the master phase graph, full catalog, zero-real result contract, complete-with-findings behavior, and strict final gate.
- `scripts/tavo_virtual_provider.py`: serve deterministic local Chat Completions, Responses, Completions, Messages, image, TTS, multipart ASR, and OpenRouter audio-chat fixtures without any upstream or forwarding path; captures are private and media bodies become MIME/length/SHA-256 metadata.
- `scripts/test_tavo_virtual_provider.py`: exercise virtual-provider auth/allowlists, protocols, streaming, faults, media redaction, unknown-route 501 behavior, and private file modes on loopback only.
- `scripts/tavo_prompt_lab.py`: compile Tavo-native presets, cards, personas, worldbooks, visible history, greetings, and current input into an evidence-bounded OpenAI-compatible request; render authored prompt-field EJS in a short-lived sandbox before macros; optionally call a real model without storing credentials in artifacts.
- `scripts/tavo_ejs_worker.mjs`: isolated Node VM worker for the documented prompt-only EJS subset, JSON chat/global state, whole-field fallback, and bounded variable traces; it does not expose TavoJS, DOM, network, filesystem, or plugin APIs.
- `scripts/test_tavo_prompt_lab.py`: verify relative/absolute order, marker expansion, greetings, examples, worldbook decisions/positions, EJS syntax/state/fallback/security, EJS-to-macro ordering, private output, and loopback-only virtual-provider execution.
- `scripts/tavo_fixture_capture_assert.py`: correlate virtual captures by nonce/intent and assert request fields, order, counts, retries, disconnects, and completion while permanently reporting zero real-model calls and no KPI credit.
- `scripts/test_tavo_fixture_capture_assert.py`: validate capture correlation, lifecycle aggregation, JSON-pointer assertions, fail-closed specs, and private reports offline.
- `scripts/tavo_generation_hook_fixture.py`: run a deterministic, source-allowlisted OpenAI-compatible LAN fixture for JSON, SSE, slow-stream, HTTP 500, and protocol-error generation-hook tests with private redacted captures.
- `scripts/test_tavo_generation_hook_fixture.py`: verify fixture authentication, allowlisting, deterministic responses, faults, streaming, secret-file rules, and capture redaction offline.
- `scripts/tavo_request_capture_gateway.py`: run a short-lived, credential-redacting OpenAI-compatible LAN relay when exact final model requests must be inspected; use source allowlists and stop it after capture.
- `scripts/test_tavo_request_capture_gateway.py`: verify gateway auth, redaction, private artifacts, redirect blocking, upstream errors, and incremental SSE relay offline.
- `scripts/test_run_phone_semantic_kpi_faults.py`: inject offline transaction faults and verify resume does not silently resend or overwrite terminal evidence.
- `scripts/test_run_phone_cross_feature_matrix.py`: exercise cross-feature ownership, no-resend, failure classification, and restoration paths without touching the phone.
- `scripts/run_phone_import_kpi.py`: retained historical import-volume runner; use the strict import artifact as its terminal evidence and prefer newer fail-closed runners for future epochs.
- `scripts/run_phone_coverage_kpi.py`: retained coverage probe used to enumerate phone-side capability paths; do not confuse its case count with semantic proof.
- `scripts/run_phone_ejs_runtime_diagnostic.py`: targeted EJS runtime seed/probe diagnostic with real chat evidence.
- `scripts/run_phone_preset_hidden_seed_diagnostic.py`: targeted preset-hidden-seed diagnostic for prompt-path isolation.
- `scripts/tavo_ui_tree.py`: semantic UIAutomator locator plus fail-closed ADB tap, swipe, and long-press helper requiring unique fresh bounds and a target-specific postcondition.
- `scripts/test_tavo_ui_tree.py`: verify gesture bounds, long-click/scrollability requirements, postconditions, timeout side-effect classification, and refusal before ADB on ambiguous targets.
- `scripts/audit_skill_skeleton.py`: verify reference/script indexing, absence of initialization remnants, and old-skill isolation.
- `scripts/audit_tavo_skill.py`: full local audit for reference indexing, required assets, scripts, evidence registry, and secret checks.
- `scripts/validate_tavo_artifact.py`: validate local cards, worldbooks, regex fixtures, plugin manifests, MCP dumps, and evidence registry files.
- `scripts/generate_from_template.py`: render `{{variable}}` template variables into concrete artifacts.
- `scripts/run_regex_fixtures.py`: run before/after regex fixtures with deterministic local checks.
- `scripts/validate_tpg_package.py`: validate plugin package structure, manifest fields, path safety, and optional requirements such as input actions, HTML fragments, and marker text.
- `scripts/tpg_spec2.py`: shared spec 1/2 manifest semantics for SemVer, min-app comparison, locale/catalog rules, strict `$t` placement, settings, and package-relative paths.
- `scripts/test_validate_tpg_package.py`: verify root/nested selection, entry precedence, legacy fallback, spec 2 SemVer/minAppVersion/i18n/catalog rules, and path/symlink/ambiguity rejection offline.
- `scripts/scan_deprecated_tavojs.py`: scan generated artifacts and old snippets for deprecated or risky TavoJS patterns.
- `scripts/compare_roundtrip_export.py`: compare submitted JSON with imported/readback/exported JSON to detect normalization or field loss.
- `scripts/record_validation_artifact.py`: append or update evidence registry rows after local, MCP, or phone validation.
- `scripts/png-card-lib.mjs`: shared PNG text-chunk helper used by the ST PNG tools.
- `scripts/embed_st_card_png.mjs`: embed a SillyTavern character JSON payload into a PNG.
- `scripts/extract_st_card_png.mjs`: extract embedded SillyTavern card data from a PNG.
- `scripts/worldbook_to_character_book.mjs`: convert compatible worldbook/lorebook data into a `character_book` payload.

## Reference Files

| File | Purpose |
| --- | --- |
| `references/00-source-of-truth.md` | Evidence hierarchy, source labels, stale-source policy, and old-skill quarantine rules. |
| `references/01-official-url-map.md` | Current official documentation IA and URL inventory from a fresh crawl. |
| `references/02-capabilities-overview.md` | Main entry for answering Tavo capability questions and inferring unusual feature boundaries. |
| `references/03-characters-cards-personas.md` | Character cards, personas, PNG cards, imports, exports, and compatibility boundaries. |
| `references/04-chat-workflows.md` | Chat, group chat, shortcuts, translation, history, and conversation operations. |
| `references/05-prompt-authoring.md` | Presets, worldbooks, regexes, long memory, and prompt construction workflows. |
| `references/06-macros-ejs.md` | Macro expansion, EJS templates, context variables, and escaping rules. |
| `references/07-rendering-tavojs.md` | Advanced Rendering, CSS/JS behavior, TavoJS APIs, and WebView verification. |
| `references/08-plugins-tpg.md` | TPG plugin structure, packaging, manifests, actions, and validation. |
| `references/09-media-voice-image.md` | Voice, image, media generation, image sending, and media provider setup. |
| `references/10-app-settings-data.md` | App settings, API/model providers, backup, storage, and data management. |
| `references/11-mcp-runtime.md` | MCP connection, tool/resource discovery, safety classes, and import checks. |
| `references/12-validation-matrix.md` | Test matrix for turning official/MCP claims into live Android evidence. |
| `references/13-creation-craft-workflows.md` | Historical-derived creative workflows from old Tavo Studio that do not conflict with current official docs. |
| `references/14-evidence-registry.md` | Claim registry rules, evidence promotion, and seed live-verified claims. |
| `references/15-phone-validation-runbook.md` | Proven real-phone validation workflow using MCP, UIAutomator, ADB fallback, screenshots, and retained evidence. |
| `references/16-capability-answer-playbook.md` | How to answer unusual "can Tavo do X?" questions without overclaiming. |
| `references/17-authoring-blueprints.md` | Repeatable creation workflows for cards, worldbooks, presets, regexes, EJS, rendering, plugins, and packages. |
| `references/18-ar-tavojs-plugin-patterns.md` | Evidence-bounded Advanced Rendering, TavoJS, floating UI, and plugin implementation patterns. |
| `references/19-debugging-pitfalls.md` | Common failures: import normalization, stale MCP, render proof, old APIs, secrets, and UI limits. |
| `references/20-forward-testing.md` | Subagent forward-testing prompts and scoring rules for this skill. |
| `references/21-worldbook-entry-semantics.md` | Native worldbook fields, constant/keyword activation, secondary logic, scan/depth/role, probability/timing, compatibility mappings, and evidence boundaries. |
| `references/22-preset-prompt-injection.md` | Preset object model, relative/absolute entries, depth/order/role, active-preset behavior, and validation workflow. |
| `references/23-regex-execution-pipeline.md` | Regex placements, timings, substitutions, depth, display/send/persistent-message distinctions, and A/B validation. |
| `references/24-character-opening-and-examples.md` | First messages, alternate greetings, dialogue examples, channel field mappings, imports, chat creation, and thread switching. |
| `references/25-ejs-tavojs-plugin-boundaries.md` | Macro, EJS, TavoJS, TPG, and MCP capability boundaries for variables, worldbooks, messages, input, permissions, and visual proof. |
| `references/26-tavo-093-live-evidence.md` | Prior 0.93 Android/MCP zero-real evidence overlay, promoted capabilities, non-promotion rules, and repeatable validation workflow. |
| `references/27-prompt-lab.md` | Agent-callable text-only prompt compiler/runner, sandboxed prompt-field EJS-before-macros behavior, case format, assembly rules, worldbook trigger report, model-call security, and explicit v2 equivalence boundaries. |
| `references/28-tavo-100-live-evidence.md` | Current 1.0 Agent Loop/MCP evidence overlay, exact 0.93 surface delta, loading modes, tool ownership, tested semantics, retry boundary, and restored state. |
| `references/historical/deprecated-claims.md` | Historical claims from old skills that must not silently enter new answers. |

## Skeleton Maintenance

Before accepting skeleton or reference edits, run:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/tavo-1-0-beta
python3 skills/tavo-1-0-beta/scripts/audit_skill_skeleton.py skills/tavo-1-0-beta
python3 skills/tavo-1-0-beta/scripts/audit_tavo_skill.py skills/tavo-1-0-beta
```

For product facts, refresh official docs with fail-closed `scripts/fetch_official_docs.py`, normalize with `scripts/normalize_official_docs.py`, and reread MCP runtime state with `scripts/dump_mcp_surface.py --strict` when a connected phone is available.

Current reusable 1.0 evidence lives in `assets/evidence/1.0.0/20260807-gate.json` and `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`. The retained 0.93 evidence remains the latest broad zero-real overlay for capabilities not rerun on 1.0: `assets/evidence/0.93.0/20260726-gate.json`, `assets/evidence/0.93.0/20260726-zero-real-matrix.json`, and `assets/evidence/0.93.0/20260726-case-outcomes.json`. Keep raw/private phone captures under `artifacts/`; never use them as distributable Skill assets.
