"""
Tests for reliability-tier weighting in compute_trust.

Before this adjustment, a 'verified' Source Network result from a weak-tier
provider (Wolfram Alpha F1=0.5) counted identically to one from a strong-tier
provider (SEC EDGAR F1=1.0). This masked low-quality verifications behind a
'high trust' verdict.

Evidence discipline (2026-04-17 revision): "uncalibrated" is NOT
the same as "weak". Uncalibrated means we have not measured the provider's
F1; weak means we measured it and the F1 is below 0.4. Only WEAK lowers
trust. Uncalibrated is reported as informational (reliability unmeasured)
without lowering the verdict. Treating "don't know" the same as "poor"
was the construct error the revision fixed: Wikipedia is the highest-
volume verification source, was uncalibrated, and would have been unfairly
flagged as tentative under the earlier logic.

Tier assignments come from calibration/results/*/reliability_tiers.json.
"""

from formatter import compute_trust, _apply_reliability_tier_adjustment


def _minimal_profile():
    """Profile with no source and no temporal so compute_trust
    takes the no-source SN-driven branch."""
    return {}


class TestTierAdjustmentHelper:
    """Unit tests for the adjustment helper in isolation."""

    def test_no_sn_stats_is_noop(self):
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [], None,
        )
        assert level == "high"
        assert reasons == []

    def test_missing_verified_by_tier_is_noop(self):
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [], {"verified": 5},
        )
        assert level == "high"
        assert reasons == []

    def test_empty_tier_counts_is_noop(self):
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [],
            {"verified_by_tier": {"strong": 0, "moderate": 0, "weak": 0, "uncalibrated": 0}},
        )
        assert level == "high"
        assert reasons == []

    def test_all_strong_tier_preserves_high(self):
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [],
            {"verified_by_tier": {"strong": 5, "moderate": 0, "weak": 0, "uncalibrated": 0}},
        )
        assert level == "high"
        assert reasons == []

    def test_weak_majority_lowers_high_to_moderate(self):
        """The headline case: HIGH trust riding on providers with
        MEASURED weak reliability (F1<0.4) gets lowered. Uncalibrated
        providers are NEUTRAL; they do not count against the weak side."""
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [],
            {"verified_by_tier": {"strong": 1, "moderate": 0, "weak": 3, "uncalibrated": 2}},
        )
        # weak(3) > measured_good(1) triggers the lowering rule.
        assert level == "moderate"
        # The caveat should reference the measured-F1 basis of the
        # adjustment, not just the label 'weak'.
        assert any(
            "measured" in r.lower() or "f1" in r.lower()
            for r in reasons
        )

    def test_uncalibrated_only_is_informational_not_trust_lowering(self):
        """Revised (2026-04-17) behavior: uncalibrated ≠ weak. All-uncal
        verifications do NOT lower trust; they note that reliability is
        unmeasured. Wikipedia is the canonical case: highest-volume
        verifier, uncalibrated, should not be penalized as tentative."""
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [],
            {"verified_by_tier": {"strong": 0, "moderate": 0, "weak": 0, "uncalibrated": 4}},
        )
        assert level == "high", (
            "Uncalibrated-only must NOT lower trust. Unmeasured is not "
            "poor. This is the construct error the revision fixed."
        )
        assert any("unmeasured" in r.lower() or "not yet been measured" in r.lower()
                   for r in reasons)
        # The word "tentative" explicitly must NOT appear for the
        # uncalibrated case. "Tentative" is the language for weak
        # reliability, not unknown reliability.
        assert not any("tentative" in r.lower() for r in reasons)

    def test_balanced_mix_preserves_level(self):
        """Equal weak vs measured-good does not trigger the lowering
        rule (strict > comparison, not >=)."""
        level, reasons = _apply_reliability_tier_adjustment(
            "high", [],
            {"verified_by_tier": {"strong": 2, "moderate": 1, "weak": 2, "uncalibrated": 1}},
        )
        # measured_good = 3, weak = 2. weak > measured_good is False, no lower.
        assert level == "high"
        assert reasons == []

    def test_adjustment_never_raises_trust(self):
        """Degenerate input cannot raise level."""
        level, reasons = _apply_reliability_tier_adjustment(
            "low", [],
            {"verified_by_tier": {"strong": 10, "moderate": 0, "weak": 0, "uncalibrated": 0}},
        )
        # Low stays low; adjustment only lowers or annotates
        assert level == "low"


class TestTierWeightedComputeTrust:
    """End-to-end compute_trust with SN stats carrying tier breakdown."""

    def test_high_verdict_on_weak_verifications_lowered(self):
        sn_stats = {
            "total": 6,
            "checked": 6,
            "verified": 6,
            "contradicted": 0,
            "unverifiable": 0,
            "verified_by_tier": {
                "strong": 1,
                "moderate": 0,
                "weak": 3,
                "uncalibrated": 2,
            },
        }
        trust = compute_trust(_minimal_profile(), sn_stats=sn_stats)
        assert trust["level"] == "moderate", (
            "Verifications where WEAK (measured F1<0.4) outnumber "
            "strong+moderate providers must not sustain a high verdict. "
            "Uncalibrated counts do NOT contribute to the weak side."
        )
        reason_blob = " ".join(trust["reasons"]).lower()
        assert "measured" in reason_blob or "f1" in reason_blob

    def test_high_verdict_on_strong_verifications_preserved(self):
        sn_stats = {
            "total": 5,
            "checked": 5,
            "verified": 5,
            "contradicted": 0,
            "unverifiable": 0,
            "verified_by_tier": {
                "strong": 5,
                "moderate": 0,
                "weak": 0,
                "uncalibrated": 0,
            },
        }
        trust = compute_trust(_minimal_profile(), sn_stats=sn_stats)
        assert trust["level"] == "high"
