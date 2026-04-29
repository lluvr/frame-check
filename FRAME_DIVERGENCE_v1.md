# Frame Divergence v1

The category definition and sovereignty argument for frame divergence as a first-class operation in Frame Check. Specifies what the category is, what it is not, why it compounds in the AGI era, why Frame Check owns it, and the non-negotiables any implementation (including V4.2 architecture choice) must honor.

**Status:** v1 (this document) is the canonical Part 1 spec; `FRAME_DIVERGENCE_CONTRACT_v1.md` is the canonical Part 2 contract pinned at `c1.0` for backward compatibility. The originally-planned v1 Parts 3-4 (V4.2 integration, self-red-team and competitive map) were SUPERSEDED 2026-04-25 by `FRAME_DIVERGENCE_v2.md`, which absorbs v1's narrow definition into a layered architecture (L0-L3) plus a five-stage lifecycle and a §11 grounded-authorship retrofit. v2 is the active spec for the broader architecture; v1 c1.0 contract carries forward unchanged for callers binding the existing `divergence` block.
**Author:** Lovro Lucic
**Date:** 2026-04-23 (last revised 2026-04-23 evening for library_v3 ratification, Rec II enhance-existing alignment, V4.2-alpha status disclosure, and fresh-eyes polish)
**MCP resource URI:** `frame-check://spec/frame-divergence/v1/part-1` (on the canonical Frame Check MCP scheme documented in MCP_SERVER.md; new path operationalization pending per Part 2 §8.5).
**Citation format:** Lucic, L. (2026). *Frame Divergence v1, Part 1.* Frame Check. URL pending production resumption.
**Companion docs:** ENGINE_TIER_STRATEGY_v1.md (three-tier architecture synthesis), MODEL_PANEL.md (panel pinning and re-validation policy), V4_2_DECISION_OPTIONS.md (Options A/B/C cost-performance data).

---

## 1. What frame divergence is

### 1.1 Definition

Frame divergence is the operation of surfacing, from a named catalog of frames, the frames a given piece of thinking has NOT used, with a traceable citation chain back to the catalog entries and to the detection evidence that surfaced the gaps, filtered by domain relevance.

It composes three Frame Check assets already shipped or in late-stage validation:
1. The Frame Vocabulary Standard (FVS) library as the named catalog.
2. The V4.2 judge engine as the measurement of which frames the document DOES use.
3. The evidence discipline as the faithfulness constraint on what the tool will say about what the document does not use.

The primitive is not set-subtraction. It is catalog-minus-present filtered by domain relevance, with citations, with faithfulness guarantees specific to absence claims, with named authorship on the whole.

### 1.2 Terminology: three senses of "frame"

Frame analysis literature uses "frame" in overlapping ways. This spec commits to one sense and flags the others.

- **Frame-as-catalog-entry** (primary sense in this spec): a named, authored FVS entry (e.g., FVS-007 Risk Frame) specifying identification cues, counter-examples, affordances, and limits.
- **Frame-as-cognitive-lens** (Lakoff, Goffman, Tversky-Kahneman tradition): the psychological construct of a mental model that shapes perception. Frame divergence does not operate on this layer directly; it operates on the catalog as an auditable approximation of this layer.
- **Frame-as-rhetorical-move** (discourse analysis): the stance or positioning a text takes. Divergence treats these as candidates for catalog matching, not as the unit of analysis.

When this spec says "frame," it means frame-as-catalog-entry unless otherwise noted.

### 1.3 A round-trip example

Input: a product-announcement paragraph claiming a new feature will "save customers hours."

V4.2 judge output (present frames): Efficiency Frame, Growth Frame, partial Completeness Illusion.

Divergence output (absent from document, present in library_v3 catalog, filtered by domain relevance):
- Risk Frame (FVS-007, stable at library_v3). Absent. Citation: FVS-007 identification cues §2.
- Failure Framing (FVS-011, stable at library_v3). Absent. Citation: FVS-011 §2.
- Authority by Citation (FVS-016, stable at library_v3, revised via Step 4 ratification). Absent. Citation: FVS-016 §2.
- Scope Narrowing (FVS-018, stable at library_v3, revised via Step 4 ratification). Absent. Citation: FVS-018 §2.

Faithfulness note surfaced with output: "These are frames named as absent from this document's current framing, not frames you should have used. Whether any is relevant is the thinker's call."

This is the operative delta from generic LLM brainstorming: every item cites a named catalog entry with version, the `stability` field names whether the entry is stable or under active revision, the tool refuses the prescriptive move. Frames retired from detection scope (FVS-020 per library_v3) never appear in divergence output. Output shape (list vs narrative vs ranked, teaching-question-attached or not) is a contract decision belonging to Part 2.

