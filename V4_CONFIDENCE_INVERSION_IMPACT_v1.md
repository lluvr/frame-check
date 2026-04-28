# V4.1 Confidence Inversion: Downstream Impact Analysis v1

**Status:** proposal v1, 2026-04-23. Companion to `fvs_eval/v4/confidence_calibration_2026_04_23.md` (the empirical Phase 2C finding). That document establishes the finding and proposes three recovery paths (A rename + disclose, B recalibrate, C remove the field). This document maps the finding's cascade across downstream architectural, product, and strategic decisions and proposes a sequencing order for operator review. Does NOT re-analyze the empirical finding. Does NOT choose between Paths A/B/C.

**Purpose:** provide a single-page impact map so each decision downstream of the finding can be made with full awareness of the others. The finding arrived alongside two orthogonal ones (F-2026-030 V4.1 failed on v2 corpus; finding #14 Grok-4 replaces Gemini as single-family SOTA), and all three interact.

---

## 1. The finding, in one paragraph

`frame_library_v4_1._confidence_from_signals` emits `confidence_level` in `{high, medium, low, not_evaluated}`. Phase 2C validated this against 3-of-4 cross-family LLM-judge consensus on combined mixed_genre_v1+v2 (n=37 rule-firing predictions). Precision decreases monotonically with confidence label: `high = 0.500`, `medium = 0.667`, `low = 0.833`. Root cause is construct error: the heuristic measures signal-strength-above-threshold calibrated on Claude Sonnet 4.6; against cross-family consensus as reference, extreme signals correspond to unusual documents where families diverge (FPs inflate), and moderate signals to typical documents where families converge (FPs suppress). The field is misnamed. See `fvs_eval/v4/confidence_calibration_2026_04_23.md` for the per-bucket data, Wilson CIs, and root-cause detail. See `fvs_eval/v4/V4_DECISION_MEMO.md` finding #13 for the concise entry.

---

## 2. Decision cascade

Five decisions depend on resolving this finding. Listed in dependency order, where later decisions are downstream of earlier ones.

### Decision 1: What to do with the `confidence_level` field (Paths A/B/C)

Governing doc: `fvs_eval/v4/confidence_calibration_2026_04_23.md §Recommendation`. Operator chooses one:

- **Path A (rename + disclose):** rename to `signal_strength` or `threshold_distance`, add explicit disclosure. Preserves field, fixes semantics. Requires downstream doc updates in MCP_CONTRACT_V2_PROPOSAL.md (currently silent on V4.1 per-frame confidence) and any future product surfaces.
- **Path B (recalibrate against consensus):** fit thresholds to consensus-reference truth. Requires larger calibration dataset than n=37; Phase 2C flags this as "needs mixed_genre_v3 corpus build." Defers resolution but lets the field survive unchanged.
- **Path C (remove field):** drop from V4.1 output entirely until V4.2 LLM-judge provides real calibration. Simplest, most construct-honest. Analysis doc's recommendation.

This decision is the fulcrum. All downstream decisions depend on it.

### Decision 2: V4.2 architecture revision

Governing doc: `fvs_eval/v4/DESIGN.md` v3. Two separate revisions now required:

**2a.** Routing logic cannot use V4.1 confidence as originally planned. DESIGN.md §3 envisioned a two-mode V4.2 where rule-based V4.1 handles easy cases and LLM-judge handles hard cases, with V4.1 confidence as the routing signal. That routes backwards. Alternatives:

- Route by rule-firing (binary): V4.1 answers when rule fires, LLM-judge verifies all firings.
- Route by document features (genre, length, domain) independent of V4.1 signals.
- Route all firings through LLM-judge as a pure augmentation (cost doubles but no routing errors).

**2b.** Single-family judge selection. `DESIGN.md` v3 specified "latest Gemini top-tier" based on finding #5 (Gemini as median family on v1). Finding #14 supersedes: Grok-4 is cross-corpus SOTA at average macro-F1 = 0.728, vs Gemini 2.5 Pro at 0.705. V4.2 should use Grok-4 unless operator has a pricing-policy or provider-diversity preference.

These two revisions are independent of each other but must both land before V4.2 implementation begins. Neither depends on Decision 1 directly, but the routing revision is sharpened by Decision 1 (if `confidence_level` is removed per Path C, the "rule-firing vs not-firing" routing becomes the only option).

### Decision 3: V4.1 production integration (V1 → V4.1 swap in MCP)

Governing doc: `DETECTOR_V2_PROMOTION.md` checklist. Current state: V4.1 Foundation committed to master but zero production integration (verified earlier in session against `app.py`, `mcp_server.py`, `pipeline.py`, `comparison.py`, all of which still import from V1 `frame_library`). The promotion checklist predates the Phase 2C finding.

If Decision 1 = Path A or Path C: the `confidence_level` field is either renamed or absent before any V4.1-to-production move. The checklist gains a prerequisite.

If Decision 1 = Path B: V4.1 production swap is further blocked until recalibration data arrives. Current recommendation against Path B is partly speed-based.

**The production stop (2026-04-23) means this decision is not time-urgent.** V4.1-to-production requires production to be live AND the field resolved. Both are open.

### Decision 4: MCP package (Move 5) content decision

Governing doc: `MCP_PACKAGE_DESIGN_v1.md` (published this session, under PUBLISH HOLD). The package ships whatever detector is in `mcp_server.py`'s call chain at release time.

- If V4.1 is still offline research code at release (current state), `frame-check-mcp==0.7.1` ships V1 detector. The confidence inversion is a latent concern not a current bug.
- If V4.1 is wired into the MCP server before release, the package ships the inverted-confidence code. Every pip install propagates the broken field. The PUBLISH HOLD should extend until Decision 1 resolves.

Interaction with the Publish Hold: the hold is explicit and separate from this finding, but the finding is a strong argument for KEEPING the hold until V4.1's field situation is resolved. Lifting the hold before Decision 1 is premature.

### Decision 5: Library revision (FVS-010/016/018/020), adjacent but unblocked

Governing doc: `data/frame_library/INDEX.md` + the RELIABILITY_STUDY §4 library-ambiguity finding. This decision is about sharpening Identification text for the four persistent-divergence frames; the confidence inversion finding does NOT change the library-revision rationale. Library revision proceeds on its own track, curator-gated.

Worth noting because library revisions may themselves change V4.1's rule-firing behavior for those frames, which in turn changes which samples land in which confidence buckets. Recalibration (Path B) interacts with library revision; the two decisions compound.

---

## 3. Strategic implications

Three observations beyond the per-decision cascade.

**Three findings in ~9 hours on the V4 boundary.** F-2026-030 failed 2026-04-22T22:20 (V4.1 on v2 = 0.215, below the 0.40 pre-reg threshold). Finding #13 inverted 2026-04-23T06:55. Finding #14 Grok-4-SOTA + Gemini-artifact 2026-04-23T07:10. Read together, this is a compression of construct-honesty work on the V4 stack: three pre-registered or post-registered negatives against the operator's own architecture in a single work cycle. That IS the discipline-lab effect (STRATEGY.md §9 effect 3) working in real time. Worth naming in SESSION_STATE §1 or STRATEGY.md §9 Extended block as concrete evidence.

**The stop + hold posture is coherent with this finding.** The production stop and MCP publish hold both arrived on 2026-04-23 alongside these findings. Speculating on operator motivation is risky (the production-stopped memory explicitly tags motivation as inferred), but the sequence is consistent with "don't ship code whose own self-audit just exposed a construct error; resolve the error first." Any agent continuation plan that pushes external channels forward during this window should defer.

**Paths A and C preserve the V4 architecture; Path B commits to more empirical work.** Path A (rename) and Path C (remove) are low-cost doc/code revisions (hours, not days). Path B (recalibrate) needs a mixed_genre_v3 corpus build at n~60, then per-frame threshold fitting, then re-validation. Days-to-weeks. If the operator chooses Path B, it effectively commits to a V4.3 or V5 cycle on top of the V4.2 architecture revision: significantly more scope than Paths A or C imply.

---

## 4. Proposed decision sequence

If the operator wants to resolve this in dependency order:

1. **Decide Paths A/B/C on the `confidence_level` field** (Decision 1). One-sitting curator call. Fast once chosen. Sharpens everything below.
2. **Revise V4 DESIGN v3 §3 routing logic** (Decision 2a) + update single-family recommendation to Grok-4 per finding #14 (Decision 2b). One revision pass on DESIGN.md. Agent can draft both revisions once Decision 1 lands.
3. **Decide V4.1 production integration posture** (Decision 3). Gated on Decisions 1+2 PLUS production restart. Lower-urgency while production is stopped.
4. **Extend MCP publish hold explicitly to "until Decision 1 resolves"** (Decision 4). Cheap doc update to `MCP_PACKAGE_DESIGN_v1.md` naming this dependency alongside the operator's existing hold directive.
5. **Library revision work** (Decision 5) proceeds independently. Could parallel-run with Decisions 1-4.

**What agent work unblocks after Decision 1:**

- If Path A: draft the rename + disclosure text for `_confidence_from_signals` docstring, `DESIGN.md`, `V4_DECISION_MEMO.md`, and any future MCP contract version that exposes the field. Mechanical.
- If Path B: draft the mixed_genre_v3 corpus build spec, pre-register F-2026-03X for the recalibration, build the validation script. Research work.
- If Path C: draft the removal PR (delete `_confidence_from_signals`, remove `confidence_level` from `suggest_frames_v4_1` output, update `DETECTABLE_FRAMES` contract, update any references in `DESIGN.md`, `V4_DECISION_MEMO.md`, tests). Mechanical.

---

## 5. What this document does NOT claim

- **Does not recommend Path A, B, or C.** The upstream analysis doc recommends Path C; this document defers to the curator on the tradeoff.
- **Does not assess whether the Grok-4-SOTA finding changes V4.2 cost economics.** `STRATEGY.md §12` $1K/yr budget still applies; Grok-4 pricing may differ from Gemini 2.5 Pro pricing; not audited here.
- **Does not predict how operator motivation maps to the stop + hold.** Noted as consistent with the finding sequence, not diagnosed as the cause.
- **Does not propose V4.2 implementation timing.** Per STRATEGY and NEXT_STEPS, V4.2 is operator-gated and subordinate to §13 domain-ladder priorities.
- **Does not touch the library-revision decision (FVS-010/016/018/020).** That is INDEX.md protocol + curator-review; this finding does not change the library-revision case.

---

## 6. Honest limits of this impact analysis

- **Dependency sequence is logical, not operational.** I mapped dependencies based on what each decision's governing doc says. Real operator decision cadence could reorder these. For example, if the operator decides to de-prioritize V4.2 entirely for a quarter, Decision 3's urgency drops and Decisions 1-2 become a longer-window choice.
- **MCP package impact assumes `frame-check-mcp` will eventually exist.** If operator decides Move 5 is not the right distribution shape (e.g., prefers a hosted API, or decides MCP distribution should wait for v2 contract), Decision 4 changes.
- **V4.2 cost under Grok-4 not verified.** Finding #14 notes "V4.2 single-family implementation should prefer Grok-4 if pricing allows." Pricing check not done in this pass.
- **The confidence-inversion finding may be n-limited.** Operator's honest-limits note in the Phase 2C doc flags n=37 as thin. Direction is robust; magnitude could tighten. A narrower inversion might change the tolerability calculus for Path A (keep the field with disclosure) vs Path C (remove).
- **STRATEGY.md §9 effect-3 discipline-lab credit is a framing proposal.** Whether the three-in-24-hours sequence is "impressive" to an external reviewer is interpretive. The commits speak for themselves; no framing is forced.
- **I am not the author of the Phase 2C analysis.** My synthesis may miss nuances the analyst intended. Operator review of this document should flag any misreading of the upstream finding.

---

## 7. Proposed next move

Produce this document (done) and halt for operator review of:

- Decision 1 (Paths A/B/C)
- Whether to explicitly extend the MCP publish hold to "until Decision 1 resolves" in `MCP_PACKAGE_DESIGN_v1.md`

Once Decision 1 is made, the downstream work is mechanical enough that an agent can draft the changes for operator confirmation without further architectural review.

---

*v1. 2026-04-23. Impact analysis for V4.1 confidence inversion finding per user request. Companion to `fvs_eval/v4/confidence_calibration_2026_04_23.md` and `fvs_eval/v4/V4_DECISION_MEMO.md` finding #13. Written at commit `9107c8d` (cross-corpus Grok-4 SOTA, operator's most recent commit) + this session's `d4100b2` (production stop). Produces no code changes, no architectural decisions; surfaces the decision cascade so operator review lands on a structured map, not a blank page.*
