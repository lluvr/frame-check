# MCP Contract v2 Proposal: Carrying the Detector Construct Through Structure

**Status:** proposal v1, 2026-04-19. Not implemented. Not approved.
**Author:** collaborating agent (under curator review).
**Purpose:** propose a v2 shape for the `frame_check` and `frame_compare` MCP tool responses that carries the detector's vocabulary-based construct (METHODOLOGY §1.3, VISITOR_AUDIT §7 Fix A) through the JSON structure itself, not only through prose caveats. v1 mitigated the construct-honesty gap with prose caveats; v2 closes it structurally.
**Relationship to shipped v1:** v1 remains correct and live. v2 is an additive redesign with a compatibility window. v2 does not retract v1.

---

## 1. Motivation

### 1.1 What v1 gets wrong, specifically

The shipped v1 MCP response for coverage exposes:

```json
"coverage": {
    "addressed": ["causes", "risks", "stakeholders"],
    "missing": ["trends", "uncertainty"],
    "addressed_count": 3,
    "total_categories": 5,
    "per_category_density_per_1kw": {"causes": 3.4, ...},
    "caveat": "Coverage is keyword-and-pattern based. The 'addressed' list names categories where the detector found its vocabulary; the 'missing' list names categories where it did not. ..."
}
```

The caveat is honest. The keys are not. An agent that serializes `missing: ["trends", "uncertainty"]` to a user without reading the caveat emits "the document does not address trends or uncertainty": the exact existential claim Fix A spent 15 shipped-surface edits removing from the product UI. The prose caveat is a sidecar; the structure carries the bug.

**The specific failure mode:**
- Agent reads `coverage.missing`.
- Agent generates prose from the key name.
- Prose restates existential claim the detector cannot support.
- The caveat field, being unstructured prose, is not naturally quoted in the agent's output.

This is not hypothetical. An agent-framework vendor whose library generates summaries from JSON responses (Claude Code, OpenAI Agents SDK, LangChain, Semantic Kernel) will emit the existential claim by default unless the JSON shape makes it harder to.

### 1.2 What "carrying construct through structure" means

The shipped METHODOLOGY §1.3 states:

> A `missing` signal is a lower-bound claim about detection, not an upper-bound claim about the document. The honest English rendering is "no markers detected for X," not "does not address X."

v2 makes the response shape express this directly:

- No flat `missing` list that invites existential serialization.
- Per-dimension object with `status`, `markers_matched` (what actually fired), and `vocabulary_searched` (what the detector looked for).
- The structural cost of existential serialization becomes higher than the structural cost of honest serialization. Agents following the shape-of-least-resistance produce honest prose by default.

### 1.3 Why now, and why not blog post, rename, or both

Three alternatives considered and rejected:

- **Rename keys (`missing` → `no_markers_detected`).** Fixes the string but not the shape. An agent serializing `no_markers_detected: ["trends"]` still emits "the document has no markers detected for trends," which collapses back to an existential-feeling claim about the document. The rename is also a breaking change without delivering structural construct-carrying benefit.

- **Stronger caveat.** Prose caveats asymptote. A maximally strong caveat would be a full paragraph per response, which consumers skip.

- **Do nothing; trust the caveat.** Consumers demonstrably ignore prose caveats in agent-framework serialization. The empirical base rate of caveat-respecting serialization in AI agent frameworks is low.

v2 structural redesign is the middle path: compatible (additive), explicit (structure carries the claim), and single-pass (one contract bump rather than repeated caveat strengthening).

**Why now, and not post-publication:** post-publication rename or redesign is more expensive because downstream agents that quote specific keys (e.g., paper supplementary code) cannot update. Pre-publication is cheap; post-publication is a migration.

---

## 2. Design principles

1. **Construct through structure.** The JSON shape should be what the detector actually produces: per-dimension evidence. Not a pair of lists (addressed, missing) that describes the dimensions as classified.

