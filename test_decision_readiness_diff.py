"""Tests for decision_readiness_diff.

Pins the contract for the per-dimension transformation diff:
- compute_diff returns None on missing/incomparable inputs
- Per-dimension change_text describes what changed
- Narrative names what changed (silent on dimensions that did
  not move)
- Methodology version mismatch produces None (cross-version
  diff would be misleading)
"""

from decision_readiness_diff import compute_diff


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def _profile(version="v0.1", **dim_overrides):
    """Build a minimal profile dict for testing. dim_overrides
    lets a test customize specific dimensions; everything else
    gets default values that pass the compute_diff guards."""
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
                "contradicted": 0, "disputed": 0, "checked": 0,
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
    """Empty profile, None, or non-dict input must return None.
    Calling code (the pair-diff harness) checks for None and
    skips the pair; an empty diff dict would be silently
    misleading."""
    print("=== compute_diff: None on empty/missing inputs ===")
    _check(compute_diff({}, _profile()) is None, "empty source -> None")
    _check(compute_diff(_profile(), {}) is None, "empty transformed -> None")
    _check(compute_diff(None, _profile()) is None, "None source -> None")
    _check(compute_diff(_profile(), None) is None, "None transformed -> None")
    _check(compute_diff("string", _profile()) is None, "non-dict source -> None")
    print("  PASS\n")


def test_returns_none_on_methodology_version_mismatch():
    """Cross-version diff would be misleading: signal semantics
    can change between methodology versions. Defend by returning
    None; the harness reports the skip explicitly."""
    print("=== compute_diff: None on methodology version mismatch ===")
    a = _profile(version="v0.1")
    b = _profile(version="v0.2")
    _check(compute_diff(a, b) is None,
           "version mismatch should return None")
    _check(compute_diff(_profile(), _profile()) is not None,
           "matching versions should return a diff")
    print("  PASS\n")


def test_diff_carries_per_dimension_change_text():
    """Every dimension in the diff must include a change_text
    sentence. The harness writes these to disk; downstream tools
    surface them verbatim."""
    print("=== compute_diff: per-dimension change_text present ===")
    diff = compute_diff(_profile(), _profile())
    _check(diff is not None, "diff should compute")
    for dim in ["coverage", "calibration", "evidence",
                "robustness", "counterfactual"]:
        _check(dim in diff["dimensions"],
               f"diff missing dimension {dim!r}")
        d = diff["dimensions"][dim]
        _check(d.get("change_text"),
               f"{dim} missing change_text")
        _check("source_value" in d and "transformed_value" in d,
               f"{dim} missing source_value/transformed_value")
    print("  PASS\n")


def test_coverage_change_names_dropped_dimensions():
    """When the transformation drops perspectives, the change_text
    must name them. This is the load-bearing signal for AI-response
    audit: 'the summary lost risks coverage'."""
    print("=== coverage change names dropped dimensions ===")
    src = _profile()
    xfm = _profile(coverage={
        "signal_value": 1,
        "covered": ["causes"],
        "missing": ["risks", "stakeholders", "trends", "uncertainty"],
    })
    diff = compute_diff(src, xfm)
    cov_text = diff["dimensions"]["coverage"]["change_text"]
    _check("3/5 -> 1/5" in cov_text,
           f"coverage delta should appear in text, got {cov_text!r}")
    _check("dropped" in cov_text.lower(),
           f"dropped-dimensions verb should appear, got {cov_text!r}")
    _check("risks" in cov_text and "stakeholders" in cov_text,
           f"dropped dimension names should be listed, got {cov_text!r}")
    print("  PASS\n")


def test_calibration_emergent_imbalance_is_visible():
    """When the LLM transformation INTRODUCES Confidence Imbalance
    where the source did not have it, the change_text must say so.
    This is the kind of finding the AI-response audit use case
    needs to surface."""
    print("=== calibration: emergent Confidence Imbalance visible ===")
    src = _profile()  # confidence_imbalance_fired: False
    xfm = _profile(calibration={
        "signal_value": 0.0, "claim_hedged": 0, "claim_unhedged": 7,
        "claim_total": 7, "confidence_imbalance_fired": True,
    })
    diff = compute_diff(src, xfm)
    cal_text = diff["dimensions"]["calibration"]["change_text"]
    _check("Confidence Imbalance pattern emerged" in cal_text,
           f"emergent imbalance should be named, got {cal_text!r}")
    print("  PASS\n")