## 2. What frame divergence is not

The category boundary matters more than the definition, because the surrounding space is crowded with operations that look similar and are not.

- Not generic LLM brainstorming. "Give me more ideas" is unbounded, uncited, and indistinguishable from confident fabrication. Divergence is bounded by a named catalog with versioned entries.
- Not fact-checking or grounding verification. Grounding is the floor per STRATEGY §2. Divergence operates on structure, not truth.
- Not critique or counter-argument. Divergence expands the perspective surface; it does not argue against the present frames.
- Not summarization, expansion, or rewriting. Divergence produces identifications, not content.
- Not the existing Frame Check teaching loop. Current "frame suggestions" are positive detections (named patterns that the document DOES exhibit, surfaced when detection rules fire). Divergence is the inverse operation (named patterns the document does NOT exhibit, surfaced from the catalog when rules do not fire).
- Not inherently pedagogical. Teaching questions are one rendering of divergence output useful in teaching contexts. Professional use (writers, analysts, decision-makers) may render divergence as a completeness-check list without teaching framing. The category is neutral on rendering.

## 3. Why it matters in the AGI era

Retrieval and synthesis compound. Current LLMs pull hundreds of sources, traverse citation graphs, and produce grounded answers with decreasing hallucination rates. That trajectory is not reversing. Grounding as a value proposition commoditizes on the timeline of the next two model generations.

What does not compound on the same curve is discernment. The argument in three parts.

**Simulation is not discrimination.** An LLM can simulate named critical theorists, role-play framings, and generate "have you considered X" lists. What it cannot do without a catalog calibrated to the thinker's domain and the document's evidence is tell the thinker WHICH absent frames matter for THIS decision. Generic simulation at catalog scale is noise. Catalog-calibrated divergence with domain-relevance filtering is signal. This gap does not close with more synthesis capacity; it requires an authored catalog.

**Synthesis-easy makes discernment-hard.** In an era where any answer is generable, the scarce skill is noticing what was not asked. Divergence is a discernment tool, not a synthesis tool. Its value grows as synthesis commoditizes, not shrinks. The economic argument inverts: the more powerful LLMs become at generating plausible content, the more valuable it becomes to have an auditable instrument that flags what the generation did not consider.

**The structural invariant holds through AGI.** Humans reason through frames. Any moment of thinking has frames taken, frames rejected, and frames invisible. Making the invisible visible against a named catalog, with citations, is catalog-anchored structural measurement of what is absent. It is not synthesis. Better synthesis models do not make this operation easier; they make demand for it higher, because generated content is voluminous and the catalog-anchored absence-check scales with the volume.

Category claim: frame divergence is the AGI-era primitive for perspective expansion, and it is the operation whose value grows as retrieval and synthesis improve.

## 4. Why Frame Check owns the category

Three pre-existing assets combine uniquely. The combination is not reproducible from code alone, but each asset is reproducible in isolation, so the moat argument has to carry weight across all three together, not any one.

**The FVS library as the catalog.** Twenty entries authored under named authorship, each specifying identification cues, counter-examples, generation affordances, domain applicability, vocabulary connections, and honest limits. Current maturity disclosed honestly: 16 published, 4 held back, zero canon-promoted as of 2026-04-23, and FVS-010/016/018/020 under active revision. The category claim is conditional on the library maturing. A copycat can replicate a schema; a peer lab with resources CAN author their own catalog. First-authored-catalog is an advantage, not a lock.

**Construct-honesty methodology as the trust moat.** Public audit of Frame Check's own signals (V4_CONFIDENCE_INVERSION_IMPACT_v1 documents inverted precision), pre-registered falsifications including F-2026-030 (detector threshold test that failed, disclosed as diagnostic), disclosed F1 below useful threshold for rule-only mode. This is the layer peer labs do NOT typically inherit, because ongoing public failure-disclosure conflicts with brand-performance incentives. The bet: in a construct-honesty-starved market, discipline compounds against brand over the 2-3 year window. A peer lab that ships a polished catalog without equivalent public-audit infrastructure is a different product serving a different trust contract.

