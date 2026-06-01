"""Tests for the decision-readiness profile computation.

Pins the Phase 1.5 contract: compute_decision_readiness(display)
returns the structured five-dimension profile from existing
display measurements, or None when the display lacks the minimum
data needed.

The profile remains experimental until Phase 2 (expert validation)
lands; these tests pin the SHAPE of the output and the COMPOSITION
RULE (every dimension is derived from existing measurements, no
new signals invented). Validity of the dimensions themselves is a
Phase 2 concern.
"""

from decision_readiness import (
    compute_decision_readiness,
    METHODOLOGY_URL,
    METHODOLOGY_VERSION,
    PROFILE_STATUS,
)


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_returns_none_for_empty_display():
    """A display dict without framing has no coverage signal and
    cannot produce a meaningful profile. Returning None is the
    construct-honest choice; a fabricated profile from missing
    data would mislead the user."""
    print("=== compute_decision_readiness: None on empty display ===")
    _check(compute_decision_readiness({}) is None,
           "empty dict should yield None")
    _check(compute_decision_readiness(None) is None,
           "None input should yield None")
    _check(compute_decision_readiness({"display": {}}) is None,
           "display without framing should yield None")
    print("  PASS\n")


def test_dimensions_carry_library_entries_citations():
    """Each dimension in the profile must carry a library_entries
    list of OBJECTS referencing canonical FVS-IDs. Each object
    carries fvs_id + library_resource_uri + public_url so an MCP
    agent or HTTP consumer can chain to the named library entry
    without doing schema translation. Same shape as adjacent_frames
    in MCP responses; the canon graph is self-resolvable from any
    consumer."""
    print("=== profile dimensions carry library_entries citation objects ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 3, "covered": ["causes"]},
            "frame_suggestions": [],
        },
    }
    profile = compute_decision_readiness(display)
    _check(profile is not None, "profile should compute")
    for dim_name in ["coverage", "calibration", "evidence",
                     "robustness", "counterfactual"]:
        d = profile["dimensions"][dim_name]
        _check("library_entries" in d,
               f"{dim_name} missing library_entries field")
        _check(isinstance(d["library_entries"], list),
               f"{dim_name} library_entries is not a list")
        # Coverage and counterfactual always have multiple
        # entries; evidence/robustness have at least one
        # (FVS-016). Calibration has at least one (FVS-012).
        _check(len(d["library_entries"]) > 0,
               f"{dim_name} library_entries is empty; bidirectional "
               f"canon graph must surface at least one citation per "
               f"dimension")
        for ref in d["library_entries"]:
            _check(isinstance(ref, dict),
                   f"{dim_name} library_entries contains non-object: "
                   f"{ref!r}; canonical refs must be objects so the "
                   f"canon graph is self-resolvable")
            _check(
                "fvs_id" in ref
                and isinstance(ref["fvs_id"], str)
                and ref["fvs_id"].startswith("FVS-"),
                f"{dim_name} ref missing valid fvs_id: {ref!r}",
            )
            # MCP resource URI must use the frame-check scheme so
            # an agent receiving the profile can resources/read it
            # directly. Path matches mcp_server's library resource
            # exposure (frame-check://library/FVS-XXX).
            _check(
                ref.get("library_resource_uri", "").startswith(
                    "frame-check://library/"
                ),
                f"{dim_name} ref missing/invalid library_resource_uri: "
                f"{ref!r}; agents chain via this URI",
            )
            _check(
                ref["library_resource_uri"].endswith(ref["fvs_id"]),
                f"{dim_name} ref URI/fvs_id mismatch: {ref!r}",
            )
            # Public URL: HTTP consumers (browser, citation tools)
            # resolve here. Must be the canonical GitHub markdown URL
            # for the entry so citations are stable. Pin the
            # ID-presence invariant rather than the full filename so
            # adding entries or renaming slugs does not break this
            # test.
            public_url = ref.get("public_url") or ""
            _check(
                public_url.startswith(
                    "https://github.com/Clarethium/frame-check"
                    "/blob/master/data/frame_library/"
                )
                and f"{ref['fvs_id']}_" in public_url
                and public_url.endswith(".md"),
                f"{dim_name} ref missing/invalid public_url: {ref!r}",
            )
            # Title field: human-readable Name from INDEX.md so
            # consumers can render "FVS-007 Failure Framing" rather
            # than bare IDs. Field always present; falls back to
            # fvs_id when INDEX.md lookup misses.
            _check(
                "title" in ref and isinstance(ref["title"], str)
                and ref["title"],
                f"{dim_name} ref missing or empty title: {ref!r}",
            )
    print("  PASS\n")


def test_library_entry_ref_carries_indexed_title():
    """library_entry_ref must inject the human-readable Name from
    INDEX.md so consumers (MCP agents, aggregate findings, profile
    JSON readers) can render proper names without re-parsing
    INDEX.md themselves. FVS-007's title is "Failure Framing"
    (canonical, non-trivial check that the INDEX.md parser is wired
    correctly through to this function)."""
    print("=== library_entry_ref carries INDEX.md title ===")
    from decision_readiness import library_entry_ref
    ref = library_entry_ref("FVS-007")
    _check(
        ref.get("title") == "Failure Framing",
        f"FVS-007 should have title 'Failure Framing' from INDEX.md, "
        f"got {ref.get('title')!r}",
    )
    # Unknown FVS-IDs fall back to the bare ID rather than crashing
    # or returning None; agents iterating refs can rely on title
    # always being a non-empty string.
    fallback = library_entry_ref("FVS-999")
    _check(
        fallback.get("title") == "FVS-999",
        f"unknown FVS-ID should fall back title to bare ID, got "
        f"{fallback.get('title')!r}",
    )
    print("  PASS\n")


