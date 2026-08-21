# MCP Runtime

This reference covers direct HTTP JSON-RPC operation against Tavo's built-in MCP server. It documents Tavo's own external MCP surface only; the native in-chat Agent Loop is a separate surface.

## Applicable Versions

- The built-in MCP server is available from Tavo `0.91`, is disabled by default, and requires a bearer token plus an app-selected access scope.
- The packaged Tavo `1.2.1` baseline uses MCP protocol `2025-06-18`.
- The `1.2.1` external surface contains `95` tools, `20` resources, `8` resource templates, and no prompts.
- External groups cover status, app identity, characters, lorebooks, regexes, presets, personas, chats, messages, input, plugins, memory, variables, files, themes, text generation, image generation, and TTS.
- ASR, STT, transcription, and microphone control are not exposed through this external surface.

Read `references/34-tavo-121-technical-facts.md` for the version-specific operation and reliability boundaries.

## Call Shape

Prefer direct HTTP JSON-RPC. Invoke Tavo tools through `tools/call`; a tool name is not a top-level JSON-RPC method.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "tavo_status",
    "arguments": {}
  }
}
```

Request the protocol declared by the connected runtime and retain the actual `initialize.result.protocolVersion` returned by the server. A requested/negotiated difference is not automatically a failure; the client must decide whether the negotiated version is usable.

Common failure classes:

- `401`: missing or invalid bearer token;
- `403`: the selected access scope does not allow the operation;
- `404` or `405`: wrong endpoint or HTTP method;
- timeout or connection failure: endpoint unreachable or app unavailable;
- JSON-RPC `Resource not found`: the requested stable object no longer exists.

## Bundled Client Boundary

The bundled client is intentionally restricted to `initialize`, `ping`, `tools/list`, and `tools/call`. It:

- requires a valid initialize result with protocol, capabilities, and server identity;
- sends `notifications/initialized` before the selected operation;
- carries the returned session id and protocol header;
- refuses tool operations unless the server advertises the tools capability;
- requires JSON responses for ordinary calls and an empty accepted response for initialization notification;
- rejects SSE, redirects, endpoint credentials in URLs, query parameters, fragments, and mixed configuration sources;
- disables environment proxies;
- redacts responses by default;
- requires HTTPS by default and an explicit acknowledgement for non-loopback HTTP;
- refuses to overwrite the endpoint file or an alias to it.

Supply connection settings either through one selected mode-`0600` endpoint JSON file or through the paired `TAVO_MCP_URL` and `TAVO_MCP_AUTH` environment variables. Do not mix file and environment values.

## New 1.2.1 Groups

Tavo `1.2.1` adds these groups relative to `1.0`:

- `tavo_app_version`, `tavo_app_version_number`;
- `tavo_variable_list/get/set/update/unset`;
- `tavo_file_save/load/list/exists/delete`;
- `tavo_theme_search/get/create/update/import/export/delete`;
- `tavo_generate`;
- `tavo_image_generate`;
- `tavo_tts_play`, `tavo_tts_stop`.

Variables, files, and custom themes are `supported` within their explicit scopes. Text generation is `limited` on the packaged Mac baseline. Image generation and TTS establish bounded integration only; they do not establish real-provider or sensory quality.

## Write Contract

Do not attach `expectedRevision` generically in Tavo `1.2.1`. It is absent from many current schemas, and current writes use last-write-wins unless a tool says otherwise.

Use:

1. exact search or read;
2. the smallest current-schema payload;
3. `dryRun` only when exposed;
4. a unique `clientRequestId` only when exposed;
5. authorized write;
6. stable-id readback;
7. cleanup or restoration when required.

Unknown legacy fields are not a safety barrier: one old revision field was accepted even though the schema disallowed additional properties. Schema validity and a success response cannot replace readback.

## Messages And Input

- Middle-message insertion is not exposed. `tavo_message_append` appends at the end.
- Use stable message ids because numeric indices can move.
- `tavo_message_find` declares a maximum/latest `100` matches per call; the synthetic `101`-message boundary is not established here.
- Draft get, set, append, and clear are not limited to a visible chat page.
- Off-page send can target the last active chat on the packaged Mac baseline, even though the declared contract requires an active chat page.

Before send, call `tavo_current_chat_get`, compare the stable id with the authorized target, inspect the draft, and read the resulting messages back.

## Memory

Memory operations were introduced in Tavo `1.0`. The packaged `1.0` result includes ordered append, idempotent `clientRequestId`, dry-run, and stale-revision rejection for schemas that exposed revision control at that version.

Do not project the old revision field into `1.2.1` requests. Memory asset operations also do not prove automatic extraction from every conversation or automatic injection into every model request.

## Agent Loop Distinction

External MCP and the native Agent Loop differ:

- external MCP is called by an outside client over HTTP JSON-RPC;
- Agent Loop places built-in tool schemas into a model conversation and executes returned tool calls;
- availability on one surface does not imply availability on the other;
- character cards and plugins do not automatically register model tools;
- enabling external MCP does not turn that server into an in-chat extension tool.

On the packaged `1.2.1` Mac baseline, Direct Agent mode initially exposes `72` tools. Dynamic Agent mode initially exposes `tavo_tool_search`, `tavo_ask_user`, and `tavo_web_fetch`.

## Safe Operation

- Never store, print, commit, or paste the bearer token into prompts, screenshots, logs, issues, or deliverables.
- Confirm the connected Tavo version before relying on a tool or schema.
- Use only the access scope needed for the task.
- Read the explicit target immediately before a write.
- Use current fields only; do not attach generic legacy controls.
- Read every actual write back by stable id.
- Keep visual, audio, model-semantic, import, and persistence checks separate.
- Restore temporary chat, input, provider, theme, voice, or plugin changes when the task requires restoration.
- Delete, reset, uninstall, and overwrite require explicit user intent.

## Minimal Compatibility Check

Before an authorized MCP workflow:

1. initialize and record the negotiated protocol;
2. confirm the required tool names and current input fields;
3. call the harmless status tool;
4. read the exact target;
5. dry-run the minimal mutation when supported;
6. perform the write only when authorized;
7. read back the final object and restore temporary state.

Do not infer broad compatibility from tool counts, one status call, or a similarly named tool in another Tavo version.
