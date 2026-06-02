# Frame Check

[![PyPI](https://img.shields.io/pypi/v/frame-check-mcp.svg)](https://pypi.org/project/frame-check-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/frame-check-mcp.svg)](https://pypi.org/project/frame-check-mcp/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Tests](https://github.com/lluvr/frame-check/actions/workflows/tests.yml/badge.svg)](https://github.com/lluvr/frame-check/actions/workflows/tests.yml)

See what any document does not show you.

Frame Check is a deterministic structural framing analysis tool. It
names which analytical perspectives a document takes, which it omits,
and how it positions the reader, and it cross-checks the document's
numeric claims against primary sources a language model can't reach
(SEC EDGAR, FRED, World Bank, and others). It makes no LLM call of its
own, so the same document always returns the same reading at no model
cost.

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

### Verifying the wheel (sigstore attestation)

Every published wheel ships with a sigstore build-provenance
attestation generated inside the GitHub Actions publish workflow
via OIDC. Adopters who want to verify the wheel was built from
this repository's CI (and not modified between the runner and
PyPI) can do so with the `gh` CLI:

    pip download frame-check-mcp --no-deps -d /tmp/fc-verify
    gh attestation verify /tmp/fc-verify/frame_check_mcp-*.whl \
      --owner Clarethium

A passing verification proves the wheel artifact's hash matches
the one signed by the publish workflow run for the corresponding
tag, with the workflow file path and git SHA recorded in the
attestation. Verification is optional; security-conscious
deployments and packaging mirrors may want it as part of their
install pipeline.

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
  cues and worked examples. Matches are candidate-level signals, not
  verified labels.
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

Named-pattern detection is a separate, beta layer from the structural
profile. It surfaces candidate matches, under-detection markers,
density caveats, and confidence states rather than confident labels,
so you can see where the tool is unsure instead of trusting an
overconfident verdict.

Calibration figures, honest limits, and the methodology behind them
live in the methodology at frame.clarethium.com/corpus/methodology.

## Why this and not just an LLM

An MCP-compatible AI client can already analyse a document by
prompting an LLM. Frame Check earns its install footprint where the
LLM falls short:

- **Determinism.** The structural layer returns the same numbers for
  the same input across runs, deploys, and model versions. An LLM
  asked "what frames does this document use" gives a different
  answer each time and a different answer per model. Reproducible
  analysis needs the deterministic shape; opinions can layer on top.
- **Zero per-query cost.** Frame Check's MCP server makes no LLM
  call server-side. The caller's agent does the prose interpretation
  if the user wants that. This means a frame-check on a 10,000-word
  document costs the user $0.00, not the $0.05 to $0.50 an LLM
  call would charge.
- **Explicit absence.** The frame-divergence block names what the
  document does not address by comparing matched frames against the
  Frame Vocabulary Standard catalog. An LLM asked "what's missing"
  hallucinates plausible-sounding gaps; Frame Check enumerates
  catalog entries that did not fire on the text and says so.
- **Calibrated detection.** The named-pattern layer is labelled beta
  in the API responses (`engine_status: beta`) and surfaces
  under-detection markers rather than confident labels. You get an
  honest "this is uncertain" instead of a confident guess.
- **Source verification.** Numeric claims with provider coverage get
  cross-checked against SEC EDGAR / FRED / World Bank / REST
  Countries / Alpha Vantage / Wolfram Alpha at provider pricing tiers (zero or
  user-keyed). An LLM asked "is this number right" cannot fetch
  primary sources; Frame Check does.

Deterministic, source-grounded measurement is not work an LLM is
suited to do. Frame Check provides that layer so the LLM can lean
on it instead of being asked to do that work in-band.

## Worked example

Same prompt, four frontier LLMs, four materially different framing
signatures.
[`data/worked_examples/four-llms-on-bitcoin-retirement-2026.md`](data/worked_examples/four-llms-on-bitcoin-retirement-2026.md)
runs Claude Haiku 4.5, GPT-5, Grok 4.1 Fast Reasoning, and Gemini 2.5
Flash against an investment question and surfaces the per-model
structural shape: voice, coverage, frame matches, sourcing rate. The
point in plain form: your AI is one framing choice among several, not
the framing.

Five more published examples live alongside it: framings of an LLM
response to a life-decision prompt, an AI-company founder essay, an
FOMC monetary-policy statement, and a Source-Network verification pass
on an LLM-summarised earnings release, plus a divergence walk-through
on Claude's Bitcoin retirement recommendation. See
[`data/worked_examples/`](data/worked_examples/) for the full set.

## Documentation

Browse [`docs/README.md`](docs/README.md) for reading paths organised
by intent (install + use, understand frame divergence, read the worked
examples). The full inventory:

- `docs/MCP_SERVER.md`: MCP server reference (tools, resources, prompts)
- `docs/COOKBOOK.md`: five recipes for common adopter tasks (frame-check before agent commit, divergence at decision points, source-grounded verification, two-LLM comparison, custom FVS rule)
- `docs/FRAME_DIVERGENCE_CONTRACT_v1.md`: interface contract for the Frame Divergence emission shape (c1.0)
- `data/frame_library/`: 20-entry Frame Vocabulary Standard catalog
- `data/worked_examples/`: published worked examples with multi-LLM comparisons + per-document Frame Check analysis (6 entries)
- The methodology behind the Frame Vocabulary Standard is documented at frame.clarethium.com/corpus/methodology

## Running tests

    pip install -e .[test]
    python3 run_tests.py

Or directly via pytest:

    python3 -m pytest -q

26 test files under `tests/`, ~30 seconds end-to-end. Includes 40 adversarial dispatcher test functions in `tests/test_mcp_adversarial.py` (parametrized into 63 tests at collection time), a per-module 80% coverage gate on the seven wheel-surface modules (`scripts/check_per_module_coverage.py`), the cookbook-recipe contract suite (`tests/test_cookbook_recipes.py`), and the genre-classifier + frame-divergence coverage.

## License

Apache-2.0 for code; CC-BY-4.0 for the FVS library and worked examples
(see `NOTICE` for the per-directory enumeration).

## Citation

If Frame Check is useful in your work, see `.github/CITATION.cff` for
the citable form. Frame Check is authored by Lovro Lucic.

## Contributing

Sign-off-by-DCO required per `.github/CONTRIBUTING.md`. Governance per
`.github/GOVERNANCE.md` (BDFL model with named forcing functions for
canon-promotion decisions).

## Issues

https://github.com/lluvr/frame-check/issues
