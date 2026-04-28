# Failure Framing

**FVS entry:** FVS-007
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12
**Source:** HI-016 (Failure Framing Asymmetry), EXP-025 (negation specificity, 2x2 factorial), EXP-017 (framing x ambiguity gradient)
**Status:** v1, single-curator, reviewers wanted

## Identification

Specifying what counts as failure constrains AI output more sharply than specifying what success looks like. "If this could apply to any company, you fail" produces more specific, differentiated output than "be specific to this company." The mechanism: concrete failure conditions narrow the unacceptable space precisely, while success conditions leave the acceptable space vaguely open. The primary lever is specificity, not negation. Vague failure framing ("don't be generic") is as weak as vague success framing. Specific failure framing ("if someone else would write this, you fail") is strong.

**What this frame makes visible:**
- How documents frame their evaluative criteria (does this document define success, failure, or neither?)
- The specificity gradient: vague framing (whether positive or negative) produces generic output; specific framing (whether positive or negative) produces specific output; specific failure framing is the sharpest of all
- Why AI-generated content so often feels interchangeable: the prompt did not specify what would make the output fail

**What this frame makes invisible:**
- Whether the output was constrained by specific criteria or allowed to float in generic space
- The evaluative standard the document was produced against (most documents carry no visible evaluative standard)
- Task-type dependency: failure framing works on open-ended tasks (d=1.24) and has near-zero effect on constrained tasks (d=0.15)

**Positive examples:** A consulting report that includes a section "This analysis would be wrong if..." is exhibiting explicit failure framing. The reader can evaluate the analysis against its own failure criteria.

**Negative examples:** A consulting report with no evaluative criteria, no "this would be wrong if" section, and no specificity constraints. The reader cannot tell whether the analysis was produced with any standard or just allowed to fill space with plausible-sounding claims.

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, generic fluent output passes scrutiny when failure criteria are absent), Default Geometry (FVS-004, without failure framing the output follows defaults; FVS-004 withdrawn per INDEX.md "v1 publication state"), Frame Amplification (FVS-001, without failure criteria to interrupt, amplification compounds unchecked), Growth Frame (FVS-008, growth narratives routinely omit failure criteria; the two frames co-fire often because absence-of-failure is how growth avoids disconfirmation)

**When this frame is appropriate:** Evaluating any AI-generated analytical content, strategy document, report, or recommendation. Any context where the reader should ask: "what would make this wrong?" and the document does not answer.

**When this frame is misleading:** Narrowly constrained tasks where the success criteria are implicit and well-defined (data formatting, translation, factual lookup). Failure framing adds value only where the interpretation space is open.

**Honest limits:** The specificity effect (d=0.96) is from EXP-025 (2x2 factorial) and is well-supported. The negation main effect null (d=0.18) is from the same experiment. The task-type dependency (d=1.24 open-ended vs d=0.15 constrained) is from EXP-017 (gradient). All are from AI-generated text experiments, not from human decision-making studies. Whether failure framing in the evaluative criteria of a document (rather than in the prompt that produced the document) has the same effect on reader judgment is unmeasured.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document does not name what would falsify its claims or what risks attend its recommendations. Affects:

- **Counterfactual** ([methodology](/corpus/decision-readiness/)): this is the canonical structural signal for the Counterfactual dimension. A document that does not engage with how it might be wrong is structurally less decision-supportive on counterfactual reasoning.

## Generation affordances

**Rewrite prompt structure:** "For each major claim in this document, add a failure condition: 'This claim would be wrong if [specific condition].' The failure conditions should be concrete enough that someone could check them against reality."

**Counter-document prompt:** "This document was produced without explicit failure criteria. Produce the failure-framed version: for each section, state what would make the analysis wrong, what evidence would contradict the conclusions, and what conditions would invalidate the recommendations. Then evaluate whether the original survives its own failure criteria."

**Salient questions under this frame:**
- What would make this analysis wrong?
- Does the document name its own failure criteria, or does it leave the reader to guess?
- If I applied specific failure conditions to this output, would the conclusions survive?
- Is the absence of failure criteria a sign of confidence or a sign of untested claims?

## Worked example

**Document excerpt:** "The AI healthcare market is experiencing explosive growth, with global spending projected to reach $187.95 billion by 2030. Machine learning applications in diagnostics, drug discovery, and patient monitoring are transforming clinical workflows and improving patient outcomes."

**Frame present:** Success framing only. "Explosive growth," "transforming," "improving" all serve the growth narrative. No failure criteria.

**Frame absent:** What would make this projection wrong. What if regulatory barriers slow adoption? What if clinical trials show ML diagnostics perform worse than claimed? What if the $187.95B projection is based on assumptions that do not hold? The document presents the growth frame without naming what could break it.

