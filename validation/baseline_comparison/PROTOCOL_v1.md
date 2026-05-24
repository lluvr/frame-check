# Baseline-comparison protocol v1

**Status:** pre-registered, not yet executed. Pilot pending authorization.
**Date pre-registered:** 2026-05-11
**Repo path:** `validation/baseline_comparison/`
**Sibling protocol:** `validation/wedge_behavior/PROTOCOL_v1.md` (load-bearing-shift measurement on agent responses)

## What this protocol exists to test

The Frame Check pitch to expert labs rests on two claims:

> 1. Frame Check is **deterministic + reproducible + zero per-query LLM cost**. Same input, same numbers, across runs and models. The structural layer never calls an LLM server-side.
> 2. Frame Check produces information a frontier LLM with a comparable framing-analysis prompt does not produce.

Claim 1 is structural and verifiable end-to-end against the implementation: tests, conformance driver, and sigstore attestation cover it. Claim 2 is empirical. Without a head-to-head comparison against a frontier LLM doing the same job, claim 2 is a design assertion.

This protocol is the empirical foothold for claim 2.

## Hypothesis

**H1 (named-absence advantage).** Frame Check's `divergence.absent_frames` block names structurally-absent canonical frames more reliably than a frontier LLM prompted "what's missing from this document's framing." Pre-registered effect direction: in N >= 20 documents, Frame Check names absences a panel of trained raters scores as VALID at a rate >= the LLM's, with the LLM's false-positive (hallucinated-absence) rate strictly higher.

**H2 (source-fidelity advantage).** When `source_text` is provided alongside `document_text`, Frame Check's per-claim `verification.source_fidelity.unsourced_items` identifies numbers present in document but absent from source via literal digit-substring match (scoped by token boundaries; see `docs/MCP_SERVER.md` for the catches/misses table). A frontier LLM prompted "list any numbers in the document that are not in the source" returns answers whose error profile differs from Frame Check's mechanical check.

Pre-registered claims:

  - **Zero false POSITIVES from Frame Check** (a number flagged `not_in_source` is verifiably not a token-bounded digit substring of the source). The substring match is deterministic.
  - **Frame Check's known false-NEGATIVE class**: same number expressed in materially different formats (`$22.1 billion` vs `$22,100,000,000`; rounded vs precise) registers as `not_in_source` despite semantic equivalence. This is a calibrated limit, not a defect; the H2 test measures whether the LLM's false-negative rate is LOWER (it might catch format-equivalent numbers Frame Check misses) AND whether its false-positive rate is HIGHER (since the LLM is interpretive, not deterministic).
  - **The directional test**: ratio of (LLM false positives) to (Frame Check false negatives) over the N=10 corpus. Pre-registered effect direction: ratio > 1 (LLM's interpretive errors exceed Frame Check's format-rigidity errors on a corpus of real LLM-summary-vs-source pairs). The null is ratio ≤ 1 — meaning interpretive matching wins on this corpus.

**H3 (reproducibility advantage).** Frame Check returns byte-identical structured output for byte-identical input across runs. A frontier LLM returns materially-different framing analyses across runs of the same document at non-zero temperature, and across model versions even at temperature zero. Pre-registered: 5 runs of each (Frame Check + LLM) on N >= 10 documents, measured as Jaccard distance of named-frame sets per pair.

**Null on H1.** No advantage on named-absence reliability. The pitch's "explicit absence" claim is theater.
**Null on H2.** No advantage on source-fidelity precision. The pitch's "deterministic source verification" claim is theater.
**Null on H3.** LLM output is stable enough that the determinism pitch does not differentiate.

## Sample-selection criteria

Documents are drawn from the boundary of "framing analysis is non-trivial." Not from where Frame Check's detectors are calibrated (that is the wedge_behavior protocol's territory).

Inclusion criteria:

- Document length 300-2,000 words. Same window as the wedge protocol so cross-protocol comparison is possible.
- Document is in the analytical-prose calibration window (English, paragraphed text).
- For H2: document must have a paired source text (LLM summary of a press release, AI paraphrase of a paper, model-generated analysis of a report). At least one number that does not literal-match source.
- Documents NOT in `data/worked_examples/` or `data/adversarial_fixtures/` (otherwise training-data contamination is possible).

Exclusion criteria:

- Documents under 300 words (density-based detectors are noisy).
- Documents over 2,000 words (LLM context-pressure confound).
- Code, poetry, non-English, or non-paragraphed text.

Sample size:

- **Pilot:** N=3 documents. You select to span recommendation, analysis, and opinion shapes. Pilot output is rubric calibration, not a hypothesis test.
- **Main study (H1):** N=20 documents drawn after pilot rubric stabilizes. Two trained raters per document. Inter-rater agreement target Cohen's kappa >= 0.6 (substantial agreement).
- **Main study (H2):** N=10 paired document-source pairs. Both raters score Frame Check + LLM identification of unsourced numbers against ground truth (which is literal substring presence in source, computable without rater).
- **Main study (H3):** N=10 documents, 5 runs each side. Jaccard distances computed mechanically.

## Treatment design

For each document, three measurement runs:

1. **Frame Check structural analysis.** `mcp_server.build_epistemic_payload(document_text, source_text=..., include_divergence=True)`. Captures all wire fields (voice, coverage, divergence.absent_frames, verification.source_fidelity, frame_library_matches, decision_readiness).

2. **LLM-prompted framing analysis (baseline).** A single frontier LLM is selected and pinned before the pilot (your authorization). Default candidate as of pre-registration date (2026-05-11): Claude Sonnet 4.6 at temperature 0.7. The exact model identifier (including any provider-side version suffix) and temperature are recorded in the per-document results record at execution time; same model + temperature + system prompt across all N documents within the same pilot or main-study run. If the default candidate is deprecated by the provider before execution, you select the strongest available substitute and records the substitution rationale in the results writeup. The pre-registration commits to the prompt template + the head-to-head methodology, not to a model identifier that may not survive to execution.

   Prompt template (locked at pre-registration):
   ```
   You are analyzing a document's framing. Produce a structured analysis with:
   - voice classification (one of: directive / promotional / descriptive / analytical)
   - five analytical perspectives addressed (causes, risks, stakeholders, trends, uncertainty);
     for each, mark present or absent
   - named framing patterns you detect (use the Frame Vocabulary Standard if you know it,
     otherwise describe in your own terms)
   - structurally absent framing patterns the document does not address but
     comparable documents would
   - numerical claims you can identify in the document; mark each as present in source or
     not present in source

   Document:
   <document_text>

   Source (for numerical claims):
   <source_text>

   Output as structured JSON.
   ```

3. **Reproducibility run (H3 only).** Each side is re-run 5 times under identical inputs. Frame Check is expected to return byte-identical output (deterministic claim). LLM is expected to return materially-different output (the empirical question).

## Output capture

Per document, save under `validation/baseline_comparison/results/<doc_slug>/`:
- `document.md`: the source document text + provenance (URL or generated-prompt + capture timestamp + SHA-256).
- `source.md` (optional, when paired): the source text for H2.
- `frame_check_payload.json`: full Frame Check payload from run 1.
- `frame_check_runs.json` (H3): list of payloads from runs 2-5 (expected byte-identical to run 1).
- `llm_baseline_run1.json`: the LLM's output from prompt template above.
- `llm_baseline_runs.json` (H3): list of LLM outputs from runs 2-5 (expected materially-different).
- `rater_scores.json`: per-rater scores per dimension per hypothesis. Populated by rater pool.

## Rating rubric

See `rating_rubric_v1.md` for the per-rater rubric. Pre-registered before pilot.

## Open questions before execution

- **LLM selection.** Sonnet 4.6 is the default candidate as of pre-reg date. You can substitute another frontier model with justification recorded in the results writeup before pilot. The point is to test the strongest plausible baseline, not a weakened one. Pre-registration commits to the prompt + methodology, not a specific model identifier.
- **Rater compensation.** Compensation rate and rater recruitment is your responsibility; documented separately.
- **Source corpus.** Worked examples are EXCLUDED from sample selection. Documents must come from outside the bundled fixtures to avoid contamination.

## Why this is its own protocol (not a fold-in to wedge_behavior)

Wedge_behavior tests agent-response shift. Baseline_comparison tests artifact-level information advantage. Different units of analysis: agent behavior vs. raw analysis output. Combining the rating rubrics would produce a study that is harder to falsify on either dimension; keeping them separate keeps each hypothesis independently testable.

## Out of scope for v1

- **Confidence calibration of Frame Check vs. LLM.** Both produce confidence-like signals; whether they are calibrated against ground truth is a separate study.
- **Cost comparison.** Trivially in Frame Check's favor at $0/query vs. LLM per-token; the interesting claim is information advantage, not cost.
- **Latency comparison.** Trivially in Frame Check's favor (1.3ms p50 vs. seconds for an LLM call); same as cost.

These are real benefits but separate measurements; the pre-registration here is on the information-advantage claim.
