# Creation Craft Workflows

This reference is for writing better cards, worldbooks, regexes, and roleplay packages. Its craft advice is `creative-guidance`; product contracts remain in the feature references.

## Scope Label

Use these ideas as:

- `creative-guidance` when improving writing quality or workflow;
- `supported` only when the relevant feature reference defines the required product behavior;
- `not-established` when the advice touches import preservation, TavoJS effects, Advanced Rendering, plugins, or app persistence without a matching current result.

## From-Zero Card Ideation

When the user starts with a vague card idea, do not jump straight into JSON. First find the role's "引力核心": the specific thing that makes the user want to keep talking.

Common attraction cores:

- personality tension;
- relationship dynamic;
- atmosphere;
- gameplay loop;
- mystery or conflict;
- caretaking, rivalry, danger, apprenticeship, intimacy, betrayal, or recovery arc.

When missing choices would materially change the result, run the interview in `references/29-creation-intake-interview.md`. Batch independent questions together and defer dependent questions until the earlier answers are known. Challenge contradictions instead of politely preserving everything; proceed once the remaining ambiguity can be safely assumed or the user delegates it.

## Creative Authority Modes

Set one authority mode before substantive field expansion. This decides what the agent may invent; the Detone protocol decides how authorized prose is written and cleaned. Asset type does not determine authority, and Detone must never silently expand or shrink it.

1. **Collaborative-confirmed creation.** Use when the user is shaping the artifact through questions and answers. Confirmed answers, supplied source material, and explicit locks are the content boundary. The agent may propose new substantive facts or design choices, but must wait for acceptance before adding them. Routine phrasing and formal glue may be supplied to express confirmed choices; new character history, motives, relationships, world rules, mechanics, or other material details may not be smuggled in as glue.
2. **Demo-delegated autonomous creation.** Use when the agent presents a compact demo, candidate, or pitch and the user approves that direction while explicitly delegating continuation — for example, “就按这个继续做”, “剩下你定”, or “直接做出来”. The agent may then add supporting facts and design details, choose among compatible options, and run multiple internal authoring rounds without seeking approval for every addition. The approved pitch, confirmed identity, relationship premise, experience direction, hard boundaries, required format, and delivery scope remain locked. Anything that overturns those pillars or materially expands the deliverable requires a new user decision. Agent-chosen details are recorded as assumptions, never rewritten as user-confirmed facts.
3. **Existing-text cleaning.** Use when the task is only to detone, polish, or conservatively repair existing prose. The supplied text and approved correction scope are the semantic source. Cleaning may not add facts, change meaning, or turn missing content into invented content. If the user also wants expansion, perform a separately authorized creation pass under mode 1 or 2, freeze that draft, and then clean it.

Authority changes only through a clear user instruction. A proposal is not authorization; approving a demo plus delegating continuation is. When scope is ambiguous, keep the narrower mode and offer the expansion as a suggestion.

## Skeleton-First Drafting

Draft in two stages; do not expand every field before the character holds together:

1. Character skeleton: anchor one concrete person on four points — how they spend ordinary days, why they speak the way they do, what makes their guarded self slip, and what kind of situation knocks them off balance. If the intake is thin, infer the smallest concrete version only in demo-delegated autonomous creation; in collaborative-confirmed creation, offer that concrete version for approval instead of silently adding it.
2. Full field expansion: write every field around that same person. The result should feel like someone living in the scenario, not a manual describing a character concept.

Empty talk is not allowed: treat phrases such as “人很立体”, “心里有伤”, “过往很精彩”, and “自带反差” as empty abstractions until they are replaced by a concrete behavior, scene, habit, decision, or relationship-specific reaction.

Field content should describe things that could actually happen to this person in daily life, rather than author praise or narrator evaluation.

## Field Placement

Use field lifecycle thinking:

- `description`: stable identity, background, body/visual traits, permanent behavior boundaries, world-linked facts.
- `personality`: compressed temperament and reaction patterns.
- `scenario`: current relationship/situation, location, immediate tension, starting condition.
- `first_mes`: style anchor; teaches pacing, action density, sentence shape, and opening energy.
- `mes_example`: voice and interaction examples, not a lore encyclopedia.
- `creator_notes`: metadata and author notes, not required prompt facts.
- persona/user identity: who `{{user}}` is, what they know, why they are here, and how the character sees them.
- worldbook: conditional background facts, not everyday style control.
- preset: system behavior and output rules, not a replacement for character identity.

## Living Character Depth

Avoid service-NPC flattening. A role should have motives, pressure points, and relationship-specific behavior.

Useful depth axes:

- fear: what the role avoids admitting or facing;
- old wound: what shaped their defense style;
- language habit: how they dodge, confess, joke, argue, or go silent;
- hidden side: what appears only under stress or trust;
- contradiction: the tension between public mask and private need;
- agency: what the character wants even when it conflicts with the user.

Pick the 2-3 axes that reinforce the attraction core. Do not fill every possible trauma slot by default.

## Worldbook Craft

Use worldbooks for stable facts and conditional context:

- places, factions, rules, secrets, history, NPCs, objects, systems;
- trigger terms and aliases that the user/model will naturally mention;
- compact `content` that stands alone if inserted without title/comment;
- layered reveal: public knowledge, private truth, later-discovered facts;
- patching strategy: add new entries when the story grows instead of overloading one master entry.

Avoid:

- dumping the whole card into every entry;
- using worldbook as a personality style prompt;
- hiding essential character facts only in rare triggers;
- vague triggers that fire constantly.

## Regex Craft

Use regex for text transformation:

- clean model artifacts;
- expand user shorthand;
- format status bars;
- normalize tags/code blocks;
- extract or display values.

Do not treat regex as a state store or JavaScript runner. If regex outputs macros or HTML, prove the downstream macro/rendering chain separately.

For risky regexes, keep fixtures:

- input text;
- matched groups;
- replacement output;
- expected side effects;
- destructive behavior notes.

## Gameplay Mode Planning

Use these nine planning modes as creative templates, not Tavo requirements:

- pure character;
- wuxia growth;
- xianxia growth;
- fantasy growth;
- ARPG growth;
- story RPG;
- survival simulation;
- farming/management;
- relationship/affection route.

Default to pure character unless the user asks for systems. Add worldbooks, presets, macros, regexes, Advanced Rendering, or plugins only when they solve a real gameplay problem.

## World Card Authoring

A world card lets the user play against a setting or simulation rather than one central person: text adventures, survival or management simulations, and scenario-driven story runs. The following is `creative-guidance`, not a guarantee about every import channel.