2. **Evidence inline, not by reference.** `markers_matched: ["because", "due to"]` is strictly more honest than `marker_count: 2`. The cost (larger payload) is acceptable for small documents; large documents can truncate.

3. **The detector's lens is visible.** `vocabulary_searched` exposes what the regex looks for. This is not a trade secret; it is in `framing.py::ANALYTICAL_CATEGORIES` and METHODOLOGY is public. Exposing it in the response saves the consumer a documentation lookup and demonstrates the construct.

4. **Status is an enum, not a boolean.** `detected` vs `not_detected` (rather than true/false for "covered") lets future extensions add `uncertain` (for low-density or contested cases) without another contract bump.

5. **Signal strength is derived, not asserted.** A threshold-based derivation ("density < 3 → nominal; density 3-10 → moderate; density > 10 → substantive") lets agents shorthand the depth question without rediscovering the density heuristic. The threshold is named, not magic.

6. **Construct statement is a first-class field, not a sidecar caveat.** The response-level `construct.statement` and `construct.reference` fields point at the detector's measurement shape; agents that serialize the response have one natural location to quote for provenance.

7. **Backwards compatibility via overlap window.** v2 emits alongside v1 for one release. Consumers migrate at their own pace. v1 is deprecated (not removed) when observed adoption hits 80%+ of active MCP sessions.

8. **Scope v2 to coverage only.** The same redesign applies to voice, temporal, epistemic, claim analysis, but expanding v2 to all five signals at once increases migration cost linearly. Coverage is the Fix A primary surface and the most-consumed signal; other signals get the v2 treatment in v3+.

---

## 3. Proposed v2 response shape

### 3.1 Top-level change in `frame_check`

The v1 shape is preserved. A new top-level `coverage_v2` field is added, mirroring `coverage` with the v2 shape. One release cycle later, clients signal v2 readiness via a `prefer_contract_version` parameter; `coverage` is populated with v2 content and `coverage_v1` is populated with v1 content for legacy consumers.

```json
{
    "coverage": { /* v1 shape, unchanged */ },
    "coverage_v2": { /* v2 shape, see below */ },
    ...
}
```

Rationale: additive. No consumer breaks. New consumers read `coverage_v2` directly.

### 3.2 `coverage_v2` shape (full)

```json
{
    "contract_version": 2,
    "dimensions": {
        "causes": {
            "status": "detected",
            "markers_matched": ["because", "due to", "stems from"],
            "marker_count": 3,
            "density_per_1kw": 3.4,
            "signal_strength": "moderate",
            "vocabulary_searched_sample": [
                "because", "due to", "driven by", "caused by",
                "as a result", "led to", "stems from", "attributed to",
                "resulting from", "..."
            ],
            "vocabulary_source": "framing.py::ANALYTICAL_CATEGORIES[\"causes\"]"
        },
        "risks": {
            "status": "detected",
            "markers_matched": ["risks", "threats", "vulnerabilities"],
            "marker_count": 4,
            "density_per_1kw": 4.1,
            "signal_strength": "moderate",
            "vocabulary_searched_sample": ["risks", "threats", "challenges", "concerns", "..."],
            "vocabulary_source": "framing.py::ANALYTICAL_CATEGORIES[\"risks\"]"
        },
        "stakeholders": {
            "status": "detected",
            "markers_matched": ["affects", "stakeholders"],
            "marker_count": 2,
            "density_per_1kw": 2.0,
            "signal_strength": "nominal",
            "vocabulary_searched_sample": ["affects", "impacts", "stakeholders", "..."],
            "vocabulary_source": "framing.py::ANALYTICAL_CATEGORIES[\"stakeholders\"]"
        },
        "trends": {
            "status": "not_detected",
            "markers_matched": [],
            "marker_count": 0,
            "density_per_1kw": 0.0,
            "signal_strength": "none",
            "vocabulary_searched_sample": ["grow", "decline", "increase", "..."],
            "vocabulary_source": "framing.py::ANALYTICAL_CATEGORIES[\"trends\"]"
        },
        "uncertainty": {
            "status": "not_detected",
            "markers_matched": [],
            "marker_count": 0,
            "density_per_1kw": 0.0,
            "signal_strength": "none",
            "vocabulary_searched_sample": ["unclear", "uncertain", "may", "might", "..."],
            "vocabulary_source": "framing.py::ANALYTICAL_CATEGORIES[\"uncertainty\"]"
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
        "statement": "The coverage signal is vocabulary-and-pattern based. Each dimension has a regex expressing the lexical markers the detector counts as evidence. 'detected' means the detector matched at least one marker; 'not_detected' means it matched none. Both directions carry measurement error: 'detected' may be substantive or nominal (see signal_strength and density_per_1kw), and 'not_detected' may reflect vocabulary the detector does not recognize rather than absence of coverage in the document. The measurement is a lower-bound claim about vocabulary, not an upper-bound claim about the document.",
        "reference": "https://frame.clarethium.com/corpus/methodology/#13-construct-what-the-analytical-coverage-detector-actually-measures",
        "how_to_serialize": "When restating this analysis to a user, say 'the detector found markers for X, Y, Z' rather than 'the document covers X, Y, Z.' Say 'no markers detected for trends and uncertainty' rather than 'the document does not address trends or uncertainty.' Under-detection is a known failure mode and this construct statement is the authoritative phrasing."
    }
}
```

