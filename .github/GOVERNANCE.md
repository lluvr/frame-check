# Frame Check Governance

**Status:** Minimal v0. Documents current de-facto governance.
**Curator:** Lovro Lucic (single-curator BDFL model for v0.x of the library).

---

## Purpose

This document names who decides what in Frame Check, where those decisions are recorded, and what is explicitly held for future specification. It closes the reference to `GOVERNANCE.md` in `CONTRIBUTING.md` without overcommitting to a formal review process that has not yet been tested against a real external reviewer.

This document covers governance mechanics only: who has authority, over what, by what process, and what happens when governance itself needs to change.

---

## Current state: single-curator

Frame Check is a single-curator project. **Lovro Lucic** is the curator. For v0.x of the library, the curator carries benevolent-dictator authority (BDFL-style) over:

- Which Frame Vocabulary Standard (FVS) entries are added, refined, promoted, or withdrawn
- Which detection rules ship in `frame_library.suggest_frames` and `framing.py`
- Which methodology and detector changes land
- Which worked examples are published
- Which pull requests merge (reviewer, per `CONTRIBUTING.md`)

The curator is the named author on every release.

---

## Where decisions live

A decision is not a decision until it lands in an authoritative source. The sources below are current:

| Decision type | Authoritative source |
|---------------|----------------------|
| FVS library state, canon trajectory, citation form | per-card prose under `data/frame_library/` |
| Contribution workflow (PR process, tests, RFC triggers) | `CONTRIBUTING.md` |
| License | `LICENSE` (corpus: CC-BY-4.0; code: Apache-2.0) |
| Public release notes | `CHANGELOG.md` |
| Divergence-block API contract | `docs/FRAME_DIVERGENCE_CONTRACT_v1.md` |

Anything not in these sources is not yet a decision.

---

## Scope of current governance

The curator decides:

- **Library curation.** Frame additions, removals, class assignments, status changes on the canon trajectory (`INDEX.md`).
- **Publication.** What ships to bundled corpora, what is held back with withdrawal banners.
- **Methodology.** Detection rules, calibration policy, regime gates.
- **Code merges.** Reviewer on pull requests (`CONTRIBUTING.md`).

The curator does NOT decide:

- What a reader concludes from a Frame Check analysis. The tool produces analytical scaffolding; the reader does the interpreting.
- What a reader concludes from a worked example. Worked examples are commentary under fair use; the reader does the interpretive work.

---

## Canon promotion

`INDEX.md` specifies five criteria for promoting a frame from `draft` to `canon`. As of v0.2.0 of the library, **zero frames have been promoted**. Every published entry carries the `[DRAFT]` marker on its citation block and the corresponding stability guarantee is ID-only.

Two blockers stand between the current state and the first canon promotion:

1. **External reviewer pipeline.** Promotion criterion 2 requires at least two reviewers outside the curator. The reviewer terms (what is being reviewed, deliverable shape, and the path from reviewer to co-curator) are agreed when the first reviewer engages, not invented against hypotheticals.
2. **Formal review process.** What a reviewer does, the review deliverable format, dissent handling, and appeals are deferred in their full form (see "Explicitly deferred" below). The first external review converts the working terms into observed practice from which `GOVERNANCE.md v1` extracts the formal review process. Specifying a process against imagined reviewers produces overspecification.

Once the first reviewer engages, `GOVERNANCE.md v1` documents the formal review process extracted from observed practice rather than invented from template.

---

## Explicitly deferred

These are real governance questions that will be answered when their forcing functions fire. Deferring them is not evasion; it is a refusal to overspecify against hypotheticals.

