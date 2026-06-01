# Failure Framing

**FVS entry:** FVS-007
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-12

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

**Honest limits:** The specificity effect (d=0.96) is (2x2 factorial) and is well-supported. The negation main effect null (d=0.18) is from the same experiment. The task-type dependency (d=1.24 open-ended vs d=0.15 constrained) is (gradient). All are from AI-generated text experiments, not from human decision-making studies. Whether failure framing in the evaluative criteria of a document (rather than in the prompt that produced the document) has the same effect on reader judgment is unmeasured.

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
