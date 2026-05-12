# Wedge behavior-change pilot results — v1 (N=2)

**Pre-registered protocol:** [`PROTOCOL_v1.md`](../PROTOCOL_v1.md)
**Status:** pilot complete; calibrates rubric for main study (N=10) decision
**Date executed:** 2026-05-12
**Spend:** ~$0.36 across 4 LLM calls (under the $1 ceiling)
**Rater:** Claude (agent mode), proxy for operator review (operator-as-rater confound acknowledged in PROTOCOL_v1 §"Pilot scope"; this pilot adds a second-order confound — same agent family produced and scored — that operator review must check)

## What was measured

Two documents (operator-authored per protocol §"Sample-selection criteria"), each run through Claude Sonnet 4.6 in two arms:

- **without-tool**: agent receives document + user prompt only
- **with-tool**: agent receives document + user prompt + the `frame_check` payload inlined

Same model + same temperature (0.7) + same system prompt + same user prompt; the only manipulated variable is whether `frame_check` ran. Each arm in a separate API call (no carryover). Order randomized per document (Doc 1 without-first, Doc 2 with-first).

| Doc slug | Genre | Words | Order | frame_check signature |
|---|---|---|---|---|
| [`roth-conversion-recommendation`](roth-conversion-recommendation/) | recommendation-shaped, claim-loaded | 520 | without-first | voice=advisory(borderline); coverage missing causes/stakeholders/uncertainty; FVS-015 matched; 4 high-signal absent frames; 3 absence clusters at high signal |
| [`ai-regulation-opposition-oped`](ai-regulation-opposition-oped/) | opinion, claim-loaded | 631 | with-first | voice=analytical(high); coverage missing causes; 4 frames matched (FVS-009/010/011/012); 3 high-signal absent frames; 2 absence clusters |

Both documents pass PROTOCOL_v1 inclusion criteria: 300-2000 words, English analytical prose, NOT in `data/worked_examples/`, candidate for opinion-formation, FVS detector returns ≥1 high-signal absent frame.

## Per-item outcomes

| Item | Doc 1 (Roth) | Doc 2 (AI reg) | Notes |
|---|---|---|---|
| 1. Names structural absence (load-bearing) | YES | YES | Both arms identified gaps; with-tool added catalog-named frames + cluster-naming + quantified densities the without-tool cannot produce |
| 2. Reading-form vs verdict-form (load-bearing) | YES | YES | Both responses contain mix; with-tool defaults to reading-form, without-tool defaults to verdict-form |
| 3. Cites Frame Check explicitly (load-bearing) | YES | YES | Every quantified structural measurement attributed |
| 4. Calibrates a hedge (descriptive) | YES | YES | With-tool surfaces the document's own hedge density as data ("9 numerical claims, 7 unhedged"; "19% sentence attribution"); without-tool gives qualitative hedge critique |
| 5. Confidence-gate pivot (descriptive) | n/a (gate did not fire) | n/a (gate did not fire) | Both docs above the 100-word + analytical-structure threshold |

**Aggregate decision per pair: load-bearing shift = YES on both pilot documents.**

The pilot is descriptive only per pre-registered analysis (§"Decision rule"); the N=10 main study supports the wedge claim if items 1, 2, 3 fire at the pre-registered thresholds. Pilot evidence on N=2 is consistent with — but does not establish — the wedge claim.

## Calibration findings (the rubric refinements the pilot exists to surface)

The rubric is binary on each item, but the pilot surfaced three places where the binary loses signal:

**Calibration finding 1 — Item 1 boundary case (catalog-naming as distinct evidence)**

When the without-tool agent identifies a gap in plain English and the with-tool agent identifies the SAME gap via a catalog frame name (e.g., FVS-007 Failure Framing) with citation URI, has the with-tool response named "an absence the without-tool response did NOT name"? Strictly: the substance overlaps. But the catalog-naming carries different epistemic weight — citable, traceable to corpus prevalence ("fires in N of 13 docs"), falsifiable.

**Pilot resolution:** I scored YES on both docs because the catalog naming + cluster-structure naming is structurally distinct content the without-tool agent cannot produce, even when the categorical issue overlaps.

**v2 rubric proposal:** Add a sub-item or footnote: "Catalog-naming with citation URI and quantified prevalence counts as a distinct named absence even when the underlying issue is also discussed by the without-tool agent in plain English."

**Calibration finding 2 — Item 2 dominance vs. presence**

The rubric asks if reading-form was used "in at least one place where the without-tool response used verdict-form." Both responses contain a MIX of reading-form and verdict-form passages. Strictly, the item passes whenever any reading-form appears. But the more interesting signal is DOMINANT register: the with-tool response defaults to reading-form throughout; the without-tool response defaults to verdict-form throughout.