### 3.3 Per-dimension field semantics

- **`status`** (enum: `"detected"`, `"not_detected"`; future: `"uncertain"`). The enum is extensible; consumers should treat unknown status values as non-binary (not as `"not_detected"`).

- **`markers_matched`** (list of strings). The specific tokens that fired. Deduplicated; lowercased. Up to 20 per dimension (truncation-safe for very-high-density documents; if truncated, a `markers_matched_truncated_at: 20` field is added and `marker_count` remains authoritative).

- **`marker_count`** (int). Total count of matches, not unique tokens. `marker_count >= len(markers_matched)` always; exceeds when the same token fires multiple times.

- **`density_per_1kw`** (float). Markers per 1,000 words of document text. Computed from `marker_count / (total_words / 1000)`. Same as v1.

- **`signal_strength`** (enum: `"none"`, `"nominal"`, `"moderate"`, `"substantive"`). Derived from density: `none` at density 0; `nominal` at 0 < density < 3; `moderate` at 3 <= density < 10; `substantive` at density >= 10. Thresholds are explicit and documented in the construct field.

- **`vocabulary_searched_sample`** (list of strings). First 10-15 tokens from the regex alternation. Truncated for payload size; full regex is at `vocabulary_source`.

- **`vocabulary_source`** (string, file reference). The code-identifier where the full regex lives. Enables consumers to audit the detector's lens.

### 3.4 Summary field

Intentionally named `dimensions_with_detected_markers` and `dimensions_without_detected_markers` rather than `addressed_count` / `missing_count`. The field name is the claim. Consumers serializing "3 of 5 dimensions with detected markers" produce honest prose by default.

### 3.5 Construct field

First-class. `statement` is the authoritative construct claim. `reference` is the canonical URL. `how_to_serialize` is explicit guidance for agents: the same content that exists as `agent_guidance.how_to_cite_faithfully` in v1, restated response-locally so agents serializing coverage see the guidance in the coverage context.

### 3.6 `frame_compare` parallel

`frame_compare` gets a `coverage_comparison_v2` field that uses the same dimension-keyed shape for A and B, plus derived cross-document fields:

```json
"coverage_comparison_v2": {
    "contract_version": 2,
    "a": { /* full dimensions-object for document A, same shape as §3.2 */ },
    "b": { /* full dimensions-object for document B */ },
    "cross_document": {
        "shared_detected": ["causes", "risks"],
        "shared_not_detected": ["uncertainty"],
        "only_a_detected": ["stakeholders"],
        "only_b_detected": ["trends"],
        "construct_note": "shared_not_detected names dimensions where neither document shows detected markers. This is a lower-bound claim about detection, not an upper-bound claim about either document; either document may discuss the dimension using vocabulary the detector does not recognize."
    }
}
```

