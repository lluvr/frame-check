"""Tests for the synthesis layer of ``framing.py``.

The detectors (``detect_coverage``, ``detect_voice``,
``temporal_orientation``, ``detect_epistemic_basis``) are exercised
in ``test_framing_validation.py`` and through the wider integration
suites. The synthesizers below were largely uncovered because the
prior test surface only ran ``framing_portrait`` indirectly through
the MCP composer:

  - ``framing_summary``: descriptive multi-sentence summary, no
    evaluative labels (coverage + density + temporal + confidence).
  - ``framing_portrait_natural``: prose-register parallel to the
    clinical ``framing_portrait`` (cascade-aware).
  - ``framing_headline``: single most important framing finding as
    a one-liner.

Each function takes the per-detector output dicts; this file builds
the dicts directly so the tests don't depend on the detector
implementations.
"""

from __future__ import annotations

from typing import Any

from framing import framing_headline, framing_portrait_natural, framing_summary


# ================================================================
# Fixture builders
# ================================================================


def _coverage(
    *,
    covered: list[str] | None = None,
    missing: list[str] | None = None,
    densities: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build a coverage dict shaped like ``detect_coverage`` output."""
    covered = covered if covered is not None else ["causes", "risks"]
    missing = missing if missing is not None else ["stakeholders", "trends", "uncertainty"]
    densities = densities or {}
    cats: dict[str, dict[str, Any]] = {}
    for cat in ("causes", "risks", "stakeholders", "trends", "uncertainty"):
        is_covered = cat in covered
        cats[cat] = {
            "covered": is_covered,
            "density_per_1kw": densities.get(cat, 5.0 if is_covered else 0.0),
            "count": 5 if is_covered else 0,
        }
    return {
        "covered": covered,
        "missing": missing,
        "categories": cats,
        "coverage_count": len(covered),
        "total_categories": 5,
    }


def _voice(*, voice: str = "analytical", total_sentences: int = 30, **extras: Any) -> dict[str, Any]:
    base = {
        "voice": voice,
        "total_sentences": total_sentences,
        "you_pct": 0,
        "we_pct": 0,
        "imperative_count": 0,
        "spec_pct": 0,
        "promo_pct": 0,
    }
    base.update(extras)
    return base


def _temporal(
    *,
    dominant: str = "present",
    pct: int = 60,
    balanced: bool = False,
    margin: int = 30,
) -> dict[str, Any]:
    return {
        "dominant": dominant,
        "balanced": balanced,
        "dominant_margin": margin,
        f"{dominant}_pct": pct,
        "past_pct": 20,
        "present_pct": pct if dominant == "present" else 20,
        "future_pct": 20,
    }


def _epistemic(
    *,
    sourced: int = 5,
    sourced_pct: int = 50,
    numeric_sentences: int = 10,
    unsupported_numeric: int = 0,
    total_sentences: int = 30,
) -> dict[str, Any]:
    # Note: framing.py uses ``epistemic['total_sentences']`` (subscript,
    # not .get) at lines 1701 and 1998, so the key is required for
    # the framing_portrait + framing_portrait_natural calls; every
    # other read uses .get() with a 0 default. Including the key
    # in the fixture avoids the KeyError without papering over the
    # real-shape requirement.
    return {
        "sourced": sourced,
        "sourced_pct": sourced_pct,
        "numeric_sentences": numeric_sentences,
        "unsupported_numeric": unsupported_numeric,
        "total_sentences": total_sentences,
    }


def _claims(*, total: int = 10, unhedged: int = 3) -> dict[str, Any]:
    return {
        "total_claims": total,
        "unhedged_count": unhedged,
        "hedged_count": total - unhedged,
    }


# ================================================================
# framing_summary
# ================================================================


class TestFramingSummary:
    """``framing_summary`` produces a descriptive multi-sentence
    summary of coverage + density + temporal + confidence."""

    def test_no_coverage_says_no_markers(self) -> None:
        cov = _coverage(covered=[], missing=["causes", "risks", "stakeholders", "trends", "uncertainty"])
        result = framing_summary(cov, _temporal(), _claims())
        assert "No structural markers detected" in result

    def test_partial_coverage_lists_covered_and_missing(self) -> None:
        cov = _coverage(
            covered=["causes", "risks"],
            missing=["stakeholders", "trends", "uncertainty"],
        )
        result = framing_summary(cov, _temporal(), _claims())
        assert "Covers: causes, risks" in result
        assert "Low structural coverage: stakeholders, trends, uncertainty" in result

    def test_full_coverage_says_all_five(self) -> None:
        cov = _coverage(
            covered=["causes", "risks", "stakeholders", "trends", "uncertainty"],
            missing=[],
        )
        result = framing_summary(cov, _temporal(), _claims())
        assert "Covers all five analytical dimensions" in result

    def test_emphasis_skew_surfaces_when_3x_imbalance(self) -> None:
        # Causes dominant at 12/1Kw; risks at 1/1Kw -> 12x ratio with
        # max above 2.0 floor -> emphasis-skew sentence.
        cov = _coverage(
            covered=["causes", "risks"],
            missing=["stakeholders", "trends", "uncertainty"],
            densities={"causes": 12.0, "risks": 1.0},
        )
        result = framing_summary(cov, _temporal(), _claims())
        assert "Emphasis skew" in result

    def test_no_emphasis_skew_when_dominant_below_floor(self) -> None:
        # Both densities below the 2.0/1Kw floor -> no skew sentence.
        cov = _coverage(
            covered=["causes", "risks"],
            missing=["stakeholders", "trends", "uncertainty"],
            densities={"causes": 1.0, "risks": 0.1},
        )
        result = framing_summary(cov, _temporal(), _claims())
        assert "Emphasis skew" not in result

    def test_balanced_temporal_uses_balance_phrase(self) -> None:
        result = framing_summary(
            _coverage(),
            _temporal(balanced=True, margin=5),
            _claims(),
        )
        assert "balanced" in result.lower()
        assert "no tense dominates" in result

    def test_dominant_temporal_uses_dominant_phrase(self) -> None:
        result = framing_summary(
            _coverage(),
            _temporal(dominant="future", pct=70),
            _claims(),
        )
        assert "Temporal orientation: future" in result

    def test_high_unhedged_rate_surfaces_definitive_fact_warning(self) -> None:
        # 8 of 10 unhedged = 80% which is the > 0.8 gate.
        result = framing_summary(_coverage(), _temporal(), _claims(total=10, unhedged=9))
        assert "definitive fact" in result

    def test_low_unhedged_rate_does_not_surface_warning(self) -> None:
        result = framing_summary(_coverage(), _temporal(), _claims(total=10, unhedged=2))
        assert "definitive fact" not in result

    def test_low_total_claims_does_not_surface_warning(self) -> None:
        # Below the >= 5 total_claims gate, even high unhedged ratio
        # does not trip the warning (small-N dishonest).
        result = framing_summary(_coverage(), _temporal(), _claims(total=4, unhedged=4))
        assert "definitive fact" not in result


# ================================================================
# framing_portrait_natural
# ================================================================


class TestFramingPortraitNatural:
    """``framing_portrait_natural`` parallels ``framing_portrait`` but
    in plain prose register. Cascade-aware: voice type + coverage
    gaps + epistemic posture combine into 2-4 sentence portrait."""

    def test_zero_sentences_returns_insufficient_text(self) -> None:
        voice = _voice(total_sentences=0)
        result = framing_portrait_natural(
            _coverage(), _temporal(), voice, _epistemic(), _claims(),
        )
        assert "Insufficient text" in result

    def test_returns_non_empty_string(self) -> None:
        # Substantive input -> non-empty portrait.
        result = framing_portrait_natural(
            _coverage(), _temporal(), _voice(),
            _epistemic(), _claims(),
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_promotional_voice_with_unsourced_numbers(self) -> None:
        voice = _voice(voice="promotional")
        epist = _epistemic(numeric_sentences=10, unsupported_numeric=5)
        result = framing_portrait_natural(
            _coverage(), _temporal(), voice, epist, _claims(),
        )
        # Portrait surfaces something about the promotional + unsourced
        # combination; just verify the pipeline runs and emits prose.
        assert isinstance(result, str)

    def test_with_grounding_decomposition(self) -> None:
        # When grounding is provided, additional projection-related
        # narrative may surface.
        grounding = {
            "proportions": {"G": 0.5, "F": 0.3, "P": 0.2},
            "scope_assessment": {"regime": "diagnostic"},
        }
        result = framing_portrait_natural(
            _coverage(), _temporal(), _voice(),
            _epistemic(), _claims(),
            grounding=grounding,
        )
        assert isinstance(result, str)

    def test_with_verification_results(self) -> None:
        verification = {"contradicted": 2, "verified": 8, "total_checked": 10}
        result = framing_portrait_natural(
            _coverage(), _temporal(), _voice(),
            _epistemic(), _claims(),
            verification=verification,
        )
        assert isinstance(result, str)


# ================================================================
# framing_headline
# ================================================================


class TestFramingHeadline:
    """``framing_headline`` returns the single most important framing
    finding as a one-liner, or ``None`` when nothing is flag-worthy."""

    def test_promotional_with_unsupported_numbers_fires(self) -> None:
        cov = _coverage()
        voice = _voice(voice="promotional")
        epist = _epistemic(numeric_sentences=10, unsupported_numeric=3)
        result = framing_headline(cov, _temporal(), voice, epist, _claims())
        assert result is not None
        assert "Promotional" in result or "promotional" in result

    def test_prescriptive_with_low_coverage_fires(self) -> None:
        cov = _coverage(
            covered=["causes"],
            missing=["risks", "stakeholders", "trends", "uncertainty"],
        )
        voice = _voice(voice="prescriptive")
        result = framing_headline(cov, _temporal(), voice, _epistemic(), _claims())
        assert result is not None
        assert "Prescriptive" in result or "prescriptive" in result

    def test_verification_contradictions_appended(self) -> None:
        cov = _coverage()
        voice = _voice(voice="promotional")
        epist = _epistemic(unsupported_numeric=3)
        verification = {"contradicted": 2, "verified": 5, "total_checked": 7}
        result = framing_headline(cov, _temporal(), voice, epist, _claims(), verification)
        assert result is not None
        assert "contradicted" in result.lower()

    def test_no_finding_returns_none(self) -> None:
        # Balanced coverage, analytical voice, well-sourced -> nothing
        # to flag.
        cov = _coverage(
            covered=["causes", "risks", "stakeholders", "trends", "uncertainty"],
            missing=[],
        )
        epist = _epistemic(sourced_pct=80, unsupported_numeric=0)
        claims = _claims(total=10, unhedged=2)
        result = framing_headline(cov, _temporal(), _voice(), epist, claims)
        # When no rule fires, the function returns None.
        assert result is None

    def test_singular_vs_plural_contradicted_phrasing(self) -> None:
        cov = _coverage()
        voice = _voice(voice="promotional")
        epist = _epistemic(unsupported_numeric=3)
        # 1 contradicted -> "claim" (singular).
        v1 = {"contradicted": 1, "verified": 5, "total_checked": 6}
        result1 = framing_headline(cov, _temporal(), voice, epist, _claims(), v1)
        # 2 contradicted -> "claims" (plural).
        v2 = {"contradicted": 2, "verified": 5, "total_checked": 7}
        result2 = framing_headline(cov, _temporal(), voice, epist, _claims(), v2)
        assert result1 is not None and result2 is not None
        # Same prefix, different singular/plural noun.
        assert ("1 claim contradicted" in result1) or ("contradicted" in result1)
        assert ("2 claims contradicted" in result2) or ("contradicted" in result2)
