# Engine Tier Recommendations v1: Five Decisions, 3/5-Year Proud-to-Own Lens

**Status:** recommendation proposal v1, 2026-04-23. Sequel to `ENGINE_TIER_STRATEGY_v1.md` (options analysis). Operator clarified the MCP vs web split (MCP's V4.2 uses the calling agent's model; Frame Check server remains zero-LLM-cost) and explicitly asked for recommendations under a 3- and 5-year empire lens, not options enumeration. This document commits to specific paths. Each recommendation names (a) the option I'd commit to, (b) 3-year proud-to-own rationale, (c) 5-year compound rationale, (d) evidence anchoring, (e) tradeoff accepted. Stress tests the recommendations for cross-cutting conflicts.
**Author:** collaborating agent (opinions explicit; operator's override stands).

---

## 1. Refined context: MCP ≠ Web

Operator clarification (2026-04-23): the MCP's V4.2 flow delegates LLM-judge work to the calling agent's own model. Frame Check's MCP server does not invoke an external LLM. Instead it returns:
- V1 structural detection (what the rule-based detector found)
- Relevant FVS library entries (the catalog)
- Detection evidence (what signals fired, where)
- `agent_guidance` text instructing the caller's model to complete the V4.2 judge step and render divergence

The agent's model (Claude Desktop's Claude, Cursor's configured model, etc.) is single-family by construction: whichever model the user has wired up. No multi-family consensus needed (and impossible from the MCP's side anyway, since it doesn't call LLMs). No cost to Frame Check regardless of how many divergence calls the agent makes.

This collapses two of my earlier framings:
- The `analysis_cost_usd == 0.0` MCP contract stays true under V4.2 (because V4.2's LLM step happens on the caller's side, not Frame Check's side).
- The "staged release to manage LLM dependencies" rationale weakens: the MCP package never ships an LLM client, so the LLM-dep-management argument doesn't drive staging.

Staging still survives on narrative-ordering grounds (reserve PyPI name early, add divergence capability once library stabilizes) but the primary rationale shifts.

**Web flow is separate.** Web runs V4.2 server-side with Grok-4.1 Fast non-reasoning as the single-family judge per MODEL_PANEL.md. Cost-per-request is borne by Frame Check; fast-tier model choice bounds it; opt-in rate-limiting bounds it further. This is operator-already-committed.

---

## 2. Recommendation I: V4.2 capability regime (web rate-limited, MCP unbounded)

**Revised 2026-04-23 afternoon after Rec II correction.** Under the single-tool `frame_check` model (see Rec II below), this decision is about V4.2 CAPABILITY per channel, not about a separate divergence tool.

**Recommend:** Single tool `frame_check`. Two cost regimes by channel:

- **Web:** V4.2-mode `frame_check` is rate-limited (candidate: 3 V4.2 calls per IP per day, matching L2 reframe pattern). V1-mode stays unbounded. UX candidate: a "run divergence analysis" action on the analysis results page that promotes to V4.2 backend (Grok-4.1 Fast). Frame Check bears the cost; fast-tier model + rate-limit bound it.

- **MCP:** V4.2 capability always available (no rate limit from Frame Check). The MCP server returns V1 detection + library resources + evidence + `agent_guidance.how_to_render_divergence` instructing the caller's model to complete the composition. Caller's agent bears the LLM cost. Frame Check bears nothing.

**3-year proud-to-own:** The cost-per-channel split maps cost-bearer to capability-user cleanly. MCP adopters (agent-framework integrators) get unrestricted access because their frameworks already bear LLM costs; web users get free fast access with a natural divergence-opt-in. No forced paywall anywhere. In 2029, the answer to "how does Frame Check handle the cost of V4?" is "web is rate-limited and cost-bounded by fast-tier, MCP delegates to caller, and neither exposes FC to scaling risk." That's a clean two-sentence story.

**5-year compound:** MCP integrations compound through the agent-framework ecosystem (every framework that supports `frame_check` with V4.2 capability becomes a citation). Web users compound through demonstration value (public portfolio per STRATEGY §9 effect 4). Both channels strengthen the empire with different compounding dynamics.

**Evidence:** MCP cost model per operator clarification: zero cost to Frame Check because caller's model does the judge step. Web cost model per MODEL_PANEL.md: fast-tier bounded. Stress test §2.2 in PUBLISH_READINESS_ASSESSMENT_v1 named "zero production integrations of MCP" as the rate-limiter; unbounded MCP access is the direct response. Existing L2 reframe rate-limit (3/IP/day) is a proven pattern for bounding LLM-backed web features within §12 envelope.

**Tradeoff accepted:** The MCP caller's agent-framework bears LLM cost for every `frame_check` V4.2 call. Frame Check's `agent_guidance` should carry a one-line note so the caller's framework budgets it correctly. Not Frame Check's problem to enforce, but being explicit is part of evidence discipline.

---

## 3. Recommendation II: Enhance `frame_check` output, NO separate tool

**Revised 2026-04-23 afternoon after operator stress-test.** Prior draft recommended a separate `frame_divergence` tool. Operator pushback was correct: divergence is an OUTPUT SHAPE + GUIDANCE concern, not a TOOL INVENTORY concern. The raw material (present frames, library catalog, detection evidence) is already in `frame_check` output. The novelty of divergence is the faithfulness constraint for absence claims (FRAME_DIVERGENCE §5.1), the domain-relevance filter, and the catalog-traceability discipline, all of which fit inside the existing tool.

**Recommend:** Enhance `frame_check` output to surface a `divergence` block alongside the existing `analysis` block. No new tool. MCP surface stays at two tools (`frame_check`, `frame_compare`). The `divergence` block carries:
- `absent_frames`: catalog entries not matched, filtered by domain-relevance metadata from FVS entries
- `domain_relevance_evidence`: why each absent frame is flagged as relevant (or not) to this document
- `provisional_markers`: flags for library entries under active revision (FVS-010/016/018/020 as of 2026-04-23)
- `agent_guidance.how_to_render_divergence`: explicit instructions for the caller's model to complete the composition with faithfulness guarantees
- `agent_guidance.absence_is_not_prescription`: the §5.1 guarantee 5 language that divergence output never implies the user should have used the absent frames

**3-year proud-to-own:** One tool, one contract, one citation target. Paper citations take the form "Frame Check's `frame_check` tool returned a divergence block showing..." (legible and stable). Compared to the separate-tool alternative: fewer moving parts, clearer maintenance story, no risk of the two tools drifting in incompatible directions.

**5-year compound:** Frame divergence lives in the canon (methodology, FVS library, FRAME_DIVERGENCE Parts 1-4) rather than in MCP tool inventory. When future products (Vaurith, Proposal Check, other agent frameworks) adopt the primitive, they call `frame_check` and render divergence from its enriched output. No need to proliferate tool names per product. Category claim is durable because it's in canon, not in a surface that might change across MCP protocol versions.

**Evidence supporting revision:** `frame_check`'s `frame_library_matches` already provides present-frames; the library catalog is reachable via `frame-check://library/FVS-XXX` resources; `coverage.missing` already carries absence-for-categories signals. The set-difference operation is trivially computable from existing primitives; what's novel is the faithfulness/domain-filter wrapping, which fits in output shape. MCP_CONTRACT_V2_PROPOSAL already moves `frame_check` toward a construct-carrying shape; adding `divergence` is a natural extension of that work, not a parallel track.

**Tradeoff accepted:** `frame_check` output grows. v1-contract consumers ignoring unknown fields (the common case) absorb the addition as additive; strict-schema consumers would break, which is why this lands in the 0.8.0 → 1.0.0 release arc (see Rec III), not patch releases.

**Alignment with FRAME_DIVERGENCE Part 2:** operator-owned. Part 2 defines the exact `divergence` block shape inside `frame_check` output (field names, provenance structure, how_to_render content). This recommendation commits to the SHAPE being an enhancement of `frame_check`, not a new tool; Part 2 fills in the specifics.

**What the prior draft got wrong:** I conflated "category claim" with "tool surface." In MCP, tool-name-in-catalog does have discovery value, but the PRIMARY citation anchor is canon: paper, library, methodology. Adding a tool to claim a category treats MCP as the authoritative surface; it is not. Canon is. The operator's pushback named this cleanly.

---

## 4. Recommendation III: Staged MCP release with narrative-ordered milestones

> **SUPERSEDED by `STRATEGY.md §14` (2026-04-23 late-late evening).** The three-milestone arc recommended below (`0.7.1` → `0.8.0` → `1.0.0`) was retired in favor of a two-milestone arc (`0.8.0` → `1.0.0`) per V4.2-first launch discipline. The `0.7.1` V1-only name-reservation release does NOT happen; the first public PyPI release is `0.8.0` with V4.2 by default. The text below is preserved as historical reasoning. Canonical release commitments live in `STRATEGY.md §14` and `MCP_SERVER.md` "Release arc." When those disagree with the text below, they win.

**Revised 2026-04-23 afternoon for Rec II alignment.** Release count unchanged (three). Content per release refined: 0.8.0 no longer "adds new tool" but "enhances `frame_check` output with divergence block" as additive to v1 consumers.

**Recommend:** Three-milestone release plan on PyPI:

- **`0.7.1`** (name reservation, V1-only, v1 contract as-shipped): `frame_check` + `frame_compare` as they currently exist on the live surface. Zero LLM deps. Reserves `frame-check-mcp` PyPI name with a usable package. Install flow validated. Claude Desktop smoke transcript archived. Does NOT include divergence capability.

- **`0.8.0`** (divergence-capable, additive to v1 contract): enhances `frame_check` output with an optional `divergence` block (see Rec II) when V4.2 data is available. Library_v3 at `data/frame_library_v3/` is the reference (ratified 2026-04-23 per commit `9abeb3d`; Step 4 outcome: adopted revisions to FVS-012/016/018, kept library_v1 text for FVS-010, retired FVS-020 from detection scope). FRAME_DIVERGENCE Part 2 contract and V4.2 engine build in operator-active progress as of 2026-04-23 late afternoon (untracked `FRAME_DIVERGENCE_CONTRACT_v1.md` and `fvs_eval/v4/v4_2_engine.py`). v1-contract consumers ignore the new block; v2-ready consumers use it. Backwards-compatible with 0.7.x installs. No new tool; `frame_check` gains capability.

- **`1.0.0`** (API freeze, v2 contract shape): adopts MCP_CONTRACT_V2_PROPOSAL's construct-carrying shape (`coverage` field restructure, `missing` key retired in favor of per-dimension `status`/`markers_matched`/`vocabulary_searched`; see v2 proposal §3). Breaking change from v1 shape. This is the canonical first stable release papers cite. `divergence` block now composes cleanly with the construct-carrying shape.

**3-year proud-to-own:** A coherent version narrative is a gift to adopters. A 0.7→0.8→1.0 arc that external developers can follow via CHANGELOG is the difference between "we shipped some versions" and "we shipped a category." 1.0.0 is the marker papers cite without ambiguity.

**5-year compound:** Agent frameworks that pin `frame-check-mcp>=1.0,<2.0` are making a commitment backed by Frame Check's API-freeze discipline. That's a trust transaction. Absent a clear 1.0.0 line, pinning is awkward; adopters either pin tightly (blocks upgrades) or loosely (blocks stability claims). Clean 1.0 makes pinning easy.

**Evidence:** MCP_PACKAGE_DESIGN_v1 §7.1 already proposes 0.7.1 as first release. MCP_CONTRACT_V2_PROPOSAL §1 frames the shape change as breaking, a natural 1.0 marker. FRAME_DIVERGENCE_v1 Parts 2-4 land between 0.7 and 0.8.

**Tradeoff accepted:** Three releases instead of one. More operator overhead. Mitigated by each release being small-scope (0.7.1 is rename-to-PyPI only; 0.8.0 adds one tool; 1.0.0 is contract-shape change).

**MCP_PACKAGE_DESIGN_v1 polish needed:** the staging rationale in §7 needs to update to reflect narrative ordering, not LLM-dep management (which the MCP-uses-user's-model clarification makes moot).

---

## 5. Recommendation IV: Publication ordering (library first, then cascading)

**Recommend:** Four-pillar ordered sequence, parallelizing where dependency permits:

**Pillar 1 (weeks 1-2): Intellectual foundation locks.**
- ~~Library v2 ratification~~ **DONE 2026-04-23** as library_v3 (commit `9abeb3d`). Revisions adopted on FVS-012/016/018; kept library_v1 on FVS-010; FVS-020 retired from detection scope. Pillar 1 item 1 closed.
- FRAME_DIVERGENCE Part 2 (contract): operator-owned
- V4.2 architecture decision: single-family Grok-4.1 Fast for web; user's model for MCP (this is already nearly-committed per MODEL_PANEL)

**Pillar 2 (weeks 2-4): Production surface rebuilt.**
- V4.2 web implementation (Grok-4.1 Fast call integrated into existing V1 pipeline as divergence-mode branch)
- FRAME_DIVERGENCE Parts 3-4 (V4.2 integration + red-team map): operator-owned
- Web resume with V4.2-capable site

**Pillar 3 (weeks 3-6): Distribution channels open.**
- MCP package `0.7.1` on PyPI (V1-only, reserves name)
- FVS-001 first canon-promotion reviewer outreach (now site is up)
- Methodology paper v0.3.0 draft advances

**Pillar 4 (weeks 5-10): Demonstration + external record.**
- MCP package `0.8.0` (enhances `frame_check` with divergence block per Rec II revision)
- First financial worked example (Move 9, demonstrates divergence on retail-ladder document)
- Methodology paper v0.3.0 arXiv preprint
- Zenodo Tier B historical snapshot (parallel; any time after Option D ratification which is done)

**3-year proud-to-own:** A four-pillar narrative that lands in ~10 weeks is a readable arc. In 2029, "we built this in Q2-Q3 2026" is a story with specifics. The alternative (shipping artifacts as they're ready without ordering) produces 12 disconnected items that don't compose.

**5-year compound:** Pillar 1 (library + divergence contract) is the citation target for everything downstream. Library_v3 (2026-04-23) is the stable catalog every 2027-2031 citation of Frame Check methodology should point to. Ratification first protected the compound; future library evolution cites library_v3 as baseline.

**Evidence:** Every V4-era asset targets library as substrate. Library stabilization is the pivotal unlock (matches the ENGINE_TIER_STRATEGY_v1 §6 canon-alignment observation). FVS-001 canon promotion can't happen on a down site without bad first impression. MCP 0.7.1 before Part 2 contract works because 0.7.1 doesn't include divergence.

**Tradeoff accepted:** 10 weeks is an estimate, not a commitment. Curator-relational items (reviewer response, Part 2-4 drafting time) carry variance. The pillars compose even if timing slips.

---

## 6. Recommendation V: Production resume after Pillar 1 + early Pillar 2

**Recommend:** Resume production `fly scale count 1 -a fabrication-profiler` when:
- Library v3 ratified (Pillar 1 item 1, DONE 2026-04-23 per commit `9abeb3d`)
- V4.2 web implementation merged and tested locally (Pillar 2 item 1)
- FRAME_DIVERGENCE Part 2 contract text finalized (Pillar 1 item 2)

Not before (site would serve pre-V4 content then update, messy narrative). Not after all pillars (delays demonstration and reviewer outreach too long).

**3-year proud-to-own:** The brief production pause (2026-04-23 to roughly 2026-05-?) becomes part of the discipline-lab narrative: "we stopped serving while we corrected the V4 stack's construct errors, then resumed with the corrected version." That story is MORE compelling than "we kept serving stale V4.1 while iterating internally." Operator's already made this choice; this recommendation names the resume trigger.

**5-year compound:** Forgotten, which is the best outcome. The 10-14-day pause leaves no durable mark; the post-resume state becomes the long-term demonstration surface.

**Evidence:** Resume cannot usefully precede Pillar 1 (site would display old state); should not trail it by more than 1-2 weeks (canon-promotion outreach and demonstration use cases both need the site). The named trigger is the Goldilocks point.

**Tradeoff accepted:** 2-4 more weeks of visible downtime on `frame.clarethium.com`. Uncomfortable but small relative to the empire horizon.

---

## 7. Cross-cutting stress tests

Checking the five recommendations against each other for conflicts.

**Conflict check 1: MCP 0.8.0 release timing vs FRAME_DIVERGENCE Part 2 completion.** Recommendation IV places MCP 0.8.0 in Pillar 4 (weeks 5-10 under revised arrangement). FRAME_DIVERGENCE Part 2 (contract defining the `divergence` block shape in `frame_check` output) is in Pillar 1 (weeks 1-2). Part 2 must ship before 0.8.0 can include the divergence enhancement; sequence holds. **No conflict.**

**Conflict check 2: FVS-001 canon promotion vs library ratification.** FVS-001 is one of the 20 library entries. The revision effort (now ratified as library_v3 per commit `9abeb3d`) focused on FVS-010/012/016/018/020. FVS-001 is NOT among the revised entries; its text stayed stable through v1 → v3. So canon promotion for FVS-001 can proceed independent of the library ratification (which is now done). **No conflict.**

**Conflict check 3: Web resume vs MCP 0.7.1 release.** Recommendation III says 0.7.1 reserves the PyPI name, reservable any time. Recommendation VI says resume on Pillar 1+early Pillar 2. 0.7.1 can ship before OR after resume; independent. But reviewer outreach (Pillar 3) should follow resume. **No conflict; order by dependency.**

**Conflict check 4: V4.2 web implementation timing vs Parts 3-4 of divergence.** V4.2 web integration (Pillar 2) is operator-engineering work. Parts 3-4 of FRAME_DIVERGENCE describe HOW V4.2 feeds divergence under different architectures. Parts 3-4 are best written AGAINST a working V4.2 implementation, not as speculation. **Minor tension:** Parts 3-4 in Pillar 2 could benefit from V4.2 web already existing; resolved by either ordering Parts 3-4 slightly after V4.2 web, OR writing Parts 3-4 against the chosen architecture spec (single-family Grok-4.1 Fast, already known). Second option works.

**Conflict check 5: Financial worked example timing.** Move 9 in Pillar 4 depends on FRAME_DIVERGENCE Part 2 (contract) to know what divergence output looks like, AND on V4.2 web being live to actually demonstrate divergence on a real document. Both are satisfied by Pillar 4 position. **No conflict.**

**Conflict check 6: If operator chooses a different V4.2 architecture than Grok-4.1 Fast single-family.** Current MODEL_PANEL.md points at Grok-4.1 Fast as web production. If operator shifts to Option B (dual-family) or C (3-of-3), web cost changes significantly. Recommendation I's "opt-in + rate-limit" framing absorbs this (higher cost per call → same rate limit → bounded cost). But V4.2 web implementation (Pillar 2) scales differently under dual vs single family. **Mitigation:** MY recommendation for V4.2 architecture (not explicitly listed as a decision above because operator's moves already narrowed it) is **single-family Grok-4.1 Fast**. Named here for the record, alignment check.

---

## 8. The implicit sixth recommendation: V4.2 architecture

I didn't list this as Recommendation VI because operator's MODEL_PANEL.md + `6d182c0` panel-shift commit narrowed it substantially. But stating it explicitly for alignment:

**Recommend:** V4.2 architecture = **single-family Grok-4.1 Fast non-reasoning** for web production; single-family caller's-model for MCP. Multi-family consensus stays research-only per operator's already-stated position.

**3-year proud-to-own:** Single-family simplicity makes V4.2 comprehensible: one call, one model, one cost. Explainability matters for canon claims. "V4.2 runs Grok-4.1 Fast" is a citable sentence; "V4.2 runs a 2-of-3 vote among Opus, Gemini, Grok at reliability threshold X" is a moving target.

**5-year compound:** Single-family binds Frame Check to the xAI trajectory (for web). Mitigated by MCP variant using caller's model: if Grok-4.1 Fast deprecates or regresses, web switches to whatever the new single-family SOTA is, and MCP is already model-agnostic by construction. Vendor risk is contained.

**Evidence:** Finding #14A (9107c8d) confirms Grok-4 family cross-corpus SOTA. Option A in V4_2_DECISION_OPTIONS.md has the cleanest cost-performance profile on OLD panel; fast-tier re-validation pending parallel-agent Step 4 completion. Operator's panel shift + MODEL_PANEL line 40 "web prod choice" essentially already committed.

**Tradeoff accepted:** +0.07 F1 left on the table versus dual-family Option B, +0.087 versus Option C. Acceptable because (a) web production runs already-bounded rate limits, (b) multi-family consensus stays internally for self-audit and reliability studies, (c) single-family cost is the only sustainable public model under §12 $1K envelope.

---

## 9. Honest limits

- **Recommendations are agent-opinions.** Operator's strategic context I do not see. Override any of these without justification needed.
- **3/5-year proud-to-own reasoning is narrative, not data-driven.** The compounding claims rely on a theory of how empire formation works that is itself under construction.
- **Parts 2-4 of FRAME_DIVERGENCE are operator-owned.** Any recommendation that touches Part 2 contract shape (notably Rec II enhance-existing, Rec III staged release, Rec IV pillar ordering) is a proposal for the operator to consider; Part 2 supersedes if it lands different.
- **Fast-tier cost estimate for V4.2 single-family is not audited.** Grok-4.1 Fast per-request cost depends on prompt length, output tokens, and current xAI pricing. "Materially cheaper than flagship" holds by public pricing but exact cost-per-divergence-call needs verification against actual invoices once V4.2 web is live.
- **10-week timeline is an estimate.** Curator-relational items (Part 2-4 writing, library v2 ratification review, reviewer response) carry variance.
- **This doc does not revisit production-stop or MCP-publish-hold.** Both remain operator-controlled directives. Resume trigger in Rec V assumes the operator lifts the production stop when the trigger fires; that's their call.
- **Recommendations assume STRATEGY.md §9 six effects as the compounding model.** An operator who reweights effects (e.g., deprioritizes audience formation in favor of thesis development) might reorder the four pillars differently.

---

## 10. Proposed next move

If recommendations land:
1. Polish `ENGINE_TIER_STRATEGY_v1.md` §3 with the MCP-vs-web split language from §1 of this doc.
2. Polish `MCP_PACKAGE_DESIGN_v1.md` §7 staging rationale to reflect narrative-ordering (not LLM-dep-management).
3. Update MEMORY.md with an entry pointing to this recommendations doc as the current canonical choice surface.
4. Await operator's explicit override or alignment on any of the six recommendations.

If any recommendation is wrong, name which and why; I'll redo that specific one without touching the others.

---

*v1. 2026-04-23. Recommendations under 3- and 5-year proud-to-own lens. Commits to specific paths on Decisions I-VI per operator's explicit request for opinions, not options. Companion to `ENGINE_TIER_STRATEGY_v1.md` (options analysis), `FRAME_DIVERGENCE_v1.md` (Part 1 anchor, operator-owned), `MODEL_PANEL.md` (fast-tier pinning). Non-colliding with parallel-agent Step 4 workstream.*