def test_corpus_entry_ref_shape_parallel_to_library_entry_ref():
    """corpus_entry_ref returns the canonical canon-graph reference
    object for validation corpus entries. Shape MUST be parallel to
    library_entry_ref's shape so the same canon-graph navigation
    pattern (identifier + title + resource_uri + public_url)
    applies across both namespaces.

    Parity means:
      library_entry_ref(fvs_id) and corpus_entry_ref(slug) both
      produce objects an MCP agent can chain on (resource_uri) and
      an HTTP consumer can follow (public_url), with a
      human-readable title for inline rendering.
    """
    print("=== corpus_entry_ref parallel to library_entry_ref ===")
    from decision_readiness import (
        corpus_entry_ref,
        library_entry_ref,
        LIBRARY_RESOURCE_SCHEME,
    )
    # Pin the URI scheme shared with library refs (frame-check://)
    ref = corpus_entry_ref(
        "four-llms-bitcoin-claude",
        title="Claude on whether to retire on Bitcoin",
    )
    _check(
        ref["slug"] == "four-llms-bitcoin-claude",
        f"slug field round-trips; got {ref!r}",
    )
    _check(
        ref["title"] == "Claude on whether to retire on Bitcoin",
        f"title field round-trips; got {ref!r}",
    )
    _check(
        ref["corpus_resource_uri"] == f"{LIBRARY_RESOURCE_SCHEME}://corpus/"
                                      f"four-llms-bitcoin-claude",
        f"corpus_resource_uri uses frame-check:// scheme + corpus/ "
        f"prefix; got {ref!r}",
    )
    _check(
        ref["public_url"].startswith("https://")
        and ref["public_url"].endswith("four-llms-bitcoin-claude/"),
        f"public_url should be HTTPS + end with slug/; got {ref!r}",
    )
    # Title falls back to slug when None; agents iterating can rely
    # on title always being a non-empty string (parity with
    # library_entry_ref's title fallback)
    fallback = corpus_entry_ref("unknown-slug")
    _check(
        fallback["title"] == "unknown-slug",
        f"title should fall back to slug when None; got {fallback!r}",
    )
    # Shape parity: both carry {identifier, title, namespaced
    # resource URI, public_url}. Identifiers and URI field names
    # are namespace-qualified (fvs_id + library_resource_uri vs
    # slug + corpus_resource_uri) which lets an agent iterating
    # refs tell which namespace it's in from field names alone.
    lib_ref = library_entry_ref("FVS-007")
    _check(
        "title" in ref and "public_url" in ref,
        f"corpus ref missing shared fields; got {sorted(ref.keys())!r}",
    )
    _check(
        "title" in lib_ref and "public_url" in lib_ref,
        f"library ref missing shared fields; got {sorted(lib_ref.keys())!r}",
    )
    _check(
        "corpus_resource_uri" in ref,
        f"corpus ref must have corpus_resource_uri (namespace-"
        f"qualified) to parallel library_resource_uri; got "
        f"{sorted(ref.keys())!r}",
    )
    _check(
        "library_resource_uri" in lib_ref,
        f"library ref must have library_resource_uri (namespace-"
        f"qualified); got {sorted(lib_ref.keys())!r}",
    )
    print("  PASS\n")


def test_fired_library_entries_empty_when_no_detector_fires():
    """Every dimension's fired_library_entries must be an empty
    LIST (not None, not absent) when the detector emitted no
    frame_suggestions. Empty is honest: the analysis ran, no
    canonically-mapped pattern fired. None would be ambiguous
    (could mean "we did not check") and missing the field would
    crash agent code that iterates it."""
    print("=== fired_library_entries: empty list when no detector fires ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 3, "covered": ["causes"]},
            "frame_suggestions": [],
        },
    }
    profile = compute_decision_readiness(display)
    for dim_name in ["coverage", "calibration", "evidence",
                     "robustness", "counterfactual"]:
        d = profile["dimensions"][dim_name]
        _check("fired_library_entries" in d,
               f"{dim_name} missing fired_library_entries field; "
               f"agents iterating this field would crash")
        _check(isinstance(d["fired_library_entries"], list),
               f"{dim_name} fired_library_entries must be a list, "
               f"got {type(d['fired_library_entries']).__name__}")
        _check(d["fired_library_entries"] == [],
               f"{dim_name} fired_library_entries should be empty "
               f"(no detectors fired), got {d['fired_library_entries']!r}")
    print("  PASS\n")


def test_fired_library_entries_surfaces_fvs010_in_coverage():
    """FVS-010 (Completeness Illusion) is a coverage-canonical
    library entry. When the detector emits FVS-010 in
    frame_suggestions, coverage.fired_library_entries must
    contain its canonical reference object, and ONLY coverage's
    list, not other dimensions' (FVS-010 is canon for coverage
    only). Validates the per-dimension filtering by canon graph."""
    print("=== fired_library_entries: FVS-010 surfaces in coverage only ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes", "trends"]},
            "frame_suggestions": [
                {"fvs_id": "FVS-010", "name": "Completeness Illusion"},
            ],
        },
    }
    profile = compute_decision_readiness(display)
    cov = profile["dimensions"]["coverage"]
    fvs_ids = [r["fvs_id"] for r in cov["fired_library_entries"]]
    _check(
        "FVS-010" in fvs_ids,
        f"coverage fired_library_entries should contain FVS-010 "
        f"when detector emits it, got {fvs_ids!r}",
    )
    # The fired ref must carry the full canon-graph shape (URI + URL)
    # so an agent receiving it can chain straight to resources/read.
    fired = next(r for r in cov["fired_library_entries"]
                 if r["fvs_id"] == "FVS-010")
    _check(
        fired.get("library_resource_uri") == "frame-check://library/FVS-010",
        f"firing ref missing/wrong library_resource_uri: {fired!r}",
    )
    _check(
        "FVS-010_" in (fired.get("public_url") or "")
        and (fired.get("public_url") or "").endswith(".md"),
        f"firing ref missing/wrong public_url: {fired!r}",
    )
    # FVS-010 is NOT in calibration/evidence/robustness/counterfactual
    # canon entries; fired_library_entries on those dimensions
    # must NOT contain FVS-010.
    for other_dim in ["calibration", "evidence", "robustness", "counterfactual"]:
        other_ids = [r["fvs_id"] for r in
                     profile["dimensions"][other_dim]["fired_library_entries"]]
        _check(
            "FVS-010" not in other_ids,
            f"FVS-010 leaked into {other_dim}.fired_library_entries "
            f"(should be canon-filtered to coverage only); got {other_ids!r}",
        )
    print("  PASS\n")


