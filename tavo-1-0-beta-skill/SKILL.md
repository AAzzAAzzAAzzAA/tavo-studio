---
name: tavo-skill
description: Create, revise, explain, validate, and prompt-test Tavo or SillyTavern character cards, personas, worldbooks, presets, regexes, EJS templates, TavoJS/Advanced Rendering, TPG plugins, Agent Loop workflows, media settings, and MCP operations. Use when the user mentions Tavo, Tavo AI, 预设, 角色卡, 世界书, 正则, EJS, TavoJS, 高级前端, TPG, Agent Loop, Prompt Lab, or asks how these parts affect the final model request.
---

# Tavo Skill

Use this skill as the community entry point for Tavo capability questions, artifact authoring, and text-prompt simulation. Load only the references needed for the current task.

This distribution is result-oriented. State the capability, applicable version, limitations, and confidence boundary. Do not expose private test paths, device/chat/request identifiers, credentials, raw captures, crawl manifests, or the process by which the packaged conclusions were obtained.

## Result Contract

Use these result states when a product claim needs qualification:

- `supported`: the behavior may be relied on within the stated version and scope.
- `limited`: the behavior works only under the stated conditions or has known gaps.
- `not-established`: the package does not contain enough information to promise it.
- `deprecated`: do not use the old behavior or API in new work.
- `creative-guidance`: an authoring recommendation, not a product guarantee.

Keep proof axes separate. Prompt assembly does not prove visual rendering, persistence, import roundtrip, model quality, media quality, or every provider. Prompt Lab proves only the text/request surfaces it actually compiles or calls.

If a current installation may differ from the packaged version summary, say so and inspect the user's current runtime only when they ask for a live check. Return the result without adding private runtime traces to this skill.

## Editing Authority

Modify only the object the user commissioned in the current task.

- A preset task may edit the commissioned preset.
- A character-card task may edit the commissioned card.
- A worldbook, persona, regex, EJS, rendering, or plugin task may edit only that commissioned object.
- Other supplied assets are read-only test fixtures unless the user explicitly commissions them too.
- Never alter a fixture to make a test pass. Report the incompatibility or limitation.

Choose one creative authority mode before substantial writing:

1. `collaborative`: implement only user-confirmed substantive choices; suggestions stay proposals until accepted.
2. `demo-delegated`: after the user accepts a small demo and authorizes continuation, expand within the locked direction and record material assumptions; do not change core identity, relationship premises, hard limits, or delivery goals.
3. `cleaning`: improve existing prose without adding facts or changing meaning.

Read `references/29-creation-intake-interview.md`, `references/13-creation-craft-workflows.md`, and `references/30-prose-detone.md` for the full handoff rules.

## Task Routing

