# Frame Check MCP Server

Exposes Frame Check's deterministic structural framing analysis as a Model
Context Protocol tool so agents (Claude Desktop, Cursor, any MCP-compatible
client) can invoke framing analysis directly instead of paraphrasing
documents as their own LLM reading.

## What makes this MCP server different

Most MCP tools return raw data. This one returns a structured epistemic
payload with three sections:

1. **`analysis`**: measurements including coverage per analytical category,
   voice classification, temporal orientation, epistemic basis, frame
   matches from the Frame Vocabulary Standard, extracted numeric claims,
   a synthesized portrait, and (when a source is provided) a verification
   block with Layer 4 source fidelity and Layer 11 grounding decomposition.
2. **`agent_guidance`**: what the tool can and cannot tell the agent,
   how to cite the output faithfully without paraphrasing it as the
   agent's own reading, and scope-regime guidance that tells the agent
   which layer to trust on number-dense sources.
3. **`provenance`**: methodology versions (app, measurement stack,
   library), license, citation string, cost ($0.00 always; no LLM is
   invoked), deterministic claim.

The agent_guidance and provenance blocks exist because an agent passing
Frame Check's output to a user without attribution would strip the
reproducibility that makes the measurement worth citing.

## Install in Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "frame-check": {
      "command": "python3",
      "args": ["/absolute/path/to/frame-check/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. Then ask: *"Can you frame-check this document?"*

## Install in Cursor or other MCP clients

Any MCP-compatible client that speaks the `stdio` transport works. Point
the client at `python3 /path/to/mcp_server.py` and the handshake runs.

## Offline sanity check

No MCP client required:

```bash
python3 mcp_server.py --test
```

Prints the full epistemic payload for a canned document, twice: once
without source material (structural-only) and once with source material
(structural + verification). Useful to verify the pipeline wiring.

## Install fingerprint

Before a session that depends on current-repo behavior, run:

```bash
python3 mcp_server.py --version
```

Emits a single-line fingerprint with `server_version`, `protocol`,
`git_sha` (plus `+dirty` flag if the working tree has uncommitted
changes), `frame_library_version`, `corpus_slugs`, `corpus_hash`,
`python`, and `script` (absolute path). Lets you confirm
the MCP install configured in Claude Desktop / Cursor is actually
running the expected code, not a stale checkout. The `corpus_hash`
is byte-identical to the hash suffix on
`validation/decision_readiness/results/{date}-{hash}/` run
directories, so a match against the most recent aggregate run
directory confirms the corpus the server sees is the corpus the
aggregate harness last ran against.

## Exercised contracts

The payload contract is pinned by `tests/test_mcp_server.py` (and,
for the canon-graph resource chain, by
`tests/test_frame_library_index.py` plus the canon-graph assertions
in `tests/test_decision_readiness.py`). Every change below counts as
a breaking change and requires a test update:

- Three top-level sections (`analysis`, `agent_guidance`, `provenance`)
- `analysis_cost_usd == 0.0` (no LLM in the deterministic layer)
- `agent_guidance.what_this_tool_tells_you` and `what_this_tool_does_not_tell_you` populated
- `agent_guidance.how_to_cite_faithfully` names Frame Check explicitly
- `frame_library_matches[*].status` in `{draft, canon, aspirational, retired}`
- `verification` block present iff `source_text` supplied
- `scope_regime_guidance` cites Layer 4 on saturated sources
- `frame_compare.agent_guidance` forbids ranking language
- Deterministic output (byte-identical minus `analysis_latency_ms`) for identical inputs
- Subprocess roundtrip works with no stderr leaking into stdout
- Validation corpus resources advertise one URI per entry with a
  readable `document.md`; per-pair URIs only advertise when the
  comparison artifact exists; `frame-check://aggregate/latest`
  resolves to the highest-mtime `aggregate.json` under
  `validation/decision_readiness/results/`
- Aggregate `cross_question_findings[*]` carry both `library_entries`
  and `corpus_entries` reference shapes (the canon-graph chain
  `aggregate -> corpus -> library`)
- Adversarial input boundaries (added 2026-04-22, limits bumped
  2026-04-24 for the 0.8.0 arc): `document_text` at exact
  `MAX_DOCUMENT_CHARS=1_000_000` accepted, over-limit rejected with
  an isError response naming the limit; `source_text` over-limit
  (`MAX_SOURCE_CHARS=2_000_000`) similarly rejected; wrong-type arguments
  (int, null, list, dict for string fields; out-of-range `prefer_contract_version`)
  handled as isError without raising; whitespace-only `document_text`
  rejected via the `.strip()` branch; embedded U+0000 NULL byte in
  `document_text` is transparent to the structural measurement layer
  (coverage counts and sentence tokenization identical to the
  clean-document baseline); unicode edge cases (emoji, bidi markers,
  zero-width chars, mixed scripts) produce valid three-section
  payloads with a populated coverage block; rapid-fire sequential
  stdio (50 requests in one session) maintains determinism and id
  routing without state drift (determinism normalization strips
  `analysis_latency_ms` AND `analysis_timestamp_utc`, matching
  `test_payload_is_deterministic`). The adversarial tests use the
  `_assert_no_new_failures(baseline, test_name)` helper so `check()`
  failures surface as pytest assertions rather than silently
  accumulating in the module-level `_FAILURES` list.

Server version follows semver; minor bumps for additive optional
fields and resource additions, major for breaking schema changes.
The current version is exposed by the `initialize` handshake and
is also pinned in `mcp_server.py` as `SERVER_VERSION`.

## Initialize handshake

The `initialize` response carries the standard MCP fields plus a
top-level `instructions` field (per the MCP protocol):

- `protocolVersion`: the supported MCP protocol version.
- `capabilities`: tools, resources, and prompts capabilities all advertised.
- `serverInfo`: `name` ("frame-check") and `version` (matches `SERVER_VERSION`).
- `instructions`: server-orientation prose for the agent. Names the use case (when to use Frame Check), the default invocation shape (`frame_check(document_text=<text>)` works zero-arg), and the four-prompt workflow surface (`frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`). MCP clients whose UI surfaces the InitializeResult can show the user a one-line answer to "what is this server"; agents reading the field get cross-tool orientation that the per-tool descriptions cannot carry.

## Release arc

This section summarizes the canonical commitments so MCP-facing readers can orient on the current release posture. The repository tracks the full release plan and any revisions.

**Current state (live on PyPI).** `SERVER_VERSION` in
`mcp_server.py` matches the released wheel reported on the MCP
`initialize` handshake; the latest published wheel is on PyPI at
[pypi.org/project/frame-check-mcp](https://pypi.org/project/frame-check-mcp/).
`frame_check` + `frame_compare`, four sovereignty prompts,
divergence block on by default (`include_divergence=true`; an
explicit `false` returns the pre-divergence response shape), FVS
catalog pinned to library_v3 per `FRAME_DIVERGENCE_CONTRACT_v1`
c1.0 contract stability. The wheel runs the deterministic V1
substrate detection (regex-based, zero LLM cost per query); V4.2
LLM-judge is evaluation-only and not invoked server-side. The MCP
surface exposes V4.2 via `agent_guidance.how_to_render_divergence`
so the caller's agent runs V4.2 judgment with its own LLM if the
caller chooses. Zero Frame Check LLM cost per MCP call; vendor
independence by construction (the caller picks the model).

**Stable release: `1.0.0`.** API freeze to the v2 construct-carrying shape documented in this file. Breaking change from v1; the canonical first stable release that papers cite.

**Collapsed release.** An earlier plan for a `0.7.1` V1-only
name-reservation release on PyPI was retired 2026-04-23 in favor of
V4.2-first launch discipline. Name-squat risk on
`frame-check-mcp` was accepted as tail-risk and did not
materialize before the 0.8.0 lift on 2026-04-27.

## Tool surface

Two tools.

### `frame_check`: single-document analysis

**Agent-facing parameters** (advertised in `tools/list` schema; the agent decides whether to pass each):

| Parameter | Required | Type | Meaning |
|---|---|---|---|
| `document_text` | yes | string (max 1,000,000 chars) | The document to analyze. English. Markdown accepted. |
| `source_text` | no | string (max 2,000,000 chars) | Pass when the user has the source material the document was supposed to ground in. Unlocks Layer 4 source fidelity (digit-level match) and Layer 11 grounding decomposition with scope-regime classification. |
| `include_divergence` | no | boolean (default `true`) | Frame divergence output per FRAME_DIVERGENCE_CONTRACT_v1 Part 2. **Default `true`; the agent does not need to pass this.** When `true` (default), the response carries a top-level `divergence` block plus two `agent_guidance` additions (`how_to_render_divergence`, `absence_is_not_prescription`). Set explicitly to `false` only for the legacy 0.7.x-shape response with no divergence block. See "Divergence block" below. |
| `divergence_rendering` | no | string (enum) | One of: `list` (default), `completeness_check`, `teaching_questions`, `narrative`. Affects `AbsentFrameRecord` decoration only; the caller's agent model performs the rendering. |
| `user_context` | no | string (max 2000 chars) | Pass when the user has stated their situation, role, or decision context in plain prose (e.g., "I'm a startup founder making a hire decision in healthcare AI"). When provided, `agent_guidance.how_to_render_divergence` is extended to instruct the caller's model to filter divergence relevance for this context. The MCP does NOT echo the value into the response (privacy posture: caller-side context never round-trips through the server). Discipline: relevance filtering, never prescription. |
| `user_goal` | no | string (enum) | Pass when the user has named a goal: `decide`, `brainstorm`, `persuade`, `learn`, `audit`. When provided, `absent_frames` carry a `goal_relevance` dict and the absent_frames sort promotes goal-relevant entries within their signal_strength tier. Omit when the user has not named a goal; behavior matches `audit`. |
| `compose_budget` | no | string (enum) | One of: `minimal`, `standard`, `full` (default). Bounds the substrate's output volume for tight working-memory budgets. `minimal` and `standard` compress `agent_guidance` to load-bearing prescriptions; `suggested_next_actions` survives at all tiers. |
| `include_frame_opportunities` | no | boolean (default `false`) | Opt-in for up to 3 LLM-augmented document-specific questions. Cost bounded at ~0.001 USD per invocation (Gemini Flash). Falls back to empty list with `available=false` if `GEMINI_API_KEY` is not set. |

**Developer-only parameters** (accepted by the dispatch layer for backward compatibility but NOT advertised in the agent-facing `tools/list` schema; an agent should not be making these decisions per call):

| Parameter | Type | Meaning |
|---|---|---|
| `prefer_contract_version` | integer (1 or 2) | Coverage contract version the client prefers. `1` (default): emit both v1 `coverage` and v2 `coverage_v2` (Phase 2 compatibility window; v1 deprecated 2026-04-21). `2`: emit only `coverage_v2` and omit v1. See "Coverage v1 and v2 shapes" below. |
| `domain_hint` | string (enum) | Hint about the document's domain. Currently echoes to `envelope.domain_inferred`; field-level filtering is deferred to a future contract minor version. Removed from the agent-facing schema 0.8.3 because the current implementation has no behavioral effect. |
| `catalog_version_pin` | string | Pins the FVS catalog used for absent-frame set difference. Currently only `library_v3` is supported (contract c1.0); unsupported pins are coerced with a limitation note in `envelope.limitations`. Removed from the agent-facing schema 0.8.3 because the agent should not be choosing catalog versions per call. |

When `source_text` is absent, you get structural framing analysis only.
When present, you also get Layer 4 source fidelity and Layer 11
grounding decomposition. When `include_divergence=true`, the response
also carries the `divergence` block described in the "Divergence block"
section below.

#### `verification.source_fidelity` (when `source_text` is supplied)

```jsonc
{
  "verification": {
    "source_fidelity": {
      "total_numbers": 25,
      "in_source": 23,
      "not_in_source": 2,
      "unsourced_rate": 0.08,
      "unsourced_items": [
        {"value": "100000000", "type": "integer",
         "context": "NVIDIA RTX now serves 100 million gamers and creators..."},
        {"value": "198", "type": "integer",
         "context": "to shareholders of record on March 6. (198 words)"}
      ],
      "note": "..."
    }
  }
}
```

`unsourced_items` (added v1.0.9) is the per-claim diagnostic for the
`not_in_source` count. Each item carries the literal value, its
extracted type (integer/decimal/percentage/currency), and the
claim-sentence context the value appeared in. Use this to surface
WHICH numbers in the document do not literal-match the source —
adopters can render the items to the user as "X numbers in the
document do not appear in the source: [item.value], [item.value], ..."
or pass them downstream to a verification subroutine.

What the literal-substring match catches and misses:

- **Catches**: same digit string in different prose contexts
  (e.g., `$22.1B` ≡ `$22.1 billion` because "22.1" matches);
  percentage variants (`94%` ≡ `94 percent`); currency variants
  (`$X` ≡ `X dollars`).
- **Misses (false negatives)**: same number expressed in
  materially different formats — `$22.1 billion` (digit substring
  "22.1") will NOT match `$22,100,000,000` (digit substring
  "22100000000"). Same for rounded vs. precise (`$22.1B` vs.
  `$22,109,000,000`). Adopters who need format-tolerant matching
  should layer their own normalization on top.
- **Catches (avoids false positives)**: a value like `$22` in the
  document does NOT spuriously match `2022` in source; the matcher
  scopes by token boundaries, not raw substring.

What the field reports vs. what it does not: this is digit-presence
in source, not numeric correctness. A number flagged `not_in_source`
may be derived, rounded, fabricated, or pulled from elsewhere; the
tool surfaces the deviation, not its cause.

### `frame_compare`: two-document structural diff

| Parameter | Required | Type | Meaning |
|---|---|---|---|
| `document_a_text` | yes | string (max 1,000,000 chars) | First document. |
| `document_b_text` | yes | string (max 1,000,000 chars) | Second document. Should cover the same subject. |
| `document_a_label` | no | string (max 60 chars) | Short label for document A. Defaults to `Document A`. |
| `document_b_label` | no | string (max 60 chars) | Short label for document B. Defaults to `Document B`. |

Returns per-document summaries plus the cross-document comparison:
shared blind spots, unique coverage gaps, voice / temporal / epistemic
deltas, and a structured framing-differences narrative with per-dimension
reader implications. The agent_guidance block explicitly tells the
caller not to treat the comparison as a ranking; Frame Check names
what differs, not which is better.

## Web JSON parity (programmatic alternative)

Both tools have HTTP/JSON equivalents on the hosted web service at
`frame.clarethium.com`. A programmatic consumer that has chosen
HTTP over MCP can reach the same deterministic substrate via:

- `frame_check`  ↔  `POST /api/profile` (returns analysis-only JSON
  matching the MCP `analysis.*` shape; pinned by
  `test_web_mcp_parity::test_frame_library_matches_parity` and
  `::test_voice_classification_parity` and four other parametrized
  parity tests over the calibration corpus)
- `frame_compare`  ↔  `GET /api/compare-stream` (Server-Sent Events;
  `model_analyzed` event payload's `frame_library_matches[]`
  matches `frame_compare`'s `analysis.documents.<label>.
  frame_library_matches[]`; `comparison.framing_differences` matches
  `frame_compare`'s `analysis.comparison.framing_differences`
  byte-for-byte; pinned by
  `test_web_mcp_parity::test_compare_stream_frame_library_matches_parity`
  and `::test_compare_stream_framing_differences_parity`)

Per-match shape on both surfaces shares 8 fields (`fvs_id`, `name`,
`signal`, `question`, `definition`, `url`, `v4_2_verdict`,
`pattern_kind`); the schema-subset invariant test
(`test_frame_library_matches_schema_subset_profile` /
`_compare_stream`) catches drift at PR time so a future MCP-side
field addition that does not propagate to web fails CI immediately.

**Intentional asymmetries** (not bugs, documented in
NEXT_STEPS.md "Per-match field allowlist" subsection):

- MCP-only fields per match: `library_url` (named differently from
  web's `url`; points at the public-repo markdown source),
  `library_resource_uri` (`frame-check://` URI scheme is MCP-protocol-
  only), `library_entry_version`, `teaching_question` (named
  differently from web's `question`), `status`, `adjacent_frames`,
  `affects_dimensions`, `claim_level`. All encode resource URIs,
  canon-graph machinery, or per-level construct treatments that
  would be construct-misleading on web.

- MCP-only top-level analyzers: `genre_classifier`, `frame_deepening`
  (temporal_scope / stakeholder_map / falsification_conditions),
  `absence_clusters`, `frame_opportunities` (opt-in LLM-augmented).
  Held back from web pending per-classifier expert validation per
  NEXT_STEPS.md "Substrate-side composition: web exposure".

- MCP-only knobs: `compose_budget`, `divergence_rendering`,
  `domain_hint`. Agent-shaped affordances with no web parallel.

### `/api/profile` always-render contract (web-only)

The web JSON surface adds two top-level fields with no MCP parallel
because the MCP `frame_check` tool runs substrate-only and does not
invoke Source Network:

- `sn_status` (enum, always present): one of
  - `"complete"` - every claim was processed by Source Network
  - `"partial"` - SN per-claim budget (`SN_BUDGET_SECONDS`, default 25s)
    exhausted before all claims processed; some claims carry
    `verdict: "unverifiable"` with `detail` containing "budget"
  - `"unavailable"` - SN raised an exception or exceeded the 35s outer
    timeout; `source_verification` is null and no per-claim results
    are returned
  - `"skipped"` - the document carried no claims for SN to verify
- `sn_status_reason` (string or null): human-readable cause when
  `sn_status` is `"partial"` or `"unavailable"`, naming the specific
  limitation (provider rate-limit, exception class, outer-budget
  exhaustion). Null on `"complete"` or `"skipped"`.

Consumers can branch on `sn_status` without parsing
`source_verification` shape; the always-render contract guarantees
substrate output is present at HTTP 200 even when SN failed
(behavioral contract pinned by
`test_always_render_contract_*` in `tests/test_pages.py`).

The pipeline runs in three layers (named in source comments at
`app.py` substrate / SN / portrait blocks):

- **Layer A.1 substrate** - regex / parsing only (measure, claim
  analysis, coverage, framing detectors). CPU-bound, mandatory, 15s
  budget. Substrate failure returns HTTP 500 with structured `{"error"}`
  JSON (NOT a generic HTML 500); consumers can branch on the type-
  named error string.
- **Layer A.2 Source Network** - network-bound, best-effort. 35s outer
  timeout is a safety net; the real graceful path is SN's internal
  `SN_BUDGET_SECONDS=25s` budget which synthesizes
  `verdict: "unverifiable"` placeholder results when exhausted. SN
  failures NEVER throw to the user; `sn_status` carries the signal.
- **Layer A.3 portrait + headline + fuzzy** - inline CPU work,
  always runs (consumes possibly-empty `sn_results`).

The same `sn_status` enum surfaces on the compare SSE stream:

- `/api/compare-stream`'s `model_analyzed` event payload carries
  `sn_status` and `sn_status_reason` per model. The two values can
  differ across the two models (one model's claims may exhaust SN
  budget while the other's complete). Frontend renders an
  `.sn-status-banner` per model card scoped to the affected document.
  Pinned by `test_compare_stream_sn_failure_renders_unavailable_status_per_model`
  and the field-presence assertion in `test_compare_stream_documents_mode`.

A consumer that needs the rich agent-guidance / divergence /
absence-clusters surface should pick MCP. A consumer that only
needs the substrate-level structural signals (FVS firings,
voice / coverage / temporal / epistemic) can pick either.

## Resource surface

Resources are the noun side of the protocol. They expose the artifacts
that justify or contextualize a tool call: the frame library entries
the tools cite, the methodology spec the measurements implement, the
calibration runs that pin verifier reliability, and the validation
corpus the experimental decision-readiness profile is measured on.
URIs are stable so an agent that cites a finding can hand the user
the exact resource that justifies it.

### Frame library

- `frame-check://library` - library index (status + adjacency).
- `frame-check://library/FVS-001` through `FVS-020` - each entry as
  markdown source.

### Methodology, transmissions, worked examples

- `frame-check://methodology` - the methodology spec.
- `frame-check://transmissions` and `frame-check://transmissions/{slug}` -
  curated research pieces (served locally because the public blog's
  edge layer blocks automated fetches).
- `frame-check://worked-examples` and `frame-check://worked-examples/{slug}` -
  applied analyses of specific public documents.

### Frame Divergence spec

The authored canonical reference for the frame divergence category
contract is `docs/FRAME_DIVERGENCE_CONTRACT_v1.md` (Part 2, c1.0).
Consumers binding against the interface contract cite this resource.

- `frame-check://spec/frame-divergence/v1` - generated spec index
  listing available parts (reflects current disk state at read time).
- `frame-check://spec/frame-divergence/v1/part-2` - contract c1.0
  (FRAME_DIVERGENCE_CONTRACT_v1.md). Specifies operations, inputs,
  outputs, faithfulness guarantees, the MCP-vs-web tier split,
  adoption-driven versioning commitments.
- Parts 3 (V4.2 integration) and 4 (self-red-team and competitive map)
  surface here by the same pattern when authored.

The dispatcher rejects non-integer part suffixes (traversal-safe) and
returns a structured error for integer suffixes that do not correspond
to a file on disk.

### Calibration evidence

- `frame-check://calibration/reliability_tiers` - per-provider F1,
  precision, recall, and tier from the most comprehensive calibration
  run on this deploy.
- `frame-check://calibration/runs/{run_id}/{report,verdicts,tiers}` -
  narrative report, per-claim verdicts, and per-provider tier snapshot
  for a specific calibration run.

### Validation corpus and decision-readiness profile

The validation corpus is the document set on which the
decision-readiness profile is measured. Profile output is currently labelled experimental and is **not** surfaced in the live UI; the gate lifts after the Phase 2 rater study (see RATERS.md in the repository).

- `frame-check://corpus/{slug}` - the entry's source document
  (markdown). Slug is alphanumeric + hyphens; traversal-safe.
- `frame-check://corpus/{slug}/profile` - the entry's
  decision-readiness profile (JSON). Five dimensions: coverage,
  calibration, evidence, robustness, counterfactual. Each dimension's
  finding lists the library entries that fired
  (`fired_library_entries`), giving the citation chain
  `profile -> library`.
- `frame-check://corpus/{slug}/peer/{partner_slug}` - per-pair side-by-side
  numerical comparison (when the same prompt was answered by multiple
  sources).
- `frame-check://corpus/{slug}/diff/{partner_slug}` - per-pair annotated
  framing-level interpretation.
- `frame-check://aggregate/latest` - the most recent cross-question
  aggregate (JSON). Each finding lists `library_entries` and
  `corpus_entries`, giving the citation chain
  `aggregate -> corpus -> library`. Selection is by mtime so the
  newest aggregate wins regardless of corpus state hash ordering.

Resources gracefully degrade: clean checkouts without the validation
tree advertise no corpus or aggregate resources rather than failing.

## Divergence block (default `include_divergence=true`)

Per FRAME_DIVERGENCE_CONTRACT_v1 Part 2 c1.0, `frame_check` emits a
top-level `divergence` block alongside `analysis` / `agent_guidance`
/ `provenance`. The block fires by default; callers who want the
pre-divergence response shape set `include_divergence=false`
explicitly. Rec II enhance-existing: no separate tool; divergence is
an output-shape enhancement of `frame_check`. The MCP surface does
not invoke any LLM for divergence; V4.2 judgment is delegated to the
caller's agent model per the two added `agent_guidance` keys.

Each absent_frame record carries a `signal_strength` tier (`high` /
`medium` / `low`) computed from the canon-graph (decision-readiness
dimensions the frame is canon for) plus the document's coverage-
weakness signal. Records are sorted high-first so the caller's model
can take the top-N entries and get the highest-leverage absences
without further filtering. The envelope carries a `divergence_summary`
prose field naming the semantic intent and a `tier_counts` dict for
quick triage.

### Block shape

```json
"divergence": {
    "absent_frames": [
        {
            "frame_id": "FVS-011",
            "frame_version": "v1",
            "frame_title": "Stakeholder Frame",
            "stability": "stable",
            "signal_strength": "high",
            "affects_dimensions": ["coverage", "counterfactual"],
            "citation_uri": "frame-check://library/FVS-011",
            "absence_basis": "Caller's model must confirm no FVS-011 identification cues fired in the supplied document. V1 rule-based detection on this document did not match FVS-011. See frame-check://library/FVS-011 for identification cues and counter-examples that inform the judgment.",
            "domain_relevance_rationale": "FVS-011 is canon for 2 decision-readiness dimensions (coverage, counterfactual); the document is weak on coverage (3 of 5 categories not detected). High reader-relevance signal."
        }
    ],
    "absence_clusters": [
        {
            "dimension": "counterfactual",
            "member_frames": ["FVS-001", "FVS-007", "FVS-009", "FVS-014"],
            "member_count": 4,
            "canon_size": 5,
            "canon_coverage_fraction": 0.8,
            "signal_strength": "high",
            "reading": "Load-bearing absences cluster on the counterfactual dimension: the document does not name conditions under which its conclusion would be wrong, alternative scenarios where the pattern shifts, or risks that would invalidate the framing. 4 of 5 counterfactual-canon frames are absent in this document."
        }
    ],
    "envelope": {
        "spec_version": "FRAME_DIVERGENCE_v1_c1.0",
        "catalog_version": "library_v3",
        "surface": "mcp",
        "divergence_summary": "Catalog-driven perspective absence with faithfulness constraints. 17 of 19 catalog frames not detected by V1 rule-based detection: 4 high-signal (5 medium, 8 low). Records are sorted by signal_strength so callers can take the first N and get the highest-leverage absences. The reader's model composes the perspective-widening interpretation per agent_guidance.how_to_render_divergence; this block is the substrate, not the verdict.",
        "v4_2_execution": {
            "location": "caller_side",
            "tier": "caller_model",
            "note": "V4.2 judge step delegated to caller's agent model per Rec I. Frame Check's MCP server does not invoke an external LLM."
        },
        "v4_2_engine_status": "beta",
        "v4_2_engine_status_reference": "Engine status reflects production-readiness of the V4.2 detection layer; the value is informational for callers that gate on stability.",
        "domain_inferred": "unfiltered",
        "provisional_count": 0,
        "tier_counts": {"high": 4, "medium": 5, "low": 8},
        "faithfulness_note": "Absent frames are named from the FVS catalog as not detected in the supplied document. Domain relevance is the tool's best judgment. Whether any absent frame is useful is the thinker's call. This is not a list of frames that should have been used.",
        "limitations": [
            "V4.2 caller-side composition: absence_basis fields are scaffolding for the caller's agent model. Caller's model determines the final absence verdict per FRAME_DIVERGENCE_CONTRACT_v1 §7.1."
        ]
    }
}
```

### Absence clusters

`divergence.absence_clusters` is the substrate's first composition layer over the divergence set. Where the agent previously had to discover dimension-level themes by reading across the `absent_frames` list ("these four absent frames cluster on the counterfactual dimension"), the substrate now surfaces the cluster directly with a dimension-specific, evidence-anchored reading.

A cluster fires when all four conditions hold:

1. At least 2 absent frames share a canonical decision-readiness dimension (`_CLUSTER_MIN_ABSENT`).
2. The absent set covers at least 50 percent of that dimension's canon membership (`_CLUSTER_MIN_CANON_FRACTION`).
3. The document is at least 100 words (`_CLUSTER_MIN_DOCUMENT_WORDS`); below this floor, `absent_frames` is dominated by catalog size minus a small number of matches and clusters would surface canon-graph structure rather than document signal.
4. At least one FVS frame matched AND at least one claim was detected; zero matches means `absent_frames` IS the catalog (off-methodology text), zero claims means the document carries no analytical content (even when an FVS detector fired vacuously). Both conditions ensure the substrate composes only when it has document signal.

The two-condition threshold is calibration-honest. An absolute threshold (e.g., "3 absent frames") would silently bias the substrate to surface only multi-canon dimensions (coverage with 8 canon members, counterfactual with 5) and never small-canon dimensions (calibration with 2 canon members; both absent is 100 percent of canon and a strong signal that an absolute threshold misses). Single-canon dimensions (`evidence`, `robustness` in the current canon graph, with FVS-016 as the only member) cannot reach 2 absent and so cannot cluster; that is honest, since "cluster" is meaningless for a one-element canon.

Each cluster carries:

- `dimension`: the canonical dimension name (one of the five in `DIMENSION_LIBRARY_ENTRIES`)
- `member_frames`: sorted list of FVS IDs that are absent and canon for this dimension
- `member_count`: integer count of member frames
- `canon_size`: total canon members for this dimension
- `canon_coverage_fraction`: `member_count / canon_size`, rounded to two decimals
- `signal_strength`: highest member-frame tier (`high` > `medium` > `low`); the cluster is at least as strong as its strongest member
- `reading`: a curated, dimension-specific prose reading composed by Frame Check, anchored in evidence (mentions `member_count` and `canon_size`)

Clusters are sorted by `signal_strength` (high first), then `canon_coverage_fraction` descending (most under-attended first), then dimension alphabetical for stable tiebreaking. The strongest-cluster-first ordering means a caller's agent that takes the first cluster gets the load-bearing dimension theme without further filtering. When no dimension meets the firing threshold, `absence_clusters` is an empty list and the agent falls back to per-frame composition over `absent_frames`.

The substrate stays deterministic. The cluster builder operates only on canon-graph set membership and aggregation of per-frame `signal_strength`; it never touches document content semantics. The dimension readings are curated text per dimension; new dimensions added to `DIMENSION_LIBRARY_ENTRIES` must add a matching reading in `_DIMENSION_CLUSTER_READINGS` or receive a construct-honest placeholder. The cluster is the substrate's reading; the per-frame walk is the supporting evidence. The agent is instructed (via `agent_guidance.how_to_render_divergence` and the four sovereignty prompts) to lead with the strongest cluster's reading when present.

### Structural genre classification

Foundational primitive that per-genre absence ranking and pattern composition build on. The classifier emits a structural genre label with confidence and runner-up using the same shape as voice: bounded label set, deterministic features, margin-aware confidence reporting.

Bounded genre set. The classifier picks among six structural genres:

- **`recommendation`**: document positions itself to name a pick or suggest action ("my pick", "I recommend", "the best option")
- **`analysis`**: document investigates without committing to a recommendation (high hedge ratio, analytical voice, alternative-surveying without an explicit pick)
- **`narrative`**: document tells a story or sequence of events (temporal-anchor density, named past dates, event chains)
- **`advocacy`**: document argues for a position with persuasive force (assertive markers like "must" / "essential" / "obviously", low hedge ratio, advisory or promotional voice without explicit pick markers)
- **`exploration`**: document surveys options without committing (alternative-surveying markers and hedging without explicit recommendation markers)
- **`instruction`**: document explains how to do something procedurally (numbered steps, "first" / "next" / procedural lists)

Output shape (mirrors voice's classification-confidence treatment):

```json
"genre": {
  "classification": "recommendation",
  "confidence": "high",
  "runner_up": "advocacy",
  "runner_up_margin": 0.42,
  "score_distribution": {
    "recommendation": 0.62,
    "analysis": 0.04,
    "narrative": 0.08,
    "advocacy": 0.20,
    "exploration": 0.06,
    "instruction": 0.0
  },
  "available_classes": ["recommendation", "analysis", "narrative", "advocacy", "exploration", "instruction"],
  "construct": "Document positions itself to name a pick or suggest an action. Detected via recommendation-marker density (\"my pick\", \"I recommend\", \"the best option\", etc.) plus advisory voice."
}
```

Construct honesty. The classifier composes existing analyzer outputs (voice classification, claim hedge ratio) with text-feature regexes (recommendation markers, instruction markers, alternative-surveying markers, advocacy markers, narrative markers) into per-genre scores. Top score is the classification; runner-up margin drives the confidence label (`high` when margin reaches the borderline threshold; `borderline` when below). When no feature fires (very short text, off-methodology structure, regexes did not match), the classifier abstains: `classification` is `null` and `confidence` is `low`. The construct field carries dimension-specific prose describing how the classification was composed.

Genre is a structural reading of how the document positions its content; not a verdict. Agents surfacing genre to the user should name it as Frame Check's reading and surface the runner-up when confidence is borderline (the cascade hesitated between two positionings).

### Genre-relative absence ranking

Built on the genre classifier. When a document classifies into a structural genre, absences that are load-bearing for that genre's reasoning are promoted within their `signal_strength` tier. The substrate carries a curated per-genre map: for each genre, an ordered list of FVS IDs with one-sentence reasons naming the structural relevance.

The ranking is reading-form. The reason for each genre-relevant absence describes what the framing does not do, not what the document is. The agent surfacing the absence cites the reason as the structural basis for the entry's priority.

Per-genre load-bearing maps live in `genre_classifier._GENRE_LOAD_BEARING_ABSENCES`. Each genre has at least three entries; recommendation has four. Adding a new genre to the classifier requires adding a matching map entry (paired with the scoring function and construct text from the classifier itself).

`absent_frames` records carry a new optional field:

```json
"genre_relevance": {
  "relevant_for_genre": true,
  "priority": 1,
  "reason": "Recommendations without falsification conditions cannot be stress-tested by the reader."
}
```

`null` when the document has no classified genre or the frame is not in that genre's load-bearing map.

Sort order on `absent_frames` is now: `signal_strength` tier first (`high` before `medium` before `low`), then `genre_relevance.priority` ascending (1 = most load-bearing for the document's genre; entries without genre_relevance sort with priority 999), then `frame_id` alphabetical for stability. Catalog/coverage tier and genre relevance compose: a high-tier non-relevant absence still outranks a medium-tier relevant one.

### Named structural patterns

Where clusters surface dimension-level themes over absences alone, named patterns surface RECOGNIZED structural shapes that combine present and absent frames into a single named composition with curated reading and corpus prevalence as empirical anchoring.

The substrate carries a curated pattern catalog in `frame_patterns._PATTERNS`. Each pattern carries:

- `id`: stable kebab-case identifier (e.g., `recommendation-without-falsification`)
- `name`: human-readable name
- `trigger`: which frames must be present, which absent, and (optionally) which document genre is required for the pattern to surface
- `reading`: curated reading-form prose composing the pattern
- `load_bearing_dimensions`: canon-graph dimensions the pattern speaks to

The current catalog has eight patterns:

- **`recommendation-without-falsification`**: genre is `recommendation`, FVS-007 fires (failure-framing absence detected), and either FVS-009 Risk Frame or FVS-014 Temporal Anchoring is not actively detected. Recommendations without falsification conditions cannot be stress-tested.
- **`growth-without-risk`**: FVS-008 Growth Frame fires while FVS-009 Risk Frame is not actively detected. The document foregrounds upside while leaving downside structurally invisible.
- **`analysis-without-grounding`**: genre is `analysis`, FVS-016 Authority by Citation is not actively detected, and either FVS-012 Uncertainty Frame or FVS-017 False Balance is absent. The analysis reads more decisive than its evidence supports.
- **`narrative-without-stakeholders`**: genre is `narrative` and `stakeholder_role_count == 0` (frame_deepening signal must be present and exactly zero). Story without people; events without perspective. The reader sees events but not the people they affect.
- **`instruction-without-failure-modes`**: genre is `instruction`, FVS-009 Risk Frame absent, and zero explicit falsification statements. Procedural document presents steps as if they cannot fail; troubleshooting scaffold is missing.
- **`forward-projection-without-anchoring`**: genre-agnostic. `projection_phrase_count >= 2` (substantial forward-looking content) and zero explicit falsification statements. Predictions without validity windows or sensitivity-to-assumptions.
- **`cited-but-promotional`**: FVS-016 Authority by Citation fires AND voice classification equals `promotional`. Citations carried in promotional register; structural shape that can mask cherry-picking.
- **`advocacy-without-counter-perspective`**: genre is `advocacy`, FVS-017 False Balance is absent, and either FVS-009 or FVS-011 Stakeholder Frame is absent. The argument is structurally one-sided.

When a pattern's trigger matches the document signal, it surfaces in `divergence.frame_patterns` as:

```json
{
  "id": "recommendation-without-falsification",
  "name": "Recommendation without falsification",
  "reading": "Document recommends a pick while Frame Check's failure-framing absence detector fires (FVS-007), and either FVS-009 Risk Frame or FVS-014 Temporal Anchoring is not actively detected. Recommendations without falsification conditions cannot be stress-tested; the pick stands or falls without the structure that would let a reader see when it stops being right.",
  "load_bearing_dimensions": ["counterfactual"],
  "trigger_genre": "recommendation",
  "supporting_evidence": {
    "frames_present": ["FVS-007"],
    "frames_absent_optional_match": ["FVS-009", "FVS-014"]
  },
  "corpus_context": {
    "prevalence": "matches the frame-shape trigger of this pattern in 4 of 10 corpus documents",
    "matches_count": 4,
    "total_corpus": 10,
    "match_rate": 0.4,
    "small_n_caveat": "Frame-shape match only; the corpus does not yet carry per-document genre classifications, so the count is the structural-shape prevalence regardless of corpus-document genre."
  }
}
```

Construct honesty. The pattern reading is curated text composed by Frame Check; agents cite it as Frame Check's reading. The `supporting_evidence` field carries which frames in the trigger lists actually fired or absented in this document, so the agent can cite the specific frames inline. Corpus prevalence is computed as a frame-shape count; the genre constraint applies to the current document only (the corpus does not yet carry per-document genre classifications), and the small_n_caveat names this honestly.

When no pattern matches, `frame_patterns` is an empty list and the agent falls back to per-cluster, per-frame, and per-absence composition.

### Per-frame deepening (Items 8 / 9 / 10)

Three deterministic regex-based detections that give the agent specific document-content evidence beyond the FVS firing/absence signals. Each deepens one load-bearing FVS area: temporal anchoring (FVS-014), stakeholder mapping (FVS-011), and falsification conditions (FVS-007 / FVS-009).

The substrate stays deterministic. Each detection is regex-based or structural; no LLM is invoked. Each emits a construct-honest shape with explicit fields and (where meaningful) candidate sentence previews. Each detector returns `null` when the document is below the 100-word floor; the MCP response then omits the corresponding sub-field rather than carrying empty placeholders.

The deepening block surfaces under `analysis.frame_deepening`:

```json
"frame_deepening": {
  "temporal_scope": {
    "years_referenced": [2010, 2026, 2030],
    "year_count": 3,
    "near_now_years": [2026],
    "historical_years": [2010],
    "projection_years": [2030],
    "decade_references": [],
    "projection_phrase_count": 1,
    "retrospective_phrase_count": 0,
    "scope_reading": "Document anchors temporal scope across near-now years (2026) plus historical years (2010) plus forward-projection years (2030). The same conclusion at different time horizons may shift; the reader can ask what changes if the figures or events were shifted forward or backward by the anchoring window."
  },
  "stakeholder_map": {
    "roles_mentioned": ["investors", "regulators"],
    "role_count": 2,
    "per_role_mention_count": {"investors": 1, "regulators": 1},
    "total_stakeholder_mentions": 2,
    "scope_reading": "Document carries 2 stakeholder roles (investors, regulators) with 2 mentions total. Stakeholder roles NOT mentioned: customers, employees, competitors, communities, suppliers, management. The reader can ask which absent stakeholders' perspectives would change the framing."
  },
  "falsification_conditions": {
    "primary_match_count": 2,
    "candidate_match_count": 0,
    "extracted_conditions": [
      "The conclusion would be wrong if carbon credit prices crashed.",
      "The main risk is policy reversal under different administrations."
    ],
    "candidate_conditions": [],
    "scope_reading": "Document carries 2 explicit falsification statements (e.g., 'would be wrong if', 'fails when', 'the conclusion depends on'). The reader can interrogate the named conditions: are they precise enough to be tested? Do they cover the load-bearing assumptions of the document's claims?"
  }
}
```

**Item 8: temporal scope.** Extracts 4-digit years (1900-2099) from the document and classifies each by relation to current year: near-now (within 2 years), historical (more than 5 years before), or forward-projection (more than 2 years after). Also counts decade references ("the 2020s"), projection phrases ("by 2030", "next decade"), and retrospective phrases ("last year", "since 2015"). The scope reading composes a one-line prose anchoring of the temporal shape.

**Item 9: stakeholder map.** Detects which of eight role categories (regulators, investors, customers, employees, competitors, communities, suppliers, management) the document mentions, plus per-role mention counts. The scope reading names which roles are present and which are absent, so the agent can compose questions about whose perspective is missing.

**Item 10: falsification conditions.** Extracts explicit "would be wrong if" / "fails when" / "the conclusion depends on" statements as primary matches; extracts conditional markers ("if X were Y", "under the assumption that") as candidate matches that may carry falsification framing without being primary statements. Up to 5 primary previews and 3 candidate previews are surfaced. The scope reading distinguishes the three cases: primary present (the document carries falsification structure; reader can interrogate the named conditions), only candidates (the document hedges but does not name conditions explicitly; reader verifies whether candidates carry true falsification framing), or neither (no falsification structure; reader composes the questions themselves).

### Frame opportunities (opt-in LLM-augmented composition)

This layer is the only path that calls an LLM. It is opt-in only via `include_frame_opportunities=true` on the `frame_check` tool; the default behavior preserves the deterministic substrate composition with zero LLM cost per query.

Where the deterministic substrate gives the agent abstract teaching questions ("What would have to be true for this analysis to be wrong?"), this layer generates document-specific questions composed from the absent frame's perspective + the document's content + the user's goal. Example: instead of the abstract teaching question, the agent receives "Given the document's recommendation for Regenerative Agriculture is based on 'right now' opportunities and 2026 market sizes, how might this advice be reconsidered if 2026 data is historical by the time the decision matures?"

Strategic discipline:

- **Opt-in.** The deterministic substrate works without this layer being called. Absence of the `include_frame_opportunities` flag (or a `false` value) suppresses LLM invocation entirely. Absence of the `GEMINI_API_KEY` environment variable degrades gracefully (`available=false`, `opportunities=[]`).
- **Cost-tracked.** Each generated opportunity carries `model_provenance` with model name, cost in USD, input/output token counts, and `is_deterministic=false`. `divergence.frame_opportunities.total_cost_usd` is the spend for the invocation.
- **Bounded.** Maximum 3 opportunities per request (one Gemini Flash call each; total bounded at ~0.001 USD per `frame_check` invocation when enabled).
- **Construct-honest.** Generated questions are clearly flagged as LLM-composed. The general catalog teaching question remains alongside the generated one (`teaching_question_general` next to `generated_question`); the substrate-deterministic identity is preserved.

Surface shape (when enabled):

```json
"frame_opportunities": {
  "opportunities": [
    {
      "frame_id": "FVS-009",
      "frame_title": "Risk Frame",
      "citation_uri": "frame-check://library/FVS-009",
      "teaching_question_general": "Is the risk analysis proportionate, or is it overweighting worst-case scenarios?",
      "generated_question": "If the document identifies three lucrative business opportunities and recommends Regenerative Agriculture without discussing potential risks, does the absence of a proportionate risk analysis lead to an implied overweighting of best-case scenarios for decision-making?",
      "model_provenance": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "cost_usd": 0.000091,
        "input_tokens": 423,
        "output_tokens": 46,
        "is_deterministic": false
      }
    }
  ],
  "total_cost_usd": 0.000282,
  "available": true,
  "note": "Frame-opportunity composition is opt-in via include_frame_opportunities=true. The deterministic substrate (clusters, patterns, absences with goal and genre relevance) provides the same insights without LLM cost when this flag is omitted. See agent_guidance.frame_opportunities_discipline for the rules that apply when opportunities are surfaced."
}
```

When the flag is omitted or set to `false`, the same key is still present but carries `opportunities=[]`, `total_cost_usd=0.0`, and `available=null` (the substrate did not invoke the LLM). When the flag is `true` but the LLM is unavailable (no API key, library not installed), `available=false` with an `unavailable_reason` field; the deterministic substrate continues to provide clusters, patterns, and absent_frames.

The `agent_guidance.frame_opportunities_discipline` field carries the rules for surfacing opportunities to the user: name the LLM provenance, surface the cost, keep the general teaching question alongside the generated one, never present LLM content as Frame Check's measurement, and handle graceful degradation as a feature (the deterministic substrate still works) rather than an error.

### Genre-segmented corpus prevalence

The corpus aggregator classifies each corpus document by structural genre at lazy-load time and surfaces per-genre counts in `corpus_summary`. Per-frame `corpus_context` carries `fires_in_by_genre` (each genre with `fires_in_count`, `genre_total`, `rate`). Per-pattern `corpus_context` carries `genre_segmented_prevalence` when the pattern has a genre constraint, alongside the full-corpus prevalence for reference.

The motivation: a claim like "fires in 3 of 10 corpus documents" mixes recommendation, analysis, narrative, and press-release docs into a single denominator. The expert reading this asks "10 of what? Is the rate the same across genres?" Without segmentation, statistical claims are thin. With segmentation, the same data reads "fires in 1 of 5 recommendation-genre corpus documents (20%)"; the comparison is now like-vs-like, and small-N is honestly named.

The substrate stays deterministic. Genre classification at corpus load uses the same `genre_classifier.classify_genre` that runs on the document under analysis (with `claim_analysis.analyze_claims` and `framing.detect_voice` providing claim/voice context). When the classifier abstains on a corpus document, the document buckets under `_unclassified` so the agent can see how much of the corpus is unsegmentable.

`corpus_summary.per_genre_counts` example:

```json
"per_genre_counts": {
  "recommendation": 5,
  "narrative": 2,
  "advocacy": 1,
  "_unclassified": 2
}
```

Per-frame `fires_in_by_genre` example:

```json
"fires_in_by_genre": {
  "recommendation": {"fires_in_count": 1, "genre_total": 5, "rate": 0.2},
  "narrative": {"fires_in_count": 1, "genre_total": 2, "rate": 0.5},
  "advocacy": {"fires_in_count": 0, "genre_total": 1, "rate": 0.0},
  "_unclassified": {"fires_in_count": 1, "genre_total": 2, "rate": 0.5}
}
```

Per-pattern `corpus_context` with segmented prevalence:

```json
"corpus_context": {
  "prevalence": "matches the frame-shape trigger of this pattern in 4 of 10 corpus documents",
  "matches_count": 4,
  "total_corpus": 10,
  "match_rate": 0.4,
  "genre_segmented_prevalence": "matches in 1 of 5 corpus recommendation-genre documents",
  "matches_in_genre_count": 1,
  "genre_total": 5,
  "genre_match_rate": 0.2,
  "trigger_genre": "recommendation",
  "small_n_caveat": "The trigger genre is 'recommendation'; segmented prevalence (matches_in_genre_count of genre_total) is the like-vs-like comparison and the more meaningful denominator..."
}
```

Both the full-corpus and genre-segmented prevalence are surfaced. The agent should prefer the segmented denominator when interpreting the rate; the full-corpus number stays for reference (and for scaling: as the corpus grows, segmented Ns become statistically meaningful while the full-corpus N grows too). The `small_n_caveat` names that both numbers are still small-N today.

### Goal-aware divergence ranking

The user (or agent on behalf of the user) signals a goal: `decide`, `brainstorm`, `persuade`, `learn`, `audit`. The divergence ranking shifts accordingly: deciding emphasizes falsification, brainstorming emphasizes perspective diversity, persuading emphasizes counter-perspectives, learning emphasizes full taxonomy, auditing applies the catalog/coverage/genre logic without goal override.

The substrate stays deterministic. Per-goal maps are curated text in `user_goals._GOAL_LOAD_BEARING_FRAMES`; the relevance lookup is exact-match against canon FVS IDs; no LLM is invoked.

`absent_frames` records gain an optional `goal_relevance` field when the user has signalled a goal:

```json
"goal_relevance": {
  "relevant_for_goal": true,
  "priority": 1,
  "reason": "When the goal is to decide, failure-framing absence is the load-bearing structural gap: a document without falsification conditions cannot be stress-tested at decision time, and the decision rests on the document's framing rather than on tested grounds."
}
```

`null` when the user has set no goal, has set goal=`audit`, or the frame is not in that goal's load-bearing map.

The `absent_frames` sort now respects four ranking dimensions, in order:

1. `signal_strength` tier (catalog + coverage logic; objective document signal).
2. `goal_relevance.priority` (the user's stated intent; 1 = most load-bearing for the goal).
3. `genre_relevance.priority` (the document's structural shape).
4. `frame_id` alphabetical (stability tiebreak).

Goal precedes genre because the user's stated goal is a more direct signal than inferred document classification; signal precedes goal because empirical signal cannot be overridden by user preference. Records without a relevance entry sort with priority 999 so they fall after curated entries.

The `audit` goal is the default-equivalent posture: no goal-specific override is applied; the existing catalog/coverage/genre ranking stands. It is named explicitly so the agent can surface "auditing this document" as a distinct sovereignty posture from the other goals. When `user_goal` is omitted entirely, behavior matches `audit`.

### Corpus context (empirical anchoring)

Frame Check ships with a small validation corpus (10 documents today) under `validation/decision_readiness/corpus/` plus aggregate findings under `validation/decision_readiness/results/{date}-{hash}/aggregate.json`. The corpus carries empirical signal: per-frame firing rates, co-fire patterns, co-absence patterns, per-dimension peer-difference rates, and cross-question outlier findings. The substrate exposes this signal as `corpus_context` blocks attached to matched frames, absent frames, and absence clusters.

Small-N discipline. The corpus is small. Every prevalence statement carries the denominator (`fires in N of M corpus documents`) so the small-N is honest. Outcome data based on expert ratings is not yet available (current `cross_check.json` reports `n_ratings_discovered: 0`); the outcome-shaped signals surfaced are peer-pair-difference rates and cross-question outlier findings from validation runs, named as such in `envelope.corpus_summary.small_n_caveat`. When the corpus is unavailable (e.g., wheel without bundled corpus), every `corpus_context` field is `None` rather than a fabricated value.

Per-frame `corpus_context` (attached to each entry in `frame_library_matches` and `divergence.absent_frames`):

```json
"corpus_context": {
  "prevalence": "fires in 3 of 10 corpus documents",
  "fires_in_count": 3,
  "fires_in_total": 10,
  "typical_co_fires": [
    {"fvs_id": "FVS-007", "count": 3, "citation_uri": "frame-check://library/FVS-007"},
    {"fvs_id": "FVS-001", "count": 3, "citation_uri": "frame-check://library/FVS-001"}
  ],
  "typical_co_absences": [
    {"fvs_id": "FVS-010", "count": 7, "citation_uri": "frame-check://library/FVS-010"},
    {"fvs_id": "FVS-017", "count": 7, "citation_uri": "frame-check://library/FVS-017"}
  ],
  "corpus_entries_fired_uris": [
    "frame-check://corpus/four-llms-bitcoin-claude",
    "frame-check://corpus/four-llms-startup-grok"
  ]
}
```

Per-dimension `corpus_context` (attached to each entry in `divergence.absence_clusters`):

```json
"corpus_context": {
  "peer_pair_difference_rate": "differs across 10 of 12 peer pairs in the validation corpus",
  "peer_pair_difference_count": 10,
  "peer_pair_total": 12,
  "cross_question_outlier": {
    "llm": "claude",
    "outlier_count": 2,
    "comparable_count": 2
  },
  "canon_size": 5
}
```

Envelope-level `corpus_summary` (attached to `divergence.envelope`):

```json
"corpus_summary": {
  "n_documents": 10,
  "state_hash": "7a6e2f294c9e",
  "aggregate_computed_at_utc": "2026-04-25T15:10:04+00:00",
  "small_n_caveat": "Frame Check's validation corpus is small (N=10 documents). Prevalence and co-pattern statistics carry the denominator; treat any single-figure rate as a corpus signal, not a population estimate. Outcome data based on expert ratings is not yet available; the outcome-shaped signals surfaced are peer-pair-difference rates and cross-question outlier findings from validation runs."
}
```

Cite-back. Every per-frame `corpus_context` carries `corpus_entries_fired_uris` pointing at corpus entries where the frame fires. The agent can chain to those entries via `resources/read` on `frame-check://corpus/{slug}` to see the frame in use and contrast with the current document's framing. Substrate auditable in both directions: methodology auditable up the chain (catalog and canon graph), evidence auditable down the chain (corpus entries).

The aggregator runs once at first query and is cached for the server's lifetime (corpus content is read-only at runtime). Aggregation is purely deterministic: read-only walks of `profile.json` files plus the most recent `aggregate.json`. No LLM is invoked.

### Signal strength tiers

`signal_strength` per absent_frame record uses a deterministic
heuristic over the canon-graph and the document's coverage signal:

- **`high`**: frame is canon for ≥2 decision-readiness dimensions
  AND the coverage dimension is canon for the frame AND the document
  is weak on coverage (any missing categories). These are the
  load-bearing absences for most readers.
- **`medium`**: frame is canon for ≥1 decision-readiness dimension.
  The caller's model decides whether the absence matters for this
  document.
- **`low`**: frame is not canon for any decision-readiness dimension
  (e.g., FVS-013 Oracle, FVS-014 Temporal Anchoring, FVS-019
  Narrative Coherence as meta-level frames). Consider only in
  cross-cutting analyses.

The heuristic is conservative; future contract minor versions (per
the §13 extension pattern in FRAME_DIVERGENCE_CONTRACT_v1) may
incorporate per-FVS domain applicability metadata, full
decision_readiness profile signals across all five dimensions, and
document-content semantics. The current heuristic produces a
defensible baseline that the caller's V4.2 model can override.

### Added `agent_guidance` keys

When the divergence block is emitted, `agent_guidance` gains two keys:

- `how_to_render_divergence`: caller-side composition instructions.
  The caller's model completes the judgment using the FVS catalog
  and library resources per the requested `divergence_rendering`
  mode. Forbids prescriptive "missing frames you should consider"
  language (contract §4.5). Requires citation by `frame_id` and
  `library_url` (the GitHub markdown URL the user can click); the
  `citation_uri` (frame-check://) is for MCP resource fetches, not
  end-user citations.
- `absence_is_not_prescription`: the §5.1 guarantee-5 language that
  divergence output never implies the user should have used the
  absent frames.

## Canonical URI/URL quartet on every FVS reference (v1.0.12+)

Every record in the payload that identifies a Frame Vocabulary
Standard entry — `frame_library_matches[*]`, `divergence.absent_frames[*]`,
`corpus_context.typical_co_fires[*]` / `typical_co_absences[*]`,
`decision_readiness.dimensions[*].library_entries[*]` /
`fired_library_entries[*]`, `frame_opportunities.opportunities[*]` —
carries four URI/URL fields:

| Field | Value | Use |
|---|---|---|
| `citation_uri` | `frame-check://library/FVS-XXX` | MCP resource URI; pass to `resources/read` |
| `library_resource_uri` | `frame-check://library/FVS-XXX` (same value) | Alias of `citation_uri`; same use |
| `library_url` | `https://github.com/Clarethium/frame-check/blob/master/data/frame_library/FVS-XXX_slug.md` | HTTPS GitHub URL; user-clickable |
| `public_url` | (same HTTPS URL) | Alias of `library_url`; same use |

The aliasing is alias-equality invariant: `citation_uri == library_resource_uri` and `library_url == public_url` in every record. Pre-v1.0.12 the field names varied across blocks (`citation_uri` only on `absent_frames` and `typical_co_*`; `library_resource_uri` only on `decision_readiness` and `frame_library_matches`; `library_url` on `absent_frames` and `frame_library_matches`; `public_url` only on `decision_readiness`). v1.0.10 / v1.0.11 / v1.0.12 progressively normalized this so an adopter writing one renderer for FVS references reads the same shape regardless of which block they parse. Integrations that hardcoded any one of the four names remain valid; the v1.0.12 sweep is additive.

Example payloads in this document show illustrative subsets (often just `citation_uri` + the FVS id) for readability — but the wire emits all four fields on every reference. Pinned by `tests/test_mcp_server.py::test_all_frame_reference_shapes_carry_canonical_uri_url_quartet`.

The `agent_guidance.how_to_cite_frame_matches` text mandates rendering FVS references as markdown links: `[FVS-XXX Frame Title](library_url)`. End-users in MCP clients (Claude Desktop, Cursor) cannot click `frame-check://library/...` URIs because those are MCP-internal; the HTTPS `library_url` / `public_url` gives them an HTTP link they can follow. Agents running entirely through MCP chain the `citation_uri` / `library_resource_uri` into `resources/read` on the matching entry.

The earlier hosted URL form pointed at `frame.clarethium.com/corpus/library/...`; the GitHub URL replaces it because it survives any future hosting transition without rewrites.

## Suggested next actions (`agent_guidance.suggested_next_actions`)

Every `frame_check` response carries an `agent_guidance.suggested_next_actions` block: a list of 2-4 specific, structural-finding-anchored
next-action entries the agent can surface to the user. The block
exists so a Frame Check finding has a discoverable path forward
(reprompts to send back to the source AI, library entries to read,
named MCP prompts to invoke) instead of a static reading.

Each entry has the shape:

```json
{
  "kind": "reprompt | resource | prompt_followup",
  "action_text": "human-readable action description",
  "rationale": "one sentence on why this action is suggested for THIS call's findings",
  "related_url": "library_url for resource kind, optional",
  "related_fvs_id": "FVS-ID for resource kind, optional"
}
```

Derivation rules (deterministic; same input produces same output, same order):

- Position 1 (when `include_divergence=true`): a `resource` entry pointing at the highest-signal_strength absent_frame's library entry, with the clickable `library_url` embedded as a markdown link.
- Position 2-3 (when conditions fire): up to two `reprompt` entries with ready-made follow-up questions for the source AI. Triggers: more than 50 percent unhedged numeric claims, or sourced sentence rate below 10 percent. Each carries the specific numbers from this call so the rationale grounds in this document's findings.
- Final position: an always-included `prompt_followup` entry pointing at the `challenge_document` MCP prompt for the deeper multi-turn loop.

The list is capped at 4 entries (more becomes noise). The block
survives `compose_budget` compression at every tier so compact
callers still get the discovery loop. The
`agent_guidance.how_to_render_suggested_next_actions` key carries
the rendering instruction (small explicit list at the end of the
response, action_text rendered verbatim, embedded markdown links
preserved).

## Composition discipline (insight-led, not measurement-walking)

`agent_guidance` carries a top-level `composition_discipline` field
on every `frame_check` invocation (whether or not divergence is
included). This field exists because testing of the 0.8.0
prerelease surfaced a UX failure: an agent that walks the
measurements one-by-one delivers a statistical readout the user
cannot act on. The field pushes the insight-led discipline into the
tool surface so it travels with every response, not only with the
four sovereignty-prompt invocations.

The discipline (paraphrased; the field carries the canonical text):

1. **INSIGHT-GROUNDED**. The agent composes ONE insight that is a
   reading the user could not see by re-reading the document
   themselves. Every insight clause cites a specific measurement
   (frame_library_matches entry, voice classification, divergence
   absent_frame, decision_readiness dimension reading). If the
   agent cannot cite, it does not assert.
2. **READING-FORM, NEVER VERDICT-FORM**. "The pattern reads as X"
   is a reading. "The document is X" is a verdict. Frame Check
   does not verdict; the agent does not verdict on its behalf.
3. **CONFIDENCE-GATE PIVOTS THE FRAME**. When an off-methodology
   signal fires (under 100 words / non-English / non-analytical
   structure), the insight pivots from "a reading of the document"
   to "what this run reveals about Frame Check's scope". The user
   still gets a reading; it is now about the tool's calibration,
   not the document's framing.
4. **CROSS-CONTEXT COMPOUNDING ONLY WHEN IT ADDS**. The validation
   aggregate or prior measurements are cited only when they
   sharpen this reading; never as scenery.
5. **ABSENCE IS NOT PRESCRIPTION**. Insights name what the framing
   does, never what the document should have done. The reader
   decides what to do with the seeing; that is the sovereignty
   case this tool serves.
6. **PER-LEVEL CLAIM TREATMENT**. The substrate produces three
   qualitatively different kinds of claim, each with its own
   construct discipline. Every composed entity in the payload
   carries a `claim_level` field naming which treatment applies.
   See "Per-level construct treatment" below for the three
   levels and the per-level discipline.

The four sovereignty prompts (`frame_check_my_response`,
`frame_check_this_ai_response`, `challenge_document`,
`explain_framing`) all reference `composition_discipline` in their
bodies and structure their default response around it. The compact
default response is ONE insight + ONE question + closing + expand
invitation; the deep measurement walk is the expand path.

### User-intent interface

The MCP tool parameters (`include_divergence`, `user_goal`, `include_frame_opportunities`, `compose_budget`, etc.) are developer-facing API surface. The end user invoking the substrate via Claude Desktop or another MCP client never types these directly; they invoke a sovereignty prompt by name (or natural language) and the calling agent translates user-intent to MCP parameter values.

The four sovereignty prompts (`frame_check_my_response`, `frame_check_this_ai_response`, `challenge_document`, `explain_framing`) accept three optional user-intent arguments that surface in the user's vocabulary:

- `depth`: `"quick"` | `"thorough"` (default `thorough`). The user's mental model is "fast read" vs "deep audit". Translates to `compose_budget=minimal|full`.
- `goal`: `"decide"` | `"explore"` | `"audit"` | `"challenge"` | `"learn"` (default `audit`). The user's mental model is "what am I trying to do with this reading". Translates to `user_goal` (decide → decide; explore → brainstorm; challenge → audit + adversarial composition note; learn → learn; audit → audit).
- `questions`: `"yes"` | `"no"` (default `no`). The user's mental model is "do I want LLM-generated questions about my document". Translates to `include_frame_opportunities=true|false`.

The prompt body interpolates the translated values into the agent's `Call frame_check(...)` instruction. The agent receives concrete MCP parameter values; the user never types them. Invalid argument values fall back to defaults (prompts are user-invoked surfaces; rejecting an invalid value would be poor UX).

`goal=challenge` is special: it maps `user_goal` to `audit` (not a separate substrate enum) AND injects an adversarial composition note into the prompt body that directs the agent to compose the insight as questions surfacing structural weaknesses (per `agent_guidance.composition_discipline` rule 5, the questions are reading-form not prescriptive).

The `compose_budget` MCP parameter (also exposed at the API layer for sophisticated callers) bounds the substrate's output volume:

- `minimal`: top-3 absent_frames, top-1 absence_cluster, top-1 frame_pattern. For agents in tight working-memory budgets.
- `standard`: top-5 absent_frames, all clusters, all patterns. Middle ground.
- `full` (default): unfiltered. Backwards-compatible.

Slicing happens AFTER the envelope is built so `envelope.tier_counts` reflects PRE-slice counts (the agent sees the truncation honestly rather than thinking the substrate found fewer absences). `divergence.compose_budget_applied` carries the slice level + per-layer returned/total counts so the agent can render "Frame Check identified N absences; showing top M".

Backwards-compatible: omitting `depth/goal/questions` from the prompt invocation produces the same prompt body the prior version produced (defaults match prior behavior). Omitting `compose_budget` from the MCP call preserves the prior unfiltered output.

The third layer of the interface UX is agent guidance for natural-language mapping. Every `frame_check` response carries `agent_guidance.how_to_map_user_intent`: when the user types natural language ("I'm trying to figure out whether to ship this") rather than structured arguments, the agent reads this key to translate user-intent vocabulary into the prompt argument space (depth/goal/questions). Concrete user-phrase → argument mappings are documented per axis (decide / explore / audit / challenge / learn for goal; quick / thorough for depth; yes / no for questions). The discipline named in the guidance: surface chosen options briefly to the user before invoking; default to safe values on ambiguity; honor explicit prompt arguments verbatim over inference. This makes the user-intent vocabulary travel with every response so agents stop guessing.

### Per-level construct treatment

Substrate-side composition shipped twelve roadmap items plus
post-roadmap polish, each adding a new layer of substrate output
(clusters, patterns, deepening, segmented prevalence, opportunities).
The earlier composition discipline treated those layers uniformly:
every signal got the same "reading-form, cite the measurement"
treatment. That conflated four qualitatively different kinds of
claim under one rule set.

The substrate now produces three qualitatively different claim
kinds, and each composed entity carries a `claim_level` field
naming which treatment applies. The per-level discipline lives at
`agent_guidance.claim_level_treatments`, keyed by `claim_level`
value. Three levels:

- **`detector_measurement`**: a deterministic regex/feature
  detector firing or non-firing on the document text. Examples:
  every `frame_library_matches` entry (V1 detector firing); every
  `divergence.absent_frames` record (V1 detector non-firing); the
  per-dimension entries inside `coverage_v2.dimensions`. Validation:
  reproducibility is the validity claim (algorithmic detectors do
  not need IRR); per-signal `construct` blocks carry the
  detector-specific caveats. The agent cites these as "Frame
  Check's detector found markers for X" or "no markers detected
  for X", never "the document covers X" or "the document does not
  address X".
- **`classifier_output`**: a deterministic cascade or scoring
  classifier with margin-aware confidence and runner-up reporting.
  Examples: `analysis.voice` (7-rule cascade), `analysis.genre`
  (six-class scoring with feature-evidence gate), `analysis.temporal`
  (distribution with dominant + balanced flag). Validation: features
  and thresholds are documented; classifier abstains without feature
  evidence (post-2026-04 fix); no precision/recall against labeled
  gold-standard yet, no inter-rater reliability pilot. The agent
  surfaces confidence and runner-up explicitly when borderline; the
  classification is named as Frame Check's reading rather than a
  measured property of the document.
- **`composed_pattern`**: a deterministic composition over
  detector and classifier outputs. The trigger conditions are
  deterministic (canon-graph set membership for `absence_clusters`;
  multi-frame plus doc-signal discriminators for `frame_patterns`;
  multi-feature scoring per dimension for
  `decision_readiness.dimensions`); the reading text inside the
  composition is single-curator authored. Examples: each entry in
  `divergence.absence_clusters`; each entry in
  `divergence.frame_patterns`; each per-dimension dict in
  `analysis.decision_readiness.dimensions` (signal_text is the
  curated reading). Validation: trigger match is reproducible;
  reading is the curator's normative claim about what the trigger
  means; no IRR pilot has measured whether other readers compose
  the same patterns from the same triggers. The agent cites the
  trigger as deterministic AND the reading as Frame Check's
  curator reading.
- **`agent_generated`**: opt-in LLM-composed content from Item 12
  `frame_opportunities`. The substrate delegates the composition to
  an external model (provider + model + cost tracked per-output in
  `model_provenance`). Distinct from the other three levels because
  the output is non-deterministic by design: different runs by
  different model versions can produce different content from the
  same inputs. Examples: each entry in
  `divergence.frame_opportunities.opportunities`. Validation: per-
  opportunity `model_provenance` (provider, model, cost_usd,
  input_tokens, output_tokens, `is_deterministic=false`) is the
  audit trail; reproducibility is not the validity claim because
  the output is generative; IRR is `not_applicable` because
  different models or runs producing different content is the
  design, not a validity gap. The substrate-deterministic identity
  is preserved: when the opt-in flag is omitted, the substrate
  composes without LLM and the agent gets the deterministic
  substrate alone (clusters, patterns, absences with goal/genre
  relevance). The agent cites the model provenance + cost AND
  never presents LLM-generated content as Frame Check's
  measurement (the `teaching_question_general` on each opportunity
  remains the stable catalog reference; the `generated_question` is
  one document-specific application).

`claim_level_treatments` carries per-level metadata for each:

```json
"claim_level_treatments": {
  "detector_measurement": {
    "claim_type": "Deterministic feature/regex detector firing or non-firing on the document text.",
    "validation_status": {
      "deterministic": true,
      "methodology_documented": true,
      "inter_rater_reliability": "not_applicable",
      "validity_data": "Vocabulary-and-pattern detection with documented lower-bound detection posture. Per-signal construct blocks carry the detector-specific caveats. IRR is not applicable to algorithmic detectors; reproducibility is the validity claim and is documented per signal."
    },
    "caveats": ["...", "...", "..."],
    "how_to_cite": "Frame Check's detector found markers for X / no markers detected for X."
  },
  "classifier_output": { "validation_status": { "inter_rater_reliability": "not_yet_measured", "...": "..." }, "...": "..." },
  "composed_pattern":   { "validation_status": { "inter_rater_reliability": "not_yet_measured", "...": "..." }, "...": "..." }
}
```

Why this exists. External evaluation needs a clear epistemic claim
chain to evaluate. The methodology paper needs per-level construct
treatment as its central argument. A teaching surface that adapts
to user state (first-time vs proficient) needs per-level metadata
to decide which claims to surface with which discipline. The
substrate carries five claim levels (`detector_measurement`,
`classifier_output`, `llm_classifier_output`, `composed_pattern`,
`agent_generated`); each carries its own validation posture and
how-to-cite guidance.

The epistemic discipline is preserved at every level. IRR status
is reported honestly (`not_yet_measured` for classifiers and
composed patterns, since no IRR pilot has shipped). Validity data
names the gap explicitly. The substrate stays construct-honest
about its own validation status; the agent inherits the per-level
treatment rather than over-claiming on the user's behalf.

### Catalog stability

Contract c1.0 pins the divergence catalog to `library_v3`. The pin
is a deliberate contract-stability commitment; a future contract
minor version (c1.1) may add additional pin options.

FVS-020 is excluded from divergence emission as a retirement from
detection scope; consumers will not see it in `absent_frames`.

### Rendering modes

`divergence_rendering` affects only `AbsentFrameRecord` decoration:

- `list` (default): flat list with citations.
- `completeness_check`: checklist with domain-relevance rationale.
- `teaching_questions`: `teaching_question` field attached to each
  record when the FVS entry defines one.
- `narrative`: caller renders as a single prose paragraph over the
  same underlying data.

The caller's agent model performs the rendering per the preference
and the `how_to_render_divergence` guidance.

## Scope regime (canon-play construct honesty)

Layer 11's primary P-detection signal degrades on number-dense sources.
Monte Carlo measurement: false-positive rate is ~4% with 2 source numbers,
~68% with 10, ~97% with 20. On saturated sources, fabricated numbers can
pass the derivation check via coincidental arithmetic match.

The `scope_assessment.derivation_regime` field classifies every invocation:

- **`diagnostic`** (N < 10 unique source numbers): Layer 11 primary signal
  is reliable. Cite either layer.
- **`transition`** (10-14): Layer 11 is noisy; cross-reference Layer 4.
- **`saturated`** (N ≥ 15): Layer 11's primary signal is effectively
  disabled. Cite Layer 4 `source_fidelity.unsourced_rate` for numerical
  claims, **not** `grounding_decomposition.has_projection`.

`agent_guidance.scope_regime_guidance` adapts per invocation so the
calling agent gets this directive in-band.

## Evidence posture across the five analytical signals

The MCP payload carries a per-signal `construct` sub-block that agent framework serializers can quote verbatim. Each signal has a construct that fits its signal shape (presence/absence vs classification vs distribution); none of the signals is restated with false certainty by agents following the `how_to_serialize` guidance.

Signal-by-signal:

| Signal | Construct | Key v2 fields |
|--------|-----------|---------------|
| Coverage | lower-bound | `coverage_v2.dimensions[cat].{status, markers_matched, candidate_sentences}` + first-class `construct` block |
| Epistemic | lower-bound | `epistemic.candidate_attribution_sentences` + per-entry caveat |
| Claims | lower-bound | `claims_extracted.candidate_hedge_count` + per-claim `candidate_hedge_marker` |
| Voice | classification-confidence | `voice.{confidence, margin_to_threshold, runner_up, runner_up_margin, construct}` |
| Temporal | distribution-with-dominant | `temporal.{dominant_margin, balanced, construct}` |

Coverage, epistemic, and claims share a **lower-bound detection** posture: the primary regex is a lower-bound detection signal; `not_detected` is a claim about vocabulary, not about the document. Candidate-miss patterns surface sentences the reader may recognize as covering the dimension despite the primary regex missing the form. Each candidate carries an explicit caveat.

Voice uses a **classification-confidence** construct: the 7-rule cascade picks a winner, but a document at a threshold boundary could flip with a small feature change. `margin_to_threshold` names how decisively the winner crossed; `runner_up` names the next cascade class; `confidence` flags borderline calls. Agents are directed to say "classified as X, borderline; Y nearly fired" rather than "the document is X" when confidence is borderline.

Temporal uses a **distribution-with-dominant** construct: past/present/future percentages sum to ~100%, and `dominant` picks the highest. But a 38/35/27 split reads `past-dominant` while being effectively balanced. `dominant_margin` reports the lead; `balanced` flags distributions where the dominant label should not be read as time-anchoring.

### Coverage v1 and v2 shapes (compatibility window)

The MCP server emits both legacy v1 and new v2 shapes for the **coverage** signal. Phase 1 (additive v1 + v2 emit) shipped 2026-04-19; Phase 2 (v1 deprecation notice in the v1 caveat) activated 2026-04-21. New integrations MUST read `coverage_v2`. Phase 3 (stop emitting v1, conditional on 80%+ v2 adoption, no earlier than six months after Phase 2) is a future release. Epistemic, claims, voice, and temporal signals use a single shape with additive Phase A/B fields (no v1/v2 split).

**v1 coverage shape** (legacy, still emitted):

```json
"coverage": {
    "addressed": ["causes", "risks", "stakeholders"],
    "missing": ["trends", "uncertainty"],
    "addressed_count": 3,
    "total_categories": 5,
    "per_category_density_per_1kw": { ... },
    "caveat": "Coverage is keyword-and-pattern based. ..."
}
```

**v2 coverage shape** (forward contract):

```json
"coverage_v2": {
    "contract_version": 2,
    "dimensions": {
        "causes": {
            "status": "detected",
            "markers_matched": ["because", "due to", "driven by"],
            "sentence_matches": [
                {
                    "sentence_index": 3,
                    "sentence_preview": "The rise was caused by regulatory changes ...",
                    "markers_in_sentence": ["caused by"]
                }
            ],
            "distinct_sentences_detected": 3,
            "marker_count": 3,
            "density_per_1kw": 3.4,
            "signal_strength": "moderate",
            "vocabulary_searched_sample": ["because", "due to", "..."],
            "vocabulary_source": "framing.py::ANALYTICAL_CATEGORIES[\"causes\"]"
        },
        "trends": {
            "status": "not_detected",
            "markers_matched": [],
            "candidate_sentences": [
                {
                    "sentence_index": 6,
                    "sentence_preview": "Analysts argue that restructuring accelerated dramatically...",
                    "candidate_marker": "restructuring",
                    "caveat": "Candidate pattern fired; primary detector did not. Reader judges whether this sentence substantively covers the dimension."
                }
            ],
            "signal_strength": "none",
            "...": "..."
        }
    },
    "summary": {
        "dimensions_with_detected_markers": 3,
        "dimensions_without_detected_markers": 2,
        "total_dimensions": 5,
        "coverage_balance": 0.49
    },
    "construct": {
        "signal_type": "vocabulary_and_pattern_detector",
        "statement": "The coverage signal is vocabulary-and-pattern based. ...",
        "reference": "https://frame.clarethium.com/corpus/methodology/",
        "how_to_serialize": "When restating this analysis to a user, say 'the detector found markers for X, Y, Z' rather than 'the document covers X, Y, Z.' ..."
    }
}
```

### Voice v2 shape (Phase B classification-confidence)

```json
"voice": {
    "classification": "prescriptive",
    "signals": { "first_person_plural_pct": 0, "second_person_pct": 45, "imperative_count": 8, "speculative_pct": 0 },
    "available_classes": ["promotional", "prescriptive", "analytical", "descriptive", "advisory"],
    "confidence": "high",
    "margin_to_threshold": 30.0,
    "runner_up": "promotional",
    "runner_up_margin": -20.0,
    "construct": {
        "signal_type": "cascade_classification",
        "statement": "Voice classification is a 7-rule deterministic cascade. ...",
        "reference": "https://frame.clarethium.com/corpus/methodology/",
        "how_to_serialize": "When restating this classification to a user, say 'classified as X' rather than 'the document is X.' When confidence is 'borderline', name the runner-up class explicitly: 'classified as X, borderline; Y nearly fired.' ..."
    }
}
```

### Temporal v2 shape (Phase B distribution-with-dominant)

```json
"temporal": {
    "dominant": "past",
    "distribution_pct": { "past": 45, "present": 35, "future": 20 },
    "dominant_margin": 10,
    "balanced": false,
    "construct": {
        "signal_type": "distribution_with_dominant",
        "statement": "Temporal orientation is the distribution of past, present, and future tense markers across sentences. ...",
        "reference": "https://frame.clarethium.com/corpus/methodology/",
        "how_to_serialize": "When restating, say 'X-oriented with a Y-point margin over the runner-up tense' rather than 'the document is X-oriented.' When balanced is True, say 'temporally balanced; no tense dominates' ..."
    }
}
```

### Why the five-signal treatment matters

Agent frameworks that serialize MCP tool responses often paraphrase raw fields into user-facing prose. Without per-signal construct scaffolding, those paraphrases tend to overclaim: `"missing": ["trends"]` becomes "the document does not address trends"; `"voice": "prescriptive"` becomes "the document is prescriptive." The first drops the vocabulary-based detection caveat; the second drops the classification confidence.

The v2 contract carries the construct through structure AND through serialization guidance (`how_to_serialize`). Agents that iterate `analysis[signal].construct.how_to_serialize` get consistent guidance regardless of which signal they are restating.

**Signal strength thresholds** (coverage only): `none` at density 0; `nominal` at 0 < density < 3; `moderate` at 3 <= density < 10; `substantive` at density >= 10.

**Voice borderline threshold:** winner `margin_to_threshold < 2` OR `runner_up_margin > -2` (small feature change could flip classification).

**Temporal balanced threshold:** no tense ≥ 50% AND `dominant_margin < 10` points.

### Migration plan (coverage only)

**Phase 1** (2026-04-19, shipped): additive v1 + v2 emit. **Phase 2** (2026-04-21, active): v1 carries a deprecation notice in its `caveat` field; clients MUST read `coverage_v2` for new integrations. **Phase 3** (conditional on 80%+ v2 adoption, no earlier than six months after Phase 2 activation): v1 stops emitting. External consumers targeting Phase 3 readiness should read `coverage_v2` directly today.

Epistemic / claims / voice / temporal Phase A+B fields are additive; no migration window needed.

The construct-carrying payload is the load-bearing surface for callers that compose framing analysis with their own model: each signal is named, scoped, and emitted with the structural matchers it derives from, so the caller's model has the same evidence base that produced the verdict. Payload sizes track the listed signals and are bounded by the configured catalog version.

## Determinism

`frame_check` is deterministic for the same inputs. Two calls with
identical `(document_text, source_text)` return bit-identical payloads
except for `provenance.analysis_latency_ms` (wall-clock). No LLM is
invoked; `provenance.analysis_cost_usd` is always `0.0`.

## Production hosting status

The provenance block carries `tool_url`, `methodology_paper`,
`frame_library`, and `calibration_corpus` URLs that point at the
canonical production site `frame.clarethium.com`. Production
hosting is active. Two provenance fields surface the state inline
so an agent can distinguish "URL canonicalized and live" from "URL
malformed or wrong" without out-of-band knowledge, and so a future
maintenance pause is communicable without protocol changes:

- `provenance.production_status`: `"active"` or `"paused"`. Single
  source of truth; the constants in `mcp_compose.py` flip together
  on a hosting transition.
- `provenance.production_status_note`: human-readable explanation
  describing the current hosting state and naming the always-resolvable
  mirrors (GitHub repository, PyPI package) that remain stable across
  any transition.

Always-resolvable mirrors: the public GitHub repository at
`https://github.com/Clarethium/frame-check` and the PyPI
package `frame-check-mcp`. Citations resolve against the versioned
PyPI release (`server_version` field), the brand version
(`frame_check_version` field, decoupled from the wheel), or the
canonical production URL.

## Citation

The tool response includes a citation string in `provenance.citation`.
When surfacing the analysis to a user, quote the Frame Check measurement
as Frame Check's, not as your own reading.

```
Lucic, L. (YEAR). Frame Check: a research instrument for framing and
verification in documents. https://github.com/Clarethium/frame-check
```

## License

- Code: Apache-2.0
- Corpus (frame library, methodology, calibration): CC-BY-4.0
- Analysis output: CC-BY-4.0; may be reproduced with attribution

## Tests

```bash
python3 -m pytest tests/test_mcp_server.py
```

Covers the three layers: epistemic-payload builder, JSON-RPC dispatcher,
and end-to-end subprocess roundtrip. The subprocess test spawns the
server exactly the way Claude Desktop does, so a green run is a
reasonably strong install-safety signal.

For the full suite (882 tests across 25 files including the
adversarial harness, conformance driver, cookbook recipes, and
per-module 80% coverage gate on the seven-module wheel surface):

```bash
python3 -m pytest -q
```
