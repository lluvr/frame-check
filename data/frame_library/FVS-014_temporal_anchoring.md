# Temporal Anchoring

**FVS entry:** FVS-014
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13

## Identification

A document anchors the reader's perception of time by choosing which temporal orientation to emphasize. Past-anchored documents present historical data as the lens for understanding the present. Future-projected documents present forecasts as the lens for understanding the present. Present-focused documents treat the current moment as if it were the complete picture. Each orientation hides the others: a future-projected document about AI makes the history of technology hype invisible; a past-anchored document about market performance makes the structural changes that break historical patterns invisible.

**What this frame makes visible:**
- How temporal orientation shapes which conclusions feel natural (past data supports trend extrapolation; future data supports optimism or fear; present data supports urgency)
- Why AI output has systematic temporal biases (training data is historical; models extrapolate from what was, not from what is changing)
- How documents that claim to be "comprehensive" often have a single dominant temporal orientation that shapes all their conclusions

**What this frame makes invisible:**
- Whichever temporal orientation is absent. Future-projected documents hide historical base rates. Past-anchored documents hide structural discontinuities. Present-focused documents hide trajectory.
- The training-cutoff effect: AI models present pre-cutoff data as current, making the temporal orientation partially a function of when the model was trained, not of what is actually happening

**Positive examples:** An economic outlook report with explicit temporal structure: "Historical trend (2010-2024): X. Current conditions (2025): Y. Forward projection (2026-2030): Z. Assumptions underlying the projection: A, B, C." Each temporal orientation is named and gets substantive analysis.

**Negative examples:** An AI-generated industry analysis where all data points are from 2022-2023 training data but the document uses present tense ("the market IS worth $X") without acknowledging that the numbers are 2-3 years old. The temporal anchoring is in the training data, not in the current reality.

**Adjacent frames:** Growth Frame (FVS-008, typically future-projected with growth assumptions), Uncertainty Frame (FVS-012, future projections always carry uncertainty that temporal anchoring may hide), Oracle Frame (FVS-013, oracle mode accepts the temporal orientation without checking against current data)

**When this frame is appropriate:** Any document that presents time-varying information: market analysis, economic assessment, technology trends, demographic projections, scientific findings that evolve. Particularly important for AI-generated content where training-cutoff effects create invisible temporal distortion.

**When this frame is misleading:** Timeless factual content (mathematical constants, geographical facts that change slowly, established scientific laws). Temporal anchoring analysis adds noise where the content is not time-dependent.

**Honest limits:** The temporal orientation detector in framing.py measures past/present/future sentence ratios via regex patterns (PAST_RE, FUTURE_RE). This captures explicit temporal language but misses implicit temporal framing (a document using present tense for historical data). The training-cutoff detection is not automated; it requires the reader to know when the model's training data ends and compare against the document's claimed recency.

## Decision-readiness implication

**Direct readiness implication.**

When a document over-anchors to one temporal orientation, it crowds out the others. Affects:

- **Coverage** ([methodology](/corpus/decision-readiness/)) indirectly: a single temporal frame is structurally narrow on what perspectives a reader can consider.
- **Counterfactual**: a future-projected document hides historical disconfirmations; a past-anchored document hides structural changes that break historical patterns.

Framecheck's temporal distribution signal (in the Document Structure card) is the direct measurement.

## Generation affordances

**Rewrite prompt structure:** "Identify this document's temporal center of gravity: is it primarily past-anchored, present-focused, or future-projected? Then rewrite the analysis from the ABSENT temporal orientation. If the document is future-projected, rewrite anchored in historical base rates. If past-anchored, rewrite with current conditions and forward projections."

**Counter-document prompt:** "This analysis was produced by an AI model with training data through [date]. Identify every claim that might be stale: numbers that could have changed, rankings that could have shifted, trends that could have reversed. Annotate each with: 'verified current as of [date]' or 'potentially stale (training data vintage).'"

**Salient questions under this frame:**
- What is this document's temporal center of gravity?
- Are the numbers current, or are they from the model's training data presented as current?
- What would this analysis look like if anchored in a different time period?
- Does the future projection account for structural changes, or does it extrapolate the past?

## Worked example

**Document excerpt:** "AI is transforming healthcare. Machine learning applications in diagnostics achieved 95% accuracy in clinical trials. Telemedicine adoption reached 38% during the pandemic and continues to grow."

**Frame present:** Past-anchored with present-tense framing. "Achieved 95% accuracy" is a past result. "Reached 38% during the pandemic" is 2020-2021 data. "Continues to grow" is an extrapolation from past trend.

**Frame absent:** Current conditions (has telemedicine adoption continued growing post-pandemic, or has it plateaued?), future uncertainty (what are the barriers to continued AI adoption in healthcare?), structural changes (how has regulation changed since the clinical trials?).

**How to read past it:** Check the vintage of each claim. "95% accuracy in clinical trials" from when? "38% adoption" measured when? If the model's training data ends in early 2025, these numbers are 3-5 years old. Present tense makes them feel current when they may not be.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via temporal_orientation output. Dominant past or dominant future orientation with low coverage of the opposite is the signal. Also detectable when the document uses present tense for claims that are likely from training data (requires cross-checking against known training cutoffs).
**Branch B:** The user can anchor their own temporal orientation in the pre-commit: "I am thinking about this topic as of [today]. What is my current understanding?" This creates a temporal reference point that makes the AI's potentially stale training data visible.
