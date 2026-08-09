# MCP Runtime

This reference covers direct HTTP JSON-RPC operation against Tavo's built-in MCP server. It documents Tavo's own MCP surface only; project-specific clients and plugins are outside this Skill.

## Applicable Versions

- The built-in MCP server is available from Tavo 0.91 onward, is disabled by default, and requires a bearer token plus an app-selected access scope.
- Tavo 1.0 uses MCP protocol `2025-06-18` for the currently exposed server surface.
- In Tavo 1.0, external MCP groups cover status, characters, lorebooks, regexes, presets, personas, chats, messages, input, plugins, and memory.
- Variables and files are still planned on the external MCP surface. Generation and image generation are deferred, and diagnostics are partial.
- No external MCP tool is currently exposed for ASR/STT, transcription, or microphone control. This does not mean that the Tavo app itself has no speech-recognition feature.

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

Use the protocol version declared by the connected runtime as the requested version, and retain the actual `initialize.result.protocolVersion` returned by the server. A difference between requested and negotiated versions is not automatically a failure; the client must judge whether the negotiated version is usable.

The bundled client is intentionally limited to the Tavo 1.0 protocol shown above and to `initialize`, `ping`, `tools/list`, and `tools/call`. It fails closed unless the initialize result contains the expected protocol, a capabilities object, and non-empty server name/version metadata. After a valid initialize response it sends `notifications/initialized`, carries the returned session ID and protocol header into the requested call, and refuses tool methods unless the server advertises the tools capability. JSON-RPC requests require an HTTP 200 `application/json` response; the initialized notification accepts only an empty HTTP 202 or 204 response. The client rejects SSE, disables environment proxies, never follows HTTP redirects, always redacts responses, and rejects credentials embedded in endpoint URLs. Connection configuration is an indivisible pair: either one explicitly selected mode-0600 endpoint JSON file supplies both URL and authorization, or `TAVO_MCP_URL` and `TAVO_MCP_AUTH` are both set; file and environment values are never mixed. HTTPS is required by default; non-loopback HTTP needs the explicit `--allow-insecure-http` acknowledgement. Endpoint URLs may not contain user information, query parameters, or fragments, and an output path may not overwrite the endpoint file or any alias/hardlink to it.

Common failure classes:

- `401`: missing or invalid bearer token.
- `403`: the selected access scope does not allow the operation.
- `404` or `405`: wrong endpoint or HTTP method.
- timeout or connection failure: endpoint unreachable, app unavailable, or network route unavailable.

## Tavo 1.0 Boundaries

### Memory

External MCP memory operations are available in Tavo 1.0. Safe clients should expect:

- dry-run without mutation;
- ordered append behavior;
- idempotency when the same `clientRequestId` is reused;
- stale `expectedRevision` rejection without mutation.

These operations maintain the memory asset. They do not by themselves prove automatic extraction from conversation or automatic injection into every model request.

### Messages

Middle-message insertion is not exposed in Tavo 1.0. `tavo_message_append` appends at the end; supplying an undocumented `message.index` must not be treated as insertion. Read and update targets should use stable message IDs because numeric indices can move.

### Agent Loop

The external MCP server and Tavo's native in-chat Agent Loop are separate tool surfaces:

- external MCP is called by an outside client over HTTP JSON-RPC;
- Agent Loop places Tavo's built-in tool schemas into a model conversation and executes returned tool calls;
- availability on one surface does not imply availability on the other;
- character cards and plugins do not automatically own or register Agent Loop tools.

### Plugins

The current plugin surface includes spec-2 packaging, localization, root `entry`, legacy entry compatibility, hook-only entry, configuration and localization reads, chat/message notifications, input interception, generation lifecycle hooks, TTS, and structured `tavo.input.send()` results. A schema or runtime contribution being visible proves registration only; it does not prove button behavior, visual layout, audio quality, or every hook branch.

## Safe Operation

- Never store, print, commit, or paste the bearer token into prompts, screenshots, logs, issues, or deliverables.
- Confirm the connected Tavo version before relying on a tool or schema.
- Prefer read/search before write, and dry-run before an actual write when supported.
- Read the target immediately before writing; preserve stable IDs and current revisions.
- Use a stable `clientRequestId` for retries so a transport retry does not duplicate a write.
- Apply the smallest patch possible and read the object back after every actual write.
- Treat a successful call as acceptance, not proof of final state. Verify persistence by stable ID and revision.
- Keep visual, audio, model-semantic, import, and persistence checks separate.
- Restore any temporarily changed chat, input, provider, theme, voice, or plugin state.
- Destructive actions such as delete, reset, uninstall, or overwrite require explicit user intent even when the access scope permits them.

## Minimal Compatibility Check

Before a user-authorized MCP workflow, confirm only what that workflow needs:

1. initialize the session and record the negotiated protocol;
2. confirm the required tool names and input fields exist;
3. call the harmless status tool;
4. read the target object and revision;
5. dry-run the intended minimal mutation;
6. perform the actual write only if authorized;
7. read back the final object and restore temporary state.

Do not infer broad product compatibility from tool counts, one successful status call, or a similarly named tool in another Tavo version.
