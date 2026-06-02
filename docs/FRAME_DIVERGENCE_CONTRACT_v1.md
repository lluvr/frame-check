# Frame Divergence v1, Part 2: Contract

The interface contract for the `divergence` block inside `frame_check` output. Binds interface, not implementation. Specifies the block shape, inputs that activate it, faithfulness guarantees specific to absence claims, provenance requirements, the MCP-vs-web capability regime, MCP resource URIs, error envelope, and versioning commitments.

**Status:** v1 contract `c1.0` is canonical and shipping. The contract carries forward unchanged across the v2 layered-architecture spec for backward compatibility; this document is the canonical Part 2 reference and the citation target for any caller binding to the `divergence` block.
**Author:** Lovro Lucic
**Date:** 2026-04-23 (last revised for capability-regime alignment and V4.2-alpha status disclosure).
**Citation format:** Lucic, L. (2026). *Frame Divergence v1, Part 2: Contract.* Frame Check. MCP resource URI: `frame-check://spec/frame-divergence/v1/part-2`.

---

## 1. Scope and stance

Part 2 specifies the `divergence` block that Frame Check exposes inside `frame_check` tool output and the capability regime under which divergence is composed on each surface. It binds interface, not implementation. Per Rec II, divergence is not a separate tool: it is an output-shape-plus-guidance enhancement of `frame_check`. Per Rec I, the V4.2 judge step runs server-side on web and caller-side on MCP, which means the block's provenance semantics differ per surface.

Stance: the contract is the promise that binds Frame Check's authored output discipline to what agents and thinkers actually receive when the `divergence` block appears. Everything downstream of this contract (library evolution, engine upgrades, rendering choices, caller-side composition) must honor it or trigger a contract version bump with a migration path once dependent adopters exist.

Contract version in this document: **c1.0**.

## 2. Surface: `divergence` block inside `frame_check` output

### 2.1 Enhance-existing, not new-tool

Frame divergence is surfaced as an additive `divergence` block on the `frame_check` tool response, alongside the existing `analysis` block. Per Rec II, divergence is an OUTPUT SHAPE and AGENT GUIDANCE concern, not a tool inventory concern. MCP tool surface stays at `frame_check` and `frame_compare`. Part 1 of this spec defines the category; this document defines the block shape.

### 2.2 When the block is present

The `divergence` block is present on a `frame_check` response when:
- The caller requested divergence explicitly via an input flag (§3.1), AND
- Raw material for composition exists (library resources reachable, detection evidence available).

Surface defaults for `include_divergence`: MCP defaults `true` (the divergence block is the headline capability; see §3.1 for the launch decision); web defaults `false` pending web V4.2 server-side implementation (Rec IV Pillar 2).

When absent, the `frame_check` response carries only the `analysis` block and `agent_guidance` (pre-existing fields). v1-contract consumers that ignore unknown fields absorb this as additive.

**Implementation status:** MCP-side implementation shipped commit `d735571` (2026-04-23 afternoon). `frame_check` accepts `include_divergence`, `domain_hint`, `divergence_rendering`, and `catalog_version_pin` inputs per §3 and emits the full `divergence` block per §4 with the MCP caller-side execution semantics per §7.1. Stimulus composition harness for Track B informal study shipped `d2de4dd` as a CLI reference implementation of §7.2 web-surface mode. Web-surface server-side V4.2 integration (Rec IV Pillar 2) pending production resume per Rec V.

### 2.3 Reserved operation names

Three names are reserved in the tool namespace and MUST NOT be used for other purposes in v1 implementations. Reservation prevents copycats or parallel implementations from claiming them before Frame Check ships them if scope expands:
- `frame_inventory` (reserved): catalog-usage fingerprint across a corpus of documents (future-extension).
- `frame_gap` (reserved): decision-level blind-spot surfacing across a structured decision record rather than a single document (deferred).
- `frame_divergence` (reserved, superseded): the rejected separate-tool shape from an earlier draft. Reserved to prevent future fragmentation of the category.

## 3. Inputs to `frame_check` that activate or shape the divergence block

