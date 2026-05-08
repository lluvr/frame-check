# Frame Check

[![PyPI](https://img.shields.io/pypi/v/frame-check-mcp.svg)](https://pypi.org/project/frame-check-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/frame-check-mcp.svg)](https://pypi.org/project/frame-check-mcp/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19888849.svg)](https://doi.org/10.5281/zenodo.19888849)
[![Tests](https://github.com/Clarethium/frame-check/actions/workflows/tests.yml/badge.svg)](https://github.com/Clarethium/frame-check/actions/workflows/tests.yml)

See what any document does not show you.

Frame Check is a structural framing analysis tool. It names which
perspectives a document takes, which it omits, and how it positions
the reader. Numerical claims are cross-checked against authoritative
sources where coverage exists.

## Quickstart (MCP server)

The PyPI package `frame-check-mcp` is the Model Context Protocol
server. It runs locally and gives any MCP-compatible AI client
(Claude Desktop, Cursor, Cline, Continue.dev, etc.) deterministic
structural framing analysis as a tool.

    pip install frame-check-mcp

Then point your MCP client at the installed entry point. For
Claude Desktop, add to `claude_desktop_config.json`:

    {
      "mcpServers": {
        "frame-check": {
          "command": "frame-check-mcp"
        }
      }
    }

Restart the client. Then in any conversation: "Can you frame-check
this document?" Full install + verification details in `docs/MCP_SERVER.md`.

## What it does

Pass a document and Frame Check returns:

- A structural framing profile: which of five analytical perspectives
  (causes, risks, stakeholders, trends, uncertainty) the document
  covers, which it omits, and the density of each.
- Voice and epistemic posture: how the document positions the reader,
  and what share of claims are attributed to sources.
- Temporal orientation: whether the document grounds its conclusions
  in historical data, present state, or projections.
- Frame Vocabulary Standard candidate matches: named frame patterns
  whose rule-based signals fire on the text, each with identification
  cues and worked examples. Matches are candidate-level; precision
  against multi-source labeling is an active research question.
- Source-network verification: numeric claims checked against SEC
  EDGAR, FRED, World Bank, REST Countries, Alpha Vantage, and Wolfram
  Alpha where those providers have coverage.
- An optional AI narrative interpreting framing at prose level.
  Labelled distinctly so readers do not conflate language-model
  interpretation with deterministic measurement.

## Approach

Structural measurement is the floor. Every framing claim the tool
makes is computed from deterministic pattern matchers and always
returns the same result for the same input. AI-assisted interpretation
is available as enrichment where an API key is configured, but is
labelled as such and never hidden behind the structural layer.

Verification is bounded. The tool only verifies numeric claims against
providers with genuine coverage for the claim type, and it surfaces
its own calibration results (precision, recall, F1 per provider)
rather than asserting verdicts without evidence.

Named-pattern detection is a separate reliability layer from the
structural profile. Detector F1 = 0.36 against expert labelers in a
pre-registered validation, below the useful threshold of 0.4. The
pivot to construct-honesty surfacing (under-detection markers,
density caveats, confidence states) rather than confident labels is
the load-bearing claim at v0; a reader-aid study (Track B,
pre-registered) tests whether this surfacing actually helps a reader
see framing they would otherwise miss.

Honest limits and anticipated adversarial readings are catalogued in
`docs/ANTICIPATED_CRITIQUES.md`.

## Worked example

Same prompt, four frontier LLMs, four materially different framing
signatures.
[`data/worked_examples/four-llms-on-bitcoin-retirement-2026.md`](data/worked_examples/four-llms-on-bitcoin-retirement-2026.md)
runs Claude Haiku 4.5, GPT-5, Grok 4.1 Fast Reasoning, and Gemini 2.5
Flash against an investment question and surfaces the per-model
structural shape: voice, coverage, frame matches, sourcing rate. The
sovereignty case in plain form: your AI is one framing choice among
several, not the framing.

Five more published examples live alongside it: framings of an LLM
response to a life-decision prompt, an AI-company founder essay, an
FOMC monetary-policy statement, and a Source-Network verification pass
on an LLM-summarised earnings release, plus a divergence walk-through
on Claude's Bitcoin retirement recommendation. See
[`data/worked_examples/`](data/worked_examples/) for the full set.

## Documentation

Browse [`docs/README.md`](docs/README.md) for reading paths organised
by intent (install + use, evaluate the methodology, understand frame
divergence, validate the substrate, verify the audit, read the worked
examples). The full inventory:

- `METHODOLOGY.md`: full methodology paper (draft)
- `docs/MCP_SERVER.md`: MCP server reference (tools, resources, prompts)
- `data/frame_library/`: 20-entry Frame Vocabulary Standard catalog
- `data/worked_examples/`: published worked examples with multi-LLM comparisons + per-document Frame Check analysis (6 entries)
- `docs/FRAME_DIVERGENCE_v1.md` (Part 1: definition) + `docs/FRAME_DIVERGENCE_CONTRACT_v1.md` (Part 2: interface contract, c1.0 shipping) + `docs/FRAME_DIVERGENCE_v2.md` (broader architecture, supersedes v1 Parts 3-4)
- `docs/ANTICIPATED_CRITIQUES.md`: self-enumerated adversarial readings
- `docs/VALIDATION_PROGRAM.md`: observational + formal validation plans
- `docs/V4_2_GAP_INVENTORY_v1.md`: self-disclosed engine gap inventory + remediation plan
- `docs/RATERS.md`: rater protocol for the validation program
- `docs/internal/MCP_CLIENT_CONFORMANCE_v1.md`: 32/32 conformance round-trips against the installed wheel
- `docs/internal/`: maintainer-internal supporting documents (audit deliverables, methodology paper outlines, archived design proposals) shipped publicly under evidence discipline

## Running tests

    pip install -e .[test]
    python3 run_tests.py

Or directly via pytest:

    python3 -m pytest -q

25 test files, ~30 seconds end-to-end. Includes 40+ adversarial dispatcher test functions in `tests/test_mcp_adversarial.py` (parametrized into more tests at collection time) plus the V4.2 engine + classifier coverage.

## License

Apache-2.0 for code; CC-BY-4.0 for the FVS library and worked examples
(see `NOTICE` for the per-directory enumeration).

## Citation

If Frame Check is useful in your work, see `CITATION.cff` for the
citable form. Frame Check is authored by Lovro Lucic; named authorship
is the project's primary credibility asset per the construct-honesty
discipline.

## Contributing

Sign-off-by-DCO required per `CONTRIBUTING.md`. Governance per
`GOVERNANCE.md` (BDFL model with named forcing functions for
canon-promotion decisions). External rater engagement per
`docs/RATERS.md`.

## Issues

https://github.com/Clarethium/frame-check/issues
