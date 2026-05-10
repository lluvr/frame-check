# Cookbook

Recipes for common adopter tasks against the Framecheck MCP server.
Each recipe states the use case, the MCP request that drives it, the
load-bearing response fields, and the honest limits an adopter
should know about before they rely on the result.

The recipes assume the MCP server is installed (`pip install
framecheck-mcp`) and configured in your MCP client per
[`docs/MCP_SERVER.md`](MCP_SERVER.md). All examples show the
JSON-RPC payload your client sends; an MCP client like Claude
Desktop or Cursor builds and dispatches that payload from a natural
language request.

The full MCP contract reference lives in
[`docs/MCP_SERVER.md`](MCP_SERVER.md); each recipe links to the
section that describes the tool / resource being used.

---

## Recipe 1: Frame-check before an AI agent commits to a recommendation

### Use case

An agent is producing a multi-paragraph recommendation (investment
thesis, technical decision memo, policy proposal). Before the
recommendation enters a downstream artifact (PR description, email
draft, document committed to a repo), run the frame-check tool and
surface what's missing structurally.

### MCP request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "frame_check",
    "arguments": {
      "document_text": "<the agent's draft, full text>",
      "include_divergence": true,
      "domain_hint": "founder_decision"
    }
  }
}
```

### Load-bearing fields

- `analysis.coverage`: which of the five analytical perspectives
  (causes, risks, stakeholders, trends, uncertainty) the draft
  carries. A draft with `risks: 0.0` is recommending without naming
  any failure mode.
- `analysis.frame_library_matches[]`: which Frame Vocabulary Standard
  entries fired on the text (each match carries `library_url` and
  `signal_strength`).
- `divergence.absent_frames[]`: the structural gaps. Each entry has
  `fvs_id`, `name`, `signal_strength`, and `agent_guidance` text the
  agent surfaces back to the user.
- `agent_guidance.suggested_next_actions[]`: 2-4 specific moves the
  agent should consider taking next: which entries to read, which
  reprompts to put back to the source AI, when to invoke the
  challenge-document MCP prompt.
- `provenance.analysis_cost_usd`: always 0.0; verifies no LLM call
  happened at the analysis layer.

### Honest limits

The detector reports F1 = 0.36 against expert labelers; named-pattern
matches are a *lower bound* (presence is high-confidence, absence is
not high-confidence). Use the divergence block as a structural prompt
for the agent's next draft, not as a verdict on what the document
"should" cover.

---

## Recipe 2: Frame divergence at decision points

### Use case

You are about to act on an LLM-produced reading of a document
(for example: act on a recommendation, accept a plan, take a position
based on the LLM's framing). Before acting, see what frames the LLM
did not put into its reading.

### MCP request

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "frame_check",
    "arguments": {
      "document_text": "<the LLM's reading, or the source document the LLM read>",
      "include_divergence": true,
      "divergence_rendering": "teaching_questions"
    }
  }
}
```

The `divergence_rendering` field accepts `list` (the default; bare
catalog entries), `completeness_check` (yes/no surface for each FVS
dimension), `teaching_questions` (each absence rendered as a
question the reader could put back to the source AI), or
`narrative` (paragraph form, suitable for showing to a non-technical
reader).

### Load-bearing fields

- `divergence.envelope.catalog_version`: the Frame Vocabulary
  Standard catalog the comparison ran against. Pin in citations.
- `divergence.absent_frames[]` ordered by `signal_strength`
  (`high` → `moderate` → `weak`). The first 3-5 entries are the
  load-bearing structural gaps for a decision-context document.
- `divergence.envelope.v4_2_engine_status`: `beta` at the current
  line. The under-detection-marker pivot means an absent frame is
  "the pattern did not fire," not "the document does not address
  this"; the distinction matters for any decision the absence
  informs.

### Honest limits

The catalog at v0.x is 20 entries; some structural shapes are not
yet catalogued. Absence on a non-catalogued dimension does not
fire because the pattern is not in the FVS at all. The divergence
block is the right tool for the catalog's current scope, not for
arbitrary structural framing.

---

## Recipe 3: Source-grounded verification of an LLM summary

### Use case

You have an LLM-produced summary of an earnings release, an
analyst note, or a research paper, and you have the underlying
source material that summary was supposed to ground in. Pass both
to Framecheck and see which claims in the summary are grounded
in the source, paraphrased, or fabricated.

### MCP request