This document specifies the divergence-related inputs. Existing `frame_check` inputs (e.g., `document_text`, `source_text`) are unchanged by this contract.

### 3.1 `include_divergence` (optional, boolean)

Default-on flag. When `true` (default), the divergence block is present in the response subject to §2.2 conditions. When `false` (explicit opt-out), no divergence block. Surface defaults as shipped in `frame-check-mcp` 0.8.0 onward:
- **MCP:** default `true` (revised from the earlier draft `false`). Caller's agent already invokes its own LLM for downstream rendering; the divergence block adds caller-side V4.2 capability via `agent_guidance.how_to_render_divergence` without invoking any Frame Check LLM (zero per-call cost, vendor independence by construction). Callers that want the pre-divergence response shape pass `include_divergence=false`. The default flip from `false` to `true` happened at the 0.8.0 launch decision (commit `2e83fec` / `94ad5fe`); rationale: the V4.2-first launch commitment makes the divergence block the first-class surface, not an opt-in. The earlier `false` default in this contract draft is preserved in git history; the shipped wheel is the canonical reference and this section is its spec.
- **Web:** default `true` rate-limited (rate-limit per IP per day per Rec I; consult web app `security.DailyFeatureLimit` for the active cap).

### 3.2 `domain_hint` (optional, enumerated string)

Hint about the document's domain, used to filter absent frames for domain relevance per Part 1 §5.1.6. Valid values drawn from FVS entry metadata. If omitted, the server infers domain from document features or returns absent frames without domain filtering (envelope flags the unfiltered mode).

Initial enumerated values: `finance`, `founder_decision`, `investment_research`, `product_announcement`, `policy`, `health_biomedical`, `tech_science`, `humanities`, `general`. Additions are additive contract changes (minor version bump).

### 3.3 `divergence_rendering` (optional, enumerated string, default `list`)

How the consumer wants absent-frame records structured. Affects decoration of each record; envelope is always present regardless.

Valid values:
- `list` (default): flat list of absent-frame records with citations. Agent-friendly and compose-friendly.
- `completeness_check`: list rendered as a checklist with domain-relevance rationale per item. Professional-thinker-friendly.
- `teaching_questions`: each absent frame rendered with an attached teaching question drawn from the FVS entry. Pedagogical-friendly.
- `narrative`: single prose paragraph naming the absent frames in sequence with citations inline. Publication-friendly.

### 3.4 `catalog_version_pin` (optional, string)

Pin the FVS catalog version. If omitted, the latest stable catalog version is used (currently `library_v3`). Provisional entries (per Part 1 §5.1.4) are included regardless of pin, flagged accordingly.

### 3.5 Input validation

All inputs validated per existing MCP adversarial-hardening protocol (MCP_SERVER.md adversarial test suite). Wrong types, over-limits, malformed enums return structured errors per §9. Input validation does not degrade silently.

## 4. Output: the `divergence` block shape

### 4.1 Position within `frame_check` response

The `frame_check` response gains an optional top-level field named `divergence` alongside the existing `analysis`, `agent_guidance`, and `provenance` fields. When present, `divergence` is an object with the fields specified in §§4.2-4.4.

### 4.2 `absent_frames` (array of `AbsentFrameRecord`)

Required when `divergence` is present. Each `AbsentFrameRecord`:

Required fields:
- `frame_id`: FVS entry ID (e.g., `FVS-007`).
- `frame_version`: version of the entry as of this invocation (e.g., `v1.0` from library_v3).
- `frame_title`: human-readable title (e.g., `Risk Frame`).
- `stability`: enum `stable` or `provisional`. Provisional values carry curator-review-in-progress semantics per Part 1 §5.1.4.
- `citation_uri`: MCP resource URI pointing to the FVS entry (see §8).
- `absence_basis`: brief machine-readable rationale for absence. On web (V4.2 server-side), this is the judge's rationale. On MCP, this is a scaffolding string describing what the caller's model should verify (e.g., `"Caller's model must confirm no FVS-007 identification cues fired; V1 rule-based check returned no match."`). Not prescriptive.
- `domain_relevance_rationale`: brief rationale for why this absent frame is surfaced for the inferred or hinted domain. Example: `"Risk framing is domain-standard for financial forecasts per FVS-007 applicability metadata."`

