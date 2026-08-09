# Prose Detone Pattern Catalog

This catalog describes patterns, not banned words. Every rule must be judged together with position, density, semantic function, register, and neighboring patterns. A single occurrence of an ordinary phrase usually stays; items marked hard residue may be processed on a single hit. The protocol that owns these patterns lives in `references/30-prose-detone.md`; narrative/RP family and lexical families continue in `references/32-prose-detone-narrative.md`.

## Strength Marks

- **H (hard residue):** normally no legitimate function in finished prose; a single hit may be repaired.
- **S (strong signal):** needs context confirmation; repair first once confirmed.
- **C (combined signal):** weak alone; repair only when repeated or clustered with other patterns.

Repair order is always: delete the uninformative part → restore agent and action → break the automatic template → adjust rhythm → swap words only last.

## A. Assistant Interaction Residue

### A01 Answer Announcement (H)

- Signal: "以下是……", "下面我将……", "我来为你……" inside prose that should deliver directly.
- Boundary: tutorials that genuinely need document navigation may keep reader-facing navigation, never model self-actions.
- Fix: start from the first effective piece of content; if navigation is necessary, use a document heading or a content transition.

### A02 Instruction Restatement (H)

- Signal: the opening rewords the user's request, format, tone, or constraints without adding content.
- Boundary: scope confirmation can be part of the task in contracts, meeting minutes, and complex commissions.
- Fix: delete the restatement; if confirmation is truly needed, keep one shortest note outside the body.

### A03 Understanding Confirmation (H)

- Signal: "我明白你的意思", "懂了", "你想要的是……" mixed into articles, character prose, or email drafts.
- Boundary: in private dialogue where the speaker really confirms understanding, it is content, not residue.
- Fix: delete the assistant confirmation, or let the character respond to the concrete content in their own voice.

### A04 Process Preview (S)

- Signal: "我会先……再……最后……" describing how the model will answer instead of a process the reader must execute.
- Boundary: experiment steps, tutorials, and project plans need real sequence.
- Fix: delete the meta-narration; turn valid steps into direct instructions or natural paragraphs.

### A05 Information-Free Praise (H)

- Signal: "好问题", "你说得非常对", "这是很有洞察力的想法" serving only as politeness padding.
- Boundary: in character dialogue, review comments, or real social contexts, praise can carry relationship function.
- Fix: answer the question directly; when acknowledging contribution, name the specific point that holds.

### A06 Model Identity and Capability Claims (H)

- Signal: "作为 AI", "我的知识截止于", "我无法实时访问" leaking into finished prose.
- Boundary: the article discusses model capability, or the user explicitly keeps the statement.
- Fix: remove from the body; if the limitation affects factual reliability, note items to verify outside the body.

### A07 Defensive Disclaimers (S)

- Signal: unrequested "仅供参考", "具体情况因人而异", "请咨询专业人士" repeatedly wrapping low-risk content.
- Boundary: necessary limits in medical, legal, financial, and safety text must stay.
- Fix: keep only the limit matching the risk, place it near the relevant conclusion; do not drown the body in generic disclaimers.

### A08 Unsolicited Extra Service (H)

- Signal: "如果你愿意，我还可以……", "需要的话告诉我" closing articles, reports, or character prose.
- Boundary: service scripts, sales emails, or real collaboration messages may need a next-step invitation.
- Fix: delete; if the genre needs a call to action, write the action the reader actually takes.

### A09 Service-Desk Well-Wishes (H)

- Signal: "希望以上内容对你有所帮助", "祝你创作愉快" unrelated to the body's purpose.
- Boundary: private emails, congratulation letters, and service notices may have genuine polite closings.
- Fix: end on the last effective information, or a short sign-off fitting the relationship and scene.

### A10 "No Beating Around the Bush" Declaration (C)

- Signal: "直接说结论", "不废话", "开门见山" followed by long preamble, or recurring across answers.
- Boundary: spoken scripts, livestream talk, or a specific character voice may use it once naturally.
- Fix: actually give the conclusion directly; delete self-advertising about directness.

### A11 Output Format Self-Description (H)

- Signal: "我将用表格呈现", "按照你的要求分为三部分" left in delivered prose.
- Boundary: accessibility notes or complex document navigation may explain how to read.
- Fix: let the format show its own structure; necessary navigation becomes content headings.

### A12 Editing Trace Leakage (H)

- Signal: "改写后如下", "这里保留了原意", "我删除了 AI 味" entering the final draft.
- Boundary: when the user asks for a change report or before/after comparison, keep it outside the body.
- Fix: strip from the final draft into a short change note.

## B. Section and Organization Inertia

### B01 Era-Background Opening (S)

- Signal: "随着……不断发展", "在……时代背景下" transferable to many topics, offering no time, mechanism, or conflict.
- Boundary: the background change itself is the argument's premise, and later text names the change and its effect chain.
- Fix: start from a concrete event, problem, observation, or conclusion; when background is needed, give verifiable change.