The v1 `unique_omissions.a_omits` / `unique_omissions.b_omits` keys become `only_a_detected` / `only_b_detected` in v2 (inverted semantically: `only_a_detected` lists dimensions where A showed markers and B did not; previously `b_omits` lists dimensions where A showed markers and B did not, inverted). The v2 key name matches the actual semantic.

---

## 4. Migration plan

### 4.1 Phase 1: additive emission (1 release window, ~1 month)

Implement v2 shape. Emit both `coverage` (v1, unchanged) and `coverage_v2` in every response. Same for `unique_omissions` and `coverage_comparison_v2`. Document in MCP_SERVER.md that v2 is the forward contract; v1 is maintained for compatibility.

Release notes to external consumers (one round of messages to the subset we can identify): "Frame Check MCP v2 available; see MCP_CONTRACT_V2_PROPOSAL.md and MCP_SERVER.md."

### 4.2 Phase 2: v1 deprecation signal (1 release window, ~1 month)

Add a `deprecation_notice` field to the v1 `coverage.caveat`: "`coverage` fields (v1) are deprecated as of 2026-XX-XX. Use `coverage_v2`. v1 emission will continue through 2026-YY-YY." Telemetry: measure v2 adoption via consumer-agent user-agent string if exposed.

### 4.3 Phase 3: v1 removal (conditional, after 80%+ v2 adoption)

When telemetry shows 80%+ of active sessions reading `coverage_v2`, stop emitting v1. Consumers still on v1 get a single error response with a migration link, then requests are rejected. Timeline: not earlier than 6 months after Phase 2.

If 80% adoption is not reached in 6 months of Phase 2, revisit: either reduce adoption expectation (v1 stays longer) or push on specific high-volume consumers to migrate.

### 4.4 Code migration points

The v2 emission requires changes in:

- `mcp_server.py::build_epistemic_payload`: add `coverage_v2` to the analysis dict (lines ~1139-1157 v1 `coverage` block).
- `mcp_server.py::_summarize_per_document`: add `coverage_v2` to the compare per-doc summary (lines ~1558-1574).
- `mcp_server.py::_build_structural_framing_data` (or whatever produces the compare cross-document framing): add `coverage_comparison_v2`.
- `comparison.py::frame_differences`: if the cross-document prose uses `unique_omissions.a_omits`, update to use the v2 inverted semantic `only_a_detected` / `only_b_detected`.
- `framing.py::detect_coverage`: add an output field surfacing per-dimension `markers_matched` (list of the actual regex matches), not just the count. This is the underlying data v2 exposes. Current implementation discards the matched strings and keeps only the count. Small refactor: capture and return.

Estimated effort: 2-3 focused days for implementation + tests. Bumps test count by ~20-30 new tests covering v2 shape.

---

## 5. Scope: what is v2 and what is not

### 5.1 In v2

- `coverage` → `coverage_v2` with full dimension objects, markers_matched, vocabulary_searched_sample, construct block.
- `frame_compare` cross-document: `coverage_comparison_v2` with inverted-semantic field names (`only_a_detected`, etc.).
- Construct block as first-class field on coverage responses.
- MCP_SERVER.md documentation update.

### 5.2 Deferred to v3

- Voice signal redesign (should also expose markers_matched for imperative/we/you patterns).
- Temporal signal redesign (expose which tense markers fired).
- Epistemic signal redesign (expose which attribution markers fired).
- Claim analysis redesign (expose which hedge patterns fired per claim).
- Frame library matches redesign (expose rule-level evidence: which coverage and voice conditions triggered each match).

v3 is a larger body of work. v2 delivers the highest-leverage construct-honesty improvement (coverage, the most consumed signal) without coupling to the full redesign.

### 5.3 Explicitly not in v2