def test_fired_library_entries_surfaces_fvs008_in_coverage():
    """FVS-008 (Growth Frame) is a coverage-canonical entry.
    Pins that the detector-to-canon mapping holds for the second
    coverage detector (not just FVS-010), so the filtering is
    pattern, not coincidence."""
    print("=== fired_library_entries: FVS-008 surfaces in coverage ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 3, "covered": ["causes", "trends"]},
            "frame_suggestions": [
                {"fvs_id": "FVS-008", "name": "Growth Frame"},
            ],
        },
    }
    profile = compute_decision_readiness(display)
    cov = profile["dimensions"]["coverage"]
    fvs_ids = [r["fvs_id"] for r in cov["fired_library_entries"]]
    _check(
        "FVS-008" in fvs_ids,
        f"coverage fired_library_entries should contain FVS-008, "
        f"got {fvs_ids!r}",
    )
    print("  PASS\n")


def test_fired_library_entries_excludes_fvs002_in_calibration_due_to_canon_mismatch():
    """FVS-002 detector fires the calibration boolean
    (confidence_imbalance_fired) but FVS-002 is NOT in
    calibration's library_entries. The library entry FVS-002 is
    "Fluency-Quality Illusion" (meta-side, different concept).

    fired_library_entries must NOT contain FVS-002 even when the
    detector emits it; surfacing it would propagate the
    detector-vs-library naming mismatch into every per-document
    profile. The boolean still fires (existing behavior preserved
    for diff/peer logic and back-compat).

    This test pins the correct behavior of the canon-graph filter
    in the presence of the documented mismatch.
    """
    print("=== fired_library_entries: FVS-002 excluded (canon mismatch) ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 3, "covered": []},
            "frame_suggestions": [
                {"fvs_id": "FVS-002", "name": "Confidence Imbalance"},
            ],
        },
        "claims": {
            "total_claims": 8,
            "hedged_count": 1,
            "unhedged_count": 7,
            "prediction_count": 2,
        },
    }
    profile = compute_decision_readiness(display)
    cal = profile["dimensions"]["calibration"]
    # Boolean still fires (detector signal preserved)
    _check(
        cal["confidence_imbalance_fired"] is True,
        "confidence_imbalance_fired boolean must still reflect the "
        "detector signal regardless of canon graph",
    )
    # But fired_library_entries excludes FVS-002 (canon filter)
    fvs_ids = [r["fvs_id"] for r in cal["fired_library_entries"]]
    _check(
        "FVS-002" not in fvs_ids,
        f"calibration fired_library_entries must NOT contain "
        f"FVS-002 (detector-vs-library mismatch documented on "
        f"methodology page); got {fvs_ids!r}",
    )
    # Calibration's canon entries are FVS-012 + FVS-017; neither
    # detector exists yet, so the list is empty.
    _check(
        cal["fired_library_entries"] == [],
        f"calibration fired_library_entries should be empty when "
        f"only FVS-002 fires (no canon-aligned detector exists for "
        f"calibration yet); got {cal['fired_library_entries']!r}",
    )
    print("  PASS\n")


def test_fired_library_entries_surfaces_fvs007_in_counterfactual():
    """FVS-007 (Failure Framing) is canon for counterfactual AND
    has an existing detector. When the detector fires, BOTH the
    boolean AND the firing list reflect it (the two signals
    agree because the canon mapping is honest here)."""
    print("=== fired_library_entries: FVS-007 surfaces in counterfactual ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 2, "covered": ["causes"]},
            "frame_suggestions": [
                {"fvs_id": "FVS-007", "name": "Failure Framing (absent)"},
            ],
        },
    }
    profile = compute_decision_readiness(display)
    cf = profile["dimensions"]["counterfactual"]
    _check(
        cf["failure_framing_absent"] is True,
        "failure_framing_absent boolean should fire",
    )
    fvs_ids = [r["fvs_id"] for r in cf["fired_library_entries"]]
    _check(
        "FVS-007" in fvs_ids,
        f"counterfactual fired_library_entries should contain "
        f"FVS-007, got {fvs_ids!r}",
    )
    print("  PASS\n")


def test_fvs016_synthesizer_fires_under_conservative_threshold():
    """FVS-016 (Authority by Citation) is detected by decision_readiness
    itself (the detector layer doesn't have source_network access).
    Pins the firing rule from the library entry's Branch applicability:
    high sourced_pct + low verification rate + enough claims checked.

    Positive case:
      sourced_pct = 60 (substantial citation markers)
      checked = 5
      verified = 1 (verification_ratio = 0.2, well below 0.5)
    Result: FVS-016 fires in BOTH evidence AND robustness (canon
    membership in both dimensions), with full library_entry_ref shape."""
    print("=== FVS-016: synthesizer fires under conservative threshold ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 60},
            "frame_suggestions": [],
        },
        "source_network": {
            "checked": 5,
            "verified": 1,
            "contradicted": 0,
        },
    }
    profile = compute_decision_readiness(display)
    ev = profile["dimensions"]["evidence"]
    rob = profile["dimensions"]["robustness"]
    ev_ids = [r["fvs_id"] for r in ev["fired_library_entries"]]
    rob_ids = [r["fvs_id"] for r in rob["fired_library_entries"]]
    _check(
        "FVS-016" in ev_ids,
        f"FVS-016 should fire in evidence under (sourced_pct=60, "
        f"verified=1 of 5); got {ev_ids!r}",
    )
    _check(
        "FVS-016" in rob_ids,
        f"FVS-016 should ALSO fire in robustness (canon membership "
        f"in both dimensions); got {rob_ids!r}",
    )
    # Full ref shape preserved in both dimensions
    fired_ev = next(r for r in ev["fired_library_entries"]
                    if r["fvs_id"] == "FVS-016")
    _check(
        fired_ev.get("title") == "Authority by Citation",
        f"FVS-016 ref must carry title from INDEX.md, got {fired_ev!r}",
    )
    _check(
        fired_ev.get("library_resource_uri") == "frame-check://library/FVS-016",
        f"FVS-016 ref must carry library_resource_uri, got {fired_ev!r}",
    )
    print("  PASS\n")


