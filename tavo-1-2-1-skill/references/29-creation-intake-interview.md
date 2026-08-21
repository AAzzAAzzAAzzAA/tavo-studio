# Creation Intake Interview

This page defines an authoring interview for vague or from-zero creation requests. It is a creative workflow, not a Tavo product guarantee. Use it mainly for character cards and world cards; adapt the same dependency-aware batching to worldbooks, presets, regexes, and multi-object packages.

## When To Interview

- Vague idea plus unresolved choices that would materially change the artifact: interview before drafting the full deliverable.
- Detailed setting or an existing artifact: ask only about missing high-impact choices; do not repeat what the user already supplied.
- Revision, diagnosis, narrow field edit, or explicit “直接出成品/别问了”: do not force the interview. Proceed with reasonable stated assumptions. A narrow revision changes only the requested target and minimum required dependencies; a diagnosis, global audit, or broad improvement follows the global-audit branch of Existing Card Revision in `references/13-creation-craft-workflows.md`.
- Stop interviewing when the remaining ambiguity can be safely inferred, the user delegates it, or further questions would only polish minor preferences.

## Interview Principles

1. Ask only about creative intent. Resolve product facts, schemas, existing files, and earlier user decisions from the available evidence instead of asking the user to research them.
2. From the second batch onward, offer at most three concrete candidate answers per question and mark one coherent recommendation. The user may choose, mix, replace, or delegate them.
3. If two answers conflict in a way that changes the result, surface the conflict and ask for the deciding preference. Do not silently preserve mutually incompatible requirements.
4. Do not impose a fixed number of rounds. Use as few batches as the dependency structure requires.

## Select Creative Authority

Before substantive drafting, select the matching mode from `references/13-creation-craft-workflows.md`:

- A user who continues answering and approving material choices is in collaborative-confirmed creation. Suggestions are welcome, but substantive additions wait for approval.
- A user who approves a compact demo, candidate, or locked pitch and then says to continue autonomously enters demo-delegated autonomous creation. The agent may fill compatible details and run internal rounds, records its assumptions, and keeps the approved pillars fixed.
- A user who asks only to detone or polish supplied prose is in existing-text cleaning. Expansion requires a separate creation authorization rather than being hidden inside cleanup.

Do not infer autonomous creative authority from silence or from approval of one isolated sentence. A clear delegation such as “剩下你定”, “按这个继续做”, or “直接做出来” is enough; do not ask for a second confirmation after receiving it.

## Dependency-Aware Batching

The rule is simple: if an earlier answer changes how a later question should be phrased, move the later question to the next batch.

- Put independent questions in the same batch.
- Defer relationship, system, field, and delivery questions that depend on the selected direction.
- Begin later batches with a one- or two-sentence summary of the current understanding.
- If the user says “剩下的你定”, complete the unresolved choices with the recommended direction and proceed.
- Do not ask for confirmation twice. A collaborative user may confirm the skeleton once; a direct-output user should receive the finished artifact plus an assumptions list.

## Wording

- Ask in plain language. Put an internal term in parentheses only when it helps the user understand the decision.
- Good: “你为什么会想一直跟这个角色聊下去？（引力核心）”
- Avoid: “请定义这张卡的引力核心。”
- Options must create visibly different outcomes. Do not offer three cosmetic variants of the same idea.
- Replace abstractions such as “有反差感”, “人很立体”, or “过往很精彩” with a concrete behavior, scene, habit, or relationship reaction.

## Character First Batch

Ask these together when they are genuinely unresolved. Questions 1-4 are broad prompts rather than multiple-choice questions; any of them may be skipped. Question 5 is the no-idea exit.

1. 这张卡是个什么人？身份、职业、气质，或者你脑子里已有的任何画面都可以一次说完。（角色身份）
2. 角色的性别、称呼或外在呈现有没有要求？如果不重要可以跳过；非人角色按其设定改问。（身份呈现）
3. 你想玩出什么感觉？例如日常治愈、恋爱拉扯、悬疑刺激、养成变强、冒险或经营。（体验方向）
4. 还有什么必须保留的东西？可以是世界观、关系、参考作品、尺度偏好，或者“这不是单人角色，而是一张 RPG/生存/经营世界卡”。（补充入口）
5. 上面这些如果一时没想法也没关系——我可以直接出几个参考方案给你挑，你看着来。（兜底入口）

The first batch doubles as triage:

- The user answers any of 1-4, even partially: continue the normal interview; treat the rest of 1-4 as a checklist and ask only what is still material.
- The user takes question 5's exit with no direction at all: follow the Quick Card Funnel in `references/33-quick-card-funnel.md` instead of asking further open questions.
- The user answers some of 1-4 and takes the exit for the rest: still follow the funnel, but every candidate must be seeded from what was already answered — nothing the user said is discarded.

If the user already poured the whole idea into question 1 or supplied it before the interview, treat the remaining questions as a checklist and ask only what is still material.

## Later Character Batches

Branch from the chosen direction rather than reading a universal questionnaire:

- Pure chat or relationship play: define how the pair met, their current stage, desired tension, and the character's independent wants.
- RPG, progression, survival, or management: define the repeatable gameplay loop, needed state, event cadence, consequence model, and maximum acceptable complexity.
- Character identity already chosen: make the skeleton concrete through four anchors — ordinary days, reason for their speech pattern, what makes their guarded self slip, and what situations knock them off balance.
- Atmosphere only: ask for one specific scene or behavior that makes the atmosphere visible.
- World card: use the `World Card Authoring` section in `references/13-creation-craft-workflows.md` and ask about world-action rules, narrator boundary, response-format tier, and starting mode.