Optional (rendering-dependent):
- `teaching_question`: present only when `divergence_rendering = teaching_questions`, drawn from the FVS entry. Omitted for `list`, `completeness_check`, and `narrative` modes.
- `reliability_signal`: present only on web responses where V4.2 ran server-side and a valid calibration measure exists. Per Part 1 §5.1.3, no inverted-precision field ships. Absence of this field is the safe default.

Forbidden:
- `prescription`, `recommendation`, `should_use`, or any field naming the absent frame as something the thinker should have used. Enforcing Part 1 §5.1.5.

### 4.3 `envelope` (`FaithfulnessEnvelope`)

Always present when divergence is present. Machine-parseable. Contains the disclosures that make divergence output trustworthy rather than decorative.

Required:
- `spec_version`: the version of this spec honored by the response (`FRAME_DIVERGENCE_v1_c1.0`).
- `catalog_version`: FVS catalog version used (e.g., `library_v3`).
- `surface`: enum `mcp` or `web`. Reports which channel produced the response.
- `v4_2_execution`: object describing where and how the V4.2 judge step ran.
  - On web: `{"location": "server_side", "tier": "single_validator_v4_2_latest", "architecture": "single_family_single_judge", "vendor": "xai/grok-4-1-fast-non-reasoning", "model_version": "<served>", "fallback_triggered": <bool>, "fallback_reason": <str|null>}`.
  - On MCP: `{"location": "caller_side", "tier": "caller_model", "note": "V4.2 judge step delegated to caller's agent model per Rec I. Frame Check's MCP server does not invoke an external LLM. See agent_guidance.how_to_render_divergence for composition instructions."}`.
- `v4_2_engine_status`: enum `alpha` | `beta` | `production_candidate` | `production`. Reports the production-readiness of the V4.2 detection layer at invocation time. Consumers that gate on stability bind against this enum.
- `domain_inferred`: actual domain used for filtering. May differ from `domain_hint` if hint was incompatible with document features; discrepancy flagged.
- `provisional_count`: number of absent-frame records flagged provisional. Lets consumers surface a caveat without parsing every record.
- `faithfulness_note`: canonical disclosure string, non-prescriptive. For v1 c1.0: `"Absent frames are named from the FVS catalog as not detected in the supplied document. Domain relevance is the tool's best judgment. Whether any absent frame is useful is the thinker's call. This is not a list of frames that should have been used."`
- `limitations`: array of any limitations specific to this invocation (e.g., `"V4.2 caller-side composition: absence_basis fields are scaffolding for caller's model; caller's model determines final absence verdict."`).

Optional:
- `telemetry_opt_in_hash`: present only if consumer opted into anonymous structural telemetry at invocation (future Tier A wiring). Absent by default.

### 4.4 `agent_guidance` additions (required for divergence block)

When the `divergence` block is present, the existing `agent_guidance` field on `frame_check` output MUST carry two additional keys:

- `how_to_render_divergence`: explicit instructions for the caller's model (MCP) or Frame Check's renderer (web) to complete the composition with faithfulness guarantees. Includes: preferred rendering per `divergence_rendering`, citation format, non-prescriptive language requirements, and the V4.2 judge prompt scaffolding (MCP only).
- `absence_is_not_prescription`: the Part 1 §5.1.5 guarantee language verbatim: `"Divergence output never implies the user should have used the absent frames. The tool surfaces absence, the thinker decides relevance."`

### 4.5 Non-prescriptive rendering requirement

Regardless of `divergence_rendering`, all human-facing text in the response MUST refer to absent frames as "absent from the document" or "not detected in the current framing," never as "missing frames you should consider" or equivalent prescriptive phrasing. This is enforced at the contract layer, not left to prompt engineering. Applies to both web-rendered text and MCP `agent_guidance` instructions given to caller's model.

## 5. Faithfulness guarantees specific to absence claims

Divergence faithfulness is not the same as detection faithfulness. Detection faithfulness = we do not overclaim presence. Divergence faithfulness = we do not overclaim absence, do not prescribe, do not fabricate catalog entries, do not infer relevance beyond evidence. Five guarantees:

