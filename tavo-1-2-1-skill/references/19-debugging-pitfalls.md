# Debugging Pitfalls

Use this file when a Tavo artifact "imports" but does not behave, or when a capability answer risks overclaiming.

## Import Is Not Preservation

An import dry-run can prove that Tavo accepts an object shape, but it does not prove every field survives. Worldbook entries may be normalized during import. Use readback/export comparison for preservation claims.

## Source Text Is Not Render Proof

For Advanced Rendering, seeing HTML/CSS/JS source text in a chat is not success. Success requires a visible marker, layout proof, JS side effect, input mutation, variable readback, or another runtime signal.

## Direct MCP Tool Method Calls Are Wrong

Tavo tools are invoked through JSON-RPC method `tools/call`. Direct JSON-RPC methods named after the tool are not the supported call path.

## Screen State Can Break MCP

Phone sleep, network state, endpoint changes, token changes, and app reinstall can invalidate an MCP session. Recheck connectivity before relying on it.

## Repeated `chat.current` And `input.get` Calls Can Accumulate File Descriptors

On Tavo `0.91.0`, background polling of `tavo.chat.current()` and `tavo.input.get()` could accumulate file descriptors and eventually leave plugin UI spinning or unresponsive.

- Do not poll these APIs on timers. Read them at explicit user actions or the smallest number of irreversible state boundaries.
- Do not generalize the regression to every TavoJS API. The known boundary covers `chat.current()` and `input.get()`; treat other operations separately.
- When a plugin spins or stops responding, inspect the unchanged Tavo PID and native resource state before blaming network or external services.
- Distinguish `/proc/<pid>/status` `FDSize` from actual open descriptors. `FDSize` is the descriptor-table capacity; use `/proc/<pid>/fd` or a platform log's held-FD count for the current open count.
- Recheck the same process's resource usage after a Tavo, Android WebView, plugin-host, or bridge change.

## Do Not Attach Legacy Revision Fields To 1.2.1

Tavo `1.2.1` removes `expectedRevision` from many current schemas and uses last-write-wins unless a specific tool says otherwise. One old unknown revision field was accepted by `tavo_chat_update` despite the schema disallowing additional properties. Do not rely on unknown-field rejection as a safety control. Use current fields, supported dry-run, actual write, stable-id readback, and restoration.

## Off-Page Input Send Can Target The Last Chat

On the packaged `1.2.1` Mac baseline, input send succeeded from a non-chat settings page and targeted the last active chat even though the declared contract required an active chat page. Always compare `tavo_current_chat_get` with the authorized stable chat id before programmatic send.

## MCP Text Generation May Fail Before The Provider

`tavo_generate` is present in Tavo `1.2.1`, but the packaged Mac baseline returned an internal text-generation failure before the selected provider received the request. Treat the tool as `limited` until the target installation completes a minimal call.

## UI Tree Proves Structure, Not Styling

UIAutomator can locate title, input, focus, messages, and controls, but it cannot prove CSS z-index, clipping, colors, animation, canvas, or WebView internals. Use screenshots for visual claims.

## Accessibility Is Not Guaranteed

Accessibility may be unavailable. Use UI-tree bounds plus an explicit tap fallback when authorized, and keep the limitation separate from the feature under test.

## Old Skill Claims Can Be Dangerous

Risky old claims include hard-coded TavoJS APIs, internal bridges, read-only/write-only assumptions, and obsolete lint rules. Check the current feature reference and scan old code before reuse.

## Provider Settings Are Sensitive

Voice, image, API, model, and provider settings can leak keys. Do not store real keys in references, scripts, fixtures, screenshots, or artifacts. Prefer status checks, redacted dumps, and disposable provider tests.

## Fake Media Gateways Prove Integration, Not Quality

A deterministic provider can exercise bounded generation, multipart ASR, TTS, and fixed-image request/response paths. It does not prove model semantics, human recognition accuracy, speaker identity, audible queue cancellation, image fidelity, or real-provider compatibility.

## Local Binding Must Be Proven Before Send

A local provider process existing on the Mac does not prove Tavo will use it. Before every request case, verify the exact feature/chat binding, fixture model id, disabled load balancing/fallback, source-IP allowlist, and capture nonce. If the local-only route cannot be proved, classify the case `blocked` and do not press send.

## Long-Press Duration Is Not A Stable Threshold

On Tavo `0.93`, a nominally short hold could still emit an ASR request. Record down/hold/release timing and the postcondition for every gesture. Do not treat one device/build timing as a universal cancel threshold.

## Retain Versus Unset Can Conflict

On Tavo `0.93`, an image-provider configuration could expose edit/copy/delete without a separate unset action. If a configuration must remain, deletion is not a valid way to make it inactive. Restore the primary chat API and other state, then report the narrow retained-provider limitation.

## Plugin Runtime Reload Can Distort Event Audits

On Tavo `0.92`, runtime reload could produce catch-up `chat:opened` behavior while a `chat:changed` alias path still missed `chat:updated`. Group observations by runtime generation; do not use a reload marker to fill in an event that was never delivered.

## Cleanup Is Part Of The Test

A live test is not passed until disposable objects are cleaned up or deliberately registered as known leftovers. Delete/readback proof is stronger than trusting a successful delete response.