### B02 Importance First (C)

- Signal: the opening announces "至关重要、不可或缺" before reasons exist.
- Boundary: abstracts, policy notes, and risk warnings sometimes state conclusions first.
- Fix: bring the grounds for importance forward, or let facts build the weight.

### B03 Automatic Total-Branch-Total (C)

- Signal: abstract opening, three parallel sections, abstract summary repeating across unrelated topics.
- Boundary: exam writing, speeches, policy material, or the user explicitly requests that structure.
- Fix: organize by real relations: time, causality, problem levels, evidence strength, or perspective shift.

### B04 Three-Point Reflex (C)

- Signal: content naturally has two or four layers but is merged or split into "第一、第二、第三".
- Boundary: the three items really are exclusive, complete, or come from a fixed norm.
- Fix: restore the true count and levels; never add a third item for rhythm.

### B05 Equal-Weight Paragraphs (C)

- Signal: every point gets nearly identical length, tone, and depth; key and minor information expanded equally.
- Boundary: product specs, comparison tables, and standardized evaluations need uniform format.
- Fix: give core content more space; merge minor items or pass them in one sentence.

### B06 Paragraph-Label Copying (C)

- Signal: consecutive paragraphs all start with an abstract noun plus colon, like "效率层面：", "体验层面：".
- Boundary: norm checklists, audit tables, troubleshooting manuals.
- Fix: let paragraph openings enter facts or actions directly; keep labels only when fast scanning needs them.

### B07 Paragraph-End Restatement (C)

- Signal: each paragraph's last sentence says the paragraph again, usually with "这意味着、由此可见".
- Boundary: complex arguments need explicit staged inference.
- Fix: delete if the inference adds no logic; if it does, write the bridge from premise to conclusion.

### B08 Double Full-Text Summary (S)

- Signal: the ending stacks "总的来说、换句话说、归根结底" repeating the same conclusion.
- Boundary: a long report's executive summary and body summary serving different readers may coexist.
- Fix: keep one closure; if the ending has no new job, stop at the last concrete fact.

### B09 Challenge-and-Outlook Template (S)

- Signal: every topic ends with "尽管面临挑战，未来仍充满希望".
- Boundary: the user truly asks for risks and next steps, and challenges, owners, and actions are concrete.
- Fix: delete generic optimism; write real open problems, conditions, or next steps.

### B10 Positive-Energy Flip (S)

- Signal: negative, complex, or tragic content suddenly turns into growth, hope, and strength in the final paragraph.
- Boundary: the author or character genuinely holds that judgment, or the genre closes with advocacy.
- Fix: respect the original emotion and unresolved state; never heal the text on its behalf.

### B11 Abstraction Ladder (S)

- Signal: rising from concrete items to industry, era, civilization, humanity — higher levels carry less information.
- Boundary: essays or criticism really arguing a macro extrapolation with bounded evidence.
- Fix: stop at the highest level the evidence supports; delete mechanism-less uplift.

### B12 Pseudo-Comprehensive Coverage (C)

- Signal: "从多个维度、全方位、系统性" claiming completeness while listing a few ordinary points.
- Boundary: methodology actually defines dimensions and coverage.
- Fix: drop the scope advertising; list the real analysis objects.

### B13 Topic Boundary Expansion (S)

- Signal: the answer extends from the user's question to history, ethics, social impact, and future trends without task need.
- Boundary: the user asks for a panoramic analysis, or missing background would mislead the conclusion.
- Fix: return to the question boundary; move optional extensions out of the body or delete them.

### B14 Symmetric Section Illusion (C)

- Signal: every section has the same number of subsections, same-shaped headings, and the same closing sentence.
- Boundary: templated manuals, courses, and compliance documents need symmetry.
- Fix: let content complexity decide section depth; never pad empty subsections.

### B15 Define Then Repeat (C)

- Signal: an abstract definition first, then the whole paragraph rewords it.
- Boundary: textbooks define, then explain or give boundary examples.
- Fix: after the definition give mechanism, counterexample, application, or evidence; if none, stop.

### B16 Every Paragraph Self-Contained (C)

- Signal: each paragraph reads as a standalone mini-essay; paragraph ends repeatedly land on judgment, realization, relationship change, or abstract meaning, so long text feels assembled from one template.
- Boundary: FAQs, card-style content, regulations, independently searchable paragraphs, and deliberate chapter-hook style.
- Fix: delete a paragraph ending that only summarizes what was just said; three-plus same-type closures across paragraphs count as a strong signal. Allow endings on fact, action, example, or question, with the next paragraph picking up naturally.

### B17 Adjacent Proposition Echo (S)

