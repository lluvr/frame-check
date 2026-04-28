"""Regression tests for voice construct-honesty audit findings.

Pins the violation documented in CONSTRUCT_HONESTY_AUDIT_v1.md so that
subsequent changes to _voice_cascade_eval, _VOICE_BORDERLINE_MARGIN, or
the residual-analytical prose produce test failures (or, when the fix
ships, test deletions). These tests document current behavior as a
known-violation state, not desired behavior; they should be inverted
when Level 3 responses ship.

See fvs_eval/THRESHOLD_SENSITIVITY_v1.md for threshold-sensitivity
context and fvs_eval/CONSTRUCT_HONESTY_AUDIT_v1.md for the audit.
"""

from __future__ import annotations

import pathlib

import pytest

from framing import (
    detect_voice, detect_coverage, detect_epistemic_basis,
    framing_portrait, temporal_orientation,
)
from claim_analysis import analyze_claims


CORPUS = pathlib.Path(__file__).parent / "fvs_eval" / "validation_study" / "corpus"


def _residual_analytical_docs():
    """Return doc paths whose voice falls through to residual analytical.

    Characterized by all voice rules missing: you_pct=0, imperative_count=0,
    we_pct<20, spec_pct<20, and promo conditions unmet. On the N=28 corpus,
    all 20 such docs have you_pct=0 and imperative_count=0 (see
    CONSTRUCT_HONESTY_AUDIT_v1.md §2.5).
    """
    out = []
    for p in sorted(CORPUS.glob("*.txt")):
        v = detect_voice(p.read_text())
        if v["voice"] == "analytical" and v["runner_up"] is None:
            out.append(p)
    return out


def test_residual_analytical_cluster_size_on_N28():
    """Regression pin: shipped thresholds produce exactly 20 residual cases.

    Drift signal: if _voice_cascade_eval or _VOICE_BORDERLINE_MARGIN
    changes such that this count differs, the threshold-sensitivity
    analysis (THRESHOLD_SENSITIVITY_v1.md §2.5) must be re-run.
    """
    residual = _residual_analytical_docs()
    assert len(residual) == 20, (
        f"Expected 20 residual-analytical docs on N=28 per "
        f"CONSTRUCT_HONESTY_AUDIT_v1.md §2.5; got {len(residual)}. "
        f"If intentional, update the audit + threshold sensitivity docs."
    )


def test_b01_residual_analytical_raw_feature_invariant():
    """Pins the concrete case used throughout the audit.

    b01_nvidia_investment is the purest residual-analytical case:
    every voice rule misses decisively. If a regex expansion or feature
    change causes this document to produce non-zero voice markers, the
    audit's concrete traces become stale.
    """
    text = (CORPUS / "b01_nvidia_investment.txt").read_text()
    v = detect_voice(text)

    assert v["you_pct"] == 0
    assert v["we_pct"] == 0
    assert v["imperative_count"] == 0
    assert v["spec_pct"] == 0
    assert v["voice"] == "analytical"
    assert v["runner_up"] is None
    assert v["margin_to_threshold"] == 5.0
    assert v["confidence"] == "high"


def test_residual_analytical_confidence_is_always_high():
    """Pins the construct-honesty violation.

    Every residual-analytical document in the corpus receives
    confidence='high' despite zero positive voice evidence. This is
    the violation audited in CONSTRUCT_HONESTY_AUDIT_v1.md §2.5. Test
    should be inverted when Level 3 responses ship (fixing the
    residual case).
    """
    residual = _residual_analytical_docs()
    for p in residual:
        v = detect_voice(p.read_text())
        assert v["confidence"] == "high", (
            f"{p.name}: expected 'high' confidence (construct-honesty "
            f"violation per audit); got {v['confidence']!r}. If this "
            f"failure is because Level 3 shipped, invert this test."
        )
        assert v["margin_to_threshold"] == 5.0, (
            f"{p.name}: residual-analytical margin is expected to equal "
            f"shipped r6_threshold=5; got {v['margin_to_threshold']}. "
            f"Coupling mechanism may have changed; re-run "
            f"THRESHOLD_SENSITIVITY_v1.md §2.5."
        )


def test_residual_analytical_portrait_is_evidence_bound():
    """Inverted 2026-04-21 on L3a ship.

    Previously pinned the violation phrase 'Analytical document
    examining the topic in third person.' Now pins the
    evidence-bound replacement that mirrors Fix A coverage
    discipline for cascade-classification residual cases.
    Per CONSTRUCT_HONESTY_AUDIT_v1.md §4 L3a.
    """
    text = (CORPUS / "b01_nvidia_investment.txt").read_text()
    cov = detect_coverage(text)
    temp = temporal_orientation(text)
    voice = detect_voice(text)
    epist = detect_epistemic_basis(text)
    ca = analyze_claims(text)

    portrait = framing_portrait(cov, temp, voice, epist, ca)

    assert "Analytical document examining" not in portrait, (
        f"L3a fix should have removed the existential phrase. "
        f"Portrait: {portrait!r}"
    )
    assert "no directive, promotional, or descriptive voice markers" in portrait.lower(), (
        f"L3a residual-aware portrait should name the absent marker "
        f"classes. Portrait: {portrait!r}"
    )
    assert "residual analytical" in portrait.lower(), (
        f"L3a portrait should name the residual classification. "
        f"Portrait: {portrait!r}"
    )