- Renaming v1 keys in place. Breaks consumers; does not carry construct through structure.
- Removing the `caveat` field in v1 `coverage`. It remains; v2 adds, v2 does not subtract from v1.
- Changing the `frame_check` tool name or parameter signature. Contract-version evolution, not endpoint rename.

---

## 6. Rationale table for design decisions

| Decision | Option considered and rejected | Why chosen path wins |
|----------|-------------------------------|---------------------|
| Dict-per-dimension vs parallel lists | Parallel lists (v1 shape but with renamed keys) | Dict surfaces all 5 dimensions at top level; consumers iterate without set operations |
| `markers_matched` inline | Matched markers via separate tool call | Single-response evidence; agent does not need multi-call choreography |
| `vocabulary_searched_sample` (truncated) vs full regex | Full regex in response | Payload size; full regex is public at `vocabulary_source` anyway |
| `signal_strength` enum vs raw density | Raw density only | Enum shortcuts common agent use cases (shorthand "substantive" check) while density is retained for precision |
| Construct as first-class field vs metadata header | HTTP header carrying construct | MCP is JSON-over-stdio, not HTTP; response-body is the only universal location |
| Additive migration vs in-place rename | In-place rename with deprecation | Breaks live consumers; no upside |
| Phase 1 both-emit vs feature flag | Client-opt-in via parameter | Both-emit lets consumers migrate at their own pace without server-side consumer tracking |

---

## 7. Honest limits of this proposal

- **This is pre-implementation.** The proposal has been stress-tested against the Fix A posture shift and METHODOLOGY §1.3 construct, but it has not been implemented, so no consumer has tested the v2 serialization behavior empirically. The design may need revision after implementation.

- **Payload size increase is real.** v2's per-dimension objects are ~5-10x larger than v1's flat lists. For a 2000-word document with 20 matches across 5 dimensions, v1 coverage payload is ~200 bytes; v2 is ~1500-2000 bytes. Not large in absolute terms, but worth measuring under realistic load if v2 emission is unconditional.

- **The v2 shape does not solve all agent serialization defects.** An agent determined to emit existential claims about the document can still do so from v2's `dimensions.trends.status = "not_detected"`. v2 makes honest serialization easier; it does not force it. Agent-framework vendors remain the bottleneck for end-to-end construct honesty.

- **The `vocabulary_searched_sample` field risks gaming.** If a document author knows the detector vocabulary, they can pepper the text with marker words to trigger `detected` without substantive coverage. v1 has the same gaming risk; v2 makes it slightly more discoverable (the sample exposes the list). Curator call: the trade-off favors transparency (consumers and readers can audit the lens) over gaming opacity (security-by-obscurity fails against motivated adversaries).

- **v2 is not a universal cure for construct mismatches.** A document author, a reader, and an agent can all reach different conclusions from the same `coverage_v2` payload; the proposal only shifts the default serialization toward honest.

- **v3 is larger than this proposal sketches.** The v3 treatment of voice, temporal, epistemic, and claim analysis requires an equivalent redesign document each; claiming "v3 extends the pattern" is a roadmap gesture, not a specification.

- **Migration telemetry assumes consumer-identifiable sessions.** If MCP sessions do not carry a stable session identifier, 80%-adoption measurement is approximation by heuristic rather than direct count.

---

## 8. Decisions required from curator

Before v2 can be implemented:

1. **Approve or revise the overall shape.** The per-dimension object structure and the construct field are the load-bearing choices. If either is rejected, the proposal restarts.

2. **Approve or revise the `frame_compare` inversion.** v1 `unique_omissions.a_omits` becomes v2 `only_a_detected` with inverted semantic. Consumers that read v1 `a_omits` as "dimensions where A omits coverage" will read `only_a_detected` as "dimensions where A has detected markers and B does not": opposite semantic. The name matches the semantic but is disorienting if a reader mentally anchored on v1.

3. **Approve the migration timeline.** Phase 1 (additive), Phase 2 (deprecation), Phase 3 (conditional removal). Timing is flexible; the shape is less so.

