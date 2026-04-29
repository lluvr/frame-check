# v3 Evidence Against DETECTOR_V2_PROMOTION Activation Criteria

**HISTORICAL (updated 2026-04-28):** SUPERSEDED by the V4.2 LLM-judge architecture (per `ENGINE_TIER_RECOMMENDATIONS_v1.md` and the V4.2-first launch commitment, operator-approved 2026-04-23). The v3 promotion question was closed by the architectural transition to V4.2 before C1-C6 ratification; v3's macro-F1=0.215 below-threshold result is now the published-negative anchor that motivated the V4.2 transition. Read this document as the audit-trail evidence for the v3 promotion attempt; current detector ladder lives in `ENGINE_TIER_RECOMMENDATIONS_v1.md` and `fvs_eval/v4/RELIABILITY_STUDY.md`.

**Date:** 2026-04-19.
**Purpose:** compact mapping of Track A v3 detector work against each pre-registered activation criterion (C1-C6) in `DETECTOR_V2_PROMOTION.md §2`, so the curator can ratify or reject promotion without re-reading all the Track A reports.
**Relationship to prior work:** this document does NOT constitute promotion. It surfaces evidence against already-pre-registered criteria and flags which are green, which fail, and which require a curator decision. Per DETECTOR_V2_PROMOTION anti-pattern #4 ("Do not promote v2 without ratified activation criteria"), promotion proceeds only after the curator locks the criteria in this document or their weaker/stronger variants.

**v3 vs v2 scope note.** DETECTOR_V2_PROMOTION.md was written primarily for v2 (rule-level retirements + tunings). Track A added v3 (v2 rules + new signals S-1 through S-4 in `framing_v2.py` and `frame_library_v3.py`). The playbook's C1 upgrade (2026-04-19) explicitly anticipates v3 promotion. This document evaluates the v3 candidate; v2 candidate evidence is in REPORT_V2.md and is stricter-retirement than v3.

---

## C1: Replicated F1 improvement

**Default threshold:** macro-F1 ≥ 0.4 on n ≥ 30 corpus with ≥ 2 independent annotators not on the Frame Check project.

**Observed v3:** macro-F1 = **0.360** on n=28 (A=8, B=10, C=10) with curator + LLM-judge.

**Verdict vs default:** **FAIL.** F1 below 0.4 threshold (by 0.040). Annotators are not independent of the project (curator IS the project; LLM-judge is not external human).

**Weaker alternative ("directional, n=12, CIs wide"):** v3 crosses 0.35 on n=28 (0.360). Does not use n=12. LLM-judge is not "independent execution" in the spirit of the criterion.

**Third option (declare insufficient power):** applicable. v3 macro-F1 = 0.360 on n=28 with non-independent annotators is diagnostic evidence, not production-gate evidence. This is the honest path for the current state.

**Per-frame upgrade (2026-04-19):** C1 additionally requires pre-registered per-frame predictions with falsifiable effect sizes. Track A DID pre-register H-A1 through H-A4 in DESIGN_v2.md §2:

| Hypothesis | Predicted | Observed | Verdict | Stat-power note |
|-----------|---------:|---------:|:-----:|-------|
| H-A1 FVS-012 F1 ≥ 0.35 (S-1 uncertainty regex) | 0.35 | 0.538 | PASS | n=18 majority-positives; robust |
| H-A2 FVS-016 F1 ≥ 0.35 (S-2 named-author citation) | 0.35 | 0.400 | PASS | n=16; credible |
| H-A3 FVS-008 F1 ≥ 0.35 (S-3 growth vocabulary) | 0.35 | 0.400 | PASS | n=7; thin |
| H-A4 FVS-015 F1 ≥ 0.35 (S-4 efficiency vocabulary) | 0.35 | 0.500 | PASS | **n=2 majority-positives; noise band** |

Four numerical passes. Two (H-A1, H-A2) stat-robust. One (H-A3) thin. One (H-A4) within noise band per REPORT_V3_TRACK_A.md §2.1.

