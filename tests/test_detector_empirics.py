"""Unit tests for scripts/detector_empirics.py harness helpers.

The harness runs `frame_check` over stdio MCP against the
adversarial-fixtures + worked-examples corpus and aggregates the
structural fields. The end-to-end run is operator-on-demand (slow:
launches an MCP subprocess per document); these unit tests CI-
protect the helpers with synthetic payloads so a regression in
`_frame_deepening_fires`, `_aggregate`, or `_markdown_report` is
caught at PR time rather than when the operator next runs the
harness and finds the report malformed.

Scope deliberately narrow to the 2026-04-30 per-detector-aggregation
addition. The pre-existing helpers (`_present_fvs`,
`_absent_pattern_fvs`, `_addressed_perspectives`, etc.) have been
exercised against the real corpus for weeks and have their own
proven behavior; pinning them here would re-state existing surface
without adding signal.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import detector_empirics  # noqa: E402


def _payload_with_frame_deepening(temporal=None, stakeholder=None,
                                  falsification=None):
    """Build a minimal MCP-shaped payload with the named
    frame_deepening sub-detector values. None means "detector
    returned None and the wire shape carries null"; a dict means
    "detector fired and emitted structural evidence" -- the actual
    dict content does not matter for the fires assertion.
    """
    return {
        "analysis": {
            "frame_deepening": {
                "temporal_scope": temporal,
                "stakeholder_map": stakeholder,
                "falsification_conditions": falsification,
            },
        },
    }


def test_frame_deepening_fires_all_three_when_all_dicts():
    """All three detectors fire when each sub-field is a dict.
    Mirrors the saturation case observed on the 2026-04-30 13-doc
    corpus where every adversarial fixture and worked example
    triggered all three detectors.
    """
    p = _payload_with_frame_deepening(
        temporal={"year_count": 4},
        stakeholder={"role_count": 3},
        falsification={"primary_match_count": 1},
    )
    assert detector_empirics._frame_deepening_fires(p) == [
        "temporal_scope",
        "stakeholder_map",
        "falsification_conditions",
    ]


def test_frame_deepening_fires_empty_when_all_none():
    """No detector fires when each sub-field is null. The
    text-without-content case (regex finds nothing). MCP wire
    shape preserves None as null; the helper reads `is not None`
    so null sub-fields are correctly counted as no-fire.
    """
    p = _payload_with_frame_deepening(
        temporal=None, stakeholder=None, falsification=None,
    )
    assert detector_empirics._frame_deepening_fires(p) == []


def test_frame_deepening_fires_partial():
    """A mix of fired / non-fired sub-detectors returns only the
    fired names, in canonical iteration order. Catches a future
    regression that drops the canonical order (e.g., switching to
    a set-then-sorted output, which would alphabetize and break
    the aggregate's tie-breaking expectation).
    """
    p = _payload_with_frame_deepening(
        temporal={"year_count": 1},
        stakeholder=None,
        falsification={"primary_match_count": 2},
    )
    assert detector_empirics._frame_deepening_fires(p) == [
        "temporal_scope",
        "falsification_conditions",
    ]


def test_frame_deepening_fires_handles_missing_block():
    """When the analysis dict has no frame_deepening key at all
    (a payload from a future MCP version that drops the block, or
    a malformed test fixture), the helper returns empty without
    raising. The defensive `.get(..., {}) or {}` guard catches both
    missing key and None.
    """
    p_missing = {"analysis": {}}
    assert detector_empirics._frame_deepening_fires(p_missing) == []

    p_none = {"analysis": {"frame_deepening": None}}
    assert detector_empirics._frame_deepening_fires(p_none) == []


def test_frame_deepening_fires_treats_empty_dict_as_fire():
    """A sub-detector returning {} (instead of None) counts as a
    fire because the helper checks `is not None`. The current
    detectors at frame_deepening.py never emit {} (they emit None
    or a non-empty dict), but this pin documents the wire-shape
    contract: the harness reads the null/non-null distinction MCP
    preserves, not the dict-emptiness signal. A future detector
    that emits {} for "no signal but field present" would over-
    count fires here; that change would need the helper updated
    AND this test updated together so the contract stays explicit.
    """
    p = _payload_with_frame_deepening(
        temporal={},
        stakeholder=None,
        falsification=None,
    )
    assert detector_empirics._frame_deepening_fires(p) == ["temporal_scope"]


def _per_doc(label, fired_detectors, **rest):
    """Synthesize a per_doc dict with the minimum fields _aggregate
    reads. Exposes only the keys the aggregator iterates so a
    refactor that drops one fails the explicit-key tests below
    rather than the generic _aggregate test (clearer signal).
    """
    base = {
        "label": label,
        "word_count": 100,
        "present_fvs": [],
        "absent_pattern_fvs": [],
        "addressed_perspectives": [],
        "genre_classification": None,
        "voice_classification": None,
        "absence_cluster_dimensions": [],
        "frame_deepening_fires": list(fired_detectors),
    }
    base.update(rest)
    return base


def test_aggregate_fills_zero_fire_detectors_in_output():
    """Aggregate must report ALL THREE frame_deepening sub-detectors
    even if one (or all) never fired on the corpus. Without the
    setdefault fill, a zero-fire detector would be absent from the
    aggregate dict and the markdown report would not mention it at
    all (silent zero), which is construct-misleading: the operator
    should see "detector X: 0 of N" explicitly so they know the
    detector exists and was measured.
    """
    docs = [
        _per_doc("a", ["temporal_scope"]),
        _per_doc("b", ["temporal_scope", "stakeholder_map"]),
    ]
    agg = detector_empirics._aggregate(docs)
    fd = agg["frame_deepening_per_detector_fires"]
    assert set(fd.keys()) == {
        "temporal_scope",
        "stakeholder_map",
        "falsification_conditions",
    }
    assert fd["temporal_scope"] == 2
    assert fd["stakeholder_map"] == 1
    assert fd["falsification_conditions"] == 0


def test_aggregate_per_detector_counts_match_inputs():
    """Aggregate counts must equal the per-doc fire occurrence
    count summed across all docs. Catches a refactor that
    accidentally double-counts (e.g., iterating `present_fvs`
    twice) or undercounts (e.g., `for det in d:` iterating
    dict keys instead of the list).
    """
    docs = [
        _per_doc("a", ["temporal_scope", "stakeholder_map",
                       "falsification_conditions"]),
        _per_doc("b", ["temporal_scope", "stakeholder_map",
                       "falsification_conditions"]),
        _per_doc("c", ["temporal_scope"]),
        _per_doc("d", []),
    ]
    agg = detector_empirics._aggregate(docs)
    fd = agg["frame_deepening_per_detector_fires"]
    assert fd["temporal_scope"] == 3
    assert fd["stakeholder_map"] == 2
    assert fd["falsification_conditions"] == 2
    assert agg["n_documents"] == 4


def test_markdown_report_renders_per_detector_section():
    """The markdown report must include the new section header,
    the per-detector table with all three rows (in `most_common`
    order on this synthetic data), and the prose explanation that
    references NEXT_STEPS.md and the saturation reading.

    Pins the report shape so a refactor that removes the section
    or breaks the table rendering fails at PR time instead of
    surfacing as a mangled report when the operator next runs the
    harness.
    """
    docs = [
        _per_doc("a", ["temporal_scope", "stakeholder_map"]),
        _per_doc("b", ["temporal_scope"]),
    ]
    agg = detector_empirics._aggregate(docs)
    report = detector_empirics._markdown_report(docs, agg)

    assert "## Frame deepening per-detector firing rate" in report
    assert "| temporal_scope | 2 | 2 | 100 |" in report
    assert "| stakeholder_map | 1 | 2 | 50 |" in report
    assert "| falsification_conditions | 0 | 2 | 0 |" in report
    assert "NEXT_STEPS.md" in report
    assert "CEILING saturation" in report


def test_markdown_report_per_doc_table_includes_deepening_column():
    """Per-document detail table must carry the new Deepening
    column with single-letter codes (T = temporal_scope, S =
    stakeholder_map, F = falsification_conditions; "-" for
    unfired). The codes preserve canonical detector order
    regardless of which fired so an operator scanning rows
    reads consistently across documents.
    """
    docs = [
        _per_doc("a", ["temporal_scope", "stakeholder_map",
                       "falsification_conditions"], word_count=100,
                 present_fvs=["FVS-011"]),
        _per_doc("b", ["temporal_scope"], word_count=200),
        _per_doc("c", [], word_count=50),
    ]
    agg = detector_empirics._aggregate(docs)
    report = detector_empirics._markdown_report(docs, agg)

    # Header includes the new column
    assert "| Deepening |" in report
    # Per-doc rows carry the right codes in canonical order
    assert "| `a` |" in report
    assert "| TSF |" in report  # all three fired -> TSF
    assert "| T-- |" in report  # only temporal -> T--
    assert "| --- |" in report  # none fired -> ---


def test_aggregate_preserves_existing_fields():
    """The new frame_deepening aggregation must be additive: the
    existing aggregate keys (per_fvs_fires, coverage_perspective_
    addressed, genre_distribution, voice_distribution, absence_
    cluster_dimension_fires, per_fvs_absent_pattern_fires) all
    stay present and count correctly. Catches a regression that
    accidentally returns ONLY the new field or shadows an
    existing key.
    """
    docs = [
        _per_doc("a", ["temporal_scope"],
                 present_fvs=["FVS-011"],
                 addressed_perspectives=["risks"],
                 genre_classification="analysis",
                 voice_classification="analytical"),
        _per_doc("b", ["temporal_scope", "stakeholder_map"],
                 present_fvs=["FVS-011", "FVS-012"],
                 absent_pattern_fvs=["FVS-007"],
                 addressed_perspectives=["risks", "stakeholders"],
                 genre_classification="advocacy",
                 voice_classification="prescriptive",
                 absence_cluster_dimensions=["calibration"]),
    ]
    agg = detector_empirics._aggregate(docs)

    assert agg["n_documents"] == 2
    assert agg["per_fvs_fires"] == {"FVS-011": 2, "FVS-012": 1}
    assert agg["per_fvs_absent_pattern_fires"] == {"FVS-007": 1}
    assert agg["coverage_perspective_addressed"] == {
        "risks": 2, "stakeholders": 1,
    }
    assert agg["genre_distribution"] == {"analysis": 1, "advocacy": 1}
    assert agg["voice_distribution"] == {
        "analytical": 1, "prescriptive": 1,
    }
    assert agg["absence_cluster_dimension_fires"] == {"calibration": 1}
    # And the new field
    assert agg["frame_deepening_per_detector_fires"]["temporal_scope"] == 2
