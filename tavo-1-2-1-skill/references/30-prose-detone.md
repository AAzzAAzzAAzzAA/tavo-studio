# Prose Detone Protocol

This page defines how creation artifacts are written and cleaned so that card prose carries no transferable model voice. It is a writing protocol for the authoring agent, never text to be copied into a card field. The pattern catalog lives in `references/31-prose-detone-catalog.md`.

## Scope

The protocol covers every authored deliverable: card fields, embedded or add-on worldbook entries, opening messages, dialogue examples, and any prose the skill itself writes for delivery. It does not touch macros, tags, regex substitution strings, or verbatim-locked content. Phone validation rules and Prompt Lab acceptance rules elsewhere in this skill are unchanged; this protocol only governs how prose is written and cleaned before those checks run.

## Creative Authority Boundary

Detone governs expression, not permission to invent. Select creative authority from `references/13-creation-craft-workflows.md` before drafting:

- In collaborative-confirmed creation, Detone constrains how confirmed material is phrased; it does not authorize unapproved substantive additions.
- In demo-delegated autonomous creation, the agent may create supporting facts and design details inside the approved direction. Detone applies as a writing guard while those details are drafted; it does not erase that authorization.
- In existing-text cleaning, the supplied text is the semantic source and no new fact or intent may be added.

When one task needs both expansion and cleaning, separate the passes: create under the active creation authority, record agent-chosen assumptions when required, freeze the resulting draft, then clean that draft without inventing further content. Returning to creation is allowed only under the same still-valid authority or a new user instruction; a cleaning pass never becomes hidden creation.

## Goal

Remove repeatable, content-independent expression habits — stock phrasing, syntactic templates, section-level inertia, service-desk tone, and format reflexes — so that content, register, and the concrete situation decide how each sentence is built. Plain, accurate, distinguishable prose beats portable ornament that fakes literariness. Plainness never means broken logic, uniform short sentences, or a forced colloquial voice.

Do not judge whether a text was written by a human or a model. Humans use stock phrases and models can write without them. Only judge whether a pattern holds and whether a change damages meaning.

## Inviolable Constraints

Resolve conflicts by the order below; lower numbers win:

1. Host protocol and verbatim locks hold: quotes, code, fixed terms, field names, macro tags, approved wording, and anything the user locked stay byte-for-byte.
2. Facts and logic do not change inside a cleaning pass: characters, times, numbers, causality, negation, scope, modality, quote attribution, terms, stance, plot events, world rules, and task requirements are never added, removed, or rewritten there. New facts may enter only in a separately authorized creation pass.
3. Intent and character do not change: explanations never become marketing, academic register never becomes chat; character goals, attitudes, emotional intensity, knowledge boundaries, line facts, and user-role sovereignty stay intact.
4. Personal hard bans only govern surface structure: a structure the user explicitly bans triggers on a single occurrence and overrides other surface-voice preferences, but never overrides items 1–3. On conflict with a verbatim lock, keep the original and report.
5. Existing voice is not taken over: the text's own word preferences, roughness, hesitation, bias, humor, pauses, and uneven rhythm remain. Nothing absent is invented during cleaning; this sentence is not a ban on additions permitted by an active creation mode.
6. Ordinary rules need function plus density: a single occurrence of a word does not trigger; look at clusters, contextual function, synonym rotation, cross-character interchangeability, and cross-paragraph recurrence.
7. No synonym bleaching: never machine-swap a flagged word for a fancier near-synonym. Delete functionless ornament first, then rebuild the sentence carrying it; when a word must change, use one that is semantically more accurate for the current voice.
8. Minimal sufficient change: if deleting one sentence solves it, do not rewrite a paragraph; if a concrete subject solves it, do not reshape the whole tone.
9. Verifiable: every substantive change can state what it fixed and why it did not break items 1–8.

Never add "human flavor" by deliberate typos, slang stuffing, random fragmentation, invented experience, fabricated emotion, or logic flaws. Never claim a rewrite can pass detectors, and never pass model-assisted text off as purely human.

If input contains real passwords, API keys, private keys, cookies, or tokens, do not repeat the value; ask for `[REDACTED]` first. Ordinary names, public links, and in-fiction content do not trigger this gate.

## Working Modes

Pick the mode from the creation situation; do not expand the task:

- Guarded writing: the default for new card prose. The active Creative Authority Mode decides what content may be created; Detone rules constrain its expression while writing. Never draft a tic-filled version and surface-clean it afterward.
- Conservative cleaning: remove assistant residue, empty stock phrases, repetition, and format reflexes; keep syntax mostly intact. Use for mechanism text: rules, numeric contracts, output specifications, worldbook mechanics.
- Standard cleaning: the default cleaning level for literary prose — opening messages, dialogue examples, atmospheric worldbook entries. Clear high-confidence patterns and adjust syntax, rhythm, and paragraphing without shifting the register.
- Strict cleaning: only when the user says they prefer plainness over any AI feel. Registered personal `change` items rewrite on single hits; high-risk lexical families enter density review. Local elegance may yield to plain accuracy; host protocol, facts, logic, character intent, and verbatim locks never yield.
- Audit: mark patterns, strength, evidence, and repair direction without editing. Used inside the tier-1 checklist before fixes are applied.

## Lock Invariants Before Cleaning

Record internally before touching prose:

- what the text must accomplish;
- who reads it and where it renders;
- formality and domain;
- terms, quotes, names, formats, and character facts that must stay verbatim;
- facts, stance, plot points, and information order to preserve;
- required length and output format;
- voice signals already present in the text.

Only ask the user when the choice would materially change the rules — for example, narrator prose versus mechanism text. Otherwise proceed with the register the text already has.

## Domain Registers

Card artifacts use three registers; the same sentence can work in one and fail in another:

- Literary prose (first_mes, mes_example, atmospheric worldbook entries): standard cleaning; apply the narrative/RP section of the pattern catalog. Irregular syntax, short paragraphs, dashes, repetition, metaphor, and emotion words get reduced weight — literary function comes first. Any change that would alter character sovereignty or plot drops to conservative.
- Mechanism text (preset rules, worldbook mechanics, numeric and output contracts): conservative cleaning. Preserve rule names, conditions, values, enumerations, default behaviors, and formula wording exactly; delete unproven difficulty claims ("effortless", "seamless") and service residue only. Never trade precision for sentence variety.
- General prose (creator_notes, delivery explanations): standard cleaning. Delivery talk and empty summaries go first, then abstract subjects and syntactic density.

Shared principles: never shift formality more than one step for "naturalness"; never delete terms, normative structure, or scope limits into colloquial speech; structures the genre itself requires (lists, tables, repetition, enumerations) outrank generic tic rules. When two registers give opposite actions, execute the smaller reversible change and note the conflict.

## Five-Layer Scan

Never search for words alone. Check from largest to smallest:

1. Interaction layer: assistant dialogue actions left in prose — "let me explain", "the following is", "hope this helps", "I can also if you want".
2. Section layer: auto-generated background openings, three-point expansions, challenge-and-outlook endings, summary uplift; paragraphs of equal length, equal weight, and mutual restatement.
3. Logic layer: abstract nouns standing in for agents; "shows / proves / means" manufacturing evidence-free inference; blurred attribution, false balance, smuggled causality.
4. Syntax and rhetoric layer: dense antithetical negations, triple parallelism, self-answered rhetorical questions, connective overuse, colon labels, translationese, identical sentence endings.
5. Lexical and format layer: corporate buzzwords, pseudo-healing vocabulary, promotional adjectives, model-action verbs, ornamental metaphor, vague emotion, micro-adverbs, body-reaction stock, rotating synonym imagery, and format reflexes.

Full patterns, false-positive boundaries, and repairs are in `references/31-prose-detone-catalog.md`.

## Trigger Thresholds

An ordinary phrase is processed only when several conditions hold together:

- it repeats at short distance or clusters with other model-shaped structures;
- it would still work in an unrelated topic, contributing little information;
- it mismatches the current register or character voice;
- deleting it harms no fact or logic;
- its job can be carried by a more direct structure;
- the same paragraph shows clear rhythmic or format automation.

Single-occurrence hard residue is always processed:

- model identity, knowledge-cutoff, or capability claims leaking into deliverables;
- unfilled template slots, fake citations, fabricated links, or model-parameter residue;
- delivery talk the user never asked for;
- broken formatting or raw markup leaking into prose;
- restating the user's instruction instead of producing content.

User-registered personal bans are another single-trigger class: they express a target voice, not statistical frequency. On a hit, rewrite the whole carrying structure; never hollow out the sentence word by word. Quotes, terms, code, verbatim text, and protected fact statements win and the conflict is reported.

