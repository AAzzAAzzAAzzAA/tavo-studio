# Capability Answer Playbook

Use this playbook when the user asks whether Tavo can do something, especially unusual UI, rendering, automation, or authoring work.

## Answer Shape

Lead with:

1. `Result`: supported, limited, workaround, not-established, or deprecated.
2. `Scope`: applicable Tavo version, configuration, and object type.
3. `How`: the shortest practical implementation path.
4. `Limits`: the exact axis the result does not cover.
5. `Check`: the smallest user-facing check when the installed build may differ.

Do not include private paths, identifiers, raw captures, or collection history. Do not turn a neighboring capability into proof of the requested one.

## Decision Ladder

1. Identify the exact object, action, and desired effect.
2. Read `references/00-capability-boundaries.md` and the topic reference.
3. Separate data shape, import, prompt behavior, persistence, UI/visual behavior, and model/media quality.
4. If the packaged result covers the exact axis, answer within its version boundary.
5. Otherwise return `not-established` and propose the smallest safe check only when the user wants one.

## Common Question Families

| User asks | First references | Smallest meaningful check |
| --- | --- | --- |
| Can I make a floating button in a chat/message? | `07-rendering-tavojs.md`, `18-ar-tavojs-plugin-patterns.md` | visible marker plus click/readback effect in the target app |
| Can a card include JS/CSS/HTML? | `07-rendering-tavojs.md` | import plus actual render/effect; source text alone is not enough |
| Can a plugin add an action or UI? | `08-plugins-tpg.md`, `18-ar-tavojs-plugin-patterns.md` | package validation, import, visible action, and bounded readback |
| Can MCP import/switch/read this object? | `11-mcp-runtime.md` | current tool availability, dry run, disposable write, readback |
| Can a worldbook trigger only under condition X? | `21-worldbook-entry-semantics.md` | one trigger input and one matched control in Prompt Lab or an isolated chat |
| Can regex change only the intended surface? | `23-regex-execution-pipeline.md` | before/after fixture plus provider/display/persistence comparison |
| Can EJS/macros compute dynamic prompt text? | `06-macros-ejs.md`, `27-prompt-lab.md` | rendered field, variable trace, and final compiled message |
| Can API/model settings be changed by MCP? | `10-app-settings-data.md`, `11-mcp-runtime.md` | current tool/schema check; do not infer settings writes from unrelated tools |

## Calibration Rules

- Say `supported` only for the exact behavior and stated version/configuration.
- Say `limited` when the direct path works only in a subset or requires a fallback.
- Say `workaround` when another mechanism can reach the user goal but is not equivalent.
- Say `not-established` when only shape, neighboring behavior, or an older incompatible result exists.
- Say `deprecated` when an old API or assumption should not be used in new work.

## Minimum Check Pattern

When the user authorizes a live check, use the smallest disposable object:

- one isolated card/chat/plugin/worldbook;
- one unambiguous marker or variable value;
- one dry-run or local validation step;
- one actual effect and one readback/visible postcondition;
- one cleanup or explicit retention decision.

Do not use real user data, destructive restore, persistent settings, or paid model calls unless they are within the user's requested scope. Do not solve a prompt problem with a plugin merely because JavaScript is available, and do not solve an app-operation problem with EJS merely because it can change prompt state.