Language behavior is normally a high-impact choice for a speaking character: sentence length, volume, habitual evasions, audience-dependent differences, and how speech changes with trust. Recurring phrases are optional and should be asked or recorded only when the user wants them or the supplied examples already establish them. Do not ask speech as a mandatory checkbox for a silent entity or a procedural world card; use a Behavior Ledger for non-verbal expression, a Narrator Voice Ledger for intentional narration, and no expression ledger for rule-only text.

Ask about content scale only when the user raises it or when the selected experience makes it materially relevant.

If the user rejects two entire proposal batches without supplying a direction, ask for a recently liked work, character, or scene and infer preferences from that example instead of presenting a third blind menu.

## Prose Style Confirmation

When style is still unresolved, propose one short direction derived from the chosen genre and tone:

> 根据这张卡的调调，我建议用 XX 文风。① 就按这个来；② 我的预设已经管文风，卡里不用重复；③ 换一个方向。

- Express a character's voice and pacing primarily through `first_mes` and `mes_example`.
- Keep stable identity facts in `description`.
- Put a persistent global narration rule in a preset or another prompt-bearing field only when the target channel preserves it and the rule genuinely belongs there.
- Do not automatically write the user's general prose preference into `description`; separate shared preset policy from character facts.

## Optional Add-Ons

After the skeleton holds, propose only add-ons that solve an identified need. The default is a plain character card, not a package containing every Tavo feature.

- Worldbook: for large or conditionally triggered places, factions, rules, NPCs, objects, and secrets.
- Advanced Rendering: for visible status panels, structured cards, buttons, and interactive UI.
- Variables/macros/EJS: for state that must be initialized, changed, or conditionally injected.
- Card art or an image-generation prompt: for a visual deliverable.

If several add-ons are plausibly useful, ask about them in one batch and give a recommendation based on the chosen play mode. Pure chat often needs none; complex RPG or management play may justify worldbook/state support. Route accepted add-ons to the matching topic references rather than improvising implementation details in the interview.

## Delivery Shape

Ask about packaging only when it changes the deliverable:

- Plain card: importable character-card JSON.
- Card plus worldbook: card JSON, standalone worldbook JSON, and optionally embedded `data.character_book` when the target format requires it.
- Complete PNG card: card data embedded into a real card image, with JSON sources retained separately.

For assembly and boundaries, read `references/03-characters-cards-personas.md`. Use `scripts/worldbook_to_character_book.mjs`, `scripts/embed_st_card_png.mjs`, and `scripts/extract_st_card_png.mjs` only for the formats they support. A PNG is not a card merely because it looks like one; extract and validate the embedded data before delivery. Tavo preservation/activation of embedded `character_book` still requires the documented import/readback validation.

## Direct-Output Mode

This section covers users who already have a direction but want no questions. Users with no direction at all take the question-5 exit into the Quick Card Funnel instead.

When the user delegates the decisions or explicitly asks for no questions:

1. Enter demo-delegated autonomous creation. Infer a coherent set of choices within the supplied direction and complete the skeleton internally; do not change the confirmed pillars or materially expand the requested deliverable.
2. Produce the requested finished artifact without a blocking approval step.
3. Include a short “我替你决定了这些” list so agent-chosen details remain distinguishable from user-confirmed facts and can be revised afterward.
4. Ask for confirmation before the final artifact only if the user chose collaborative mode or a genuinely irreversible external action is required.

## Other Objects

For a worldbook, preset, regex, or multi-object package, begin with no more than these high-impact questions when they are unresolved:

1. What problem should this object solve?
2. Which character, chat, preset, or runtime does it attach to?
3. Is there an existing artifact or source material to preserve?

Ask dependent implementation questions only after those answers. Skip the interview entirely for a bounded edit whose target and acceptance criteria are already clear.

## Handoff To Authoring

1. Record the active Creative Authority Mode and summarize the agreed direction in a few lines, unless the user chose direct-output mode. Do not let the later Detone pass change that authority.
2. Draft the skeleton and expand fields using `references/13-creation-craft-workflows.md` and `references/17-authoring-blueprints.md`, passing the Authoring Gates along the way — interview reconciliation before the skeleton, skeleton solidity before expansion, cross-field consistency before cleaning, adversarial read after the mechanical checklist; a gate failure returns to its step before anything proceeds.
3. Resolve material contradictions before authoring; document safe assumptions instead of inventing another interview round for minor details.
4. Before any checklist, run full detone cleaning per the Chinese Prose Cleanup section in `references/13-creation-craft-workflows.md`, with the matching expression ledger as the acceptance check when one applies; record every fix for the delivery report.
5. After the artifact is written, run the mandatory free checklist from the `Prompt Lab Self-Check` section in `references/13-creation-craft-workflows.md`. Once it passes, ask the paid live-test tiers (behavior probes, short arc, synthetic long-history stress test, long-range session) as the final interview batch in plain language — for example “要不要花几次真实模型调用实测一下？可以选：行为探针 / 5 轮短弧线 / 合成长历史压力测试 / 20-30 轮长程，随便组合，不测也可以直接交付”. Deliver with only the checklist report when the user declines.
6. Write the delivery report to the workspace per the `Delivery Report` section in `references/13-creation-craft-workflows.md`; it stays there by default. Deliver the card plus whatever the user selected in the delivery-content question, mention the report's existence in one line, and attach the report itself only when the user explicitly asks.
