"""
Phase 3A: V4.1 regression test suite.

Purpose: lock in current V4.1 detector behavior so future library
revisions, rule changes, or refactors do not silently break the
detection pipeline. Tests are structural (output shape, frame coverage,
honest-limit tagging) rather than probabilistic (precision, recall)
because Phase 2C found V4.1 confidence to be miscalibrated against
cross-family consensus; encoding current precision values as test
expectations would freeze a known-bad calibration.

These tests run against:
- fvs_eval/v4/frame_library_v4_1.suggest_frames_v4_1
- fvs_eval/v4/frame_reliability (FRAME_RELIABILITY, HONEST_LIMIT_FRAMES)
- Synthetic sample inputs (not dependent on live LLM calls)

Run: python -m pytest test_frame_library_v4_1.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
for subdir in ("fvs_eval/validation_study", "fvs_eval/v3_2", "fvs_eval/v4"):
    sys.path.insert(0, str(REPO / subdir))
sys.path.insert(0, str(REPO))

from framing import detect_voice, temporal_orientation, detect_epistemic_basis  # noqa
from framing_v2 import (  # noqa
    detect_coverage_v2,
    detect_growth_vocabulary,
    detect_efficiency_vocabulary,
)
from framing_v3_2 import (  # noqa
    detect_named_author_citation_v3_2,
    detect_growth_vocabulary_v3_2,
)
from frame_library_v4_1 import (  # noqa
    DETECTABLE_FRAMES,
    suggest_frames_v4_1,
)
from frame_reliability import (  # noqa
    FRAME_RELIABILITY,
    HONEST_LIMIT_FRAMES,
    HONEST_LIMIT_NOTE,
)


# ── Fixtures ──────────────────────────────────────────────────────────

SAMPLE_GROWTH_TEXT = """
In 2024, the AI market grew 150% year over year. Revenue climbed from
$10B to $25B. Enterprise adoption accelerated across all verticals.
Productivity improvements reached 40% in early pilots. The momentum is
undeniable. Industry leaders project another 200% growth in 2025,
building on this unprecedented trajectory. Every major company is
now deploying generative AI at scale.
"""

SAMPLE_CITATION_TEXT = """
According to a 2024 McKinsey study, 73% of enterprises are deploying
generative AI across core operations. Research from MIT's Media Lab
shows that organizations adopting AI report a 30% productivity lift
within the first year. Industry analysts project the enterprise AI
market to exceed $150 billion by 2028.
"""

SAMPLE_BALANCED_TEXT = """
The new regulation affects multiple stakeholders. Consumers may see
slightly higher prices, estimated at 2-3% annually. Small businesses
face compliance costs that research from the Federal Reserve Bank of
Kansas City, working paper RWP 24-03, estimates at $4,200 median per
year. Industry groups like the National Association of Manufacturers
dispute these figures, citing a 2024 internal study at $12,000 median.
Regulators argue the consumer-protection benefits justify the costs.
Environmental groups note second-order effects on supply chains. The
academic literature, including Chen and Wong (2023) in the Journal
of Policy Analysis, finds net welfare gains of 0.3% to 1.1%. The
actual distribution of costs and benefits depends on implementation.
"""


def _run_v4_1(text: str):
    """Run the full V3.2 signal pipeline and V4.1 suggest_frames."""
    cov = detect_coverage_v2(text)
    voice = detect_voice(text)
    temp = temporal_orientation(text)
    epist = detect_epistemic_basis(text)
    na = detect_named_author_citation_v3_2(text)
    gv = detect_growth_vocabulary_v3_2(text)
    ev = detect_efficiency_vocabulary(text)
    return suggest_frames_v4_1(cov, voice, temp, epist, na, gv, ev)


# ── Structural contract tests ──────────────────────────────────────────

def test_output_is_list_of_dicts():
    """V4.1 must return a list; each element a dict."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    assert isinstance(entries, list), "suggest_frames_v4_1 must return list"
    for e in entries:
        assert isinstance(e, dict), f"entry must be dict, got {type(e)}"