- Signal: adjacent sentences or paragraphs restate the same claim with near-synonyms, adding no condition, evidence, exception, causality, scope, or perspective difference.
- Boundary: boundary/counterexample after a definition; confirmation, refusal, irony, stutter, or deliberate repetition in dialogue; restatement needed for disambiguation in legal, technical, and safety text.
- Fix: after semantic confirmation keep the more concrete, better-scoped, or more voice-faithful occurrence; near-synonym does not mean synonym — never delete differences in modality, negation, scope, or source.

## C. Logic and Semantic Idling

### C01 Vague Authority (S)

- Signal: "专家认为、研究表明、业内普遍认为" without an identifiable source or scope.
- Boundary: the original text supplies the source later, or is explicitly a common-knowledge overview.
- Fix: give the source the input already has; otherwise downgrade to a limited statement or drop the authority claim.

### C02 Vague Data (S)

- Signal: "数据显示、实践证明、大量案例" without data, samples, or cases.
- Boundary: the abstract cites a dataset defined in the same document.
- Fix: point to concrete evidence; otherwise delete "data proves" and lower the conclusion's strength.

### C03 Empty Causal Connectors (S)

- Signal: "因此、由此、这也意味着" joining two sentences that are merely parallel or sequential.
- Boundary: the first sentence really is a full or partial cause of the second.
- Fix: write the mechanism and conditions; with only correlation, use parallel or uncertain phrasing.

### C04 Circular Definition (S)

- Signal: explaining itself with synonymous abstractions, like "高质量来自对质量的重视".
- Boundary: rhetorical emphasis serving a specific voice.
- Fix: add observable standards, actions, or boundaries; if impossible to concretize, delete.

### C05 Abstract Subject Agency (C)

- Signal: "机制、体系、模式、逻辑" repeatedly performing "赋能、驱动、带来"; real actors vanish.
- Boundary: institutions or algorithms really are analyzable mechanisms.
- Fix: restore who does what, to whom, under what conditions.

### C06 Abstract Value Landing (C)

- Signal: facts automatically followed by "体现价值、彰显意义、反映趋势".
- Boundary: the text's task is value interpretation, and the landing is argued.
- Fix: delete empty landings, or explain which value affects whom and which decision.

### C07 Pseudo-Concrete Enumeration (S)

- Signal: listing "场景一、场景二、场景三" that are one abstract point renamed.
- Boundary: the scenarios differ in participants, conditions, actions, or results.
- Fix: merge duplicates; keep only differences that change decisions.

### C08 Excessive Subject Omission (S)

- Signal: "需要、应当、可以" in a row with no idea who is responsible.
- Boundary: operation manuals where the reader is the default subject.
- Fix: name the agent at responsibilities, judgments, and commitments; unambiguous action chains may omit.

### C09 Generalized Beneficiaries (C)

- Signal: "帮助用户、满足需求、提升体验" without saying which users, what task, or what measure.
- Boundary: the context has defined target users and metrics.
- Fix: refer back to known objects; when impossible, delete the benefit claim.

### C10 Absolute Conclusions (S)

- Signal: limited evidence written as "必然、彻底、所有、唯一".
- Boundary: mathematics, protocols, or explicit rules allow absolute judgment.
- Fix: restore evidence scope and conditions; never stack vague words in place of precision.

### C11 Uncertainty Stacking (C)

- Signal: "可能、也许、一定程度上、某种意义上" chained so the author commits to nothing testable.
- Boundary: high-uncertainty fields need separate uncertainty from separate sources.
- Fix: keep the one most accurate limit; say whether uncertainty comes from sample, time, or mechanism.

### C12 False Balance (S)

- Signal: automatic "一方面……另一方面……" when the evidence is asymmetric, or only to seem neutral.
- Boundary: the task requires comparison and both sides have evidence.
- Fix: express by evidence weight; not every judgment needs a manufactured opposite.

### C13 Problem-Solution Auto Kit (C)

- Signal: every problem paired with a broad "加强、优化、完善" plan lacking owners, costs, and constraints.
- Boundary: early brainstorming explicitly marked as direction, not plan.
- Fix: write action, owner, constraints, and verification; otherwise call it an open research direction.

### C14 Motivation Ghostwriting (S)

- Signal: asserting "用户真正想要的是", "他其实害怕的是", "品牌希望传达" without evidence.
- Boundary: the original text, interviews, or character setup give the motivation.
- Fix: return to observable words and deeds; "可能" does not replace evidence.

### C15 Emotion Diagnosis (S)

- Signal: ordinary behavior explained as trauma, anxiety, control need, or self-protection.
- Boundary: professional assessment, or a character interior view with sufficient setup.
- Fix: describe behavior and spoken feelings; never name deep psychology unbidden.

### C16 Slogan Replacing Mechanism (S)

- Signal: "以人为本、长期主义、守正创新" answering how-to questions.
- Boundary: the text explicitly states principles and has a separate execution section.
- Fix: ground principles in selection criteria or actions; if ungroundable, delete.

