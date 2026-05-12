# Wedge behavior-change study — status

**Pre-registered protocol:** [`PROTOCOL_v1.md`](PROTOCOL_v1.md)
**Pilot smoke test:** executed 2026-05-12 (data kept private, not committed to this repo)
**Main study (N=10):** pending external-document sourcing + independent rater pool

## What ships in this directory

- [`PROTOCOL_v1.md`](PROTOCOL_v1.md) — pre-registered hypothesis, sample-selection criteria, treatment design, rubric, decision rule.
- [`run_pilot.py`](run_pilot.py) — produces both arm prompts (without-tool, with-tool) for one document.
- [`run_arms.py`](run_arms.py) — drives both arms via Anthropic API (Claude Sonnet 4.6, temperature 0.7, fixed system prompt; separate API calls per arm = no carryover). Captures responses with full execution metadata. Spend bounded; ~$0.18 per document run at v1.0.x pricing.
- [`rubric_template.md`](rubric_template.md) — per-rater scoring form (5 binary items per response pair).

This is the framework. Anyone with `ANTHROPIC_API_KEY` and a document corpus can execute the protocol end-to-end.

## What does NOT ship in this directory

The 2026-05-12 pilot was a **harness smoke test**, not validation evidence. Per-document data is kept private, not committed to this repo. The pilot used:

- **Two agent-authored documents** (one recommendation-shaped on Roth conversions, one opinion-shaped on AI regulation). Methodologically these are stress materials, not test fixtures — they were composed with knowledge of frame_check's signature, then run through the pipeline.
- **One rater (Claude in agent mode)**, proxying for operator review. Same agent family produced and scored both arms.
- **N=2** documents (descriptive only per pre-reg).

A reviewer reading per-document scoring under those conditions would correctly read it as pipeline verification, not as evidence about the wedge claim. Publishing the data in this public repo created a high risk of misinterpretation (synthetic opinion documents could be mistaken for Clarethium positioning; "load-bearing shift = YES on both" could be over-read despite the protocol's "pilot is descriptive only" caveat). The chosen path (private pilot data, public framework) preserves the methodologically valid output of the smoke test while removing the demonstration-as-evidence risk.

## What the smoke test surfaced (legitimate output)

Three rubric refinements for v2 if accepted by operator:

**Calibration finding 1 — Item 1 boundary case (catalog-naming as distinct evidence).** When the without-tool agent identifies a gap in plain English and the with-tool agent identifies the SAME gap via a catalog frame name (FVS-XXX) with citation URI + corpus prevalence count, both arms named the absence. The DIFFERENCE is epistemic provenance — the catalog name is citable, traceable, falsifiable. v2 rubric should clarify: catalog-naming with citation URI counts as a distinct named-absence even when the underlying issue is also discussed by the without-tool agent.

**Calibration finding 2 — Item 2 dominance vs. presence.** Both arm responses contain a mix of reading-form and verdict-form passages. The rubric scores YES on item 2 if reading-form appears anywhere; the more interesting signal is DOMINANT register. v2 should add a sub-level: "is reading-form the dominant register, or only an occasional appearance among verdict-form passages?"

**Calibration finding 3 — Item 4 distinguishes two kinds of hedge calibration.** The rubric example is "without-tool overstates → with-tool rebalances." A second kind: with-tool surfaces the document's hedge density as a quantified measurement ("9 numerical claims, 7 unhedged"; "19% sentence attribution"), turning the without-tool's qualitative observation into a measured rate. v2 should split item 4 into 4a (agent-side hedge calibration) and 4b (document-side hedge density as data).

These calibration findings are the legitimate output of the smoke test — methodology refinements that can ship into PROTOCOL_v2 before main-study execution.

## Path to actual validation evidence

The 2026-05-12 smoke test verified the pipeline. The next gate is methodologically credible evidence, which requires three changes:

1. **Externally-sourced documents.** Documents must come from outside the author's reach — public LLM-output corpus (LMSYS chatbot arena, etc.), random sample of recent op-eds from major publications with URL + retrieval timestamp + SHA, or Wikipedia featured articles. Eliminates the self-authored-document confound.
2. **Independent raters.** Per pre-reg, the main study requires three independent raters with Gwet's AC1 reported per item. The operator's pool selection determines the credibility ceiling.
3. **Rubric refinements applied.** PROTOCOL_v2 with the three calibration findings above (or operator's modifications) locks before main-study execution.

The harness in this directory is ready to drive the main study once the three above are sourced. Estimated spend at N=10 with main-study sample: ~$2 in API cost; rater compensation per operator's recruitment pool.

## Honest scope of the smoke test (what was actually demonstrated)

The 2026-05-12 smoke test demonstrated:

- The pipeline (frame_check → both arms via API → response capture → rubric scoring → aggregation) works end-to-end.
- The pre-registered rubric is operationally testable; the three calibration findings above are concrete refinements before main-study execution.
- API spend is well below the protocol's $1 ceiling at the pilot scale.

It did NOT demonstrate:

- That the wedge claim holds (N=2, agent-authored docs, single same-family rater = pipeline verification, not validation).
- That the result generalizes beyond Claude Sonnet 4.6 at temperature 0.7.
- That the rubric distinguishes load-bearing shift from theater under independent-rater conditions.

The wedge claim — "agent responses shift in load-bearing ways when frame_check is invoked" — remains a design assertion until the main study under PROTOCOL_v2 with externally-sourced documents and independent raters publishes results.
