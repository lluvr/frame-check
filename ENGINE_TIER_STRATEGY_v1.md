# Engine Tier Strategy v1: V1 Baseline + V4.2 Divergence, Cost-Efficient Publication

**Status:** synthesis proposal v1, 2026-04-23. Options enumeration. Specific recommendations landed in `ENGINE_TIER_RECOMMENDATIONS_v1.md` (revised 2026-04-23 afternoon after operator stress-test; notably, Decision II below resolved as "enhance existing `frame_check`, no separate tool"). Companion to `FRAME_DIVERGENCE_v1.md` (operator's Part 1 of 4, strategic anchor), `fvs_eval/v4/MODEL_PANEL.md` (fast-tier panel pinning), and `fvs_eval/v4/V4_2_DECISION_OPTIONS.md` (options A/B/C cost-performance table). This document does NOT preempt the operator-owned Parts 2-4 of FRAME_DIVERGENCE or decide V4.2 architecture; it pulls the strategic pieces into one reviewable synthesis addressing the operator-posed question "how do we publish V4 without it becoming a cost bottleneck" and names the remaining decisions.
**Author:** collaborating agent (under curator review).

---

## 1. The tension the user named

V1 is a zero-LLM-cost rule-based detector, designed for cost-efficient public deployment (MCP `analysis_cost_usd == 0.0` contract). V4 is more robust under cross-family reliability validation but requires LLM-judge calls per detection. Publishing V4 as the default engine would either (a) force a cost-per-request model onto public users, (b) force quota/premium gating, or (c) expose Frame Check to runaway API spend. Any of those collapses the "free, demonstration tool" posture STRATEGY §2 describes.

User's directive: find a way to publish V4 that preserves cost-efficient public access AND aligns with library, canon, empire compounding.

---

## 2. Why the tension is already half-resolved

Three operator moves in the last 48 hours quietly reframed the question before it was fully asked.

**Move 1: D1 Path C (commit `928a447`) removed `confidence_level` from V4.1 output.** This simplified the V4 stack, eliminated a construct-misnamed field, and narrowed the surface area that had to be defended in any public release.

**Move 2: MODEL_PANEL.md pinned a fast-tier panel (commit `6d182c0`).** Claude Haiku 4.5, Gemini 3.1 Flash Lite, Grok 4.1 Fast, GPT-5.4 Mini. The panel comment is explicit: "evaluation panel mirrors web production (`grok-4-1-fast-non-reasoning`) so evaluation metrics directly inform production behavior." Translation: V4.2 web production target is Grok-4.1 Fast single-family. The cost question was answered by model-tier choice, not engine architecture.

**Move 3: FRAME_DIVERGENCE_v1 elevated frame divergence as the new product category.** V4.2 is no longer "a better detector" but "the measurement primitive under frame divergence." The category claim (§3 of divergence spec) is that divergence is the AGI-era primitive whose value grows as synthesis commoditizes. V4.2's cost justification shifts from "V4 detects slightly better than V1" to "V4.2 powers a product category no competitor has first-authored."

Combined, these three moves produce an emerging architecture that the user may be closer to than the "still thinking" framing suggests. The remainder of this document names the emerging architecture and the decisions it still leaves open.

---

## 3. Proposed tier model (emerging from operator moves)

Three tiers, coherent with the moves above.

### Tier 0: V1 baseline (free, default, cost-efficient)

Current shipped detector. Rule-based, $0 LLM cost, deterministic, regex+signal heuristics. Stays the default for:
- Public web traffic on `frame.clarethium.com` (when resumed)
- MCP `frame_check` and `frame_compare` tool calls (no source_text)
- Demonstration use under STRATEGY §9 effect 4 (public portfolio)

V1 is the cost-efficient contract the MCP server pins via `analysis_cost_usd == 0.0`. No change here. V1 is the honest-limit of "deterministic structural framing measurement against a rule-based catalog," which is a defensible floor.

### Tier 1: V4.2 measurement engine (TWO variants with different cost boundaries)

V4.2 is NOT the default engine. It powers frame divergence (FRAME_DIVERGENCE_v1 §1.1 composition: library + V4.2 + construct-honesty) and higher-reliability detection when a user explicitly opts in. The V4.2 flow differs materially between the web product and the MCP distribution; both use "single-family" architecture but with different agents calling different models, different cost-bearers, and different rate-limit regimes.

**Tier 1 Web: single-family Grok-4.1 Fast non-reasoning (Frame Check bears the cost).**

- Web user clicks "run frame divergence" on a document analysis result
- Frame Check's web server invokes Grok-4.1 Fast as the V4.2 LLM-judge via API
- Cost-per-call is borne by Frame Check; bounded by the fast-tier model choice (materially cheaper than flagship tier per public pricing)
- Further bounded by per-IP rate limit (candidate: 3 divergence calls per IP per day, matching the existing L2 reframe pattern)
- V4.2 Option A cost-performance per V4_2_DECISION_OPTIONS.md (F1=0.765 avg on OLD panel; pending fast-tier re-validation via parallel-agent Step 4)
- Production target per MODEL_PANEL.md line 40 "web prod choice"

**Tier 1 MCP: single-family caller's model (the agent bears the cost).**

- Agent calls `frame_check(document_text)` on the MCP server (the existing tool; see ENGINE_TIER_RECOMMENDATIONS_v1 §3 Rec II revision: no separate `frame_divergence` tool; divergence is an enhancement of `frame_check`'s output)
- Frame Check's MCP server does ZERO LLM calls. It returns V1 detection + relevant FVS library entries + detection evidence + an optional `divergence` block (absent-frames + domain-relevance filter + faithfulness notes) + `agent_guidance.how_to_render_divergence` text instructing the caller's model to complete the V4.2 judge composition
- The caller's agent (Claude Desktop's Claude, Cursor's configured model, any MCP-compatible client with a configured LLM) executes the V4.2 judge step using its own model
- Cost to Frame Check: $0. The `analysis_cost_usd == 0.0` MCP contract stays true
- Cost to caller: whatever their model's per-call cost is; that's their framework's budget, not Frame Check's
- Single-family by construction: the caller's agent is typically one model per session; multi-family consensus is structurally impossible on MCP side and would require coordinated multi-agent flows the MCP contract does not specify

This split is the core cost-containment mechanism. Web uses a fast-tier model Frame Check can afford at scale; MCP delegates entirely to the caller. Both are single-family. Neither exposes Frame Check to cost-per-request scaling risk.

### Tier 2: Multi-family consensus (research-only, not production)

V4.2 Options B (dual-family AND) and C (3-of-3 2-of-3) per V4_2_DECISION_OPTIONS.md. Used for:
- Reliability studies (F-2026-0XX pre-registrations)
- Library revision validation (Step 4 library_v1 vs library_v2 comparison)
- Cross-family reference for divergence-output self-audit

Not exposed in production. Not packaged in `frame-check-mcp`. Maintainer-internal evaluation tool only.

---

## 4. Why this tier model answers the user's question

The tension "V4 publication as cost bottleneck" dissolves under this decomposition:

- **Public users pay nothing.** V1 continues to serve them. No change to STRATEGY §2 "perspective expander" posture.
- **V4.2 cost is bounded by opt-in.** A user who wants divergence calls Tier 1; a user who wants basic framing stays at Tier 0. Per-call cost is visible to the user at request time, not silently accrued.
- **V4.2 cost is further bounded by fast-tier model choice.** The operator already committed to this with the panel shift; Grok-4.1 Fast non-reasoning is materially cheaper than flagship tier, and V4.2 performance under this tier is being re-validated as this document is written.
- **Empire role preserved.** Frame Check remains a demonstration tool under PL1 per STRATEGY §9. V4.2's cost is operator-controlled via tier, not user-passed-through. Budget §12 envelope ($1K normal) holds as long as opt-in usage stays within expectations.

The emerging architecture is: **V4.2 is a higher-reliability opt-in mode, not a replacement for V1, and its costs are tiered to stay within the existing free-tool contract.**

---

## 5. What this leaves for the operator to decide

Five decisions not resolved by the emerging architecture. Listed in rough priority order.

### Decision I: Opt-in rendering in V1 surfaces

How does a user opt into Tier 1 (V4.2 divergence)? Options:

- **MCP only.** V4.2 exposed only via `frame-check-mcp`, not the web site. Web users stay V1-forever. Agent framework users get divergence via MCP tool call. Lowest complexity, cleanest cost story.
- **Web opt-in button.** `frame.clarethium.com` adds a "Run frame divergence" button on analysis results. Daily-rate-limited (e.g., 3 divergence calls per IP per day, same pattern as current L2 reframe). Slightly more complex, more visible, better demonstration.
- **Both.** Ship MCP first (lower variance), add web opt-in once usage signal justifies.

Cost containment argument favors MCP-only at first; demonstration argument favors web-opt-in; hybrid is probably the operator's default.

### Decision II: Frame divergence as separate MCP tool vs enhancement to `frame_check`

Frame divergence is a new operation per FRAME_DIVERGENCE_v1 §1.2. MCP contract shape (Part 2 territory, operator-owned) has two candidate shapes:

- **Separate tool:** `frame_divergence` as a new MCP tool alongside `frame_check` and `frame_compare`. Clean separation; clients opt in by name. Cost-per-call is explicit (this tool is LLM-backed, others aren't).
- **Parameter on existing tool:** `frame_check(document_text, mode="divergence")` opts into V4.2 + divergence output. Lower surface-area growth; unclear cost semantics (one tool, two costs depending on parameter).

Separate tool is probably cleaner for the cost-contract posture. Operator-owned in FRAME_DIVERGENCE Part 2.

### Decision III: MCP package content scope (Move 5 revisited)

`MCP_PACKAGE_DESIGN_v1.md` predates frame divergence and the tier model. Three candidate package scopes:

- **V1-only.** `frame-check-mcp==0.7.1` ships current V1 detector. Defers V4.2 to a future release (say 0.8.0 or 1.0.0). Simplest package, no LLM deps needed, matches "cost-efficient public" posture.
- **V1 + V4.2.** First release includes both. V4.2 call requires user-provided API keys (per family). LLM deps become optional extras. Bigger package surface from day one.
- **Staged release.** 0.7.1 ships V1-only. 1.0.0 (coincident with FRAME_DIVERGENCE Parts 2-4 landing) ships divergence. Clear narrative for external adopters.

Staged release aligns with PUBLISH HOLD still in place + Parts 2-4 still pending. Natural sequence.

### Decision IV: Publication ordering

Multiple artifacts are now ready or near-ready:
- MCP package (held pending D1 resolution; D1 now resolved, hold still in operator hand)
- Zenodo Tier B snapshot (Move 6: dataset publication)
- Tier A quarterly export (Move 7: infrastructure needed, then first export)
- Methodology paper (MCP contract + V4.2 architecture stabilization)
- FRAME_DIVERGENCE Parts 2-4 (operator-owned)
- Financial worked example (Move 9)
- ED-1 sovereignty manifesto (drafted, ratified state unverified)
- First FVS canon promotion (Move 8, curator-gated)

Ordering matters because each downstream publication gains from upstream ones landing first. One coherent sequence:

1. FRAME_DIVERGENCE Parts 2-4 land (define the product)
2. ~~Library v2 ratified~~ DONE 2026-04-23 as library_v3 (commit `9abeb3d`; adopted revisions to FVS-012/016/018, kept v1 for FVS-010, retired FVS-020 from detection)
3. V4.2 architecture decision + implementation (D2; operationalizes divergence)
4. MCP package 1.0.0 (staged release, ships divergence-complete)
5. Methodology paper v0.3.0 preprint (stabilized V4.2 + library_v3 as basis)
6. Zenodo Tier B snapshot (orthogonal; any time after Option D reshape)
7. Financial worked example (demonstration asset; any time after divergence contract lands)
8. Tier A quarterly export (once production resumes + accumulates another quarter)

Steps 6, 7, 8 parallelize. Steps 1-5 are sequential dependency-wise but 2 and 3 can overlap.

### Decision V: When does production resume

Production STOPPED 2026-04-23 per operator directive. Resume triggers are not spelled out. Candidate triggers for operator consideration:

- **Library ratified (now library_v3, done 2026-04-23) and V4.2 architecture decided (single-family Grok-4.1 Fast per V4_2_SHIP_PLAN).** Resume ships a coherent V4-integrated product.
- **FRAME_DIVERGENCE Parts 2-4 landed.** Resume with the new product category visible.
- **MCP package 1.0.0 released.** Resume coordinates with PyPI release for coherent external narrative.
- **Ad-hoc.** Resume whenever operator wants; decouple from V4 landing.

Operator-owned; each option has different signaling and compounding consequences.

---

## 6. Canon and empire alignment map

The user's directive to "align with library, ensure everything is documented, everything compounds in building an empire and creating a canon." A mapping of current assets to their empire role:

| Asset | Current state | Canon status | Empire role | STRATEGY §9 effect |
|---|---|---|---|---|
| FVS library (20 entries) | 16 published, 4 held back, 0 canon. Library_v3 ratified 2026-04-23 per commit `9abeb3d`: adopted revisions to FVS-012/016/018, kept library_v1 text for FVS-010, retired FVS-020 from detection scope | DRAFT (all entries, though library as a whole is at ratified v3 baseline) | Named catalog for frame divergence (§1.1) | 1, 2, 3 |
| Methodology paper | v0.2.0 with v0.3.0 draft pending | Pre-canon | Formal spec referenced by Expert Witness (PL2) and Due Diligence (PL4) | 3, 4 |
| Worked examples | 10 slugs shipped | Reference, not canon | Demonstration artifacts for PL1 Observability buyers | 1, 4 |
| Transmissions | ~few shipped | Research pieces, not canon | Thesis development (§9 effect 6) | 6 |
| V1 detector | Production-ready (stopped) | Stable baseline | Free-tier cost-efficient floor; MCP v0.7 surface | 2, 4 |
| V4.1 Foundation | Committed, Path C applied | Research code | Bridge to V4.2; not production target | 2 |
| V4.2 engine | Pending architecture decision + implementation | Under design | Divergence measurement primitive | 1, 2, 3 |
| Frame divergence spec | Part 1 of 4 shipped | Pre-canon | NEW product category; PL1 demonstration anchor | 1, 3, 6 |
| Evidence discipline | Institutionalized per STRATEGY §4 | Practice, not artifact | Trust moat per FRAME_DIVERGENCE §4 | 3 |
| MCP v1 contract | Production shipped, held | Canon-adjacent | First distribution channel | 2, 4 |
| MCP v2 proposal | Draft | Pre-canon | Construct-carrying upgrade | 2 |
| MCP package (Move 5) | Design doc, hold active | Pre-canon | PyPI distribution | 2, 4, 5 |
| Observatory Option D | Ratified | Canon (v2 of DATA_MOAT) | Data moat on Tier A | 2 |
| Falsification registry | 31 entries | Canon (process) | Discipline-lab evidence (effect 3) | 3 |
| Validation program | Observational-v1 active | Pre-canon | External-validation discipline | 4 |

**Observations for the user's "everything compounds" directive:**

- Effect 3 (discipline lab) is over-indexed in current assets. The V4-burst (Phase 1-2C, three pre-registered negatives in ~9 hours) is strong evidence. The public-portfolio effect 4 needs more demonstration artifacts (financial worked example Move 9 would help).
- Canon status is uniformly DRAFT or pre-canon. First canon promotion (FVS-001 via reviewer outreach Move 8) remains the unlock. Currently curator-relational + gated on production resumption (reviewers shouldn't land on a down site).
- Every V4-era asset (V4.1, V4.2, divergence spec) points to the library as the shared substrate. Library ratification was the pivotal compounding moment; done 2026-04-23 as library_v3. V4.2 now targets a stable catalog; divergence Parts 2-4 cite library_v3 (Part 2 contract in operator-active progress).

The assets COMPOUND only if the library stabilizes. That is the highest-leverage curator-relational move after Part 1-4 of frame divergence.

---

## 7. What this document explicitly does not claim

- **Does not decide V4.2 architecture (Options A/B/C).** V4_2_DECISION_OPTIONS.md is the decision doc; operator owns the choice.
- **Does not preempt FRAME_DIVERGENCE Parts 2-4.** Those are operator-owned. This document sits strategically adjacent, not within.
- **Does not choose between the three MCP package scope options in §5 Decision III.** Names the options and the alignment with the staged-release pattern; operator decides.
- **Does not quantify cost under fast-tier panel.** Per-detection cost on Grok-4.1 Fast non-reasoning requires the parallel-agent Step 4 output. Numbers land when that does.
- **Does not price tier-gating.** If V4.2 is opt-in paid, the price is operator-strategic; STRATEGY §5 durable decision defers premium. This document does not reopen that.

---

## 8. Honest limits

- **Author sits outside the operator's active workstream.** The parallel agent is executing Step 4 library revision test with fast-tier labels right now; their results may change the cost-per-detection and F1-per-option numbers that the proposed tier model relies on. This synthesis is based on pre-Step-4-completion state.
- **FRAME_DIVERGENCE_v1 is Part 1 of 4.** Parts 2-4 are operator-owned and may revise the architecture implications this document extrapolates. Most notably, Part 2 (contract) will specify MCP tool shape, which directly constrains §5 Decision II.
- **Per-detection cost on fast-tier panel is estimated, not audited.** Fast-variant models are 5-10x cheaper than flagship per public pricing, but actual V4.2 call costs depend on prompt length, output tokens, and per-family pricing; the operator should verify against actual invoices before committing to a tier model.
- **"Web production choice" in MODEL_PANEL.md is a current choice, not an irrevocable one.** `grok-4-1-fast-non-reasoning` as web production could shift if Grok-4.1 Fast regresses on subsequent evaluations or xAI pricing changes. The tier model's cost claim is as durable as the fast-tier panel.
- **Publication ordering in §5 Decision IV is dependency-logical, not operationally verified.** Real curator cadence may deviate; no claim of "this is the only valid order."
- **Canon alignment map in §6 is as of 2026-04-23 morning.** Every item is subject to change as Step 4 completes and FRAME_DIVERGENCE Parts 2-4 ship.
- **This synthesis risks being wrong about what the operator is thinking.** The user's "still thinking" language is taken at face value; the emerging architecture in §§3-4 may not match the operator's internal model. Operator review of this doc should flag any misreading.

---

## 9. Proposed next move

Produce this document (done). Operator review before anything else. Specifically:

- Confirm §3 tier model matches the emerging architecture operator has in mind.
- Confirm §5 five decisions are the right decision surface (or flag missing ones).
- Confirm §6 alignment map is accurate (or identify mislabelled assets).

If the synthesis lands as useful framing, concrete downstream agent work unlocks:

- Update `MCP_PACKAGE_DESIGN_v1.md` with the tier model and staged-release decision in §5 Decision III.
- Draft Move 9 financial worked example with frame divergence as the demonstration thesis (once FRAME_DIVERGENCE Part 2 contract stabilizes).
- Add a STRATEGY.md §14 stub naming "Engine tier strategy" with a pointer to this document, so the tier model is citeable.

If the synthesis misreads the operator's intent, discard and re-anchor.

---

*v1. 2026-04-23. Strategic synthesis proposal addressing operator's "how do we publish V4 without being a cost bottleneck" question. Non-colliding with parallel-agent Step 4 technical workstream. Companion to FRAME_DIVERGENCE_v1.md (operator Part 1), MODEL_PANEL.md (pinned panel), V4_2_DECISION_OPTIONS.md (cost-performance table). Does not preempt operator-owned strategic content. Written for operator review, not for implementation.*