## D. Syntax and Connection Inertia

### D01 "不是 X，而是 Y" Over-Density (C)

- Signal: antithetical negation repeated at short distance, X/Y both abstract bucket words, the information stateable directly. When the user registers this frame as a personal hard ban, a single occurrence enters semantically safe rewriting.
- Boundary: genuinely correcting a misunderstanding, explicit character rebuttal, or logical exclusion needs the contrast.
- Fix: when X is only padding, state Y directly; when X must be excluded, state the correct conclusion and the negation of X separately. Never swap "而是" for "其实是/恰恰是/在于" and keep the same frame.

### D02 "不只是，更是" Escalation (C)

- Signal: every ordinary function lifted into relationship, fate, growth, value, or identity meaning; the second half is usually an abstract synonym-uplift of the first.
- Boundary: both layers are verifiable independent facts, or the second has evidence and truly sits on a different level.
- Fix: if both are facts, plain coordination or separate sentences; if the second half only uplifts, stop at the more concrete one. Under personal hard ban, break the frame on a single hit without losing factual additions.

### D03 "从 X 到 Y" Pseudo-Range (C)

- Signal: X/Y on different scales or with no coverage between, used only for expansiveness.
- Boundary: time, process, geography, or magnitude really forms a continuous range.
- Fix: describe the two items separately, or give the real range.

### D04 "通过……从而……" Chain (C)

- Signal: one sentence crams method, process, purpose, and result with unverified causality.
- Boundary: technical mechanisms or operation notes need compact real chains.
- Fix: split into action and result; when the result is uncertain, state conditions.

### D05 Redundant Preposition Shells (C)

- Signal: "通过……的方式", "基于……的基础", "由于……的原因".
- Boundary: specific legal or technical terms cannot be altered.
- Fix: convert to direct verbs or simple preposition structures.

### D06 "进行 + Action Noun" Density (C)

- Signal: everyday or narrative text chaining "进行分析、进行优化、进行讨论".
- Boundary: academic, official, and process text needs nominalization for stable reference.
- Fix: use direct verbs where no downgrade occurs; keep "进行" that truly names one formal activity.

### D07 Connective Parade (C)

- Signal: every paragraph opens with "此外、同时、然而、因此、另一方面"; relations claimed by words, not built by content.
- Boundary: complex argument really needs explicit logical markers.
- Fix: delete connectives the sequence already shows; when the relation is unclear, fix the logic, not the connective.

### D08 "这表明/意味着" Reflex (C)

- Signal: nearly every fact followed by an interpretation that only rewords it.
- Boundary: data needing its meaning or limits explained.
- Fix: keep only genuinely new inference, with scope stated.

### D09 Excess Referential Shells (C)

- Signal: "这一现象、这种趋势、该模式、这一做法" in a row, distant or unnecessary reference.
- Boundary: professional long-form needs stable terms for complex objects.
- Fix: omit nearby, restore concrete nouns, or merge sentences.

### D10 Passive Translationese (C)

- Signal: "被认为、被视为、被广泛用于" repeatedly hiding the judge.
- Boundary: academic register, unknown agent, or patient emphasis justifies passive.
- Fix: name the agent when known; otherwise lower the authority tone.

### D11 Nested Long Attributives (C)

- Signal: multiple layers of "的" pressing conditions, actions, and objects in front of the noun.
- Boundary: legal names, fixed terms, or unbreakable proper nouns.
- Fix: turn conditions and actions into predicates; bring the topic forward.

### D12 Unnecessary Subject Repetition (C)

- Signal: consecutive sentences mechanically repeat the same proper name or "它/他们" where Chinese context is clear.
- Boundary: multi-agent switching, legal responsibility, or cross-paragraph reference needs disambiguation.
- Fix: omit or merge when unambiguous; keep concrete subjects where ambiguous.

### D13 English-Style Abstract Subjects (C)

- Signal: dense literal translations like "这一事实使得……成为可能", "这种方法允许用户去……".
- Boundary: technical contexts where "允许/禁止" express permission or protocol acts.
- Fix: use natural Chinese predication: "用户可以……", "因此能……".

### D14 Judgment Before Colon (C)

- Signal: "逻辑很清晰：", "原因很简单：", "答案很明确：" — evaluating before stating.
- Boundary: speeches and spoken scripts deliberately creating a pause.
- Fix: delete the evaluation; give the reason, answer, or logic directly.

### D15 Modality Stacking (C)

- Signal: "可能会有望进一步", "应该需要考虑" stacked before one predicate.
- Boundary: distinct modalities for probability, norm, and plan may coexist if clear.
- Fix: choose the one most accurate, or separate uncertainties from different sources.

### D16 Abstract Sentence-End Complement (C)

