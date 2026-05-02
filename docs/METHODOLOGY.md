# Frame Check Methodology

**Version:** 0.3.1 (draft)
**Author:** Lovro Lucic
**Date:** 2026-04-19
**Status:** Working draft. Post external-validation-study revision
(see §2.4, §5.2). Construct-honesty section §1.3 added 2026-04-19
alongside the shipped Fix A posture sweep (see `VISITOR_AUDIT.md
§7`). Not yet published.

## Construct-honesty note (2026-04-18)

The first external validation study of Frame Check's detector
completed 2026-04-18 and its pre-registered H3 falsification
threshold fired: macro-F1 of detector versus majority-union of
two independent labelers on a 12-document mixed-genre corpus is
**0.157**, well below the pre-registered threshold of 0.4.
Detector-versus-curator kappa is +0.031; detector-versus-LLM-judge
kappa is -0.008. Both are essentially chance-level agreements.

The study's findings are preserved in full at
`fvs_eval/validation_study/REPORT.md`. A post-audit rule
revision cycle followed on the same day: a per-frame audit
(RULE_AUDIT.md) produced a v2 detector
(`frame_library_v2.py`) whose macro-F1 measures at 0.274 on
the same corpus (REPORT_V2.md), a 75 percent relative
improvement from rule-level revisions alone. v2 remains below
the pre-registered useful floor of 0.4; rule-level tuning on
the current signal substrate appears to have limited headroom.

This methodology document has been revised to reflect what the
studies do and do not establish. The controlled frame-
transformation validation described in §5.1 (same data rewritten
from different frames produces measurably different structural
profiles) remains accurate; neither study contradicts that. The
v1 study contradicts a stronger claim, that the detector's
labels match what independent readers see, which this document
must no longer assert without qualification. The v2 study shows
the gap is partially narrowable at the rule level but not
closable without new signal dimensions. §2.4 (with §2.4.1 for
the v2 follow-up) and §5.2 are the substantive revisions.

## 1. What Frame Check measures

Frame Check is a computational instrument for detecting structural framing patterns in text. It answers: what perspectives does this document take, what perspectives does it omit, and how does it position the reader?

Frame Check does NOT measure: reasoning quality, logical validity, whether conclusions follow from premises, whether the analysis is insightful, or whether the output is useful for a specific purpose. These require human judgment.

Frame Check does NOT detect semantic framing. A document can pass all structural tests while being subtly manipulative at the semantic level. Structural detection is a necessary precondition for frame analysis, not a sufficient one.

### 1.1 Two layers

**Layer 1: Framing analysis (zero LLM, deterministic).** Seven computational functions detect the structural frame:
- Analytical coverage: 5 categories (causes, risks, stakeholders, trends, uncertainty), density per 1,000 words
- Temporal orientation: past, present, future sentence ratios
- Voice detection: prescriptive, promotional, analytical, descriptive, advisory
- Epistemic basis: sourced vs. unsupported numerical claims
- Claim density: hedged, unhedged, predictions
- Framing portrait: synthesis of all signals into 2-4 sentence structural narrative
- Framing headline: single most important finding

**Layer 2: Verification floor (structured APIs, no LLM for measurement).** Numerical claims are checked against authoritative data sources where coverage exists. Verification coverage is strongest for US public company financials and macroeconomic indicators; many domains (medical, legal, niche industry) have near-zero coverage. In the EXP-094 calibration corpus, 86% of claims were unverifiable. Verification is the floor that frame analysis stands on: if the facts are wrong, the frame collapses regardless of structure.

Sources: SEC EDGAR (US public company filings, annual and quarterly), World Bank (country statistics), FRED (US macroeconomic), REST Countries (demographics, geography), CoinGecko (crypto), Alpha Vantage (equity), Wolfram Alpha (physical/computational), Wikipedia (encyclopedic reference), Brave Search (fallback).

### 1.2 What the output looks like

For each document, Frame Check produces:
- A framing portrait (the structural narrative)
- A trust level with reasons (based on verification results)
- An annotated document with claim-level highlighting
- Frame pattern suggestions from the FVS library with teaching questions
- Claim verification cards with confidence dimensions (where Source Network coverage exists)

### 1.3 Construct: what the analytical-coverage detector actually measures

The five-category analytical-coverage signal (causes, risks, stakeholders, trends, uncertainty) is vocabulary-and-pattern based. Each category has a regex expressing the lexical markers the detector counts as evidence of that category. A category flagged as **covered** means the detector matched at least one marker; a category flagged as **missing** means it matched none.

The construct has a known asymmetry. Over-detection is bounded: a covered flag on a category with density below approximately 3 matches per 1,000 words is more likely nominal than substantive, and density is surfaced for readers to check. Under-detection is unbounded in principle: a document may discuss causation using structural reasoning that never activates the causal-vocabulary regex (example patterns: "centers on," "rationale," "given," implicit causation across sentence boundaries). The same failure mode applies to each other category. The regex lists in `framing.py::ANALYTICAL_CATEGORIES` are the exhaustive statement of what the detector searches for.

Therefore:
- A `missing` signal is a **lower-bound claim about detection**, not an **upper-bound claim about the document**. The honest English rendering is "no markers detected for X," not "does not address X."
- A `covered` signal is a lower-bound claim about substance. The detector saw vocabulary; whether it is substantive or nominal is the reader's call (density is a proxy, not a proof).

The product surfaces have been aligned to this posture as of 2026-04-19. The shipped portrait, headline, and comparison prose say "Low structural coverage of X" or "no markers detected" rather than "does not address X"; the MCP `frame_check` and `frame_compare` tool responses name under-detection in `what_this_tool_does_not_tell_you` and in the coverage-field `caveat`. See `framing.py::framing_portrait`, `comparison.py`, `mcp_server.py` for the implementation. The `VISITOR_AUDIT.md §7 Fix A` entry documents the posture shift and its call sites.

This construct applies only to the five-category coverage signal. Voice classification, temporal orientation, epistemic basis (sourced vs unsupported numerical claims), and FVS matches have their own construct caveats, summarized in the first-discipline section (§6).

### 1.3.1 Construct-honesty for cascade-classification residual cases (added 2026-04-20)

The §1.3 discipline was scoped to the coverage signal because that is where Fix A (2026-04-19) identified and addressed the failure. A separate but structurally analogous failure exists in the voice signal, surfaced by `fvs_eval/CONSTRUCT_HONESTY_AUDIT_v1.md` (2026-04-20).

Voice is a 7-rule deterministic cascade with analytical as the residual class. For documents where no cascade rule fires (no directive, promotional, descriptive, or advisory markers detected), voice is assigned the `analytical` label as a residual fallback. These documents constitute 71% of the N=28 validation corpus (20 of 28). The audit finds that user-facing surfaces (`framing.py::framing_portrait` line 1425 emits "Analytical document examining the topic in third person") and the MCP agent-facing surface (`mcp_server.py::_build_voice_construct` says "When confidence is 'high', the classification is safe to restate without the margin caveat") treat residual cases as decisively-classified. This is the SAME construct-honesty violation §1.3 names for coverage: making an existential claim about the document on the basis of absence-of-markers.

The discipline extended:

- For the voice cascade-classification signal, `confidence = "high"` silently admits two populations: documents where a rule fires with margin ≥ `_VOICE_BORDERLINE_MARGIN` (decisive positive evidence), and documents where no rule fires and the analytical bucket is the residual fallback (absence of positive evidence). These are semantically distinct; the shipped `confidence` label does not distinguish them.
- The §1.3 honest-rendering rule ("no markers detected for X" rather than "does not address X") applies structurally to cascade residuals. For voice, the honest rendering for residual-analytical is "no directive, promotional, or descriptive voice markers detected; narration is third-person by default" rather than "Analytical document examining the topic in third person."
- `CONSTRUCT_HONESTY_AUDIT_v1.md §4` names three response levels. Level 1 (regression tests pinning the finding) and Level 2 (this section) executed 2026-04-20. Level 3 (prose amendment, new `confidence` state, MCP text update) is curator-gated because it changes shipped user-facing and agent-facing output.

This subsection is Level 2 of the audit response. The discipline stated in §1.3 for coverage now extends explicitly to cascade-classification residual cases. Downstream artifacts that cite voice confidence rates (methodology paper §4.4, shipped headline copy, MCP `how_to_serialize`) must qualify the residual population or be updated to surface it.

### 1.4 Relationship to the L5 per-level claim discipline (added 2026-04-27)

The §1.3 and §1.3.1 evidence disciplines (under-detection for presence/absence signals; classification-confidence for categorical signals) operate within a broader L5 framework that tags every emitted construct with one of four claim levels: `detector_measurement`, `classifier_output`, `composed_pattern`, `agent_generated`. Each claim level carries its own per-level discipline shipped in `agent_guidance.claim_level_treatments` on every MCP payload.

The 5-signal posture documented in §1 (coverage / epistemic / claims / voice / temporal) and the 8 named structural patterns (recommendation-without-falsification, growth-without-risk, instruction-without-failure-modes, etc.) are specific cases under the L5 framework:

- Coverage / epistemic / claims live at `detector_measurement` (regex/heuristic surface counts) composed into `composed_pattern` (the dimension reading).
- Voice / temporal live at `classifier_output` (cascade or distribution classification with confidence + runner-up).
- Genre lives at `classifier_output` (per-class scoring with abstention discipline).
- Frame patterns live at `composed_pattern` (multi-signal composition triggering on genre + frame matches + falsification thresholds).
- LLM-augmented constructs (frame_opportunities) live at `agent_generated` (cited as agent reading, not substrate measurement).

