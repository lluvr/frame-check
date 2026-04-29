"""Tests for decision_readiness_peer.

Pins the contract for non-directional peer comparison:
- compute_peer_comparison returns None on missing/incomparable inputs
- Per-dimension comparison_text uses non-directional language
  (does not say 'transformation did X')
- Narrative names dimensions where peers differ; silent on those
  that agree
- 'differs' flag drives the narrative filter correctly
- Methodology version mismatch returns None
"""

from decision_readiness_peer import compute_peer_comparison


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def _profile(version="v0.1", **dim_overrides):
    base = {
        "methodology_url": "/corpus/decision-readiness/",
        "methodology_version": version,
        "status": "experimental",
        "dimensions": {
            "coverage": {
                "name": "Coverage of perspectives",
                "signal_value": 3, "signal_secondary": 0.5,
                "covered": ["causes", "risks", "stakeholders"],
                "missing": ["trends", "uncertainty"],
            },
            "calibration": {
                "name": "Claim calibration",
                "signal_value": 0.4, "signal_secondary": 1,
                "claim_total": 5, "claim_hedged": 2,
                "claim_unhedged": 3, "claim_predictions": 1,
                "confidence_imbalance_fired": False,
            },
            "evidence": {
                "name": "Evidence backing",
                "signal_value": None, "signal_secondary": 30,
                "verified": 0, "checked": 0, "providers_count": 0,
                "sourced_pct": 30,
            },
            "robustness": {
                "name": "Robustness",
                "signal_value": 0, "signal_secondary": 0,
            },
            "counterfactual": {
                "name": "Counterfactual thinking",
                "signal_value": True, "signal_secondary": None,
                "failure_framing_absent": False,
                "uncertainty_addressed": True,
                "risks_addressed": True,
            },
        },
    }
    for dim, overrides in dim_overrides.items():
        base["dimensions"][dim].update(overrides)
    return base


def test_returns_none_on_empty_inputs():
    print("=== peer compare: None on empty inputs ===")
    _check(compute_peer_comparison({}, _profile()) is None, "empty A -> None")
    _check(compute_peer_comparison(_profile(), {}) is None, "empty B -> None")
    _check(compute_peer_comparison(None, _profile()) is None, "None A -> None")
    print("  PASS\n")


def test_returns_none_on_methodology_version_mismatch():
    print("=== peer compare: None on methodology version mismatch ===")
    _check(
        compute_peer_comparison(_profile(version="v0.1"), _profile(version="v0.2"))
        is None,
        "version mismatch -> None",
    )
    print("  PASS\n")


def test_per_dimension_comparison_text_is_non_directional():
    """Peer comparison must NOT use directional 'transformation
    did X' language. The comparison is between two independent
    peers; neither is a transformation of the other."""
    print("=== peer comparison_text uses non-directional language ===")
    a = _profile()
    b = _profile(coverage={
        "signal_value": 1,
        "covered": ["causes"],
        "missing": ["risks", "stakeholders", "trends", "uncertainty"],
    })
    cmp = compute_peer_comparison(a, b, label_a="claude", label_b="grok")
    cov_text = cmp["dimensions"]["coverage"]["comparison_text"]
    # Should not say 'transformation' anywhere
    _check(
        "transformation" not in cov_text.lower(),
        f"comparison text should NOT use 'transformation' wording: "
        f"{cov_text!r}",
    )
    # Should name BOTH labels
    _check(
        "claude" in cov_text and "grok" in cov_text,
        f"comparison should name both peer labels, got {cov_text!r}",
    )
    print("  PASS\n")


def test_narrative_lists_differing_dimensions_only():
    """The narrative must list only dimensions where the peers
    measurably differ. Listing all dimensions would dilute the
    signal a researcher needs to act on."""
    print("=== peer narrative: differs-only filter ===")
    a = _profile()
    # b matches a on most dimensions, differs only on coverage
    b = _profile(coverage={
        "signal_value": 1,
        "covered": ["causes"],
        "missing": ["risks", "stakeholders", "trends", "uncertainty"],
    })
    cmp = compute_peer_comparison(a, b, label_a="A", label_b="B")
    narrative = cmp["narrative"]
    _check(
        "Coverage" in narrative,
        f"narrative should name the differing dimension, got {narrative!r}",
    )
    # Counterfactual is identical (both engage); should not appear
    _check(
        "Both peers engage" not in narrative,
        f"narrative should not include unchanged-dimension filler "
        f"text, got {narrative!r}",
    )
    print("  PASS\n")


def test_narrative_handles_full_agreement():
    """When two peers produce structurally similar profiles, the
    narrative must say so explicitly (not silently produce an
    empty difference list)."""
    print("=== peer narrative: clear message when peers agree ===")
    cmp = compute_peer_comparison(_profile(), _profile(), "A", "B")
    narrative = cmp["narrative"]
    _check(
        "structurally similar" in narrative
        or "not measurable" in narrative.lower(),
        f"identical profiles should yield a clear no-difference "
        f"narrative, got {narrative!r}",
    )
    print("  PASS\n")


def test_counterfactual_asymmetry_named():
    """When only one peer engages with counterfactual thinking,
    the comparison must name WHICH peer engages and which does
    not. Symmetric language ('they differ') would lose the
    teaching point."""
    print("=== peer counterfactual: named asymmetry ===")
    a = _profile()  # counterfactual engages = True
    b = _profile(counterfactual={
        "signal_value": False,
        "failure_framing_absent": True,
        "uncertainty_addressed": False,
        "risks_addressed": False,
    })
    cmp = compute_peer_comparison(a, b, label_a="claude", label_b="grok")
    cf_text = cmp["dimensions"]["counterfactual"]["comparison_text"]
    _check(
        "Only claude engages" in cf_text,
        f"counterfactual asymmetry should name the engaging peer "
        f"by label, got {cf_text!r}",
    )
    _check(
        "grok does not" in cf_text,
        f"asymmetry should also name the non-engaging peer by "
        f"label, got {cf_text!r}",
    )
    print("  PASS\n")