### 5.1 "Absent" is operationally defined, and the definition differs per surface

"Absent" means: the detection step (web: V4.2 server-side; MCP: caller's model informed by V1 + library resources + agent_guidance) did not detect the frame in the document, at the configured tier for that surface. An absent frame is not claimed as cognitively missing from the thinker's reasoning, only as not present in the supplied text under the detection applied. The `absence_basis` field per §4.2 carries the operational basis.

### 5.2 Citation enforcement

Every absent-frame record carries a resolvable `citation_uri` to the FVS entry. Absent frames without a resolvable citation are not surfaced. No exceptions.

### 5.3 Provisional flagging

Under the current `library_v3` catalog: FVS-012/016/018 revised and stable; FVS-010 retains earlier text, stable with `honest_limit` disclosure; FVS-020 retired from detection and never appears in divergence output; no frames currently flagged provisional. The `stability: stable | provisional` enum on `AbsentFrameRecord` and the mandatory-flagging protocol are retained in this contract for future revisions. If a later library version reopens a frame for review, divergence output surfaces that record with `stability: provisional` and consumers can filter at parse time.

### 5.4 Calibration honesty

Per Part 1 §5.1.3, no inverted-precision field ships. The `confidence_level` field is intentionally absent. Per-entry reliability is reported via two distinct constructs: `library_v3_consensus_ac1` (library-entry-level, cross-family inter-rater agreement) and `detector_intra_rater_ac1` (single-family detection consistency at temperature zero). The `reliability_signal` field on absent-frame records is scoped narrowly to contexts where valid calibration exists; omitted by default.

### 5.5 No fabrication beyond catalog

The tool never surfaces a named frame that does not correspond to an authored FVS entry. Emergent-pattern suggestions (frames the engine "sensed" that are not in the catalog) are explicitly out of scope for divergence. If the engine detects a novel pattern, the appropriate surface is a library proposal, not a divergence suggestion.

## 6. Provenance requirements

Every `divergence` block response carries provenance sufficient for the consumer to reproduce, audit, or cite the result.

### 6.1 V4.2 engine provenance

Per `envelope.v4_2_execution` in §4.3. Key invariant: the envelope always reports where the V4.2 judge ran (server-side on web; caller-side on MCP). This is the load-bearing disclosure that distinguishes the two surfaces.

On web, the envelope carries model version (e.g., `xai/grok-4-1-fast-non-reasoning-2026-03`), architecture tier, and fallback state. V4.2 server-side status uses the `alpha` | `beta` | `production_candidate` | `production` enum to communicate engine readiness; the value upgrades as the underlying detection layer matures.

On MCP, the envelope explicitly notes the caller-side execution model. Caller's agent is responsible for naming its own model in its downstream report; Frame Check cannot observe caller's model choice and does not claim to. Vendor-independence per Part 1 §5.2.1 is automatically preserved on MCP because the caller chooses the model.

### 6.2 Catalog provenance

In `envelope.catalog_version` (catalog-wide) and per-record `frame_version` (per-entry). Catalog-wide version is a semver pin (currently `library_v3`). Per-entry versions allow tracking revisions to specific entries.

### 6.3 Spec provenance

In `envelope.spec_version` (`FRAME_DIVERGENCE_v1_c1.0` for this contract).

### 6.4 V4.2 engine status

In `envelope.v4_2_engine_status`. Consumers see the engine's production-readiness state at invocation time. The enum (`alpha` | `beta` | `production_candidate` | `production`) is the load-bearing surface; downstream consumers gate on it directly.

### 6.5 Invocation context

Response also includes:
- `request_id`: unique per invocation, carried in error envelope for traceability.
- `invocation_timestamp`: UTC ISO-8601.

## 7. MCP-vs-web capability regime

This operationalizes Rec I. The two surfaces run divergence under different cost and model wiring, but honor the same contract specified in §§3-6.

### 7.1 MCP: raw material + agent guidance, zero Frame Check LLM cost

On MCP, `frame_check` returns:
- V1 rule-based detection (the pre-existing `analysis` block, zero LLM cost).
- Library resources accessible via `frame-check://library/FVS-XXX` (see §8).
- Detection evidence (what signals fired, where).
- `divergence` block when `include_divergence=true`: includes `absent_frames` with `absence_basis` as scaffolding (caller's model completes the verdict), plus `agent_guidance.how_to_render_divergence` carrying V4.2 judge prompt scaffolding, plus `agent_guidance.absence_is_not_prescription` verbatim.

Frame Check's MCP server does not invoke an external LLM. The `analysis_cost_usd == 0.0` MCP contract holds. The caller's agent (Claude Desktop's Claude, Cursor's configured model, etc.) performs the V4.2 judge step using its own model and bears the LLM cost.

MCP surface default for `include_divergence`: `true` per §3.1 (the divergence block is the headline capability; callers wanting the pre-divergence response shape pass `include_divergence=false` explicitly). No rate limit from Frame Check.

### 7.2 Web: server-side V4.2, rate-limited, cost-bounded

On web, the divergence UI action promotes `frame_check` to V4.2-mode, in which Frame Check invokes `grok-4-1-fast-non-reasoning` server-side as the single-family judge. Frame Check bears the LLM cost; fast-tier model choice plus rate limiting (candidate: 3 V4.2 calls per IP per day) bound the per-IP exposure.

Web surface default for `include_divergence`: `false`. V1 detection is the default; V4.2-mode + divergence is a user-triggered action on the results page.

### 7.3 Same faithfulness contract, different cost bearer

Both surfaces honor the contract specified in §§3-6 of this document. The `divergence` block's shape, the faithfulness guarantees, the provenance structure, the error envelope, and the versioning commitments apply uniformly. The differences are structural: who invokes the V4.2 judge, who bears LLM cost, and how the envelope reports execution location.

### 7.4 Strategic value

The capability-per-channel split is the resolution to the "how to publish V4 without being a cost bottleneck" question that motivated ENGINE_TIER_STRATEGY_v1. Three properties compound:

1. **Cost bottleneck dissolves.** MCP delegates LLM work to caller (zero FC cost); web runs V4.2 behind rate limits within budget. Neither surface exposes Frame Check to scaling risk.
2. **Vendor independence is automatic on MCP.** Caller chooses their model; Frame Check makes no vendor commitment on MCP. Web commits to Grok-4.1 Fast as current single-validator with MODEL_PANEL re-validation trigger protocol as the drift-management mechanism.
3. **Category claim lives in canon, not in tool inventory.** Per Rec II, divergence is an output-shape enhancement on `frame_check`, citable through methodology + FVS library + Parts 1-4 of this spec. Future products (Vaurith, Proposal Check, other agent frameworks) call `frame_check` and render divergence from its output; no tool proliferation.

## 8. MCP resource URIs

URI scheme: `frame-check://`. This is the canonical Frame Check MCP resource scheme, established in mcp_server.py v0.6.0 and documented in MCP_SERVER.md. This contract extends the scheme with new paths for spec, versioned library, versioned methodology, and provenance resources; existing paths are unchanged and remain valid. Scheme and path grammar at c1.0 are additive to the established convention.

Notation: resources listed below that already exist in mcp_server.py are marked (existing); resources introduced by this contract are marked (new). Path grammar follows the established `frame-check://{resource_type}/{id}[/{subresource}]` convention.

### 8.1 Spec resources (new)

- `frame-check://spec/frame-divergence/v1` -> spec index for v1 (lists parts 1-4 with present/pending status).
- `frame-check://spec/frame-divergence/v1/part-1` -> Part 1 of this spec (category and non-negotiables).
- `frame-check://spec/frame-divergence/v1/part-2` -> this document (contract).

### 8.2 Library resources

- `frame-check://library` -> full catalog index (existing).
- `frame-check://library/FVS-XXX` -> current version of entry FVS-XXX (existing; e.g., `frame-check://library/FVS-007`).
- `frame-check://library/FVS-XXX/v/{version}` -> specific version of entry FVS-XXX (new; enables version-pinning per §3.4).

### 8.3 Methodology resource

- `frame-check://methodology` -> current methodology version (existing).
### 8.4 Provenance resources (new)

- `frame-check://provenance/engine/{version}` -> engine version manifest (tier, architecture, vendor(s), model version(s), engine status label, validation records).
- `frame-check://provenance/catalog/{version}` -> catalog version manifest (library version, per-entry version map, ratification references).

### 8.5 Necessary steps to operationalize the new paths

The `frame-check://` scheme itself is the established Frame Check MCP convention (mcp_server.py v0.6.0+, ~150 references across code/tests/docs). An initial draft of this contract proposed `framecheck://` (no hyphen); an audit on 2026-04-23 caught the drift, and this contract was corrected to align with the canonical scheme. These steps operationalize the new PATHS (spec, versioned library, versioned methodology, provenance) added by this contract on top of the existing scheme:

1. **Extend mcp_server.py resource handlers for the new paths in §§8.1-8.4.** Handlers for `frame-check://spec/frame-divergence/v1/part-{1,2}` and the spec index shipped commit `25c28f0` with traversal-safe dispatch and 5 regression tests. Library/methodology/provenance versioned-path handlers remain pending (future extension; not blocking current Track B or first-adopter flow). `frame_check` tool-surface divergence integration shipped commit `d735571` (see §2.2 implementation status).
2. **Conflict audit (complete).** Completed 2026-04-23. No external conflict with `frame-check://`. Internal conflict with the incorrect `framecheck://` draft was caught and corrected before commit.
3. **Document the new paths in MCP_SERVER.md.** Section "Frame Divergence spec" added in commit `25c28f0` listing the spec path patterns. Library/methodology/provenance versioned paths documentation remains pending.
4. **Consistency sweep across Frame Check docs.** Existing docs use `frame-check://` consistently; this document was aligned to the canonical scheme in the same commit.
5. **Announce the new paths.** Publish hold lifted 2026-04-27; `frame-check-mcp` 0.8.0/0.8.1/0.8.2 shipped on PyPI. Path-list announcement in MCP_SERVER.md is the announcement vehicle (the spec resource handlers ship with each release).
6. **Include path coverage in package metadata.** Path coverage is wheel-resident (mcp_server.py resource handlers shipped per step 1); package-metadata path enumeration in pyproject.toml description is a future-extension polish item, not blocking.

Steps 1-4 are complete or partially complete (spec-paths shipped; versioned library/methodology/provenance paths are additive future extensions). Steps 5-6 transitioned post-publish-hold-lift to ongoing maintenance items.

### 8.6 URI stability

URI scheme and path grammar at c1.0 are stable per §10 adoption-driven commitments. Breaking scheme or path changes require a contract version bump with a deprecation window once dependent adopters exist.

## 9. Error envelope

When the divergence block cannot be composed, the response returns the `frame_check` response WITHOUT the `divergence` block, and the `envelope.limitations` field on `analysis` block carries a structured reason. This degrades gracefully: `analysis` still returns; divergence absence is disclosed, not silent.

Structural errors (invalid inputs, traversal attempts on resource URIs) continue to return the existing `frame_check` error envelope.

### 9.1 Divergence-specific failure reasons

Reported in `envelope.limitations` when divergence requested but not composed:
- `DIVERGENCE_CATALOG_UNAVAILABLE`: catalog resources not reachable on this deploy.
- `DIVERGENCE_ENGINE_UNAVAILABLE` (web only): V4.2 server-side judge unavailable (vendor down or deprecated). Details include vendor/model pair that failed. Per Part 1 §5.2.1, divergence never silently becomes "what one vendor thinks you missed."
- `DIVERGENCE_RATE_LIMITED` (web only): caller exceeded rate limit; absence disclosed with retry-after.
- `DIVERGENCE_CALLER_MODEL_MISSING` (MCP only): caller's agent signaled no model available for composition; MCP server cannot complete on caller's behalf.

### 9.2 Structural errors

Existing `frame_check` input validation (document size, type correctness, enum validity per MCP_SERVER.md adversarial test suite) returns the existing structured error envelope. Divergence-specific inputs per §3 integrate into this validation.

## 10. Versioning and stability

### 10.1 Contract version c1.0 (pre-adoption)

The contract specified in this document is c1.0. Current status: pre-adoption (no dependent external consumer integrates against the divergence block in production as of publication).

### 10.2 Stability commitments emerge from adoption, not from publication date

Binding stability commitments kick in upon first dependent adopter, not upon spec publication. Before that, the contract can evolve freely with changelog disclosure. This prevents premature lock-in against an interface that may need revision during pre-adoption iteration; the posture is open by design, with no artificial urgency.

Specifically:
- **Pre-adoption (current state).** Contract changes possible with a changelog entry. No deprecation window required. The contract is subject to change as the product matures and as Parts 3-4 of the spec land.
- **Post-first-adopter.** Breaking changes trigger the deprecation protocol in §10.4. Contract version bumps to c2.0 on the first breaking change after a dependent adopter exists.

### 10.3 Change classification

- **Additive** (backward-compatible): new optional fields on `AbsentFrameRecord` or `FaithfulnessEnvelope`, new `divergence_rendering` values, new error reasons, new enumerated `domain_hint` values, new resource URIs under the existing scheme, upgrading the V4.2 production pin per MODEL_PANEL updates. Minor version bump (c1.1, c1.2, ...).
- **Breaking**: removed or renamed fields, changed field semantics, changed URI scheme, changed error code semantics, change to non-prescriptive-rendering requirement in §4.5, change to MCP caller-side execution model, change to web server-side execution model. Major version bump (c2.0).

### 10.4 Deprecation protocol (post-first-adopter)

Before any breaking change, after a dependent adopter exists:
- Deprecation notice in `envelope.limitations` for minimum 90 days before removal.
- Migration guide published as a sibling document in the spec tree.
- Both old and new behaviors supported during the deprecation window.
- Notice also published in the public changelog and, if the adopter is known, directly communicated.

Deprecation windows scale up if the adopter base grows: 90 days is the floor, not a cap.

### 10.5 Spec vs contract versioning

This document version (v1) and contract version (c1.0) evolve independently. Part 1 of the spec can bump to v2 (category redefinition) without forcing a contract bump if the contract is still honored. Contract can bump to c2.0 (interface break) without forcing a spec v2 if the category definition is unchanged.

### 10.6 Tracking first dependent adopter

First dependent adopter status is recorded in a separate adoption-log document when established (proposed: FRAME_DIVERGENCE_ADOPTION_LOG.md). Until that log contains a first entry, this contract is pre-adoption and §10.2 applies. The adoption log is also the audit trail for the predictions in Part 1 §7 (P2: agent framework integration within 12 months of MCP publish resumption).

### 10.7 MCP package release arc

Per Rec III, this contract lands on PyPI in MCP package release 0.8.0 (divergence-capable, additive to v1 frame_check shape). 0.7.1 ships before contract lands (name reservation, V1-only). 1.0.0 ships after adopting MCP_CONTRACT_V2_PROPOSAL's construct-carrying shape for `frame_check` output (API freeze). Spec resource handlers in mcp_server.py (§8.1) landed additively on the 0.7.1 track (no version bump); 0.8.0 adds the `divergence` block itself.

## 11. What Part 2 does not specify

Deferred to Part 3 (V4.2 integration):
- Per-architecture behavior details: how each V4.2 tier (single-family Grok-4.1 Fast current, multi-family consensus research-only) is realized under the hood, including the enumerated values for web `v4_2_execution.architecture`.
- Fallback order specifics under vendor-specific failures.
- Cost model per web V4.2 call under current pricing.
- Caller-side V4.2 judge prompt scaffolding (the specific content of `agent_guidance.how_to_render_divergence` on MCP).

Deferred to Part 4 (self-red-team + competitive map):
- Self-red-team of the contract (what breaks under copycat, engine failure, catalog drift, no adoption, peer-authored-catalog scenarios, caller-side adversarial composition).
- Competitive map of adjacent operations (structured brainstorming APIs, cognitive bias checklists, red-teaming frameworks, decision-quality tools).

## 12. Extension pattern: future categories beyond frame divergence

Frame divergence is one instance of a more general primitive: catalog-driven perspective absence with faithfulness constraints. The catalog can be the FVS frames as in c1.0, but the same shape generalizes to other categories of perspective expansion that an AGI-era thinker may want surfaced from a document. Active research directions name several candidate categories: scenario divergence (scenarios the document does not consider), persona divergence (decision-makers or readers the document does not address), constraint divergence (boundary conditions absent from the analysis), timeframe divergence (temporal horizons the document does not cover), cultural-lens divergence (framings outside the document's implicit cultural register), regulatory-regime divergence (compliance contexts the document does not name), stakeholder-position divergence (who-wins-and-loses asymmetries left implicit). Other categories will be authored as research surfaces them.

This section reserves the architectural namespace for those future categories without committing to any specific category at c1.0. The contract design discipline is additive sibling fields under the existing `divergence` block:

- `divergence.absent_frames` ships at c1.0 (frame category, library_v3 catalog).
- `divergence.absent_scenarios` may ship at a future contract minor version when a scenario catalog and faithfulness envelope are authored. Same record shape: each entry carries a stable `scenario_id`, `citation_uri` to a scenario-library entry, `absence_basis` scaffolding for the caller's model, `domain_relevance_rationale`. The category-specific catalog version pins to the relevant catalog (e.g., `scenario_library_v1`) with the same library-versioning discipline this contract applies to FVS.
- `divergence.absent_personas`, `divergence.absent_constraints`, `divergence.absent_timeframes`, etc., follow the same additive sibling-field pattern.

Three invariants govern any future category addition:

1. **Additive, not breaking.** A new category MUST land as a new sibling field (`absent_X`) under the existing `divergence` block. The category MUST NOT change the shape or semantics of `absent_frames`. A v1-contract consumer who reads only `absent_frames` continues to work unchanged when new categories ship.
2. **Same faithfulness contract.** Each new category's records carry `citation_uri`, `absence_basis`, and `domain_relevance_rationale` with the same discipline as `absent_frames`. The `agent_guidance.absence_is_not_prescription` guarantee extends category-wide: no surfaced absence in any category implies the user should have used it. The `how_to_render_divergence` guidance is updated additively to instruct the caller's model on per-category rendering when the category is enabled.
3. **Catalog-traceable.** Every absent record traces back to a catalog-versioned entry via `citation_uri`. The category is meaningless without a stable catalog. A new category cannot ship until its catalog is authored, versioned, and citation-resolvable.

The MCP surface adds opt-in flags per category mirroring `include_divergence`. Specifically: when c1.1 introduces (e.g.) scenario divergence, the `frame_check` parameters gain `include_scenario_divergence: bool` (default `false`) plus optional category-specific shaping parameters (analogous to `domain_hint`, `divergence_rendering`, `catalog_version_pin`). A caller who passes `include_divergence=true` and `include_scenario_divergence=true` receives both `absent_frames` and `absent_scenarios` in the same response. A caller who passes only `include_divergence=true` receives only `absent_frames` (existing c1.0 behavior, unchanged).

The reserved namespace under §2.3 (`frame_divergence`, `frame_inventory`, `frame_gap`) extends category-by-category at c1.1+ when each category is authored. Future contract revisions also reserve the analogous tool-name space (`scenario_divergence`, `persona_divergence`, etc.) per Rec II discipline: enhancement, not tool proliferation. The MCP tool surface stays at `frame_check` and `frame_compare`; new categories are output-shape extensions, not new tools.

This extension pattern is the load-bearing architectural commitment that makes `frame_check`'s `divergence` block the substrate for AGI-era multi-perspective primitives, not a single-category endpoint. The contract honors the strategic claim by reserving the architecture; specific category implementations follow when their catalogs ship.

## 13. References

- MCP server implementation: [MCP_SERVER.md](MCP_SERVER.md).
- FVS library: `data/frame_library/` (FVS-001 through FVS-020).
- Methodology: [frame.clarethium.com/corpus/methodology/](https://frame.clarethium.com/corpus/methodology/).
