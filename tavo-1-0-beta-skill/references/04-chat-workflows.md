# Chat Workflows

This reference covers chat operations and workflow design.

## Chat Operations

| Feature | Current behavior and boundary |
| --- | --- |
| Start chat | Start a conversation from a character or start-chat entry point. |
| Filter chats | Filter the chat list by character to show related histories. |
| Rename | Edit the current chat title. |
| Pin | Pin a chat from its list-item menu. |
| Statistics | View companionship duration, message counts, and total text volume for the chat. |
| Restart | Permanently clear the current history and start blank with the same role/settings baseline. Back up first. |
| Clone | Copy a chat and its history into an independent branch for experimentation. |
| Delete | Permanently remove a chat and its messages after confirmation. |
| Character history | Open past chats associated with a character. |
| Import/export | Import `.jsonl` chat records and export `.txt` or `.json`; confirm the target version's schema before generating bulk imports. |

## Diagnostics And Session State

- Context logs can show token use, worldbook/regex/preset matching, context construction, and model-call details.
- Reroll alternatives are session-scoped. They can survive chat switching and message backtracking during the same app session, but only the selected visible result remains after restart.
- “Hide model chain of thought” changes display only; it does not make generation faster or change the model's reasoning behavior.

## Per-Chat Settings

The chat side panel can control the current conversation's:

- API connection and model;
- preset;
- worldbook;
- regex;
- long memory;
- translation settings.

These are native UI capabilities. Do not assume every setting is writable through TavoJS or external MCP.

## External MCP Message Boundary

In Tavo 1.0, external MCP supports message listing/get/find, append, update, and delete. It does not expose middle-message insertion.

- `append` adds at the end; an undocumented `message.index` field must not be treated as insertion.
- If insertion is essential, redesign around append/update or use a complete history import only when the user explicitly authorizes it.
- This limitation applies to external MCP and does not imply that the native UI cannot edit existing messages.

## Group Chat

Group chat supports selecting multiple characters, adding/removing members, and muting/unmuting members. Reply modes include:

- **natural chat**: a mentioned character replies first; without a mention, a character may be selected;
- **all reply**: every character replies to each user message;
- **specified speaker**: the user must mention a character;
- **contextual speaker**: a model chooses which character or characters speak next.

For contextual speaker mode, a dedicated API can be used. Keep `{{group}}` in its prompt when the current member list must be injected.

Quick group speech adds member-avatar controls near the composer. After entering text, selecting an avatar can designate the respondent without manually typing `@角色名`.

## Translation

- Enable translation in chat settings.
- Choose the device language or a manual target language.
- Optionally assign a dedicated translation API so translation does not use the normal chat model.
- Keep `{{language}}` and `{{content}}` in the translation template unless intentionally replacing their function.
- Translate a specific bubble from its long-press action.

Separate accurate translation from natural localization; they may need different prompt wording or models.

## Workflow And Validation Method

- Clone a chat before testing alternate prompts, presets, or model settings.
- Export before restart, delete, bulk edit, or history import.
- For group chat, define who should speak under mention and no-mention cases; otherwise the scene may collapse into silence or all-speaker noise.
- Test every reply mode with the same short scenario and compare speaker selection, order, and duplicate responses.
- Test translation with names, formatting, dialogue, and culturally specific text; verify that placeholders remain intact.
- For history import, use a disposable character and a tiny history first. Check character matching, message roles, ordering, metadata, and re-export shape.
- For automation, verify that the intended chat is active before reading or mutating current-chat state.
- Treat destructive operations as a separate phase with an explicit rollback path.