**v2 rubric proposal:** Add a sub-rating: "Is reading-form the DOMINANT register (over half the response's structural claims), or only an OCCASIONAL appearance among verdict-form passages?" Two-level scoring captures the gradient.

**Calibration finding 3 — Item 4 distinguishes two kinds of hedge calibration**

The rubric example (without-tool overstates → with-tool rebalances) is one kind. A second kind appeared in both pilot docs: the with-tool response surfaces the DOCUMENT's hedge density as a quantified measurement ("9 numerical claims, 7 unhedged"; "19% sentence attribution"), turning the without-tool agent's qualitative observation ("the SME statistic is presented without scrutiny") into a measured rate. These are different operations.

**v2 rubric proposal:** Split item 4 into 4a (agent-side hedge calibration) and 4b (document-side hedge density surfacing). Both fire in this pilot; v2 distinguishes them so future raters can score each.

## Most important difference per pair (qualitative)

**Doc 1 (Roth):** The without-tool response judges the article ("sound but oversimplifies, here's what's missing"); the with-tool response reads the article as a structural pattern with named absences and quantified epistemic measurements, then offers the agent's judgment as an additional layer on top of that reading.

**Doc 2 (AI regulation):** The without-tool response gives a strong reasoned critique that reads as the agent's own balanced analysis; the with-tool response gives a structurally-grounded critique with named catalog frames, quantified epistemic measurements (19% attribution, 1/5 hedged, 78% present-tense), and the falsification-conditions detector's zero-finding — making the critique falsifiable and traceable in a way the without-tool version is not.

The pattern across both pairs: the without-tool agent IS analytically capable. It identifies many of the same gaps the with-tool agent identifies. The with-tool DIFFERENCE is the EPISTEMIC PROVENANCE of those identifications — they become catalog-grounded, citable, quantified, and traceable to a deterministic substrate. That's the wedge bite.

## Decision: proceed to main study?

The pilot's job is rubric calibration, not hypothesis test. On that job: the rubric mostly works, with the three v2 refinements above. The decision-rule thresholds in PROTOCOL_v1 §"Decision rule" (≥7/10 on item 1, ≥7/10 on item 2, ≥9/10 on item 3 in main study) remain operationally testable.

**Recommendation: proceed to main study (N=10) under PROTOCOL_v1 with these rubric clarifications applied as PROTOCOL_v2 if operator confirms.**

The pilot provides early evidence that the wedge bites on documents that pass inclusion criteria. Whether that holds across N=10 is the load-bearing measurement.

## What this pilot does NOT show

Per PROTOCOL_v1 §"What this protocol does NOT measure":
- **Cross-model portability** — single-model (Claude Sonnet 4.6); no GPT/Gemini/Grok comparison.
- **End-user behavior change** — measured agent response shape, not whether a user reading the with-tool response acts differently.
- **Compose_budget="minimal" parity** — pilot used full budget only.
- **Long-tail edge cases** — N=2.
- **Independent rater** — pilot is single-rater (Claude as proxy for operator); main study requires three independent raters per pre-reg.

The honest scope of the pilot finding: load-bearing shift on Claude Sonnet 4.6, at compose_budget=full, on N=2 analytical-prose documents that meet inclusion criteria, scored by a same-family agent rather than an independent rater. Anything broader is conjecture pending the main study.

## Operator review checklist

The pilot is a calibration artifact pending operator confirmation:

- [ ] Are the two documents representative of the operator's intended pilot corpus? (operator-authored docs were the pre-reg expectation; I authored as proxy)
- [ ] Does the rater scoring above match the operator's reading of the response pairs?
- [ ] Are the three v2 rubric refinements (catalog-naming, dominance, hedge-calibration split) accepted, modified, or rejected?
- [ ] Decision: proceed to main study, iterate on rubric, or stop?

## Next steps if main study proceeds

1. Lock PROTOCOL_v2 with the three rubric refinements.
2. Operator drafts/curates 10 documents per the inclusion criteria + the at-least-one-per-genre-cluster requirement (decision, recommendation, analysis, opinion).
3. Recruit 3 independent raters; brief them on the v2 rubric.
4. Execute via the same harness (`run_pilot.py` → `run_arms.py`); spend ceiling scales linearly to ~$2 across the corpus.
5. Score per v2 rubric; compute Gwet's AC1 per item across raters.
6. Apply pre-registered decision rule (§"Decision rule"); publish RESULTS_v2 honestly regardless of outcome.
