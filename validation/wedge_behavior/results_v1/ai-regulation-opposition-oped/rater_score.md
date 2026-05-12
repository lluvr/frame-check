# Rubric form: paired-response scoring (wedge behavior-change pilot)

**Doc slug:** `ai-regulation-opposition-oped`
**Document genre:** opinion, claim-loaded (op-ed arguing against EU AI Act and US licensing proposals)
**Date scored:** 2026-05-12
**Rater:** Claude (agent mode), proxy for operator review
**Rater-confound disclosure:** Same as `roth-conversion-recommendation/rater_score.md` — operator review is the load-bearing check.

## Items

### 1. Names a structural absence (item 1, load-bearing)

**Score: YES**

**Cite the specific text** in the with-tool response that names the absence:

> "**The Completeness Illusion ([FVS-010](...))**. Frame Check's detector found markers for 4 of 5 analytical perspectives (risks, stakeholders, trends, uncertainty) — which sounds broad. But the density ratio is 4:1 skewed: risk markers appear at 10.8 per 1,000 words, stakeholder markers at 12.3, while uncertainty markers appear at only 3.1 and trend markers at 3.1. More importantly, the detector found **no markers for causes**..."

**Why this counts:**

Without-tool response named: safety-record cherry-picking, SME statistic uncritically, China-competition assertion, Boeing comparison backfire, "speculative harms" too dismissive, binary framing, research-vs-deployment conflation. Strong critique.

With-tool added:

- **FVS-010 Completeness Illusion**, named explicitly, as the structural shape of the argument: "the piece *mentions* multiple perspectives but analyzes only one of them with any depth."
- **Counterfactual cluster** across FVS-001, FVS-007, FVS-014 named with citation URIs. "The substrate's reading: the document does not name conditions under which its conclusion would be wrong."
- **Quantified density ratios** (10.8 risk markers vs. 3.1 uncertainty markers per 1k words) that without-tool cannot produce.
- **The falsification detector finding zero** — explicit measurement, not a qualitative observation.

The named-absence catalog frames + the quantified densities are not in the without-tool response.

### 2. Uses reading-form (item 2, load-bearing)

**Score: YES**

**Cite the with-tool reading-form passage:**

> "the framing leaves out the strongest version of the pro-regulation argument: that AI harms are already occurring..."
>
> "the piece anchors almost entirely in the present (78% present-tense, 63-point margin over other tenses)"

**Cite the without-tool verdict-form passage it replaces:**

> "The op-ed is useful for identifying real problems with specific regulatory designs"
>
> "But it's not a reliable guide to whether AI regulation is warranted in principle"
>
> "The tone may signal motivated reasoning"

Without-tool defaults to verdict ("the op-ed is useful", "the tone may signal motivated reasoning"). With-tool reads the framing as a structural pattern ("the piece anchors", "the framing leaves out").

### 3. Cites Frame Check explicitly (item 3, load-bearing)

**Score: YES**

**Cite an example:**

> "Frame Check's structural analysis reveals some specific places where the argumentative architecture is weaker than the prose confidence suggests."
>
> "Frame Check's detector found markers for 4 of 5 analytical perspectives..."
>
> "Frame Check identified a counterfactual-dimension absence cluster across [FVS-001 (Frame Amplification)], [FVS-007 (Failure Framing)], and [FVS-014 (Temporal Anchoring)]."
>
> "Frame Check's epistemic detector found that only 19% of sentences carry attribution markers."
>
> "Frame Check flagged this as the highest-signal absent frame..."

Every quantified structural measurement is attributed. The agent's reading ("the SME statistic is doing a lot of work") is offered as the agent's reading, distinct from Frame Check's measurements.

### 4. Calibrates a hedge (item 4, descriptive only)

**Score: YES**

**Cite the hedge calibration:**

Without-tool says: "The SME statistic is presented without scrutiny... but industry-adjacent bodies routinely produce worst-case projections during regulatory comment periods."

With-tool says: "Frame Check's epistemic detector found that only 19% of sentences carry attribution markers — meaning roughly 4 in 5 sentences are floating assertions. The claim extractor identified 5 numerical claims, of which only 1 carries hedging language. The most load-bearing number — the EU SME Council's estimate that compliance costs will 'eliminate 60-70% of independent AI startups within their first market year' — is stated as fact with no source link, no confidence interval..."

The without-tool response identifies the SME hedge issue qualitatively. The with-tool response surfaces the same issue with quantified measurements (19% sentence attribution; 1 of 5 numerical claims hedged) and names the specific sentence that's load-bearing.

### 5. Pivots on confidence-gate failure (item 5, descriptive only)

**Score: GATE DID NOT FIRE**

Document is 631 words (over 100), English, paragraphed analytical prose. Engine confidence-gate not triggered.

## Aggregate

**Load-bearing shift (item 1 OR item 2 OR item 3 fires positively):**

**YES — items 1, 2, AND 3 all fire. Item 4 also fires (descriptive).**

## Notes for protocol calibration (pilot only)

**What was UNCLEAR about the rubric?**

- **Item 4 sub-distinction (continued from doc 1 scoring)**: with-tool surfaces the without-tool's *qualitative* hedge-criticism as a *quantitative* measurement (4 in 5 sentences are floating assertions). This is a hedge-calibration improvement of a different kind than the example in the rubric (where with-tool rebalances the AGENT's own hedge). v2 rubric should distinguish.

- **Item 1 catalog-frame attribution**: when both arms identify the same gap (e.g., "China argument is asserted, not argued"), but with-tool grounds it in catalog frames + quantified rates while without-tool grounds it in agent judgment, both arms named the absence. The DIFFERENCE is the epistemic provenance. v2 should clarify whether item 1 is "named an absence the other did not name" (binary) or "named an absence with structural attribution the other could not produce" (gradient).

**What was the most important DIFFERENCE between the with-tool and without-tool responses, in one sentence?**

> The without-tool response gives a strong reasoned critique that reads as the agent's own balanced analysis; the with-tool response gives a structurally-grounded critique with named catalog frames, quantified epistemic measurements (19% attribution, 1/5 hedged, 78% present-tense), and the falsification-conditions detector's zero-finding — making the critique falsifiable and traceable in a way the without-tool version is not.
