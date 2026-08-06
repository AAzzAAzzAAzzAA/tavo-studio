# Source Of Truth

This file defines how the Tavo skill decides what is current, what is inferred, and what is historical.

## Current 1.0 Evidence Baseline

- `official-current`: complete 83-page crawl fetched on 2026-07-26, stored in `assets/official-docs/text-20260726/`, `assets/official-docs/official_manifest-20260726.json`, and `assets/official-docs/url_map-20260726.json`. It is the newest retained crawl but predates the connected 1.0 build.
- `release-announcement`: the Tavo 1.0 notice announces native tool calling, plugin center, UI/performance work, `memory.append`, and fixes. It selects test targets but does not define schemas, defaults, or reliability.
- `mcp-runtime`: the redacted 1.0 strict gate in `assets/evidence/1.0.0/20260807-gate.json`. It records Tavo `1.0.0`, negotiated MCP protocol `2025-06-18`, 72 tools, 19 resources, 7 templates, 0 prompts, all dynamic docs/schema reads, and a successful `tavo_status`.
- `live-verified`: the incremental Agent Loop/MCP summary in `assets/evidence/1.0.0/20260807-agent-loop-mcp-live-matrix.json`.
- `prior-version`: the 0.93 broad zero-real matrix, `assets/evidence/0.92.0/20260717-live-matrix.json`, and retained 0.91 artifacts remain version-scoped controls for behavior that 1.0 did not retest.

The 1.0 Agent Loop run used a real provider through a credential-redacting gateway. That proves only the exact model-visible schemas, tool choices, loop transitions, and app effects captured per case; it does not turn unrelated features into real-provider or semantic passes. The prior 0.93 run used a deterministic provider with no upstream or real credentials and remains bounded to its recorded request-assembly/UI/persistence axes.

The retained official crawl has no dedicated release-notes page and does not describe the 1.0 Agent Loop. Treat the MCP `serverInfo.version` and Android package version as runtime version evidence; do not infer a complete changelog from documentation diffs or promote every announcement bullet without a matching runtime/live test.

## Source And Behavior Order

For **declared capabilities and field shapes**:

1. `official-current`: the latest crawl of `https://docs.tavoai.dev/cn/` produced by `scripts/fetch_official_docs.py`.
2. `release-announcement`: current release bullets only for identifying likely deltas.
3. `mcp-runtime`: live tools, resources, schemas, runtime docs, and read-only app state from the connected phone.
4. `historical`: older Tavo-family skills, old probe logs, and old generated guides.

For **whether a feature actually works and is reliable**, use `live-verified` evidence from the current app version. Positive and negative Android/MCP experiments both count. A reproducible live regression outranks a general official support statement for the narrower runtime-behavior claim.

When a current official page and the current MCP runtime document the same new contract, label it `official-current` or `mcp-runtime` until the exact Android effect is executed and read back. Two declarations do not equal a live test.

## Conflict Policy

- When official docs and old skills conflict, use official docs as the current claim and move the old claim to `references/historical/deprecated-claims.md`.
- When official docs are vague but MCP runtime exposes a concrete schema/tool, describe the MCP evidence and mark the result `mcp-runtime`.
- When docs and MCP both leave a behavior ambiguous, design an Android experiment in `references/12-validation-matrix.md` before answering as fact.
- When official docs or MCP expose a feature but current live tests fail, say that the feature is declared but currently unreliable. Preserve both sides and use a `mixed` or `blocked` verdict; do not let documentation overwrite the regression.
- When live positive and live negative results conflict, scope each configuration, app/runtime state, and date. The aggregate reliability verdict remains `mixed` until a discriminating retest resolves it.
- When answering creative quality questions, separate product guarantees from authoring guidance. Use `creative-guidance` for craft advice.
- Use `historical-derived` for non-conflicting material from old skills that improves workflow but still needs current Tavo validation before becoming a product fact.

## Old Skill Quarantine

Old Tavo skills are valuable as search material, not as truth. They may provide:

- candidate workflows to retest;
- script ideas and stable SillyTavern-format utilities;
- known traps, removed APIs, and stale mental models;
- examples of card/worldbook/prompt structure that still need current validation.

They must not provide:

- current API signatures without MCP or official-doc confirmation;
- current app UI paths without Android confirmation;
- current plugin or TavoJS behavior without retesting;
- claims about write permission, persistence, or import success without a current evidence path.

## Evidence In Answers

For non-trivial capability answers, state the evidence tier briefly:

- "官方文档当前写到..." for `official-current`;
- "1.0 更新公告提到，但文档尚未给出契约..." for `release-announcement`;
- "MCP 当前暴露..." for `mcp-runtime`;
- "真机本轮验证..." for `live-verified`;
- "旧 skill 的创作经验可借用，但尚未当作当前产品事实..." for `historical-derived`;
- "旧 skill 里有这个说法，但尚未重验..." for `historical`;
- "旧 skill 里的这个说法现在按废弃处理..." for `deprecated`.

## Refresh Commands

```bash
python3 scripts/fetch_official_docs.py --output /tmp/tavo-official-docs-current
python3 scripts/normalize_official_docs.py
python3 scripts/dump_mcp_surface.py --strict --output /tmp/tavo-mcp-surface-current
python3 scripts/compare_mcp_surfaces.py <previous-mcp-surface.json> <current-mcp-surface.json>
python3 scripts/audit_skill_skeleton.py .
python3 scripts/audit_tavo_skill.py .
```

The current complete official-doc text snapshot is stored under `assets/official-docs/text-20260726/`, with normalized metadata in `assets/official-docs/official_manifest.json`. The 2026-07-16 and 2026-07-10 snapshots are retained as 0.92/0.91 comparison baselines. Refresh the live site and MCP surface before treating this draft as current after future product updates.

`scripts/fetch_official_docs.py` is fail-closed by default: incomplete crawl, fetch errors, or unfetched discovered URLs should return nonzero unless `--allow-partial` is explicitly passed.