- Signal: sentences repeatedly ending with "提供支撑、带来价值、具有意义、形成赋能".
- Boundary: report conclusions really evaluating concrete impact.
- Fix: end on observable results; without results, stop at the action.

### D17 "越 X 越 Y" Cluster (C)

- Signal: "越 X 越 Y" repeated in the same or adjacent paragraphs, especially chaining abstract psychology, relationship, or life judgments.
- Boundary: mathematics, physics, statistics, and clear trend relations; stable character voice; deliberate repetition in poetry or oratory.
- Fix: when a real variable relation exists, keep one occurrence preserving direction and conditions; decorative progressions become action, condition, or result. Never convert correlation into causation.

### D18 Auto-Explanation After Statement (C)

- Signal: short-distance repetition of "fact/action → 这说明/意味着", narration explaining after dialogue, translating the moral after a metaphor, or "换句话说" echo; multiple explanation frameworks jointly taking over progression.
- Boundary: new inference needing an evidence bridge; explanation adding scope, limits, counterexample, or perspective difference.
- Fix: keep genuinely new inference with its basis stated; delete psychology-overreach explanations; hand fully synonymous single-proposition repetition to B17 for merging. Similarity only earns a second look — never automatic deletion.

## E. Lexicon and Collocation Inertia

### E01 Corporate Jargon Cluster (C)

- Signal: "赋能、抓手、闭环、飞轮、颗粒度、组合拳、心智、方法论" clustering outside industry need.
- Boundary: the organization uses these words for clearly defined processes or metrics.
- Fix: write the actual action, object, and measure; keep terms with stable definitions.

### E02 Generalized Intensity Words (C)

- Signal: "深度、全面、高效、精准、系统、持续" frequently modifying ordinary actions without a comparison baseline.
- Boundary: metrics, scope, or method have defined the intensity's meaning.
- Fix: delete baseline-less modifiers, or substitute the input's own metrics.

### E03 Model Action Verbs (C)

- Signal: "解锁、激活、撬动、重塑、重构、释放、沉淀" fixed to abstract value objects.
- Boundary: technical, gaming, or business contexts where the sense is concrete, like "解锁账号", "重构函数".
- Fix: replace with the real action — open, modify, accumulate, add, remove.

### E04 Grand Imagery Package (C)

- Signal: "时代浪潮、壮丽画卷、璀璨篇章、历史长河、星辰大海" with no unique connection to the topic.
- Boundary: literary, oratory, or character voice deliberately cultivating the same image system.
- Fix: delete ornament; if the image matters, connect it to concrete objects and feelings in the scene.

### E05 Promotional Adjective Stacking (C)

- Signal: "令人惊叹、卓越、非凡、领先、颠覆、革命性、沉浸式" without verifiable basis.
- Boundary: advertising register allows evaluation but must fit brand voice and facts.
- Fix: substitute features, results, or evidence; purely subjective copy at least reduces same-paragraph density.

### E06 Pseudo-Healing Collocations (C)

- Signal: "温柔而坚定、接住情绪、看见自己、允许自己、内在力量" applied to ordinary relations or advice.
- Boundary: the speaker really talks this way, or psychoeducational text has defined the concepts.
- Fix: return to concrete feelings, behaviors, and boundaries; never complete the emotion-naming for the person.

### E07 Self-Media Strong Hooks (C)

- Signal: "狠狠、拉满、拿捏、封神、天花板、建议收藏、不允许你不知道" mismatching the platform or account voice.
- Boundary: the account stably uses the expression, or the user explicitly wants algorithm-style spoken copy.
- Fix: open with real benefit, conflict, or observation; never manufacture false urgency.

### E08 Fake-Candor Hooks (C)

- Signal: "说实话、讲真、坦白说" used only to add truthfulness to an ordinary conclusion.
- Boundary: the speaker really admits an unfavorable fact, changes stance, or risks the relationship.
- Fix: delete without real cost; with cost, keep it and make the candor content explicit.

### E09 High-Frequency Evaluation Bucket Words (C)

- Signal: "关键、核心、重要、深刻、复杂、丰富、多元" recurring without distinguishing concrete dimensions.
- Boundary: term names, or argument really comparing importance.
- Fix: say where it is key and what the complexity consists of; otherwise delete the evaluation.

### E10 Four-Character Phrase Chaining (C)

- Signal: one sentence stacking several four-character phrases with loose relations, forming one promotional beat.
- Boundary: official documents, speeches, archaic-style characters, or deliberate parallelism.
- Fix: keep the one or two most accurate; turn the rest into concrete actions or delete.

### E11 Synonym Rotation (C)

- Signal: to avoid repetition, the same object is called "平台、系统、生态、载体、阵地" in turn, causing concept drift.
- Boundary: the words really correspond to different levels or components.
- Fix: use one stable name for one object; define first when distinction is needed.

### E12 Redundant Bilingual Annotations (C)