**V4.2 judge engine as the measurement primitive.** Under the OLD panel (Sonnet 4.6, Gemini 2.5 Pro, Grok-4-0709, GPT-5), V4.2 single-family Grok-4 achieves cross-corpus average macro-F1 of 0.765, clearing the F-2026-030 threshold (0.40) by 0.36 margin per V4_2_DECISION_OPTIONS.md Option A. NEW panel (fast/flash tier per MODEL_PANEL.md) re-validation is in progress. Current engine status: **V4.2-alpha** per V4_2_GAP_INVENTORY_v1.md §5. 27 gaps named in the inventory; Tier 1A construct-honesty fix shipped 2026-04-23 (split `library_v3_consensus_ac1` from `detector_intra_rater_ac1`); Tier 1D detector intra-rater measurement landed commit `8353187` (mean intra-rater AC1 0.941 across 19 emitted frames, range 0.707 to 1.000, zero frames below 0.70). Tier 1B (prompt injection mitigation) and Tier 1C (output schema validation) pending before V4.2-beta; production-grade status (V4.3 "proud to own in 2-3 years" bar) requires closing Tiers 1-4 per the inventory. Without the FVS library, V4.2 is a generic classifier. Without V4.2, the FVS library is a static catalog. Composed, with faithfulness constraints on both sides, and with the gap inventory published as the honest-status anchor: frame divergence.

The sovereignty argument, restated against the peer-authored-catalog threat: the durable position is not "only we can build a catalog." It is "we shipped the first publicly authored canonical spec for this category, backed by public audit of our own failures, with named authorship that commits to the discipline over time." First-citation status in the category plus disciplined public-audit practice is the compound. Frame Check does not pivot to divergence. Frame Check names what it has already been building toward.

## 5. Non-negotiables any implementation must honor

These bind Parts 2 through 4 of this spec, and they bind the pending V4.2 architecture, confidence, and library-revision decisions. They are separated into user-visible guarantees (experienced directly in divergence output) and maintainer-side invariants (constraints on how divergence is built and shipped, load-bearing on the category claim though invisible to most users).

### 5.1 User-visible guarantees

1. **Catalog traceability.** Every suggested frame links to a named FVS entry with version. No anonymous suggestions. No "here are five frames" without citations to entry IDs.
2. **Faithfulness over completeness.** Better to surface three cited frames than ten invented ones. The tool refuses to fabricate beyond what the catalog and V4.2 evidence jointly support.
3. **Calibration honesty.** V4.1's `confidence_level` field was inverted (precision-high 0.50, precision-low 0.83 per V4_CONFIDENCE_INVERSION_IMPACT_v1) and was REMOVED entirely under Path C (commit 928a447). V4.2's per-entry reliability ships as split fields per V4_2_GAP_INVENTORY_v1.md Tier 1A: `library_v3_consensus_ac1` (library-entry-level, from 4-family consensus) and `detector_intra_rater_ac1` (V4.2 single-family Grok 4.1 fast, populated from the Tier 1D measurement artifact per commit `8353187`; mean 0.941 across 19 emitted frames). No inverted precision claim ships into divergence outputs.
4. **Library gating.** After library_v3 ratification (commit 9abeb3d, 2026-04-23): FVS-012/016/018 revised and stable; FVS-010 kept library_v1 text and stable with `honest_limit` disclosure; FVS-020 retired from detection scope (never appears in divergence output); no frames currently flagged provisional. The `stability: stable | provisional` enum and flagging protocol are retained in the contract for future revisions; if a frame is reopened for review in later library versions, divergence output flags it as `provisional` and consumers can filter accordingly.
5. **Absence is not prescription.** Divergence output never implies the user should have used the absent frames. The tool surfaces, the thinker decides.
6. **Domain relevance.** Absent frames filtered for domain applicability from FVS entry metadata. A Risk Frame absent from a poem is noise; absent from a financial forecast is signal.

### 5.2 Maintainer-side invariants

1. **Vendor-independent sovereignty.** V4.2 single-family production target is `grok-4-1-fast-non-reasoning` per MODEL_PANEL.md NEW panel (web production choice, operator directive 2026-04-23 afternoon). The contract must define fallback behavior when this vendor is unavailable, deprecated, or materially drifts, per the MODEL_PANEL.md re-validation trigger protocol (small-panel labeling + drift AC1 + macro-F1 regression check). Divergence must not silently become "what one vendor thinks you missed." Operationalized in Part 2 §7 (surface-dependent engine config defaults) and §9 (error envelope with engine fallback behavior).
2. **Named authorship.** The spec, the library, the methodology, and the divergence outputs (in their citations) all carry Lovro Lucic authorship. This is the moat per STRATEGY §4. No anonymous canon.
3. **Construct-honesty propagation.** Divergence outputs carry the same disclosure discipline as the detector. Public audit of divergence-specific failures (false-absence claims, domain-relevance miscalibration) ships on the same cadence as detector audit. This is non-negotiable because dropping it collapses the trust-moat argument in §4.
4. **Thinker primacy over agent convenience.** The tool serves the thinker, not the agent. Agent-facing responses are a delivery channel, not the audience. When agent-rendering and thinker-clarity conflict, thinker-clarity wins.

## 6. Relationship to existing Frame Check surface