| Task | Read first | Then use |
| --- | --- | --- |
| What Tavo can do; feature comparison; unusual capability question | `references/02-capabilities-overview.md`, `references/16-capability-answer-playbook.md` | `references/00-capability-boundaries.md` and the feature reference |
| Vague or from-zero creation | `references/29-creation-intake-interview.md` | `references/33-quick-card-funnel.md`, `references/13-creation-craft-workflows.md` |
| Character card, persona, greetings, examples, PNG card | `references/03-characters-cards-personas.md`, `references/24-character-opening-and-examples.md` | `references/17-authoring-blueprints.md`, card/PNG scripts |
| Worldbook and keyword/depth/probability behavior | `references/21-worldbook-entry-semantics.md`, `references/05-prompt-authoring.md` | worldbook templates and validator |
| Preset order, roles, markers, depth, injection | `references/22-preset-prompt-injection.md`, `references/05-prompt-authoring.md` | Prompt Lab |
| Regex placement, timing, substitution, display/send/persistence | `references/23-regex-execution-pipeline.md` | `scripts/run_regex_fixtures.py`, Prompt Lab |
| Macros and EJS | `references/06-macros-ejs.md`, `references/25-ejs-tavojs-plugin-boundaries.md` | Prompt Lab and `scripts/tavo_ejs_worker.mjs` |
| Compile preset + card + persona + worldbooks + regexes; test model reaction | `references/27-prompt-lab.md` | `scripts/tavo_prompt_lab.py` |
| Advanced Rendering, CSS/JS, TavoJS | `references/07-rendering-tavojs.md`, `references/18-ar-tavojs-plugin-patterns.md` | `references/25-ejs-tavojs-plugin-boundaries.md` |
| TPG plugin authoring and packaging | `references/08-plugins-tpg.md`, `references/18-ar-tavojs-plugin-patterns.md` | plugin templates and validators |
| Agent Loop, MCP, memory, messages, tool calling | `references/11-mcp-runtime.md`, `references/10-app-settings-data.md` | `scripts/tavo_mcp_client.py` when live access is authorized |
| Image, voice, TTS, ASR, provider settings | `references/09-media-voice-image.md`, `references/10-app-settings-data.md` | state the sensory/provider boundary explicitly |
| Debugging or suspicious old APIs | `references/19-debugging-pitfalls.md`, `references/25-ejs-tavojs-plugin-boundaries.md` | scan and validation scripts |
| Remove AI tone from authored prose | `references/30-prose-detone.md` | `references/31-prose-detone-catalog.md`, `references/32-prose-detone-narrative.md` |

## Default Workflows

### Capability answers

1. Identify the exact object and behavior.
2. Read its reference and `references/00-capability-boundaries.md`.
3. Answer with result, version/scope, and limitation.
4. If the result is not established, say so; do not invent a hidden API or promote a neighboring feature.

### Creation and revision

1. Resolve the creative authority mode.
2. Inspect supplied assets without changing uncommissioned objects.
3. Draft the smallest correct mechanism and keep related facts in the correct field.
4. Validate structure with the matching local validator.
5. Run Prompt Lab when the acceptance question is how the assembled text affects a model.
6. Run the detone and cross-field checks before delivery.
7. Deliver a separate report only when the user requests one.

For a narrow revision, change only the requested point and then offer a separate global audit. For a requested global audit, report the findings and let the user approve broad changes.

### Prompt Lab

Prompt Lab is the default acceptance surface for ordinary single-chat text behavior. It supports preset/card/persona/worldbook composition, keyword activation, supported regex stages, macros, sandboxed prompt-field EJS, provider/display/persistence views, real model calls, and adaptive multi-turn state.

Prefer `run-turn` for multi-turn tests:

1. Run one turn.
2. Inspect the compiled request and reply.
3. Choose the next user input deliberately.
4. Continue only after a successful text response.

Stop on HTTP failure, empty text, tool-only output, unsupported response shape, malformed structured streaming data, or an explicit stream error. A failed turn must not commit conversation or EJS state.

Do not claim Prompt Lab covers Advanced Rendering DOM/WebView behavior, TavoJS bridge effects, plugin lifecycle, native Agent Loop execution, app persistence, import/export fidelity, or media quality.

### Live operations

Live MCP calls, request relays, model calls, imports, writes, and UI operations require the user's current authorization and target. Redact credentials by default. Prefer read-only inspection before mutation and keep captured output outside the distributable skill tree.

## Included Scripts

