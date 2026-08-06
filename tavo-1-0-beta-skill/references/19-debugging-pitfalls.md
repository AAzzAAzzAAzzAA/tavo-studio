# Debugging Pitfalls

Use this file when a Tavo artifact "imports" but does not behave, or when a capability answer risks overclaiming.

## Import Is Not Preservation

An import dry-run can prove that Tavo accepts an object shape, but it does not prove every field survives. The 2026-07-09 lorebook smoke showed entry normalization after actual import. Use readback/export comparison for preservation claims.

## Source Text Is Not Render Proof

For Advanced Rendering, seeing HTML/CSS/JS source text in a chat is not success. Success requires a visible marker, layout proof, JS side effect, input mutation, variable readback, or another runtime signal.

## Direct MCP Tool Method Calls Are Wrong

Tavo tools are invoked through JSON-RPC method `tools/call`. Direct JSON-RPC methods named after the tool returned method-not-found behavior in the smoke test.

## Screen State Can Break MCP

Phone sleep, network state, endpoint changes, token changes, and app reinstall can make old MCP assumptions invalid. Re-probe every run.

## Repeated `chat.current` And `input.get` Calls Can Accumulate File Descriptors

`live-verified-regression` on Android with Tavo `0.91.0`: background polling of `tavo.chat.current()` and `tavo.input.get()` was associated with reproducible file-descriptor growth and eventually a spinning or unresponsive plugin UI.

- Do not poll these APIs on timers. Read them at explicit user actions or the smallest number of irreversible state boundaries.
- Do not generalize the regression to every TavoJS API. The strongest direct A/B evidence is for `chat.current()` and `input.get()`; other returned operations require isolated tests before being named individually.
- When a plugin spins or stops responding, inspect the unchanged Tavo PID and native resource state before blaming network or external services.
- Distinguish `/proc/<pid>/status` `FDSize` from actual open descriptors. `FDSize` is the descriptor-table capacity; use `/proc/<pid>/fd` or a platform log's held-FD count for the current open count.
- Re-run the same-PID resource gate in `references/15-phone-validation-runbook.md` after a Tavo, Android WebView, plugin-host, or bridge change.

## Expected Revision Can Be Too Strict

`tavo_chat_update` with `expectedRevision` returned a stale error in smoke while update without it worked. For smoke tests, prefer dryRun -> actual without expected revision -> readback -> restore, unless the exact test is about revision safety.

## UI Tree Proves Structure, Not Styling

UIAutomator can locate title, input, focus, messages, and controls, but it cannot prove CSS z-index, clipping, colors, animation, canvas, or WebView internals. Use screenshots for visual claims.

## Accessibility Is Not Guaranteed

The current phone did not have accessibility service enabled. Use UI-tree bounds plus ADB tap as the default fallback. Record accessibility as blocked rather than spending time on it during unrelated validation.

## Old Skill Claims Can Be Dangerous

Known risky old claims include hard TavoJS APIs, internal bridges, read-only/write-only assumptions, and old lint rules. Check `references/historical/deprecated-claims.md` before reusing old snippets.

## Provider Settings Are Sensitive

Voice, image, API, model, and provider settings can leak keys. Do not store real keys in references, scripts, fixtures, screenshots, or artifacts. Prefer status checks, redacted dumps, and disposable provider tests.

## Fake Media Gateways Prove Integration, Not Quality

On Tavo 0.93, the zero-upstream virtual provider proved bounded generation, multipart ASR, TTS, and fixed-image request/response paths without any real credential or model call. Do not promote those results into model semantics, human recognition accuracy, speaker identity, audible queue cancellation, image fidelity, or real-provider compatibility. Keep those proof axes separate and report `countsTowardKpi=false`.

## Local Binding Must Be Proven Before Send

A local provider process existing on the Mac does not prove Tavo will use it. Before every request case, verify the exact feature/chat binding, fixture model id, disabled load balancing/fallback, source-IP allowlist, and capture nonce. If the local-only route cannot be proved, classify the case `blocked` and do not press send.

## Long-Press Duration Is Not A Stable Threshold

The 0.93 automated ASR run completed a normal hold path, but one nominally short hold still emitted a request. Record down/hold/release timing and the postcondition for every gesture. Do not publish one device/build timing as a universal cancel threshold.

## Retain Versus Unset Can Conflict

The 0.93 image-provider UI exposed edit/copy/delete but no unset action for the sole retained config. If the user requires the test config to remain, deletion is not a valid way to make it inactive. Restore the primary chat API and other state, then record the narrow retained-provider limitation.

## Plugin Runtime Reload Can Distort Event Audits

The 0.92 notification matrix observed runtime reload plus catch-up `chat:opened` while a controlled `chat:changed` alias path still missed `chat:updated`. Timestamp and group rows by runtime generation; do not use a reload marker to fill in an event that was never delivered. Treat each generation source independently: terminal semantics can pass even when one declared source path regresses.

## Cleanup Is Part Of The Test

A live test is not passed until disposable objects are cleaned up or deliberately registered as known leftovers. Delete/readback proof is stronger than trusting a successful delete response.