The L5 framework is documented per-construct in CONSTRUCT_VALIDITY_AUDIT_v1.md (v1.1 as of 2026-04-27), which walks 13 substrate constructs through 5 evaluator questions (validity / honesty / calibration / failure modes / reproducibility) at all 4 claim levels. The 13th construct (V4.2 LLM-judge FVS detection, evaluation-engine-only as of v1.1) surfaces an L5 framework gap that the audit names explicitly: V4.2 binary judgments without confidence/runner-up structure fit none of the four existing claim levels cleanly, and the audit proposes two resolution paths (Proposal A: fifth claim level `llm_classifier_output`; Proposal B: broaden `classifier_output`) for operator-decision in v1.2. The audit also distinguishes 4 patterns of construct-honesty mechanism (structured construct block, prose-only construct string, inline note prose, claim_level inheritance via claim_level_treatments) explaining why different epistemic surfaces deserve different shapes.

The adversarial fixture suite at `data/adversarial_fixtures/` provides operational test infrastructure for the L5 framework: each fixture pins the substrate's per-level reading on a deliberately-composed motivated-writer document, exposing per-level catch-vs-miss diagnosis. The suite has 5 fixtures as of 2026-04-27 covering all 4 claim levels.

## 2. The Frame Vocabulary Standard (FVS)

The FVS is a curated library of named framing patterns. The
library (`VERSION` 0.1.0) contains 20 entries on the canon
trajectory (all currently `draft`; no promotions to `canon`
yet); 16 are published to the v1 web surface and 4 are
withdrawn from v1 rendering while their IDs are preserved for
citation continuity. Entries divide into two classes along the
detection-possibility axis: **text-side** (11 entries; frame
manifests as patterns detectable in document text, with a
matching detection rule in `frame_library.py`), and **meta-side**
(9 entries; frame describes a reader, system, or relational
mechanism that text-alone cannot surface). Full class assignments
and promotion criteria are the source of truth in
`data/frame_library/INDEX.md`.

### 2.1 Entry format

Each entry has:
- **Identification:** name, type, one-paragraph definition, detection signals
- **Generation affordances:** how a user encountering this frame can expand their thinking
- **Worked example:** a concrete document excerpt showing the frame in action
- **Branch applicability:** which Frame Check detection surfaces connect to this frame
- **Vocabulary connections:** links to related entries and to Clarethium terminology
- **Honest limits:** what this entry cannot detect, common false positives, when it is inappropriate

### 2.2 Curation methodology

Entries were curated by a single investigator (Lovro Lucic) from a vault of 94 experiments, 48+ documented falsifications, and 118+ growth insights. The curation process:
1. Candidate frame identified from experimental evidence or literature
2. Worked example constructed from real AI-generated text patterns
3. Detection signals mapped to Frame Check's computational outputs
4. Honest limits section written before the identification section
5. Vocabulary connections established to existing entries

### 2.3 Limitations of v1

- **Single curator.** No inter-rater reliability data. A second
  curator would likely produce a different library. This is a
  reliability gap that canon promotion is designed to close
  (INDEX.md promotion criteria require at least two external
  reviewers per entry); zero entries have completed promotion
  as of the current library version.
- **Western-dominated.** All entries draw from Western epistemics
  (cognitive linguistics, argumentation theory, political
  science). Non-Western framing traditions are not represented.
- **Detection coverage tied to class honesty.** Of the 16
  v1-published entries, all 11 text-side entries have automated
  match rules in `frame_library.py`. The 5 v1-published
  meta-side entries (FVS-005, FVS-006, FVS-013, FVS-017, FVS-020)
  name phenomena the detector cannot surface from text alone,
  by design; they serve as teaching surface and as adjacency
  pointers for text-side matches. A prior version of this
  document conflated meta-side entries with "detection gaps"
  in text-side entries; the 2026-04-18 IDX-1 curator pass
  separated the two (see `INDEX.md` coverage summary).
- **Schema limit on multi-document detection.** The binary
  text-side / meta-side does not distinguish single-document
  detection from detection that requires a reference document
  supplied as `source_text`. FVS-018 (Scope Narrowing) is the
  clearest case: narrowing is detectable if the original
  question is provided as source material, but not from the
  response document alone. Tracked as an open INDEX v2 schema
  question.
- **No domain-specific calibration.** The library applies the
  same frames across financial, health, scientific, and general
  domains. Domain-specific thresholds would improve precision.
- **Detector-labeler agreement is low on first external
  validation.** See §2.4 for the preliminary numbers and
  per-frame breakdown. The detector's output should be read
  as "this document exhibits the pattern that historically
  correlates with frame X," not as "this document is a case
  of frame X." The distinction is load-bearing and previously
  understated.

### 2.4 Limits of detection precision (external validation v1)

Frame Check's detector was externally validated for the first
time 2026-04-18 in a pre-registered study documented in
`fvs_eval/validation_study/`. The study measured detector
output against two independent labelers (curator and LLM-judge)
on a 12-document mixed-genre corpus.

**Primary result.**

| Metric | Value | Pre-registered threshold | Outcome |
|--------|------:|-------------------------:|---------|
| Macro-F1 detector vs majority-union | 0.157 | ≥ 0.4 useful-floor | H3 fires; below threshold |
| Macro-kappa detector vs curator | +0.031 | | chance-level |
| Macro-kappa detector vs LLM-judge | -0.008 | | chance-level |

The pre-registered H3 threshold fired. The DESIGN.md-specified
response is project-pivot, not threshold adjustment. This
section documents the pivot.

**Per-frame variance.** Of 11 detectable frames, only FVS-011
Stakeholder Frame achieved F1 above 0.5 (0.727) against the
majority-union of labelers. Two frames (FVS-014 Temporal
Anchoring, FVS-016 Authority by Citation) had zero detector
fires across all 12 documents despite labelers flagging them
in 4 and 6 documents respectively. Two frames (FVS-001 Frame
Amplification, FVS-007 Failure Framing) over-fired relative
to labeler flags. The detector's per-frame behaviour is not
uniform; it works on frames where framing-relevant vocabulary
appears directly in the sentences the frame names (FVS-011's
"customers / employees / investors" signal) and underperforms
on frames that require inference about narrative arc,
selection, or emphasis (FVS-014, FVS-016).

**Per-stratum variance.** Detector macro-F1 on human-authored
public documents (0.525, n=2) was higher than on fresh
AI-generated analyses (0.194, n=6) and Wikipedia encyclopedic
text (0.100, n=4). The detector works better on short,
structurally-explicit documents (the FOMC statement alone
scored F1 = 0.800, all labelers agreeing) than on longer
analytical text.

**What the study does not establish.** See REPORT.md §6 for
honest limits. Summary: n=12 is small; the LLM-judge is not a
human expert; the study does not establish which labels are
correct, only that the detector disagrees with both available
labelers. A larger study with independent human annotators is
the logical next measurement (REPORT.md §8.2, feeding back
into SPEC.md §8 v0.2 inter-annotator validation).

**How to read detector output after this finding.** Until rule
revision lands and produces an improved F1 on a replication
corpus, the detector's output in `frame_library.suggest_frames`
should be treated as **teaching-question generator**, not as
a framing-label claim. The suggestion "this document may exhibit
FVS-008 Growth Frame, teaching question: what would a risk
analyst say about this same data?" stands as a reader-prompt
regardless of whether the frame label itself has low agreement
with independent labelers, because the teaching question has
value as reader affordance independent of classification
accuracy. This is the re-scoping REPORT.md §7.1 names as "the
vocabulary is the asset; the detector is one implementation of
the vocabulary among several that could be built."

**Rule revision follow-up is tracked** in REPORT.md §8.1 (per-
frame rule audit) and is curator-owned engineering work. The
library's `data/frame_library/INDEX.md` already carries per-entry
versioning so rule revisions can ship as v1 -> v2 without
destabilising citation.

### 2.4.1 v2 post-audit result (2026-04-18)

The per-frame rule audit recommended by §8.1 of the v1 report
completed on the same day. Full documentation in
`fvs_eval/validation_study/RULE_AUDIT.md` (282 lines of per-frame
analysis) and `fvs_eval/validation_study/REPORT_V2.md` (v2 measurement
results). A post-audit detector implementation is in
`fvs_eval/validation_study/frame_library_v2.py`.

**Primary result.** Applying the audit's recommended rule revisions
to the same 12-document corpus, the same curator and LLM-judge
labels:

| Metric | v1 | v2 | Delta |
|--------|---:|---:|------:|
| Macro-F1 vs majority-union | 0.157 | **0.274** | +0.118 |
| Stratum A (human-authored) | 0.525 | 0.622 | +0.097 |
| Stratum B (fresh AI-generated) | 0.195 | 0.310 | +0.116 |
| Stratum C (Wikipedia encyclopedic) | 0.100 | 0.434 | +0.335 |

A 75 percent relative improvement in macro-F1 from rule-level
revisions alone. **v2 remains in the pre-registered H3
falsification zone** (< 0.4). The audit's diagnoses worked on
the frames it targeted, but the ceiling on rule-level tuning
against the current signal substrate (coverage, voice, temporal,
epistemic) appears to sit below the pre-registered useful floor.

