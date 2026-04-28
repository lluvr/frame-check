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

**Adjacent frames:** Fluency-Quality Illusion (FVS-002, generic fluent output passes scrutiny when failure criteria are absent), Default Geometry (FVS-004, without failure framing the output follows defaults), Frame Amplification (FVS-001, without failure criteria to interrupt, amplification compounds unchecked)

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

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.089 |
| Gwet's AC1 (pairwise mean) | 0.866 |
| Raw agreement (pairwise mean) | 0.889 |
| Union prevalence (all families) | 7% |

Per-family positives (of 15 docs): Claude 0, Gemini 3, Grok 1, GPT-5 0.

**V4 detection mode:** default (sparse-consensus note)

**Interpretation:** Kappa paradox pattern (low Cohen's kappa due to prevalence extreme 7%, but Gwet's AC1 shows substantial cross-family agreement). Reliable under prevalence-robust metrics.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See [fvs_eval/v4/RELIABILITY_STUDY.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/RELIABILITY_STUDY.md) for methodology, [fvs_eval/v4/DESIGN.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/DESIGN.md) for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-12; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) (n=15, four-family panel; F-2026-027 baseline 2026-04)
- HI-016 Failure Framing Asymmetry case study
- EXP-025 negation specificity 2x2 factorial
- EXP-017 framing x ambiguity gradient
- M-004 Frame Inventory corpus
- MCP integration as canonical absent-frame in `_PROMPT_AI_RESPONSE_AUDIT` and `_PROMPT_CHALLENGE_DOCUMENT`
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Kappa paradox at low prevalence. F-2026-027 showed kappa 0.089 (very low) but AC1 0.866 (substantial). Union prevalence 7% across families. The frame fires rarely (only on documents that explicitly name failure criteria), so kappa is paradox-distorted. AC1 carries the actual agreement signal; reliable under prevalence-robust metrics.
2. Detection misses surface failure-language without structural framing. Documents that include "this analysis would be wrong if" as a single sentence but do not structurally organize around failure conditions still fire detection but are not failure-framed in the EXP-025 sense. Structural-vs-surface boundary is interpretive at v0.
3. Task-type dependency unmeasured for document reading. EXP-017 showed d=1.24 on open-ended tasks vs d=0.15 on constrained tasks for AI generation; whether the same dependency holds for reader judgment of finished documents (rather than for prompt-induced output) is not measured. Generalization claim across measurement modes is open.

**Success record.** Two operationalized cases:
1. AI healthcare market analysis (worked example in v1 Identification). Document presented $187.95B 2030 projection with growth narrative and no failure conditions. Failure-framing counter-frame surfaced: regulatory adoption barriers, clinical trial evidence gaps, projection-model assumption inconsistencies. Material additions for due-diligence-grade reading.
2. Decision-readiness Counterfactual dimension structural signal. FVS-007 is the canonical structural signal for the Counterfactual readiness dimension. Documents that do not name what would falsify their claims are structurally less decision-supportive on counterfactual reasoning. Operationalized in MCP `_PROMPT_AI_RESPONSE_AUDIT` and `_PROMPT_CHALLENGE_DOCUMENT` as canonical absent-frame question: "What would have to be true for the conclusion to be wrong?"

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where applying the failure-framing question ("what would make this wrong") to an unframed analysis shifted the read; (2) the contrast between the unframed reading and the failure-framed reading is concrete; (3) outcome differential observed (decision changed, position adjusted, claim withdrawn); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application (no tools, experienced reader): ~30-60 seconds to ask "does this document name what would make it wrong"
- V4.2 LLM judge invocation: ~$0.0008/document (Grok 4.1 fast non-reasoning)
- Branch B pre-commit (user names own failure conditions before consulting AI): 1-2 minutes
- One-pass detection: appropriate for any analytical document; high-leverage on AI-generated analytical content

**Applicability metadata.**
- Domains: investment analysis (high stake-relevance), strategic decisions (high), policy assessment (high), AI-generated analytical content (high), due diligence (high)
- Decision types: any with counterfactual readiness requirement; any open-ended interpretive task
- Stake levels: medium to high; low-stake casual reading does not require this analysis
- Inappropriate contexts: data formatting, translation, factual lookup, narrowly constrained tasks (per EXP-017 d=0.15 on constrained tasks)

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.089, AC1 0.866 (substantial via prevalence-robust metric), raw 0.889, union prevalence 7% (Claude 0, Gemini 3, Grok 1, GPT-5 0 of 15)
- EXP-025 effect size: d=0.96 for specificity main effect (well-supported)
- EXP-017 task-type dependency: d=1.24 open-ended vs d=0.15 constrained
- HI-016 origin study: foundational case
- MCP integration: operationally embedded as canonical absent-frame in challenge and audit prompts
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