def test_narrative_lists_what_changed():
    """The narrative is a synthesis sentence (or list) naming what
    moved. Dimensions that did not measurably move are NOT in the
    narrative, since listing every dimension would dilute the signal."""
    print("=== narrative: lists what moved, silent on stable ===")
    src = _profile()
    xfm = _profile(coverage={
        "signal_value": 1,
        "covered": ["causes"],
        "missing": ["risks", "stakeholders", "trends", "uncertainty"],
    })
    diff = compute_diff(src, xfm)
    narrative = diff["narrative"]
    _check("Coverage" in narrative,
           f"narrative should name moved dimension, got {narrative!r}")
    # Stable dimensions should not crowd the narrative
    _check("counterfactual thinking" not in narrative.lower()
           or "Both" not in narrative,
           "narrative should not include 'Both sides' filler text")
    print("  PASS\n")


def test_narrative_handles_no_movement():
    """When two profiles are identical, the narrative explicitly
    says all dimensions held steady, not 'no data'."""
    print("=== narrative: clear message when nothing changed ===")
    src = _profile()
    diff = compute_diff(src, src)  # diff against self
    narrative = diff["narrative"]
    _check(
        "held steady" in narrative.lower()
        or "unchanged" in narrative.lower(),
        f"identical profiles should produce a clear no-movement "
        f"narrative, got {narrative!r}",
    )
    print("  PASS\n")


def test_diff_metadata_carries_through():
    """The diff carries methodology_url, version, status, and the
    source/transformed labels + transformation_kind. Downstream
    consumers route off these fields."""
    print("=== diff metadata propagates from source profile ===")
    diff = compute_diff(
        _profile(),
        _profile(),
        source_label="src-doc",
        transformed_label="xfm-doc",
        transformation_kind="llm_summary",
    )
    _check(diff["methodology_url"] == "/corpus/decision-readiness/",
           "methodology_url should be present")
    _check(diff["methodology_version"] == "v0.1",
           "methodology_version should match the source")
    _check(diff["source_label"] == "src-doc",
           "source_label should round-trip")
    _check(diff["transformed_label"] == "xfm-doc",
           "transformed_label should round-trip")
    _check(diff["transformation_kind"] == "llm_summary",
           "transformation_kind should round-trip")
    print("  PASS\n")


def test_fired_pattern_gain_surfaces_in_diff():
    """A transformation that introduces a previously-absent named
    pattern (e.g., adds Frame Amplification by narrowing the
    document) must surface in the diff output. The detector-
    identified pattern is a load-bearing structural change that
    raw signal_value alone may not name. fired_patterns_gained
    carries the full canon-graph reference shape so a downstream
    consumer can chain to the canonical entry without re-lookup."""
    print("=== diff: fired-pattern gain surfaces in dimension diff ===")
    src = _profile()
    # Source has no fired patterns
    src["dimensions"]["coverage"]["fired_library_entries"] = []
    xfm = _profile()
    # Transformation introduces FVS-001 firing in coverage
    xfm["dimensions"]["coverage"]["fired_library_entries"] = [
        {
            "fvs_id": "FVS-001",
            "title": "Frame Amplification",
            "library_resource_uri": "frame-check://library/FVS-001",
            "public_url": "https://frame.clarethium.com/corpus/library/FVS-001.html",
        },
    ]
    diff = compute_diff(src, xfm)
    cov = diff["dimensions"]["coverage"]
    _check(
        cov["moved"] is True,
        f"coverage should report moved when fired pattern gained, "
        f"got {cov['moved']}",
    )
    gained = cov["fired_patterns_gained"]
    _check(
        len(gained) == 1 and gained[0]["fvs_id"] == "FVS-001",
        f"fired_patterns_gained should contain FVS-001, got {gained!r}",
    )
    _check(
        gained[0].get("title") == "Frame Amplification",
        f"gained ref must preserve full library_entry_ref shape "
        f"(title field), got {gained[0]!r}",
    )
    _check(
        cov["fired_patterns_lost"] == [],
        f"fired_patterns_lost should be empty, got "
        f"{cov['fired_patterns_lost']!r}",
    )
    _check(
        "transformation introduced detected pattern" in cov["change_text"]
        and "FVS-001" in cov["change_text"],
        f"change_text should name the introduced pattern, "
        f"got {cov['change_text']!r}",
    )
    print("  PASS\n")