- Signal: common Chinese words mechanically followed by English, or English terms followed by a full Chinese re-explanation.
- Boundary: first-time term definition, cross-language readers, standard names, or search needs.
- Fix: keep one at the first necessary spot; use a stable short form after.

### E13 Golden-Line Formula (S)

- Signal: screenshot-ready frames like "真正的 X 从来不是 Y，而是 Z", "X 是成年人的 Y" replacing argument.
- Boundary: the text itself is speech, advertisement, or character dialogue, and the line fits that voice.
- Fix: break into verifiable statements; never keep symmetric structure for quotability.

### E14 "一场关于" Uplift (C)

- Signal: ordinary products, events, or actions described as "一场关于成长/边界/自我的探索".
- Boundary: curation notes or themes explicitly given by the creator.
- Fix: say what the event does; theme judgments need a source or work details.

### E15 Relationship-Word Anthropomorphizing (C)

- Signal: products, institutions, or concepts written as "陪伴、守护、拥抱、理解每一个人" without concrete service mechanism.
- Boundary: brand anthropomorphism is a confirmed long-term strategy.
- Fix: state the actual function, response, or guarantee provided.

### E16 Trendy Slang Smuggling (C)

- Signal: current buzzwords sprinkled evenly across unrelated topics, mismatching semantics and audience.
- Boundary: subculture authors really use them and the target readers understand.
- Fix: do not chase "sounding like netizens"; restore the domain's ordinary expression.

### E17 Portable Ornament Clusters (C)

- Signal: decorative comparisons, rare lyric words, light/fate/ripple imagery clustered with abstract adjectives; the whole passage would still work transplanted to another person or topic.
- Boundary: literary, oratory, or brand text with an explicit image system; words coming from character experience and developed later.
- Fix: keep the most object-bound rendering with consequence; delete the rest or restore concrete action, objects, and judgment. Never reskin within a synonym cluster.

### E18 Vague Feeling Kit (C)

- Signal: "说不出的、难以言喻、莫名、微妙、复杂、某种" continuously declaring emotion without conflict source, perspective limit, or behavioral consequence.
- Boundary: the inability to name is itself the character's state, suspense, or real uncertainty in argument.
- Fix: carry it with the input's own conflict choices, senses, or judgments; delete when adding nothing, never diagnose the character.

### E19 Micro/Slow-Motion/Silent Adverb Stacking (C)

- Signal: "微微、轻轻、缓缓、悄然、微不可察、不易察觉" densely attached to ordinary actions, uniformly shrinking, slowing, or muting them.
- Boundary: amplitude, speed, sound, or perceptibility are physical and narrative facts, or the expression belongs to an established character voice.
- Fix: delete degrees the verb already expresses; check amplitude, speed, sound, and perceptibility separately — never swap in another adverb.

### E20 Non-Volitional Action Label Stacking (C)

- Signal: "不由自主、下意识、不自觉、不禁、无意识" repeatedly declaring actions non-volitional, skipping trigger, hesitation, or choice.
- Boundary: non-volitionality already asserted by existing text is a semantic lock; medical, legal, psychological states, or physical reflexes need precise distinction. The surprise of "竟/竟然" does not belong to this rule.
- Fix: under guarded writing, never generate the labels without setup or event basis. When cleaning existing text, preserve volitionality only with the input's own triggers or equivalent wording; if no safe restructure exists, keep it — never convert to neutral or volitional choice.

## F. Rhetoric, Rhythm, and Voice Homogenization

### F01 Antithetical Negation Burst (S)

- Signal: consecutive "不是 X，也不是 Y，更不是 Z，而是……" landing on abstract nouns.
- Boundary: debate, rebuttal, or character emphasis really needs item-by-item exclusion.
- Fix: keep only the misunderstanding that needs correcting; state the rest affirmatively.

### F02 Triple Isomorphism (C)

- Signal: "既 X 又 Y 还 Z", "从 X 到 Y 再到 Z" triads, or consecutive binary-symmetric sentences highly identical in grammar, length, and abstraction when content does not demand parallelism.
- Boundary: the three items are genuinely independent or exclusive; protocols/norms listing item by item; oratory, poetic prose, official style, or a character's rhetorical habit.
- Fix: when several symmetric/triple structures cluster at short distance, restore the true levels and merge near-synonymous items; never randomly reduce three to two, nor break states that must stay itemized.

### F03 Rhetorical Self-Answer Reflex (C)

- Signal: "为什么？因为……", "答案是什么？其实……" repeatedly serving as transitions in one piece.
- Boundary: teaching where the question is a real cognitive step, or a character thinking.
- Fix: state directly, or keep only questions with real suspense that change understanding.

### F04 Dramatic Short Paragraphs (C)

- Signal: "答案很简单。", "事情开始变得有趣。", "一切都变了。" standing alone without a matching turn.
- Boundary: novel pacing, spoken-cut editing, or deliberate paragraph hammering.
- Fix: merge with concrete content; when a real turn exists, let the next sentence cash it in immediately.