def test_fvs016_synthesizer_does_not_fire_when_sourced_pct_low():
    """No citation markers (or sparse) means no Authority by Citation
    pattern. Pins the lower-bound guard."""
    print("=== FVS-016: does not fire when sourced_pct < 30 ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 20},  # below threshold
            "frame_suggestions": [],
        },
        "source_network": {"checked": 10, "verified": 1},
    }
    profile = compute_decision_readiness(display)
    ev_ids = [r["fvs_id"] for r in
              profile["dimensions"]["evidence"]["fired_library_entries"]]
    _check(
        "FVS-016" not in ev_ids,
        f"FVS-016 must not fire when sourced_pct=20 (no substantial "
        f"citation markers); got {ev_ids!r}",
    )
    print("  PASS\n")


def test_fvs016_synthesizer_does_not_fire_when_too_few_claims_checked():
    """checked < 3 means the verification ratio is statistically
    too noisy to compute. Pins the minimum-sample guard."""
    print("=== FVS-016: does not fire when checked < 3 ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 60},
            "frame_suggestions": [],
        },
        "source_network": {"checked": 2, "verified": 0},  # below threshold
    }
    profile = compute_decision_readiness(display)
    ev_ids = [r["fvs_id"] for r in
              profile["dimensions"]["evidence"]["fired_library_entries"]]
    _check(
        "FVS-016" not in ev_ids,
        f"FVS-016 must not fire when checked < 3 (ratio is too noisy); "
        f"got {ev_ids!r}",
    )
    print("  PASS\n")


def test_fvs016_synthesizer_does_not_fire_when_verification_high():
    """When most checked claims DO verify, the citation-form signal
    matches citation substance. The pattern requires the GAP."""
    print("=== FVS-016: does not fire when verification_ratio > 0.5 ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 60},
            "frame_suggestions": [],
        },
        "source_network": {"checked": 5, "verified": 4},  # 80% verify
    }
    profile = compute_decision_readiness(display)
    ev_ids = [r["fvs_id"] for r in
              profile["dimensions"]["evidence"]["fired_library_entries"]]
    _check(
        "FVS-016" not in ev_ids,
        f"FVS-016 must not fire when verification_ratio > 0.5 "
        f"(citations verify; no authority-by-citation pattern); "
        f"got {ev_ids!r}",
    )
    print("  PASS\n")


def test_fvs016_threshold_boundaries_inclusive():
    """Pin exact boundary behavior so a future tuning of thresholds
    moves the boundary deliberately rather than discovering it by
    surprise. The current rule per the synthesizer:
      - sourced_pct >= 30          (boundary INCLUSIVE)
      - checked >= 3                (boundary INCLUSIVE)
      - verification_ratio <= 0.5   (boundary INCLUSIVE)

    All three boundaries fire (i.e., trigger FVS-016) when met
    exactly; one notch below any of them and the synthesizer
    short-circuits."""
    print("=== FVS-016: boundary values are inclusive (fire at exact) ===")
    # Boundary case: every threshold met EXACTLY. Should fire.
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 30},  # at threshold
            "frame_suggestions": [],
        },
        "source_network": {
            "checked": 3,  # at threshold
            "verified": 1,  # 1/3 = 0.333...
        },
    }
    profile = compute_decision_readiness(display)
    ev_ids = [r["fvs_id"] for r in
              profile["dimensions"]["evidence"]["fired_library_entries"]]
    _check(
        "FVS-016" in ev_ids,
        f"FVS-016 should fire at sourced_pct==30, checked==3, "
        f"ratio<0.5; got {ev_ids!r}",
    )
    # Verification ratio EXACTLY at 0.5 (verified=1, checked=2 would
    # be 0.5 but checked < 3; use verified=2 of checked=4 which is
    # 0.5 exactly with checked >= 3).
    display["source_network"] = {"checked": 4, "verified": 2}
    profile = compute_decision_readiness(display)
    ev_ids = [r["fvs_id"] for r in
              profile["dimensions"]["evidence"]["fired_library_entries"]]
    _check(
        "FVS-016" in ev_ids,
        f"FVS-016 should fire at verification_ratio==0.5 exactly; "
        f"got {ev_ids!r}",
    )
    # One notch above 0.5: 3 of 5 = 0.6. Should NOT fire.
    display["source_network"] = {"checked": 5, "verified": 3}
    profile = compute_decision_readiness(display)
    ev_ids = [r["fvs_id"] for r in
              profile["dimensions"]["evidence"]["fired_library_entries"]]
    _check(
        "FVS-016" not in ev_ids,
        f"FVS-016 should NOT fire at verification_ratio==0.6 (above "
        f"0.5 ceiling); got {ev_ids!r}",
    )
    print("  PASS\n")


def test_fvs016_firing_augments_evidence_robustness_signal_text():
    """When FVS-016 fires, evidence + robustness signal_text must
    gain the prose mention "Authority by Citation pattern detected
    (FVS-016)". This mirrors the existing convention (calibration
    mentions FVS-002 in prose, counterfactual mentions FVS-007).

    Why prose matters: the MCP sovereignty prompts instruct agents
    to "name each dimension by its signal_text reading"; agents
    that consume the prose channel without iterating
    fired_library_entries get the named pattern automatically. The
    structured field carries the chain affordance; the prose
    carries the name."""
    print("=== FVS-016: signal_text gains prose mention when firing ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 60},
            "frame_suggestions": [],
        },
        "source_network": {"checked": 5, "verified": 1},
    }
    profile = compute_decision_readiness(display)
    ev_text = profile["dimensions"]["evidence"]["signal_text"]
    rob_text = profile["dimensions"]["robustness"]["signal_text"]
    _check(
        "Authority by Citation pattern detected (FVS-016)" in ev_text,
        f"evidence signal_text should mention FVS-016 firing in prose; "
        f"got {ev_text!r}",
    )
    _check(
        "Authority by Citation pattern detected (FVS-016)" in rob_text,
        f"robustness signal_text should mention FVS-016 firing in prose; "
        f"got {rob_text!r}",
    )
    # Pre-existing signal_text content must still be present (the
    # augmentation appends, doesn't replace).
    _check(
        "1 of 5 numerical claims source-verified" in ev_text,
        f"evidence signal_text augmentation must preserve original "
        f"content; got {ev_text!r}",
    )
    print("  PASS\n")


