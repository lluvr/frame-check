# Methodology Paper Outline v1

**Status:** outline v1, 2026-04-20. Preparation for external-audience publication of Frame Check's methodology. Venue and authorship shape are open questions the outline names rather than resolves. Submission is gated on (a) curator venue decision, (b) Track B reader-aid study results (if the paper claims reader-aid value rather than methodology alone), (c) curator editorial review.

**Purpose:** convert the project's shipped work into a paper structure an external audience can read. The outline enumerates sections, contribution statements, key figures, related-work anchors, and honest-limits. A full draft follows once curator approves structure + venue.

**What exists as spine for each section:** pointers throughout to the shipped artifacts (METHODOLOGY.md, VISITOR_AUDIT.md, CANDIDATE_MISS_REPORT.md, FVS_COACTIVATION_REPORT.md, MCP_CONTRACT_V2_PROPOSAL.md, validation_study/REPORT_V3_TRACK_A.md, reader_aid_study/DESIGN_v1.1.md).

---

## 1. Target contribution (the paper's claim)

**Primary claim.** Structural framing analysis tools report signals with regex-null or classification-threshold outputs that readers systematically over-interpret. We introduce a construct-honest posture that operationalizes under-detection (for presence/absence signals) and classification-confidence (for categorical signals) at sentence granularity, shipped through both a web product and an MCP contract, measured empirically on a stratified 28-document corpus. The posture makes the reader-aid use case inspectable per-sentence rather than paragraph-aggregate.

**Structural novelty.** No prior structural-framing tool (Media Frames Corpus, FrameAxis, LIWC, MoralFoundations, Readability/Flesch) ships real-time sentence-level attribution paired with per-signal construct-honesty surfacing. The combination of five-signal construct treatment (coverage + epistemic + claims under the under-detection construct; voice + temporal under classification-confidence) is, to the best of the authors' knowledge, novel.

**Empirical contribution.** Under-detection prevalence measured on the N=28 validation corpus: coverage candidate-miss surfaces on 36% of documents (10/28); epistemic candidate-attribution on 11% with corpus-wide ratio 0.405 of candidate-to-primary; claims candidate-hedge on 1/18 documents with claims (limited by corpus composition). Co-activation findings: FVS-007 / FVS-008 co-fire at Jaccard 0.73; FVS-009 / FVS-012 at 0.67.

---

## 2. Proposed structure

Eight sections. Length targets assume a CSCW/CHI-style paper (~8-10k words); can compress to an arXiv preprint (~5-7k words) or expand to a journal paper (12-15k words).

### §1 Introduction (~800 words)

- Problem: structural framing tools report with false certainty. "Does not address X" / "unsourced" / "analytical voice" are existential claims the detector cannot fully support.
- Concrete failure motivation: the VISITOR_AUDIT semiconductor-essay case (primary detector reports "does not address causes/trends" on a document that plainly addresses both via vocabulary the regex does not recognize).
- Contribution summary (three bullet points mapping §1 claims).
- Paper structure preview.

Source material: `VISITOR_AUDIT.md §4 Failure 1, §4 Failure 3`; `METHODOLOGY.md §1.3`.

### §2 Related work (~700 words)

- Framing effects: Entman 1993 (selection/salience), Iyengar 1991 (episodic/thematic), Chong and Druckman 2007, Scheufele and Iyengar 2014.
- Computational framing: Media Frames Corpus (Card et al. 2015), FrameAxis (Mokhberian et al. 2020).
- Related text analytics: LIWC (Pennebaker), MoralFoundations (Frimer et al.), Readability (Flesch, Dale-Chall).
- Construct-honesty / measurement-theory precedent: MacKenzie et al. 2011 ("Construct validity measurement"), Jacobs and Wallach 2021 ("Measurement and Fairness").
- Gap: none of the above ships real-time sentence-level attribution + per-signal construct-honesty surfacing + citable named-frame library. Frame Check's contribution occupies that gap.

Source material: `fvs_eval/reader_aid_study/DESIGN_v1.1.md §1a`.

### §3 The Frame Vocabulary Standard (~900 words)