### F05 Screenshot Endings (C)

- Signal: every section closing with a rhythmic, symmetric, abstract golden line.
- Boundary: brand columns or speeches with a designed uniform closure.
- Fix: let some paragraphs end on fact, action, question, or incompletion.

### F06 Uniform Sentence Length (C)

- Signal: consecutive sentences with near-identical length and clause count, reading like template copies.
- Boundary: regulations, spec tables, subtitles, and children's books need stable length.
- Fix: merge or split by information unit; never vary length at random.

### F07 Uniform Paragraph Length (C)

- Signal: every paragraph the same four or five sentences with the same rise-turn-close, hiding emphasis.
- Boundary: card-style content, course notes, or hard layout limits.
- Fix: let paragraph length follow the argument's weight; short paragraphs only for genuine emphasis.

### F08 One Sentence Ending (C)

- Signal: consecutive sentences all ending with "……的重要体现/有力支撑/关键所在/必然选择".
- Boundary: clauses or lists requiring grammatical parallelism.
- Fix: delete abstract tails, end sentences on concrete action or object; merge same-function sentences.

### F09 Colon Chaining (C)

- Signal: repeated "judgment: explanation" inside one paragraph; every sentence reads like a label card.
- Boundary: glossaries, field descriptions, troubleshooting lists.
- Fix: turn into natural predication or split paragraphs; keep colons only where label lookup is needed.

### F10 Dash-Explanation Addiction (C)

- Signal: every sentence patched with a dash for "也就是说/这意味着", constantly interrupting the body.
- Boundary: literary asides, parentheticals, or term explanations with clear rhythm function.
- Fix: fold into the main clause where possible; delete repeated explanations outright.

### F11 Parenthetical Meta-Commentary (C)

- Signal: "（这里很关键）", "（注意，不是……）" repeatedly directing the reader's reaction.
- Boundary: textbook tips, legal definitions, stage directions, and genuine aside voices.
- Fix: write necessary information into the body; delete information-free evaluations.

### F12 Metaphor Followed by Explanation (C)

- Signal: every metaphor immediately translated into abstract reasoning, distrusting the reader.
- Boundary: children's education, cross-cultural explanation, or metaphors likely to mislead.
- Fix: keep either the metaphor or the explanation; when a limit is needed, add only the crucial boundary.

### F13 Same-Shape Sensory Description (C)

- Signal: different characters and scenes all using the same visual-auditory-tactile trio.
- Boundary: the work deliberately uses a recurring motif.
- Fix: write only what the current viewpoint truly notices and that advances atmosphere or action.

### F14 Everyone Same Voice (S)

- Signal: different characters, departments, or authors all using equally complete, polite, abstract syntax and lexicon.
- Boundary: unified institutional documents, or one narrator retelling everything.
- Fix: restore lexicon range, sentence length, directness, and information preference from existing setup; never invent catchphrases from nothing.

### F15 Emotion Explanation Over Events (C)

- Signal: one action followed by multiple "这不是……而是……" psychological expositions while events stall.
- Boundary: introspective literature or counseling records genuinely aimed at experience analysis.
- Fix: keep the one feeling or action closest to the viewpoint; let subsequent events carry the change.

### F16 Reader Hand-Holding (C)

- Signal: "你会发现、我们不妨想象、让我们一步步来看" constantly arranging the reader's cognition.
- Boundary: tutorials, classrooms, and interactive speeches need explicit guidance.
- Fix: show evidence or steps directly; keep guidance only where the cognitive leap is genuinely hard.

### F17 Compare-Explain-Uplift Relay (S)

- Signal: one simple fact first metaphorized with "仿佛/宛如", then translated with "这意味着", finally uplifted with "真正/不仅是"; three layers without three distinct propositions.
- Boundary: the metaphor provides concrete understanding, the explanation adds necessary limits, and the conclusion truly follows.
- Fix: keep one or two layers by new information; delete synonymous layers; never write a prettier summary to fill the gap.

### F18 Synonym-Modifier Roulette (C)

- Signal: to avoid literal repetition, one semantic function rotates across near-synonym modifier sets — degree adverbs, gaze descriptions, liquid emotions, abstract evaluations — diverse on the surface, isomorphic in function.
- Boundary: each word corresponds to an explainable difference in scale, stage, agent, or observer.
- Fix: label each modifier's function and merge duplicates; where difference is needed, write action, scale, or consequence — never mine a thesaurus to fill holes.

## G. Format and Delivery Reflexes

### G01 Heading Overdensity (C)

- Signal: a Markdown heading every one or two paragraphs; headings longer than content or deeper than the information structure.
- Boundary: searchable manuals, technical documents, long reports.
- Fix: merge short sections; headings mark only real topic turns.

