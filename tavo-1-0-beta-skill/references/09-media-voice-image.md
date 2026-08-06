# Media, Voice, And Image

This reference covers voice, TTS/STT-like flows, image providers, image generation, and image sending.

Current evidence snapshot: `assets/official-docs/text-20260726/`, `assets/evidence/0.93.0/20260726-gate.json`, and `assets/evidence/0.93.0/20260726-zero-real-matrix.json`. Media evidence is deliberately split into provider-request integration, UI persistence, chat insertion, and human sensory judgment. Prior 0.92 media rows remain version-scoped controls.

## Official Pages

- `https://docs.tavoai.dev/cn/guides/voice-connection/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/get-keys/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/get-keys/elevenlabs/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/get-keys/gemmini/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/get-keys/volink/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/voice-api-settings/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/voice-setting/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/voice-binding/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/tts-guide/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/tts-guide/google-tts/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/tts-guide/iflyrec-tts/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/image-api-settings/`
- `https://docs.tavoai.dev/cn/guides/voice-connection/image-setting/`
- `https://docs.tavoai.dev/cn/guides/others/image-sent/`

## Official-Current Voice Surface

The official docs include:

- voice API key acquisition pages for Volink, Gemini, and ElevenLabs;
- voice API settings;
- voice settings;
- character voice binding;
- local TTS service configuration;
- Google TTS guide;
- iFlyrec TTS guide.

Treat provider credential setup, provider status, and actual sample playback as separate validation layers. A configured key is not proof that a voice can be generated or played.

Official-current settings details to preserve:

- voice API setup creates a provider config, selects platform, fills API key, chooses a voice model, and saves;
- custom OpenAI-compatible TTS may require manually entering a model id or voice id;
- voice binding is under the voice settings area and binds a role/character to a configured voice;
- voice playback settings include automatic playback, narration handling, quote/code/tag handling, and background playback;
- voice playback regex can include or exclude matched content for speech output.

## Official-Current TavoJS TTS

The current TavoJS page and MCP runtime docs expose:

- `tavo.tts.play(text, options)` through an existing character/persona binding;
- `tavo.tts.stop()` for the current chat's shared playback and queue;
- exactly one `character` or `persona` selector in `voice` when called from plugin code;
- optional speaker inheritance for ordinary message TavoJS;
- `queue: false` and `applyPlaybackRules: false` defaults;
- boolean `play()` result, with `false` for empty text, missing targets, or unusable bindings;
- no direct `voiceId` or TTS endpoint-id option in the current public contract.

The 0.93 zero-real run preserved TTS provider configuration with redacted test credentials and captured one bounded role-target request containing `model`, `voice`, `input`, `speed`, and output-format fields against a fixed local WAV. This promotes request assembly and persistence only. Persona targeting, the full playback-rule matrix, two-item queue scheduling, speaker identity, sound quality, and audible stop remain separate.

The prior 0.92 fake-gateway run also observed authorized `/v1/audio/speech` JSON and bounded character/queue behavior. Keep it version-labeled; it does not substitute for 0.93 human listening or full scheduler proof.

## ASR / Speech Input Boundary

The current 83-page official crawl contains no ASR, STT, speech-recognition, transcription, or microphone-input guide. The 0.93 MCP surface likewise contains no matching tool, resource, resource template, runtime-doc section, or schema.

This absence means only **not exposed through current official docs or MCP**. It does not prove that no native Android UI exists. Inspect the app UI, Android microphone permission flow, provider schema, and logs without a key first. If a provider key is required, the user must enter it directly on the phone; never pass it through chat, ADB, CLI, logs, screenshots, or the evidence registry.

The 0.93 Android UI exposed OpenRouter and custom ASR configuration plus parameter fields even though docs/MCP do not expose ASR. Sentinel values persisted across reopen and restart. A deterministic local provider received custom OpenAI multipart WAV requests with `model`, `language`, `prompt`, `response_format`, `temperature`, and WAV MIME/size/SHA-256 metadata. A normal automated long-press down/hold/release path completed without retaining raw audio.

OpenRouter audio-chat wire capture, human recognition accuracy, the complete permission/fault matrix, and every short/cancel/fill gesture boundary were not promoted. In particular, do not encode a fixed safe short-press threshold from this run.

## Official-Current Image Surface

The official docs include:

- image API settings;
- image generation settings;
- image sending.

Image sending docs say the feature lets the user send images to characters, and a multimodal model API must be selected for image understanding. The docs distinguish:

- enabling image sending;
- configuring an image-description API;
- using a model with image understanding;
- configuring description generation and injection prompts;
- sending images in chat.

Treat image-provider configuration, generated image creation, and chat attachment behavior as separate validation layers.

Official-current image-generation details:

- image API settings are separate from voice API settings;
- Volink has a one-click style configuration path in docs;
- users can generate from the chat input `+` menu or with `/imagine <prompt>`;
- preview supports editing prompt, regenerating, and downloading;
- image injection prompt defaults to a text marker that includes `{{prompt}}`.

The TavoJS image docs mention NovelAI/SD behavior for negative prompts and say the NovelAI protocol uses only the first reference image. On 0.92, a disposable fake-key NovelAI entry followed the force-save path after a network failure, reopened with its provider/model fields, and was deleted. This is UI lifecycle proof only; no real NovelAI request or credential was used.

The 0.93 deterministic image provider completed both `b64_json` and local-URL fixed PNG responses through the tested imagine path, with provider persistence and bounded chat/UI evidence. This proves request invocation, response handling, and insertion for those paths, not visual quality, prompt fidelity, every image entry point, attachment/context ordering, or real-provider compatibility.

The prior 0.92 one-pixel gateway remains a version-scoped control and does not expand the 0.93 claim.

## Secret Handling

- Never store real API keys in this skill.
- Do not paste provider keys into reference files, prompt examples, logs, screenshots, or MCP dumps.
- Use minimal harmless prompts for provider tests.
- Record only provider name, model name, status, and non-secret error text.

## Historical-Derived Guidance

- Media features often fail at provider, model, permission, or prompt-injection layers separately; test each layer independently.
- For image sending, use a tiny harmless local image first before testing generation.
- For voice binding, verify both binding persistence and actual playback/generation.
- Keep media tests cheap and reversible.

## Remaining Validation Targets

- Persona TTS with a working binding plus human speaker, quality, and audible queue-stop confirmation.
- Complete voice binding choose/cancel/reopen, playback-rule request counts, and queue-stop scheduling; do not treat persistence as audible behavior.
- Human ASR accuracy, OpenRouter audio-chat wire, permission recovery, and controlled HTTP/malformed-response cases.
- Real NovelAI wire compatibility only when a revocable key is explicitly provided; current save/reopen/delete remains UI-only.
- Meaningful image preview/fidelity, other entry points, error responses, real-provider generation, image sending, and final multimodal prompt/context injection.