- Library structure: 20 entries, canon trajectory, per-entry detection rule + worked example + teaching question + adjacency.
- Entry shape: ID, version, curator, date, identification, visible/invisible, examples, adjacency, honest limits, decision-readiness implication.
- Library governance: GOVERNANCE.md v0 (single-curator state), REVIEWERS.md external invitation, INDEX.md five-criterion promotion gate.
- Library-side empirics: `FVS_COACTIVATION_REPORT.md` activation counts on N=28 corpus. 10/20 entries fired; 11/20 never fired (classified as intentional-no-rule, missing-rule, or threshold-too-high in `DETECTION_RULE_AUDIT_v1.md`).
- Strongest co-activation pairs: FVS-007 / FVS-008 (Jaccard 0.73); FVS-009 / FVS-012 (0.67).

Source material: `data/frame_library/INDEX.md`, `data/frame_library/FVS-*.md`, `fvs_eval/FVS_COACTIVATION_REPORT.md`, `fvs_eval/analyze_fvs_coactivation.py`.

### §4 The construct-honesty posture across five signals (~1800 words)

Core methodological contribution. One subsection per signal; each states the construct, the posture's operationalization, and the empirical prevalence.

#### §4.1 Coverage (under-detection construct)

- Signal: 5 analytical dimensions (causes, risks, stakeholders, trends, uncertainty), vocabulary-and-pattern based regex per dimension.
- Construct: `not_detected` is a lower-bound claim about detection, not an upper-bound claim about the document. Under-detection is a known failure mode.
- Operationalization: per-dimension `candidate_sentences` (secondary regex CANDIDATE_PATTERNS targeting semantic hints the primary regex misses: "rationale centers on," "restructuring," "diversification," "observers raise"). Explicit caveat attached per sentence. MCP contract emits the structure; web product renders sentences under the Analytical Coverage card.
- Empirical: coverage candidate-miss surfaces on 36% of 28 corpus documents; per-dimension under-detection rates range from 0% (trends) to 33% (uncertainty).

#### §4.2 Epistemic (under-detection construct)

- Signal: source-attribution detection via `_SOURCE_RE` + entity-reporting-verb pattern.
- Construct: primary regex misses scholarly passives and citation formats. `sourced_pct` is a lower-bound claim about attribution-marker density.
- Operationalization: `candidate_attribution_sentences` via `EPISTEMIC_CANDIDATE_ATTRIBUTION` regex targeting "observers raise," "analysts argue," "some have argued," bracketed citations, parenthetical citations, data-source references.
- Empirical: 11% of corpus documents surface at least one candidate-attribution sentence; corpus-wide candidate-to-primary ratio of 0.405.

#### §4.3 Claims hedging (under-detection construct)

- Signal: hedging detection via `HEDGE_RE` (approximately, may, might, could, possibly, potentially, etc.).
- Construct: primary regex misses academic/conditional/scholarly-soft hedges ("arguably," "broadly speaking," "subject to," "in principle," "tentatively," "on the order of").
- Operationalization: `CANDIDATE_HEDGE_RE` per-claim surfacing; `candidate_hedge_marker` field on each stated-as-fact or prediction claim when the candidate regex fires. Explicit caveat.
- Empirical: 1/18 corpus documents with claims surface a candidate-hedge (low because corpus uses primary HEDGE_RE forms). Validated behavior on synthetic scholarly-hedge documents.

#### §4.4 Voice (classification-confidence construct)

- Signal: 5-class voice cascade (prescriptive / promotional / descriptive / advisory / analytical) via threshold rules on `you_pct`, `we_pct`, `imperative_count`, `spec_pct`, `promo_pct`.
- Construct: classification is cascade-first-match; a document at you_pct=14 is analytical, at you_pct=15 is prescriptive. The Fix A under-detection construct does not apply (no not_detected state). The analogous posture for classification signals: expose margin.
- Operationalization: `_voice_cascade_eval` returns per-rule fire state and margin-to-threshold. `margin_to_threshold` is the best margin across firing rules of the winning class (decisively-crossed threshold if any rule fires clearly). `runner_up` and `runner_up_margin` name the next cascade class and its best rule margin. `confidence` flag: "borderline" when winner margin or runner-up margin is within 2 percentage points of flipping.
- Empirical: measured on N=28 corpus. Distribution of borderline vs high-confidence classifications (supplementary figure).
- **Threshold-dependency qualifier** (2026-04-20 per `THRESHOLD_SENSITIVITY_v1.md §2.1, §2.5`): the 3.6% borderline rate on N=28 is coupled to the rule-6 advisory threshold (`you_pct >= 5`). 20 of 28 documents have `margin_to_threshold == 5.0` exactly (residual-analytical fall-through when `you_pct = 0`); shifting `_VOICE_BORDERLINE_MARGIN` from 2 to 6 flips the rate from 3.6% to 75%, and shifting `r6_threshold` from 5 to 1 produces the same flip at the shipped T=2. The 3.6% headline is NOT a robust instrument property; it is conditional on both thresholds. Paper must cite this qualifier.
- **Open construct-design issue.** The residual-analytical case inherits `margin_to_threshold = r7_margin = distance of nearest competitor from firing` while the firing-rule case uses `margin_to_threshold = distance above firing threshold`. Both are informative but semantically distinct; the shipped `confidence` label conflates them. `THRESHOLD_SENSITIVITY_v1.md §5 R1` names three design responses (new residual-confidence state; normalize by competitor threshold; document the coupling in `how_to_serialize`); decision curator-gated.

