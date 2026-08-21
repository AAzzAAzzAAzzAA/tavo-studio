# App Settings And Data

This reference covers provider configuration, model settings, Agent Loop controls, privacy, themes, backup/restore, storage, and workflow settings.

## API And Model Configuration

Tavo supports provider connections for OpenAI, Claude, Gemini, DeepSeek, OpenRouter, Doubao/Volcano/ByteDance, Volink, and custom OpenAI-compatible protocols.

Configuration behavior:

- Use one-click provider setup where available, or manually create a connection, select platform/model, enter provider values, and save.
- A custom OpenAI-compatible base URL may end at `/v1`; do not normally include `/chat/completions` in the base URL.
- Third-party compatibility is not guaranteed merely because an endpoint claims OpenAI compatibility.
- Prompt-format conversion can merge adjacent same-role messages or adapt providers that restrict system/user message shapes.
- Global model settings include context length, reply-token limit, temperature, Top-P, Top-K, and streaming.
- Connection-level parameters usually override global model settings.
- Provider configuration is a native UI responsibility unless a current runtime API explicitly exposes a safe write operation.

Tavo v0.93 includes dedicated Fable 5 and Mythos 5 parameter controls. Their UI fields can be configured, but proprietary wire fields and real endpoint behavior must be confirmed with the chosen provider before making compatibility claims.

## Tavo 1.2.1 Agent Loop Settings

Advanced Rendering settings include three global tool controls:

- **启用工具**: enables native in-chat model tool calling; default is off.
- **动态加载工具**: starts with discovery/user-dialog/Web Fetch tools so the model can find additional Tavo tools without placing the full catalog in initial context; default is on after tools are enabled.
- **隐藏工具调用**: hides tool-call traces or cards without disabling tool execution.

On the packaged `1.2.1` Mac baseline, turning dynamic loading off exposed `72` built-in tools directly. Dynamic mode initially exposed `tavo_tool_search`, `tavo_ask_user`, and `tavo_web_fetch`. These are global Tavo settings, not rolecard, preset, worldbook, or plugin fields.

Boundaries:

- The Agent Loop is available only when the selected provider/model can return compatible tool calls.
- The tool catalog belongs to Tavo; a rolecard or plugin cannot register new Agent Loop tools.
- Dynamic loading changes tool visibility and context cost, not the card's prose content.
- External MCP and the in-chat Agent Loop are separate capabilities.
- Web Search requires its own compatible search configuration; Web Fetch does not supply that configuration.
- Enabling external MCP does not register that server as an in-chat extension tool.
- A model may choose not to call a tool even when it is available; prompt design should explain when and why a tool is appropriate.

## Local Data And Privacy

Tavo uses local-first storage for chat history, personalized settings, API keys, user-created characters, and other app configuration.

When a user invokes a third-party AI provider, relevant chat content and provider credentials are transmitted to that provider over HTTPS and are governed by the provider's terms and privacy policy. “Stored locally” must not be restated as “never leaves the device.”

Security rules:

- Never copy provider keys into cards, presets, plugins, logs, screenshots, or community fixtures.
- Ask users to enter secrets directly in Tavo.
- Treat backup files as sensitive because they may contain credentials.
- Use revocable, least-privilege test keys only when a real provider test is explicitly authorized.

## Theme

Theme management supports applying an included theme or a user-created theme, copying a built-in theme as a template, and customizing:

- chat background;
- status bar;
- message bubble styles;
- fonts;
- character-avatar presentation;
- functional elements such as inner-monologue hints.

Theme editing is a native capability. Tavo `1.2.1` external MCP supports custom-theme search, get, create, update, import, export, delete, and chat binding through `themeId`. Do not assume theme files expose unrestricted CSS or that every visual field and restart-persistence path has the same result.

## Media API Configuration

Image and voice provider entries remain native UI configuration. External MCP `1.2.1` can request image generation and TTS playback, but it does not expose provider-configuration create/update/delete tools. Provider setup and generation/playback are separate capabilities.

## Backup And Restore

Tavo can back up core data and restore from backup files. A backup may include API keys if the user selects that option.

Boundaries:

- Backups from a newer app version may not restore into an older version.
- Restore can restart the app; process continuity is not a correctness condition.
- Merge/overwrite behavior and coverage of every data family should be confirmed before automated restore.
- Do not inspect, log, commit, or embed backup contents.

Use a two-backup method for destructive validation:

1. **Rollback backup**: create before any test write and keep permission-restricted.
2. **Scenario backup**: create after preparing one disposable object and its known settings; use it to test mutation/removal followed by restore.

After restore, compare the disposable object's fields, enabled state, settings, and runtime contributions. If anything unexpected appears, stop further writes and use the rollback backup.

## Storage Space

The storage page reports used space and can clean categories such as:

- cache, including TTS audio cache;
- logs, including context and load-balancer logs;
- character-related assets such as avatars and images.

Core records such as chats, characters, and worldbooks should not be assumed removable through cache cleanup. Storage cleanup is not a factory reset or data-reset tool.

## Shortcuts And Quick Group Speech

Tavo supports custom keyboard shortcuts and quick group speech controls. Quick group speech adds member-avatar response controls near the group-chat composer. Exact shortcut export/import and programmatic visibility can vary by version.

## Validation Method

### Providers and models

1. Confirm base URL, protocol, model ID, and parameter precedence with a harmless minimal request.
2. Test text, reasoning, image, function/tool, and structured-output capabilities separately; provider flags alone are insufficient.
3. Test streaming and non-streaming paths if both matter.
4. Record only redacted configuration and non-secret errors.

### Agent Loop

1. Use an isolated chat and a model known to support tool calls.
2. Enable tools and compare dynamic-loading and full-catalog modes with the same prompt.
3. Ask for one harmless read operation before testing any mutation.
4. Check tool-call visibility, model follow-up behavior, and whether the final answer uses the tool result.
5. Do not modify the supplied preset/card/worldbook just to make a tool call occur.

### Themes, backup, and storage

1. Copy a theme rather than editing an irreplaceable original; check save, reopen, restart, and rollback.
2. Create the rollback backup before any restore experiment.
3. Use one disposable object to distinguish merge, overwrite, and restore behavior.
4. Measure storage categories before and after cleaning, then confirm core chats/cards/worldbooks remain intact.