4. **Decide on scope constraint.** v2 = coverage only, or v2 = coverage + one other signal (voice most-requested for concrete teaching-question construction)? Broader v2 increases implementation time but reduces the v3 surface.

5. **Decide on telemetry.** Phase 3 removal depends on adoption measurement. If the project does not want to instrument consumer identification, v1 never removes; v2 stacks forever. Acceptable outcome; the curator should name the preference rather than default.

---

## 9. References

- `METHODOLOGY.md` §1.3: the construct statement this proposal carries into structure.
- `VISITOR_AUDIT.md` §7 Fix A: the posture shift in product surfaces; v2 brings the same posture to the MCP contract.
- `mcp_server.py`: v1 contract emission.
- `comparison.py`: v1 cross-document compare payload.
- `framing.py::ANALYTICAL_CATEGORIES`: the vocabulary the v2 payload exposes.
- `MCP_SERVER.md`: external-facing documentation; will need v2 section on approval.

---

## 10. Empirical payload-size measurements (added 2026-04-20)

Measured post-implementation against three realistic document sizes, confirming the §7 honest-limit about payload growth and quantifying the `prefer_contract_version=2` savings.

| Document size | Word count | v1 coverage bytes | v2 coverage bytes | Total payload bytes | v2:v1 ratio |
|---------------|-----------:|------------------:|------------------:|--------------------:|------------:|
| short | 89 | 968 | 3,606 | 16,242 | 3.73x |
| medium | 308 | 969 | 3,671 | 17,180 | 3.79x |
| long | 2,450 | 973 | 3,708 | 17,950 | 3.81x |

v2 coverage is ~3.7-3.8x the v1 byte size. The extra bytes are `markers_matched` (per-dimension matched tokens, deduplicated and capped at 20), `vocabulary_searched_sample` (13 tokens per dimension), `vocabulary_source` strings, and the `construct` block (statement, reference, how_to_serialize).

Absolute v2 coverage payload is 3.6-3.7KB regardless of document length, because the construct block and vocabulary samples are constant and `markers_matched` is capped. Document-length-dependent growth is negligible at current vocabulary cardinality.

`prefer_contract_version=2` savings (dropping the duplicate v1 coverage block):

| Document size | Both-emit total | v2-only total | Savings | Savings % |
|---------------|----------------:|--------------:|--------:|----------:|
| short | 16,242 | 15,260 | 982 | 6.0% |
| medium | 17,180 | 16,197 | 983 | 5.7% |
| long | 17,950 | 16,963 | 987 | 5.5% |

Savings are ~1KB per response. Not large in absolute terms; the shape-of-least-resistance cost of additive emission is modest. A consumer that expects to make millions of calls can use `prefer_contract_version=2` to eliminate the duplication; for typical use, default additive emission is cheap enough.

**Honest-limit §7 confirmed:** v2 IS larger than v1 by the predicted magnitude. **Honest-limit §7 bounded:** the absolute payload stays under 18KB even on long documents, well within any reasonable network budget for MCP tool responses. The measurement closes the honest-limit at the empirical level; no further action required.

---

---

## 11. Phase A extension shipped 2026-04-20: sentence attribution + candidate-miss

Post-initial-implementation upgrade to v2 coverage. Closes the under-detection construct (METHODOLOGY §1.3) at operational granularity. Shipped additively; no breaking change to v2 clients.

### 11.1 What was added

Two new per-dimension fields in `coverage_v2.dimensions[cat]`:

- **`sentence_matches`**: list of dicts, one per unique sentence where the primary regex fired for this dimension. Deduplicated by sentence index. Each entry: `{sentence_index, sentence_preview, markers_in_sentence}` where `markers_in_sentence` is the list of primary markers that fired in that sentence. Capped at 20 sentences per dimension; `distinct_sentences_detected` reports the full pre-cap count; `sentence_matches_truncated_at_20` boolean flag.