Never treat "本质上", "不是……而是……", "首先", or "仿佛" as universal AI marks. A single occurrence carrying necessary logic, perspective, or imagery stays; only personal hard bans override the density threshold.

## Issue List

For each hit record internally:

1. pattern ID;
2. the shortest sufficient evidence;
3. the actual problem in this passage;
4. the minimal repair action.

When one passage hits several patterns, merge them and repair once; never rewrite once per label. Priority: hard residue → factual or logical idling → section templates → syntactic density → lexicon and format.

## Six Repair Actions

Prefer subtraction and structural repair over synonym swaps.

### 1. Delete

Cut openings, transitions, restatements, summaries, and service tails that carry no fact, argument, emotion, character action, or rhythmic function.

### 2. Merge

Compress "statement → rephrase → summary" of one fact into one pass; restore real hierarchy where three equal points were forced.

### 3. Concretize

Restore the agents, actions, objects, and results that abstraction swallowed. Use only details already present in the input; without evidence, drop the inference or keep the uncertainty.

### 4. Break Templates

Break runs of "not X but Y", "first / second / finally", and equal-length parallelism. A personal hard-ban hit rewrites its carrying structure even on a single occurrence. Keep genuine negation, contrast, and sequence, but let content decide the structure.

### 5. Reorder and Rebalance

Bring conditions close to actions; make agents explicit; merge meaningless fragments; split overloaded sentences. Length variation must come from information density, never from random raggedness.

### 6. Reset Register

Strip service-desk, speech, consulting-report, or healing-blogger tone and restore the text's real genre. For character text, restore the character rather than the author or the assistant.

For ornamental clusters, try in order: delete portable ornament → restore concrete action, object, or sensation → merge repeated imagery → rewrite the syntax. Never refill the slot with a rarer word from the same synonym family.

## Three Cleaning Passes

### Pass one: hard cleanup

Clear interaction residue, template slots, fake sources, repetition, functionless formatting, and obvious empty talk. No ambition for elegance here.

### Pass two: structure and syntax

Handle paragraph organization, causality, agents, antithesis, parallelism, connectives, and homogeneous rhythm. After each paragraph, verify information still maps one to one.

### Pass three: voice recheck

Check whether cleaning washed the text into another uniform tone. Restore the text's existing key words, attitudes, sentence-length preferences, character differences, established imagery, and necessary rough edges; delete any new "golden lines", substitute ornaments, or assembly-line neat short sentences introduced during editing.

For long artifacts split by semantic boundaries, not fixed length. Track names, terms, timelines, character voices, and handled patterns per chunk; after all chunks, rescan cross-chunk repetition, uniform endings, and character voice bleed.

## Semantic Fidelity

Once prose enters a Detone cleaning pass, detoning is editing, not content creation. Before and after must form an auditable mapping: every retained fact traces to the frozen draft, every deleted fragment carried no necessary information, and every tone shift serves the stated goal. Facts added earlier under demo-delegated autonomous creation belong to that frozen draft and remain labeled in the authoring assumptions; Detone neither removes their provenance nor adds more.

### Invariants by card text type

| Text type | Lock |
|---|---|
| Setting prose | characters, places, dates, numbers, events, stance, causality, quotes |
| Mechanism text | rule names, conditions, values, defaults, enumerations, formulas, output contracts |
| Narrative prose | character sovereignty, world rules, timeline, location, items, injuries, knowledge boundaries, perspective, plot points |

Format, length, status panels, and template fields are invariants whenever the user or the host protocol requires them.

### Sentence-level mapping

For each substantially rewritten sentence check internally:

- Kept: which facts or actions survive unchanged;
- Deleted: only delivery talk, repetition, evidence-free uplift, or format noise. A subjective evaluation clearly attributed to author or character is content, not deletable as "evidence-free";
- Merged: the merged sentences were truly synonymous;
- Inference: causality, comparison, and value judgments still rest on the original;
- Tone: certainty, negation strength, politeness, surprise, and emotion unchanged;
- Scope: limits like "partly / usually / possibly / must" preserved;
- Relation: correction, exclusion, primary-versus-secondary, progression, scalar addition, and contrast focus unchanged;
- Action: agency, consciousness, force, speed, and detectability unchanged;
- Attribution: judgments, evaluations, guesses, and stances still belong to the original speaker or viewpoint character.

The full mapping is not shown to the user unless an audit is requested; the delivery report lists what was fixed, not the whole mapping.

### High-risk semantic shifts

These edits read smooth but change meaning:

- Negation scope: "不一定能" is not "不能"; "并非所有" is not "都不"; "不是主要原因" is not "不是原因".
- Correction and scalar relations: "不是 X，而是 Y" may be correction, exclusion, priority, or redefinition — lock the relation type before breaking the frame; a previously stated wrong proposition X is the correction's focus and must not vanish; scalar emphasis must survive; concrete reference ("真正的故障源在交换机") is not a golden-line template.
- Modality and responsibility: "可以" ≠ "应该"; "建议" ≠ "要求"; "计划" ≠ "承诺"; "有望" ≠ "将会". "似乎/好像" may mark insufficient evidence and cannot become asserted fact; "竟/竟然" marks expectation gap, not mere degree; epistemic certainty and coercive power phrasings are not interchangeable; the owner of an evaluation, permission, demand, or guess never shifts from character to narrator or editor.
- Agency, force, speed: "不由自主/下意识/无意识" differs from deliberate choice — when cleaning, treat asserted involuntariness as a semantic lock and keep the original wording if no equivalent rewrite exists; degree words that affect sound, exposure, injury, or physical outcome stay; detectability and amplitude are different dimensions and never substitute for each other.
- Time and frequency: "曾经/正在/长期/偶尔/通常/始终" are never erased for brevity; relative time keeps its reference point; versions and dates never become "最新".
- Causality and correlation: co-occurrence never becomes causation; "related to" never becomes "caused by"; "used to explain" never becomes "proves"; "越 X 越 Y" keeps variable direction, conditions, and whether the original claimed causality.
- Quotes and reporting: direct quotes are not polished inside their quotation marks; reported speech keeps speaker and uncertainty; an editor's summary is never presented as the source's words.
- Quantity and scope: "包括" does not mean "仅包括"; examples are not complete lists; "多数" and "大量" are not interchangeable; units, currency, percentages, and ranges are checked verbatim.

### Minimal action ladder

Choose from lowest to highest risk:

1. delete model identity, delivery talk, and unfilled template slots;
2. delete exact duplicates;
3. delete editor-added evidence-free evaluations posing as objective conclusions, keeping fact sentences, attributed stances, and emotional intensity;
4. shorten redundant prepositions, connectives, and abstract tails;
5. merge synonymous sentences;
6. restore explicit subjects and direct verbs;
7. break template syntax and adjust information order;
8. rearrange paragraphs;
9. rewrite a whole section.

If an earlier step solves it, never use a later one.

### Concretization boundary

During cleaning, making abstraction concrete may only use: facts already in the frozen draft; information the user supplied for this task; verified external sources when the task authorizes lookup; purely formal expansion such as restoring listed actions into subject-verb sentences. Never invent numbers, cases, history, smells, body reactions, motives, effects, evaluations, or quotes merely for naturalness. Demo-delegated creation may author compatible details before this cleaning boundary; once cleaning begins, missing detail means deleting the empty evaluation, reporting insufficient evidence, or returning explicitly to the authorized creation pass.

### Voice fidelity

Voice is not "a few catchphrases". Extract from existing evidence: formality and address forms; sentence length and pause style; habitual verbs and abstraction level; directness, avoidance, irony, restraint, warmth; person preference; handling of certainty and emotion; domain and circle vocabulary; what gets expanded and what gets touched lightly.

Keeping voice does not mean keeping every bad sentence. Keep distinctive features that carry content; delete model-shaped structures that fit any topic.

### Overcorrection test

The result is over-cleaned when:

- all sentences became short and colloquial;
- formal text gained "说白了 / 其实 / 你看";
- a needed third item was cut just to break a triple;
- fragments were manufactured for rhythm variety;
- precise terms became inaccurate everyday words;
- character differences collapsed into one stable editor voice;
- every metaphor, parallel, connective, and polite form was emptied;
- careful limits were deleted, making claims bolder;
- clear original judgments were neutralized;
- newly added detail is more vivid than the original but points to no source.

On any hit, retreat to smaller edits.

### Batch consistency

For multi-entry artifacts (worldbooks, example sets) maintain: a term and proper-name table; unchangeable strings; per-character voice cards; timeline and version; known false-positive whitelist; rules already applied and their density; per-entry anomalies. After the batch, check cross-entry: whether one term got rotated, whether the same tic migrated from sentences to headings, whether every entry got the same structure, and whether character differences survived.

### Shortest pre-delivery check