1. Field allocation. Keep the stable world premise and a few core rules in prompt-bearing fields that the target channel actually preserves. In CC-style packages, `system_prompt` and `post_history_instructions` are common homes for engine rules and output conventions, but verify schema/readback before relying on them in Tavo. A thin `description` and empty `personality` or `scenario` can be a valid design only when the selected import path accepts and preserves that shape.
2. Narrator stance. State what the narrator records and what it never decides for the player. In particular, do not choose, speak, or silently steer on the user's behalf unless that is an explicit mechanic.
3. Skeleton. Define both world-action rules and response format. World-action rules cover event pacing, faction reactions, triggers, and consequences; response format defines what one model reply looks like. Without the first, the world only reacts. Without the second, presentation drifts.
4. Complexity tier. Light means prose narration. Medium means text-defined structures such as status lines, choices, or battle reports. Heavy means machine-readable markers plus regex/CSS/JS rendering; route that to `references/07-rendering-tavojs.md` and `references/18-ar-tavojs-plugin-patterns.md` instead of hiding UI engineering inside card prose.
5. Worldbook allocation. Use keyword entries for large or conditional lore. Reserve constant entries for compact rules or facts genuinely needed on every turn. Large maps, faction catalogs, and numeric tables may be easier to maintain as separate entries, but constant activation still spends context and should not be presented as a context-saving technique.
6. Openings. Either drop the player into a concrete scene or use `first_mes` as a start/character-creation selector. Use `alternate_greetings` for genuinely different starting states, not as dialogue examples; keep the field boundaries in `references/24-character-opening-and-examples.md`.
7. Format rules. Prefer closed enumerations, explicit empty/default behavior, and deterministic formulas over vague scaling. State each required output contract once and precisely; repeated “must” wording does not make an ambiguous contract machine-checkable.
8. NPCs. Large cards may begin with a batch-generated shallow roster when the world needs an initial cast: walk-ons get a one-line position, while supporting characters get a position, one relationship tension with the lead, and one story hook. Deepen characters individually only when the user selected them, the agreed design already identifies them as core, or the running story actually promotes them. Core characters receive the full skeleton anchors and the matching expression ledger. Never silently upgrade an ordinary NPC to protagonist depth merely because more detail might be useful. When the user has explicitly delegated cast design, the agent may choose a small number of core NPCs and record that choice in the assumptions list; if the upgrade materially expands the deliverable, ask first.

## Chinese Prose Cleanup

All authored deliverable text — card fields, embedded or add-on worldbook entries, openings, dialogue examples — goes through full detone cleaning before delivery, governed by the Prose Detone Protocol in `references/30-prose-detone.md` with its catalogs `references/31-prose-detone-catalog.md` and `references/32-prose-detone-narrative.md`. Boundaries:

- Guarded writing first for the style-teacher fields: first_mes and mes_example are written under the detone rules as generation constraints, not drafted tic-heavy and washed afterward; structural habits formed while writing survive surface cleaning. Other fields may rely on cleaning passes.
- A confirmed hit is repaired in place; the delivery report lists every detone fix — field, pattern family, what changed. The cleaned text itself never mentions the process.
- Mechanism text (rules, numeric contracts, output specifications, worldbook mechanics) gets conservative cleaning only: expression changes, precision never does.
- Cleaning must not wash the intended expression flat. The matching expression ledger's acceptance pass verifies that cleaned prose preserves the relevant speech, narrator, or non-verbal behavior facets; rule-only text has no ledger and is checked for precision instead. Protagonist-depth NPCs pass the same applicable check.
- Tone governance follows the commission boundary. A preset supplied only to test a card remains untouched; a preset explicitly commissioned for creation or revision may be edited within that scope. Never bundle an unrequested companion detone preset with a card.

The quick blacklist below stays as a fast default scan, not a rigid ban. Common weak patterns:

- passive emotion words like "不禁", "情不自禁", "油然而生";
- overused similes like "宛如", "仿佛", "如同";
- vague modifiers like "淡淡的", "轻轻地", "微微一笑", "深邃的眼眸";
- melodramatic stock phrases like "命运的齿轮", "难以言喻";
- repeatedly reused sentence molds such as “很多……”, “不是……而是……”, “真正……的是……”, and “越……越……”.

Replace with concrete action, tone shift, posture, silence, decision, or dialogue.

## Multi-Object Delivery Order

For complex packages:

1. Write the role/card text first.
2. Extract worldbook entries from facts that are conditional or too large for the card.
3. Add preset behavior only if the role needs a special generation policy.
4. Add macros/EJS for dynamic state only when the design needs it.
5. Add regex for transformation and display.
6. Add Advanced Rendering for visual layout.
7. Add plugin packaging only when the behavior should be reusable across cards/chats.
8. Validate each layer before adding the next.

## Quality Checklist

- Does the card have one clear attraction core?
- Are permanent facts in persistent fields rather than buried in notes?
- Does the opening message teach the desired style?
- Do examples demonstrate voice and relationship dynamics?
- Are worldbook triggers specific enough?
- Are regexes tested against before/after examples?
- Are dynamic variables documented and initialized?
- Does every product claim state its applicable version or configuration?
- Are older-version results kept version-scoped instead of silently promoted?

