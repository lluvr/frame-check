# Uncertainty Frame

**FVS entry:** FVS-012
**Version:** 1
**Curator:** Lovro Lucic
**Curated:** 2026-04-13

## Identification

**Uncertainty Frame fires when the document structurally organizes its analysis around what is unknown, contested, or assumption-dependent. The frame must be the ORGANIZING PRINCIPLE of the analysis, not a surface feature.**

The uncertainty frame asks: what do we not know? Most AI-generated analysis presents conclusions with high confidence even when the underlying evidence is thin, assumptions are untested, or expert consensus does not exist. Documents that surface the gap between confidence of presentation and confidence of evidence exhibit this frame.

The frame fires when the document:
- Explicitly names sources of uncertainty and weighs each (not just "there is uncertainty" but "uncertainty comes from: sources X, Y, Z, each weighted differently")
- Presents claims as ranges or point-estimates-with-error-bars as the primary evidential form, not as occasional hedges
- Surfaces expert disagreement or contested evidence as a structural element (a section or recurring move, not one mention in passing)
- Treats "what we don't know" as a primary section, argumentative move, or conclusion

The frame does NOT fire when:
- The document uses hedging language ("may," "could," "approximately," "likely") without treating uncertainty as the organizing principle
- Open questions or speculative phrasing appear in a document whose actual claims are presented confidently
- The document merely includes some uncertainty acknowledgments as politeness or genre convention; it must ORGANIZE around them
- A single hedged paragraph is embedded in an otherwise confident argument

**What this frame makes visible:**
- Claims presented as facts that are actually projections, estimates, or contested
- Assumptions underlying specific conclusions that have not been tested
- Error bars, confidence intervals, and ranges where the document presents point estimates
- Disagreement among experts or sources that the document does not mention
- The difference between "this is true" and "this is our best current estimate"

**What this frame makes invisible:**
- Action readiness (the uncertainty frame can produce paralysis if applied without context about what level of certainty is sufficient for the decision at hand)
- Relative confidence (not all uncertainties are equal; some are minor and some are decision-critical)
- Whether the uncertainty has practical implications for the specific decision being made

**Positive examples:** A climate science summary that presents temperature projections as ranges (1.5-4.5C by 2100) with named sources of uncertainty (climate sensitivity, emissions pathway, feedback loops) as an organizing structure. Each projection carries its evidence quality. Uncertainty IS the frame.

**Negative examples:** An AI-generated market analysis that says "the AI market will reach $500 billion by 2028" without any qualifier, source, confidence interval, or acknowledgment. A document with occasional "perhaps" and "may" hedges in otherwise confident prose does NOT fire; uncertainty language alone isn't the frame, structural organization around uncertainty is.

**Adjacent frames:** Risk Frame (FVS-009, addresses what could go wrong, while uncertainty addresses what is unknown), Failure Framing (FVS-007, specifies what would make claims wrong, while uncertainty names what cannot yet be known; uncertainty can exist without explicit failure criteria, the inverse is not symmetric), Completeness Illusion (FVS-010, uncertainty dimension may be mentioned briefly without analysis), False Balance (FVS-017, false balance manufactures artificial uncertainty by elevating minority positions to majority-evidence levels; what reads as genuine uncertainty in the document may be a false-balance artifact), Authority by Citation (FVS-016, authority-by-citation strips uncertainty markers from citations; genuine citations include uncertainty as a signal of epistemic care), Temporal Anchoring (FVS-014, future-projected content gives uncertainty cover; temporal anchoring's future orientation can hide the epistemic uncertainty that uncertainty framing surfaces)

**When this frame is appropriate:** Scientific analysis, investment decisions, policy assessment, any context where the reader needs to distinguish between what is known with confidence and what is estimated, projected, or contested.

**When this frame is misleading:** Stable factual domains where uncertainty is negligible (the speed of light, the population of France, the boiling point of water). Applying uncertainty framing to well-established facts produces false balance. Also misleading when used to delay action on claims that are sufficiently certain for practical purposes.

**Honest limits:** The detection heuristic (presence of uncertainty-dimension markers) catches explicit uncertainty language (hedging, ranges, "may," "approximately," "estimated") but misses cases where uncertainty is high but the document presents false precision. A claim like "$500 billion by 2028" has enormous uncertainty but uses no uncertainty language. Under the revised (Phase 1C) definition, hedging language alone does NOT fire the frame; structural organization does. The detector can identify surface uncertainty language; whether the document's STRUCTURE is organized around uncertainty remains an interpretive judgment.

**Revision note (2026-04-23, Phase 1C):** Revised from v1 to require structural organization around uncertainty as the primary analytical frame, not mere surface hedging. v1 permitted narrow and broad readings that produced low cross-family agreement (v2 mean AC1 0.359). The revised definition tightens toward the narrow reading, excluding cases where uncertainty language appears but does not organize the analysis. Predicted cross-family Gwet's AC1 lift: 0.359 → approximately 0.55-0.65.

## Decision-readiness implication

**Direct readiness implication.**

When this frame fires, the document explicitly names what is unknown, contested, or assumption-dependent. Affects:

- **Calibration** ([methodology](/corpus/decision-readiness/)): the document hedges where uncertainty warrants it. The methodology page's Calibration dimension is the formal structural proxy for what this frame qualitatively names.
- **Counterfactual**: alternative interpretations are surfaced.

Absence of this frame in contexts where uncertainty is real is a structural overconfidence signal.

## Generation affordances

**Rewrite prompt structure:** "For each projection, estimate, or forward-looking claim in this document, add an uncertainty annotation: what is the evidence quality (measured, estimated, projected, speculated)? What is the range of plausible values? What assumptions does this depend on? What do experts disagree about?"

**Counter-document prompt:** "This document presents its conclusions with high confidence. Rewrite with honest uncertainty: for each point estimate, provide a range. For each projection, name the assumptions. For each 'experts say,' name the disagreements. The goal is not to undermine the analysis but to make the reader aware of where the floor might give way."

**Salient questions under this frame:**
- Is this a fact, an estimate, or a projection?
- What is the range of plausible values, not just the point estimate?
- What assumptions does this projection depend on, and have they been tested?
- If I came back to this analysis in 2 years, which claims would still hold?

## Worked example

**Document excerpt:** "Global semiconductor revenue will exceed $1 trillion by 2030. Artificial intelligence will drive 40% of this growth, with data center chips accounting for the largest share."

**Frame present:** Confident projection. "$1 trillion by 2030" and "40% of this growth" are presented as facts.

**Frame absent:** Any uncertainty signal. Questions not addressed: whose projection? What is the confidence interval? ($800B to $1.2T? $600B to $1.5T?) What are the assumptions about AI adoption rates? What happens if there is a recession, a trade war, or a technology plateau? What was the accuracy of similar projections made 5 years ago?

**How to read past it:** For each number, ask: "is this a measurement or a guess?" $1 trillion by 2030 is a guess (projection). 40% AI-driven is a guess within a guess. Neither is wrong per se, but presenting them without uncertainty framing implies a precision that does not exist.

## Branch applicability

**Primary branch:** A (document analysis)
**Branch A:** Detected via coverage analysis. Presence of uncertainty markers indicates the document acknowledges its own limits. ABSENCE of uncertainty markers in a document that makes forward-looking claims or uses point estimates is the actionable signal.
**Branch B:** The user can apply the uncertainty frame in pre-commit: "What am I uncertain about in my own assessment?" before seeing AI's confident answer. The pre-commit makes the user's own uncertainty visible as a comparison point.
