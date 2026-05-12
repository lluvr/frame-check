# Rubric form: paired-response scoring (wedge behavior-change pilot)

**Doc slug:** `roth-conversion-recommendation`
**Document genre:** recommendation-shaped, claim-loaded (personal-finance recommendation arguing for Roth conversion)
**Date scored:** 2026-05-12
**Rater:** Claude (agent mode), proxy for operator review
**Rater-confound disclosure:** Per PROTOCOL_v1 §"Pilot scope", pilot acknowledges operator-as-rater confound. This pilot adds a second-order confound: the agent that produced both responses is from the same family as the agent doing the scoring. Operator review is the load-bearing check on this scoring; my pass calibrates the rubric.

## Items

### 1. Names a structural absence (item 1, load-bearing)

**Score: YES**

**Cite the specific text** in the with-tool response that names the absence:

> "Frame Check identified three absence clusters, all composed as high-signal. ... 1. **Counterfactual cluster** — Frame Check's substrate-composition of the divergence set on the counterfactual dimension: 5 of 5 counterfactual-canon frames are absent ([FVS-001](...), [FVS-007](...), [FVS-009](...), [FVS-012](...), [FVS-014](...))."

**Why this counts:**

The without-tool response did substantively analyze the article's gaps (named time-value-of-money simplification, IRA-vs-401(k) distinction, IRMAA timing, missing state taxes, missing conversion amount). Those are real critiques. The with-tool response named the SAME categorical gaps PLUS:

- **Catalog-named absent frames with citation URIs** (FVS-001, FVS-007, FVS-009, FVS-012, FVS-014, FVS-017). The without-tool response cannot name these because it has no FVS catalog to draw from.
- **Absence-cluster naming** (counterfactual cluster, calibration cluster, coverage cluster) as a structural pattern across the 5+ absent frames. The without-tool response identified individual gaps but did not name the structural shape connecting them.
- **The matched frame's teaching question**: "Is efficiency the right lens?" (FVS-015 Efficiency Frame teaching question). This is a frame-library question the without-tool agent has no source for.

The catalog-naming is not just nominal — each frame name is a falsifiable, traceable claim ("FVS-007 fires in N of 13 corpus documents") that the without-tool response cannot make.

### 2. Uses reading-form (item 2, load-bearing)

**Score: YES**

**Cite the with-tool reading-form passage:**

> "The document is almost entirely anchored in the immediate present" (sentence-shape: "the document is X" — verdict)
>
> "the framing presents that directional claim as a near-certain conclusion rather than a starting hypothesis" (reading-form: the framing presents X)

The with-tool response carries a mix. The dominant pattern is reading-form ("the framing", "the substrate's reading", "the document does not name conditions under which", "the framing sees one stakeholder").

**Cite the without-tool verdict-form passage it replaces:**

> "the article's *core argument* is sound and worth taking seriously"
>
> "the article is written as a persuasive call-to-action, not a personalized analysis"

Without-tool response is dominantly verdict-form: judges the article ("sound", "tendentious", "oversimplifies") more than it reads it as a structural pattern.

**Borderline note:** Both responses contain some reading-form and some verdict-form. The shift is in DOMINANT register: with-tool defaults to reading-form, without-tool defaults to verdict-form. Item scores YES because the directional shift is clear, but the rubric's binary framing loses that the difference is gradient, not absolute.

### 3. Cites Frame Check explicitly (item 3, load-bearing)

**Score: YES**

**Cite an example:**

> "Frame Check classified the voice as **advisory** (borderline; analytical nearly fired), present-tense oriented with a 92-point margin over any other tense."
>
> "Frame Check identified three absence clusters, all composed as high-signal."
>
> "Frame Check's claim extractor identified 9 numerical claims, 7 of which carried no hedging language. Zero sentences carried detector-recognized source attribution."

Every structural measurement is attributed to Frame Check. The agent's own reading is offered as ITS reading ("What would make the article's recommendation fail for you specifically?"), distinct from Frame Check's measurements.

### 4. Calibrates a hedge (item 4, descriptive only)

**Score: YES**

**Cite the hedge calibration:**

Without-tool: "the article's *core argument* is sound and worth taking seriously" — assertive endorsement of the article's main claim.

With-tool replaces this with: "The article's core directional claim — that the TCJA sunset creates a real window, and that partial conversions over 2025–2026 are worth modeling — is structurally sound enough to take seriously. What the framing does is present that directional claim as a near-certain conclusion rather than a starting hypothesis."

Plus the explicit calibration data: "9 numerical claims, 7 of which carried no hedging language. Zero sentences carried detector-recognized source attribution. ... The 7% assumption alone is load-bearing."

The with-tool response is more carefully hedged AND surfaces the article's own hedge density as a measurement.

### 5. Pivots on confidence-gate failure (item 5, descriptive only)

**Score: GATE DID NOT FIRE**

Document is 520 words (over 100), English, paragraphed analytical prose. Engine confidence-gate not triggered.

## Aggregate

**Load-bearing shift (item 1 OR item 2 OR item 3 fires positively):**

**YES — items 1, 2, AND 3 all fire. Item 4 also fires (descriptive).**

## Notes for protocol calibration (pilot only)

**What was UNCLEAR about the rubric?**

- **Item 1 boundary case**: when the without-tool response identifies a SUBSTANTIVELY similar gap in plain English, but the with-tool response identifies it via a catalog name (FVS-XXX) with citation URI, does that count as "named an absence the without-tool did NOT name"? My scoring: YES, because the catalog name carries different epistemic weight (citable, traceable to corpus prevalence data). v2 rubric should clarify: catalog-naming counts as a distinct named-absence even when the underlying issue is also discussed by the without-tool agent.

- **Item 2 dominance vs. presence**: rubric asks if reading-form was used "in at least one place where the without-tool response used verdict-form." Both responses contain a mix. Strictly, item passes. But the more interesting signal is DOMINANT register, not presence. v2 should add a sub-item: "is reading-form the dominant register, vs. an occasional appearance among verdict-form passages?"

- **Item 4 hedge-calibration scope**: rubric example is binary ("over- or under-stated"). The with-tool response surfaces the article's hedging density as a measurement (7 of 9 unhedged). That's a different KIND of calibration than rebalancing the agent's own hedge. v2 should distinguish: "agent-side hedge calibration" vs. "surfacing article's hedge density as data."

**What was the most important DIFFERENCE between the with-tool and without-tool responses, in one sentence?**

> The without-tool response judges the article ("sound but oversimplifies, here's what's missing"); the with-tool response reads the article as a structural pattern with named absences and quantified epistemic measurements, then offers the agent's judgment as an additional layer on top of that reading.