**How to read past it:** Add the failure frame: "This analysis would be wrong if: (a) adoption rates are slower than projected due to regulation, (b) clinical evidence does not support the claimed improvements, (c) the projection model uses assumptions inconsistent with current hospital IT budgets." Then evaluate whether the original analysis addressed these.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected when a document has high assertion density with no epistemic hedging, no limitations section, and no self-referenced failure conditions. The absence of failure framing is itself the detection signal: the document claims without naming what would make the claims wrong.
**Branch B:** In the pre-commit intervention, the user can add their own failure frame before consulting AI: "I think [X]. My analysis would be wrong if [Y]." This forces the construction trace to include evaluative criteria that the AI's response can be compared against.

## Vocabulary connections

- **The construction trace** (T-356): failure framing is a specific form of construction trace. By naming what would make the analysis wrong, the user constructs the evaluative standard that makes deep evaluation possible.
- **Source conditioning** (T-351): providing source material is one way to ground failure criteria. "If the numbers do not match the source, the analysis fails" is a concrete failure condition that source conditioning operationalizes.

## Cross-family reliability


**Engine-canonical reading (library_v4 ratified 2026-04-24).** library_v4 Identification sections are byte-equivalent to library_v3 per [fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md). The V4.2 engine reads only the Identification section per `v4_2_engine.py::_extract_identification`, so cross-family AC1 on library_v4 equals cross-family AC1 on library_v3 by judge-visible byte-equivalence. The library_v3 row in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence)' subsection above carries the engine-canonical reliability values for this frame. The 'V4.2 NEW panel measurement against library_current' subsection below documents the working-library measurement immediately prior to ratification, retained as historical pre-ratification context.

**Engine-emit disclosure.** `library_consensus_ac1` = **0.420** (tier: **moderate**), per [fvs_eval/v4/library_v4_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_reliability.json). Per-corpus reproducible values (regen: [fvs_eval/v4/compute_per_corpus_reliability.py](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/compute_per_corpus_reliability.py); artifact: [fvs_eval/v4/library_v4_per_corpus_reliability.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/library_v4_per_corpus_reliability.json)): MG_v3=0.534 (clean library_v4 via Identification byte-equivalence), MG2_v4=0.582 (3-family partial; Anthropic queued). Historical: MG2_v1=0.449 (library_v1), MG2_v2=0.674 (library_v2). Note: ac1_avg is NOT reproducible from these via simple or weighted averaging per [fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md); rebuild queued for library_v5.

**Intra-rater stability (Grok 4.1 fast).** `detector_intra_rater_ac1` = **0.707** across n=41 docs at temp=0 (6 verdict flip(s); per [fvs_eval/v4/grok_intra_rater_ac1.json](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/grok_intra_rater_ac1.json)). Measures single-family consistency, independent of cross-family AC1: low cross-family + high intra-rater is possible (and common).

**Construct-validity caveat.** `library_consensus_ac1` measures cross-family LLM agreement, NOT agreement with human reader labels. Per [METHODOLOGY.md](https://github.com/lluvr/frame-check/blob/master/METHODOLOGY.md) section 1.3, V1 detector macro-F1 against human labelers was 0.157 (chance-level, n=12); library_v4 LLM-judge has not been re-validated against humans. Read AC1 as inter-LLM consensus proxy, not human-validated reliability.

### Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants

- **library_v3 (Step-4 ratified variant, commit `9abeb3d` 2026-04-18):** Gwet's AC1 0.534, kappa 0.150, union 8/15. Under library_v4 ratification (2026-04-24), library_v3's Identification text is the engine-canonical Identification per byte-equivalence; library_v3's cross-family numbers are therefore the engine's reliability claim under library_v4. AC1 delta (library_current historical − library_v3 engine-canonical): +0.13.
- **library_v2 (earlier variant):** Gwet's AC1 0.736, kappa 0.318, union 5/15.

See [fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md) §3 for library-wide tier context and [fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md) §3 for reasoning-coherence profile.

### V4.2 NEW panel measurement against library_current (2026-04-24, historical pre-ratification)

V4.2 NEW panel (2026-04-24 measurement): Claude Haiku 4.5, Gemini 3.1 flash lite, Grok 4.1 fast (V4.2 canonical), GPT-5.4 mini. Corpus: [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15. Library reference: the working library state at `data/frame_library/` immediately prior to library_v4 ratification (2026-04-24). This subsection's numbers are historical pre-ratification context. Engine-canonical numbers under library_v4 are in the 'Engine-canonical (library_v3 = library_v4 by Identification byte-equivalence) and earlier variants' subsection above (library_v3 row), per the byte-equivalence statement at the top of this Cross-family section.

| Metric | Value |
|---|---|
| Gwet's AC1 (pairwise mean) | 0.666 |
| Cohen's kappa (pairwise mean) | 0.427 |
| Raw agreement (pairwise mean) | 0.789 |
| Union prevalence | 7/15 = 47% |
| Intersection (all 4 agree positive) | 1/15 |

Per-family positives (of 15 docs): Claude 3, Gemini 4, Grok 5, GPT 3.