### G02 Bold-Label Lists (C)

- Signal: every item starting with "**关键词：**", like a default answer template.
- Boundary: fast scanning, term definitions, checklists.
- Fix: return narrative content to sentences; keep labels only where locating help is real.

### G03 List Reflex (C)

- Signal: stories, commentary, private expression, or interdependent argument force-split into bullets.
- Boundary: steps, options, parameters, exclusive points, action items.
- Fix: restore interdependent content to paragraphs; keep lists for genuinely parallel items.

### G04 Table Reflex (C)

- Signal: two or three ordinary descriptions converted into a table, or long narrative crammed into cells.
- Boundary: exact field comparison, multi-option comparison, parameter matrices.
- Fix: simple content uses sentences or short lists; tables only for horizontally comparable fields.

### G05 Emoji Navigation (C)

- Signal: light bulbs, rockets, checkmarks, pins replacing structure, mismatching brand or register.
- Boundary: social platforms, children's content, or user-specified visual style.
- Fix: delete decoration; when navigation is needed, use headings, whitespace, or clear labels.

### G06 Markdown Source Leakage (H)

- Signal: unclosed code fences, bare asterisks, broken links, rendering directives, or quote markers appearing in the target format.
- Boundary: the body is literally about Markdown syntax.
- Fix: repair or convert to the target format; never keep source residue as style.

### G07 Unfilled Slot Residue (H)

- Signal: `[姓名]`, `{{date}}`, `<insert example>`, `TBD` and other unfilled slots in finished prose.
- Boundary: the user asked for a reusable template.
- Fix: in template tasks declare fields uniformly; in finished prose fill only with sources, otherwise report the gap — never guess values.

### G08 Pseudo-Quotes or Pseudo-Sources (H)

- Signal: quoted content, authors, papers, links, footnotes, or precise statistics not present in the input written as fact.
- Boundary: the user authorized retrieval and it was verified, or explicitly wants in-fiction citations.
- Fix: delete, mark as to-verify, or replace with verified sources; never mask the gap with polish.

### G09 Heading Grammar Copying (C)

- Signal: every heading normalized to "X：Y 的 Z" although content relations differ.
- Boundary: course series, product specs, and brand columns needing a naming system.
- Fix: use the shortest accurate topic; never sacrifice distinction for tidiness.

### G10 Unnecessary Code Blocks (C)

- Signal: ordinary text, a single path, or one command wrapped in large code fences, breaking the read.
- Boundary: content needing copying, whitespace preservation, render avoidance, or multi-line code display.
- Fix: single identifiers use inline code; only executable or verbatim-copy content gets code blocks.

### G11 Templated Risk Boxes (C)

- Signal: every low-risk suggestion trailed by "注意事项、潜在风险、最佳实践" boxes repeating each other.
- Boundary: safety operations, production changes, and medical/legal/financial content genuinely need risk layering.
- Fix: place risks next to the relevant action; delete generic boxes unrelated to the task.

### G12 Delivery Process in Body (H)

- Signal: file paths, processing status, model self-checks, token budgets — delivery-note material — entering the work itself.
- Boundary: meta-fiction, technical reports, or task logs genuinely discussing this information.
- Fix: output body and delivery notes in separate layers.

## Combination Rules

A single C-level pattern is usually insufficient. Prioritize these combinations:

- any hard residue in family A + format reflexes in family G;
- B03/B04/B08 + D07/D08: section and sentence level both repeating;
- B11/B12 + C05/C06: abstract uplift without agents or evidence;
- D01/D02 + E09/E13: antithesis being used to manufacture golden lines;
- D18/B17 + F12/F17: one proposition echoed through metaphor, explanation, and uplift;
- E01/E02/E03 + C09/C16: jargon replacing beneficiaries, mechanisms, or plans;
- E17/E18/E19/E20 + F18: ornamental clusters, vague feelings, micro-adverbs, and non-volition labels relaying as a synonym roulette;
- F06/F07/F08 all elevated: rhythm governed by template;
- G01/G02/G03 co-occurring in non-manual text: strong format reflex.

## False-Positive Recheck

Before editing, recheck at least once:

1. Is this a fixed term or regulatory wording of the domain?
2. Does the structure carry real sequence, comparison, responsibility, or lookup function?
3. Does it belong to a voice the character, author, or brand already has?
4. Would deletion lose risk limits, logical relations, or emotional rhythm?
5. Is the fix merely swapping in another set of stock phrases?
6. Is the hit a user's personal hard ban? If so, can it be restructured without touching facts, negation, and verbatim-protected items?

Any yes on 1–4 shrinks the edit or preserves the function; yes on 5 withdraws the swap and repairs structure instead; yes on 6 restructures by the personal rule rather than keeping the original frame. When a personal rule conflicts with a verbatim lock or other invariant, keep the content and record `protected_verbatim` or `blocked_by_invariant`.