- **`candidate_sentences`**: list of dicts for not-detected dimensions only. Each entry: `{sentence_index, sentence_preview, candidate_marker, caveat}` where `candidate_marker` is a token from `framing.py::CANDIDATE_PATTERNS`, a weaker regex targeting syntactic/semantic hints the primary detector does not recognize (e.g., "rationale," "centers on," "given" for causes; "restructuring," "diversification" for trends). Capped at 10 candidates per not-detected dimension. Each carries an explicit `caveat` field naming the construct: "Candidate pattern fired; primary detector did not. Reader judges whether this sentence substantively covers the dimension."

### 11.2 What makes this novel

No prior structural-framing tool ships per-sentence attribution paired with candidate-miss surfacing in a deterministic, zero-LLM, real-time API. Media Frames Corpus provides sentence-level annotations but as human-labeled corpus, not live detection. FrameAxis quantifies documents along axes but does not attribute to sentences. LIWC counts words without sentence attribution. The combination, with candidate-miss as the construct-honesty-operationalized feature, is Frame Check's frontier territory.

### 11.3 Empirical measurement of the Phase A addition

| Document size | Pre-Phase-A cov_v2 | Post-Phase-A cov_v2 | Delta | Total payload post-Phase-A |
|---------------|-------------------:|--------------------:|------:|---------------------------:|
| short 200w | 3,671 B | 4,541 B | +870 B (+24%) | 16,469 B |
| medium 600w repetition | 3,708 B | 17,695 B | +13,987 B (+377%) | 32,225 B |

Observations:
- Short-document growth is modest (+24%); typical user documents in this size range remain well under 18KB total payload.
- Repetition-heavy medium-document growth is substantial but bounded by the 20-sentence-per-dimension cap. Real documents (vs artificial repetition) rarely produce 20 distinct sentences per dimension; the cap exists for defense-in-depth.
- Absolute post-Phase-A payloads remain under 35KB even on repetition-heavy test documents. Not a concern for MCP stdio transport.

### 11.4 Test coverage

- `test_coverage_v2_sentence_attribution`: pins that detected dimensions carry `sentence_matches` with non-empty entries, dedup by sentence_index, required fields.
- `test_coverage_v2_candidate_miss_surfacing`: pins that VISITOR_AUDIT reconstruction documents produce expected candidate surfacing for causes (rationale/motivation) and trends (restructuring/diversification), with caveats attached.

All 289 tests pass (was 287 pre-Phase-A; +2 new).

### 11.5 Deferred to Phase B+ follow-ups

- Sentence attribution for voice, temporal, epistemic signals (currently coverage-only). Follows the MCP v3 roadmap.
- Counter-frame generation per FVS entry using a deterministic template library.
- FVS co-activation empirical graph on validation-study corpus.

---

---

## 12. Phase B extension shipped 2026-04-20: voice + temporal construct exposure

Natural follow-up to Phase A. Phase A shipped construct-honesty treatment for the three presence/absence signals (coverage, epistemic, claims) using the under-detection construct. Phase B extends construct-honesty treatment to the two categorical / distributional signals (voice, temporal) using different constructs that fit those signal types.

### 12.1 Voice: classification-confidence construct

Voice is a 7-rule deterministic cascade emitting one of {prescriptive, promotional, descriptive, advisory, analytical}. The Fix A under-detection construct does not apply: every document is classified; there is no `not_detected` state. The analogous construct-honesty posture is classification-confidence.

**Data fields added to the v2 voice payload:**

- `margin_to_threshold` (float): the BEST margin across firing rules for the winning class. Positive values indicate decisive crossing; near-zero values indicate borderline activation. Units are percentage-points with `imperative_count` distances scaled by IMP_TO_PCT=5.
- `runner_up` (string or null): the next cascade class (different from winner) whose rule would be evaluated if the winner's rule had not fired.
- `runner_up_margin` (float or null): that class's best rule margin. Positive means its rule fires too (preempted by cascade); negative means it missed activation by that much.
- `confidence` (enum: `high`, `borderline`, `insufficient`): borderline when winner margin < 2 OR runner_up margin > -2. Either condition means a small feature change could flip the classification.