| Deferred item | Forcing function | Enabling artifact |
|---------------|------------------|-------------------|
| Formal review process (reviewer deliverable, format, dissent handling) | First external reviewer engages | Working terms agreed at engagement; v1 extracts from observed practice |
| Canon-vote disagreement resolution (full v1 rule) | First canon-vote with dissenting reviewer | The both-positions-published default; the provisional rule below names the minimum bright line that governs until the first real disagreement arrives |
| Canon retirement process (who initiates, who decides, transition for external references) | First canon frame challenged on evidence | None yet |
| Amendment process for this document (what requires RFC, who ratifies) | First governance dispute | None yet |
| Curator succession (how authority transfers) | Curator transition planning | Reviewer to repeat reviewer to co-curator on-ramp |
| Council / multi-curator model | Library scale exceeds single-curator capacity | Deferred until the first co-curator pair forms |

Each is a genuine governance question. None is urgent until its forcing function fires.

---

## Provisional dissent rule for the first canon promotion

The "Canon-vote disagreement resolution" item above is deferred to its full v1 form. A reviewer engaging the first canon promotion needs to know the minimum bright line that governs today, not "we'll figure it out when it happens." This provisional rule names the minimum, explicitly bounded to the first promotion, and commits to `GOVERNANCE.md v1` specifying the full rule from observed practice once disagreement actually happens.

**Provisional rule (governs the first canon promotion only):**

1. **Unanimous support among engaged reviewers required to promote.** If every engaged reviewer recommends "promote" (plain or conditional), the curator may promote per the five INDEX criteria.
2. **A single "no-promote" verdict from any engaged reviewer blocks promotion at this step.** The entry remains draft. Both verdicts are published (the editorial-independence default). The dissenting evidence drives the next iteration of the entry and subsequent re-review.
3. **Curator-override of a dissent requires an `[RFC]` that overturns this provisional rule.** The RFC is published with reasoning and the dissenting reviewer's prior verdict inline. This is deliberately expensive; the cost is the safeguard against a dissent being waved away silently.
4. **Tied holds (e.g., one "promote," one "hold at draft")** treat "hold" as non-blocking if the "hold" reviewer explicitly opts into "promote if the other reviewer's conditions are met." Otherwise treat as a "no-promote" and apply (2).

This provisional rule is deliberately conservative: it is easier to loosen than to tighten once precedent is set. v1 will revisit with observed dissent data (one or more real cases) and may replace with a majority rule, a weighted rule, or a domain-expert-specific rule. Until then, unanimity-required is the published bright line.

The rule is bounded to the first canon promotion because first-wave promotions carry outsized weight on the library's citation record. Later promotions with an established canon as reference point may warrant a less conservative rule; that is a v1 question, not a v0 one.

---

## Relationship to other documents

- **`CONTRIBUTING.md`** references this document for "who decides and when a contribution becomes canon." `CONTRIBUTING.md` continues to own the mechanical contribution workflow (PR format, tests, commit conventions).
- **`INDEX.md`** defines the canon-trajectory status taxonomy (`canon` / `draft` / `aspirational` / `retired`).

---

## Versioning this document

Governance is a living document. This stub (v0.x) will expand.

- **v0.x → v1.0:** first canon promotion completes; formal review process + dissent handling + reviewer deliverable format specified from observed practice rather than imagined cases.
- **v1.0 → v2.0:** amendment process + curator succession specified when their forcing functions fire.
- **v2.0 → v3.0:** council / multi-curator model specified when library scale exceeds single-curator capacity.

---

## Honest limits of this document

- **Documents current de-facto governance; pending external ratification.** This stub describes how decisions are already being made and where they are recorded. It has not been reviewed by external parties. The deferred items (review process, dissent, retirement, amendment, succession, multi-curator) are all places where external input will materially shape what gets specified when their forcing functions fire.
- **BDFL model is provisional.** Single-curator authorship aligns with BDFL-style curation. If the library scales to multi-curator, this model evolves. The current model is fit-for-v0.x, not fit-forever.
- **First canon promotion is the first real test.** Until one frame promotes, the promotion process is theoretical. Observed practice on the first promotion will expose which parts of the current spec hold and which need revision.