- `scripts/tavo_prompt_lab.py`: compile and optionally call a text model; supports adaptive stateful turns.
- `scripts/tavo_ejs_worker.mjs`: bounded prompt-field EJS sandbox used by Prompt Lab.
- `scripts/tavo_virtual_provider.py`: loopback deterministic provider for offline protocol tests.
- `scripts/tavo_request_capture_gateway.py`: optional credential-redacting OpenAI-compatible request relay.
- `scripts/tavo_mcp_client.py`: small redacting JSON-RPC client for an authorized Tavo MCP endpoint.
- `scripts/validate_tavo_artifact.py`: validate cards, worldbooks, regex fixtures, TPG manifests, or generic JSON.
- `scripts/run_regex_fixtures.py`: execute deterministic regex fixtures.
- `scripts/validate_tpg_package.py`, `scripts/tpg_spec2.py`: validate TPG packages and spec-2 semantics.
- `scripts/embed_st_card_png.mjs`, `scripts/extract_st_card_png.mjs`, `scripts/png-card-lib.mjs`: handle PNG character-card payloads.
- `scripts/worldbook_to_character_book.mjs`: convert a standalone worldbook into `character_book` form.
- `scripts/generate_from_template.py`: create a new artifact from a bundled template.
- `scripts/compare_roundtrip_export.py`: compare expected and exported JSON structures.
- `scripts/scan_deprecated_tavojs.py`: scan authored code for unsupported legacy TavoJS calls.
- `scripts/audit_skill_skeleton.py`, `scripts/audit_tavo_skill.py`: self-contained community package audits.
- `scripts/test_tavo_prompt_lab.py`, `scripts/test_tavo_mcp_client.py`, `scripts/test_tavo_virtual_provider.py`, `scripts/test_tavo_request_capture_gateway.py`, `scripts/test_validate_tpg_package.py`: bundled regression suites run by the discovery command below.

## Reference Index

- `references/00-capability-boundaries.md`: packaged capability/version boundaries and answer rules.
- `references/02-capabilities-overview.md`: product capability overview.
- `references/03-characters-cards-personas.md`: card, persona, import/export, and compatibility behavior.
- `references/04-chat-workflows.md`: chat and group-chat operations.
- `references/05-prompt-authoring.md`: presets, worldbooks, regexes, memory, and prompt layers.
- `references/06-macros-ejs.md`: macro and EJS behavior.
- `references/07-rendering-tavojs.md`: Advanced Rendering and TavoJS boundaries.
- `references/08-plugins-tpg.md`: TPG package and runtime behavior.
- `references/09-media-voice-image.md`: media, image, voice, TTS, and ASR boundaries.
- `references/10-app-settings-data.md`: settings, providers, backup, storage, and Agent Loop controls.
- `references/11-mcp-runtime.md`: MCP and native Agent Loop boundaries.
- `references/13-creation-craft-workflows.md`: creative authority, craft, reviews, and delivery.
- `references/16-capability-answer-playbook.md`: calibrated capability-answer workflow.
- `references/17-authoring-blueprints.md`: repeatable authoring blueprints.
- `references/18-ar-tavojs-plugin-patterns.md`: rendering and plugin implementation patterns.
- `references/19-debugging-pitfalls.md`: common failures and deprecated assumptions.
- `references/21-worldbook-entry-semantics.md`: worldbook entry semantics.
- `references/22-preset-prompt-injection.md`: preset entry and injection semantics.
- `references/23-regex-execution-pipeline.md`: regex execution pipeline.
- `references/24-character-opening-and-examples.md`: opening and example-message fields.
- `references/25-ejs-tavojs-plugin-boundaries.md`: mechanism and permission boundaries.
- `references/27-prompt-lab.md`: Prompt Lab case format and operation.
- `references/29-creation-intake-interview.md`: creation intake.
- `references/30-prose-detone.md`: prose cleaning protocol.
- `references/31-prose-detone-catalog.md`: general detone catalog.
- `references/32-prose-detone-narrative.md`: narrative/RP and lexical detone catalog.
- `references/33-quick-card-funnel.md`: quick-card candidate and direct-output loop.

## Package Validation

Runtime requirements:

- Python 3.10 or newer.
- Node.js with `--permission` and `--allow-fs-read` support for EJS. The comprehensive audit checks these flags and compiles both bundled Prompt Lab templates.

Run from the skill root:

```bash
python3 -B scripts/audit_skill_skeleton.py .
python3 -B scripts/audit_tavo_skill.py .
python3 -B -W error::ResourceWarning -m unittest discover -s scripts -p 'test_*.py'
```

The published directory name must be `tavo-skill` so it matches the frontmatter name and explicit `$tavo-skill` trigger. A development checkout may use another folder name, but its packaged/install target must use `tavo-skill`.