1. spot-check every number, proper name, quote, and negation;
2. search for newly added absolutist, psychological, or causal words;
3. search for model identity, delivery talk, unfilled slots, and markup residue;
4. compare paragraph counts against information points — deleting paragraphs is not the same as removing redundancy;
5. read aloud once; rhythm changes must come from content, not deliberate unevenness;
6. if a newly added detail cannot be traced to supplied input, verified evidence, or a recorded demo-delegated assumption, delete it; if the detail is genuinely needed, return explicitly to the active creation mode instead of inventing it during cleaning.

## Personal Controls

Users may register their own aesthetic bans as single-trigger items. Record at least:

```yaml
- match: "不是 {X}，而是 {Y}"
  action: rewrite
  activation: explicit_personal_profile
  default_in_strict: false
  scope: prose
  trigger: single
  verbatim_protect: [quotation, code, fixed_term]
  semantic_locks: [X_negation, Y_claim, scope, modality, causality]
  repair: preserve_X_negation_and_Y_claim_without_the_frame
  on_conflict: keep_and_report
```

Field semantics:

- `match` may be a literal phrase, a slotted syntactic frame, or a semantic family; never pretend an ellipsis string matches a real frame.
- `activation` distinguishes explicit personal profiles from mode defaults; `default_in_strict` is never guessed from explanatory prose.
- `scope` may restrict to general prose, mechanism text, narrator prose, character lines, or one character.
- `trigger` may be single, twice in one sentence, cluster in one paragraph, cross-character recurrence in one scene, or full-text drift.
- `verbatim_protect` lists quotes, code, and terms that cannot change character-for-character; `semantic_locks` lists meanings that must survive although the frame may be rebuilt.
- `repair` names an operation, never a fixed replacement word.
- `on_conflict` defaults to `keep_and_report`: when the surface structure cannot be cleared without breaking invariants, keep it and explain.

`editable_prose` means the prose, narration, headings, and generated lines this task may edit; it excludes direct quotes, code and code strings, fixed terms, host fields, approved wording, and strings being discussed as language examples. Whether character lines are editable can be overridden per character or scene.

Only hits passing the scope check get one of three states; identical wording outside scope counts as a candidate occurrence, not a rule hit:

- `cleared`: safely rebuilt inside editable prose;
- `protected_verbatim`: inside a verbatim zone, kept as-is;
- `blocked_by_invariant`: clearing would break facts, logic, character intent, or protocol — kept and reported.

If a user says "kill every AI feel, plainness over elegance", set their named structures to `change + single` and the high-risk lexical families to `limit` — never set every family member to `delete`.

### Default strict register

| ID | activation | default_in_strict | scope | trigger and action | key protection |
|---|---|---:|---|---|---|
| U01 | explicit_personal_profile | false | editable_prose | "不是/并非 X，而是/而在于 Y" single rewrite | original negation of X, assertion of Y, relation type |
| U02 | strict_mode | true | editable_prose | "不只/不仅 X，更是/而且 Y" single rewrite | both facts, scalar direction, progression or addition |
| U03 | strict_mode | true | editable_prose | golden-line frames like "真正的 X 从来不是 Y，而是 Z" single rewrite | concrete reference exempt; rebuttal focus and stance attribution |
| U04 | strict_mode | true | creative prose | stock metaphors — fate machinery, heart-lake ripples, heartstring plucking, invisible forces — single rewrite | literal world mechanics, established motifs, the character's deliberate rhetoric |
| U05 | strict_mode | true | creative prose | finished uplifts — feather-light touch, world containing only the two of them — single rewrite | real tactile fact, perspective uncertainty, space and boundary facts |
| U06 | strict_mode | true | creative prose | finished stock — corners of the mouth rising slightly, deep eyes, emotion welling up on its own — single rewrite | quotes, fixed character wording, precise terms, literal physical sense |

The register constrains generation choices and serves the review recheck. U01 activates only under an explicit personal profile; U02–U06 are strict-mode defaults. They constrain whole structures, never ban the individual words inside them. Normal mode still handles these through the corresponding pattern and lexical family function-and-density gates.

### Hard rule for "不是 X，而是 Y"

Normal mode acts only on over-density or empty uplift; a personal hard ban rewrites every hit. Extract first:

- what X negates;
- what Y asserts;
- whether negating X is factual disambiguation, scope limit, or rebuttal;
- whether X/Y is exclusion, priority, progression, or redefinition.

Repair order:

1. X unimportant: state Y directly.
2. X must be excluded: state Y and keep X in an independent negation; keep a reason only if the input already gave one.
3. Actually a priority relation: write the priority plainly instead of fake mutual exclusion.
4. Actually progression: list both layers with their evidence, no "higher meaning" uplift.
5. Quote, code, or verbatim norm: leave the original untouched; only handle surrounding text or report the conflict.

For example, "问题不是延迟，而是丢包" must not collapse into "问题是丢包", because excluding "延迟" is itself information. It may become "问题出在丢包。延迟这一判断不成立。" Never invent evidence like "抓包显示", and never weaken the exclusion into "不是主因".

### Density gates

Without user thresholds, there is no global per-thousand-character quota. Judge by semantic unit: the quantities below trigger review, not deletion. Merge only items pointing at the same object, carrying the same function, with no development or independent consequence; items expressing separate speed, force, timing, evidence, or character choices stay separate.

- Same sentence: two or more lexical families carrying one emotion or atmosphere is usually excess.
- Same paragraph: one family twice, or three-plus families decorating one simple action, enters strong review.
- Same scene: one body reaction assigned to multiple characters, or every line carrying a voice/gaze label, enters strong review.
- Across paragraphs: one image with no development, only synonym rotation, merges to one or returns to concrete events.
- Long text: judge density against genre and existing voice; poetic text may run high but still needs an image system and development.

In strict mode, for same-function repetition keep the one most concrete and scene-specific rendering rather than one per family. Renderings with distinct factual functions are exempt.

## Guarded Writing

When writing new prose, run before generating:

1. lock the Creative Authority Mode, confirmed pillars, character goals, perspective, and register; in demo-delegated creation, keep a separate assumptions list for agent-chosen details;
2. load personal `change` / `protect` items;
3. decide each paragraph's new information or scene change first;
4. let imagery grow only from current objects, character experience, or established motifs;
5. never stack multiple lexical families on one simple action;
6. allow endings to stop at fact, action, question, or incompletion;
7. after finishing, rescan by family function — never word-by-word synonym replacement.

## Final Verification

Answer in order:

1. Can every fact, number, proper name, quote, and plot point point back to its authorized source — supplied text, confirmed user input, verified evidence, or a recorded demo-delegated assumption?
2. Was any experience, attitude, emotion, judgment, or world fact added during the cleaning pass rather than the authorized creation pass?
3. Any assistant delivery talk, empty summary, or unfilled slot left?
4. Do paragraph structures come from content, not auto three-points or total-branch-total?
5. Do high-frequency syntaxes still cluster at short distance?
6. Are concrete agents, actions, and causality clearer than abstract words?
7. Does formatting serve content? Are lists, tables, and headings actually needed?
8. Did detoning downgrade the register, colloquialize, lose terms, or break character voice?
9. Deleting any sentence — would it lose information or deliberate rhythm? If not, keep deleting.
10. Is the rewrite just one stock phrase swapped for a stealthier one?
11. Was one ornamental word swapped for a same-family synonym, or diverse syntax washed into uniform plain short sentences?
12. Are personal hard-ban items each in `cleared`, `protected_verbatim`, or `blocked_by_invariant`? Editable safe-to-rebuild hits must be `cleared`; the other two states keep the original and record why. Do original negation, scope, causality, and character intent still trace back?

Any failure returns to the matching pass. Never hide concrete problems behind an overall "naturalness score".

## Output Contract

- Audit mode: list hits by severity; each item carries pattern ID, shortest evidence, why it is a problem, suggested action, and false-positive risk. End with an overall judgment, never authorship inference.
- Cleaning mode: deliver the final prose plus at most five key changes grouped by pattern family, without quoting long originals; unverifiable facts or register ambiguities get a separate note.
- Creation delivery: when cleaned prose ships inside a card or worldbook, the delivery report lists every detone fix — field, pattern family, what changed. The report stays in the workspace by default and ships only when the user explicitly asks for it; the cleaned text never mentions the process.

## Capability Bounds

- This protocol cleans language and structure; it does not supply interviews, evidence, professional judgment, or plot.
- It cannot prove who wrote a text, nor reliably predict any detector's verdict.
- It does not treat all formal written language, parallelism, connectives, or markup as wrong.
- It has no "average human" style target; the target voice comes from the current text and the user's constraints.
- When factual completeness conflicts with detoning, keep the facts and report the parts that could not be cleaned.