## Expression Ledgers

Use a ledger only when the artifact has an expression channel to preserve. The ledger is an internal working document maintained by the agent across several passes; it is normally not delivered unless the user asks for it. All passes are internal agent work and never interrupt the user.

Choose only the matching forms. A mixed world card may need a Narrator Voice Ledger plus separate Speech or Behavior Ledgers for core NPCs; do not create a ledger for a channel the artifact does not contain.

- **Speech Pattern Ledger:** for a speaking character. Record sentence length, directness or evasion, vocabulary and knowledge boundaries, audience-dependent differences, and how speech changes under pressure. Recurring phrases are optional: record them only when the user requests them, the source card already contains them, or multiple examples establish a natural recurrence. Otherwise write `no fixed catchphrase`; never invent one just to fill the ledger.
- **Narrator Voice Ledger:** for a world card or artifact with a deliberate narrator voice. Record distance, tense, descriptive density, judgment boundary, pacing, and what the narrator may never decide for the player. Do not manufacture character catchphrases for narration.
- **Behavior Ledger:** for a silent or primarily non-verbal character. Record gesture vocabulary, pacing, signals, relationship-dependent behavior, and pressure responses instead of speech traits.
- **No expression ledger:** for procedural, encyclopedic, or rule-only worldbook entries with no intentional narrator voice. Validate precision, trigger behavior, factual consistency, and output contracts instead.

Each selected ledger follows five passes:

1. Design stage. While the skeleton is being fixed, write only the expression anchors applicable to that ledger type.
2. Proof pass. After the relevant opening, examples, narration, or behavior demonstrations have first drafts, extract the regularities those texts actually display and reconcile them with the design item by item.
3. Probe feed. Once the ledger is valid, the probe derivation protocol takes applicable language, narrator, or behavior traits from it.
4. Checklist pass. The tier-1 checklist verifies that the ledger's genuinely distinctive features survive compilation into the final request; an absent optional catchphrase is never a failure.
5. Review yardstick. Text review checks only the expression channels the artifact actually contains. Speaking examples should cover ordinary, pressured, and avoiding speech when those facets apply; silent entities and narrator-only artifacts use their own ledger traits instead.

A protagonist-depth NPC from the World Card Authoring rules goes through the same applicable passes. Detone cleaning per the Chinese Prose Cleanup section runs on the same drafts; the selected ledger doubles as the acceptance check that cleaning removed generic model tone without flattening the intended voice or behavior.

## Authoring Gates

Five gates run inside the agent loop during authoring — free, internal, and never interrupting the user. A gate failure returns work to the step it guards; nothing proceeds on a failed gate. Each gate leaves one line in the delivery report — gate name, pass or fail, number of fixes — with details expanded only for failures. A protagonist-depth NPC passes the same gates.

### Interview Reconciliation Gate

Runs after the interview closes, before drafting the skeleton. Reconcile the skeleton against the active Creative Authority Mode. In collaborative-confirmed creation, every confirmed decision must have a landing point and no unconfirmed substantive choice may be silently added. In demo-delegated autonomous creation, the approved pitch and locked pillars must land intact, while agent-chosen compatible details remain marked as assumptions rather than user decisions. Existing-text cleaning reconciles against the supplied source and approved correction scope instead of inventing a new skeleton.

### Skeleton Solidity Gate

Runs after the skeleton is fixed, before field expansion. Rescan the whole skeleton against the empty-talk rule: every anchor must be backed by a concrete behavior, scene, habit, decision, or relationship-specific reaction. An anchor surviving only as abstraction goes back for follow-up questions or rewriting before expansion starts. The applicable expression anchors from each selected ledger's design stage are checked here too — they must be concrete enough to produce derivable probe expectations later.

