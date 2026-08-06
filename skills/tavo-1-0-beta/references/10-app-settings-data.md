# App Settings And Data

This reference covers app-level settings, provider configuration, backup, storage, theme, and data management.

Current evidence snapshot: complete official crawl `assets/official-docs/text-20260726/`, Tavo `1.0.0` strict gate `assets/evidence/1.0.0/20260807-gate.json`, and incremental Agent Loop/MCP summary `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`. Use the 0.93 zero-real matrix only for app settings not rerun on 1.0.

## Official Pages

- `https://docs.tavoai.dev/cn/guides/api-setting/`
- `https://docs.tavoai.dev/cn/guides/api-setting/api-setting-1/`
- `https://docs.tavoai.dev/cn/guides/api-setting/select-model/`
- provider key pages under `guides/api-setting/get-key/`
- `https://docs.tavoai.dev/cn/guides/theme/`
- `https://docs.tavoai.dev/cn/guides/others/backup/`
- `https://docs.tavoai.dev/cn/guides/others/storage-space/`
- `https://docs.tavoai.dev/cn/guides/others/customize-keyboard/`
- `https://docs.tavoai.dev/cn/guides/others/quickly-group-chat/`
- `https://docs.tavoai.dev/cn/privacy-policy/`

## Official-Current API And Model Surface

The current official docs include:

- general API setup;
- API settings;
- model selection;
- provider key pages for OpenAI, Claude, Gemini, DeepSeek, OpenRouter, Doubao/Volcano/ByteDance, Volink, and custom OpenAI-compatible protocol;
- common API error troubleshooting.

Treat UI configuration as official. Treat programmatic editing of provider connections as `needs-mcp` or UI-only until current runtime tools prove otherwise.

Official-current configuration notes:

- novice flow can use one-click provider setup where offered;
- manual flow creates an API connection, selects platform/model, fills provider config, and saves;
- custom OpenAI-compatible endpoints may need `/v1` as base URL, but should not be filled down to `/chat/completions`;
- compatibility is not guaranteed for every third-party endpoint;
- prompt-format converters include options for merging adjacent same-role messages and handling providers that restrict system/user message shape;
- global model settings include context memory length, reply token limit, temperature, Top-P, Top-K, and streaming;
- API-connection-level parameters usually override global model settings.

The 0.93 Android UI exposed dedicated Fable 5 and Mythos 5 parameter controls. Sentinel values survived save, reopen, and app restart. No safely redirected proprietary request reached the local fixture, so field persistence is `ui-pass` while wire shape and real endpoint behavior remain blocked.

## Tavo 1.0 Tool Settings

Advanced Rendering settings expose three global controls:

- **启用工具**: turns native model tool calling on; runtime docs declare the default off;
- **动态加载工具**: when on, initial requests use discovery to reduce context; runtime docs declare the default on after tool use is enabled;
- **显示工具调用**: shows tool-call traces/cards in the conversation.

Live provider captures proved the mode change: dynamic mode exposed exactly search/user-dialog/web on the initial round, while direct mode exposed 59 callable tools and no search tool. Re-enabling dynamic loading restored the three-tool initial surface. These switches are app-global tool-delivery settings, not rolecard fields. Read `references/28-tavo-100-live-evidence.md` for counts, ownership, limits, and evidence boundaries.

## Local Data And Privacy Boundary

Official-current privacy docs describe Tavo as using local-first storage for:

- chat history;
- personalized settings and preferences;
- API key information;
- user-created character data;
- other app-related configuration.

The same docs say chat content and API keys are transmitted to third-party AI providers only when the user uses those provider services, through HTTPS, and then fall under the provider's own terms and privacy policy. For skill answers, this means "stored locally by Tavo" is official-current, while "never leaves the device" is too broad once a provider call is made.

## Theme

Official-current theme docs say users can open theme management from the left side menu and:

- apply an official default theme or a self-made theme;
- copy an official theme as a template and modify the copy;
- customize chat background, status bar, message bubble style, font, character avatar display, and functional elements such as inner-monologue hint style.

