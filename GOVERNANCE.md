# Frame Check Governance

**Status:** Minimal v0. Documents current de-facto governance. Formal review process and dissent handling are deferred to named forcing functions (see "Explicitly deferred" below).
**Date:** 2026-04-18; substrate-sources amendment 2026-04-26 (five new authoritative-source rows added covering v2 architecture, §11 catalog discipline retrofit, anchor authorship methodology, pre-registered empirical protocol, and cross-curator engagement; library version reference v0.1.0 → v0.2.0 reconciled with VERSION).
**Curator:** Lovro Lucic (single-curator BDFL model for v0.x of the library).

---

## Purpose

This document names who decides what in Frame Check, where those decisions are recorded, and what is explicitly held for future specification. It closes the reference to `GOVERNANCE.md` in `CONTRIBUTING.md` without overcommitting to a formal review process that has not yet been tested against a real external reviewer.

The overall strategic direction, durable product decisions, and project identity live in STRATEGY.md. This document covers **governance mechanics only**: who has authority, over what, by what process, and what happens when governance itself needs to change.

---

## Current state: single-curator

Frame Check is a single-curator project. **Lovro Lucic** is the curator. For v0.x of the library, the curator carries benevolent-dictator authority (BDFL-style) over:

- Which FVS entries are added, refined, promoted, or withdrawn
- Which detection rules ship in `frame_library.suggest_frames` and `framing.py`
- Which methodology changes land in `METHODOLOGY.md`
- Which worked examples are published to `/corpus/worked-examples/`
- Which durable decisions in `STRATEGY.md §6` are adopted, amended, or held
- Which pull requests merge (reviewer, per `CONTRIBUTING.md`)

**Named authorship is the moat** (`STRATEGY.md §4` durable decision 5). The curator is the named author on every publication until the project scales to multiple contributors with published track records in framing analysis.

---

## Where decisions already live

A decision is not a decision until it lands in an authoritative source. The sources below are current:

| Decision type | Authoritative source |
|---------------|----------------------|
| Product strategy and empire role | STRATEGY.md |
| Durable product decisions (require RFC to overturn) | `STRATEGY.md §6` |
| Original product decisions (premium gate, framing architecture, content loop) | DECISIONS.md |
| Prioritized unbuilt improvements | NEXT_STEPS.md |
| FVS library state, canon trajectory, citation form | `data/frame_library/INDEX.md` |
| v1 publication withdrawals and rationale | `build_corpus_site.py` `_WITHDRAWN` dict |
| Recent architectural decisions | `SESSION_STATE.md §2` |
| Contribution workflow (PR process, tests, RFC triggers) | `CONTRIBUTING.md` |
| Library license | `LICENSE` (corpus: CC-BY-4.0; code: Apache-2.0) |
| Vault↔fork sync for `clarethium_measure` | CLARETHIUM_MEASURE_SYNC.md |
| FVS-Eval (framing benchmark for LLMs): scope, corpus criteria, scoring, reporting format, roadmap, lab engagement plan | `fvs_eval/SPEC.md` |
| Canon-promotion dossiers (per-entry reviewer packages with self-assessment against INDEX.md criteria, named weaknesses, reviewer ask, and verdict-consequence mapping) | `data/frame_library/promotions/` (README + one dossier per candidate) |
| v2 layered architecture (taxonomy, lifecycle, cross-cutting principles, falsifiable predictions) | `FRAME_DIVERGENCE_v2.md` |
| §11 catalog discipline retrofit (grounded-authorship sections; structural-grade across 19 active entries) | `data/frame_library_v3/` (parallel retrofit directory) + `FRAME_DIVERGENCE_v2.md` §11 |
| Anchor authorship methodology (introspective protocol, corroboration discipline, retraction protocol) | `ANCHOR_AUTHORSHIP_METHODOLOGY_v1.md` |
| Pre-registered empirical protocol (Claim A: chain-output beats single-frame on decision quality) | CLAIM_A_PROTOCOL_v1.md |
| Cross-curator engagement (recruitment, outreach templates, engagement protocol, findings format) | `CROSS_CURATOR_OUTREACH_v1.md` |

Anything not in these sources is not yet a decision. An `[RFC]` issue is required to change items in `STRATEGY.md §6` or to introduce items that would overturn a durable decision (see `CONTRIBUTING.md` "What a contribution cannot do without an RFC").

---

## Scope of current governance

The curator decides:

- **Library curation.** Frame additions, removals, class assignments, status changes on the canon trajectory (`INDEX.md`).
- **Publication.** What ships to `/corpus/`, what is held back with withdrawal banner + `noindex` (`build_corpus_site.py` `_WITHDRAWN`).
- **Methodology.** Detection rules, calibration policy, regime gates.
- **Code merges.** Reviewer on pull requests (`CONTRIBUTING.md`).

The curator does NOT decide:

- What a reader concludes from a Frame Check analysis. The tool produces analytical scaffolding; readers remain sovereign (`STRATEGY.md §4` durable decision 4: open by design; and the sovereignty thesis from the upstream).
- What a reader concludes from a worked example. Worked examples are commentary under fair use; the reader does the interpretive work.

---

## Canon promotion

`INDEX.md` specifies five criteria for promoting a frame from `draft` to `canon`. As of v0.2.0 of the library, **zero frames have been promoted**. Every published entry carries the `[DRAFT]` marker on its citation block and the corresponding stability guarantee is ID-only.

Two blockers stand between the current state and the first canon promotion:

1. **External reviewer pipeline.** Promotion criterion 2 requires at least two reviewers outside the curator. Recruitment is open; the terms, honest state of what a reviewer would be reviewing, deliverable shape, and upgrade path from reviewer to co-curator are specified in `docs/RATERS.md`. NEXT_STEPS.md and `SESSION_STATE.md §4` track recruitment status. **The first canon-promotion candidate has a published dossier:** `data/frame_library/promotions/FVS-001_v1.md`. That dossier is the concrete package a reviewer receives when engaging on FVS-001; it is the v1 of the first-review surface and is itself a canon-candidate artifact subject to `docs/RATERS.md` measurement-construct review path.
2. **Formal review process.** What a reviewer does, the review deliverable format, dissent handling, and appeals are partially specified in `docs/RATERS.md` v0 as the outreach-anchor form and in `data/frame_library/promotions/README.md` + the FVS-001_v1 dossier as the concrete first-promotion shape, and are deferred in their full v1 form (see "Explicitly deferred" below). The first external review converts these v0 artifacts into observed practice from which `GOVERNANCE.md v1` extracts the formal review process. Specifying a process against imagined reviewers produces overspecification; the v0 artifacts name terms concretely enough to recruit and loosely enough to update after contact.

Once the first reviewer engages, `GOVERNANCE.md v1`, `docs/RATERS.md v1`, and `data/frame_library/promotions/FVS-001_v2` (if needed) co-release with the formal review process extracted from observed practice rather than invented from template.

---

## Explicitly deferred

These are real governance questions that will be answered when their forcing functions fire. Deferring them is not evasion; it is a refusal to overspecify against hypotheticals. Each will be specified in a future `GOVERNANCE.md` version when its forcing function fires.

| Deferred item | Forcing function | Enabling artifact |
|---------------|------------------|-------------------|
| Formal review process (reviewer deliverable, format, dissent handling) | First external reviewer engages | `docs/RATERS.md` v0 (outreach + terms + deliverable shape; v1 extracts from observed practice) |
| Canon-vote disagreement resolution (full v1 rule) | First canon-vote with dissenting reviewer | `docs/RATERS.md` "Editorial independence" paragraph names the both-positions-published default; this document's "Provisional dissent rule for the first canon promotion" below names the minimum bright line that governs until the first real disagreement arrives |
| Canon retirement process (who initiates, who decides, transition for external references) | First canon frame challenged on evidence | None yet |
| Amendment process for this document (what requires RFC, who ratifies) | First governance dispute | None yet |
| Curator succession (how authority transfers) | Curator transition planning | `docs/RATERS.md` "upgrade path" (reviewer → repeat reviewer → co-curator) is the succession on-ramp |
| Council / multi-curator model | Library scale exceeds single-curator capacity | `docs/RATERS.md` co-curator terms sketch the first pair; council form is deferred |

Each is a genuine governance question. None is urgent until its forcing function fires. Writing them against imagined cases would produce a process that does not match real practice once it arrives.

---

## Provisional dissent rule for the first canon promotion

The "Canon-vote disagreement resolution" item above is deferred to its full v1 form. A reviewer engaging the first canon promotion (FVS-001, per `data/frame_library/promotions/FVS-001_v1.md`) needs to know the minimum bright line that governs **today**, not "we'll figure it out when it happens." Shipping without one would mean a reviewer's "no-promote" verdict has no legible consequence, which defeats the point of recruiting them. This provisional rule names the minimum, explicitly bounded to the first promotion, and commits to `GOVERNANCE.md v1` specifying the full rule from observed practice once disagreement actually happens.