### Cross-Field Consistency Check

Runs after field expansion completes, before detone cleaning. Extract every trait claim from description, personality, scenario, first_mes, mes_example, and add-on worldbook entries, then check them pairwise for contradiction — a character written withdrawn in personality must not open by confidently working the room; worldbook facts must not contradict card facts; world cards include their rule contracts in the same sweep. Repair contradictions at the fact level first — decide which field is right, then align the others; never smooth wording over a factual conflict. Running before cleaning saves one pass, since cleaning rewrites text.

### Adversarial Read

Runs after `compile` produces the final request, once the tier-1 mechanical checklist passes. Read the assembled request as the model receiving it: hunt ambiguity, mutually conflicting instructions, sections the model is likely to misread, and crucial instructions buried where attention is weak. The card's final form is the assembled request, not the fields. Findings that would change model behavior are fixed only in the commissioned source fields and recompiled; if the cause is an immutable non-commissioned test asset, report it without modification. Stylistic-only findings go to the text review report.

### Regression Loop

Runs after any modification to a checked artifact — accepted text-review suggestions, detone fixes, or user-requested changes. Minimum rule: any field change reruns the compiled tier-1 checklist; changes to an expression channel rerun the matching ledger proof pass; changes to facts rerun the cross-field consistency check. The delivery report states which gates were rerun and why.

## Prompt Lab Self-Check

For supported ordinary text prompt chains, semantic verification of a finished artifact runs through Prompt Lab (`references/27-prompt-lab.md`) as the default and sufficient acceptance surface: use `compile` to inspect the assembled request and `run` to observe the model's text response. Upgrade to phone/runtime validation only when the case crosses one of the explicit unsupported or approximation boundaries in `references/27-prompt-lab.md`, such as Advanced Rendering, TavoJS/plugin behavior, regex display behavior, native persistence, unsupported EJS/regex branches, or a fresh runtime-version mismatch.

Build the case from the finished artifacts: the card, the exact test preset supplied or selected by the user, persona when defined, add-on worldbooks, regex groups, and history. Editing authority follows the current commission exactly: any explicitly commissioned preset, character card, Persona, worldbook, regex group, or other named source may be edited within the requested scope; every non-commissioned test input is byte-for-byte read-only. If a non-commissioned fixture suppresses or blocks the target, report that configuration finding against the untouched fixture and ask the user either for another fixture or for an explicit scope expansion. Never change an out-of-scope asset, relax its `forbidOverrides`, change its entry types, add a jailbreak entry, or create a modified A/B variant merely to make the commissioned artifact pass.

### The Five-Tier Ladder

1. Checklist, mandatory and free. `compile` the case and verify: skeleton-anchor content and the selected expression ledger's distinctive features are present in the final messages when a ledger applies, worldbook trigger decisions match intent, no unrendered `<%` or `{{macro}}` residue remains, dialogue-example count and field fill rates meet the card's own claims, and every warning is triaged. Fix the commissioned artifact before proceeding if the checklist fails; all non-commissioned test assets remain untouched.
2. Behavior probes, paid API calls, offered in the interview live-test batch. Run the derived probe set as single-turn `run` cases against a real model.
3. Short multi-turn arc, paid, offered in the same batch. Run a `turns` session of exactly 5 turns with no injected history and check whether the relationship arc actually moves.
4. Synthetic long-history stress test, paid, for important cards and deliverables. Generate a realistic history segment with the agent model from the card itself — never hand-write it — put it into the case `history`, then run targeted deep-history probes against it. Label every result `synthetic`: it can expose weaknesses but cannot prove behavior under a real evolved chat. Only a captured real conversation qualifies as real-session long-history validation.
5. Long-range probe, paid, derived from tier 3. Extend one continuous `turns` session to 20–30 turns to watch arc drift, state continuity, and persona stability over a long session. This is the most API-call-heavy tier.