#### §4.5 Temporal (distribution-margin construct)

- Signal: past/present/future percentages of sentences.
- Construct: dominant tense label can mislead on distributions where two tenses are nearly tied.
- Operationalization: `dominant_margin` (dominant_pct - runner-up_pct); `balanced` flag when no tense reaches 50% and margin < 10.
- Empirical: corpus distribution of margins + balanced-flag rate.
- **Threshold-dependency qualifier** (2026-04-20 per `THRESHOLD_SENSITIVITY_v1.md §2.2-2.3, §2.6-2.7`): the 0% balanced rate on N=28 is a property of corpus composition, not the instrument. Every N=28 document has `max_pct >= 50`, so the 50% gate intercepts every case and the margin threshold does no work. The margin-only rule (`margin < 10`, gate removed) flags 1 document on the same corpus (c05_wikipedia_nuclear_fusion at max=54, margin=8). The shipped conjunction is over-specified on sums-to-100 distributions: on those, `margin < 10` alone produces identical behavior except in the narrow band `max ∈ [50, 55)` where the margin can still be small. Paper should cite 0% balanced rate with "on this corpus" qualifier, not as instrument behavior.
- **Open construct-design issue.** The strict-inequality 50% gate creates a discontinuity at exactly 50: 49/49/2 flags balanced, 50/50/0 does not, despite both being intuitively balanced. `THRESHOLD_SENSITIVITY_v1.md §2.7` lays out four alternatives (inclusive boundary, drop the gate, soften the gate, continuous score) with Alt B (drop the gate) argued as principled and the least-change option. Decision curator-gated.

### §5 Measurement and reproducibility (~800 words)

- Reproducible scripts: `fvs_eval/measure_candidate_miss.py`, `fvs_eval/analyze_fvs_coactivation.py`. Both deterministic; bit-identical output on the same corpus.
- MCP contract versioning: `MCP_CONTRACT_V2_PROPOSAL.md` documents the payload shape, phased migration, backward compatibility.
- Test coverage: 312 tests (as of 2026-04-20) pinning the construct-honesty surfacing end-to-end (detection layer + web template + MCP payload).
- Data availability: validation corpus CC-BY-4.0, code Apache-2.0, documentation CC-BY-4.0.

### §6 Validation

Two paths; venue shapes the choice.

#### §6a Classifier validation (Track A, already complete)

- Pre-registered study at `fvs_eval/validation_study/DESIGN.md`.
- Result: macro-F1 of 0.36 on N=28 corpus with curator + LLM-judge labels.
- Honest framing: below pre-registered 0.4 threshold. v3 signal additions brought F1 from 0.157 (v1) through 0.274 (v2) to 0.36 (v3); further F1 gains at the rule level appear exhausted. Paper reports this honestly.
- Construct-honesty interpretation: F1 below threshold motivates the shift from classifier-accuracy claim to construct-honest-detection claim. The paper frames this as a methodological pivot, not a retreat.

#### §6b Reader-aid validation (Track B, pre-registered, awaiting execution)

- Pre-registration: `fvs_eval/reader_aid_study/DESIGN_v1.1.md` with OSF-standard content in `OSF_SUBMISSION.md`.
- Hypothesis: readers shown Frame Check's output produce more distinct framing observations than readers who do not (H1; effect size >= 1.5; one-sided alpha=0.05).
- Study shape: within-subjects split-half, N=30-50 via Prolific, two-coder rubric with kappa >= 0.6 gate.
- Status at paper-draft time: paper may draft before or after Track B. If before, §6b reports pre-registration content + null-result publication commitment. If after, §6b reports results per §11 decision rules.

### §7 Limitations and honest limits (~600 words)

