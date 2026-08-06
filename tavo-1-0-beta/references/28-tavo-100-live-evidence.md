# Tavo 1.0 Agent Loop And MCP Evidence

Use this overlay for claims that are new or changed in Tavo `1.0.0`. It is not a blanket revalidation of the older product. For unchanged capabilities that were not rerun, retain the explicit 0.93, 0.92, or 0.91 evidence label from the feature reference.

Durable summaries:

- strict runtime gate: `assets/evidence/1.0.0/20260807-gate.json`;
- Agent Loop/MCP behavior matrix: `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`.

Raw phone, MCP, and provider captures remain under `artifacts/tavo-validation/` and are not distributable Skill assets. Neither reusable summary contains the bearer token, LAN endpoint, provider credential, device serial, or private chat identity.

## Release-Notice Boundary

The 1.0 release notice announces native tool calling across OpenAI/Anthropic/Gemini-style protocols, Tavo object operations, web/user-dialog tools, an install/upload plugin center, a redesigned UI, performance work, `memory.append`, and assorted persistence/fix items. The latest retained official documentation crawl predates this build, so the notice is a `release-announcement` source: it identifies what to inspect, but does not define exact schemas, defaults, reliability, or compatibility. Only the live/runtime findings below are promoted.

## Current MCP 1.0 Gate

`live-verified` on 2026-08-07:

- server identity Tavo `1.0.0`;
- requested and negotiated MCP protocol `2025-06-18`;
- `72` tools, `19` resources, `7` resource templates, `0` prompts;
- all five top-level discovery calls, every dynamic docs/schema read, and `tools/call -> tavo_status` passed.

Exact surface delta from the retained 0.93 dump:

| Kind | Added | Removed |
| --- | --- | --- |
| Tools | `tavo_memory_get`, `tavo_memory_update`, `tavo_memory_append` | `tavo_message_insert` |
| Resources | `tavo://docs/tool-calling` | none |
| Templates/prompts | none | none |

Nineteen same-name tools also changed schema or description. The important pattern is stricter explicit IDs/types plus broader documented compatibility forms for character and lorebook imports. Treat a schema delta as a contract change, not behavioral proof; use actual import/readback evidence for preservation claims.

## Two Tool Surfaces, Not One

Tavo 1.0 exposes two related but distinct automation surfaces:

1. **External MCP server:** the LAN HTTP JSON-RPC server used by an outside agent. Its current surface contains 72 tools.
2. **Native Agent Loop:** tools inserted into the selected model provider request while the user chats in Tavo. Its named built-in catalog contains 58 Tavo tools, with discovery and web tools exposed according to the loading mode.

Do not infer that an external MCP tool is available to the chat model, or vice versa, merely because their names overlap. Agent Loop variables are live-tested even though variables remain absent from the external MCP surface. External MCP gained memory CRUD/append, while middle-message insertion disappeared.

The tool catalog belongs to Tavo globally. In this release, rolecards and message scripts cannot register model tools. Plugin/MCP tool definitions have a separate extension-search design, but external registration is dormant in the tested build. Therefore the default tools are not carried by the character card.

## Agent Loop Exposure Modes

The Android UI exposes three global switches in Advanced Rendering settings:

- **启用工具**: global tool-use switch, default off;
- **动态加载工具**: discovery mode, default on after tools are enabled;
- **显示工具调用**: shows persisted tool-call cards/markers in the conversation.

With dynamic loading enabled, all 26 observed initial requests without prior tool results exposed exactly three tools:

1. `tavo_tool_search`;
2. `tavo_ask_user`;
3. `tavo_web_fetch`.

Search queries must be English. The result limit defaults to and caps at 8. A matched tool schema becomes callable on the next provider round, not in the same assistant response. Activations are additive for the current generation and discarded afterward.

With dynamic loading disabled, the live initial request exposed 59 tools: all 58 named built-in Tavo tools, including `tavo_ask_user`, plus the separate `tavo_web_fetch`; `tavo_tool_search` was absent. A real provider called `tavo_get` directly on the first round. After dynamic loading was re-enabled, a new probe returned to the exact three-tool surface.

Counts are versioned observations, not eternal constants. Reinspect `tavo://docs/tool-calling` and a fresh provider request after future updates.

## Loop Limits And Trace Semantics

The current runtime document declares:

- maximum batches: 20;
- maximum calls per batch: 5;
- named tool timeout: 60 seconds;
- JavaScript tool timeout: 120 seconds;
- internal generation ceiling: 50 calls;
- per-result limit: 64 KiB;
- aggregate result limit: 256 KiB.

Tool-trace messages are omitted from later provider history. When **显示工具调用** is enabled, Tavo can persist a visible tool-call card/link in the assistant message, so stored chat text need not equal the provider's final plain token text.

## Live Behavior Promoted In 1.0

- Real-model discovery and tool execution covered variables, input, chat/messages, character, persona, worldbook, regex, preset, memory, user dialog, and web fetch in isolated state.
- `tavo_ask_user` produced the native green dialog and continued after user input. Two earlier dialog attempts failed before a later success, so reliability is not promoted to unconditional.
- A localized minimal spec-2 plugin installed through MCP, enabled, exposed a native input action, wrote the exact marker, disabled cleanly, and was retained disabled.
- External MCP `tavo_memory_append` passed dry-run, ordered accumulation, idempotent `clientRequestId`, stale-revision rejection, and exact cleanup.
- `tavo_message_append` ignored a requested middle index and appended at the end. It is not a replacement for removed `tavo_message_insert`.

## Retry Boundary

One direct-mode attempt lost the provider stream before reaching a tool call. The user tapped **Retry**; Tavo started a fresh initial provider round, the model then called a tool, and the continuation completed. This proves a user-triggered fresh retry path only. It does not prove automatic retry, checkpointing, or seamless continuation of an already-partial Agent Loop.

Keep transport failures separate from Agent Loop semantics. A local relay or upstream disconnect can fail a turn even when tool selection and tool execution are correct.

## Final Restored State

The validation epoch finished with dynamic loading enabled, composer input empty, the minimal test plugin retained disabled with no active contribution, test memory restored to its original disabled/empty state, and the disposable message-insertion chat deleted.

## Repeatable Refresh

For a future version:

1. strict-dump the current MCP surface;
2. compare it with the previous raw dump using `scripts/compare_mcp_surfaces.py`;
3. read `tavo://docs/tool-calling` and capture one fresh initial provider request in each loading mode;
4. rerun only changed/high-risk semantics with isolated objects and explicit cleanup;
5. save a new versioned gate and overlay instead of rewriting older evidence.