def test_fired_pattern_loss_surfaces_in_diff():
    """A transformation that removes a previously-present pattern
    (e.g., a rewrite that resolves Failure Framing absent by adding
    risk language) must surface as a loss with its title preserved."""
    print("=== diff: fired-pattern loss surfaces in dimension diff ===")
    src = _profile()
    src["dimensions"]["counterfactual"]["fired_library_entries"] = [
        {
            "fvs_id": "FVS-007",
            "title": "Failure Framing",
            "library_resource_uri": "frame-check://library/FVS-007",
            "public_url": "https://frame.clarethium.com/corpus/library/FVS-007.html",
        },
    ]
    xfm = _profile()
    xfm["dimensions"]["counterfactual"]["fired_library_entries"] = []
    diff = compute_diff(src, xfm)
    cf = diff["dimensions"]["counterfactual"]
    _check(
        cf["moved"] is True,
        f"counterfactual should report moved when pattern lost",
    )
    _check(
        len(cf["fired_patterns_lost"]) == 1
        and cf["fired_patterns_lost"][0]["fvs_id"] == "FVS-007",
        f"fired_patterns_lost should contain FVS-007, got "
        f"{cf['fired_patterns_lost']!r}",
    )
    _check(
        cf["fired_patterns_gained"] == [],
        "fired_patterns_gained should be empty",
    )
    _check(
        "transformation removed detected pattern" in cf["change_text"],
        f"change_text should name the removed pattern, "
        f"got {cf['change_text']!r}",
    )
    print("  PASS\n")


def test_fired_pattern_unchanged_does_not_register_movement():
    """When source and transformed have the same fired patterns,
    no addendum or movement should fire from the pattern channel.
    Pins that the comparator does not produce noise when there's
    nothing to report."""
    print("=== diff: identical fired patterns do not register movement ===")
    src = _profile()
    src["dimensions"]["coverage"]["fired_library_entries"] = [
        {
            "fvs_id": "FVS-001", "title": "Frame Amplification",
            "library_resource_uri": "frame-check://library/FVS-001",
            "public_url": "https://frame.clarethium.com/corpus/library/FVS-001.html",
        },
    ]
    xfm = _profile()
    xfm["dimensions"]["coverage"]["fired_library_entries"] = [
        {
            "fvs_id": "FVS-001", "title": "Frame Amplification",
            "library_resource_uri": "frame-check://library/FVS-001",
            "public_url": "https://frame.clarethium.com/corpus/library/FVS-001.html",
        },
    ]
    diff = compute_diff(src, xfm)
    cov = diff["dimensions"]["coverage"]
    _check(
        cov["fired_patterns_gained"] == []
        and cov["fired_patterns_lost"] == [],
        f"unchanged fired patterns should produce empty gain/loss "
        f"lists; got gained={cov['fired_patterns_gained']!r} "
        f"lost={cov['fired_patterns_lost']!r}",
    )
    # signal values are also unchanged here, so moved should be False
    _check(
        "introduced detected pattern" not in cov["change_text"]
        and "removed detected pattern" not in cov["change_text"],
        f"change_text should not mention firing changes, "
        f"got {cov['change_text']!r}",
    )
    print("  PASS\n")


def test_old_profile_without_fired_field_is_backwards_compatible():
    """A profile produced by an older decision_readiness without
    fired_library_entries must not crash the diff. Result: no
    pattern movement registered (empty gain/loss); raw-signal diff
    still works. Pins that the field is treated as absent rather
    than crashing on missing key."""
    print("=== diff: old profiles without fired field do not crash ===")
    src = _profile()
    xfm = _profile()
    # Neither side has fired_library_entries field at all
    _check(
        "fired_library_entries" not in src["dimensions"]["coverage"],
        "fixture should not have fired_library_entries (test invariant)",
    )
    diff = compute_diff(src, xfm)
    cov = diff["dimensions"]["coverage"]
    _check(
        cov["fired_patterns_gained"] == []
        and cov["fired_patterns_lost"] == [],
        "missing fired_library_entries should produce empty lists, "
        "not crash",
    )
    print("  PASS\n")


if __name__ == "__main__":
    import sys
    try:
        test_returns_none_on_empty_inputs()
        test_returns_none_on_methodology_version_mismatch()
        test_diff_carries_per_dimension_change_text()
        test_coverage_change_names_dropped_dimensions()
        test_calibration_emergent_imbalance_is_visible()
        test_narrative_lists_what_changed()
        test_narrative_handles_no_movement()
        test_diff_metadata_carries_through()
        test_fired_pattern_gain_surfaces_in_diff()
        test_fired_pattern_loss_surfaces_in_diff()
        test_fired_pattern_unchanged_does_not_register_movement()
        test_old_profile_without_fired_field_is_backwards_compatible()
        print("=== ALL DECISION_READINESS_DIFF TESTS PASSED ===")
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