Paper enumerates honest limits at the same prominence as findings, per the project's evidence discipline. Draft candidates:

- Corpus N=28 is small; per-dimension rates are directional.
- Stratified corpus composition is deliberately not representative; results don't predict general-population rates.
- Candidate-miss regexes are conservative and false-positive-accepting by design; prevalence measurements do not equal correctness rates.
- Candidate-vs-primary ratios treat candidates as informationally equivalent to primary, which they are not; reader judgment is load-bearing.
- Voice/temporal classification confidence depends on feature-threshold-crossing; does not capture semantic uncertainty within-class.
- **Voice borderline rate is threshold-coupled.** `_VOICE_BORDERLINE_MARGIN = 2` and rule-6 advisory threshold (`you_pct >= 5`) jointly determine the 3.6% borderline rate on N=28. Shifting either independently swings the rate from 0% to 75% (`THRESHOLD_SENSITIVITY_v1.md §2.5`). Paper reports the rate with the coupling qualifier.
- **Temporal balanced rate is corpus-dependent, not instrument-dependent.** 0% balanced on N=28 is because every corpus document has `max_pct >= 50`; the 50% gate intercepts every case. On corpora with mixed retrospective-prospective analysis, the balanced region would populate. The shipped conjunction is over-specified on sums-to-100 distributions (`THRESHOLD_SENSITIVITY_v1.md §2.6-2.7`).
- Library is single-curator-authored; inter-rater reliability data is zero at paper-draft time.
- Track B under-powered at N=30 (~55% at d=0.5).
- Tools are English-only.

### §8 Conclusion (~400 words)

- Restatement of contribution.
- Future work: Track B execution, reader-aid follow-up studies, FVS library external review, corpus expansion, cross-model framing cartography.

---

## 3. Key figures

Six candidate figures; pick 3-5 depending on venue page budget.

**F1. Construct-honesty posture across five signals.** Table with signal / construct / operationalization / empirical prevalence. High-information; anchors §4.

**F2. Coverage candidate-miss per-dimension.** Bar chart with under-detection rates per dimension (causes: 7.7%, risks: 9.1%, stakeholders: 20.0%, trends: 0%, uncertainty: 33.3%).

**F3. Epistemic candidate-attribution scatter.** Primary sourced_pct x axis, candidate_attribution_count y axis; one point per document. Shows correlation pattern.

**F4. FVS co-activation matrix.** Heat map of the 20x20 co-activation matrix from `FVS_COACTIVATION_REPORT.md`. Shows empirical adjacency graph.

**F5. Voice-confidence histogram.** Distribution of `margin_to_threshold` values across corpus; x-axis margin, y-axis count, with borderline threshold marked.

**F6. Before/after posture example.** Side-by-side rendering of the VISITOR_AUDIT semiconductor case with pre-Phase-A output ("does not address causes") vs post-Phase-A output ("low structural coverage of causes; 2 candidate sentences inspect"). Anchors the contribution narrative.

Source data for all figures is already generated by the shipped scripts; the figure-drafting step is matplotlib/ggplot work, not new analysis.

---

## 4. Venue options

**arXiv preprint (cs.CL or cs.HC).** Free, fast, permanent DOI. Low peer-review bar. Suitable if the paper goal is fast citation of the methodology posture. Does not count toward academic credentials for some evaluators.

**CHI (Conference on Human Factors in Computing Systems).** Peer-reviewed, high-prestige HCI venue. Fit: if paper leads with reader-aid framing (requires Track B results). Submission deadline pattern: September (for next-year May conference). 10-page format.

**CSCW (Computer-Supported Cooperative Work).** Peer-reviewed, closely adjacent to CHI. Fit: strong if the paper claims reader-aid-in-collaborative-reading value. April and October submission deadlines.

**JASIST (Journal of the American Society for Information Science and Technology).** Peer-reviewed journal. Fit: strong for information-science / measurement-theory framing. Longer turnaround (months). Higher word budget allows full methodology treatment.

**ACL / EMNLP (NLP conferences).** Peer-reviewed, NLP-specialized. Fit: moderate; the paper's NLP component is regex-based rather than ML-heavy, which may miss the venue's typical contribution shape.

**ICLR Socially Responsible ML workshop.** Workshop-level. Fit: niche but good construct-honesty-framing fit.

**Recommendation:** arXiv preprint first (establishes priority and citation anchor), followed by CSCW or JASIST for peer-reviewed validation. CHI only if Track B runs pre-submission.