Tiers 2–5 are never run by default; they are asked as the final interview batch after the checklist passes. Choose tiers by verification purpose, not cost: tier 3 for a quick arc check, tier 4 for controlled long-context semantic capture, tier 5 for long-range drift, freely combined.

Every reply generated in tiers 2–5 passes a reply tone recheck against the detone catalogs `references/31-prose-detone-catalog.md` and `references/32-prose-detone-narrative.md`. The card text is cleaned before delivery, but the teaching loop only closes if the model's own replies are checked too: confirmed residue is recorded as a live-test finding, and when residue traces back to the commissioned artifact's text that still teaches a tic, only that commissioned source field is fixed and the regression loop reruns. If the cause lies in a non-commissioned test asset, record the finding without changing the asset. The recheck applies the catalog's strength marks and the RP false-positive protection — the character's own voice is never counted as residue.

### Text Review

Run a read-only text review bound to the mandatory checklist: once the tier-1 checklist passes, review the written fields themselves. It costs no API calls, so it never becomes a user-choice tier. Review angles follow the artifact's actual composition: character consistency, believability, opening appeal, model-tone residue judged against the detone catalogs, and dialogue-example quality when dialogue exists — judged against the matching expression ledger; worldbook usage, variable, and regex completeness only when those add-ons exist. The opening carries the heaviest angle — judge hook, naturally embedded character detail, and respect for user agency against the opening rules, and give concrete improvement directions instead of a rewrite. Never modify the artifact in read-only review mode. Output an opinion report that does not restate the artifact, keeps every pro and con at field or resource level, and lists zero to five genuine priority fixes. If no material or useful fix exists, say so plainly; never manufacture findings to fill a quota. When the user accepts any suggestion, opening improvements go first.

### Probe Derivation Protocol

Probe expectations are derived from the finished card's declared traits, never from a generic template:

1. Trait inventory: list every behavioral trait written into the card — language, narrator, or non-verbal habits taken primarily from the matching expression ledger when one exists, cognition habits such as memory quality, emotional triggers, behavioral inertia, relationship-arc stages, and rule contracts for world cards.
2. Triple per trait: trait text as written in the card → a probe input that provokes it → registered expectations.
3. Expectations are registered before sending, so replies can only be judged against them, never rationalized afterward.
4. Expectations must be checkable features: sentence length caps, presence or absence of named phrases or details, refusal instead of compliance, presenting options instead of deciding. Wording like “the reply feels right” is not an expectation.
5. Expectations are bidirectional. A character written as forgetful passes when they forget correctly; a character who must refuse passes by refusing. The verdict is consistency with the persona, not a generic quality standard.
6. A trait that yields no derivable probe is flagged as vague writing and sent back to the empty-talk rule for a rewrite or demoted to atmosphere.
7. Assemble the set from the most playable traits, typically 4–6 positives plus one negative probe that invites the character to violate its strongest trait, with resistance or discomfort as the expected outcome. Never derive probes from traits the card never declares.
8. Tone expectations ride along with trait expectations. Every probe's registered expectation set includes one negative tone expectation — the reply contains no confirmed detone-catalog hit, registered by pattern family before sending and judged with the catalog's strength marks, combination rules, and false-positive recheck. Character voice is not residue: a reply failing only on voice is a pass on tone.

Deep-history probes follow the same protocol: a persona written as attentive to small details expects captured deep facts delivered in the character's own voice; a forgetful persona expects natural forgetting.

### Report Format

Report one line per probe — purpose, registered expectation, verdict of pass/fail/uncertain, and the shortest supporting excerpt from the reply — plus the checklist summary and any tier-5 drift findings. Keep the report in this fixed shape instead of prose.

## Delivery Report