Pass the LLM's output as `document_text` and the underlying
source as `source_text`. Setting `source_text` unlocks the
digit-level source-fidelity layer plus a sentence-level
grounded / fabricated / paraphrased decomposition.

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "frame_check",
    "arguments": {
      "document_text": "<the LLM's summary or analyst note>",
      "source_text": "<the SEC filing, press release, paper, ...>",
      "domain_hint": "finance"
    }
  }
}
```

### Load-bearing fields

- `analysis.verification.source_fidelity`: digit-level fidelity
  counts (`total_numbers`, `in_source`, `not_in_source`). A summary
  with numbers that don't appear in the source is structurally
  suspect regardless of the surrounding prose.
- `analysis.verification.grounding_decomposition`: per-sentence
  grounded / paraphrased / fabricated counts (sentence-level
  decomposition Layer 11).
- The two layers carry their own scope guidance: the digit-fidelity
  layer is load-bearing on number-dense sources (financial filings,
  macroeconomic releases) and the sentence-decomposition layer is
  load-bearing on prose-dense sources.

For free-text claim verification against external authorities (no
`source_text` available), Framecheck additionally cross-checks
numeric claims against SEC EDGAR, FRED, World Bank, Alpha Vantage,
and Wolfram Alpha when the claim's subject classifies to a
matching entity type and the provider has coverage. Those checks
run automatically when applicable; no extra parameter required.

### Honest limits

Provider coverage is bounded. Claim verification fires only when:
the subject classifies to a matching entity type
(COMPANY to SEC EDGAR; COUNTRY to World Bank; CRYPTO_ASSET to
CoinGecko); the claim type matches the provider's data shape;
the provider returned a value within the comparison tolerance.
Claims outside coverage are silently skipped, not reported as
"unverifiable"; the distinction matters when reasoning about
absence.

API key configuration enables higher-rate-limit access on FRED,
Alpha Vantage, and Wolfram. Without keys, those providers fall
through to public-rate-limited endpoints; rate-exhausted requests
look like absence of the underlying datum.

---

## Recipe 4: Compare two LLMs on the same prompt

### Use case

You have two LLM responses to the same prompt (different models,
different prompts to the same model, different sampling seeds).
You want to see how their structural framing differs. The
[`four-llms-on-bitcoin-retirement-2026.md`](../data/worked_examples/four-llms-on-bitcoin-retirement-2026.md)
worked example is this recipe applied to four frontier models.

### MCP request

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "frame_compare",
    "arguments": {
      "document_a_text": "<LLM A's response>",
      "document_b_text": "<LLM B's response>",
      "document_a_label": "Claude",
      "document_b_label": "GPT-5"
    }
  }
}
```

### Load-bearing fields

- `analysis.comparison.coverage`: surfaces `shared_blind_spots`
  (perspectives both documents miss), `only_a_misses` and
  `only_b_misses` (perspectives one document covers and the other
  does not), and `addressed_count_delta`.
- `analysis.comparison.voice`, `.temporal`, `.epistemic`: per-
  dimension structural deltas between the two documents.
- `analysis.comparison.framing_differences`: a structured
  `cards` list with one entry per dimension that materially
  differs, plus `unique_omissions` naming what each document
  omitted that the other addressed. Suitable for surfacing in a
  user-facing reader.
- `analysis.documents`: per-document profiles keyed by label
  (`"Document A"` / `"Document B"` by default, or the values passed
  via `document_a_label` / `document_b_label`), so consumers that
  want to read what each side did before reading the diff have the
  underlying values.

### Honest limits

The comparison is structural, not semantic. Two responses that
disagree in framing may both be defensible readings; two that
agree in framing may both be missing the same structural gap. The
output identifies *where* they differ, not which is correct.

---

## Recipe 5: Add a custom Frame Vocabulary Standard entry

### Use case

You have noticed a structural framing pattern in your work that
the existing FVS catalog does not name. Drafting an entry, running
it against a corpus, and proposing it for the public catalog is the
mechanism the program uses to grow the catalog deliberately.

This recipe is the contributor flow, not an MCP call. It points at
the published mechanism.

### Steps

1. **Author the rule.** A new entry lives at
   `data/frame_library/FVS-NNN_<short_name>.md` and follows the
   format of the existing entries (front-matter with `fvs_id`,
   `name`, `dimension`, `class`, `status`; body sections for
   identification cues, worked examples, related entries). The
   `data/frame_library/INDEX.md` file documents the row format.
2. **Run the rule against a calibration corpus.** The validation
   harness at `validation/decision_readiness/` runs a candidate
   rule against the calibration set and reports per-document
   firing patterns.
3. **Submit a `[RFC]` issue per `GOVERNANCE.md`.** The governance
   file documents which decisions require an RFC. A new FVS entry
   is one of them.
4. **Pre-register a study.** Following the protocol shape at
   [`validation/wedge_behavior/PROTOCOL_v1.md`](../validation/wedge_behavior/PROTOCOL_v1.md),
   pre-register what the rule predicts and what would falsify it.
5. **Submit the PR.** Sign-off-by-DCO, link the RFC and the
   pre-registered study, run the full test suite plus
   `bash scripts/canon_audit.sh`.

### Load-bearing references

- [`CONTRIBUTING.md`](../CONTRIBUTING.md): the mechanical PR flow.
- [`GOVERNANCE.md`](../GOVERNANCE.md): which decisions require an
  RFC and the maintainer's authority on canon.
- [`docs/RATERS.md`](RATERS.md): the rater protocol. New entries
  enter the catalog after surviving rater rounds, not before.
- [`Clarethium/lodestone`](https://github.com/Clarethium/lodestone):
  the methodology canon. Pre-public candidate entries live there
  before promotion to the FVS catalog.

### Honest limits

The catalog is intentionally conservative. An entry that fires on
the contributor's worked examples but does not survive a rater
round does not enter the public catalog. The bar at v0.x is "F1 ≥
0.4 against expert labelers in a pre-registered validation"; below
that bar, entries surface as candidates in the methodology canon
rather than as advertised FVS detections.

---

## See also

- [`README.md`](../README.md): quickstart, what-it-does, approach,
  worked example.
- [`docs/MCP_SERVER.md`](MCP_SERVER.md): full MCP contract
  reference.
- [`docs/FRAME_DIVERGENCE_CONTRACT_v1.md`](FRAME_DIVERGENCE_CONTRACT_v1.md):
  the divergence-block interface contract.
- [`data/worked_examples/`](../data/worked_examples/): six published
  worked examples that apply these recipes to real documents.
- [`docs/VALIDATION_PROGRAM.md`](VALIDATION_PROGRAM.md): the
  observational and formal validation plans the catalog is being
  measured against.