---

## 5. Authorship shape

Two open questions:
- **Solo-curator or co-authored with reviewers?** REVIEWERS.md mentions "v1 methodology paper co-authorship" as one compensation option for first-wave reviewers. If the first external reviewer (per `INVITATION_TEMPLATE.md`) accepts that option, they co-author.
- **Collaborating-agent attribution?** The collaborating AI agent (this one) contributed analysis scripts, test coverage, construct framing, and outline drafting. Attribution options: (a) acknowledgment-section only, (b) tool-use disclosure (per emerging convention for AI-assisted research), (c) co-authorship (rare, contentious).

**Curator decision required.** Neither question is mine to resolve.

---

## 6. Dependencies and sequence

- **arXiv preprint:** no dependencies beyond curator commit.
- **CSCW/JASIST/CHI:** require Track B results for the strongest claim. Paper can draft before Track B but submission should wait.
- **Figures F1-F4:** can draft now from existing scripts.
- **Figures F5-F6:** F5 requires rerunning measurement with distribution-plotting additions; F6 requires before/after screenshots from web product (Phase A is shipped, so both states are available in git history).
- **Related-work section:** needs 2-4 hours of literature collection beyond the anchors in DESIGN_v1.1 §1a.

---

## 7. Honest limits of this outline

- **Outline is preparation, not a paper.** Drafting the full paper is a separate 15-25-hour work block.
- **Venue decision deferred to curator.** The outline presents options; curator picks.
- **Track B dependency not resolved.** The outline describes two submission shapes (pre-Track-B methodology paper vs post-Track-B validated paper) without picking. Paper draft will differ materially.
- **Authorship shape deferred.** Reviewer-as-coauthor, agent-attribution, solo-authored all remain open.
- **Page-budget uncertainty.** The 8-section structure fits CSCW/CHI/JASIST but overflows a short arXiv format. Compression or expansion follows venue pick.
- **Claims not yet verified by peer review.** The construct-honesty "novel combination" claim is stated based on the authors' literature search; reviewers may identify prior work the authors missed.

---

## 8. What this outline unlocks

- **Curator venue decision:** the outline names the option space concretely so the curator can pick.
- **Figure drafting:** F1-F4 can be drafted from current scripts in a separate session.
- **Related-work expansion:** the literature anchors named here can be expanded to a full Related Work section in a separate session.
- **Full draft readiness:** when curator approves outline + venue, the eight-section drafting becomes a scoped work block rather than an open-ended writing session.

---

## 9. Cross-references

- `METHODOLOGY.md`: long-form methodology reference; the paper compresses this to §3-§5.
- `VISITOR_AUDIT.md §7 Fix A`: the posture-shift that grounds §1 and §4.
- `CANDIDATE_MISS_REPORT.md`: empirical spine for §4 under-detection numbers.
- `fvs_eval/CORRESPONDENCE_STUDY_v1.md`: AI-coder correspondence rates (50% coverage / 78% epistemic) qualifying §4.1 and §4.2 candidate-miss prevalence.
- `fvs_eval/CONSTRUCT_EMPIRICS_REPORT.md`: five-signal construct empirics spine; auto-generated from corpus.
- `fvs_eval/THRESHOLD_SENSITIVITY_v1.md`: voice-borderline and temporal-balanced threshold sensitivity (v1.1 including r6 sweep, conjunction decomposition, first-principles gate analysis). Qualifiers in §4.4 and §4.5 above are sourced from that study.
- `FVS_COACTIVATION_REPORT.md`: empirical spine for §3 library findings.
- `MCP_CONTRACT_V2_PROPOSAL.md`: contract design section (§5 reproducibility).
- `fvs_eval/reader_aid_study/DESIGN_v1.1.md`: Track B pre-registration (§6b).
- `fvs_eval/validation_study/REPORT_V3_TRACK_A.md`: Track A results (§6a).
- `DETECTION_RULE_AUDIT_v1.md`: library detection-state audit (§3).
- `ADJACENCY_RECONCILIATION_v1.md`: reconciliation proposal (references in §3).
- `OSF_SUBMISSION.md`: pre-registration submission content.

---

*v1. 2026-04-20. Outline by collaborating agent. Curator review required before drafting begins. On approval + venue pick: full draft estimated 15-25 hours. This outline preserves the construct-honesty posture at paper level: contribution statement named explicitly, honest-limits sections at the same prominence as findings, venue tradeoffs explicit rather than picked silently.*
