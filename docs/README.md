# Documentation

Navigation for the substantive documents in this directory and adjacent paths.
Each pointer below is the start of a real document; this file just helps
you find the one that matches your need.

## Reading paths by intent

### "I want to install and use the MCP server"

1. [`../README.md`](../README.md): install in 60 seconds + Quickstart for Claude
   Desktop, Cursor, Cline, Continue.dev.
2. [MCP_SERVER.md](MCP_SERVER.md): full reference: tool surface (`frame_check`,
   `frame_compare`), resource scheme (`frame-check://`), prompt templates,
   provenance contract, cost discipline ($0.00 per query).
3. [COOKBOOK.md](COOKBOOK.md): five concrete recipes for common adopter tasks
   (frame-check before agent commit, divergence at decision points,
   source-grounded verification, two-LLM structural comparison, custom FVS
   rule contribution).

### "I want to evaluate the methodology"

The methodology is documented at
[frame.clarethium.com/corpus/methodology/](https://frame.clarethium.com/corpus/methodology/).
It is the reference for the methodology, frame library, and honest
limits.

### "I want to understand frame divergence"

[FRAME_DIVERGENCE_CONTRACT_v1.md](FRAME_DIVERGENCE_CONTRACT_v1.md) is the
adopter-facing wire contract for the `divergence` block: MCP resource URIs,
error envelope, versioning commitments. The contract version `c1.0` is the
shipping interface; future revisions follow the documented compatibility
discipline.

### "I want to verify the wheel"

The reproducibility verification path is documented in
[`../.github/SECURITY.md` "How to verify the audit yourself"](../.github/SECURITY.md). It
walks through installing the wheel, running the conformance driver, the
adversarial harness, and the canon-discipline audit against any released
wheel.

### "I want to read the worked examples"

[`../data/worked_examples/`](../data/worked_examples/): six published
worked examples with multi-LLM comparisons and per-document Frame Check
analysis. Each has a `.md` writeup and a directory carrying the underlying
JSON artifacts (LLM responses, frame_check results, pairwise comparisons).

Suggested entry point: `four-llms-on-bitcoin-retirement-2026.md` runs the
same question across four frontier LLMs and surfaces materially different
framing signatures.

## Artifacts in this directory

- [COOKBOOK.md](COOKBOOK.md): five recipes for common adopter tasks.
- [FRAME_DIVERGENCE_CONTRACT_v1.md](FRAME_DIVERGENCE_CONTRACT_v1.md): the
  adopter-facing wire contract for the `divergence` block (c1.0 shipping).
- [MCP_SERVER.md](MCP_SERVER.md): full MCP server reference.

## What this index is not

- Not a substitute for reading the canonical documents.
- Not a release-notes log; see [`CHANGELOG.md`](CHANGELOG.md).
- Not a tutorial; see [`../README.md`](../README.md) for the 60-second install path.