def test_fvs016_does_not_augment_signal_text_when_not_firing():
    """When FVS-016 doesn't fire (e.g., low sourced_pct), evidence
    and robustness signal_text must NOT contain the Authority by
    Citation prose. Prevents false-positive prose that would
    mislead agents reading signal_text alone."""
    print("=== FVS-016: signal_text NOT augmented when pattern absent ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": ["causes"]},
            "epistemic": {"sourced_pct": 10},  # below firing threshold
            "frame_suggestions": [],
        },
        "source_network": {"checked": 5, "verified": 1},
    }
    profile = compute_decision_readiness(display)
    ev_text = profile["dimensions"]["evidence"]["signal_text"]
    rob_text = profile["dimensions"]["robustness"]["signal_text"]
    _check(
        "Authority by Citation" not in ev_text,
        f"evidence signal_text must NOT mention Authority by Citation "
        f"when FVS-016 didn't fire; got {ev_text!r}",
    )
    _check(
        "Authority by Citation" not in rob_text,
        f"robustness signal_text must NOT mention Authority by Citation "
        f"when FVS-016 didn't fire; got {rob_text!r}",
    )
    print("  PASS\n")


def test_fvs016_synthesizer_does_not_mutate_callers_framing():
    """Synthesis happens against a shallow copy of framing so the
    caller's display dict is unaffected. Other code that reads
    display.framing.frame_suggestions must NOT see the synthesized
    FVS-016 entry unless it explicitly opts in. Pins purity."""
    print("=== FVS-016: synthesis does not mutate caller's framing ===")
    framing_in = {
        "coverage": {"coverage_count": 4, "covered": ["causes"]},
        "epistemic": {"sourced_pct": 60},
        "frame_suggestions": [{"fvs_id": "FVS-008", "name": "Growth"}],
    }
    display = {
        "framing": framing_in,
        "source_network": {"checked": 5, "verified": 1},
    }
    compute_decision_readiness(display)
    # framing.frame_suggestions should still contain ONLY the
    # original detector emission, not the synthesized FVS-016.
    suggestions_after = framing_in["frame_suggestions"]
    fvs_ids_after = {s.get("fvs_id") for s in suggestions_after}
    _check(
        fvs_ids_after == {"FVS-008"},
        f"caller's frame_suggestions must be unchanged after "
        f"compute_decision_readiness; got {fvs_ids_after!r}",
    )
    _check(
        len(suggestions_after) == 1,
        f"caller's frame_suggestions length must be unchanged; "
        f"got {len(suggestions_after)}",
    )
    print("  PASS\n")


def test_real_detector_output_flows_into_fired_library_entries():
    """Integration pin: run the ACTUAL detector layer
    (frame_library.suggest_frames) on inputs designed to trigger
    FVS-008 (Growth Frame), then verify that the resulting
    frame_suggestions integrate cleanly into compute_decision_readiness's
    fired_library_entries field.

    The other fired_library_entries tests use synthetic
    frame_suggestions dicts. This test exercises the END-TO-END
    flow: detector -> frame_suggestions -> decision_readiness ->
    fired_library_entries. A regression in suggest_frames'
    emission shape (e.g., field rename, removal of FVS-008
    detector) would break agent chaining and is invisible to the
    synthetic-input tests.

    FVS-008 (Growth Frame) is a stable detector anchor: triggered
    by high trends density + low risks density in business-domain
    documents. It is canon for coverage."""
    print("=== integration: real detector output flows to fired_library_entries ===")
    from frame_library import suggest_frames
    # Inputs designed to fire FVS-008. Pattern from frame_library.py
    # _DEFINITIONS for FVS-008 + the suggest_frames Growth Frame
    # branch: trends-density present + risks-density absent +
    # promotional/prescriptive voice. total_sentences >= 5 so the
    # short-document guard does not suppress.
    coverage = {
        "covered": ["trends", "causes"],
        "missing": ["risks", "stakeholders", "uncertainty"],
        "categories": {
            "trends": {"density_per_1kw": 15, "matched_keywords": ["growth", "increase"]},
            "causes": {"density_per_1kw": 8, "matched_keywords": ["because"]},
            "risks": {"density_per_1kw": 0, "matched_keywords": []},
            "stakeholders": {"density_per_1kw": 0, "matched_keywords": []},
            "uncertainty": {"density_per_1kw": 0, "matched_keywords": []},
        },
    }
    voice = {"voice": "promotional", "total_sentences": 12}
    temporal = {"present_dominant": True}
    epistemic = {"sourced_pct": 10}
    # Run the real detector. FVS-008 requires text alongside the
    # structural signal; pass minimal growth-vocab text so the rule
    # fires on this trends-dominant business-domain input.
    business_growth_text = (
        "Revenue grew by 30 percent year over year. Market expansion "
        "drove customer adoption across the new segments."
    )
    frame_suggestions = suggest_frames(
        coverage, voice, temporal, epistemic, text=business_growth_text,
    )
    fvs_ids = {s["fvs_id"] for s in frame_suggestions}
    _check(
        "FVS-008" in fvs_ids,
        f"detector regression: suggest_frames should emit FVS-008 "
        f"for trends-dominant business-domain inputs; got {fvs_ids!r}",
    )
    # Now feed into compute_decision_readiness via the display dict
    display = {
        "framing": {
            "coverage": coverage,
            "frame_suggestions": frame_suggestions,
            "epistemic": epistemic,
        },
    }
    profile = compute_decision_readiness(display)
    cov_fired = [
        r["fvs_id"]
        for r in profile["dimensions"]["coverage"]["fired_library_entries"]
    ]
    _check(
        "FVS-008" in cov_fired,
        f"integration regression: FVS-008 emitted by detector "
        f"must surface in coverage.fired_library_entries; got "
        f"{cov_fired!r}",
    )
    # And the title is preserved through the full pipeline
    fired_ref = next(
        r for r in profile["dimensions"]["coverage"]["fired_library_entries"]
        if r["fvs_id"] == "FVS-008"
    )
    _check(
        fired_ref.get("title") == "Growth Frame",
        f"title from INDEX.md must flow through end-to-end; got "
        f"{fired_ref!r}",
    )
    print("  PASS\n")