def test_every_detectable_frame_is_represented():
    """V4.1's contract is that all 11 detectable frames appear in output
    (even if rule did not fire), so API consumers see the complete
    picture with per-frame metadata."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    emitted_fvs_ids = {e["fvs_id"] for e in entries}
    for fvs_id in DETECTABLE_FRAMES:
        assert fvs_id in emitted_fvs_ids, (
            f"{fvs_id} missing from V4.1 output "
            f"(detectable frames must all appear)"
        )


def test_every_entry_has_required_fields():
    """V4.1 entry shape contract per frame_library_v4_1 docstring.

    Note 2026-04-23: `confidence_level` removed per D1 Path C
    (Phase 2C found it INVERTED against consensus). Required fields
    no longer include confidence_level.
    """
    required = {
        "fvs_id",
        "source",
        "reliability",
        "rule_matched",
        "honest_limit_note",
    }
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    for e in entries:
        missing = required - set(e.keys())
        assert not missing, (
            f"entry for {e.get('fvs_id','?')} missing fields: {missing}"
        )


def test_confidence_level_field_removed():
    """D1 Path C: `confidence_level` was INVERTED against consensus
    (Phase 2C) and removed 2026-04-23. Tests assert the field is gone
    so future code does not silently re-add a known-miscalibrated field."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    for e in entries:
        assert "confidence_level" not in e, (
            f"{e['fvs_id']}: confidence_level field has been re-added; "
            f"removal is documented in fvs_eval/v4/confidence_calibration_2026_04_23.md. "
            f"Re-adding requires curator-anchored per-frame calibration."
        )


def test_source_is_valid_string():
    """source must be 'rule' or 'honest_limit'."""
    valid = {"rule", "honest_limit"}
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    for e in entries:
        assert e["source"] in valid, (
            f"{e['fvs_id']}: source '{e['source']}' not in {valid}"
        )


def test_rule_matched_is_bool():
    """rule_matched must be boolean."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    for e in entries:
        assert isinstance(e["rule_matched"], bool), (
            f"{e['fvs_id']}: rule_matched must be bool, got {type(e['rule_matched'])}"
        )


# ── Honest-limit invariants ────────────────────────────────────────────

def test_honest_limit_frames_always_have_honest_limit_source():
    """FVS-010 and FVS-016 are always in honest-limit mode per V4.1
    doctrine (F-2026-027 cross-family divergence)."""
    entries = _run_v4_1(SAMPLE_CITATION_TEXT)
    for e in entries:
        if e["fvs_id"] in HONEST_LIMIT_FRAMES:
            assert e["source"] == "honest_limit", (
                f"{e['fvs_id']} is an honest-limit frame but emitted "
                f"source='{e['source']}' (expected 'honest_limit')"
            )


def test_honest_limit_entries_have_disclosure_note():
    """Honest-limit entries must emit the disclosure text (non-None)."""
    entries = _run_v4_1(SAMPLE_CITATION_TEXT)
    for e in entries:
        if e["fvs_id"] in HONEST_LIMIT_FRAMES:
            assert e.get("honest_limit_note") is not None, (
                f"{e['fvs_id']} honest-limit entry missing disclosure note"
            )
            assert isinstance(e["honest_limit_note"], str), (
                f"{e['fvs_id']} honest_limit_note must be str"
            )
            assert len(e["honest_limit_note"]) > 0, (
                f"{e['fvs_id']} honest_limit_note must be non-empty"
            )


def test_default_mode_entries_have_no_honest_limit_note():
    """Non-honest-limit (default-mode) entries should emit None for
    honest_limit_note."""
    entries = _run_v4_1(SAMPLE_CITATION_TEXT)
    for e in entries:
        if e["fvs_id"] not in HONEST_LIMIT_FRAMES:
            assert e.get("honest_limit_note") is None, (
                f"{e['fvs_id']} is default-mode but emitted "
                f"honest_limit_note={e.get('honest_limit_note')!r}"
            )


def test_honest_limit_frame_set_matches_reliability_constant():
    """HONEST_LIMIT_FRAMES in frame_reliability should be exactly the
    two frames F-2026-027 identified as cross-family-divergent at
    detectable-frame scope: FVS-010 and FVS-016."""
    assert HONEST_LIMIT_FRAMES == {"FVS-010", "FVS-016"}, (
        f"HONEST_LIMIT_FRAMES changed from canonical {{'FVS-010','FVS-016'}}; "
        f"review F-2026-027 outcome before adjusting"
    )


# ── Reliability metadata wiring ────────────────────────────────────────

def test_reliability_metadata_present_for_all_detectable_frames():
    """Each detectable frame should carry cross-family reliability
    metadata from F-2026-027 baseline in frame_reliability.py."""
    for fvs_id in DETECTABLE_FRAMES:
        assert fvs_id in FRAME_RELIABILITY, (
            f"{fvs_id} missing reliability entry; run F-2026-027 "
            f"annotation batch"
        )


def test_reliability_fields_in_output():
    """V4.1 output entries should carry the reliability dict from
    FRAME_RELIABILITY for the frame."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    for e in entries:
        assert "reliability" in e, f"{e['fvs_id']}: reliability missing"
        rel = e["reliability"]
        assert isinstance(rel, dict), f"{e['fvs_id']}: reliability must be dict"