**Specific wins.** Three rules moved from broken to usable:
FVS-009 Risk Frame (F1 0.364 to 0.875, loosened threshold drops
the uncertainty-coverage requirement), FVS-016 Authority by
Citation (0.000 to 0.444, lowered citation-density threshold from
50 to 20), FVS-014 Temporal Anchoring (0.000 to 0.400, lowered
past/future-percentage thresholds from 70/60 to 35/35).

**Retirements.** Three rules were retired from the v2 detector
because the v1 signal substrate (coverage, voice, temporal,
epistemic density) cannot distinguish their target cases from
similarly-shaped non-cases on the validation corpus: FVS-001
Frame Amplification, FVS-008 Growth Frame, FVS-015 Efficiency
Frame. Retirement cleaned nine false positives without costing
true positives because true positives were already zero on
detectable cases in v1. The FVS library entries remain in place;
only the detection rules are retired.

**Three claims the retirement evidence supports, and one it
does not.** The retirement supports: (1) the v1 rules produce
zero true positives on this corpus, (2) the rule signals measure
vocabulary distribution rather than the frame-level phenomena
the entries describe (per `fvs_eval/validation_study/RULE_AUDIT.md`
§2.1 for FVS-001 specifically: "the rule labels vocabulary-
distribution patterns as amplification"), and (3) rule-level
tuning on the current signal substrate has limited headroom
(v2 macro-F1 = 0.274 remains below the pre-registered useful
floor of 0.4). The retirement does **not** support the claim
that the frames themselves are falsified: the 12-document
validation corpus does not contain documents in FVS-001's stated
scope ("extended AI-assisted analysis sessions"), FVS-008's
growth-essay scope, or FVS-015's efficiency-claim scope at
enough depth to test the frames against their own target
populations. The retired rules failed on this corpus; the frame
concepts remain empirically open and are testable by (i) richer
signals in `framing.py`, (ii) V4.2 LLM-judge evaluation on
target-scope corpora, or (iii) dedicated experimental designs.

Future rule revisions (for example, adding growth-vocabulary
signals to `framing.py`) could restore detection under a
different design.

**Non-delivering change.** FVS-012 Uncertainty Frame threshold
loosening produced no F1 change. The binding constraint is
upstream coverage-classification (minimum marker count in
`detect_coverage`), not the density threshold the audit adjusted.
Proper fix requires expanding the uncertainty regex in
`framing.py` to catch hedge constructions the current vocabulary
misses ("undemonstrated," "theoretically promising but practically
unproven," "years or decades away"). Deferred.

**Implication for further progress.** Additional rule tuning on
the current signal substrate has limited headroom. Closing the
gap to useful-floor (0.4) or beyond requires new signals in
`framing.py` itself (growth-vocabulary, efficiency-vocabulary,
named-author-citation, expanded uncertainty regex), a larger
corpus for tuning and validation, or acceptance of the detector-
as-teaching-question-generator framing stated in §2.4 above.
The path forward is curator-decidable; the v2 result closes the
rule-level iteration cycle.

**Production integration of v2.** The v2 detector
(`frame_library_v2.suggest_frames_v2`) has not been merged into
the main `frame_library.py`. This is a deliberate pause: before
replacing the production detector, a curator decision is needed
on how to reflect the three retirements in `INDEX.md` (the FVS
entries are not meta-side in concept, but their v1 detection
rules are retired) and on whether to ship v2 as-is or wait for
new-signal work. Tracked as an open decision.

### 2.4.2 V4.2-era library-wide cross-family reliability baseline (2026-04-23)

Sections 2.4 and 2.4.1 report reliability for the retired v1
rule-based detector. The canonical detector going forward is V4.2
LLM-judge per the project's release-arc commitments;
reliability claims in published artifacts (canon-promotion
dossiers, reviewer references, future publications) should rest
on V4.2-era numbers, not v1 rule numbers.
This subsection names the library-wide V4.2 baseline so that the
methodology-level reliability claim is current-generation.

**Measurement.** Library-wide cross-family reliability across all 20
FVS entries, NEW-panel fast/flash tier (Claude Haiku 4.5, Gemini 3.1
flash lite, Grok 4.1 fast as V4.2 canonical, GPT-5.4 mini). Two
corpora:

- **Mixed-genre baseline** (`fvs_eval/mixed_genre_v1`, n=15 docs,
  library_v2): 15 mixed-genre essays covering commentary, political
  analysis, and academic pieces. Labels reused from existing
  NEW-panel runs.
- **Target-scope corpus** (`data/worked_examples/*.md`, n=4 docs,
  library_v3): four analytical documents closer to FVS-001's stated
  scope (multi-LLM comparison essays and a framing-dense
  AI-company-founder essay). Labels from the 2026-04-23 S5
  measurement (`fvs_eval/v4_2/fvs_001_cross_family_target_scope_raw.json`).

Full methodology, per-frame results table, and interpretation at
`fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md`. Computed stats
at `fvs_eval/v4_2/library_cross_family_stats.json`. Zero new API
spend on this baseline (existing labels reused; computation only).

**Tier structure.** Per the baseline document §3, the 20-frame
library divides empirically into three canon-readiness tiers under
V4.2 cross-family measurement, plus a meta-side baseline:

**Canonical measurement reference (2026-04-24): library_current = `data/frame_library/`.** Library_v3 reclassified as an archived Step-4 detection-testing variant (commit `9abeb3d`, 2026-04-18), preserved for historical comparison. Tier structure below is reported on library_current.

- **Tier 1, canon-promotable on current evidence (library_current)**:
  FVS-008 Growth Frame (MG cur AC1 **0.85** / kappa 0.53; stable across
  library versions; TS unanimous intersection 4/4). FVS-017 False
  Balance (MG cur AC1 **0.84**; no v1 rule; empirical validation of
  detector-generation-agnostic Criterion 1).
- **Tier 1-B, canon-promotable with scope framing (library_current)**:
  FVS-014 Temporal Anchoring (MG cur AC1 0.68, up from v3 0.45),
  FVS-007 Failure Framing (MG cur AC1 0.67, recovered from v3 0.53
  via session refinement), FVS-015 Efficiency Frame (MG cur AC1 0.67),
  FVS-001 Frame Amplification (MG cur AC1 **0.65**, improved from
  v3 0.57 via session Identification refinements; current canon
  candidate per `data/frame_library/promotions/FVS-001_v1.md`).
- **Tier 2, canon-promotable with caveats (library_current)**:
  FVS-002 Fluency-Quality Illusion (MG cur AC1 0.30, dropped from
  v3 0.53 as Step-4 adjacent-frame tightenings in library_v3 are
  absent from current), FVS-010 Completeness Illusion, FVS-011
  Stakeholder Frame (dropped from v3 Tier 1), FVS-012 Uncertainty
  Frame, FVS-016 Authority by Citation (dropped from v3 Tier 1),
  FVS-020 The Invisible Frame (improved from v3 0.09 to current
  0.34 via removal of library_v3's retirement blockquote).
- **Tier 3, weaker measurement regime (library_current)**:
  FVS-009 Risk Frame (MG cur AC1 0.35, stable across versions).
- **Meta-side baseline**: FVS-003/FVS-005/FVS-006 fire 0/15 on
  mixed-genre across all four families (AC1 1.00 by all-agree-negative
  degeneracy); FVS-013 Oracle Frame fires 1/15 (essentially meta-side).
  Empirically validates the class-assignment audit.

Notable library-state transitions: **FVS-016 and FVS-011 drop out of
Tier 1 under library_current** (were Tier 1 on archived library_v3 via
Step-4 cross-frame tightening context). **FVS-014, FVS-001, FVS-007,
FVS-015 enter Tier 1-B** under library_current from archived library_v3
Tier 2/3 positions. **FVS-020 reliability improves** from library_v3
0.09 to library_current 0.34 after removal of library_v3's retirement
blockquote. See `fvs_eval/v4_2/FVS_007_ABLATION_RESULTS_v1.md` for the
mechanistic attribution of library-version context effects.
- **Meta-side baseline** (frames expected to fire rarely from text
  alone): FVS-003, FVS-005, FVS-006, FVS-013 all fire 0/15 on
  mixed-genre across all four families. This empirically validates
  the 2026-04-23 class-assignment audit resolution at
  `data/frame_library/INDEX.md` §open-questions §1: meta-side
  frames do not fire on text-only input, exactly as the
  class-assignment criterion predicts.

**Methodology-level interpretation.** Two claims the baseline
supports, and one it does not.

*Supports.* (1) V4.2 LLM-judge cross-family reliability is
heterogeneous across the library: some frames achieve substantial
cross-family agreement (Tier 1), some moderate (Tier 2), some weak
(Tier 3). Reliability is a per-frame property, not a library-wide
property; this is correct as measurement and should be reported this
way in any future publication. (2) FVS-017's strong cross-family
agreement without a v1 suggestion rule is direct evidence that the
`INDEX.md` Criterion 1 rewrite from 2026-04-23 (detector-generation-
agnostic framing, which permits canon promotion on LLM-judge
evidence alone) is empirically viable.

*Does not support.* The baseline does not establish correctness.
Judge-to-judge agreement measures whether four LLM families converge
on a label, not whether the label is right. A curator ground-truth
pass on a subset of the combined corpus, or an independent
human-annotator study, is what would add a correctness denominator.
Queued as future work per the 1-year test criterion on formal
external validation.

**Limitations.** Enumerated at LIBRARY_CROSS_FAMILY_BASELINE_v1.md
§6. Summary: n is small on both corpora (n=15, n=4); library_v2 and
library_v3 are mixed across the two corpora with the confound not
isolated (follow-up measurement queued, ~$2-4 spend); single-run
measurement without intra-rater sampling; judges-to-judges not
judges-to-ground-truth; NEW panel is fast/flash tier not LATEST
capability tier.

**How to read this subsection versus §§2.4, 2.4.1.** Sections 2.4
and 2.4.1 are historical: they document the v1 rule-based detector's
external validation (Macro-F1 0.157) and the v2 rule-audit cycle
that closed with the retirement of three rules. Section 2.4.2 is
the current-generation measurement: V4.2 LLM-judge against
library_v3 where available, library_v2 as baseline where v3 not yet
re-run. For canon-promotion reviewers, §2.4.2 is the reliability
section load-bearing for their ruling; §§2.4/2.4.1 supply generation
context and rule-retirement rationale.

**Library_v2 vs library_v3 trade-off (2026-04-23 ablation evidence).**
Three ablation tests documented in `fvs_eval/v4_2/FVS_007_ABLATION_RESULTS_v1.md`
isolated the cross-frame context effects of library_v3's two revisions
(FVS-010 simplification, FVS-020 vocabulary-only retirement marker) on
adjacent frames whose Identification was unchanged. Principal findings:
(1) per-entry library revisions produce asymmetric context effects across
the library via the judge's full-library-reference comparison space;
(2) no tested modification to library_v3 produces both a specific frame
recovery AND net-positive library-wide AC1; (3) library_v3 is empirically
approximately optimal given its structure. The measured consequence is
FVS-007's mixed-genre regression (AC1 0.53, coherence 0.08) is accepted
as a local cost of library-wide stability; FVS-007's canon-promotion
candidacy defers until a future library revision addresses this without
library-wide cost. FVS-008, FVS-017, FVS-011, FVS-016 remain the
near-term canon-promotion candidates under the current library per the
construct-validity audit and library-wide baseline.

**Methodology implication.** Future library revisions should be tested
with ablation-style cross-frame measurement before shipping, not only
revised-entry measurement. The single-entry-view is measurably
insufficient; per-entry revisions produce library-wide effects that are
not predictable from the revised entry alone. This is a generalizable
finding for multi-frame LLM-judge library design, codified as a
discipline in §2.4.3 below.

### 2.4.3 Library revision discipline (2026-04-23)

Origin: the 2026-04-23 FVS-007 ablation study
(`fvs_eval/v4_2/FVS_007_ABLATION_RESULTS_v1.md`) empirically demonstrated
that per-entry library revisions produce asymmetric context effects on
adjacent frames via the LLM judge's full-library-reference comparison
space. Three ablations on library_v3 (restoring library_v2 FVS-010,
restoring library_v2 FVS-020, stripping the FVS-020 retirement
blockquote) produced library-wide AC1 deltas of +0.75, +0.02, and
−0.67 respectively. No tested modification recovered the specific
frame under investigation (FVS-007) while preserving net-positive
library-wide AC1. The revised-entry-view (measuring only how a
revision affects the revised entry) is insufficient to predict
shipping readiness.

**The discipline.** Any library revision proposed for canonical
adoption (library_vN to library_v(N+1), or library_vN to library_vN.1)
shall be tested with ablation-style cross-frame measurement before
merge. Concretely:

1. **Baseline.** Measure V4.2 NEW panel cross-family reliability on
   a pinned corpus (currently `fvs_eval/mixed_genre_v1` n=15 + worked-
   examples n=4) against the current canonical library. Per-frame AC1,
   reasoning coherence cosine, and per-family positive counts are the
   minimum reportable metrics. Corpus and panel pinned in
   `fvs_eval/v4/MODEL_PANEL.md`.

2. **Revision variant.** Construct the proposed library variant
   (the revision applied to the canonical library, otherwise identical).
   Run the same panel on the same corpus against the variant library.

3. **Per-frame delta report.** For each of the 20 frames, report
   AC1 delta, reasoning coherence delta, and per-family positive-count
   delta. Frames with material deltas (|ΔAC1| ≥ 0.05 or |Δcoherence|
   ≥ 0.05) are flagged as affected by the revision.

4. **Library-wide net evaluation.** Sum per-frame AC1 deltas across
   the 20-frame library. Revisions producing net AC1 delta < 0 (library-
   wide reliability regression) shall not merge without explicit
   curator override acknowledging the regression. Revisions producing
   net AC1 delta ≥ 0 pass the library-wide-net test; per-frame affected
   frames shall be named in the revision commit message.

5. **Canon-candidate protection.** If any frame currently named as a
   near-term canon-promotion candidate (per LIBRARY_CROSS_FAMILY_BASELINE_v1.md
   §3 Tier 1 or documented dossier in `data/frame_library/promotions/`)
   experiences ΔAC1 ≤ −0.10 under the revision, the revision shall not
   merge without explicit curator statement that the canon-candidate
   regression is accepted. Protection list as of 2026-04-23: FVS-008
   (Tier 1, first post-FVS-001 candidate), FVS-016 (Tier 1), FVS-011
   (Tier 1), FVS-017 (Tier 1 prevalence-caveat), FVS-001 (active
   dossier).

6. **Committed evidence.** The revision commit shall include (a) the
   baseline + variant per-frame tables, (b) the library-wide net AC1
   delta, (c) a named disposition for each affected frame and each
   protected canon candidate, (d) a pointer to the raw label
   artifacts so the measurement is reproducible, AND (e) the
   computation script that produced the published numbers, alongside
   the numeric artifact itself.

   The (e) discipline was added 2026-04-24 as a consequence of the
   post-ratification reproducibility audit at
   `fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md`.
   The original library_v4 reliability artifact
   (`fvs_eval/v4/library_v4_reliability.json`) published per-frame
   `ac1_avg` values with a `measurement_note` claiming an MG + MG2
   average; 11 of 19 values turned out not to reproduce from on-disk
   labels via either simple or weighted averaging, even after a clean
   library_v4 re-measurement on MG2 (only 2 of 19 match). The original
   derivation script was not preserved. Without the script, future
   audits depend on backward-engineering, which in that case was
   insufficient to close the gap. A published numeric artifact
   without its derivation script is an unauditable claim from the
   moment of publication; the library cannot defend its own numbers.

   Satisfying (e) means: alongside every `*_reliability.json`,
   `*_stats.json`, or equivalent numeric artifact, ship a
   `*_compute.py` (or equivalent) that, re-run against the stated
   input labels, produces a file byte-equivalent to the committed
   artifact (modulo timestamps). A discipline test may assert this
   (see `test_v4_2_discipline_boundary.py::test_per_corpus_reliability_supplement_reproduces_from_labels`
   for the pattern applied to the reproducible post-audit
   supplement). For the next ratification (library_v5), the new
   reliability artifact MUST carry its derivation script and a
   discipline test that locks reproduction; this is non-negotiable
   under (e).

**Cost.** A full ablation measurement on the current pinned corpus is
60 API calls per variant (15 docs × 4 families) at ~$1.20-$1.50 spend
and ~15-30 minutes engineering. Three ablations during the FVS-007
study cost $3.60 total. For most revisions a single-variant ablation
suffices (~$1.20); multi-variant ablations are warranted when the
mechanism attribution is load-bearing (as it was for the FVS-007
study).

**Exception.** Emergency revisions (curator-declared, with explicit
rationale) may bypass the discipline but shall include a named
intent-to-run ablation follow-up within a specified window (e.g.,
within 30 days of merge). Bypass without ablation follow-up shall
not be considered part of canonical methodology.

**Recording.** Ablation outcomes shall be preserved as data
artifacts (raw labels, computed stats, interpretation report) in
`fvs_eval/v4_2/` or equivalent generation-specific subdirectory.
The 2026-04-23 ablation study artifacts are the reference
implementation of this discipline:
`fvs_eval/v4_2/measure_ablation.py`,
`fvs_eval/v4_2/analyze_ablation.py`,
`fvs_eval/v4_2/FVS_007_ABLATION_RESULTS_v1.md`,
`fvs_eval/v4_2/ablation_stats.json`,
`fvs_eval/v4_2/ablation_stats_full.json`.

**Why this is a discipline and not a suggestion.** Library revisions
that appear to improve one entry can cascade-harm several adjacent
entries through context effects. Shipping a revision without cross-
frame measurement risks silent cascade damage to canon-candidate
frames and to the library's overall reliability profile. The FVS-007
study is the proof case: the naive FVS-007 Identification revision
path (originally recommended) was abandoned after ablation showed
the FVS-007 regression was a context effect from adjacent entries,
not a FVS-007 internal issue. Without ablation, a FVS-007
Identification revision would have shipped as a "fix" that did not
address the actual mechanism, and would have introduced its own
cascade effects measurable only post-merge.

### 2.4.4 Engine library pinning discipline (2026-04-24)

Origin: the 2026-04-24 library_v3 → library_v4 ratification
(`fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md`) revealed that
editorial refinements to library entries affect the V4.2 judge
reliability only to the extent they touch `## Identification`
sections. The V4.2 engine at `fvs_eval/v4/v4_2_engine.py::_extract_identification`
composes its LLM-judge prompt from Identification sections only. All
other sections (Cross-family reliability, Adjacent frames, Honest
limits, Worked examples, Decision-readiness implication, Generation
affordances) are invisible to the engine.

**The discipline.** Library revisions operate in two separable
domains that the engine distinguishes and the discipline now names
explicitly:

1. **Identification-domain revisions.** Changes to `## Identification`
   sections. Affect cross-family AC1 through changed prompt content
   passed to the LLM judge. **Require §2.4.3 ablation-style
   measurement before merge.** A revision that modifies even one
   entry's Identification text is Identification-domain.

2. **Non-Identification-domain revisions.** Changes to Honest limits,
   Adjacent frames, Worked examples, Cross-family reliability sections,
   Decision-readiness implication, Generation affordances. **Do not
   affect engine behavior** because the engine does not read these
   sections. §2.4.3 ablation is not required for these revisions.

**Library version bump triggers.** A VERSION file bump (minor: 0.N.0 →
0.N+1.0 or 0.0.N → 0.N+1.0) is appropriate when either domain's
revisions are substantive enough to warrant a versioned snapshot.
Identification-domain revisions additionally require §2.4.3 pass.
Non-Identification revisions can bump VERSION on curator judgment
without ablation.

**Composition revisions** (engine-facing new library composed from
parts of existing libraries, as library_v4 is composed from library_v3
Identifications + library_current non-Identifications) pass §2.4.3
trivially if the Identification portion is byte-equivalent to an
already-ratified library. Verification is a byte-diff check on
`## Identification` sections across all 20 entries, not a fresh
cross-family measurement.

**Field-naming discipline.** Engine output fields tied to
library-version-specific reliability numbers (cross-family AC1,
library hash) shall use version-neutral names in the output contract.
The version itself lives in `meta.library_version`. Precedent:
library_v3's engine exposed `library_v3_consensus_ac1` and
`library_v3_hash` as field names, which forced an API-contract change
at the library_v3 → library_v4 migration. library_v4 forward uses
`library_consensus_ac1` and `library_hash`; future library_v5
ratification does not require field-name renames.

**Engine pinning vs. living library.** The engine reads a frozen
snapshot (currently `data/frame_library_v4/`). The working library
(`data/frame_library/`) evolves with ongoing editorial work between
ratifications. Divergence between the two is expected and disciplined:
the snapshot is what the engine measures against; the working library
is what reviewers read. At each ratification, the working library's
Identifications are frozen into the next snapshot after §2.4.3 pass.
Non-Identification evolution continues in the working library
immediately, available to reviewers before the next engine-snapshot
ratification.

**Why this is a discipline and not a suggestion.** Conflating the
two domains is exactly the mistake that almost blocked the
library_v3 → library_v4 migration. An early proposal framed the
migration as "find a minimal-surgical Identification-restoration
variant that passes both corpora," ran three ablation variants, and
found no single variant could pass §2.4.3 Step 5 protection on both
mixed_genre and target-scope corpora. The fresh-eyes frame
(Ident-vs-non-Ident) resolved the problem instantly: library_v4 =
library_v3 Idents + library_current non-Idents passes by
byte-equivalence of judge-visible content, preserves all non-Ident
editorial work, and requires no overrides. The FVS-007 ablation
(§2.4.3 origin) plus the library_v3 → library_v4 migration (§2.4.4
origin) together establish the two-domain discipline.

**Corollary (added post-library_v4 stress-test).** The two-domain
discipline above identifies `## Identification` as the engine-LLM-
facing section. This is true for the V4.2 labeling judge but
incomplete for the broader engine. The reframe feature at
`reframe.py::load_affordances` extracts the `## Generation
affordances` section from each entry and feeds the
`**Counter-document prompt:**` content into a Grok LLM call to
produce the reframed document. Generation affordances are therefore
engine-LLM-facing for the reframe path even though they are not
engine-LLM-facing for the labeling-judge path. The two-domain split
refines into three:

1. **Identification-domain revisions.** As stated above. Affect
   labeling-judge cross-family AC1. Require §2.4.3 ablation.

2. **Generation-affordances-domain revisions.** Affect reframe LLM
   behavior. Do not affect cross-family AC1. Require a reframe-
   behavior smoke test (one or more representative documents through
   `reframe.rewrite_from_frame` for each affected frame, comparing
   outputs structurally against the prior library version), not
   §2.4.3 ablation.

3. **Other non-Identification revisions** (Honest limits, Adjacent
   frames, Worked examples, Cross-family reliability sections,
   Decision-readiness implication). Reviewer-facing only. Neither
   §2.4.3 ablation nor reframe smoke test required.

Library_v4 itself is byte-equivalent to library_v3 on Generation
affordances (verified by direct file diff across all 20 entries
during the post-migration stress test), so the library_v4 ratification
carries zero reframe-behavior risk; the corollary is preventive for
future revisions where Generation affordances might evolve
independently of Identification text.

### 2.4.5 v2 architecture and grounded-authorship retrofit (2026-04-25)

The Frame Vocabulary Standard catalog gained a v2 architecture
overlay 2026-04-25 per `FRAME_DIVERGENCE_v2.md`. The architecture
absorbs `FRAME_DIVERGENCE_v1.md`'s narrow definition (catalog-minus-
present-rhetorical-frame) as one operation within a wider structural
and operational architecture: five-layer taxonomy (L0 receiver state,
L1 atomic axes, L2 simultaneous composites, L2.5 sequential chains,
L3 reality construct), five-stage lifecycle (detect, diverge, chain,
converge, ground), nine cross-cutting design principles. A paper-
shaped extract for external readers is at `FRAME_DIVERGENCE_v2_SUMMARY.md`.

Catalog discipline operationalization (Principle P5 of v2; primary
empire moat). Each catalog entry carries seven public-facing fields:
authorship dated, context of testing, failure record, success record,
lived-experience anchor, applicability metadata, empirical track record.
Plus one internal-operational field (friction-cost estimate) that
supports curation-layer workflow but does not appear in public-facing
entry summaries or external citation contexts. Catalog entries that
combine named authorship with grounded operational context provide
citation-anchored discipline that scales beyond template-only references.
This is the discipline the curation methodology of §2.2 produces under
v2; the structural rigor in §2.3 limitations remains accurate under v2
(single-curator, Western-dominated gaps remain), but the catalog
discipline framework is now uniformly applied.

Retrofit milestone. As of 2026-04-25, all 19 active FVS entries
(FVS-001 through FVS-019; FVS-020 retired per §5.1.4 of v1) carry
the v2 §11 grounded-authorship retrofit section. Each retrofitted
entry has all eight §11 fields populated. The lived-experience anchor
field is uniformly held "Open" with entry-specific criteria per
honest-scope discipline (§6 of this methodology), pending curator
authorship. The catalog is therefore at v2 §11 STRUCTURAL grade
(all eight fields present and operationally substantive) but not
at full v2 §11 grade (which requires authored anchors). Full-grade
catalog is maintainer-side activation work scheduled subsequent to
the retrofit milestone.

Anchor authorship discipline. `ANCHOR_AUTHORSHIP_METHODOLOGY_v1.md`
(shipped 2026-04-26) specifies the workflow for converting "Open"
placeholders to authored anchors without violating construct-honesty.
The methodology covers the L0 prerequisite (cultivation-pulled
operating state required), the introspective protocol (setup,
surface, deepen with evocation and sensory anchoring, corroborate,
commit-or-defer) adapted from Petitmengin and Vermersch's micro-
phenomenology, the failure-mode catalog with detection signals,
the construct-honest absence outcome (legitimate first-class
outcome when no anchor of viable quality is available), and the
retraction protocol. The methodology is reusable for cross-curator
practitioners (`CROSS_CURATOR_OUTREACH_v1.md`) and is the operational
instrument for accumulating evidence that tests v2 Prediction P6
(grounded authorship beats citation-only on user trust and adoption;
Claim B in v2 §15.2).

Phase 1C-revised entries (FVS-012 Uncertainty Frame, FVS-016
Authority by Citation, FVS-018 Scope Narrowing) include explicit
pre-revision-vs-post-revision documentation in their failure
record, demonstrating principled revision discipline rather than
moving-target definitions. The v2 retrofit format is consistent
across all 19 active entries; uniform language and structure.

Empirical infrastructure. v2 ships a pre-registered protocol
(CLAIM_A_PROTOCOL_v1.md) testing v2 Prediction P3 (chain-output
beats single-frame-output on decision quality) per §15.1 Claim A.
Runner (`scripts/claim_a_runner.py`) and analysis (`scripts/
claim_a_analysis.py`) ship with the protocol. Pre-registration
discipline mirrors the evidence discipline of §6 of this
methodology: hypothesis, decision rule, treatments, rubric, and
analysis plan fixed before data collection; outcome published
regardless of result.

Cross-curator validation infrastructure. v2 §3.5 names cross-
curator validation as the next test for L0 doctrine and DOF
taxonomy. Operator-actionable recruitment kit ships at
`CROSS_CURATOR_OUTREACH_v1.md`: six candidate practitioner
domain profiles, three outreach email templates, engagement
protocol, findings format, $300 honorarium model.

What v2 changes for citation. Researchers citing the FVS catalog
under v2 cite specific FVS entries with the eight-field grounded-
authorship discipline. The empire moat (Principle P5) is at the
catalog grounded-authorship layer; v1 citation-only discipline is
absorbed and extended. v2 architecture itself (the layered taxonomy,
the lifecycle, the cross-cutting principles) is the substrate
within which the catalog operates.

## 3. Detection methodology

### 3.1 Coverage categories

Five analytical categories are detected via regex pattern matching against curated word lists:

| Category | What it detects | Threshold for "covered" |
|----------|----------------|------------------------|
| Causes | Causal language (driven by, caused by, because, results in) | 2+ markers |
| Risks | Risk/threat language (risks, challenges, vulnerabilities, concerns) | 2+ markers |
| Stakeholders | Affected parties (customers, employees, investors, communities) | 2+ markers |
| Trends | Directional change language (grew, increased, declined, shifted) | 2+ markers |
| Uncertainty | Hedging/unknown language (may, possibly, approximately, unclear) | 2+ markers |

**Theoretical grounding.** The five categories are derived from policy analysis practice (what a complete analysis should address) rather than from a specific theoretical framework. A future version should engage with Toulmin's argumentation structure, Entman's framing theory, and Lakoff's conceptual metaphor theory to ground the categories more rigorously.

### 3.2 Voice classification

Documents are classified into one of five voice types based on pronoun usage, imperative density, specification patterns, and promotional marker frequency:

| Voice | Signal | Interpretation |
|-------|--------|---------------|
| Prescriptive | you-pct >= 15% + imperatives >= 2 | Tells reader what to do |
| Promotional | we-pct >= 20% OR promo markers >= 20% | Asserts value of product/org |
| Descriptive | specification patterns >= 20% | Reference catalog |
| Advisory | you-pct 5-15% | Some reader-directed guidance |
| Analytical | Residual (none of the above) | Third-person examination |

### 3.3 Temporal orientation

Past/present/future sentence ratios computed via tense marker detection. "Present" is the residual bucket for sentences with no past/future markers.

### 3.4 Epistemic basis

Per-sentence source attribution detection. Two signals: explicit source markers ("according to", "study", "research") and entity attribution ("Apple reported", "NIH announced"). Self-references ("the company reported", "we disclosed") are excluded.

### 3.5 Dismissive mention filtering

Risk and uncertainty markers are filtered for diminishing modifiers that use the vocabulary of risk to dismiss rather than analyze it. The diminisher check operates bidirectionally:

- **Pre-match window (60 characters):** Catches "minimal risks," "negligible threats," "no significant concerns." No sentence boundary restriction because a modifier preceding a risk keyword always modifies it.
- **Post-match window (same sentence):** Catches "risks are minimal," "challenges remain manageable," "concerns are largely overblown." Bounded by sentence-ending punctuation to prevent unrelated diminishers in adjacent sentences from causing false suppression.

Diminisher vocabulary: minimal, negligible, minor, few, limited, overblown, unlikely, manageable, low, slight, marginal, trivial, insignificant, immaterial, modest, remote, hypothetical, overstated, exaggerated, no real/significant/major.

**What this catches:** Lexical dismissal where a diminishing modifier directly weakens a risk/uncertainty keyword in the same sentence.

**What this does not catch:** Structural dismissal ("a substantial buffer against any challenges"), multi-clause dismissal where the risk is named in one clause and dismissed in another sentence, and euphemistic dismissal that avoids explicit diminishing vocabulary.

**Validation:** Tested against synthetic documents with pure dismissive language (correctly classified as risks-missing), mixed genuine-and-dismissive documents (genuine mentions survive, dismissive suppressed), and adversarial documents that dismiss risks using both pre-keyword and post-keyword patterns.

### 3.6 Frame suggestion rules

11 automated match rules map structural signals to FVS library
entries. Each rule specifies: which framing outputs trigger it,
what frame it suggests, and a teaching question for the reader.
Rules are structural pattern matches (hypotheses), not semantic
verdicts. Suggestions are suppressed on documents shorter than
5 sentences to avoid noise from single-keyword triggers.

**Empirical precision on external labels (external-validation
v1, 2026-04-18).** v1 rules agree with a majority-union of two
independent labelers at macro-F1 = 0.157 on a 12-document mixed-
genre corpus. Only FVS-011 Stakeholder Frame cleared F1 > 0.5
on v1; FVS-014 and FVS-016 did not fire at all. A post-audit v2
detector (`fvs_eval/validation_study/frame_library_v2.py`)
raised macro-F1 to 0.274 (+0.118) via threshold revisions on
FVS-009, FVS-014, FVS-016, and retirement of rules for FVS-001,
FVS-008, FVS-015; v2 remains below the pre-registered
falsification threshold of 0.4. Full breakdown in §2.4 and
`fvs_eval/validation_study/REPORT_V2.md`. Production integration
of v2 is paused pending curator decision on INDEX.md schema
updates for the three retired rules.

## 4. Verification methodology

### 4.1 Source Network architecture

Claims are decomposed into structured parts (subject, metric, value, unit, time period, claim type). Each claim is routed to 2-3 of 9 authoritative APIs based on domain classification. Results are aggregated via consensus.

### 4.2 Calibration

The Source Network has two calibration streams that answer
different questions:

**Coverage corpus (EXP-094, 2026 snapshot).** 45 documents, 641
total claims drawn from 5 topics (9 AI-generated analyses each).
Measures what share of realistic AI-generated claims can be
verified at all. Key findings:

- **86% of claims are unverifiable** in realistic AI-generated text
- **Wikipedia is the dominant source** for matches across all
  domains
- **SEC EDGAR is effective for annual and quarterly financial
  data** when claims have correct subject and time period
  metadata
- **BLS employment and pharmaceutical data** have near-zero
  coverage (no authoritative API for those domains)
- **The framing analysis provides value on 100% of documents**
  regardless of verification coverage

**Reliability corpus (seeded, N=33, 2026-04-17 latest run).**
Per-provider precision, recall, and F1 against a seeded corpus
of 33 claims across 7 providers with independently-re-derivable
ground truth (primary-source URLs are part of the corpus). Each
claim carries an expected verdict (`verified`, `close`,
`contradicted`, `unverifiable`) and a category
(`KNOWN_TRUE`, `KNOWN_FALSE`, `OUT_OF_COVERAGE`, `TEMPORAL_EDGE`).
The harness (`calibration/run_calibration.py`) submits each
claim through the live Source Network and computes confusion
matrices. Current tier assignments (2026-04-17 run,
`calibration/results/2026-04-17-full-with-wiki/`):

| Provider | F1 | Tier |
|----------|---:|------|
| SEC EDGAR | 1.00 | strong |
| World Bank | 1.00 | strong |
| Wikipedia | 0.89 | strong |
| REST Countries | 0.86 | strong |
| Alpha Vantage | 0.67 | moderate |
| FRED | 0.50 | weak |
| Wolfram Alpha | 0.50 | weak |

The tier assignments surface in the UI trust meter via the
reliability-tier weighting discipline (§7.2 below). The seeded
corpus is intentionally small (N=33) so ground truth can be
manually verified per claim; an expanded corpus is queued
follow-up work. The N=33 floor means per-provider N ranges
from 4 to 6, giving wide confidence intervals on individual
F1 values; tier assignments are the load-bearing output rather
than the absolute F1 numbers.

The two streams answer different questions and should not be
conflated: EXP-094 measures how much verification coverage the
Source Network provides on in-the-wild AI output (low, at 14%);
the seeded corpus measures how accurate each provider is on
claims that DO route to it (variable per provider, tier-
categorised). A reader evaluating whether a specific
Frame Check verdict is trustworthy wants the second number,
scoped to the provider that produced the verdict.

### 4.3 Known limitations

- Subject extraction fails on bold-markdown bullet lists (common AI output format)
- Date-component numbers (27 from "December 27") can produce false positive Wikipedia matches
- Non-English content has near-zero coverage
- Time-sensitive claims for future periods produce no results

## 5. Structural detection validation

Two validation studies have been completed and report different
things. §5.1 through §5.4 describe the controlled frame-
transformation study (the instruments respond to frame changes
in the way frame theory predicts). §5.2 describes the external
validation study (the detector's labels against independent
labelers). The two studies answer different questions and
produce different verdicts; both must be read to understand
what Frame Check's detector is and is not.

### 5.0 Controlled frame-transformation study

The controlled study validated that the structural detection
methodology is *responsive to frame changes*: the same data
rewritten from different analytical frames produces measurably
different structural profiles.

### 5.1 Methodology

Five scenarios were tested across 2 documents (financial: NVIDIA fiscal report; health/pharma: GLP-1 market analysis), 2 frame pairs (Growth to Risk, Growth to Stakeholder), and 1 consistency check (same document rewritten twice). For each scenario, an LLM (Grok) was prompted to rewrite the document from the target frame using the generation affordances defined in the corresponding FVS entry, preserving all data points. The framing analysis pipeline was then run on both the original and reframed document, and the structural delta was computed.

### 5.2 Results

All 5 scenarios produced measurable structural shifts across 3 or more of 6 dimensions.

| Dimension | Shifted in N/5 | Interpretation |
|---|---|---|
| Coverage (categories gained/lost) | 5/5 | Different frames emphasize different analytical categories |
| Density (markers per 1Kw) | 5/5 | Frame determines depth of attention to each dimension |
| Frame suggestions | 5/5 | Different structural profiles trigger different named frames |
| Temporal orientation | 4/5 | Some frames shift time perspective (risk = more present) |
| Hedging | 3/5 | Risk frame decreases hedging; stakeholder frame increases it |
| Voice | 1/5 | Voice rarely shifts because most frames can be expressed analytically |

Consistency across stochastic LLM outputs: 5/6 dimensions agreed between two independent rewrites of the same document.

### 5.3 What the controlled study validates

The structural detection instruments (coverage, density,
temporal, voice, epistemic, frame suggestions) can distinguish
documents that present the same data from different analytical
frames. This is evidence that the instruments respond to
structural framing differences, not only to surface text
features.

### 5.4 What the controlled study does not validate

- Semantic framing detection (still out of scope)
- Whether the named frames in the FVS library are the right
  taxonomy
- Whether users find the structural delta meaningful
- Whether the rewrite itself is high quality (the LLM may
  introduce artifacts)
- Whether the detector's named-frame labels match what
  independent readers see when they label the same documents.
  (This is the claim §5.2 below tests, with a different outcome.)

### 5.2 External validation study (detector-vs-labeler agreement)

The external validation study asked a different question: when
the detector fires and labels a document with a specific FVS
entry, does that label match what independent labelers see
when they label the same document from the FVS library
reference?

**Design.** Pre-registered in `fvs_eval/validation_study/DESIGN.md`.
12 documents across 3 strata (human-authored public, fresh
AI-generated, Wikipedia encyclopedic). Three labelers: curator,
LLM-judge (Claude Sonnet 4.6 at temperature 0.0 with FVS library
reference in prompt), detector (`frame_library.suggest_frames`).
Pre-registered falsification threshold: macro-F1 < 0.4 fires H3
and triggers project-pivot.

**Result.** Macro-F1 of detector against majority-union of
(curator, LLM-judge) = 0.157. Pre-registered threshold of 0.4
not met. H3 fired. Macro-kappa detector-vs-curator = +0.031;
detector-vs-LLM-judge = -0.008 (both chance-level).

**Interpretation.** Per the pre-registered design, this is a
falsification of the strong claim that the detector labels
match labeler judgment. It is not a falsification of the
controlled frame-transformation validation in §5.0 through
§5.4; those remain accurate at what they validated. The
reconciliation: the detector responds to frame-structural
changes (the controlled study), and the detector's labels do
not reliably match labeler judgment (the external study). Both
can be true because the former measures *responsiveness to
change* and the latter measures *absolute label agreement*.

**The operational consequence.** See §2.4. The detector's
named-frame output in the product surface should be read as
"this document exhibits the pattern that historically
correlates with frame X" rather than "this document is a case
of frame X." The teaching questions attached to each suggestion
retain their value as reader affordances; the classification
value is the part the study places under question.

**Follow-up work.** REPORT.md §8 names the sequence: per-frame
rule audit, expansion of the validation corpus to 30-50
documents with independent human annotators, update of
strategic documents to reflect the gap. This methodology
document records the finding; the product-surface and strategic-
document updates are separate commits.

## 6. Evidence discipline

Frame Check follows the evidence discipline established in EXP-094:

- Every metric names what it actually measures, not what we want it to measure
- Every finding has a "what this does not claim" disclosure
- Every limitation is published at the same prominence as the findings
- The falsification record is public (48+ overturned hypotheses)
- Quarterly retro audits are calendared at phase boundaries

Two concrete applications of this discipline are visible in the product surface:

1. **Verifier blindspots on the about page.** The `/about` page names five specific failure modes of the verification engines: semantic fabrication with sourced vocabulary, paraphrase that defeats substring matching, derivation correctness beyond the patterns checked, entities outside the source network, and intent vs. structure. Each is stated at the same visual weight as the tool's positive claims. See [templates/about.html §"What Frame Check cannot detect"].

2. **Verbosity-sensitivity disclosure in the trust meter.** The meter displays verified/contradicted/unchecked as a ratio of total claims. A ratio says nothing about the denominator. The results page renders the document's claim density ("X claims per 1,000 words") adjacent to the meter with a caveat: comparing documents is meaningful only between texts of similar density. See `formatter.py:compute_verdict` for the computation and `templates/results.html` for the rendering.

3. **Measured-cost telemetry in the corpus** (§7.1 below). Cost is reported from token counts, not from estimates.

All three are the same move: surface the denominator, name the failure mode, publish the number you measured rather than the one you hoped to measure.

### 6.1 What Frame Check does not detect

- Semantic framing (selective emphasis, motivated reasoning, rhetorical devices)
- Causal validity (whether stated causes are actually causal)
- Source quality (whether cited sources are credible or cherry-picked)
- Reasoning quality (whether conclusions follow from premises)
- Intent (whether framing is deliberate or unconscious)
- Fixed-point confabulation (AI producing the same wrong number consistently)

## 7. The Observatory

The Frame Check Observatory continuously measures how AI models frame reality on a controlled set of topics. Version 1 has 21 active topics across financial, scientific, health, geopolitical, and evergreen domains, running against Gemini and Grok. Operational status in production has not been independently verified.

The Observatory produces:
- Per-topic, per-model structural framing fingerprints
- Verification verdicts against authoritative sources
- Stability measurements across regenerations
- Longitudinal drift data as models are updated

The corpus is published under CC-BY-4.0 at corpus.clarethium.com.

### 7.1 Cost transparency

Two surfaces contribute cost data to the Frame Check Corpus:

1. **Primary analyses.** Every `analysis_completed` Tier A event (the `/profile` endpoint and the document-mode `/compare` endpoint) carries a `cost.total_usd` field populated from the pipeline's measured token usage. Gemini grounding uses a flat per-request rate; Gemini generation and Grok generation use token counts extracted from the provider's own usage metadata and multiplied against a versioned pricing table.

2. **Observatory runs.** Every `observatory_model_response` Tier B event carries `response_token_count_input`, `response_token_count_output`, and `response_cost_usd` for each model invocation, computed the same way.

Secondary, user-triggered LLM endpoints (`/api/ai-interpret`, `/api/reframe`, `/api/compare-framing`, `/api/stability-check`) measure cost at call time and charge it against local rate-limiting gates, but do not currently emit a dedicated corpus event. That is a known scope limit, not a design claim: extending the corpus schema to include these calls is queued follow-up work so that the "every LLM call" version of this claim can hold literally.

The Tier A schema also carries `verification.by_entity_type`, a histogram of how many Source Network verdicts in an analysis belonged to each entity type (company, country, crypto asset, unknown). The histogram is aggregate only; individual claim subjects and their canonical forms are never recorded. The field exists so corpus queries can split per-source reliability by the kind of subject the claim was about, which is the form of calibration question §7.2 describes.

The design choice follows from the research purpose of the corpus: a researcher picking up the NDJSON dump in a year should be able to ask "what did this cost" and get a real answer, not a footnote saying the numbers were approximated. Token counts are the primary signal, cost is the derivation. When provider prices change, anyone with access to a historical dump and a new pricing table can re-derive cost without re-running a single claim.

This is a deliberate position: verification tools that report fabricated statistics about their own operation are in no position to audit anyone else. Frame Check instruments itself with the same calibration discipline it applies to its subject matter. `llm_cost.py` is the single source of truth for pricing; `charge_cost_gates` is the single choke point through which every LLM cost passes into the rate-limiting gates. If the cost number in a primary or observatory corpus event is wrong, exactly one table is wrong.

The pricing table, the extraction functions, and the compute path are source-visible. The Phase 1.10 sanity check reconciles measured cost against the prior estimates to validate that instrumentation is operating end-to-end.

### 7.2 Per-provider verifier calibration

The Source Network is the production primary verification path. Nine providers (SEC EDGAR, FRED, REST Countries, World Bank, CoinGecko, Alpha Vantage, Wolfram Alpha, Wikipedia, Brave Search) each handle different claim types against different authoritative databases with different confidence thresholds. Historically none of them had been measured against an external known-truth corpus (see `REFINEMENT_AUDIT.md:113-137`); "this source said verified" is an opaque signal without per-provider precision and recall numbers to calibrate the prior likelihood of the claim being correct.

Frame Check now ships a calibration corpus and harness at `calibration/`:

- `calibration/source_network_corpus.yaml`: seed set of 27 claims across 6 providers. Each claim names a primary source, an as-of-date, an expected verdict, and a category (`KNOWN_TRUE`, `KNOWN_FALSE`, `OUT_OF_COVERAGE`, `TEMPORAL_EDGE`). Ground truth is independently re-derivable from the primary source URL.
- `calibration/run_calibration.py`: harness that submits each claim through the live Source Network, collects the observed verdict, and writes a per-provider confusion matrix plus precision, recall, and F1 to `calibration/results/<date>/`.
- `calibration/README.md`: methodology, provider status, extension protocol.

Per-provider reliability tiers will surface in the UI once the first calibration run lands a report. Shipping UI badges before the data exists would replicate the bug this discipline is designed to fix: opaque confidence without calibration.

Three providers are deliberately unseeded in v0.1. Wikipedia (high ambiguity in ground truth because articles themselves drift), CoinGecko (spot-price volatility requires a narrow as-of-date protocol), and Brave Search (fallback-only, tested indirectly through cross-provider cases) each need category-specific methodology before calibration is meaningful. That work is queued, not lost.

### 7.3 Entity-type routing discipline

A verification system that routes by regex features of the subject string (is it capitalized, does the sentence contain financial keywords) will misroute claims whose string features match multiple entity categories. The first calibration run surfaced this failure mode directly: a macroeconomic claim about "US national debt" was routed to SEC EDGAR and returned an unrelated US-suffixed filing, producing a `disputed` consensus verdict when the claim was in fact true. See `calibration/results/2026-04-16-first-run/FINDINGS.md` category B.3.

The structural response was to add a first-class subject classifier (`entity_classifier.py`) that answers "what kind of subject is this?" with a stable enum (COMPANY, COUNTRY, CRYPTO_ASSET, UNKNOWN) and to route off the answer. The router gates the company-focused verifiers (SEC EDGAR, Alpha Vantage) on the classification. A country or crypto subject cannot reach company verifiers regardless of capitalization or keyword heuristics. Unknown subjects (private companies, non-US entities, historical figures, abstract concepts) still flow through the keyword heuristic so their legacy SEC attempts remain; unresolvable SEC queries return `no_data` and the corpus records that honestly.

Each classification carries a stable reason slug (`country_alias_match`, `crypto_name_match`, `sec_cik_resolved`, `no_rule_matched`, `empty_subject`) and the canonical form of the subject. The corpus Tier A event schema (§7.1) carries `verification.by_entity_type`, an aggregate histogram of how many verdicts in an analysis belonged to each type. Per-entity-type precision and recall queries against the corpus NDJSON are therefore first-class; "what is Source Network's F1 on COUNTRY claims versus COMPANY claims?" is a question the corpus can answer.

The classifier is strictly additive to the historical routing: verifiers that were previously keyword-driven (World Bank, REST Countries, FRED, Wolfram) still trigger on sentence content. The classifier adds a gate on the company-focused verifiers only. This deliberate asymmetry (subject-only classification for negative gates, sentence-wide detection for positive macro routing) is documented in the RUNBOOK alongside the structural justification so the next engineer inherits the decision rather than reverse-engineering it.

### 7.4 Time-scope routing discipline

A verification system that falls back to adjacent-period data when the claim's specific period is unavailable will produce false contradictions. The first calibration run surfaced this directly: a Q4 2023 quarterly claim was matched against the company's annual FY2023 revenue (a different period entirely) and received a `contradicted` verdict with a 284% diff. See `calibration/results/2026-04-16-first-run/FINDINGS.md` category B.1.

The structural response parallels §7.3: a first-class time-scope classifier (`time_context.py`) that answers "what time period does this claim refer to?" with a stable enum (ANNUAL, QUARTERLY, RANGE, CURRENT, HISTORICAL, UNKNOWN) and typed numeric fields for year, quarter, and year-range. The router attaches the classification to `ClaimDecomposition`. Verifiers consult it.

The effect on specific verifiers:

- **SEC EDGAR** filters 10-Q for QUARTERLY claims and returns `no_data` when quarterly data is unavailable, rather than falling back to 10-K and misusing annual data as contradiction evidence. Honest "unverifiable" beats confident wrong.
- **REST Countries** returns `no_data` for HISTORICAL claims rather than matching current population against a historical year (which can produce coincidental verifications that look real but aren't).
- **Future verifiers** register against period types at add-time; routing is declarative, not regex-inferred.

Each classification carries a stable reason slug (`quarterly_q_notation`, `quarterly_spelled_out`, `annual_fy_notation`, `annual_bare_year`, `range_between`, `range_dash`, `current_marker`, `historical_old_year`, `no_time_anchor`, `empty_input`). The corpus Tier A event schema carries `verification.by_time_context`, a fixed-key histogram parallel to `verification.by_entity_type`. Per-time-scope precision and recall queries against the corpus NDJSON are therefore first-class; "what is Source Network's F1 on QUARTERLY claims versus HISTORICAL claims?" is now a question the corpus can answer.

The typed-claim-semantics discipline (EntityType for subjects, TimeContext for periods) establishes a foundation other verifier additions can build against. Every future verifier registers with {entity types it handles, time scopes it handles} and gets routed correctly by construction rather than by keyword heuristic.

## 8. Relationship to existing work

Frame Check sits at the intersection of three research programs. The honest positioning is that it borrows operationalizations from each and combines them into a different deliverable: a deterministic, citable, structural framing layer that ships under the agent at the moment of the conversation, with explicit construct-honesty for what each signal does and does not measure.

**Framing theory and computational framing analysis.**
- **Entman (1993), "Framing: Toward Clarification of a Fractured Paradigm":** the five coverage categories are an operationalization of "salience" in Entman's framework, restricted to a closed vocabulary that makes detection deterministic.
- **Lakoff (2004), Don't Think of an Elephant:** the FVS library entries are concrete instances of Lakoff's "frames" applied to AI output rather than political discourse.
- **LIWC (Pennebaker et al. 2015) and dictionary-based text analysis:** Frame Check's coverage and voice signals are dictionary-and-pattern based in the same family. The evidence discipline (Section 6) is the explicit acknowledgement that this family measures vocabulary, not meaning, and the v2 contract (under-detection, classification-confidence, distribution-with-dominant) is the load-bearing addition.
- **Card et al. (2015), "The Media Frames Corpus":** annotated framing in news; Frame Check's worked-examples corpus is smaller, slug-addressed, and applied to AI-generated rather than journalistic text.

**Hallucination detection and grounded generation.**
- **SelfCheckGPT (Manakul et al. 2023):** consistency-based hallucination detection. Frame Check's temporal-consistency check is related; the framing layer is distinct and the verification layer is provider-grounded rather than self-consistency-based.
- **FActScore (Min et al. 2023):** fine-grained factuality scoring against a knowledge source. Frame Check's verification layer (Layer 4 source fidelity, Layer 11 grounding decomposition) is in the same family but scope-regime-aware: the methodology explicitly disables Layer 11's primary signal on number-saturated sources rather than reporting it with miscalibrated confidence.
- **RAG evaluation literature (RAGAS, ARES):** focused on retrieval+generation pipelines. Frame Check assumes the document already exists and asks what frame it carries; the verification layer is a checker, not a retriever.

**Decision quality and structured deliberation.**
The decision-readiness profile (currently labelled experimental, methodology published at (production paused), gated on the Phase 2 rater study described in `RATERS.md`) draws on a separate literature.
- **Kahneman, Sibony, and Sunstein (2021), Noise:** distinguishes bias (consistent error) from noise (variance across decisions). Frame Check measures structural framing as a partial input to decision quality, not the decision itself.
- **Russo and Schoemaker, Decision Traps:** taxonomy of recurring decision-process failures (overconfidence, frame blindness, plunging in). The five readiness dimensions (coverage, calibration, evidence, robustness, counterfactual) are an attempt to make some of these failures detectable in the document the decision rests on, not in the decision-maker's reasoning.
- **Tetlock and Gardner (2015), Superforecasting:** calibration as a measurable property of forecasts. Frame Check's calibration dimension is a structural cousin: it asks whether the document's claims carry the hedging the underlying evidence would warrant, not whether a specific forecast resolved correctly.

**Frame divergence as the AGI-era primitive for perspective expansion.** Frame divergence is the category Frame Check claims: naming frames a document could have used but did not, with faithfulness constraints so surfaced absences carry citation (`citation_uri` to the FVS entry) and do not become prescription (divergence never tells the user which frames they should have used). It is composed of three elements already in this methodology: the FVS library (Section 2) as the catalog from which absences are computed, the V4.2 judge engine as the measurement primitive that distinguishes "not detected by rules" from "actually absent," and the evidence discipline (Section 6) that bounds the absence claim faithfully. The canonical references are `FRAME_DIVERGENCE_v1.md` (Part 1, category definition and non-negotiables), `FRAME_DIVERGENCE_CONTRACT_v1.md` (Part 2 c1.0, interface contract for the `divergence` block inside `frame_check` output), and `FRAME_DIVERGENCE_v2.md` (the layered architecture spec shipped 2026-04-25 that absorbs v1's narrow definition into a wider taxonomy and lifecycle: five layers, five-stage lifecycle, nine cross-cutting design principles, seven falsifiable predictions, and §11 catalog discipline as the primary empire moat per Principle P5; v1 c1.0 contract carries forward into v2 unchanged for backward compatibility). The paper-shaped extract for citation is `FRAME_DIVERGENCE_v2_SUMMARY.md`. The MCP surface exposes divergence with zero Frame Check LLM cost by delegating V4.2 judgment to the caller's agent model; the web surface runs V4.2 server-side with rate-limited opt-in. The engineering status of V4.2 is disclosed per `V4_2_GAP_INVENTORY_v1.md §5` (current: `V4.2-beta`) so consumers see the gap state at invocation time.

What Frame Check is not. It does not classify documents as biased or balanced (that is the agent_guidance prohibition). It does not measure ground truth in the way fact-checkers do (verification is bounded to providers with genuine coverage; everything else is `unverifiable`). It does not produce decision recommendations (the readiness profile names structural gaps, not what to do about them). The category Frame Check is in is "make the frame visible to the user at the moment of the conversation," and that category is close to empty in the literature surveyed above.

## 9. Citation

If you use Frame Check or the FVS library in research, please cite:

```
Lucic, L. (2026). Frame Check: Computational framing analysis for AI-generated text.
Frame Check Methodology v0.2.0. https://corpus.clarethium.com/frame-check/methodology/
```

## 10. Contact

hello@clarethium.com