def test_library_resource_scheme_matches_mcp_server():
    """The decision_readiness module emits library_resource_uri
    strings prefixed with frame-check://. The MCP server defines
    its own RESOURCE_SCHEME; if these drift, agents reading
    library_resource_uri from the profile try to chain via a URI
    the MCP server does not recognize. Pin agreement so a future
    rename of either constant fails this test instead of silently
    breaking the canon-graph chain."""
    print("=== canon-graph URI scheme: profile <-> MCP server agreement ===")
    import sys as _sys
    from pathlib import Path as _Path
    repo_root = _Path(__file__).resolve().parent.parent
    _sys.path.insert(0, str(repo_root))
    try:
        from decision_readiness import LIBRARY_RESOURCE_SCHEME as dr_scheme
        # Read the MCP server's RESOURCE_SCHEME source. Since the
        # Step 2 decomposition (2026-04-29), the constant lives in
        # mcp_resources.py rather than mcp_server.py; mcp_server
        # imports it back via the re-export pattern. Source-grep
        # remains the lightweight pin (avoids importing the whole
        # module which would run import-time side effects in the
        # test environment).
        mcp_src = (repo_root / "src" / "mcp_resources.py").read_text(encoding="utf-8")
    finally:
        _sys.path.pop(0)

    import re as _re
    m = _re.search(r'RESOURCE_SCHEME\s*=\s*["\']([^"\']+)["\']', mcp_src)
    _check(m is not None,
           "could not locate RESOURCE_SCHEME assignment in mcp_resources.py")
    mcp_scheme = m.group(1)
    _check(
        dr_scheme == mcp_scheme,
        f"URI scheme drift: decision_readiness.LIBRARY_RESOURCE_SCHEME="
        f"{dr_scheme!r} but mcp_server.RESOURCE_SCHEME={mcp_scheme!r}. "
        f"Agents chaining from profile.library_entries via the URI "
        f"would hit a scheme the MCP server does not recognize.",
    )
    print(f"  PASS  (both = {dr_scheme!r})\n")


def test_emits_full_structure_with_framing():
    """A display with framing data should produce all five
    dimensions plus the methodology metadata."""
    print("=== compute_decision_readiness: full structure shape ===")
    display = {
        "framing": {
            "coverage": {
                "coverage_count": 4,
                "total_categories": 5,
                "coverage_balance": 0.32,
                "covered": ["causes", "risks", "stakeholders", "trends"],
                "missing": ["uncertainty"],
            },
            "epistemic": {"sourced_pct": 45},
            "frame_suggestions": [],
        },
        "claims": {
            "total_claims": 7,
            "hedged_count": 3,
            "unhedged_count": 4,
            "prediction_count": 1,
        },
        "source_network": {
            "checked": 5,
            "verified": 2,
            "contradicted": 1,
            "disputed": 0,
            "verified_providers": [
                {"name": "SEC Filing", "tier": "strong", "f1": 0.91, "count": 2},
            ],
        },
    }
    profile = compute_decision_readiness(display)
    _check(profile is not None, "should produce profile")
    _check(profile["methodology_url"] == METHODOLOGY_URL,
           "methodology_url field missing or wrong")
    _check(profile["methodology_version"] == METHODOLOGY_VERSION,
           "methodology_version field missing or wrong")
    _check(profile["status"] == PROFILE_STATUS,
           "status field missing or wrong")
    dims = profile["dimensions"]
    for required_dim in [
        "coverage", "calibration", "evidence",
        "robustness", "counterfactual",
    ]:
        _check(required_dim in dims,
               f"dimension {required_dim!r} missing from profile")
        d = dims[required_dim]
        _check("name" in d and d["name"],
               f"{required_dim} missing 'name'")
        _check("signal_text" in d and d["signal_text"],
               f"{required_dim} missing 'signal_text'")
        _check("explanation" in d and d["explanation"],
               f"{required_dim} missing 'explanation'")
    print("  PASS\n")


def test_coverage_dimension_reads_from_existing_signals():
    """Coverage dimension must reflect coverage_count / balance /
    covered / missing without inventing new fields."""
    print("=== coverage dimension: derives from existing fields ===")
    display = {
        "framing": {
            "coverage": {
                "coverage_count": 3,
                "total_categories": 5,
                "coverage_balance": 0.18,
                "covered": ["causes", "trends", "risks"],
                "missing": ["stakeholders", "uncertainty"],
            },
            "frame_suggestions": [],
        },
    }
    profile = compute_decision_readiness(display)
    cov = profile["dimensions"]["coverage"]
    _check(cov["signal_value"] == 3,
           f"coverage signal_value should be 3, got {cov['signal_value']}")
    _check(cov["signal_secondary"] == 0.18,
           f"coverage secondary should be 0.18, got {cov['signal_secondary']}")
    _check("3 of 5 perspectives addressed" in cov["signal_text"],
           f"coverage text should name count, got {cov['signal_text']!r}")
    _check("18%" in cov["signal_text"],
           f"coverage text should include balance pct, got {cov['signal_text']!r}")
    _check(cov["covered"] == ["causes", "trends", "risks"],
           "covered list should be passed through")
    _check(cov["missing"] == ["stakeholders", "uncertainty"],
           "missing list should be passed through")
    print("  PASS\n")


