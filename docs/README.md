# Documentation

Navigation for the substantive documents shipped in this directory and adjacent
paths. Each pointer below is the start of a real document; this file just helps
you find the one that matches your need.

## Reading paths by intent

### "I want to install and use the MCP server"

1. [`../README.md`](../README.md): install in 60 seconds + Quickstart for Claude
   Desktop, Cursor, Cline, Continue.dev.
2. [MCP_SERVER.md](MCP_SERVER.md): full reference: tool surface (`frame_check`,
   `frame_compare`), resource scheme (`frame-check://`), prompt templates,
   provenance contract, cost discipline ($0.00 per query).

### "I want to evaluate the methodology"

1. [`../METHODOLOGY.md`](../METHODOLOGY.md): the methodology paper (v0.3.1 draft).
   Read sections §1 (substrate), §3 (frame library), §6 (validation program),
   §7 (honest limits).
2. [ANTICIPATED_CRITIQUES.md](ANTICIPATED_CRITIQUES.md): self-enumerated
   adversarial readings of the project's claims.
3. [V4_2_GAP_INVENTORY_v1.md](V4_2_GAP_INVENTORY_v1.md): 28 self-disclosed
   engine gaps with remediation roadmap. The "proud to own in 2-3 years" bar.

### "I want to understand frame divergence"

1. [FRAME_DIVERGENCE_v1.md](FRAME_DIVERGENCE_v1.md): Part 1: definition,
   sovereignty argument, non-negotiables (canonical c1.0).
2. [FRAME_DIVERGENCE_CONTRACT_v1.md](FRAME_DIVERGENCE_CONTRACT_v1.md): Part 2:
   the wire contract for the `divergence` block, MCP resource URIs, error
   envelope, versioning commitments.
3. [FRAME_DIVERGENCE_v2.md](FRAME_DIVERGENCE_v2.md): broader architecture:
   layered taxonomy (L0-L3), five-stage lifecycle, supersedes v1's narrow
   definition by absorption while preserving the c1.0 contract.

### "I want to validate the substrate myself"

1. [VALIDATION_PROGRAM.md](VALIDATION_PROGRAM.md): observational + formal
   validation plans (Phase 1: gold-standard substrate; Phase 2: rater study).
2. [RATERS.md](RATERS.md): Phase 2 rater contract: time commitment,
   deliverable shape, blinding requirement, how to engage.
3. [`../calibration/results/`](../calibration/results/): per-run REPORT.md
   files documenting empirical detector firing rates against the calibration
   corpus.
4. [`../validation/decision_readiness/results/`](../validation/decision_readiness/results/)
  : date-stamped harness re-runs of the decision-readiness profile against
   the validation corpus.

### "I want to verify the audit"

1. [internal/MCP_CLIENT_CONFORMANCE_v1.md](internal/MCP_CLIENT_CONFORMANCE_v1.md)
  : 32/32 conformance round-trips against the installed wheel.
2. [internal/LEAKAGE_AUDIT_v1.md](internal/LEAKAGE_AUDIT_v1.md): pre-publish
   leakage findings (16 catalogued, 14 closed + 2 partial).
3. [internal/REMEDIATION_LOG_v1.md](internal/REMEDIATION_LOG_v1.md):
   per-finding remediation record.
4. [internal/PUBLISH_READINESS_VERDICT_v1.md](internal/PUBLISH_READINESS_VERDICT_v1.md)
  : the campaign synthesis verdict.
5. [EXTRACT_POLICY.md](EXTRACT_POLICY.md): the public/private boundary
   policy that governs which files in the upstream tree ship to the public
   mirror.

### "I want to read the worked examples"

[`../data/worked_examples/`](../data/worked_examples/): four published
worked examples with multi-LLM comparisons + per-document Frame Check
analysis. Each has a `.md` writeup and a directory carrying the underlying
JSON artifacts (LLM responses, frame_check results, pairwise comparisons).

Suggested entry point: `four-llms-on-bitcoin-retirement-2026.md`: same
question across four frontier LLMs, materially different framing
signatures, the cleanest demonstration of the sovereignty case.

## Artifacts in this directory

- [ANTICIPATED_CRITIQUES.md](ANTICIPATED_CRITIQUES.md): self-enumerated
  adversarial readings.
- [EXTRACT_POLICY.md](EXTRACT_POLICY.md): public/private boundary policy.
- [FRAME_DIVERGENCE_v1.md](FRAME_DIVERGENCE_v1.md): Part 1: definition.
- [FRAME_DIVERGENCE_CONTRACT_v1.md](FRAME_DIVERGENCE_CONTRACT_v1.md): Part 2:
  wire contract (c1.0 shipping).
- [FRAME_DIVERGENCE_v2.md](FRAME_DIVERGENCE_v2.md): broader architecture
  (supersedes v1 Parts 3-4).
- [MCP_SERVER.md](MCP_SERVER.md): full MCP server reference.
- [RATERS.md](RATERS.md): Phase 2 rater contract.
- [V4_2_GAP_INVENTORY_v1.md](V4_2_GAP_INVENTORY_v1.md): engine gap inventory.
- [VALIDATION_PROGRAM.md](VALIDATION_PROGRAM.md): validation plans.
- [internal/](internal/): maintainer-internal supporting documents shipped
  publicly under evidence discipline (audit deliverables,
  methodology paper outlines, archived design proposals). Not required
  reading; provided so a determined evaluator can reproduce the
  publish-readiness verdict.

## What this index is not

- Not a substitute for reading the canonical documents.
- Not a release-notes log; see [`../CHANGELOG.md`](../CHANGELOG.md).
- Not a tutorial; see [`../README.md`](../README.md) for the 60-second install path.
