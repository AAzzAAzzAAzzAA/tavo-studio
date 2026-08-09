# Macros And EJS

This reference covers macro and EJS prompt logic.

## Macros

Macros are dynamic tokens used in character definitions, presets, worldbooks, regexes, and other generation-prompt positions.

Basic forms:

- `{{macroName}}`
- `{{macroName::arg}}`
- escaped braces when literal braces are needed;
- comment-style macros that render as empty text.

Macro families include:

- user, character, group, muted-member, and active-member values;
- card fields such as description, personality, scenario, persona, prompts, examples, version, and creator notes;
- current input, last message, and last user message;
- date/time, random, and formatting helpers;
- chat-variable get/set/add/increment/decrement operations;
- matching global-variable operations;
- legacy compatibility macros.

Macro names can change as the app evolves. Confirm an exact macro in the target Tavo version before building a reusable public template around it.

Boundary: prompt-field macro support does not mean the same token executes in arbitrary HTML, PNG metadata, plugin files, or app settings. Expansion belongs to the generation/prompt/regex pipeline unless that specific surface defines otherwise.

## EJS

EJS prompt templates are available since v0.87.0 in prompt-bearing fields such as:

- character description, personality, scenario, and opening messages;
- presets;
- worldbooks;
- regexes.

Use EJS when plain macros are not enough:

- conditionals;
- loops;
- variable reads, writes, and arithmetic;
- selectively injecting prompt text;
- emitting macro text for the next rendering stage.

Common tags include script blocks such as `<% ... %>` and escaped output such as `<%= ... %>`. Tavo supports a common EJS subset, not the complete Node/browser feature set. Do not rely on include, partial, or custom-delimiter features.

## Rendering Order And State

Tavo renders EJS first, then passes the result through the `{{}}` macro engine. EJS can therefore intentionally emit a macro for later expansion.

Available helpers include `getvar`, `setvar`, `incvar`, `decvar`, and `delvar`. The default scope is `chat`; `global` is persistent across chats. Compatibility scopes may include message, initial, or cache-style state, but use them only when the target version supports the exact scope.

Built-in values include `charName`, `userName`, `lastUserMessage`, `lastCharMessage`, and `characterId`.

In the v0.91 character-description assembly path, EJS output and generated macros are resolved before the provider-facing request. The request retains normal system/history/current-user ordering. This does not prove identical placement for every preset, worldbook, regex, greeting, or rendering field.

If an EJS tag fails, the containing field can fall back to its original unrendered text. Keep independent logic blocks small so one failure does not obscure the entire prompt field.

## Authoring Rules

- Prefer readable templates over compact cleverness.
- Give every variable a clear owner, scope, default, and update point.
- Use explicit fallbacks for optional values.
- Separate state mutation from state display; rendering `{{getvar::hp}}` is not the same as changing `hp`.
- For RPG/status systems, use EJS for branching and macros for compact state operations when practical.
- Use short, stable, documented variable keys.
- Escape user-controlled values before inserting them into HTML, JavaScript, regex, or JSON.
- Do not let a template silently invent story state when a variable is missing.
- When EJS emits HTML for Advanced Rendering, validate both escaping and Android layout behavior.

## Validation Method

1. Test plain text with no EJS or macros to establish the assembly baseline.
2. Test one macro family at a time, including its missing-value behavior.
3. Test one EJS conditional, one loop, and one variable mutation independently.
4. Test EJS emitting a macro and confirm the macro expands only after EJS.
5. Continue for a second turn to confirm chat-scope state; open an isolated chat to distinguish chat and global scope.
6. Inspect the assembled provider-facing messages when exact prompt order matters. A model paraphrase proves semantic influence, not exact role/order.
7. Introduce one intentionally invalid tag and confirm the fallback boundary without risking a production card.
8. If output feeds regex or Advanced Rendering, test each downstream stage separately.