def test_calibration_dimension_handles_zero_claims():
    """When the document has no extracted claims, the calibration
    dimension should NOT divide-by-zero or invent a hedge ratio."""
    print("=== calibration dimension: zero-claim guard ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": []},
            "frame_suggestions": [],
        },
        "claims": {
            "total_claims": 0,
            "hedged_count": 0,
            "unhedged_count": 0,
            "prediction_count": 0,
        },
    }
    profile = compute_decision_readiness(display)
    cal = profile["dimensions"]["calibration"]
    _check(cal["signal_value"] is None,
           f"hedge ratio with 0 claims should be None, got {cal['signal_value']}")
    _check("No claims extracted" in cal["signal_text"]
           or "no claims extracted" in cal["signal_text"].lower(),
           f"text should name the empty case, got {cal['signal_text']!r}")
    print("  PASS\n")


def test_calibration_flags_confidence_imbalance_pattern():
    """When FVS-002 (Confidence Imbalance) fires in frame_suggestions,
    the calibration dimension should surface that fact in its
    signal_text so the user sees not just the hedge ratio but the
    pattern detection alongside it."""
    print("=== calibration dimension: surfaces FVS-002 detection ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": []},
            "frame_suggestions": [
                {"fvs_id": "FVS-002", "name": "Confidence Imbalance"},
            ],
        },
        "claims": {
            "total_claims": 8,
            "hedged_count": 1,
            "unhedged_count": 7,
            "prediction_count": 2,
        },
    }
    profile = compute_decision_readiness(display)
    cal = profile["dimensions"]["calibration"]
    _check(cal["confidence_imbalance_fired"] is True,
           "FVS-002 detection should be reflected in dimension")
    _check("Confidence Imbalance" in cal["signal_text"],
           f"calibration text should mention the fired pattern, "
           f"got {cal['signal_text']!r}")
    print("  PASS\n")


def test_evidence_dimension_combines_verification_and_attribution():
    """Evidence backing should expose BOTH the source-verification
    ratio (numerical claims) AND the sentence-level attribution
    percentage. They are different proxies for the same construct
    (evidence backing) and the user benefits from seeing both."""
    print("=== evidence dimension: verification + attribution combined ===")
    display = {
        "framing": {
            "coverage": {"coverage_count": 4, "covered": []},
            "epistemic": {"sourced_pct": 60},
            "frame_suggestions": [],
        },
        "source_network": {
            "checked": 5,
            "verified": 3,
            "contradicted": 0,
            "verified_providers": [
                {"name": "SEC Filing", "tier": "strong", "f1": 0.91, "count": 2},
                {"name": "Wikipedia", "tier": "moderate", "f1": 0.74, "count": 1},
            ],
        },
    }
    profile = compute_decision_readiness(display)
    ev = profile["dimensions"]["evidence"]
    _check(abs(ev["signal_value"] - 0.6) < 0.001,
           f"verification ratio should be 0.6, got {ev['signal_value']}")
    _check(ev["signal_secondary"] == 60,
           f"sourced_pct should be 60, got {ev['signal_secondary']}")
    _check("3 of 5 numerical claims source-verified" in ev["signal_text"],
           f"evidence text should name verification ratio, "
           f"got {ev['signal_text']!r}")
    _check("60% of sentences attributed" in ev["signal_text"],
           f"evidence text should name attribution %, "
           f"got {ev['signal_text']!r}")
    _check("2 providers" in ev["signal_text"],
           f"evidence text should name provider count, "
           f"got {ev['signal_text']!r}")
    print("  PASS\n")


def test_robustness_dimension_handles_clean_and_dirty():
    """Robustness dimension should distinguish clean (no
    contradictions) from dirty (contradictions present) and
    surface both raw counts."""
    print("=== robustness dimension: clean vs dirty handling ===")
    # Clean: 5 checked, 0 contradicted
    display_clean = {
        "framing": {"coverage": {"coverage_count": 4, "covered": []}, "frame_suggestions": []},
        "source_network": {"checked": 5, "verified": 5, "contradicted": 0, "disputed": 0},
    }
    profile_clean = compute_decision_readiness(display_clean)
    rob_clean = profile_clean["dimensions"]["robustness"]
    _check(rob_clean["signal_value"] == 0,
           f"clean robustness signal should be 0, got {rob_clean['signal_value']}")
    _check("no contradictions" in rob_clean["signal_text"].lower(),
           f"clean text should say no contradictions, got {rob_clean['signal_text']!r}")

    # Dirty: 5 checked, 2 contradicted
    display_dirty = {
        "framing": {"coverage": {"coverage_count": 4, "covered": []}, "frame_suggestions": []},
        "source_network": {"checked": 5, "verified": 2, "contradicted": 2, "disputed": 1},
    }
    profile_dirty = compute_decision_readiness(display_dirty)
    rob_dirty = profile_dirty["dimensions"]["robustness"]
    _check(rob_dirty["signal_value"] == 3,
           f"dirty robustness should be 3 (2+1), got {rob_dirty['signal_value']}")
    _check("3 of 5 checked claims" in rob_dirty["signal_text"],
           f"dirty text should name fail count, got {rob_dirty['signal_text']!r}")
    print("  PASS\n")


def test_counterfactual_dimension_composes_signals():
    """Counterfactual thinking should compose: failure-framing
    absent (FVS-007) + uncertainty/risks coverage. The composite
    signal is True only when the document engages with at least
    one positive signal AND the failure-framing absent pattern
    does NOT fire."""
    print("=== counterfactual dimension: composite signal logic ===")
    # Engaged: uncertainty addressed, FVS-007 not fired
    display_engaged = {
        "framing": {
            "coverage": {
                "coverage_count": 4,
                "covered": ["causes", "risks", "uncertainty", "stakeholders"],
            },
            "frame_suggestions": [],
        },
    }
    profile = compute_decision_readiness(display_engaged)
    cf = profile["dimensions"]["counterfactual"]
    _check(cf["signal_value"] is True,
           f"engaged document should signal True, got {cf['signal_value']}")
    _check(cf["uncertainty_addressed"] is True,
           "uncertainty_addressed should be True")
    _check(cf["risks_addressed"] is True,
           "risks_addressed should be True")
    _check(cf["failure_framing_absent"] is False,
           "failure_framing_absent should be False (no FVS-007)")

    # Disengaged: FVS-007 fires
    display_disengaged = {
        "framing": {
            "coverage": {
                "coverage_count": 3,
                "covered": ["causes", "trends", "stakeholders"],
            },
            "frame_suggestions": [
                {"fvs_id": "FVS-007", "name": "Failure Framing (absent)"},
            ],
        },
    }
    profile = compute_decision_readiness(display_disengaged)
    cf = profile["dimensions"]["counterfactual"]
    _check(cf["signal_value"] is False,
           f"disengaged document should signal False, got {cf['signal_value']}")
    _check(cf["failure_framing_absent"] is True,
           "failure_framing_absent should be True when FVS-007 fires")
    _check("Failure Framing absent" in cf["signal_text"],
           f"disengaged text should name FVS-007 firing, "
           f"got {cf['signal_text']!r}")
    print("  PASS\n")