One report aggregates every authoring trace. It is written to the workspace alongside the artifact with an immutable, artifact-bound name: `<artifact-stem>.delivery-report.<YYYYMMDD-HHMMSS>.<sha8>.md`, where `sha8` is the first eight hexadecimal characters of the artifact's SHA-256. If that exact name already exists, append the first free increasing suffix before `.md` — `.2`, `.3`, and so on. Never overwrite an earlier report. The report header records only the artifact basename or a sanitized package/workspace-relative path—never an absolute machine path—plus its full SHA-256, generation time, task mode (`creation`, `narrow-revision`, or `global-audit`), and the previous report filename when the current work continues an earlier revision; use `none` when there is no parent report. Resolve a revision baseline by artifact hash or an explicitly named parent, never by blindly taking the newest report.

The report remains in the workspace by default and is not part of the standard delivery. The delivery contains the requested artifact plus whatever the user selected in the delivery-content question (PNG assembly and similar). Attach the report only when the user explicitly asks for it; at the end of every delivery, one line tells the user that the report exists in the workspace.

Report sections in fixed order:

1. Commission summary — the agreed direction in a few lines, plus the assumptions list when the agent was authorized to choose details.
2. Gate rows — one row per authoring gate: gate name, pass or fail, number of fixes; only failures expand with details.
3. Detone fix list — field, pattern family, what changed.
4. Checklist summary — the compile checks, including skeleton-anchor and ledger-feature presence.
5. Text review — the opinion report's priority fixes, and which ones the user accepted.
6. Live tests — the per-probe rows from the Report Format plus the reply tone-recheck findings when the user chose tiers; otherwise one line noting the user declined.
7. Regression notes — which gates reran after fixes, and why.
8. Unresolved or deferred items — genuine issues left after a five-round cap, frozen repeated issues, and findings the user declined; write `none` when empty.

Expression ledgers stay out of the report body; they remain internal documents available on request.

## Existing Card Revision

This section applies to any existing card the user brings back for revision, whether or not this pipeline originally authored it. Route by the requested scope; do not turn a bounded edit into an unsolicited full-card audit.

### Narrow revision

1. When the user names one field or one change, that target is the complete pre-authorized scope. Inspect only the target plus the minimum dependencies required to avoid an invalid artifact or an immediate factual contradiction.
2. Make only the requested change. Do not scan, list, clean, or repair unrelated fields first.
3. Apply the matching guarded-writing and regression checks only to the touched field and necessary dependencies. Build a temporary expression ledger only when the change touches an expression channel such as an opening, dialogue examples, narrator voice, or non-verbal behavior; pure fact edits need no ledger.
4. After delivering the requested edit, the agent may ask one non-blocking question: whether the user wants a separate full-card read-only audit. Do not ask when the user already declined extra checking. The completed narrow edit never waits for this answer.

### Global audit or broad improvement

1. Enter this branch only when the user asks to audit, review, diagnose, optimize, clean, or broadly improve the card, or accepts the post-edit audit offer.
2. Run the free full scan: detone catalogs over the whole card, cross-field consistency over all trait claims, and the matching expression-ledger extraction only for expression channels that exist.
3. Present the genuine findings in one list and let the user choose what to fix. Each finding carries a severity mark — cosmetic (不改也能玩), recommended (建议改), or material (明显影响体验) — so the user can triage quickly; false positives may be rejected on the spot. “扫出来的都修” upgrades authorization to everything listed.
4. Execute only the approved items. After every fix round, rerun the regression checks applicable to the touched fields.
5. Only gates that stand alone apply: cross-field consistency, adversarial read, and the regression loop. Interview reconciliation and skeleton solidity have nothing to reconcile against and stay off.
6. The delivery report follows the usual format and, for global-audit mode, adds scan findings and the user's disposition — fixed, declined, or deferred. A narrow-revision report records only the requested change and necessary dependency work; it must not imply that the untouched card was globally audited.

Diagnosis requests (“这张卡怎么聊着没意思”) still enter through the revision entry in `references/29-creation-intake-interview.md`; the diagnosis may be converted directly into this section's checklist.