def test_framing_ai_llm_context_analytical_is_evidence_bound():
    """Inverted 2026-04-21 on L3a ship.

    Previously pinned the violation phrase in framing_ai._build_user_message
    ('Voice: analytical (third-person examination)'). Now pins the
    evidence-bound replacement that sends the LLM construct-honest
    context for residual-analytical documents.
    Per CONSTRUCT_HONESTY_AUDIT_v1.md §4 L3a.
    """
    import framing_ai as _fa
    import inspect

    src = inspect.getsource(_fa)
    assert 'f"Voice: {voice_type} (third-person examination)"' not in src, (
        "L3a fix should have removed the existential fallback "
        "from framing_ai._build_user_message."
    )
    assert "no directive/promotional/descriptive markers detected" in src, (
        "L3a residual-aware framing_ai context should name the "
        "absent marker classes for LLM consumption."
    )


def test_comparison_voice_implications_analytical_is_evidence_bound():
    """Inverted 2026-04-21 on L3a ship.

    Previously pinned the violation phrase in comparison.py
    voice_implications dict ('presents third-person examination').
    Now pins the evidence-bound replacement.
    Per CONSTRUCT_HONESTY_AUDIT_v1.md §4 L3a.
    """
    import comparison as _comp
    import inspect

    src = inspect.getsource(_comp)
    assert '"analytical": "presents third-person examination"' not in src, (
        "L3a fix should have removed the existential phrase from "
        "comparison.py voice_implications."
    )
    assert "no directive/promotional/descriptive voice markers detected" in src, (
        "L3a residual-aware comparison prose should name the "
        "absent marker classes."
    )


def test_temporal_balanced_rate_zero_on_N28():
    """Regression pin on THRESHOLD_SENSITIVITY_v1.md headline.

    Shipped temporal rule (max<50 AND margin<10) flags 0 documents on
    the validation corpus because every document has max>=50. If this
    drifts (via corpus change or rule change), the sensitivity study
    headlines become stale.
    """
    balanced = 0
    for p in sorted(CORPUS.glob("*.txt")):
        t = temporal_orientation(p.read_text())
        if t["balanced"]:
            balanced += 1
    assert balanced == 0, (
        f"Expected 0 balanced docs per THRESHOLD_SENSITIVITY_v1.md "
        f"§2.2; got {balanced}. Re-run the sensitivity study."
    )


def test_framing_summary_respects_balanced_flag():
    """Closes §5.2 leak: framing_summary now honors temporal.balanced.

    Prior to 2026-04-21, framing_summary emitted "Temporal orientation:
    present (47%)" for docs with balanced=True, leaking the balanced
    state. The fix aligns framing_summary with templates/results.html
    line 1288-1296 which already handled balanced correctly.
    """
    from framing import framing_summary

    coverage = {
        "covered": ["causes"],
        "missing": ["risks", "stakeholders", "trends", "uncertainty"],
        "categories": {
            "causes": {"covered": True, "density_per_1kw": 3.5},
            "risks": {"covered": False, "density_per_1kw": 0},
            "stakeholders": {"covered": False, "density_per_1kw": 0},
            "trends": {"covered": False, "density_per_1kw": 0},
            "uncertainty": {"covered": False, "density_per_1kw": 0},
        },
    }
    temporal_balanced = {
        "past_pct": 47, "present_pct": 45, "future_pct": 8,
        "dominant": "past", "dominant_margin": 2, "balanced": True,
    }
    temporal_dominant = {
        "past_pct": 10, "present_pct": 80, "future_pct": 10,
        "dominant": "present", "dominant_margin": 70, "balanced": False,
    }
    claim_stats = {"total_claims": 0, "unhedged_count": 0}

    balanced_out = framing_summary(coverage, temporal_balanced, claim_stats)
    dominant_out = framing_summary(coverage, temporal_dominant, claim_stats)

    assert "balanced" in balanced_out, (
        f"balanced temporal should produce balanced summary; got: "
        f"{balanced_out!r}"
    )
    assert "no tense dominates" in balanced_out, (
        f"balanced summary should state 'no tense dominates'; got: "
        f"{balanced_out!r}"
    )
    assert "Temporal orientation: present (80%)" in dominant_out, (
        f"dominant temporal should produce dominant summary; got: "
        f"{dominant_out!r}"
    )
    assert "balanced" not in dominant_out, (
        f"dominant temporal should NOT produce balanced summary; got: "
        f"{dominant_out!r}"
    )


def test_temporal_margin_only_rule_would_flag_one():
    """Regression pin on §2.6 temporal rule decomposition.

    If the shipped conjunction were replaced with margin-only
    (`margin < 10`), exactly 1 document (c05_wikipedia_nuclear_fusion,
    max=54 margin=8) would flag balanced. This test pins the
    decomposition finding; any drift indicates the corpus or the
    temporal feature extraction has changed.
    """
    count = 0
    for p in sorted(CORPUS.glob("*.txt")):
        t = temporal_orientation(p.read_text())
        if t["dominant_margin"] < 10:
            count += 1
    assert count == 1, (
        f"Expected 1 doc with margin<10 per "
        f"THRESHOLD_SENSITIVITY_v1.md §2.6; got {count}."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
