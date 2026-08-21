# Prompt Authoring

This reference covers presets, worldbooks, regexes, long memory, and prompt architecture.

## Prompt Layers

| Layer | What it controls | Do not treat it as |
| --- | --- | --- |
| Preset | Reusable system behavior, output rules, prompt order, style, scenario framing, group progression, continuation, and helper prompts. | A specific character biography or lore database. |
| Worldbook | Conditional or constant background injected when trigger, scan, probability, and budget rules allow. | A guarantee that the model always recalls or obeys a fact. |
| Regex | Recognition, cleanup, replacement, formatting, and transformations at configured placements and timings. | A state database or guaranteed JavaScript runner. |
| Long memory | Retention of user preferences, habits, relationship facts, and important details through manual or automatic extraction. | Deterministic database recall. |
| Macros | Dynamic tokens and compact variable operations in prompt-bearing positions. | Universal execution in every display surface or metadata field. |
| EJS | Prompt logic using conditions, loops, variable operations, and macro-producing templates. | Full Node/browser EJS with include, partial, or custom delimiters. |

## Presets

Presets can define reusable behavior for:

- user/character relationship framing;
- character behavior and dialogue style;
- scenario handling;
- new-chat and example-chat behavior;
- group-chat progression;
- continuation;
- impersonation or helper-answer generation.

The TavoJS preset object uses `basicPrompts` and `entries`. Entries can contain identifier, name, content, enabled/active state, type, role, injection position, and injection depth.

Built-in prompt identifiers include:

- `main`
- `worldInfoBefore`
- `personaDescription`
- `charDescription`
- `charPersonality`
- `scenario`
- `enhanceDefinitions`
- `nsfw`
- `worldInfoAfter`
- `dialogueExamples`
- `chatHistory`
- `jailbreak`

Use presets for system-level behavior and assembly rules. Keep character-specific identity facts in the card unless the preset is deliberately shared by a family of characters.

## Worldbooks

Worldbooks maintain setting consistency, keep narrative focus, and reveal large settings through constant or triggered entries. Entry content is injected into the prompt; it does not normally appear as its own visible user message.

Important fields include:

- `strategy`: `constant` or `keyword`;
- `keywords` and `secondaryKeywords`;
- `secondaryKeywordStrategy`;
- `scanDepth`;
- `caseSensitive` and `matchWholeWord`;
- `injectionPosition`, `injectionDepth`, and `injectionRole`;
- `probability`;
- `sticky`, `cooldown`, and `delay`.

Authoring rules:

- Make each entry's `content` understandable on its own; title, keys, and comments may not be injected.
- Use precise triggers plus likely aliases, inflections, and names.
- Split large lore by function: location, faction, rule, secret, relationship, timeline, object.
- Put stable objective facts and conditional background here, not transient emotion or global output style.
- Avoid multiple entries that compete to restate the same fact.
- Treat CC-style keys, selective flags, and insertion positions as compatibility inputs; confirm the converted Tavo object after import.

## Regex

Regex can identify patterns, replace or trim text, clean formatting, and transform configured user, character, reasoning, or lorebook content. Timings include display, send, send-and-display, receive, and edit-and-receive paths. Substitution can be none/raw/escaped and may be limited by depth.

Use regex for:

- cleanup and normalization;
- shorthand expansion;
- status-display formatting;
- guarded transformation of known tags or blocks;
- assistant templates for reasoning, quotes, narration, Markdown code blocks, and tag-like text.

Boundaries:

- Regex output may contain text, macros, or HTML, but downstream timing determines whether a later engine expands or renders it.
- Import-object fields and TavoJS regex-object fields are not necessarily identical.
- Avoid destructive expressions without before/after fixtures and a rollback copy.
- Keep state mutation separate from display formatting.

## Long Memory

Long memory can retain user preferences, interests, habits, relationship details, and other important information across future conversations. Users can manage what is saved. Manual extraction and automatic extraction after roughly ten conversation turns/messages are separate mechanisms.

TavoJS represents current-chat memory as an enabled flag plus a list of memory strings. In Tavo 1.0, external MCP exposes get, update, and append operations. Append supports validation without persistence, ordered sequential parts, idempotent `clientRequestId`, and revision checks through `expectedRevision`.

Boundaries:

- Explicit storage does not prove that automatic extraction chose the right facts.
- Saved memory does not guarantee recall in every response.
- Injection timing, merge/deletion behavior, and cross-chat usefulness remain runtime- and model-dependent.
- Static world rules belong in the card or worldbook, not long memory.
- Do not silently convert guesses into memory; distinguish observed facts from interpretation.

## Prompt Assembly Validation

1. Lock the test inputs: preset, card, persona, worldbook, regex set, history, and current user message.
2. Use Prompt Lab to assemble the request in Tavo order and inspect the resulting roles and prompt blocks.
3. Test a baseline with no conditional trigger, then one primary keyword, a secondary-key condition, and a non-trigger near miss.
4. Test probability, sticky, cooldown, delay, scan depth, case sensitivity, and whole-word matching separately rather than in one opaque scenario.
5. Run regex at its actual placement/timing and compare raw, provider-facing, and display text.
6. For multi-turn behavior, run one turn at a time. Inspect the model output before choosing the next user message.
7. Stop when an upstream response succeeds but contains no usable text; do not silently manufacture an assistant message or continue the history.
8. Never modify a supplied test preset or unrelated object to make a test pass. Change only the object the user commissioned.

## Authoring Standards

- Prefer small, inspectable prompt components over monolithic blocks.
- Make each worldbook entry state why it exists, when it should fire, and what it must not override.
- Keep regex transformations reversible where possible and document destructive replacements.
- Separate style guidance, world facts, current state, and long-term memory.
- Compare semantic behavior, not just the presence of marker words.
