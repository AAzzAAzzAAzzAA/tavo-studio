# MCP Runtime

This reference covers direct HTTP JSON-RPC operation against Tavo's built-in MCP server. It documents Tavo's own MCP surface only; project-specific MCP client/plugin logic does not belong in this Skill.

## Official Page And Security

- `https://docs.tavoai.dev/cn/guides/mcp-server/`
- The server exists since v0.91.0, is disabled by default, and uses a bearer token plus an app-selected access scope.
- Never store or print the bearer token. Saved dumps must redact authorization values and scrub sensitive URL data.
- Common official failure classes are `401` bad/missing token, `403` insufficient scope, `404/405` wrong URL or method, and timeout/reachability failures.

Preferred access for this workflow is direct HTTP JSON-RPC. Invoke app tools through `tools/call`; do not treat tool names as top-level JSON-RPC methods.

## Current 1.0 Gate

`live-verified` on 2026-08-07:

- server identity: Tavo `1.0.0`;
- 72 tools, 19 resources, 7 resource templates, 0 prompts;
- `initialize`, `tools/list`, `resources/list`, `resources/templates/list`, and `prompts/list` all returned without failure;
- every dynamically discovered docs/schema resource read successfully;
- the operator gate also called `tools/call -> tavo_status` successfully;
- one authorized Android device exposed package `app.bitbear.tav` versionName `1.0.0`.

Durable redacted evidence:

- `assets/evidence/1.0.0/20260807-gate.json`
- `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`

The exact 0.93 -> 1.0 surface delta added `tavo_memory_get`, `tavo_memory_update`, `tavo_memory_append`, and `tavo://docs/tool-calling`; it removed `tavo_message_insert`. Nineteen same-name tool schemas/descriptions also changed. Use `scripts/compare_mcp_surfaces.py` on raw dumps after each release instead of inferring equivalence from similar counts.

This gate proves reachability, identity, discovery, document readability, one harmless status call, and current Android readiness. It does not prove every tool, model, TTS, generation, theme, backup, ASR, or UI semantic by itself. The retained 0.93 gate and matrix remain prior-version evidence for broad features not rerun in the 1.0 overlay.

## Protocol Version Distinction

The current `tavo://capabilities` resource declares MCP protocol `2025-06-18`. Both the redacted 0.93 and 1.0 strict gates requested and negotiated `2025-06-18`. Record both the request and actual response for each artifact:

- use the runtime-declared `2025-06-18` as the default protocol request for refreshed clients;
- record the actual `initialize.result.protocolVersion` returned by the server;
- never rewrite a negotiated value to match the requested value.

A request/response difference is evidence, not by itself a failure. A strict gate fails only when required calls/resources fail or the negotiated protocol is unusable for the tested client.

## Strict Readiness Contract

A current strict dump must fail closed unless all of these pass:

1. `initialize`;
2. `tools/list`;
3. `resources/list`;
4. `resources/templates/list`;
5. `prompts/list`;
6. every dynamically discovered docs/schema/capabilities/runtime resource read;
7. one `tools/call` of `tavo_status`.

The dump must save `serverInfo`, requested and negotiated protocol versions, counts, failed top-level calls, failed resource reads, and document read status. Do not downgrade a missing prompts call or failed dynamic document to a warning in strict mode.

`scripts/test_dump_mcp_surface.py` is the offline regression test for this strict contract: prompts/list, every resource read, and `tavo_status` are required, and requested/negotiated protocol plus status success must appear in the summary.

## Current Runtime Boundary

Available external MCP groups cover status, characters, lorebooks, regexes, presets, personas, chats, messages, input, plugins, and memory. Variables/files remain declared planned; generation/image generation remain deferred; diagnostics are partial.

Memory is no longer deferred in MCP 1.0. `tavo_memory_append` was live-verified for no-op dry run, ordered accumulation, idempotent `clientRequestId`, stale `expectedRevision` rejection without mutation, and exact restoration. Keep these semantics separate from automatic memory extraction/injection, which this case did not prove.

Middle-message insertion is no longer exposed. `tavo_message_insert` disappeared, and `tavo_message_append` ignored a supplied `message.index` and appended at the end in a disposable-chat regression test. Do not emulate insert by relying on an undocumented append index.

The retained 0.93 surface had no ASR/STT/speech-recognition/transcription/microphone tool, resource, resource template, or schema, and no such addition appeared in the 1.0 surface delta. Report this as “not exposed through current MCP,” not “the app has no ASR.” The native 0.93 UI exposed OpenRouter/custom ASR configuration; that UI path was not rerun in the 1.0 overlay.

The external MCP server is not the native in-chat Agent Loop. The latter has a separate 58-tool built-in catalog and dynamic discovery rules documented in `tavo://docs/tool-calling`; read `references/28-tavo-100-live-evidence.md` before comparing the two surfaces.

Current plugin contracts are present in `tavo://docs/plugins` and `tavo://docs/tavojs`, including spec 2/i18n, root `entry`, legacy alias precedence, hook-only entry, config/i18n reads, chat/message notifications, input interception, generation lifecycle Hooks, TTS, and structured `tavo.input.send()` results. Those are `mcp-runtime`; schema/document visibility is not Android effect or semantic proof.

## Runtime Principles

- Reread connectivity, version, endpoint, and token state for every live run.
- Prefer read/list before write and dry-run before actual write where exposed.
- Treat runtime docs as point-in-time evidence for the connected app version.
- Preserve stable IDs/revisions and read back every actual write.
- Keep visual, persistence, audio, import, and semantic proof separate.
- Restore the exact user chat/input/API/theme/voice/plugin state after isolated writes.

## Evidence Layout

Use a unique case directory:

```text
artifacts/tavo-validation/YYYYMMDD-<case>/
  run-manifest.json
  device.txt
  package.txt
  mcp_surface.json
  mcp-requests-redacted.jsonl
  mcp-responses-redacted.jsonl
  ui-before.xml
  ui-after.xml
  screen-before.png
  screen-after.png
  readback.json
  restoration.json
  notes.md
```

Record app/device version, current chat, tool names, retained test object IDs, restore actions, and final evidence tier. Keep bearer tokens, API keys, backup contents, and unredacted provider bodies out of the Skill and repository.
