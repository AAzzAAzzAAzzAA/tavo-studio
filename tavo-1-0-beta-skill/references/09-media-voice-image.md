# Media, Voice, And Image

This reference covers voice providers, TTS, native speech input, image providers, image generation, and image sending.

## Voice And TTS

Tavo can configure voice providers, bind a character to a voice, and control playback behavior. Supported setup paths include Volink, Gemini, ElevenLabs, custom OpenAI-compatible TTS, local TTS services, Google TTS, and iFlyrec TTS.

Voice configuration can include:

- provider and API credential;
- voice model and voice ID where the provider requires them;
- role/character voice binding;
- automatic playback and background playback;
- narration, quote, code, and tag handling;
- regex-based inclusion or exclusion of spoken text.

Treat provider configuration, binding persistence, request acceptance, audio playback, speaker identity, and audio quality as separate capabilities. A saved key or successful request does not prove audible output or the intended voice.

## TavoJS TTS Contract

- `tavo.tts.play(text, options)` uses an existing character/persona binding.
- Plugin code must provide exactly one `character` or `persona` selector in `voice`; ordinary message TavoJS can inherit its host speaker.
- `queue` and `applyPlaybackRules` default to `false`.
- `play()` returns a boolean and returns `false` for empty text, missing targets, or unusable bindings.
- `tavo.tts.stop()` stops the current chat's shared playback and clears the queue.
- The public TavoJS contract does not provide direct `voiceId` or TTS endpoint-id playback.

In v0.93, custom OpenAI-compatible TTS supports provider requests carrying model, voice, input, speed, and output-format values. This establishes request-shape support, not speaker accuracy, quality, or queue scheduling.

## Native Speech Input Boundary

Tavo v0.93 exposes native speech-input settings for OpenRouter and custom ASR, including model, language, prompt, response format, and temperature-style parameters. Custom OpenAI-compatible ASR can send multipart WAV input.

This native UI capability is not currently exposed as an external MCP tool or public TavoJS operation. Do not promise programmatic microphone capture, transcription, or permission control through those surfaces.

Speech-input boundaries:

- Android microphone permission and press/hold/release gestures remain part of the native UI flow.
- A configured ASR provider does not prove human recognition accuracy.
- Do not prescribe a universal short-press threshold; gesture behavior can vary by device and app version.
- Provider credentials must be entered by the user through the app, never embedded in a card, plugin, log, or reusable test file.

## Image Generation

Image API settings are separate from voice settings. Image generation can be started from the composer `+` menu or with `/imagine <prompt>`. Preview supports editing the prompt, regenerating, and downloading.

The image-injection template uses `{{prompt}}` when the original prompt should be included. TavoJS image generation can accept options such as size, aspect ratio, negative prompt, reference images, extra request values, save target, and scope.

Protocol boundaries:

- NovelAI/Stable Diffusion-style providers can use negative prompts.
- The NovelAI protocol uses only the first reference image.
- v0.93 handles fixed `b64_json` and local-URL PNG responses in the image-generation path.
- Request/response handling does not establish visual quality, prompt fidelity, or compatibility with every real provider.

## Image Sending

Tavo can send user images to a character when a multimodal model API is selected. The workflow separates:

- enabling image sending;
- choosing an image-description API;
- selecting a model capable of image understanding;
- configuring description generation and injection prompts;
- attaching and sending the image in chat.

Image-provider configuration, generated-image creation, attachment transport, image description, and final multimodal context injection are separate layers. Test them independently.

## Secret And Safety Rules

- Never store real API keys in this Skill, cards, presets, plugins, examples, or screenshots.
- Ask the user to enter provider credentials directly in Tavo.
- Use harmless prompts and non-sensitive media for tests.
- Record only provider/model names and non-secret status or error information.
- Do not retain microphone recordings unless the user explicitly requests it.
- Remove disposable provider configurations when the app offers a safe delete path.

## Validation Method

### Voice

1. Save a disposable provider configuration with no secret in exported artifacts.
2. Bind one test character and confirm the binding survives reopen.
3. Test manual play, automatic play, narration/quote/code/tag rules, and regex filtering separately.
4. Test one queued pair and then stop; listen for order, speaker identity, audio quality, and actual queue clearing.
5. Repeat with a persona binding only if that is part of the deliverable.

### Speech input

1. Check permission denial, grant, cancellation, and normal press/hold/release behavior.
2. Use a harmless sentence with known wording.
3. Compare transcription accuracy, punctuation, language handling, and prompt influence.
4. Test provider error and malformed-response recovery without retaining raw audio.

### Images

1. Use a tiny harmless local image for attachment tests.
2. Test provider save/reopen independently from generation.
3. Test generation, preview, regeneration, download, and chat insertion as separate actions.
4. For image sending, compare the visible attachment, generated description, and model response.
5. Use meaningful human review for composition and prompt fidelity; a technically valid PNG is not a quality pass.