Current Frame Check ships a teaching loop per STRATEGY §2: detect present frames, name them, ask teaching questions, link to catalog entries. Frame divergence inverts the same loop on the same assets: identify absent frames from the catalog, name them, attach whatever rendering the consumer needs (teaching question for pedagogical use, completeness checklist for professional use, ranked list for agent consumption), link to the same entries.

Per ENGINE_TIER_RECOMMENDATIONS_v1.md Rec II (operator-approved 2026-04-23), divergence surfaces as an additive `divergence` block on the existing `frame_check` tool output, not as a separate tool. Rec II rationale: the raw material (present frames, library catalog, detection evidence) is already in `frame_check` output; the novelty of divergence is the faithfulness constraint for absence claims (§5.1), the domain-relevance filter, and the catalog-traceability discipline, all of which fit inside the existing tool. Category claim lives in canon (methodology + FVS library + Parts 1-4 of this spec), not in MCP tool inventory. Part 2 of this spec defines the exact `divergence` block shape inside `frame_check` output (field names, provenance structure, agent-guidance content, capability regime per surface).

## 7. Falsifiable predictions

Predictions commit the spec to an audit trail rather than leaving the category claim untested. Two for Part 1. Both registered here and checked against reality at their horizons. The outcome updates the spec, the strategy, or both.

**P1 (24-month horizon, 2028-04-23).** At least one publicly authored frame catalog or divergence-style capability (catalog plus absence-filter operation, whether surfaced as a separate tool, an output enhancement on an existing detector, or another packaging) ships from a third party. Falsification conditions:
- If none ships, the category claim in §3 is premature and the AGI-era argument needs empirical grounding rather than theoretical defense.
- If one ships WITHOUT citation to this spec, the first-citation thesis in §4 is weaker than claimed and the authorship moat needs a different defense (likely the construct-honesty-discipline argument, not the catalog-authorship argument).

**P2 (12-month horizon from MCP publish resumption + Parts 2-4 completion).** At least one agent framework or MCP-consuming product integrates frame divergence as a user-callable operation with citations to FVS entries. Falsification conditions:
- If zero integrations, the category is academic rather than operational, and the distribution path needs rethinking before v2 of this spec.
- If integrations exist but drop citations, §5.1 guarantee 1 has adoption friction and the contract in Part 2 needs to push harder on citation enforcement.

## 8. Outlook

Parts 2-4 pending:
- **Part 2: Contract.** Tool names, inputs, outputs, faithfulness guarantees, provenance requirements, output-shape commitments, MCP resource URI. Binds interface, not implementation.
- **Part 3: V4.2 integration.** How the judge engine feeds divergence under single-family (Grok-4), dual-family, and 3-of-4 consensus architectures. Names what changes for divergence under each, including the fallback contract required by §5.2.1.
- **Part 4: Self-red-team and competitive map.** Copycat scenario, V4.2 engine failure scenario, Track B null scenario, zero-adoption scenario, peer-authored-catalog scenario. Each paired with the minimum artifact that survives the failure. Competitive map of adjacent categories (structured brainstorming methods, cognitive bias catalogs, red-teaming frameworks, decision-quality tools) and what divergence is and is not versus each.

Part 1 is load-bearing for the other three: every contract claim, integration detail, and red-team survival path must honor the category definition and non-negotiables specified here. If Part 1 is wrong, the rest is wrong.

---

## References

- Part 2 contract: `FRAME_DIVERGENCE_CONTRACT_v1.md` (bundled).
- Engine tier architecture synthesis: [ENGINE_TIER_STRATEGY_v1.md](https://github.com/lluvr/frame-check-mcp/blob/master/ENGINE_TIER_STRATEGY_v1.md).
- Model panel pinning and re-validation policy: fvs_eval/v4/MODEL_PANEL.md.
- V4.2 Options A/B/C cost-performance data: fvs_eval/v4/V4_2_DECISION_OPTIONS.md.
- FVS library: `data/frame_library/` entries FVS-001 through FVS-020 (library_v3 current per commit `9abeb3d`; FVS-012/016/018 revised, FVS-010 kept library_v1 text with `honest_limit`, FVS-020 retired from detection).
- Methodology paper: `METHODOLOGY.md` (bundled).
- Confidence-field resolution (Path C, confidence_level removed): commit `928a447` and the V4 confidence-inversion impact study at [V4_CONFIDENCE_INVERSION_IMPACT_v1.md](https://github.com/lluvr/frame-check-mcp/blob/master/V4_CONFIDENCE_INVERSION_IMPACT_v1.md).
- Construct-honesty audit infrastructure: [VALIDATION_PROGRAM.md](https://github.com/lluvr/frame-check-mcp/blob/master/VALIDATION_PROGRAM.md).
