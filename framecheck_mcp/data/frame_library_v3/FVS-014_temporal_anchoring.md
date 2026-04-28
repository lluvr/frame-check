# Temporal Anchoring

**FVS entry:** FVS-014
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13
**Source:** temporal_orientation in framing.py, EXP-094 (training-cutoff confabulation regimes), the Observatory cadence design
**Status:** v1, single-curator, reviewers wanted

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

Frame Check's temporal distribution signal (in the Document Structure card) is the direct measurement.

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

## Vocabulary connections

- **The amplification thesis** (HI-062): temporal orientation amplifies across a session. A past-anchored first response sets the temporal frame for every subsequent response.
- **Source conditioning** (T-351): providing current source material is the antidote to training-data-vintage temporal anchoring. The source material sets the temporal frame, not the model's training data.

## Cross-family reliability (F-2026-027, April 2026 baseline)

Measured on [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) n=15 across four top-tier LLM families
(Claude Sonnet 4.6, Gemini 2.5 Pro, Grok 4, OpenAI GPT-5):

| Metric | Value |
|---|---|
| Cohen's kappa (pairwise mean) | 0.094 |
| Gwet's AC1 (pairwise mean) | 0.808 |
| Raw agreement (pairwise mean) | 0.844 |
| Union prevalence (all families) | 90% |

Per-family positives (of 15 docs): Claude 14, Gemini 14, Grok 14, GPT-5 12.

**V4 detection mode:** default

**Interpretation:** Kappa paradox pattern (low Cohen's kappa due to prevalence extreme 90%, but Gwet's AC1 shows substantial cross-family agreement). Reliable under prevalence-robust metrics.

**Latest-model discipline:** values reflect April 2026 Gemini 2.5 Pro baseline (and equivalents for other families at time of F-2026-027 run). Newer model versions may shift reliability; periodic re-calibration is V4 operational doctrine. See [fvs_eval/v4/RELIABILITY_STUDY.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/RELIABILITY_STUDY.md) for methodology, [fvs_eval/v4/DESIGN.md](https://github.com/lluvr/frame-check/blob/master/fvs_eval/v4/DESIGN.md) for architecture, and F-2026-027 / F-2026-028 for pre-registration + outcome.

## Grounded authorship (v2 §11 retrofit)

**Authorship.** Lovro Lucic. v1 curated 2026-04-13; grounded-authorship retrofit 2026-04-25 per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check/blob/master/FRAME_DIVERGENCE_v2.md) §11 catalog discipline.

**Context of testing.** Tested in the V4.2 single-validator pipeline against:
- [fvs_eval/mixed_genre_v1](https://github.com/lluvr/frame-check/tree/master/fvs_eval/mixed_genre_v1) (n=15, four-family panel; F-2026-027 baseline 2026-04)
- `temporal_orientation` in `framing.py` (PAST_RE, FUTURE_RE regex patterns; rule-based detector)
- EXP-094 training-cutoff confabulation regimes
- Observatory cadence design (structural answer to temporal anchoring)
- AI healthcare market analysis worked example (v1 Identification)
- Observatory daily-topic stream from 2026-04-08 forward (Tier B paused 2026-04-22)

**Failure record.** Three failure modes observed in operation:
1. Kappa paradox at extreme high prevalence. F-2026-027 showed kappa 0.094 (very low) but AC1 0.808 (substantial). Union prevalence 90% across families - nearly every document has some temporal orientation. Kappa paradox-distorted; AC1 carries actual agreement signal under prevalence robustness.
2. Detection captures explicit but misses implicit. Regex patterns (PAST_RE, FUTURE_RE) capture explicit temporal language ("was," "had been," "will be," "by 2030"). Documents using present tense for historical data ("the market IS worth $X" when the number is from 2022 training data) pass through the detector unflagged. Implicit temporal anchoring is a known under-detection failure mode; LLM-judge V4.2 partially addresses but tense-vs-vintage mismatch is interpretive.
3. Training-cutoff effect not automated. Detecting when AI presents pre-cutoff data as current requires knowing the model's training data cutoff and comparing against the document's claimed recency. Frame Check has no automated training-cutoff detection. Manual cross-checking is the operational solution; tooling is open work.

**Success record.** Two operationalized cases:
1. AI healthcare worked example (v1 Identification). Document presented "achieved 95 percent accuracy" plus "reached 38 percent during the pandemic" plus "continues to grow" - past results presented in present tense with extrapolation. Vintage-check question ("when from?") exposes the temporal anchoring is in training data, not in current reality. Operationalized as "verified current as of [date]" or "potentially stale (training data vintage)" annotation per claim.
2. Observatory cadence design. The Observatory's daily-topic stream is the structural answer to temporal anchoring at the methodology level: regular cadence ensures that what Frame Check measures is current, not training-vintage. The temporal-orientation detector plus Observatory cadence together address the temporal-anchoring failure mode at the methodology level rather than the per-document level.

**Lived-experience anchor.** Open. Anchor criteria for this entry: (1) a specific moment where the operator caught a temporal-anchoring issue in AI output (data presented as current that was actually vintage from training data); (2) the vintage-check antidote applied (asking "when from" for each numerical claim); (3) outcome differential observed (claim re-verified against current source, conclusion adjusted, projection re-grounded); (4) concrete first-person recall. Held open per [FRAME_DIVERGENCE_v2.md](https://github.com/lluvr/frame-check/blob/master/FRAME_DIVERGENCE_v2.md) P5 honest-scope discipline rather than synthesized.

**Friction-cost estimate** (operator-validation pending):
- Manual application: ~30-60 seconds (check vintage of each numerical claim; apply tense-vs-vintage check)
- V4.2 LLM judge invocation: ~$0.0008/document (detects explicit but misses implicit; honest-limit mode)
- Vintage-check (manual cross-reference against training cutoff): 1-3 minutes per document for substantive verification
- One-pass detection: appropriate for any AI-generated time-varying analysis
- Deep-dive engagement: appropriate when training-cutoff vintage is load-bearing (high-stake forward-looking decisions)

**Applicability metadata.**
- Domains: market analysis (high stake-relevance), economic assessment (high), technology trends (high), demographic projections (high), scientific findings that evolve (high), AI-generated analysis on rapidly-changing topics (high)
- Decision types: any decision based on time-varying data
- Stake levels: medium to high (training-cutoff effect operates regardless of stakes; impact scales with stakes and recency-sensitivity)
- Inappropriate contexts: timeless factual content (mathematical constants, established scientific laws, geographical facts that change slowly); narrowly factual queries about stable domains

**Empirical track record (consolidated).**
- Cross-family reliability (F-2026-027): kappa 0.094 (paradox-distorted), AC1 0.808 (substantial), raw 0.844, union prevalence 90% (Claude 14, Gemini 14, Grok 14, GPT-5 12 of 15) - one of the highest-prevalence frames; near-universal document presence
- EXP-094 training-cutoff confabulation regimes
- temporal_orientation regex detector in `framing.py`
- Observatory cadence: structural methodology-level answer
- Observatory fire rate: pending Tier A quarterly export
- User-reported outcomes: not yet collected (Tier 3 future work)