def test_metadata_propagates():
    """The peer comparison output carries methodology metadata,
    both labels, and the peer group name so downstream consumers
    can route off these fields."""
    print("=== peer comparison: metadata propagates ===")
    cmp = compute_peer_comparison(
        _profile(), _profile(),
        label_a="claude", label_b="grok",
        peer_group="bitcoin_retirement_question",
    )
    _check(cmp["methodology_url"] == "/corpus/decision-readiness/",
           "methodology_url present")
    _check(cmp["methodology_version"] == "v0.1",
           "methodology_version matches source")
    _check(cmp["label_a"] == "claude", "label_a round-trips")
    _check(cmp["label_b"] == "grok", "label_b round-trips")
    _check(cmp["peer_group"] == "bitcoin_retirement_question",
           "peer_group round-trips")
    print("  PASS\n")


def test_fired_pattern_only_one_peer_surfaces_in_comparison():
    """Two peers with the same raw signal_value but different fired
    patterns should differ on those dimensions. Pattern-level
    asymmetry is a structural difference the raw values do not
    carry. Pins that the peer comparator surfaces fired_patterns
    only_a / only_b with full ref shape."""
    print("=== peer: fired-pattern asymmetry surfaces ===")
    a = _profile()
    a["dimensions"]["counterfactual"]["fired_library_entries"] = [
        {
            "fvs_id": "FVS-007", "title": "Failure Framing",
            "library_resource_uri": "frame-check://library/FVS-007",
            "public_url": "https://github.com/lluvr/frame-check-mcp/blob/master/data/frame_library/FVS-007_failure_framing.md",
        },
    ]
    b = _profile()
    b["dimensions"]["counterfactual"]["fired_library_entries"] = []
    cmp = compute_peer_comparison(
        a, b, label_a="claude", label_b="grok",
    )
    cf = cmp["dimensions"]["counterfactual"]
    _check(
        cf["differs"] is True,
        "counterfactual should report differs when one peer fires "
        "FVS-007 and the other does not, even with same raw signal",
    )
    _check(
        len(cf["fired_patterns_only_a"]) == 1
        and cf["fired_patterns_only_a"][0]["fvs_id"] == "FVS-007",
        f"only_a should contain FVS-007, got "
        f"{cf['fired_patterns_only_a']!r}",
    )
    _check(
        cf["fired_patterns_only_b"] == [],
        f"only_b should be empty, got {cf['fired_patterns_only_b']!r}",
    )
    _check(
        "only claude fires" in cf["comparison_text"]
        and "FVS-007" in cf["comparison_text"]
        and "Failure Framing" in cf["comparison_text"],
        f"comparison_text should name the asymmetric pattern with "
        f"its title, got {cf['comparison_text']!r}",
    )
    print("  PASS\n")


def test_fired_patterns_in_both_peers_does_not_register_difference():
    """When both peers fire the same pattern, that's NOT a peer
    difference. The non-directional comparator should report no
    asymmetry. Pins that the comparator does not produce noise."""
    print("=== peer: shared fired patterns do not register difference ===")
    fired_ref = {
        "fvs_id": "FVS-001", "title": "Frame Amplification",
        "library_resource_uri": "frame-check://library/FVS-001",
        "public_url": "https://github.com/lluvr/frame-check-mcp/blob/master/data/frame_library/FVS-001_frame_amplification.md",
    }
    a = _profile()
    a["dimensions"]["coverage"]["fired_library_entries"] = [fired_ref]
    b = _profile()
    b["dimensions"]["coverage"]["fired_library_entries"] = [fired_ref]
    cmp = compute_peer_comparison(a, b, label_a="claude", label_b="grok")
    cov = cmp["dimensions"]["coverage"]
    _check(
        cov["fired_patterns_only_a"] == [] and cov["fired_patterns_only_b"] == [],
        "shared fired patterns should produce empty asymmetry lists",
    )
    _check(
        "only claude fires" not in cov["comparison_text"]
        and "only grok fires" not in cov["comparison_text"],
        f"comparison_text should not name asymmetry, "
        f"got {cov['comparison_text']!r}",
    )
    print("  PASS\n")


def test_old_profiles_without_fired_field_do_not_break_peer():
    """Backwards compatibility: profiles without fired_library_entries
    must not crash the peer comparison. Result: empty asymmetry,
    raw-signal comparison still works."""
    print("=== peer: old profiles without fired field handled ===")
    a = _profile()
    b = _profile()
    cmp = compute_peer_comparison(a, b, label_a="claude", label_b="grok")
    cov = cmp["dimensions"]["coverage"]
    _check(
        cov["fired_patterns_only_a"] == [] and cov["fired_patterns_only_b"] == [],
        "missing fired_library_entries should produce empty lists",
    )
    print("  PASS\n")


if __name__ == "__main__":
    import sys
    try:
        test_returns_none_on_empty_inputs()
        test_returns_none_on_methodology_version_mismatch()
        test_per_dimension_comparison_text_is_non_directional()
        test_narrative_lists_differing_dimensions_only()
        test_narrative_handles_full_agreement()
        test_counterfactual_asymmetry_named()
        test_metadata_propagates()
        test_fired_pattern_only_one_peer_surfaces_in_comparison()
        test_fired_patterns_in_both_peers_does_not_register_difference()
        test_old_profiles_without_fired_field_do_not_break_peer()
        print("=== ALL DECISION_READINESS_PEER TESTS PASSED ===")
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