Treat theme editing as a real app capability. Treat theme export/import format, CSS-like expressiveness, and MCP visibility as `needs-live-verify`.

The current official theme page does not enumerate every concrete font or layout control, and the 0.93 MCP surface exposes no theme tool/schema. The 0.93 UI matrix copied a theme, selected a visibly non-default font, and proved save/reopen/app-restart persistence before restoring the original theme. The italic-whitespace repair also preserved one space after `*foo*` and `_foo_` through persistence, UI, reopen, and restart. Treat these as scoped `ui-pass`, not theme-format or blanket Markdown proof.

## Backup And Restore

Official-current backup docs say Tavo can back up core data and restore from backup files. They also say backup may include API keys if selected.

Important boundaries:

- Backup files are sensitive because they can include API keys.
- Backups from a higher app version may not restore into lower versions.
- Before destructive testing, create a backup and record app version.
- Restore strategy, overwrite/merge behavior, and backup file schema need live verification before any automated restore work.

For the 0.93 zero-real restore case, use two distinct files:

- Backup A: full pre-test rollback before any write. Store in a permission-restricted directory and record only size/SHA-256 in ordinary evidence.
- Backup B: created after installing/enabling the unique backup fixture and saving its config marker; use it to test uninstall -> restore -> exact plugin/config/enabled/runtime-contribution readback.

Backup B restoration is a high-risk, late-stage case. Run only after lower-risk plugin tests pass. On any restore anomaly, stop writes and use Backup A for rollback. Neither backup contents nor provider secrets may be inspected, logged, committed, or embedded in reusable Skill assets.

The 0.93 run created native Backup A and Backup B without opening or parsing either file. A separate discriminating spec-2 drill changed a plugin config and enabled state, observed active runtime contributions, restored Backup B, and matched the saved config, disabled state, and zero contributions exactly. Tavo may legitimately restart during native restore, so PID continuity is not an acceptance condition for that phase. This is a bounded `roundtrip-pass`, not a claim about downgrade restore or every data class.

## Storage Space

Official-current storage docs say the storage page shows used space and safe cleanup categories such as:

- cache, including TTS voice cache;
- logs, including context/load-balancer logs;
- role/character-related assets such as avatars and images.

Docs explicitly distinguish core "data" from cleanup categories; chat records, characters, worldbooks, and similar core data should not be assumed removable through storage cleanup.

## Shortcuts And Quick Group Speech

Official docs include custom shortcuts and quick group chat speech. These belong to app workflow configuration and should be summarized in later UI-focused expansion. Treat exact UI paths and exportability as `needs-live-verify`.

## Prior 0.93 Live Boundaries

- Custom model/provider request work used a deterministic local service with `realModelRequestsSent=0`, `realProviderCredentialsUsed=false`, and `countsTowardKpi=false`.
- Protected chat payload, input, primary API, preset, persona, theme, permissions, original plugin hashes, and original enabled states matched the pre-write anchor after restoration.
- Retained test plugins finished disabled; the local provider stopped.
- The sole retained test image-provider configuration remained shown as the image current item because 0.93 exposes edit/copy/delete but no unset action. Deleting it would contradict the retention policy; the primary chat API was restored.
- iOS behavior is `not-applicable` to this Android run and cannot be promoted.

## Historical-Derived Guidance

- API provider settings are high-secrecy; do not screenshot or persist full keys.
- Provider/model capability flags are not enough; image, reasoning, function, and structured-output support should be tested against the selected endpoint.
- Backup and restore tests should always record app version and rollback path.
- Storage cleanup is not a data reset tool.

## Verification Targets

- Current provider list and model fields.
- Complete Custom OpenAI/Responses/legacy protocol and fault behavior beyond the completed local paths.
- Backup artifact format and secret handling.
- Backup restoration across every data family and version boundary.
- Fable/Mythos proprietary wire fields and real endpoint behavior.
- Disposable NovelAI form save/reopen/delete without a real key or provider call.
- Storage cleanup categories and preserved data.
- Shortcut export/import or MCP visibility.
