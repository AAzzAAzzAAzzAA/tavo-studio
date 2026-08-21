# Characters, Cards, And Personas

This reference routes character-card, persona, PNG-card, and SillyTavern-compatible creation work.

## Character And Persona Surface

| Field | Role and boundary |
| --- | --- |
| Character description | Stable identity, appearance, background, motives, boundaries, concrete traits, and behavior-shaping facts. |
| First message | Opening scene and a strong style anchor for tone, pacing, action density, response length, and dialogue rhythm. |
| Dialogue examples | Voice and interaction examples. Separate examples with `<START>` and use `{{char}}` / `{{user}}`; insertion depends on available context and API format. |
| Main Prompt | Character-specific behavior instructions that can supplement or replace the preset's Main Prompt. If original-content preservation is needed, confirm the target version's exact placeholder syntax before generating an import. |
| Post-History Instructions | Continuity instructions placed after chat history, useful for relationship progression, emotional continuity, and preventing resets. |
| Group chat greeting | Group-only opening. Multiple greetings may be separated with `<START>` for random selection; it does not affect one-to-one chat. |
| Nickname | Group-only alias. It does not replace the character `name` or automatically create one-to-one nickname behavior. |
| Source | Author ID or original link. Treat it as provenance metadata, not prompt content. Editing rights may depend on the original installation identity. |
| Tags | Short comma-separated labels for search and organization; they do not affect model behavior. |
| Creator notes | Reader-facing notes; the character does not see them. Do not place required behavior only here. |
| Traits and scene | Personality traits and the situation/scene setting. Keep them consistent with description and greeting. |
| Persona / user identity | Who `{{user}}` is, the relationship to `{{char}}`, current state, and interaction tone. Multiple personas can be managed and one can be set as default. |

TavoJS exposes character and persona create/read/update/delete operations plus character import. Character creation requires at least `name` and `firstMes`; persona creation requires at least `name` and `description`. Optional avatar, active/default state, and sort order should be preserved only when the target object shape supports them.

## Import And Compatibility

Tavo supports two broad card-import paths:

- a shared character URL;
- a downloaded character-card file, including JSON and card-bearing PNG workflows.

Supported community services include:

- `aicharactercards.com`;
- `chub.ai`;
- `janitorai.com` for URL import;
- `pygmalion.chat`;
- `realm.risuai.net`.

Do not infer that every service supports both URL and file import. In particular, treat JanitorAI as URL-only unless the current app explicitly offers another path.

Compatibility boundaries:

- A PNG image is importable as a card only when it contains an extractable card payload; an ordinary picture is not a character card.
- CC-style payloads may use a structured `data` object and can contain `character_book` or `extensions.regex_scripts`, but preservation, activation, and binding of extensions must be checked after import.
- `chara_card_v2` / CC-style JSON and PNG helpers describe file packaging, not every detail of Tavo's import behavior.
- Extra PNG chunks for presets, regexes, or plugins are packaging data and must not be described as automatically installed.
- Import conversion can change field names or omit unsupported extensions; always compare the imported object with the source.

## Creation Method

- Put stable, must-remember facts in character fields, not only in creator notes or conditional worldbook entries.
- Use the first message as a concrete demonstration of the desired experience.
- Use dialogue examples for voice, decisions, boundaries, and interaction patterns rather than encyclopedic lore.
- Keep the persona compact and relational: identity, reason for being present, relationship dynamic, and immediate tone.
- Find the card's “引力核心” before expanding it: the tension, relationship, atmosphere, or gameplay loop that makes the user want another turn.
- Avoid service-NPC flattening. Give the character private motives, limits, hesitation, misreadings, and relationship-specific reactions.
- Replace vague emotion labels with observable actions, tone, choices, and consequences during prose cleanup.
- Choose the gameplay mode before adding subsystems. A pure character may need only a card; RPG, growth, survival, farming, or relationship systems may also need worldbook, preset, variables, regex, and rendering.

## Bundled Card Utilities

- `scripts/embed_st_card_png.mjs`
- `scripts/extract_st_card_png.mjs`
- `scripts/worldbook_to_character_book.mjs`
- `scripts/png-card-lib.mjs`

Use these for local ST-compatible packaging and extraction. They do not prove that Tavo will preserve or activate every embedded extension.

## Validation Method

1. Create or import a disposable card rather than overwriting an important character.
2. Check all prompt-bearing fields, especially description, first message, examples, Main Prompt, and Post-History Instructions.
3. Start a fresh isolated chat with the intended preset, persona, and worldbook bindings.
4. Test voice/style, relationship handling, a hard boundary, and a lore-dependent prompt in separate turns.
5. Export or read the imported object and compare required fields, embedded worldbook, and regex entries.
6. For PNG workflows, extract the payload again and compare it with the source JSON.
7. Confirm that group-only greeting and nickname behavior do not leak into one-to-one chat.