**C1 summary:** default FAIL. Weaker alternative PARTIAL (crosses 0.35 but n≠12 and annotators aren't independent). Third option ("declare insufficient power") is the honest verdict. Per-frame upgrade: 4/4 numerical pass, 2/4 stat-robust.

**Curator decision required:** lock one of:
- (a) Declare insufficient power → v3 does not promote under C1 on internal-only evidence; external annotators required per default;
- (b) Lock weaker alternative (0.35 threshold) and ship with perpetual "internal-only labelers, n=28" caveat in METHODOLOGY.md;
- (c) Defer C1 until Track B reader-aid study results arrive (concurrent per DETECTOR_V2_PROMOTION Decision 2 locked 2026-04-19), use Track B outcome to inform whether v3 ship-gate is classifier-precision or system-value.

---

## C2: No per-frame regression

**Default:** for every frame v1 detects at F1 ≥ 0.5, v2/v3 F1 on same frame does not drop by more than 0.05.

**v1 frames at F1 ≥ 0.5 on n=28 corpus:** FVS-011 Stakeholder only (v1 F1 = 0.632 on n=28; note higher than the n=12 figure of 0.727 because the expanded corpus has more Stakeholder-appropriate documents).

Actually re-examining: v1 on EXPANDED corpus had FVS-011 F1 = 0.632 per REPORT_V3_TRACK_A §3. v3 F1 = 0.588 per same table. Delta = -0.044.

**Verdict vs default:** **PASS.** Drop of 0.044 is within the 0.05 threshold.

**Note:** Track A's v2 candidate (rule-only, n=12) had a larger FVS-011 drop (0.727 → 0.667 = 0.061 drop) that marginally exceeded C2 default. v3 candidate (v2 rules + new signals, n=28) has a smaller drop within threshold. **v3 passes C2 where v2 narrowly did not.** This is an argument for promoting v3 over v2.

---

## C3: Reproducibility-test path chosen

**Status:** curator decision required.

**Three paths in §1.5:**
- Path A: version-scope the test. Preserve v1 data.json unchanged; add v2/v3 data_v2.json alongside; parametrize test.
- Path B: regenerate data.json under v3; archive v1 as data_v1.json; update worked example text.
- Path C: add `detector_version` argument to `build_epistemic_payload`; pin test to v1.

**Recommendation: Path A.** Rationale:
- Preserves the v1 captured artifact under its original detector version (per anti-pattern #8: "Do not retroactively rewrite worked-example captures under a new detector version").
- Adds the v3 capture as parallel, not replacement. External citations of v1 frame matches continue to resolve.
- Engineering effort is modest: add a `@pytest.mark.parametrize` over detector version, capture v3 output once, assert both reproduce.
- Path B requires updating the worked-example commentary (which cites specific v1 frames); high-effort and anti-pattern #8 adjacent.
- Path C adds a new parameter to a core function; larger surface change.

**Curator decision required:** lock Path A, B, or C.

---

## C4: INDEX.md retirement policy

**v3 specific divergence from v2.** v2 retired FVS-001, FVS-008, FVS-015. v3 keeps FVS-001 retired but REWIRES FVS-008 and FVS-015 via new signals (S-3 growth vocabulary, S-4 efficiency vocabulary). INDEX.md Detection column needs:

- FVS-001 Frame Amplification: **retired** (v3 keeps v2's retirement; no signal substrate for iteration within a session).
- FVS-008 Growth Frame: **yes** under v3 (rewired with S-3); would be retired under v2.
- FVS-015 Efficiency Frame: **yes** under v3 (rewired with S-4); would be retired under v2.

**INDEX.md action on v3 promotion:** FVS-001 Detection = `retired`; FVS-008 and FVS-015 Detection = `yes` (active detection rule exists in production). Add a note describing the rewire.

**This changes the INDEX update scope.** DETECTOR_V2_PROMOTION.md §2.4 anticipated v2's retirement-only update ("v2 promotion only promotes the framework, not new rules"). v3 introduces NEW signal implementations. Per the playbook's description ("A new `yes` Detection state appears for any v2 rule that has been redesigned beyond retirement"), v3's FVS-008 and FVS-015 qualify as redesigned-beyond-retirement.

**C4 summary:** resolvable on v3 promotion with clear documentation of the S-3 and S-4 signal additions. Not a failure.

---

## C5: METHODOLOGY.md version bump

**Status:** not yet executed; pre-promotion task per §3 Step 5.

**Planned updates under v3 promotion:**
- Version bump to 0.4.0 (or 0.3.1 if Patch-level, curator's call).
- §2.4.1: update from "v2 post-audit result" to "v2 superseded by v3" or equivalent.
- §2.4.2 (new): name v3 as current production detector, activation criteria met, evidence citation (REPORT_V3_TRACK_A.md).
- §2.4.3 (new): construct-honesty note on tuning-set F1 vs held-out (not-yet-validated) generalization.
- Document-head note: production runs v3 with v2 rules + S-1 through S-4 signal additions.

**C5 summary:** straightforward once v3 promotion activates; no blocker.

---

## C6: Not blocked on worked-example citations

**Status:** zero external citations exist that pin to specific v1 frame IDs for any worked example. Trivially met.

---

## Summary table

| Criterion | Verdict on v3 | Blocker? |
|-----------|:-------------:|:--------:|
| C1 macro-F1 | default FAIL (0.360 < 0.4); weaker PARTIAL; third option APPLICABLE | YES, requires curator decision |
| C1 per-frame | 4/4 numerical pass, 2/4 stat-robust | Informational |
| C2 no per-frame regression | PASS (FVS-011 delta = -0.044 < 0.05 threshold) | No |
| C3 reproducibility path | OPEN, curator choice | YES, requires curator decision |
| C4 INDEX.md | Resolvable; v3 restores FVS-008/015 as `yes` | No (execution detail) |
| C5 METHODOLOGY.md bump | Pre-promotion task | No (execution detail) |
| C6 worked-example citations | Trivially met (zero external citations) | No |

**Two curator decisions required before v3 promotion proceeds:**
1. **C1 posture:** declare insufficient power (defer), weaker alternative with caveat, or defer C1 pending Track B.
2. **C3 path:** A (version-scope), B (regenerate+archive), C (detector_version param).

**v3-specific argument vs v2:** v3 passes C2 where v2 narrowly failed. v3's macro-F1 (0.360) is closer to 0.4 than v2's (0.274). v3 restores FVS-008 and FVS-015 via new signals where v2 retires them. v3 is a strictly-more-complete candidate for promotion; v2 remains available as the rule-only-change variant.

---

## Evidence citations

- **Macro-F1 numbers:** `fvs_eval/validation_study/results/results_v3.json` and `fvs_eval/validation_study/REPORT_V3_TRACK_A.md §1, §3`.
- **Per-frame F1:** REPORT_V3_TRACK_A.md §3.
- **n=28 corpus:** `fvs_eval/validation_study/corpus/manifest.json` v5.
- **v3 code:** `fvs_eval/validation_study/framing_v2.py` (signals), `fvs_eval/validation_study/frame_library_v3.py` (rules).
- **Labels:** `fvs_eval/validation_study/labels/labels_curator_v3.json`, `labels_llm_v3.json`, `labels_detector_v3.json`.
- **Honest-framing caveats:** REPORT_V3_TRACK_A.md §1 lists four caveats (tuning-set bias, LLM-judge permissiveness, low-n CIs, construct validity gap). All inherited by this document.

---

## What this document is NOT

- **Not a promotion.** No production code has been modified.
- **Not a recommendation to promote.** The verdict on C1 is "curator decision required"; the honest third option (declare insufficient power and defer) is viable and may be the right choice.
- **Not a replacement for Track B.** DETECTOR_V2_PROMOTION Decision 2 (2026-04-19) locks Track A and Track B as concurrent promotion surfaces. v3 evidence is Track A only.

## What happens next

If the curator ratifies C1 (picks posture) and C3 (picks path), v3 promotion proceeds per `DETECTOR_V2_PROMOTION.md §3` steps 1-8. If the curator chooses to defer C1 pending Track B or pending external annotators, v3 stays in `fvs_eval/validation_study/` as research artifact; production continues on v1; this document is preserved as the evidence record for future reconsideration.

---

*v1. 2026-04-19. Maps Track A v3 evidence against DETECTOR_V2_PROMOTION.md activation criteria. Not a promotion. Curator ratification required before any production change.*