**First-class `construct` sub-block** parallels coverage_v2's construct block:

```json
"construct": {
    "signal_type": "cascade_classification",
    "statement": "Voice classification is a 7-rule deterministic cascade. ...",
    "reference": "https://frame.clarethium.com/corpus/methodology/",
    "how_to_serialize": "When restating... say 'classified as X' rather than 'the document is X.' When confidence is 'borderline', name the runner-up class explicitly..."
}
```

The `how_to_serialize` field is load-bearing: agent frameworks that restate the classification verbatim produce "the document is prescriptive" even when confidence is borderline; the serialize guidance explicitly prohibits that restatement on borderline cases.

### 12.2 Temporal: distribution-with-dominant construct

Temporal orientation is a 3-tense distribution (past/present/future) summing to ~100%. The `dominant` field picks the highest-percentage tense, which can mislead when the distribution is near-tied (e.g., past=38, present=35, future=27 reads "past-dominant" but is actually balanced).

**Data fields added to the v2 temporal payload:**

- `dominant_margin` (int): dominant_pct minus runner-up_pct. Large = genuinely time-anchored; small = narrowly won.
- `balanced` (bool): True when no tense reaches 50% AND dominant_margin < 10 points. Flags distributions where the dominant label should NOT be read as time-anchoring.

**First-class `construct` sub-block:**

```json
"construct": {
    "signal_type": "distribution_with_dominant",
    "statement": "Temporal orientation is the distribution of past, present, and future tense markers. ...",
    "reference": "...",
    "how_to_serialize": "When balanced is True, say 'temporally balanced; no tense dominates' rather than restating the dominant label..."
}
```

### 12.3 Implementation summary

- **Helpers added:** `mcp_server.py::_build_voice_construct(voice)` and `_build_temporal_construct(temp)` build the construct sub-blocks from the detect_voice / temporal_orientation output dicts.
- **Wired in:** `build_epistemic_payload` (frame_check tool) and `_summarize_per_document` (frame_compare tool). Both single-doc and compare paths expose the Phase B construct fields.
- **Tests added:** `test_mcp_voice_carries_classification_confidence_construct` and `test_mcp_temporal_carries_distribution_construct` in test_mcp_server.py pin: data field presence, construct block shape, signal_type enum, how_to_serialize content (must name borderline/runner-up for voice; balanced/margin for temporal).

### 12.4 Signal-by-signal construct summary

The five analytical signals now carry construct-honesty treatment with per-signal posture:

| Signal | Construct | v2 shape |
|--------|-----------|----------|
| Coverage | under-detection | `coverage_v2.dimensions[cat]` with status, markers_matched, candidate_sentences, first-class construct block |
| Epistemic | under-detection | `epistemic.candidate_attribution_sentences` + caveat notes |
| Claims | under-detection | `claims_extracted.candidate_hedge_count` + per-claim candidate_hedge_marker |
| Voice | classification-confidence | `voice.{confidence, margin_to_threshold, runner_up, runner_up_margin, construct}` |
| Temporal | distribution-with-dominant | `temporal.{dominant_margin, balanced, construct}` |

The first three share the under-detection construct (vocabulary-based signals with regex-null failure modes). The last two have per-signal constructs that fit their signal shapes (cascade classification; distribution). All five expose a first-class construct sub-block with signal_type / statement / reference / how_to_serialize, so agent framework serializers have consistent guidance regardless of which signal they are restating.

This completes the Phase B work outlined in METHODOLOGY_PAPER_OUTLINE_v1.md §4 and closes the final contract-level gap in the construct-honesty posture across all five analytical signals.

---

*v1. 2026-04-19. Proposal by collaborating agent. Curator review required before implementation. On approval: implementation estimate 2-3 focused days plus test additions. Section 10 empirical measurements appended 2026-04-20 post-implementation. Section 11 Phase A (sentence attribution + candidate-miss surfacing) shipped 2026-04-20. Section 12 Phase B (voice + temporal construct exposure) shipped 2026-04-20.*