**Provisional rule (governs the first canon promotion only):**

1. **Unanimous support among engaged reviewers required to promote.** If every engaged reviewer recommends "promote" (plain or conditional), the curator may promote per the five INDEX criteria.
2. **A single "no-promote" verdict from any engaged reviewer blocks promotion at this step.** The entry remains draft. Both verdicts are published per `docs/RATERS.md` Editorial-independence. The dissenting evidence drives the next iteration of the entry (curator-authored v2 dossier) and subsequent re-review.
3. **Curator-override of a dissent requires an `[RFC]` that overturns this provisional rule.** The RFC is published with reasoning and the dissenting reviewer's prior verdict inline. This is deliberately expensive; the cost is the safeguard against a dissent being waved away silently.
4. **Tied holds (e.g., one "promote," one "hold at draft")** treat "hold" as non-blocking if the "hold" reviewer explicitly opts into "promote if the other reviewer's conditions are met." Otherwise treat as a "no-promote" and apply (2).

This provisional rule is deliberately conservative: it is easier to loosen than to tighten once precedent is set. v1 will revisit with observed dissent data (one or more real cases) and may replace with a majority rule, a weighted rule, or a domain-expert-specific rule. Until then, unanimity-required is the published bright line.

The rule is bounded to the first canon promotion because first-wave promotions carry outsized weight on the library's citation record (cf. `docs/RATERS.md` "Maximum-reviewer-count policy"). Later promotions with an established canon as reference point may warrant a less conservative rule; that is a v1 question, not a v0 one.

---

## Relationship to other documents

- **`CONTRIBUTING.md`** references this document for "who decides and when a contribution becomes canon." That reference now resolves. `CONTRIBUTING.md` continues to own the mechanical contribution workflow (PR format, tests, commit conventions).
- **`docs/RATERS.md`** is the open invitation and terms document for external reviewers on canon-promotion candidates. It names the honest state of what a reviewer would be reviewing, the deliverable shape, per-engagement terms (framing locked 2026-04-18 and propagated into the document on 2026-04-21: compensation defaults to co-curator aspiration plus named attribution plus a situational $500-$1,000 honorarium only where the reviewer's context requires it; maximum-reviewer target is 3 for the first canon promotion with 4th and 5th solicited after), and the reviewer-to-co-curator upgrade path. This document specifies the governance frame; `docs/RATERS.md` specifies the reviewer-facing offer.
- **`INDEX.md`** defines the canon-trajectory status taxonomy (`canon` / `draft` / `aspirational` / `retired`). This document specifies that the curator moves entries between statuses, informed by external reviewers once recruited, subject to the five promotion criteria.
- **`STRATEGY.md §6`** durable decisions are the only decisions with explicit `[RFC]`-required gating. See `CONTRIBUTING.md` "What a contribution cannot do without an RFC" for the RFC pattern.
- **SESSION_STATE.md** is the running changelog of architectural decisions including governance-adjacent ones (D-2026-04-17-a through g, D-2026-04-18-a, D-2026-04-18-b). This document is the stable reference; `SESSION_STATE.md §2` is the chronological append-log.

---

## Versioning this document

Governance is a living document. This stub (v0.x) will expand.

- **v0.x → v1.0:** first canon promotion completes; formal review process + dissent handling + reviewer deliverable format specified from observed practice rather than imagined cases.
- **v1.0 → v2.0:** amendment process + curator succession specified when their forcing functions fire.
- **v2.0 → v3.0:** council / multi-curator model specified when library scale exceeds single-curator capacity.

Each version bump records what forcing function fired and what was extracted. Version bumps are the curator's decision with RFC for any change that overturns a `STRATEGY.md §6` durable decision.

---

## Honest limits of this document

- **Documents current de-facto governance; pending external ratification.** This stub describes how decisions are already being made and where they are recorded. It has not been reviewed by external parties. The deferred items (review process, dissent, retirement, amendment, succession, multi-curator) are all places where external input will materially shape what gets specified when their forcing functions fire.
- **BDFL model is provisional.** The named-authorship moat (STRATEGY.md §4 durable decision 5) aligns with BDFL-style curation. If the library scales to multi-curator, this model evolves. The current model is fit-for-v0.x, not fit-forever.
- **This document does not decide strategy.** STRATEGY.md does. If a decision here conflicts with a durable decision in `STRATEGY.md §6`, STRATEGY.md wins and this document updates to match.
- **First canon promotion is the first real test.** Until one frame promotes, the promotion process is theoretical. Observed practice on the first promotion will expose which parts of the current spec hold and which need revision.