def test_profile_status_reflects_pre_validation_phase():
    """The profile status field must say 'experimental' until
    Phase 2 validation lands. This is the contract that justifies
    keeping the profile out of the UI surface."""
    print("=== profile status: experimental until validated ===")
    _check(PROFILE_STATUS == "experimental",
           f"PROFILE_STATUS should be 'experimental' pre-Phase 2, "
           f"got {PROFILE_STATUS!r}")
    print("  PASS\n")


def test_aggregate_outlier_counts_by_llm_emits_sorted_keys():
    """Pin the byte-stability invariant on validation/decision_readiness/
    aggregate_corpus_findings.py::_aggregate_outlier_counts_by_llm.

    The function builds per-LLM dicts via Counter + defaultdict from a
    set iteration (group_members), which is non-deterministic in hash
    order. Without explicit sort-at-emission, re-runs on identical
    inputs produce different key orders and noise diffs in git. Sort
    is applied at the emission boundary. This test pins the invariant:
    appearances_per_llm, outlier_counts_per_llm, and
    non_comparable_per_llm all emit keys in alphabetical order.
    """
    print("=== aggregate_outlier_counts_by_llm emits sorted keys ===")
    import sys
    import pathlib
    harness_path = pathlib.Path(__file__).parent.parent / "validation" / "decision_readiness"
    if not (harness_path / "aggregate_corpus_findings.py").exists():
        # The harness is upstream-only: `validation/decision_readiness/`
        # Python files are excluded from the public extract per
        # `setup.py::_should_skip`. Skip cleanly on the public mirror
        # rather than ImportError-failing the suite.
        print(f"  SKIP (harness {harness_path}/aggregate_corpus_findings.py not present; upstream-only module)\n")
        return
    sys.path.insert(0, str(harness_path))
    try:
        import aggregate_corpus_findings as acf
    finally:
        sys.path.pop(0)

    # Synthesize per_group_outliers input. Two groups; one LLM per
    # group is the outlier on some dimensions. Insertion order here
    # does NOT match alphabetical; the function must still emit sorted.
    sample = {
        "group1": {
            dim: {
                "values_by_member": {
                    "startup-grok": None,
                    "startup-claude": None,
                    "startup-openai": None,
                    "startup-gemini": None,
                },
                "outliers": ["startup-grok"] if dim == "coverage" else [],
                "non_comparable": dim == "evidence",
            }
            for dim in acf.DIMENSIONS
        },
        "group2": {
            dim: {
                "values_by_member": {
                    "bitcoin-openai": None,
                    "bitcoin-claude": None,
                    "bitcoin-gemini": None,
                    "bitcoin-grok": None,
                },
                "outliers": ["bitcoin-claude"] if dim == "calibration" else [],
                "non_comparable": False,
            }
            for dim in acf.DIMENSIONS
        },
    }

    result = acf._aggregate_outlier_counts_by_llm(sample)

    for field in ("appearances_per_llm", "outlier_counts_per_llm", "non_comparable_per_llm"):
        keys = list(result[field].keys())
        _check(
            keys == sorted(keys),
            f"{field} keys must be alphabetical; got {keys!r}",
        )
    print(f"  {list(result['appearances_per_llm'].keys())}")
    print("  PASS\n")


if __name__ == "__main__":
    try:
        test_returns_none_for_empty_display()
        test_emits_full_structure_with_framing()
        test_dimensions_carry_library_entries_citations()
        test_library_entry_ref_carries_indexed_title()
        test_corpus_entry_ref_shape_parallel_to_library_entry_ref()
        test_fired_library_entries_empty_when_no_detector_fires()
        test_fired_library_entries_surfaces_fvs010_in_coverage()
        test_fired_library_entries_surfaces_fvs008_in_coverage()
        test_fired_library_entries_excludes_fvs002_in_calibration_due_to_canon_mismatch()
        test_fired_library_entries_surfaces_fvs007_in_counterfactual()
        test_fvs016_synthesizer_fires_under_conservative_threshold()
        test_fvs016_synthesizer_does_not_fire_when_sourced_pct_low()
        test_fvs016_synthesizer_does_not_fire_when_too_few_claims_checked()
        test_fvs016_synthesizer_does_not_fire_when_verification_high()
        test_fvs016_threshold_boundaries_inclusive()
        test_fvs016_firing_augments_evidence_robustness_signal_text()
        test_fvs016_does_not_augment_signal_text_when_not_firing()
        test_fvs016_synthesizer_does_not_mutate_callers_framing()
        test_real_detector_output_flows_into_fired_library_entries()
        test_library_resource_scheme_matches_mcp_server()
        test_coverage_dimension_reads_from_existing_signals()
        test_calibration_dimension_handles_zero_claims()
        test_calibration_flags_confidence_imbalance_pattern()
        test_evidence_dimension_combines_verification_and_attribution()
        test_robustness_dimension_handles_clean_and_dirty()
        test_counterfactual_dimension_composes_signals()
        test_profile_status_reflects_pre_validation_phase()
        test_aggregate_outlier_counts_by_llm_emits_sorted_keys()
        print("=== ALL DECISION_READINESS TESTS PASSED ===")
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        import sys
        sys.exit(1)
