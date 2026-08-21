# Tavo 1.2.1 Technical Facts

This reference contains versioned conclusions for Tavo `1.2.1`. It applies to the packaged macOS baseline unless a paragraph says otherwise. It contains no endpoint, account, chat, device, or request identity.

## App And Protocol

- App version: Tavo `1.2.1`, build `1021`, macOS.
- External MCP server version: `1.2.1`.
- MCP protocol: `2025-06-18`.
- External MCP collections: `95` tools, `20` resources, `8` resource templates, and `0` prompts.
- App-version tools and the server identity agree on the packaged baseline.

These values identify one release baseline. They do not promise that a later build has the same surface.

## External MCP Delta From 1.0

Tavo `1.2.1` adds `23` tools and removes none relative to the packaged `1.0` surface:

- app identity: `tavo_app_version`, `tavo_app_version_number`;
- variables: `tavo_variable_list`, `tavo_variable_get`, `tavo_variable_set`, `tavo_variable_update`, `tavo_variable_unset`;
- files: `tavo_file_save`, `tavo_file_load`, `tavo_file_list`, `tavo_file_exists`, `tavo_file_delete`;
- themes: `tavo_theme_search`, `tavo_theme_get`, `tavo_theme_create`, `tavo_theme_update`, `tavo_theme_import`, `tavo_theme_export`, `tavo_theme_delete`;
- text generation: `tavo_generate`;
- image generation: `tavo_image_generate`;
- TTS: `tavo_tts_play`, `tavo_tts_stop`.

It also adds the chat-theme schema and a theme resource template. ASR, STT, transcription, and microphone control are not exposed through this external MCP surface.

## Variables

Result: `supported` within explicit scope.

- Global, chat, and message scopes are distinct.
- Get, set, shallow update, list, and unset are available.
- Values preserve JSON types, including strings that resemble numbers and explicit `null` values.
- A path must identify one explicit scope; do not silently fall back between scopes.

## Files

Result: `supported` within explicit scope.

- Save, load, list, existence check, and delete are available.
- Chat-scoped and global storage are distinct.
- File names must follow the current schema and must not contain traversal or path-separator forms.
- Chat-scoped files follow the chat lifecycle. Use global scope only when persistence beyond one chat is intended.

## Themes

Result: `supported` for custom-theme operations.

- Search, get, create, recursive update, import, export, and delete are available.
- A custom theme can be bound to a chat with the chat object's `themeId`.
- Export and import use the Tavo theme package shape.
- Official themes are not safe mutation targets; copy one before editing.
- A successful object update does not prove every visual field, font, archive variant, or restart-persistence behavior.

## Write Contract

Tavo `1.2.1` changes the external write contract:

- `expectedRevision` is absent from `39` previously common tool schemas.
- Current writes use last-write-wins behavior unless a specific tool says otherwise.
- `clientRequestId` deduplication is process-scoped where the schema exposes it.
- An old unknown `expectedRevision` field was accepted by `tavo_chat_update` even though the schema rejected additional properties.

Therefore a client must not attach legacy fields generically. Use this sequence:

1. search or read the exact authorized target;
2. send the smallest schema-valid payload;
3. use `dryRun` only when the current tool exposes it;
4. use a unique `clientRequestId` only when exposed;
5. perform the authorized write;
6. read the stable object id back;
7. restore temporary state when the task requires it.

Schema validation and a successful response are not substitutes for side-effect readback.

## Messages And Input

- `tavo_message_append` appends at the end; a supplied undocumented index is not middle insertion.
- `tavo_message_find` declares a maximum/latest `100` matches per call. The synthetic `101`-message boundary is `not-established` in this package.
- Draft get, set, append, and clear are not limited to a visible chat page.
- Input send is declared to require an active chat page, but the packaged Mac baseline accepted an off-page send into the last active chat.

Treat off-page send as `limited` and unsafe for implicit targeting. Before any programmatic send, compare `tavo_current_chat_get` with the authorized stable chat id, verify the draft, send only to that chat, and read the resulting messages back.

## Text Generation

Result: `limited` on the packaged Mac baseline.

`tavo_generate` is present, but a minimal `context:false` request failed internally before reaching the selected text provider. Do not promise reliable external-MCP text generation until the target installation completes its own minimal call.

This limitation does not imply that ordinary chat generation or the native Agent Loop is unavailable.

## Image Generation

Result: `supported` only for bounded OpenAI-compatible integration.

- Tavo can assemble an image-generation request and accept a valid PNG response.
- A generated file can be saved in chat-scoped storage and read back through the file tools.
- A successful file result does not guarantee a visible image bubble.

The packaged conclusion does not establish real-provider compatibility, prompt fidelity, visual quality, or every response variant.

## TTS

Result: `supported` only for bounded OpenAI-compatible integration.

- `tavo_tts_play` can submit text, receive accepted playback state, and return a play id.
- `tavo_tts_stop` stops active playback and clears the shared queue.

The packaged conclusion does not establish audibility, voice identity, pronunciation, human quality, or every provider format.

## Native Agent Loop

External MCP and the native in-chat Agent Loop remain separate surfaces.

On the packaged Mac baseline:

- Direct mode initially exposes `72` built-in tools and does not include `tavo_tool_search`.
- Dynamic mode initially exposes `tavo_tool_search`, `tavo_ask_user`, and `tavo_web_fetch`.
- Dynamic file discovery can save and load a chat-scoped file.
- Dynamic theme discovery can update an explicitly selected custom theme after Tavo approval.
- Web Fetch can continue a long response once with its cursor.
- Ask-user dialogs remain associated with the chat that started the request.
- Web Search requires an existing compatible search configuration; this package does not provide one.
- `extension_tool_search` is not active in this baseline.
- Enabling external MCP does not turn that server into an in-chat extension tool.

A model may still decline to call an available tool. Tool presence and model choice are separate facts.

## Plugin And TavoJS Boundary

Current runtime contracts describe spec-2 plugins, localization, root entry scripts, legacy entry compatibility, configuration and localization reads, chat/message notifications, input interception, generation lifecycle Hooks, TTS, and structured input-send results.

Those contracts do not upgrade every older plugin, EJS, TavoJS, Advanced Rendering, character-card, worldbook, preset, or regex behavior to a `1.2.1` behavior result. Use the explicit version in each topic reference.

## Platform Boundary

The new Agent Loop counts, external-MCP groups, input behavior, theme operations, text-generation limitation, image integration, and TTS integration above are macOS `1.2.1` conclusions. Do not present them as iOS, Android, or later-version guarantees without checking that target.
