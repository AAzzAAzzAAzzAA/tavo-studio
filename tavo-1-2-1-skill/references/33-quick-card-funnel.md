# Quick Card Funnel

This page is a complete creation branch for users who have little or no idea and just want a new card to play with. They cannot answer open creative questions, but they can pick from candidates: picking is recognition, answering is creation, and the two differ by an order of magnitude in effort. The funnel replaces open questions with pick-and-expand rounds, then forks into either the normal interview handoff or a self-contained direct-output quality loop. It is a creative workflow, not a Tavo product guarantee.

## When To Use

- The user takes the question-5 exit in the Character First Batch of `references/29-creation-intake-interview.md` with no direction at all.
- The user opens with “没什么想法，你来” or “随便给我做张能玩的卡”.
- Do not use it for a user who already has a direction: route them to the normal interview, or to Direct-Output Mode in `references/29-creation-intake-interview.md` when they want no questions.

## Candidate Quality Standard

Every candidate must be concrete enough to picture. A candidate is a short pitch containing:

- One character hook that implies behavior, not a label — “冷面总裁” alone is rejected; the hook must suggest what this person does, wants, or hides.
- One experience direction — what playing this card feels like.
- One concrete scene or behavior that makes the pitch visible.

Candidates in one batch must differ visibly from each other; three cosmetic variants of the same idea violate this section.

World cards use the same standard with the hook swapped: a world-card candidate carries a gameplay-loop hook instead of a character hook — what the player does every turn and what changes as they do, plus the experience direction and one concrete scene. “一个修仙世界” alone is rejected the same way “冷面总裁” is.

## Funnel Steps

1. **First batch.** Present 5-10 candidates meeting the quality standard above. If the user already answered some first-batch questions, every candidate is seeded from those answers — nothing the user said is discarded.
2. **Pick.** The user selects one candidate (“这个不错”). Do not treat a pick as a lock; it is a seed.
3. **Expand.** From the picked seed, write another batch of variants that vary along meaningful axes — relationship stance, tone, stakes, world, or the character's core want. The seed itself may be refined rather than replaced.
4. **Loop.** Pick and expand repeat as many times as the user needs. The user may mix elements from several candidates; assemble the mix and confirm it in one line before continuing.
5. **Lock.** The user says “就要这个” or equivalent. Record the locked pitch verbatim; it becomes the agreed direction for everything downstream.

## Fork After Lock

Ask one question in plain language, for example “要不要我再问几个细节问题，还是直接给你做出来？”

- **Interview path.** The user accepts more questions: enter the normal interview, but most of first-batch 1-4 is already answered by the locked pitch — ask only the gaps, starting from Later Character Batches in `references/29-creation-intake-interview.md`.
- **Direct output.** The user says just make it: this explicitly activates demo-delegated autonomous creation from `references/13-creation-craft-workflows.md`. Proceed to the Direct-Output Quality Loop below without asking for another approval.

## Direct-Output Quality Loop

The user supplied little material, so quality comes from an internal agent loop that does not interrupt the user. This branch owns the complete authoring flow; it does not run the normal Handoff a second time.

1. **Draft through the applicable gates.** Treat the locked pitch as the approved creative direction and use demo-delegated authority to fill compatible details. Reconcile the pitch plus the assumptions list, pass skeleton solidity, expand the fields, and pass cross-field consistency. Assumptions stay marked as assumptions; the pitch's pillars and delivery scope stay locked. Select only the expression ledgers that match the artifact: Speech Pattern, Narrator Voice, Behavior, or none for rule-only worldbook text.
2. **Cleaning.** Run full detone cleaning per the Chinese Prose Cleanup section in `references/13-creation-craft-workflows.md`, with the selected expression ledgers as acceptance checks when they apply.
3. **Compile and mechanical checklist.** Compile the finished sources, run the mandatory tier-1 checklist, and fix mechanical failures before review.
4. **Adversarial read.** Only after compilation and the mechanical checklist pass, read the assembled request as the receiving model and fix behavior-changing findings only in the commissioned source fields. If a finding originates in an immutable test asset, report it without changing that asset.
5. **Bounded auto review.** In this direct-output branch, Text Review changes from a read-only opinion pass to an internal inspector pass. Run at most five review rounds. One round means: review every commissioned artifact and selected commissioned add-on once; fix every genuine in-scope finding; then rerun the regression checks required by those changes. Test fixtures and other non-commissioned assets remain untouched. Stop immediately when a review finds no issue. Do not manufacture findings to consume the remaining rounds.
6. **Five-round stop.** If genuine issues remain after round five, stop automatic revision. Present the current artifact with the unresolved items and their impact recorded in the delivery report, then let the user accept it, select fixes, or explicitly authorize another bounded cycle of at most five rounds. The earlier same-issue escape remains valid: freeze an issue that returns after being fixed for two consecutive rounds instead of ping-ponging.
7. **Final regression and live-test offer.** Rerun the final compile checklist and every gate required by the last changes. If round five left unresolved failures, pause here for the user's decision and do not claim a full pass. Once the checks pass or the user explicitly accepts the documented remainder, ask the paid live-test tiers in the same plain-language batch used by the normal flow.
8. **Delivery report.** Write the immutable artifact-bound report per the Delivery Report section in `references/13-creation-craft-workflows.md`. The “我替你决定了这些” assumptions list is mandatory for quick-card deliveries and is normally larger than usual; review rounds, fixes, frozen issues, and round-five unresolved items all appear in their report sections. Keep it in the workspace by default and attach it only when the user asks.

## Handoff Boundary

The interview path rejoins the normal Handoff To Authoring section in `references/29-creation-intake-interview.md`, with the locked pitch standing in for the interview summary. The direct-output path does not rejoin that Handoff: its Direct-Output Quality Loop already performs gates, the applicable expression ledger, detone, compile/checklist, adversarial read, bounded review, live-test offer, and delivery reporting exactly once.