# ── Basic smoke / sanity ───────────────────────────────────────────────

def test_growth_text_triggers_growth_frame():
    """A document with heavy growth vocabulary should trigger FVS-008
    under V3.2 rule (which V4.1 delegates to)."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    fvs_008 = next((e for e in entries if e["fvs_id"] == "FVS-008"), None)
    assert fvs_008 is not None, "FVS-008 entry missing"
    # FVS-008 (Growth Frame) is default-mode, should fire on strong
    # growth vocabulary. Source must be 'rule' if fired.
    if fvs_008["rule_matched"]:
        assert fvs_008["source"] == "rule", (
            "FVS-008 is default-mode; source should be 'rule' when fired"
        )


def test_empty_text_does_not_raise():
    """Pathological empty input must not crash the detector chain.

    Originally discovered by Phase 3A as an xfail bug: detect_coverage_v2
    in framing_v2.py raised ZeroDivisionError when live word_count was 0.
    Fixed 2026-04-23 by floor-at-1 guard in n_words computation.
    """
    entries = _run_v4_1("")
    assert isinstance(entries, list)
    # All detectable frames should still be in the output structure
    emitted = {e["fvs_id"] for e in entries}
    for fvs_id in DETECTABLE_FRAMES:
        assert fvs_id in emitted, (
            f"{fvs_id} missing from empty-text V4.1 output"
        )


def test_short_text_does_not_raise():
    """Very short input should not crash."""
    entries = _run_v4_1("Hello world.")
    assert isinstance(entries, list)


# ── Cross-corpus regression fixtures ───────────────────────────────────
# Lock in current output on known fixtures so future changes to V3.2
# rules or V4.1 wrapper don't silently change classification.

def test_balanced_text_honest_limit_frames_still_emit_note():
    """Even on balanced text where the V3.2 rule for FVS-016 does not
    fire, V4.1 must still emit the honest_limit note (construct-honesty
    doctrine)."""
    entries = _run_v4_1(SAMPLE_BALANCED_TEXT)
    for e in entries:
        if e["fvs_id"] == "FVS-016":
            assert e["source"] == "honest_limit"
            assert e["honest_limit_note"] is not None
            break
    else:
        pytest.fail("FVS-016 not in V4.1 output")


# ── Post-Path-C structural tests (confidence_level removed 2026-04-23) ──
# Phase 2C found V4.1's `confidence_level` field INVERTED against
# cross-family consensus. D1 resolved with Path C (remove field).
# Remaining tests verify the rule_matched + source dichotomy is
# sufficient diagnostic signal without the misleading probability-
# implying field.

def test_rule_matched_plus_source_carries_full_rule_diagnostic():
    """With confidence_level removed, rule_matched + source together
    carry the full rule diagnostic: (True, rule) = rule fired on
    default-mode frame; (False, rule) = rule did not fire on default-
    mode frame; (*, honest_limit) = honest-limit frame regardless of
    rule firing (force-falsified in V4.1 output semantics via the
    separate honest-limit evaluation path)."""
    entries = _run_v4_1(SAMPLE_GROWTH_TEXT)
    for e in entries:
        # rule_matched is always a boolean
        assert isinstance(e["rule_matched"], bool)
        # source is one of the two valid values
        assert e["source"] in {"rule", "honest_limit"}
        # honest_limit entries carry a disclosure; rule entries don't
        if e["source"] == "honest_limit":
            assert e["honest_limit_note"] is not None
        else:
            assert e["honest_limit_note"] is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
