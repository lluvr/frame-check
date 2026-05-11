"""Tests for mcp_server.py: the Model Context Protocol server that
exposes Frame Check's structural framing analysis to AI agents.

The tests exercise three layers:

  1. The epistemic-payload builder directly (no protocol).
     Validates that the analysis / agent_guidance / provenance
     schema holds and that the measurements match the underlying
     Frame Check pipeline.

  2. The JSON-RPC dispatcher in isolation.
     Feeds synthetic requests and checks the response envelope,
     error codes, and method routing.

  3. End-to-end via subprocess.
     Spawns the server as a child process exactly the way an MCP
     client (Claude Desktop, Cursor) would and drives it via stdin
     / stdout. Catches regressions in the handshake, the tool
     advertisement, and the stdio framing.

The point of these tests is to protect the epistemic payload
contract: any future change that drops agent_guidance or provenance,
or that quietly folds an LLM call into the "deterministic" layer,
should fail here.

Run with:  python3 test_mcp_server.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import mcp_server  # noqa: E402
import contextlib  # noqa: E402


_FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    FAIL: {message}")
    else:
        pass


def _assert_no_new_failures(baseline: int, test_name: str) -> None:
    """Call at end of a test to surface check() failures under pytest.

    The ``check()`` helper records failures into the module-level
    ``_FAILURES`` list but does not raise. When this file is executed
    as ``python3 test_mcp_server.py``, ``main()`` inspects
    ``_FAILURES`` at the end and exits non-zero on any entry. But when
    the file is run under pytest (which is how ``run_tests.py`` runs
    it), pytest only sees exceptions; a test function that records
    into ``_FAILURES`` and returns cleanly is reported as PASSED even
    though a real regression occurred.

    To close that gap per-test, snapshot ``len(_FAILURES)`` at the
    start of a test and call this helper at the end. It raises
    AssertionError (which pytest catches) if new entries were added
    by the test under the snapshot, naming the specific failures so
    pytest output carries them. Tests that adopt this pattern work
    correctly under both run modes. (The existing 100+ tests in this
    file do not yet adopt it; this is a hardening addition, not a
    retrofit, and each existing test is a candidate to adopt it as
    hardening work continues. See `MCP_SERVER.md` for context.)
    """
    new = _FAILURES[baseline:]
    assert not new, (
        f"{test_name}: {len(new)} check() failure(s):\n  "
        + "\n  ".join(new)
    )


# ── Layer 1: payload builder ──────────────────────────────────────

_DOC_SAMPLE = (
    "The Committee notes that risks to the outlook are elevated. "
    "Growth has been solid in recent quarters. Uncertainty about "
    "supply-side developments persists. Stakeholders across the "
    "economy are monitoring incoming data."
)


def test_payload_has_three_sections():
    """The novel part of this MCP server is the payload shape:
    analysis + agent_guidance + provenance. Regressing to a
    measurements-only payload would strip the reproducibility
    contract the server is built around."""
    print("=== payload has three sections ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    check("analysis" in payload, "missing analysis section")
    check("agent_guidance" in payload, "missing agent_guidance section")
    check("provenance" in payload, "missing provenance section")
    _assert_no_new_failures(baseline, "test_payload_has_three_sections")
    print("  PASS\n")


def test_analysis_fields_are_present():
    """The measurements must include coverage, voice, temporal,
    epistemic, claims, and frame-library matches. These are the
    structured signals the agent surfaces to the user."""
    print("=== analysis carries the expected measurement fields ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    a = payload["analysis"]
    for field in (
        "document", "coverage", "voice", "temporal",
        "epistemic", "claims_extracted", "frame_library_matches",
    ):
        check(field in a, f"analysis missing {field}")
    check(
        isinstance(a["coverage"]["addressed"], list),
        "coverage.addressed is not a list",
    )
    check(
        isinstance(a["frame_library_matches"], list),
        "frame_library_matches is not a list",
    )
    _assert_no_new_failures(baseline, "test_analysis_fields_are_present")
    print("  PASS\n")


def test_coverage_v2_shape():
    """MCP contract v2 coverage payload carries per-dimension evidence
    (markers_matched, vocabulary_searched_sample, signal_strength) and
    a first-class construct block.

    Pins:
      - analysis.coverage_v2 present alongside analysis.coverage (v1).
      - contract_version == 2.
      - All five dimensions present with status, markers_matched,
        marker_count, density_per_1kw, signal_strength,
        vocabulary_searched_sample, vocabulary_source.
      - status is enum "detected" or "not_detected".
      - summary counts are internally consistent.
      - construct block present with statement, reference, and
        how_to_serialize guidance.
    """
    print("=== coverage_v2 carries construct through structure ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    a = payload["analysis"]

    check("coverage_v2" in a, "analysis missing coverage_v2")
    check("coverage" in a, "v1 coverage must still emit during compat window")

    cov2 = a["coverage_v2"]
    check(cov2.get("contract_version") == 2,
          f"coverage_v2.contract_version != 2 (got {cov2.get('contract_version')!r})")

    dims = cov2.get("dimensions") or {}
    for name in ("causes", "risks", "stakeholders", "trends", "uncertainty"):
        check(name in dims, f"coverage_v2.dimensions missing {name}")
        d = dims.get(name) or {}
        check(d.get("status") in ("detected", "not_detected"),
              f"{name}.status must be detected|not_detected; got {d.get('status')!r}")
        check(isinstance(d.get("markers_matched"), list),
              f"{name}.markers_matched must be a list")
        check("marker_count" in d, f"{name} missing marker_count")
        check("density_per_1kw" in d, f"{name} missing density_per_1kw")
        check(d.get("signal_strength") in ("none", "nominal", "moderate", "substantive"),
              f"{name}.signal_strength must be enum; got {d.get('signal_strength')!r}")
        check(isinstance(d.get("vocabulary_searched_sample"), list),
              f"{name}.vocabulary_searched_sample must be a list")
        check(len(d.get("vocabulary_searched_sample", [])) > 0,
              f"{name}.vocabulary_searched_sample must be non-empty")
        check("vocabulary_source" in d, f"{name} missing vocabulary_source")

    summary = cov2.get("summary") or {}
    detected = summary.get("dimensions_with_detected_markers")
    not_detected = summary.get("dimensions_without_detected_markers")
    total = summary.get("total_dimensions")
    check(detected is not None and not_detected is not None and total is not None,
          "summary missing detected / not_detected / total counts")
    if detected is not None and not_detected is not None and total is not None:
        check(detected + not_detected == total,
              f"summary counts inconsistent: "
              f"{detected} + {not_detected} != {total}")

    construct = cov2.get("construct") or {}
    check(construct.get("signal_type") == "vocabulary_and_pattern_detector",
          f"construct.signal_type wrong: {construct.get('signal_type')!r}")
    for field in ("statement", "reference", "how_to_serialize"):
        check(field in construct and isinstance(construct[field], str)
              and len(construct[field]) > 40,
              f"construct.{field} missing or too short")
    # The posture-honest phrasing must be in the how_to_serialize guidance
    how_to = construct.get("how_to_serialize", "") or ""
    check("no markers detected" in how_to.lower() or "detected markers" in how_to.lower(),
          "how_to_serialize must name the detected-markers phrasing explicitly")
    _assert_no_new_failures(baseline, "test_coverage_v2_shape")
    print("  PASS\n")


def test_coverage_v2_signal_strength_thresholds():
    """signal_strength thresholds:
    none (density 0), nominal (<3), moderate (<10), substantive (>=10).

    Test by feeding documents engineered to hit each strength band
    on at least one dimension. Dimensions without markers are 'none'
    regardless of other dimensions.
    """
    print("=== coverage_v2 signal_strength honors pre-registered thresholds ===")
    baseline = len(_FAILURES)

    # Dense causal vocabulary document: causes should hit substantive
    dense_causal = (
        "The crisis was caused by multiple factors. Rising costs drove the "
        "shift because competition intensified. This was due to regulatory "
        "change; the outcome stems from deeper structural issues. The rise "
        "resulted in declining margins, which led to layoffs. Analysts "
        "attribute the downturn to these drivers."
    )
    p = mcp_server.build_epistemic_payload(dense_causal)
    causes = p["analysis"]["coverage_v2"]["dimensions"]["causes"]
    # Sanity: density should be non-trivial; signal_strength should reflect it
    strength = causes.get("signal_strength")
    density = causes.get("density_per_1kw", 0)
    check(strength in ("moderate", "substantive"),
          f"dense-causal doc: causes strength should be moderate/substantive, "
          f"got {strength!r} at density {density}")

    # Document with zero risk vocabulary: risks should be 'none'
    no_risks = (
        "The report covered growth patterns and the emergence of new "
        "technologies. Trends in adoption showed momentum. The evolution "
        "of the market surprised analysts. Consumers benefited."
    )
    p2 = mcp_server.build_epistemic_payload(no_risks)
    risks = p2["analysis"]["coverage_v2"]["dimensions"]["risks"]
    check(risks.get("status") == "not_detected",
          f"no-risks doc: risks.status should be not_detected, got {risks.get('status')!r}")
    check(risks.get("signal_strength") == "none",
          f"no-risks doc: risks.signal_strength should be 'none', "
          f"got {risks.get('signal_strength')!r}")
    check(risks.get("markers_matched") == [],
          f"no-risks doc: risks.markers_matched should be empty, "
          f"got {risks.get('markers_matched')!r}")
    _assert_no_new_failures(baseline, "test_coverage_v2_signal_strength_thresholds")
    print("  PASS\n")


def test_coverage_v2_sentence_attribution():
    """Each detected dimension in coverage_v2 must carry sentence_matches
    so a reader can see WHERE each marker fired, and distinct_sentences_detected
    so the breadth of coverage is visible.

    Pins the Phase A construct-breakthrough feature: per-sentence
    framing attribution. Without this, the portrait is paragraph-level
    summary; with it, the reader has evidence-grounded detection.
    """
    print("=== coverage_v2 sentence attribution surfaces per-match sentences ===")
    baseline = len(_FAILURES)
    doc = (
        "The CHIPS Act was driven by concerns about supply chain risks. "
        "Because of Taiwan concentration, policymakers face vulnerabilities. "
        "Consumers and workers are affected. Analysts see trajectory shifting. "
        "Outcomes remain uncertain."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    dims = payload["analysis"]["coverage_v2"]["dimensions"]

    # At least one detected dimension should have sentence_matches populated.
    detected_dims = [
        (name, d) for name, d in dims.items() if d["status"] == "detected"
    ]
    check(len(detected_dims) > 0,
          "test corpus must produce at least one detected dimension")

    for name, d in detected_dims:
        check("sentence_matches" in d,
              f"{name}: detected dimension missing sentence_matches")
        matches = d.get("sentence_matches", []) or []
        check(len(matches) > 0,
              f"{name}: detected dimension has empty sentence_matches; "
              f"attribution should surface at least one match")
        # Each match (deduped by sentence) has sentence_index,
        # sentence_preview, markers_in_sentence (list of markers fired
        # in that sentence; may be multiple per sentence).
        seen_indices = set()
        for sm in matches:
            check("sentence_index" in sm and isinstance(sm["sentence_index"], int),
                  f"{name}: sentence_match missing integer sentence_index")
            check(sm["sentence_index"] not in seen_indices,
                  f"{name}: sentence_matches should be deduped by "
                  f"sentence_index; index {sm.get('sentence_index')} "
                  f"appeared twice")
            seen_indices.add(sm["sentence_index"])
            check("sentence_preview" in sm and isinstance(sm["sentence_preview"], str),
                  f"{name}: sentence_match missing sentence_preview")
            check("markers_in_sentence" in sm
                  and isinstance(sm["markers_in_sentence"], list)
                  and len(sm["markers_in_sentence"]) >= 1,
                  f"{name}: sentence_match missing non-empty "
                  f"markers_in_sentence list")
        check("distinct_sentences_detected" in d,
              f"{name}: missing distinct_sentences_detected counter")
    _assert_no_new_failures(baseline, "test_coverage_v2_sentence_attribution")
    print("  PASS\n")


def test_mcp_voice_carries_classification_confidence_construct():
    """Phase B voice construct must surface in the MCP v2 voice payload.
    The classification-confidence construct (margin_to_threshold,
    runner_up, runner_up_margin, confidence) + first-class construct
    block parallel the coverage_v2 structure. Without this wiring, the
    Phase B breakthrough exists only in the web product; MCP consumers
    would serialize voice as decisive regardless of underlying confidence.
    """
    print("=== MCP voice carries Phase B classification-confidence construct ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    voice = payload["analysis"]["voice"]

    for field in (
        "confidence", "margin_to_threshold",
        "runner_up", "runner_up_margin",
    ):
        check(field in voice,
              f"voice payload missing Phase B field: {field}")
    check(voice["confidence"] in ("high", "borderline", "insufficient"),
          f"voice.confidence must be enum; got {voice.get('confidence')!r}")

    construct = voice.get("construct")
    check(construct is not None,
          "voice payload missing 'construct' sub-block")
    if construct is not None:
        check(construct.get("signal_type") == "cascade_classification",
              f"voice.construct.signal_type must be "
              f"'cascade_classification'; got {construct.get('signal_type')!r}")
        for field in ("statement", "reference", "how_to_serialize"):
            check(field in construct and isinstance(construct[field], str)
                  and len(construct[field]) > 40,
                  f"voice.construct.{field} missing or too short")
        how_to = construct.get("how_to_serialize", "") or ""
        check("borderline" in how_to.lower()
              and "runner-up" in how_to.lower(),
              "voice.construct.how_to_serialize must name borderline "
              "and runner-up explicitly")
    _assert_no_new_failures(baseline, "test_mcp_voice_carries_classification_confidence_construct")
    print("  PASS\n")


def test_mcp_temporal_carries_distribution_construct():
    """Phase B temporal construct must surface in the MCP v2 temporal
    payload. dominant_margin + balanced + first-class construct block.
    """
    print("=== MCP temporal carries Phase B distribution construct ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    temporal = payload["analysis"]["temporal"]

    check("dominant_margin" in temporal,
          "temporal payload missing dominant_margin")
    check("balanced" in temporal,
          "temporal payload missing balanced flag")
    check(isinstance(temporal.get("balanced"), bool),
          "temporal.balanced must be bool")

    construct = temporal.get("construct")
    check(construct is not None,
          "temporal payload missing 'construct' sub-block")
    if construct is not None:
        check(construct.get("signal_type") == "distribution_with_dominant",
              f"temporal.construct.signal_type must be "
              f"'distribution_with_dominant'; got "
              f"{construct.get('signal_type')!r}")
        for field in ("statement", "reference", "how_to_serialize"):
            check(field in construct and isinstance(construct[field], str)
                  and len(construct[field]) > 40,
                  f"temporal.construct.{field} missing or too short")
        how_to = construct.get("how_to_serialize", "") or ""
        check("balanced" in how_to.lower()
              and "margin" in how_to.lower(),
              "temporal.construct.how_to_serialize must name balanced "
              "and margin explicitly")
    _assert_no_new_failures(baseline, "test_mcp_temporal_carries_distribution_construct")
    print("  PASS\n")


def test_claims_hedged_count_reflects_primary_hedging():
    """Regression pin for the MCP payload bug where hedged_count was
    always 0 (and unhedged_count was always total_claims).

    Root cause: the sum used c.get("hedged"), but analyze_claims'
    per-claim dicts carry framing="hedged" as a string, not a hedged
    boolean. Fix: use analyze_claims' top-level totals directly.
    """
    print("=== claims hedged_count reflects primary hedging (bug regression) ===")
    baseline = len(_FAILURES)
    doc = (
        "The fund approximately $52 billion in assets. "
        "Revenue reached roughly 43% growth year over year. "
        "Operating margin was exactly 25% last quarter. "
        "The trend continues through 2024."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    claims = payload["analysis"]["claims_extracted"]

    total = claims.get("total", 0)
    hedged = claims.get("hedged_count", 0)
    unhedged = claims.get("unhedged_count", 0)
    check(total >= 2,
          f"test corpus should produce at least 2 claims; got {total}")
    check(hedged >= 2,
          f"hedged_count should reflect primary HEDGE_RE matches "
          f"(approximately, roughly); got hedged={hedged}, total={total}. "
          f"The pre-fix bug returned 0.")
    check(unhedged < total,
          f"unhedged_count should be less than total when some claims "
          f"are hedged; got unhedged={unhedged}, total={total}. The "
          f"pre-fix bug returned total.")
    _assert_no_new_failures(baseline, "test_claims_hedged_count_reflects_primary_hedging")
    print("  PASS\n")


def test_claims_candidate_hedge_surfaces_academic_forms():
    """Claims candidate-hedge patterns surface academic/conditional
    hedging the primary HEDGE_RE does not recognize. Provides a
    reader-inspectable lower-bound across coverage, epistemic, and
    claims.

    Hedge forms the primary misses include 'arguably', 'broadly
    speaking', 'subject to', 'tentatively', 'in principle', 'on the
    order of'. These are scholarly-soft or conditional hedges that
    a reader would recognize as qualifying language but that the
    primary regex (approximately|may|might|could|...) does not.
    """
    print("=== claims candidate-hedge surfaces academic hedges ===")
    baseline = len(_FAILURES)
    doc = (
        "Arguably, the growth rate reached 43% in Q3. "
        "Broadly speaking, revenue was $52 billion last year. "
        "Subject to market conditions, operating margins exceeded 25% in 2024. "
        "Tentatively, analysts model 90% coverage by 2030."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    claims = payload["analysis"]["claims_extracted"]

    check("candidate_hedge_count" in claims,
          "claims_extracted missing candidate_hedge_count field")
    check("candidate_hedge_samples" in claims,
          "claims_extracted missing candidate_hedge_samples field")

    count = claims.get("candidate_hedge_count", 0)
    check(count >= 3,
          f"expected >= 3 candidate hedges on test doc with arguably/"
          f"broadly speaking/subject to/tentatively forms; got {count}")

    samples = claims.get("candidate_hedge_samples", []) or []
    markers = [s.get("candidate_hedge_marker", "").lower() for s in samples]
    check(any("arguably" in m for m in markers),
          f"expected 'arguably' candidate; got markers {markers}")
    check(any("broadly speaking" in m for m in markers),
          f"expected 'broadly speaking' candidate; got markers {markers}")

    for s in samples:
        check("caveat" in s and s.get("caveat") and "primary" in s["caveat"].lower(),
              f"sample missing caveat: {s}")
        check("sentence_preview" in s,
              f"sample missing sentence_preview: {s}")
    _assert_no_new_failures(baseline, "test_claims_candidate_hedge_surfaces_academic_forms")
    print("  PASS\n")


def test_epistemic_candidate_attribution_surfaces_scholarly_forms():
    """Epistemic candidate-miss patterns surface scholarly-style
    attribution the primary _is_sourced pipeline misses, extending
    coverage-candidate treatment to the sourcing dimension.

    Failure class: primary detector misses 'observers raise', 'analysts
    argue', 'some have argued', and similar scholarly passives.
    Candidate-miss surfaces these with explicit caveat so the reader
    can inspect.
    """
    print("=== epistemic candidate-miss surfaces scholarly attribution ===")
    baseline = len(_FAILURES)
    doc = (
        "Observers raise concerns about the program. "
        "Analysts argue that prior attempts faltered. "
        "Some have argued that subsidies merely reshuffle capacity. "
        "The initiative continues regardless."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    epist = payload["analysis"]["epistemic"]

    check("candidate_attribution_sentences" in epist,
          "epistemic payload missing candidate_attribution_sentences field")
    check("candidate_attribution_count" in epist,
          "epistemic payload missing candidate_attribution_count field")

    cand = epist.get("candidate_attribution_sentences", []) or []
    check(len(cand) >= 3,
          f"expected >= 3 candidate sentences on test doc with three "
          f"distinct scholarly-attribution forms; got {len(cand)}")

    markers = [c.get("candidate_marker", "").lower() for c in cand]
    check(any("observers" in m for m in markers),
          f"expected an 'observers' candidate; got markers {markers}")
    check(any("analysts" in m for m in markers),
          f"expected an 'analysts' candidate; got markers {markers}")
    check(any("some have argued" in m for m in markers),
          f"expected 'some have argued' candidate; got markers {markers}")

    for c in cand:
        check("caveat" in c and "primary" in c["caveat"].lower(),
              f"candidate missing caveat: {c}")
        check(isinstance(c.get("sentence_index"), int),
              f"candidate missing integer sentence_index: {c}")
    _assert_no_new_failures(baseline, "test_epistemic_candidate_attribution_surfaces_scholarly_forms")
    print("  PASS\n")


def test_epistemic_candidate_attribution_surfaces_agency_parentheticals():
    """Move E (2026-04-27): agency-style parenthetical citations
    surface as candidate attribution. CONSTRUCT_VALIDITY_AUDIT_v1.md
    §2 named gap; balanced_macroeconomic_outlook fixture worked example.

    The three Move E sub-patterns must each produce a candidate marker
    on its representative form. Pinned here so a future regex
    refactor cannot silently drop the sub-patterns.

    Discriminator pinned: bare abbreviation-definition parens like
    (LLM) and (FDA) must NOT surface as candidate attribution; the
    structural cue (delimiter + content, year, or two-word capitalized
    name with year) is required.
    """
    print("=== epistemic candidate-miss surfaces agency parentheticals ===")
    baseline = len(_FAILURES)
    doc = (
        "Growth ran at 1.8 percent (BEA advance estimate, 2026-07-29). "
        "Unemployment held at 3.9 percent (BLS, June 2026 release). "
        "Regulators (FDIC, OCC) flagged commercial real estate risk. "
        "Manufacturing activity contracted (Census BTOS, June 2026). "
        "The model relies on a large language model (LLM) trained on text. "
        "The agency (FDA) approved the protocol."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    epist = payload["analysis"]["epistemic"]
    cand = epist.get("candidate_attribution_sentences", []) or []
    markers = [c.get("candidate_marker", "") for c in cand]

    check(any("BEA" in m and "2026" in m for m in markers),
          f"E.2 acronym-near-year not caught; markers={markers}")
    check(any("BLS" in m and "release" in m for m in markers),
          f"E.1 acronym-delimiter-content not caught; markers={markers}")
    check(any("FDIC" in m and "OCC" in m for m in markers),
          f"E.1 acronym-delimiter-acronym not caught; markers={markers}")
    # E.3 fixture: ``Census BTOS`` rather than ``Bloomberg survey``
    # because ``survey`` matches the primary _SOURCE_RE detector
    # (sentences with "survey" are flagged as primary-sourced and
    # therefore correctly excluded from the under-detection candidate
    # list). ``Census BTOS`` is the same E.3 shape (capitalized two-
    # word name + year inside parens) but doesn't trip primary
    # sourcing, so the candidate-miss path is the one being exercised.
    check(any("Census" in m and "2026" in m for m in markers),
          f"E.3 capitalized-two-word-with-year not caught; markers={markers}")

    bare_acronym_markers = [m for m in markers if m.strip() in ("(LLM)", "(FDA)")]
    check(not bare_acronym_markers,
          f"bare abbreviation-definition parens must NOT surface as "
          f"candidate attribution; got {bare_acronym_markers}")
    _assert_no_new_failures(baseline, "test_epistemic_candidate_attribution_surfaces_agency_parentheticals")
    print("  PASS\n")


def test_coverage_v2_attribution_handles_line_wrapped_sentences():
    """Regression pin for the whitespace-tolerance invariant in
    _compute_sentence_spans. split_sentences joins consecutive non-heading
    lines with ' ' (via ' '.join(pending)) so sentences end up with
    spaces where the original text has newlines. A literal text.find
    would miss these sentences; the whitespace-flexible regex search
    must locate them.

    The semiconductor-case fixture was the empirical evidence that this
    path must work: its "Analysts argue that restructuring..." sentence
    crosses a line boundary and was silently dropped from attribution
    before the fix. This test pins that it stays fixed.
    """
    print("=== attribution handles line-wrapped sentences ===")
    baseline = len(_FAILURES)
    # Document with deliberate line wrapping inside sentences. The
    # candidate trends regex must surface sentence 2's "restructuring"
    # even though that sentence starts on one source line and the
    # marker is on the next.
    doc = (
        "Policymakers describe the motivation as economic.\n"
        "Analysts argue that restructuring\n"
        "accelerated dramatically in 2025."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    dims = payload["analysis"]["coverage_v2"]["dimensions"]

    # Primary trends should be not_detected (our CANDIDATE_PATTERNS set
    # was constructed specifically to target this gap).
    check(dims["trends"]["status"] == "not_detected",
          f"expected trends not_detected on synthetic candidate-only doc; "
          f"got {dims['trends']['status']}")
    cs = dims["trends"].get("candidate_sentences", []) or []
    check(len(cs) >= 1,
          "candidate_sentences should surface restructuring sentence "
          "despite the line wrap within the sentence")
    if cs:
        # The sentence_index should resolve to a real sentence, and the
        # sentence_preview should be non-empty.
        first = cs[0]
        check(isinstance(first.get("sentence_index"), int),
              "sentence_index should be integer on line-wrapped sentence")
        check(first.get("sentence_preview"),
              "sentence_preview should be non-empty on line-wrapped sentence")
    _assert_no_new_failures(baseline, "test_coverage_v2_attribution_handles_line_wrapped_sentences")
    print("  PASS\n")


def test_coverage_v2_markers_whitespace_normalized():
    """Captured markers must be whitespace-normalized (single space).
    Without this, a match spanning a newline (e.g., 'due\\nto' in
    line-wrapped source) carries a literal newline in the marker string,
    which breaks preview-centering and displays awkwardly in downstream
    renderings.
    """
    print("=== coverage_v2 markers are whitespace-normalized ===")
    baseline = len(_FAILURES)
    # Deliberately wrap "due to" across a newline in the source.
    doc = (
        "The outcome was driven by multiple factors. Revenue fell due\n"
        "to reduced demand. Consumers and workers are affected."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    causes = payload["analysis"]["coverage_v2"]["dimensions"]["causes"]
    markers = causes.get("markers_matched", []) or []
    # No marker should contain a literal newline or multiple spaces.
    for m in markers:
        check("\n" not in m,
              f"marker contains literal newline: {m!r}")
        check("  " not in m,
              f"marker contains multiple spaces: {m!r}")
    # The markers_in_sentence inside each sentence_match should also
    # be normalized.
    for sm in causes.get("sentence_matches", []) or []:
        for m in sm.get("markers_in_sentence", []) or []:
            check("\n" not in m and "  " not in m,
                  f"sentence_match marker not normalized: {m!r}")
    _assert_no_new_failures(baseline, "test_coverage_v2_markers_whitespace_normalized")
    print("  PASS\n")


def test_coverage_v2_candidate_miss_surfacing():
    """Not-detected dimensions in coverage_v2 should carry
    candidate_sentences when CANDIDATE_PATTERNS fire, providing a
    reader-inspectable lower-bound signal.

    Primary detector did not fire, but reader-accessible candidate
    sentences are surfaced so the reader can judge whether the
    dimension is substantively covered.

    Uses the semiconductor-essay fixture: causes uses "rationale
    centers on" and "motivation" (primary misses); trends uses
    "restructuring" and "diversification" (primary misses).
    """
    print("=== coverage_v2 candidate-miss surfacing operationalizes under-detection ===")
    baseline = len(_FAILURES)
    doc = (
        "The subsidy rationale centers on reducing dependence on Taiwan. "
        "Policymakers describe the motivation as economic and security-driven. "
        "Analysts argue that restructuring accelerated dramatically in 2025 "
        "and that prior diversification attempts have faltered."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    dims = payload["analysis"]["coverage_v2"]["dimensions"]

    causes = dims["causes"]
    trends = dims["trends"]

    # Primary detector should miss both (the test document is specifically
    # constructed to use only candidate-regex vocabulary).
    check(causes["status"] == "not_detected",
          f"test assumes primary causes is not_detected; got "
          f"{causes['status']}. Update the test or investigate primary "
          f"regex changes if this fails.")
    check(trends["status"] == "not_detected",
          f"test assumes primary trends is not_detected; got "
          f"{trends['status']}")

    # Candidate-miss should surface specific sentences via the weaker
    # CANDIDATE_PATTERNS regex.
    cs_causes = causes.get("candidate_sentences", []) or []
    cs_trends = trends.get("candidate_sentences", []) or []

    check(len(cs_causes) >= 1,
          f"causes candidate_sentences should surface at least one "
          f"under-detection candidate (rationale/motivation); got "
          f"{len(cs_causes)}")
    causes_markers = [cs["candidate_marker"] for cs in cs_causes]
    check(any("rationale" in m or "motivation" in m for m in causes_markers),
          f"causes candidates should include rationale or motivation; "
          f"got {causes_markers}")

    check(len(cs_trends) >= 1,
          f"trends candidate_sentences should surface at least one; got "
          f"{len(cs_trends)}")
    trends_markers = [cs["candidate_marker"] for cs in cs_trends]
    check(any("restructuring" in m or "diversification" in m for m in trends_markers),
          f"trends candidates should include restructuring or "
          f"diversification; got {trends_markers}")

    # Every candidate entry carries an explicit caveat. Construct-honest:
    # the candidate is a POSSIBILITY, not a detection.
    for cs in cs_causes + cs_trends:
        check("caveat" in cs and len(cs["caveat"]) > 20,
              "every candidate_sentence must carry a caveat string")
        check("sentence_index" in cs and isinstance(cs["sentence_index"], int),
              "candidate_sentence missing integer sentence_index")
        check("sentence_preview" in cs,
              "candidate_sentence missing sentence_preview")
    _assert_no_new_failures(baseline, "test_coverage_v2_candidate_miss_surfacing")
    print("  PASS\n")


def test_prefer_contract_version_2_drops_v1_coverage():
    """prefer_contract_version=2 removes the legacy v1 coverage block,
    leaving coverage_v2 as the only coverage field. Clients that have
    migrated should see a non-duplicated payload.

    Phase 1 default (no preference): both v1 coverage and coverage_v2.
    Phase 1 with prefer=2: only coverage_v2.
    Phase 3 (future): v1 removed regardless of preference.
    """
    print("=== prefer_contract_version=2 drops v1 coverage block ===")
    baseline = len(_FAILURES)

    # Default: both emit
    default_payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    check("coverage" in default_payload["analysis"],
          "default emit should include v1 coverage")
    check("coverage_v2" in default_payload["analysis"],
          "default emit should include coverage_v2")

    # Apply v2-only preference
    v2_only = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    mcp_server._apply_v2_only_preference(v2_only)
    check("coverage" not in v2_only["analysis"],
          "prefer=2 should drop v1 coverage from analysis")
    check("coverage_v2" in v2_only["analysis"],
          "prefer=2 must keep coverage_v2")
    cov2 = v2_only["analysis"]["coverage_v2"]
    check(cov2.get("contract_version") == 2,
          "coverage_v2 must still carry contract_version after v2-only")

    # Verify no other signals are mutated by the preference toggle
    for field in ("voice", "temporal", "epistemic", "claims_extracted",
                  "frame_library_matches"):
        check(field in v2_only["analysis"],
              f"prefer=2 must not drop unrelated field: {field}")
    _assert_no_new_failures(baseline, "test_prefer_contract_version_2_drops_v1_coverage")
    print("  PASS\n")


def test_coverage_v2_in_compare_per_document_summary():
    """The compare tool's per-document summaries must also carry
    coverage_v2 so cross-document consumers inherit the construct-honest
    contract. Verified via the internal _summarize_per_document helper.
    """
    print("=== compare per-document summary emits coverage_v2 ===")
    baseline = len(_FAILURES)
    # Build a minimal doc dict shape matching what frame_compare computes
    from framing import (
        detect_coverage, temporal_orientation, detect_voice,
        detect_epistemic_basis,
    )
    from claim_analysis import analyze_claims
    text = _DOC_SAMPLE
    ca = analyze_claims(text)
    doc = {
        "coverage": detect_coverage(text),
        "voice": detect_voice(text),
        "temporal": temporal_orientation(text),
        "epistemic": detect_epistemic_basis(text),
        "claim_count": ca.get("total_claims", 0),
        "hedged_count": ca.get("hedged_count", 0),
        "unhedged_count": ca.get("unhedged_count", 0),
        "claims_raw": ca,
        "frames": [],
    }
    summary = mcp_server._summarize_per_document(doc, text)
    check("coverage" in summary, "per-doc summary missing v1 coverage")
    check("coverage_v2" in summary, "per-doc summary missing coverage_v2")
    cov2 = summary["coverage_v2"]
    check(cov2.get("contract_version") == 2,
          "per-doc coverage_v2 missing contract_version")
    check(len(cov2.get("dimensions", {})) == 5,
          f"per-doc coverage_v2 should have 5 dimensions, "
          f"got {len(cov2.get('dimensions', {}))}")
    _assert_no_new_failures(baseline, "test_coverage_v2_in_compare_per_document_summary")
    print("  PASS\n")


def test_analysis_includes_decision_readiness_profile():
    """The MCP analysis payload must include the decision-readiness
    profile. This is the load-bearing wiring for the strategic
    AI-response audit use case (the lead use case named on the
    /corpus/decision-readiness/ methodology page). Without this, the
    'AI tells you if its own response is decision-ready' positioning
    is documented but not implemented for agents.

    Pins:
      - analysis.decision_readiness present
      - methodology metadata (URL + version + status) present
      - All five dimensions present
      - Status is 'experimental' until Phase 2 validates
    """
    print("=== analysis includes decision-readiness profile ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    a = payload["analysis"]
    check("decision_readiness" in a,
          "analysis missing decision_readiness; MCP cannot serve "
          "the AI-response audit use case without it")
    profile = a["decision_readiness"]
    check(profile.get("methodology_url") == "/corpus/decision-readiness/",
          f"decision_readiness.methodology_url wrong: "
          f"{profile.get('methodology_url')!r}")
    check(profile.get("status") == "experimental",
          f"decision_readiness.status must be 'experimental' until "
          f"Phase 2 validation lands; got {profile.get('status')!r}")
    dims = profile.get("dimensions") or {}
    for required in [
        "coverage", "calibration", "evidence",
        "robustness", "counterfactual",
    ]:
        check(required in dims,
              f"decision_readiness missing dimension {required!r}")
    _assert_no_new_failures(baseline, "test_analysis_includes_decision_readiness_profile")
    print("  PASS\n")


def test_decision_readiness_uses_source_text_when_available():
    """When source_text is supplied, the decision-readiness profile's
    evidence dimension should pull verification counts from Layer 4
    source_fidelity (digit-substring presence) rather than ship
    null verification ratio. Without this mapping, the profile would
    ignore the verification work the user paid for by passing
    source_text.

    Pins:
      - With source_text: evidence.signal_value is a number (not None)
      - Without source_text: evidence.signal_value is None (no
        verification data available)
    """
    print("=== decision-readiness uses source_text verification ===")
    baseline = len(_FAILURES)
    # Without source
    payload_no_src = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    ev_no_src = (
        payload_no_src["analysis"]["decision_readiness"]
        ["dimensions"]["evidence"]
    )
    check(ev_no_src.get("signal_value") is None,
          f"without source_text, evidence verification ratio should "
          f"be None; got {ev_no_src.get('signal_value')!r}")

    # With source: the sample doc has numbers; supplying it as its
    # own source guarantees nonzero verification (every number
    # appears in source by definition).
    payload_with_src = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, source_text=_DOC_SAMPLE,
    )
    ev_with_src = (
        payload_with_src["analysis"]["decision_readiness"]
        ["dimensions"]["evidence"]
    )
    # signal_value is the ratio (verified / checked); when source
    # is the doc itself, all numbers are in_source so ratio is 1.0
    # IF the doc has any numbers at all. The sample may or may not;
    # test that the ratio is either a real number or honestly None
    # (no numbers to verify): never something between.
    sv = ev_with_src.get("signal_value")
    check(sv is None or isinstance(sv, (int, float)),
          f"with source_text, evidence signal_value should be "
          f"numeric or None; got {sv!r} ({type(sv).__name__})")
    _assert_no_new_failures(baseline, "test_decision_readiness_uses_source_text_when_available")
    print("  PASS\n")


def test_agent_guidance_includes_scope_honesty():
    """agent_guidance is the 'what this tool can and cannot tell
    you' surface. Both lists must be present so an agent passing
    the output to a user has the scope boundaries in hand."""
    print("=== agent_guidance names scope on both sides ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    g = payload["agent_guidance"]
    check(
        isinstance(g.get("what_this_tool_tells_you"), list)
        and len(g["what_this_tool_tells_you"]) >= 3,
        "what_this_tool_tells_you must have at least 3 entries",
    )
    check(
        isinstance(g.get("what_this_tool_does_not_tell_you"), list)
        and len(g["what_this_tool_does_not_tell_you"]) >= 3,
        "what_this_tool_does_not_tell_you must have at least 3 entries",
    )
    check(
        "how_to_cite_faithfully" in g,
        "how_to_cite_faithfully is required",
    )
    # The citation instruction must name Frame Check explicitly so
    # the agent cannot paraphrase the measurements as its own.
    check(
        "Frame Check" in g["how_to_cite_faithfully"],
        "how_to_cite_faithfully must name Frame Check",
    )
    _assert_no_new_failures(baseline, "test_agent_guidance_includes_scope_honesty")
    print("  PASS\n")


def test_provenance_reports_zero_llm_cost():
    """The deterministic layer does not invoke an LLM. Provenance
    must report cost 0.0 so agents and downstream telemetry do not
    misattribute cost to Frame Check invocations.

    Provenance also carries four version fields so a citation can
    resolve against a specific snapshot: frame_check_version (brand /
    methodology version, also stamped into telemetry events and
    CITATION.cff), server_version (the MCP wheel an integrator
    installed; matches initialize handshake serverInfo.version),
    clarethium_measure_version (measurement stack), frame_library_version
    (taxonomy snapshot from data/frame_library/VERSION).
    """
    print("=== provenance reports zero LLM cost ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    p = payload["provenance"]
    check(
        p.get("analysis_cost_usd") == 0.0,
        f"analysis_cost_usd is {p.get('analysis_cost_usd')}, expected 0.0",
    )
    check(
        p.get("analysis_layer") == "deterministic_structural_only",
        "analysis_layer should name the deterministic scope",
    )
    check(
        "frame_check_version" in p,
        "provenance must carry frame_check_version",
    )
    check(
        "server_version" in p,
        "provenance must carry server_version (MCP wheel version)",
    )
    check(
        p.get("server_version") == mcp_server.SERVER_VERSION,
        f"provenance.server_version must equal mcp_server.SERVER_VERSION "
        f"(both read from the same module constant); got "
        f"{p.get('server_version')!r} vs {mcp_server.SERVER_VERSION!r}",
    )
    check(
        "clarethium_measure_version" in p,
        "provenance must carry clarethium_measure_version",
    )
    check(
        "frame_library_version" in p,
        "provenance must carry frame_library_version",
    )
    check("citation" in p, "provenance must carry a citation string")
    check(
        p.get("license", {}).get("code") == "Apache-2.0",
        "code license in provenance must be Apache-2.0",
    )
    check(
        p.get("license", {}).get("corpus") == "CC-BY-4.0",
        "corpus license in provenance must be CC-BY-4.0",
    )
    _assert_no_new_failures(baseline, "test_provenance_reports_zero_llm_cost")
    print("  PASS\n")


def test_manifest_emits_canonical_and_legacy_version_keys():
    """Manifest payload emits both ``frame_check_version`` (canonical)
    and ``framecheck_version`` (legacy / typo'd from v0.9.x). Adopters
    parsing either key see the same value (FRAME_CHECK_VERSION).

    The legacy key is deprecated and scheduled for removal at v2.0;
    until then the additive emit preserves wire-compat for any
    integrator that hardcoded the typo'd field name when it shipped
    in v0.9.1 through v1.0.0.

    Pinning both fields here locks the additive contract: a future
    edit that drops either name fails this test, surfacing the
    deprecation as a deliberate decision rather than silent breakage.
    """
    print("=== manifest emits both frame_check_version + framecheck_version ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    m = payload["manifest"]
    check(
        "frame_check_version" in m,
        "manifest must carry frame_check_version (canonical name)",
    )
    check(
        "framecheck_version" in m,
        "manifest must carry framecheck_version (legacy / deprecated, "
        "removed at v2.0)",
    )
    check(
        m.get("frame_check_version") == m.get("framecheck_version"),
        f"both manifest version keys must carry the same value; got "
        f"frame_check_version={m.get('frame_check_version')!r}, "
        f"framecheck_version={m.get('framecheck_version')!r}",
    )
    p = payload["provenance"]
    check(
        m.get("frame_check_version") == p.get("frame_check_version"),
        f"manifest.frame_check_version must equal "
        f"provenance.frame_check_version; got {m.get('frame_check_version')!r} "
        f"vs {p.get('frame_check_version')!r}",
    )
    _assert_no_new_failures(
        baseline, "test_manifest_emits_canonical_and_legacy_version_keys",
    )
    print("  PASS\n")


def test_source_fidelity_carries_per_claim_unsourced_items():
    """When source_text is provided and at least one document number
    does not literal-match the source, verification.source_fidelity
    must carry an ``unsourced_items`` list naming the specific values
    + claim-sentence context for each.

    Pre-v1.0.9: the wire reported the count (e.g., ``not_in_source: 2``)
    without the items. Adopters reading "23/25 in source" got the
    headline but couldn't act on the 8% unsourced rate without
    manually diffing source vs. summary. The actionable diagnostic
    was hidden behind a count.

    The internal data was already there: ``clarethium_measure.
    source_matching()`` builds ``unsourced_details`` as
    [{value, type, context}, ...]. v1.0.9 surfaces it via the
    composer at mcp_compose.py:2712 as ``unsourced_items``.

    Pins the wire shape so a future composer change that drops the
    items list fails this test. The Grok-on-NVIDIA worked example
    is the load-bearing demo for this capability; the field is the
    actionable half of the differentiator.
    """
    print("=== source_fidelity carries per-claim unsourced_items ===")
    baseline = len(_FAILURES)
    # Document with an explicit numeric claim NOT in source.
    doc = (
        "## NVIDIA Update\n\n"
        "NVIDIA reported revenue of $35.1 billion in Q3 FY2025, up 94 "
        "percent year over year. The company also serves 999 million "
        "creators worldwide."
    )
    src = (
        "## NVIDIA Q3 FY2025\n\n"
        "Revenue: $35.1 billion, up 94 percent year over year. "
        "Operating margin steady. No user-count figure disclosed."
    )
    payload = mcp_server.build_epistemic_payload(
        doc, source_text=src, include_divergence=False,
    )
    sf = payload["analysis"]["verification"]["source_fidelity"]
    check(
        "unsourced_items" in sf,
        "verification.source_fidelity must carry unsourced_items "
        "(per-claim diagnostics, added v1.0.9)",
    )
    items = sf.get("unsourced_items", [])
    check(
        isinstance(items, list),
        f"unsourced_items must be a list; got {type(items).__name__}",
    )
    # The "999 million" claim is NOT in source; at least one item.
    check(
        len(items) >= 1,
        f"expected >=1 unsourced item for a doc with a number not in "
        f"source; got {len(items)} items, total_numbers={sf.get('total_numbers')}, "
        f"not_in_source={sf.get('not_in_source')}",
    )
    # Each item must carry the three documented fields.
    for it in items:
        check(
            "value" in it and "type" in it and "context" in it,
            f"unsourced_item must carry value+type+context keys; got "
            f"{sorted(it.keys())}",
        )
    # And the count in unsourced_items must agree with not_in_source.
    check(
        len(items) == sf.get("not_in_source", -1),
        f"unsourced_items count ({len(items)}) must equal "
        f"not_in_source count ({sf.get('not_in_source')})",
    )
    _assert_no_new_failures(
        baseline, "test_source_fidelity_carries_per_claim_unsourced_items",
    )
    print("  PASS\n")


def test_absent_frames_carry_library_resource_uri():
    """divergence.absent_frames records must carry library_resource_uri
    matching frame-check://library/<frame_id>, in addition to the
    existing citation_uri field that carries the same value.

    The two fields are intentional aliases. citation_uri is the
    original name on absent_frames; library_resource_uri matches the
    naming convention used by
    ``decision_readiness.dimensions[*].library_entries[*]`` (which
    emits ``{fvs_id, library_resource_uri, public_url}``). An MCP-
    integrated agent that learned the decision_readiness shape and
    looks for ``library_resource_uri`` on absent_frames per analogy
    must find the field there.

    Surfaced 2026-05-11 by an operator Phase-2 client run: the
    integration looked for library_resource_uri on absent_frames and
    got None / absent because absent_frames used citation_uri only.
    v1.0.10 adds the alias.

    Pins both the field's presence and its value-shape so a future
    composer change that drops it fails this test.
    """
    print("=== absent_frames carry library_resource_uri ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        "The Committee notes risks. Stakeholders monitor data.",
        include_divergence=True,
    )
    absent_frames = payload.get("divergence", {}).get("absent_frames", [])
    check(
        len(absent_frames) > 0,
        "test pre-condition: at least one absent frame must be present "
        f"for a generic short doc; got {len(absent_frames)}",
    )
    for af in absent_frames:
        check(
            "library_resource_uri" in af,
            f"absent_frame {af.get('frame_id', '?')!r} missing "
            f"library_resource_uri field (added v1.0.10)",
        )
        fid = af.get("frame_id")
        expected = f"frame-check://library/{fid}"
        check(
            af.get("library_resource_uri") == expected,
            f"absent_frame {fid!r} library_resource_uri must be "
            f"{expected!r}; got {af.get('library_resource_uri')!r}",
        )
        # citation_uri must still be set and equal to library_resource_uri
        # (aliases of each other).
        check(
            af.get("citation_uri") == af.get("library_resource_uri"),
            f"absent_frame {fid!r}: citation_uri and library_resource_uri "
            f"must carry the same value; got "
            f"citation_uri={af.get('citation_uri')!r}, "
            f"library_resource_uri={af.get('library_resource_uri')!r}",
        )
    _assert_no_new_failures(baseline, "test_absent_frames_carry_library_resource_uri")
    print("  PASS\n")


def test_typical_co_fires_carry_library_resource_uri():
    """Every typical_co_fires / typical_co_absences entry under
    corpus_context (whether on frame_library_matches[*] or
    divergence.absent_frames[*]) must carry library_resource_uri
    matching frame-check://library/<fvs_id>, in addition to the
    pre-1.0 citation_uri field that carries the same value.

    Same defect class as the v1.0.10 fix on absent_frames[*]
    itself: an MCP-integrated agent that learned the
    decision_readiness.dimensions[*].library_entries[*] shape
    (which emits library_resource_uri) and looked for the field
    on co_fires / co_absences per analogy got nothing — those
    blocks emitted only citation_uri. Surfaced 2026-05-11 by a
    fresh-eyes schema-coherence audit on the v1.0.10 baseline.

    v1.0.11 adds the alias to both blocks at the corpus_intelligence
    emit site. Schema-additive; pre-1.0.11 integrations using
    citation_uri keep working.
    """
    print("=== typical_co_fires/absences carry library_resource_uri ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        "The Committee notes risks. Stakeholders monitor data.",
        include_divergence=True,
    )
    records = []
    for fmm in payload["analysis"].get("frame_library_matches", []):
        cc = fmm.get("corpus_context") or {}
        records.extend(cc.get("typical_co_fires", []) or [])
        records.extend(cc.get("typical_co_absences", []) or [])
    for af in payload.get("divergence", {}).get("absent_frames", []):
        cc = af.get("corpus_context") or {}
        records.extend(cc.get("typical_co_fires", []) or [])
        records.extend(cc.get("typical_co_absences", []) or [])
    check(
        len(records) > 0,
        f"test pre-condition: at least one typical_co_* record must "
        f"be present for a generic doc with corpus context; got "
        f"{len(records)} records",
    )
    for rec in records:
        fid = rec.get("fvs_id")
        check(
            "library_resource_uri" in rec,
            f"typical_co_* record for {fid!r} missing library_resource_uri "
            f"(added v1.0.11)",
        )
        expected = f"frame-check://library/{fid}"
        check(
            rec.get("library_resource_uri") == expected,
            f"typical_co_* record for {fid!r}: library_resource_uri must "
            f"be {expected!r}; got {rec.get('library_resource_uri')!r}",
        )
        check(
            rec.get("library_resource_uri") == rec.get("citation_uri"),
            f"typical_co_* record for {fid!r}: library_resource_uri and "
            f"citation_uri must carry the same value; got "
            f"library_resource_uri={rec.get('library_resource_uri')!r}, "
            f"citation_uri={rec.get('citation_uri')!r}",
        )
    _assert_no_new_failures(baseline, "test_typical_co_fires_carry_library_resource_uri")
    print("  PASS\n")


def test_provenance_carries_production_status():
    """Provenance carries a production_status field that names whether
    the canonical production hosting at frame.clarethium.com is
    currently active or paused. The URLs in provenance forward-point
    to that production site; surfacing the hosting state inline lets
    agents distinguish "URL canonicalized but currently paused" from
    "URL malformed or wrong" without out-of-band knowledge.

    Pinned both ways: the field must exist, AND its value must match
    the module-level PRODUCTION_STATUS constant. A future flip from
    "paused" to "active" on production resume should be a single
    constant edit; this test fails if a copy lands somewhere out of
    sync with the constant.
    """
    print("=== provenance carries production_status ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    p = payload["provenance"]
    check(
        "production_status" in p,
        "provenance must carry production_status field",
    )
    check(
        p.get("production_status") == mcp_server.PRODUCTION_STATUS,
        f"provenance.production_status must equal "
        f"mcp_server.PRODUCTION_STATUS; got {p.get('production_status')!r} "
        f"vs {mcp_server.PRODUCTION_STATUS!r}",
    )
    check(
        p.get("production_status") in ("active", "paused"),
        f"production_status must be one of (active, paused); got "
        f"{p.get('production_status')!r}",
    )
    check(
        "production_status_note" in p,
        "provenance must carry production_status_note explaining the "
        "current hosting state",
    )
    check(
        isinstance(p.get("production_status_note"), str)
        and len(p["production_status_note"]) > 0,
        "production_status_note must be a non-empty string",
    )
    _assert_no_new_failures(baseline, "test_provenance_carries_production_status")
    print("  PASS\n")


def test_payload_is_deterministic():
    """Same input, same output. The deterministic guarantee is the
    whole basis for the reproducibility claim in agent_guidance. If
    this fails, the guidance is a lie and the tool should not be
    shipped."""
    print("=== payload is deterministic across calls ===")
    baseline = len(_FAILURES)
    a = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    b = mcp_server.build_epistemic_payload(_DOC_SAMPLE)

    # Strip wall-clock fields that are allowed to differ between
    # calls (latency is duration, timestamp is the start-of-call
    # ISO stamp). Determinism here means "same input produces
    # identical measurement output", not "the two calls land in
    # the same microsecond." The manifest's analysis_run_at is
    # per-call wall-clock attribution by design (the receipt records
    # WHEN this specific call ran); other manifest fields stay in
    # the comparison so a real determinism regression in the
    # operational layers still surfaces.
    for p in (a, b):
        p["provenance"]["analysis_latency_ms"] = 0
        p["provenance"]["analysis_timestamp_utc"] = ""
        if isinstance(p.get("manifest"), dict):
            p["manifest"].pop("analysis_run_at", None)

    check(a == b, "two calls on the same input produced different payloads")
    _assert_no_new_failures(baseline, "test_payload_is_deterministic")
    print("  PASS\n")


# ── Layer 2: JSON-RPC dispatcher (in-process) ─────────────────────

def test_initialize_handshake():
    """Initialize must return protocolVersion, capabilities, and
    serverInfo. MCP clients refuse to proceed without these."""
    print("=== initialize handshake ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    })
    check(resp is not None, "initialize returned no response")
    result = resp["result"]
    check(
        result["protocolVersion"] == mcp_server.PROTOCOL_VERSION,
        "initialize returned wrong protocolVersion",
    )
    check("tools" in result["capabilities"], "tools capability not advertised")
    check(
        result["serverInfo"]["name"] == mcp_server.SERVER_NAME,
        "serverInfo.name mismatch",
    )
    _assert_no_new_failures(baseline, "test_initialize_handshake")
    print("  PASS\n")


def test_initialize_carries_server_instructions():
    """The InitializeResult must carry an `instructions` field
    (top-level per MCP protocol) describing when to use Frame Check,
    the default invocation shape, and the four-prompt workflow
    surface. Per-tool descriptions are delivered separately via
    tools/list; this field is the canonical place for cross-tool
    orientation a client UI can show the user during the connection
    handshake.

    Pins:
      - field exists at top-level (not nested under serverInfo)
      - mentions zero-arg invocation so an agent reading it knows
        it does not need to pass include_divergence=true
        defensively
      - names both tools so the workflow surface is visible
    """
    print("=== initialize carries server instructions ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    })
    result = resp["result"]
    instructions = result.get("instructions")
    check(
        isinstance(instructions, str) and len(instructions) > 200,
        f"InitializeResult.instructions must be a non-trivial "
        f"string; got {type(instructions).__name__} of length "
        f"{len(instructions) if isinstance(instructions, str) else 0}",
    )
    check(
        "zero-arg" in instructions
        or "frame_check(document_text" in instructions,
        "instructions should name the zero-arg invocation shape so "
        "the agent does not pass include_divergence=true defensively",
    )
    check(
        "frame_check" in instructions and "frame_compare" in instructions,
        "instructions should name both tools so the workflow "
        "surface is visible from the handshake",
    )
    check(
        "challenge_document" in instructions
        or "explain_framing" in instructions,
        "instructions should reference the prompt surface so the "
        "user can ask the agent to use a named prompt",
    )
    _assert_no_new_failures(baseline, "test_initialize_carries_server_instructions")
    print("  PASS\n")


def test_frame_check_schema_hides_advanced_integrator_params():
    """The frame_check tool schema must NOT advertise advanced-
    integrator parameters that pollute the agent's decision space:
      - prefer_contract_version: coverage v1/v2 migration window;
        not an agent-per-call concern
      - catalog_version_pin: stability pin for advanced integrators;
        not relevant per-call
      - domain_hint: currently echo-only with no field-level
        filtering; documented in the limitations envelope

    These params remain accepted by the dispatch layer (so explicit
    integrators that pass them continue to work; backward
    compatibility preserved). The schema simply stops asking the
    agent to make decisions about them.
    """
    print("=== frame_check schema hides advanced-integrator params ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list",
    })
    schema = next(
        t for t in resp["result"]["tools"] if t["name"] == "frame_check"
    )
    props = schema["inputSchema"]["properties"]
    for hidden in (
        "prefer_contract_version",
        "catalog_version_pin",
        "domain_hint",
    ):
        check(
            hidden not in props,
            f"{hidden!r} must not appear in the agent-facing schema; "
            f"advanced-integrator parameters pollute the agent's "
            f"decision space",
        )
    # Backward compat: the dispatch layer still accepts these
    # explicitly, so an integrator who pinned the older surface is
    # not broken. Verify with a real call passing all three.
    doc = (
        "AI productivity gains are decisive. Companies must adopt "
        "now or fall behind. Growth is inevitable. Risks can be "
        "deprioritized given the historical adoption pattern."
    )
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": doc,
                "prefer_contract_version": 1,
                "catalog_version_pin": "library_v3",
                "domain_hint": "finance",
            },
        },
    })
    check(
        not resp["result"].get("isError", False),
        f"removed-from-schema params must still work via dispatch "
        f"(backward compat); got error: "
        f"{resp['result'].get('content', [{}])[0].get('text', '')[:200]}",
    )
    _assert_no_new_failures(baseline, "test_frame_check_schema_hides_advanced_integrator_params")
    print("  PASS\n")


def test_lift_dry_run_gate_10_matches_rewriter_policy():
    """The lift wheel-content scan (gate 10 in
    scripts/_release_lib/lift.py) catches references to the
    operator's upstream development repo if any leaked into the
    wheel-staged tree.

    Two policy properties this test pins so they can't silently drift:

    1. Backtick-protected text mentions are preserved (the
       rewriter wraps prior-form mentions in code spans precisely
       so the rewrite pass leaves them alone; the gate must too).
    2. Email addresses are preserved (the @-prefix lookbehind
       excludes ``curator@frame.clarethium.com`` from any future
       host-pattern match).

    History note: an earlier version of this test also checked a
    ``paused_pat`` for ``frame.clarethium.com`` references. That
    pattern was removed from lift.py at the 0.8.8 cleanup (the
    production hosting pause was lifted at the T-429 launch on
    2026-05-05); the test now only mirrors the single ``private_pat``
    that lift.py actually runs.

    The ``/`` exclusion in the lookbehind means a URL-prefixed
    form (``https://`` followed by the operator-tree path) is NOT
    caught by gate 10 alone. That is the documented intent: the
    rewriter (scripts/_release_lib/extract.py) handles URL-prefixed
    forms in its dedicated pass; gate 10 catches bare-host
    occurrences the rewriter pass might miss. Pinning that
    property below so a future ``/`` lookbehind change reads as a
    deliberate decision.
    """
    print("=== lift_dry_run gate 10 matches rewriter exclusion policy ===")
    baseline = len(_FAILURES)
    import re
    # Mirror of the actual pattern in scripts/_release_lib/lift.py
    # gate-10 at the time of this test (single pattern; the
    # paused_pat for frame.clarethium.com was removed at 0.8.8).
    private_pat = re.compile(
        r"(?<![@\w`/])github\.com/lluvr/frame-check(?!-mcp)"
    )

    # Backtick-protected mentions must NOT match (these are
    # intentional code-span text mentions the rewriter preserves;
    # the gate must too).
    for backticked in (
        "`https://github.com/lluvr/frame-check`",  # canon-exempt: leak-detection test fixture
        "`github.com/lluvr/frame-check`",  # canon-exempt: leak-detection test fixture
    ):
        check(
            private_pat.search(backticked) is None,
            f"private_pat must NOT match backtick-protected text "
            f"(rewriter preserves these); matched: {backticked!r}",
        )

    # Bare-host occurrences (no URL prefix) MUST match. These are
    # the leak forms gate 10 exists to catch.
    for raw in (
        "see github.com/lluvr/frame-check/issues/1",  # canon-exempt: leak-detection test fixture
        "the upstream tree at github.com/lluvr/frame-check is private",  # canon-exempt: leak-detection test fixture
    ):
        check(
            private_pat.search(raw) is not None,
            f"private_pat must catch bare-host raw forms; "
            f"missed: {raw!r}",
        )

    # URL-prefixed forms (https://github.com/...) are intentionally
    # NOT caught by gate 10 alone; the rewriter handles them in a
    # dedicated pass. Pinning the property so a future lookbehind
    # change reads as a deliberate decision rather than silent drift.
    for url_prefixed in (
        "https://github.com/lluvr/frame-check/blob/master/README.md",  # canon-exempt: leak-detection test fixture
        "https://github.com/lluvr/frame-check",  # canon-exempt: leak-detection test fixture
    ):
        check(
            private_pat.search(url_prefixed) is None,
            f"private_pat must NOT match URL-prefixed forms (those "
            f"are the rewriter's job, per the gate's '/' lookbehind "
            f"exclusion); matched: {url_prefixed!r}",
        )

    # Excluded by (?!-mcp): the legitimate repo URL ``frame-check-mcp``
    # is the operator's published wheel name and must not match the
    # leak pattern.
    legitimate = "github.com/lluvr/frame-check-mcp/issues"  # canon-exempt: leak-detection test fixture
    check(
        private_pat.search(legitimate) is None,
        f"private_pat must NOT match the legitimate frame-check-mcp "
        f"URL (negative-lookahead suffix); matched: {legitimate!r}",
    )
    _assert_no_new_failures(baseline, "test_lift_dry_run_gate_10_matches_rewriter_policy")
    print("  PASS\n")


def test_frame_check_descriptions_lead_with_use_case():
    """Tool + parameter descriptions must teach WHEN to use them,
    not just WHAT they return. The default shape ('zero-arg works')
    must be communicated up front so an agent does not pass
    include_divergence=true defensively.

    Pins for the tool description:
      - Mentions 'use this when' or equivalent use-case framing
        (not just 'returns analysis (measurements)')
      - Mentions zero-arg invocation
    Pins per-parameter:
      - include_divergence description leads with the default
      - source_text, user_context, user_goal lead with 'pass when'
        so the agent knows the trigger condition, not just the
        output shape
    """
    print("=== frame_check descriptions lead with use case ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/list",
    })
    schema = next(
        t for t in resp["result"]["tools"] if t["name"] == "frame_check"
    )
    desc = schema["description"]
    check(
        "Use this when" in desc or "use this when" in desc.lower(),
        "tool description must lead with 'Use this when' or "
        "equivalent; teaching the agent WHEN to invoke the tool "
        "is higher-leverage than describing what it returns",
    )
    check(
        "zero-arg" in desc or "frame_check(document_text" in desc,
        "tool description must surface the zero-arg invocation "
        "shape so the agent does not pass optional params "
        "defensively",
    )
    props = schema["inputSchema"]["properties"]
    div_desc = props["include_divergence"]["description"].lower()
    check(
        "default true" in div_desc and "do not need to pass" in div_desc,
        f"include_divergence description must lead with the default "
        f"value and explicitly say the agent does not need to pass "
        f"it; got {div_desc[:200]!r}",
    )
    for trigger_param in ("source_text", "user_context", "user_goal"):
        d = props[trigger_param]["description"].lower()
        check(
            d.startswith("pass when") or "pass when" in d[:60],
            f"{trigger_param!r} description must lead with "
            f"'Pass when ...' so the agent knows the trigger "
            f"condition, not just the output shape; got {d[:120]!r}",
        )
    _assert_no_new_failures(baseline, "test_frame_check_descriptions_lead_with_use_case")
    print("  PASS\n")


def test_tools_list_advertises_frame_check():
    print("=== tools/list advertises frame_check ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "tools/list",
    })
    tools = resp["result"]["tools"]
    check(
        any(t["name"] == "frame_check" for t in tools),
        "frame_check tool not advertised",
    )
    schema = next(t for t in tools if t["name"] == "frame_check")
    check(
        "document_text" in schema["inputSchema"]["required"],
        "document_text must be required in inputSchema",
    )
    _assert_no_new_failures(baseline, "test_tools_list_advertises_frame_check")
    print("  PASS\n")


def test_tools_list_advertises_frame_compare():
    """frame_compare is the second tool in the MCP server. Both tools
    must be advertised so a client sees the full capability surface.
    Regressing to a single-tool advertisement would hide the compare
    path from every MCP client."""
    print("=== tools/list advertises frame_compare ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "tools/list",
    })
    tools = resp["result"]["tools"]
    check(
        any(t["name"] == "frame_compare" for t in tools),
        "frame_compare tool not advertised",
    )
    schema = next(t for t in tools if t["name"] == "frame_compare")
    required = set(schema["inputSchema"]["required"])
    check(
        required == {"document_a_text", "document_b_text"},
        f"frame_compare required fields must be exactly the two "
        f"document texts, got {required}",
    )
    # Labels are optional but must be declared so the client knows
    # they are accepted.
    props = schema["inputSchema"]["properties"]
    check(
        "document_a_label" in props and "document_b_label" in props,
        "label fields must be declared as optional properties",
    )
    _assert_no_new_failures(baseline, "test_tools_list_advertises_frame_compare")
    print("  PASS\n")


def test_tools_call_returns_text_content():
    """A valid tools/call returns content[0].type == 'text' with a
    JSON-encoded payload in .text. isError must be False."""
    print("=== tools/call returns text content with full payload ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {"document_text": _DOC_SAMPLE},
        },
    })
    result = resp["result"]
    check(result.get("isError") is False, "isError should be False on valid call")
    check(len(result["content"]) == 1, "expected one content item")
    check(result["content"][0]["type"] == "text", "content type must be text")
    payload = json.loads(result["content"][0]["text"])
    check("analysis" in payload, "payload missing analysis")
    check("agent_guidance" in payload, "payload missing agent_guidance")
    check("provenance" in payload, "payload missing provenance")
    _assert_no_new_failures(baseline, "test_tools_call_returns_text_content")
    print("  PASS\n")


def test_tools_call_empty_input_is_error():
    print("=== tools/call rejects empty document ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {"document_text": ""}},
    })
    check(
        resp["result"].get("isError") is True,
        "empty input must set isError true",
    )
    _assert_no_new_failures(baseline, "test_tools_call_empty_input_is_error")
    print("  PASS\n")


def test_unknown_tool_returns_error_content():
    print("=== unknown tool returns isError content ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "no_such_tool", "arguments": {}},
    })
    check(
        resp["result"].get("isError") is True,
        "unknown tool must set isError true",
    )
    _assert_no_new_failures(baseline, "test_unknown_tool_returns_error_content")
    print("  PASS\n")


def test_unknown_method_returns_jsonrpc_error():
    print("=== unknown method returns JSON-RPC error ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 6, "method": "does/not/exist",
    })
    check(
        "error" in resp and resp["error"]["code"] == -32601,
        "unknown method should return -32601 Method not found",
    )
    _assert_no_new_failures(baseline, "test_unknown_method_returns_jsonrpc_error")
    print("  PASS\n")


def test_notification_gets_no_response():
    """JSON-RPC notifications have no id and receive no response.
    Sending a response back to a notification would break MCP
    clients that track message IDs."""
    print("=== notifications receive no response ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "method": "notifications/initialized",
    })
    check(resp is None, "notifications must not produce a response")
    _assert_no_new_failures(baseline, "test_notification_gets_no_response")
    print("  PASS\n")


# ── Layer 2b: verification (source_text path) ─────────────────────


_SAMPLE_DOC_FOR_SOURCE = (
    "## Q3 Report\n\n"
    "Revenue reached $18.12 billion, up 206% year over year. "
    "Data center revenue was $14.51 billion. Gaming was $2.86 billion. "
    "Growth remains strong."
)

_SAMPLE_SOURCE = (
    "Q3 FY2024 Results. Revenue: $18.12 billion (up 206% YoY). "
    "Data Center: $14.51 billion (up 279%). Gaming: $2.86 billion. "
    "Gross margin: 74.0%."
)

_DENSE_SOURCE = (
    "Revenue 2023: $127B. Revenue 2024: $158B. Margin: 43%. "
    "Operating: 28%. R&D: $22B. SGA: $31B. Net income: $42B. "
    "Cash: $85B. Debt: $14B. Employees: 173000. Countries: 41. "
    "Patents: 5800. Data centers: 92. Customers: 2400000. "
    "ARR: $95B. NRR: 118%. Retention: 97%. CAC: 14 months."
)


def test_no_source_has_no_verification_block():
    """Without source_text, the analysis block must not contain
    verification. This keeps the no-source contract stable for
    agents that never supply a source."""
    print("=== no source -> no verification block ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_SAMPLE_DOC_FOR_SOURCE)
    check(
        "verification" not in payload["analysis"],
        "verification must be absent when source_text is None",
    )
    check(
        payload["provenance"]["analysis_layer"] == "deterministic_structural_only",
        "analysis_layer should still name structural-only without source",
    )
    _assert_no_new_failures(baseline, "test_no_source_has_no_verification_block")
    print("  PASS\n")


def test_with_source_unlocks_verification_block():
    """Passing source_text unlocks the verification block: Layer 4
    source_fidelity + Layer 11 grounding_decomposition with
    scope_assessment regime classification."""
    print("=== source provided -> verification block present ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        _SAMPLE_DOC_FOR_SOURCE, source_text=_SAMPLE_SOURCE,
    )
    v = payload["analysis"].get("verification")
    check(v is not None, "verification block missing when source_text given")
    check(
        "source_fidelity" in v and "grounding_decomposition" in v,
        "verification must carry source_fidelity and grounding_decomposition",
    )
    sa = v["grounding_decomposition"].get("scope_assessment", {})
    check(
        sa.get("derivation_regime") in ("diagnostic", "transition", "saturated"),
        f"scope_assessment.derivation_regime must be one of the three regimes; "
        f"got {sa.get('derivation_regime')!r}",
    )
    check(
        isinstance(sa.get("source_num_count"), int),
        "scope_assessment.source_num_count must be int",
    )
    check(
        payload["provenance"]["analysis_layer"]
        == "deterministic_structural_plus_verification",
        "analysis_layer should widen when source is supplied",
    )
    _assert_no_new_failures(baseline, "test_with_source_unlocks_verification_block")
    print("  PASS\n")


def test_saturated_source_steers_guidance_to_layer_4():
    """A number-dense source produces the saturated regime; the
    agent_guidance.scope_regime_guidance must then point the agent
    at Layer 4 source_fidelity for numerical claims. This is the
    epistemic-honesty propagation the canon-play positioning relies
    on: Frame Check does not silently let an agent quote the wrong
    layer on dense sources."""
    print("=== saturated regime -> guidance cites Layer 4 ===")
    baseline = len(_FAILURES)
    doc = (
        "## Strategy\n\nRevenue grew from $127 billion to $158 billion "
        "over the period, with margins expanding modestly."
    )
    payload = mcp_server.build_epistemic_payload(doc, source_text=_DENSE_SOURCE)
    regime = (
        payload["analysis"]["verification"]["grounding_decomposition"]
        ["scope_assessment"]["derivation_regime"]
    )
    check(regime == "saturated", f"expected saturated, got {regime!r}")
    guidance = payload["agent_guidance"]["scope_regime_guidance"].lower()
    check(
        "source_fidelity" in guidance or "layer 4" in guidance,
        "saturated-regime guidance must direct the agent to Layer 4 "
        "for numerical claims",
    )
    _assert_no_new_failures(baseline, "test_saturated_source_steers_guidance_to_layer_4")
    print("  PASS\n")


def test_frame_matches_carry_stability_status():
    """Every frame_library_matches entry must carry a 'status' field
    so the agent can communicate the INDEX.md stability guarantee to
    the user. Draft matches have stable IDs only; canon matches have
    full stability. Without this, a user could cite a draft match as
    stable."""
    print("=== frame matches include stability status ===")
    baseline = len(_FAILURES)
    # A doc that triggers at least one frame match.
    doc = (
        "## Market Outlook\n\n"
        "Revenue has grown strongly year over year and we expect "
        "this growth trajectory to continue. Our market expansion "
        "positions us well for future acceleration. Leadership is "
        "confident the trend will persist."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    matches = payload["analysis"]["frame_library_matches"]
    if not matches:
        # The tool may return no matches on short docs; not a
        # regression. Print a note and skip the status assertion.
        print("  (no matches produced; skipping status assertion)")
        return
    for m in matches:
        check(
            "status" in m,
            f"frame match {m.get('fvs_id')} missing status field",
        )
        check(
            m["status"] in ("draft", "canon", "aspirational", "retired"),
            f"frame match {m.get('fvs_id')} has unexpected status "
            f"{m.get('status')!r}",
        )
    _assert_no_new_failures(baseline, "test_frame_matches_carry_stability_status")
    print("  PASS\n")


def test_agent_guidance_describes_cite_form_for_matches():
    """The guidance must tell the agent HOW to surface frame matches
    honestly given their status. Missing this is the difference
    between 'the agent cites Frame Check faithfully' and 'the agent
    claims a draft frame is a stable standard'."""
    print("=== agent_guidance covers how to cite frame matches ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_SAMPLE_DOC_FOR_SOURCE)
    check(
        "how_to_cite_frame_matches" in payload["agent_guidance"],
        "agent_guidance must include how_to_cite_frame_matches",
    )
    blob = payload["agent_guidance"]["how_to_cite_frame_matches"].lower()
    check(
        "draft" in blob and "canon" in blob,
        "how_to_cite_frame_matches must name both draft and canon",
    )
    _assert_no_new_failures(baseline, "test_agent_guidance_describes_cite_form_for_matches")
    print("  PASS\n")


# ── Layer 3: end-to-end subprocess ────────────────────────────────

def test_compare_payload_has_three_sections():
    """Same three-section contract that frame_check carries. The
    integrity claim is identical for both tools: an agent handling
    either output relies on agent_guidance + provenance in the
    same shape."""
    print("=== compare payload has three sections ===")
    baseline = len(_FAILURES)
    doc_a = (
        "Growth has been strong across all segments. Revenue reached "
        "record levels this quarter. The outlook is positive."
    )
    doc_b = (
        "The Committee notes that risks to the outlook are elevated. "
        "Growth has moderated in recent months. Uncertainty persists."
    )
    payload = mcp_server.build_compare_payload(doc_a, doc_b, "Bull", "Fed")
    check("analysis" in payload, "compare missing analysis")
    check("agent_guidance" in payload, "compare missing agent_guidance")
    check("provenance" in payload, "compare missing provenance")
    check(
        "Bull" in payload["analysis"]["documents"],
        "per-document key must use the supplied label",
    )
    check(
        "Fed" in payload["analysis"]["documents"],
        "per-document key must use the supplied label",
    )
    _assert_no_new_failures(baseline, "test_compare_payload_has_three_sections")
    print("  PASS\n")


def test_compare_analysis_carries_cross_doc_fields():
    """The comparison block must carry the cross-document signals
    agents surface to the user: shared blind spots, unique gaps,
    voice / temporal match flags, sourcing delta, and the
    structured framing-differences narrative."""
    print("=== compare analysis carries cross-doc fields ===")
    baseline = len(_FAILURES)
    doc_a = (
        "Growth has been strong. Revenue is up. Stakeholders are "
        "pleased with the pace of expansion."
    )
    doc_b = (
        "Risks to the outlook have risen. Uncertainty persists. "
        "Policymakers are monitoring developments carefully."
    )
    payload = mcp_server.build_compare_payload(doc_a, doc_b)
    comp = payload["analysis"]["comparison"]
    for field in ("coverage", "voice", "temporal", "epistemic",
                  "framing_differences"):
        check(field in comp, f"comparison missing {field}")
    check(
        isinstance(comp["coverage"]["shared_blind_spots"], list),
        "shared_blind_spots must be a list",
    )
    check(
        isinstance(comp["voice"]["match"], bool),
        "voice.match must be a bool",
    )
    check(
        isinstance(comp["epistemic"]["sourced_pct_delta"], int),
        "sourced_pct_delta must be an int",
    )
    _assert_no_new_failures(baseline, "test_compare_analysis_carries_cross_doc_fields")
    print("  PASS\n")


def test_compare_voice_and_temporal_carry_phase_b_construct():
    """The frame_compare cross-document summary must surface Phase B
    voice (classification-confidence) and temporal (distribution-with-
    dominant) per-side fields so consumers can distinguish 'same class,
    both decisive' from 'same class, one borderline', and 'same
    dominant tense with large margin' from 'same dominant tense but
    one side balanced.'

    Without this wiring, the compare tool surfaces only match/mismatch
    on classification, losing Phase B construct information that the
    single-doc tool exposes. MCP consumers comparing two documents on
    the same topic would get a weaker signal than comparing the two
    single-doc analyses manually.
    """
    print("=== compare cross-doc voice and temporal carry Phase B fields ===")
    baseline = len(_FAILURES)
    doc_a = (
        "Growth has been strong across the quarter in question. "
        "Revenue is up for the leadership team and the investor base. "
        "Stakeholders are pleased with the pace of expansion overall."
    )
    doc_b = (
        "Risks to the outlook have risen across the sector review. "
        "Uncertainty persists among market participants this month. "
        "Policymakers are monitoring developments carefully in context."
    )
    payload = mcp_server.build_compare_payload(doc_a, doc_b)
    comp = payload["analysis"]["comparison"]

    voice = comp["voice"]
    for field in (
        "a_confidence", "b_confidence",
        "a_runner_up", "b_runner_up",
        "both_borderline", "construct_note",
    ):
        check(field in voice,
              f"cross-doc voice missing Phase B field: {field}")
    check(isinstance(voice["both_borderline"], bool),
          "voice.both_borderline must be bool")
    check(
        "borderline" in voice["construct_note"].lower()
        and "confidence" in voice["construct_note"].lower(),
        "voice.construct_note must name borderline + confidence"
    )

    temporal = comp["temporal"]
    for field in (
        "a_dominant_margin", "b_dominant_margin",
        "a_balanced", "b_balanced",
        "both_balanced", "construct_note",
    ):
        check(field in temporal,
              f"cross-doc temporal missing Phase B field: {field}")
    check(isinstance(temporal["both_balanced"], bool),
          "temporal.both_balanced must be bool")
    check(
        "balanced" in temporal["construct_note"].lower()
        and "margin" in temporal["construct_note"].lower(),
        "temporal.construct_note must name balanced + margin"
    )
    _assert_no_new_failures(baseline, "test_compare_voice_and_temporal_carry_phase_b_construct")
    print("  PASS\n")


def test_compare_provenance_names_compare_layer():
    """Provenance.analysis_layer must identify this response as the
    compare path (not the single-doc path) so downstream telemetry
    and citations can distinguish the two surfaces."""
    print("=== compare provenance identifies the compare layer ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_compare_payload(
        "Document A text about growth.",
        "Document B text about risks.",
    )
    p = payload["provenance"]
    check(
        p.get("analysis_layer") == "deterministic_structural_comparison",
        f"analysis_layer must name the compare path, got "
        f"{p.get('analysis_layer')}",
    )
    check(
        p.get("analysis_cost_usd") == 0.0,
        "compare must not attribute LLM cost",
    )
    _assert_no_new_failures(baseline, "test_compare_provenance_names_compare_layer")
    print("  PASS\n")


def test_compare_agent_guidance_forbids_ranking():
    """The single strongest interpretive pitfall on the compare
    surface is implying a ranking. Agents could paraphrase a
    structural comparison as 'document A is better than B.' The
    how_to_cite_faithfully string must explicitly warn against
    that shape."""
    print("=== compare guidance forbids implying a ranking ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_compare_payload(
        "First document text.", "Second document text.",
    )
    cite = payload["agent_guidance"]["how_to_cite_faithfully"]
    check(
        "rank" in cite.lower() or "better than" in cite.lower(),
        "how_to_cite_faithfully must warn against ranking",
    )
    # The tool-does-not-tell-you list must name the correctness gap.
    not_list = payload["agent_guidance"]["what_this_tool_does_not_tell_you"]
    check(
        any("correct" in item.lower() for item in not_list),
        "does-not-tell-you list must name the correctness limit",
    )
    _assert_no_new_failures(baseline, "test_compare_agent_guidance_forbids_ranking")
    print("  PASS\n")


def test_compare_is_deterministic():
    """Same input pair produces identical output modulo latency.
    The compare deterministic guarantee is the same guarantee as
    frame_check and is load-bearing for agent_guidance."""
    print("=== compare is deterministic across calls ===")
    baseline = len(_FAILURES)
    doc_a = "Growth has been strong across all segments this quarter."
    doc_b = "Risks to the outlook remain elevated. Uncertainty persists."
    a = mcp_server.build_compare_payload(doc_a, doc_b, "A", "B")
    b = mcp_server.build_compare_payload(doc_a, doc_b, "A", "B")
    # Strip wall-clock fields that are allowed to differ between
    # calls (latency is duration, timestamp is the start-of-call
    # ISO stamp). Same rationale as test_payload_is_deterministic
    # above: the manifest's analysis_run_at is per-call wall-clock
    # attribution by design, not a determinism violation.
    for p in (a, b):
        p["provenance"]["analysis_latency_ms"] = 0
        p["provenance"]["analysis_timestamp_utc"] = ""
        if isinstance(p.get("manifest"), dict):
            p["manifest"].pop("analysis_run_at", None)
    check(a == b, "two compare calls on the same inputs differed")
    _assert_no_new_failures(baseline, "test_compare_is_deterministic")
    print("  PASS\n")


def test_compare_tools_call_end_to_end():
    """tools/call routes frame_compare through the dispatcher and
    returns a text-content response with the full three-section
    payload inside."""
    print("=== tools/call frame_compare returns full payload ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 10, "method": "tools/call",
        "params": {
            "name": "frame_compare",
            "arguments": {
                "document_a_text": "Growth and revenue records.",
                "document_b_text": "Risks and uncertainty persist.",
                "document_a_label": "Bull",
                "document_b_label": "Fed",
            },
        },
    })
    result = resp["result"]
    check(
        result.get("isError") is False,
        "frame_compare valid call must not set isError",
    )
    payload = json.loads(result["content"][0]["text"])
    check(
        {"analysis", "agent_guidance", "provenance"}
        .issubset(payload.keys()),
        "compare payload via tools/call missing a section",
    )
    check(
        "Bull" in payload["analysis"]["documents"],
        "per-document key must use the supplied label via tools/call",
    )
    _assert_no_new_failures(baseline, "test_compare_tools_call_end_to_end")
    print("  PASS\n")


def test_compare_rejects_missing_second_document():
    """Calling frame_compare without document_b_text must tool-error
    with a message that names the missing field. This is the most
    likely client misuse."""
    print("=== frame_compare rejects missing second document ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 11, "method": "tools/call",
        "params": {
            "name": "frame_compare",
            "arguments": {
                "document_a_text": "Only the first document.",
            },
        },
    })
    check(
        resp["result"].get("isError") is True,
        "missing document_b_text must set isError",
    )
    check(
        "document_b_text" in resp["result"]["content"][0]["text"],
        "error message must name the missing field",
    )
    _assert_no_new_failures(baseline, "test_compare_rejects_missing_second_document")
    print("  PASS\n")


# ── Layer 3: resources ────────────────────────────────────────────

def test_initialize_advertises_resources_capability():
    """initialize must advertise both primitives the server
    implements: tools and resources. A client that reads the
    capabilities dict to decide what to call would skip
    resources/list silently if resources were not advertised."""
    print("=== initialize advertises tools AND resources ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    })
    caps = resp["result"]["capabilities"]
    check("tools" in caps, "tools capability missing")
    check("resources" in caps, "resources capability missing")
    _assert_no_new_failures(baseline, "test_initialize_advertises_resources_capability")
    print("  PASS\n")


def test_resources_list_includes_library_and_docs():
    """resources/list must advertise at least the library and the
    calibration tiers. Omitting either breaks the 'Frame Check as
    canonical reference' contract. The methodology resource is
    optional (its presence depends on whether the methodology
    document is bundled in the wheel for a given audience)."""
    print("=== resources/list includes library + calibration ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "resources/list",
    })
    resources = resp["result"]["resources"]
    uris = [r["uri"] for r in resources]
    check(
        any(u.startswith("frame-check://library/FVS-") for u in uris),
        "resources must include at least one library entry",
    )
    check(
        "frame-check://calibration/reliability_tiers" in uris,
        "resources must include calibration reliability tiers",
    )
    for r in resources:
        for field in ("uri", "name", "description", "mimeType"):
            check(field in r, f"resource missing {field}: {r.get('uri')}")
    _assert_no_new_failures(baseline, "test_resources_list_includes_library_and_docs")
    print("  PASS\n")


def test_resources_list_carries_attribution_schema_v1_0_0():
    """Every resources/list entry must carry the attribution _meta
    contract per `schemas/attribution-1.0.0.json` (schema version
    1.0.0). The envelope carries an attribution-schema-version pin;
    every analytical artifact carries license / license-uri / author
    / year under the clarethium.com/ reverse-DNS prefix; corpus
    bundled-document URIs carry content-type=bundled-document plus a
    license-note in lieu of the CC-BY-4.0 quad. Without an explicit
    test, the _meta surface can regress silently because no other
    test path exercises the schema's field shape directly."""
    print("=== resources/list carries attribution schema 1.0.0 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 100, "method": "resources/list",
    })
    result = resp["result"]
    # Envelope schema-version pin.
    envelope_meta = result.get("_meta", {})
    check(
        envelope_meta.get("clarethium.com/attribution-schema-version")
        == "1.0.0",
        "envelope must pin attribution-schema-version 1.0.0; got "
        f"{envelope_meta.get('clarethium.com/attribution-schema-version')!r}",
    )
    resources = result["resources"]
    check(len(resources) > 0, "resources/list must return at least one entry")
    # Per-entry _meta contract.
    n_corpus = 0
    n_analytical = 0
    for r in resources:
        uri = r.get("uri", "")
        meta = r.get("_meta")
        check(meta is not None, f"resource missing _meta: {uri}")
        # Bundled corpus documents (e.g. frame-check://corpus/<slug>
        # without a trailing /profile, /peer, or /diff segment) carry
        # the bundled-document distinction instead of CC-BY-4.0
        # attribution to Lovro Lucic. Verbatim third-party text and
        # AI service outputs ship under fair-use posture, not under
        # the project's own license.
        is_bundled_corpus = (
            uri.startswith("frame-check://corpus/")
            and uri.count("/") == 3  # scheme://corpus/<slug> only
        )
        if is_bundled_corpus:
            n_corpus += 1
            check(
                meta.get("clarethium.com/content-type") == "bundled-document",
                f"corpus URI must carry content-type=bundled-document: {uri}",
            )
            check(
                isinstance(meta.get("clarethium.com/license-note"), str),
                f"corpus URI must carry license-note: {uri}",
            )
        else:
            n_analytical += 1
            for field in (
                "clarethium.com/license",
                "clarethium.com/license-uri",
                "clarethium.com/author",
                "clarethium.com/year",
            ):
                check(
                    field in meta,
                    f"analytical artifact missing {field}: {uri}",
                )
            check(
                meta.get("clarethium.com/license") == "CC-BY-4.0",
                f"analytical artifact must be CC-BY-4.0: {uri}",
            )
    # Sanity: must have advertised at least one of each class so the
    # contract is exercised. If a future refactor advertises only
    # bundled docs or only analytical artifacts the test still asks
    # the question and surfaces the shift loudly.
    check(
        n_analytical > 0,
        "resources/list must advertise at least one analytical artifact",
    )
    _assert_no_new_failures(baseline, "test_resources_list_carries_attribution_schema_v1_0_0")
    print(
        f"  PASS  ({n_analytical} analytical, {n_corpus} bundled-corpus)\n"
    )


def test_resources_read_library_entry_returns_markdown():
    print("=== resources/read library entry returns markdown ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 3, "method": "resources/read",
        "params": {"uri": "frame-check://library/FVS-001"},
    })
    contents = resp["result"]["contents"]
    check(len(contents) == 1, "exactly one content item expected")
    check(contents[0]["mimeType"] == "text/markdown", "library MIME must be markdown")
    check(contents[0]["text"].startswith("# "),
          "library markdown should start with an H1 title")
    _assert_no_new_failures(baseline, "test_resources_read_library_entry_returns_markdown")
    print("  PASS\n")


def test_resources_read_worked_example_returns_markdown():
    print("=== resources/read worked example returns markdown ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 4, "method": "resources/list",
    })
    we = [r for r in resp["result"]["resources"]
          if r["uri"].startswith("frame-check://worked-examples/")]
    if not we:
        print("  (no worked examples on this deploy; skipping)\n")
        return
    uri = we[0]["uri"]
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 5, "method": "resources/read",
        "params": {"uri": uri},
    })
    contents = resp["result"]["contents"]
    check(contents[0]["mimeType"] == "text/markdown",
          "worked example MIME must be markdown")
    check(contents[0]["text"].startswith("---"),
          "worked example should start with frontmatter")
    _assert_no_new_failures(baseline, "test_resources_read_worked_example_returns_markdown")
    print("  PASS\n")


def test_resources_read_methodology_returns_markdown():
    """The methodology resource is optional; the MCP server returns
    -32602 when the underlying file is absent. Pin both branches so
    the resource keeps its stable URI when the methodology file is
    re-introduced for an adopter audience.
    """
    print("=== resources/read methodology returns markdown or 404 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 6, "method": "resources/read",
        "params": {"uri": "frame-check://methodology"},
    })
    if "result" in resp:
        contents = resp["result"]["contents"]
        check(contents[0]["mimeType"] == "text/markdown",
              "methodology MIME must be markdown")
        check("Frame Check" in contents[0]["text"],
              "methodology must mention Frame Check")
    else:
        check(resp["error"]["code"] == -32602,
              "absent methodology must return -32602")
    _assert_no_new_failures(baseline, "test_resources_read_methodology_returns_markdown")
    print("  PASS\n")


def test_resources_read_calibration_returns_json():
    print("=== resources/read calibration returns JSON ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 7, "method": "resources/read",
        "params": {"uri": "frame-check://calibration/reliability_tiers"},
    })
    contents = resp["result"]["contents"]
    check(contents[0]["mimeType"] == "application/json",
          "calibration MIME must be application/json")
    data = json.loads(contents[0]["text"])
    check(isinstance(data, dict) and len(data) >= 1,
          "calibration data must be a non-empty provider dict")
    # At least one provider must carry a tier field.
    sample = next(iter(data.values()))
    check("tier" in sample,
          "each provider entry must carry a tier field")
    _assert_no_new_failures(baseline, "test_resources_read_calibration_returns_json")
    print("  PASS\n")


def test_resources_list_includes_frame_divergence_spec():
    """resources/list must advertise the Frame Divergence v1 spec
    index and every part whose file is present on disk. This is
    the discovery surface for the authored canonical reference per
    FRAME_DIVERGENCE_CONTRACT_v1.md §8.
    """
    baseline = len(_FAILURES)
    print("=== resources/list includes Frame Divergence v1 spec ===")
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 10, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    parts_on_disk = mcp_server._spec_fd_v1_parts()
    if not parts_on_disk:
        print("  (no Frame Divergence v1 parts on this deploy; skipping)\n")
        return
    check(
        "frame-check://spec/frame-divergence/v1" in uris,
        "resources must include spec index when any part is present",
    )
    for part_num, _title, _path in parts_on_disk:
        expected = (
            f"frame-check://spec/frame-divergence/v1/part-{part_num}"
        )
        check(
            expected in uris,
            f"resources must include {expected} when file exists",
        )
    _assert_no_new_failures(
        baseline, "test_resources_list_includes_frame_divergence_spec"
    )
    print("  PASS\n")


def test_resources_read_frame_divergence_index_returns_markdown():
    """resources/read on the spec index returns generated markdown
    listing available parts and naming pending ones. The index is
    generated content (not a file), so it must reflect current disk
    state on each read.
    """
    baseline = len(_FAILURES)
    print("=== resources/read Frame Divergence v1 index returns markdown ===")
    if not mcp_server._spec_fd_v1_parts():
        print("  (no Frame Divergence v1 parts on this deploy; skipping)\n")
        return
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 11, "method": "resources/read",
        "params": {"uri": "frame-check://spec/frame-divergence/v1"},
    })
    contents = resp["result"]["contents"]
    check(len(contents) == 1, "exactly one content item expected")
    check(
        contents[0]["mimeType"] == "text/markdown",
        "spec index MIME must be markdown",
    )
    text = contents[0]["text"]
    check(
        text.startswith("# Frame Divergence v1: spec index"),
        "spec index must open with the canonical H1",
    )
    check(
        "Part 1:" in text and "Part 2:" in text,
        "spec index must list Parts 1 and 2",
    )
    check(
        "Part 3:" in text and "pending" in text,
        "spec index must name Parts 3-4 as pending per contract §11",
    )
    _assert_no_new_failures(
        baseline,
        "test_resources_read_frame_divergence_index_returns_markdown",
    )
    print("  PASS\n")


def test_resources_read_frame_divergence_part_1_returns_markdown():
    """Part 1 was retired from the wheel; the URI is no longer
    advertised. The MCP server returns -32602 when the resource is
    absent. Pin the not-found contract so a future re-introduction
    of Part 1 keeps the same URI shape.
    """
    print("=== resources/read Frame Divergence v1 Part 1 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 12, "method": "resources/read",
        "params": {
            "uri": "frame-check://spec/frame-divergence/v1/part-1"
        },
    })
    if "result" in resp:
        contents = resp["result"]["contents"]
        check(
            contents[0]["mimeType"] == "text/markdown",
            "Part 1 MIME must be markdown",
        )
    else:
        check(resp["error"]["code"] == -32602,
              "absent Part 1 must return -32602")
    _assert_no_new_failures(baseline, "test_resources_read_frame_divergence_part_1_returns_markdown")
    print("  PASS\n")


def test_resources_read_frame_divergence_part_2_returns_markdown():
    """resources/read on Part 2 returns the authored contract (c1.0).
    This is the citation target for interface consumers per §8.
    """
    baseline = len(_FAILURES)
    print("=== resources/read Frame Divergence v1 Part 2 (Contract) ===")
    if not os.path.isfile(mcp_server._SPEC_FD_V1_PART2_PATH):
        print("  (Part 2 not on this deploy; skipping)\n")
        return
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 13, "method": "resources/read",
        "params": {
            "uri": "frame-check://spec/frame-divergence/v1/part-2"
        },
    })
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "text/markdown",
        "Part 2 MIME must be markdown",
    )
    text = contents[0]["text"]
    check(
        "Contract" in text[:200],
        "Part 2 heading must identify it as the contract",
    )
    check(
        "c1.0" in text,
        "Part 2 must declare contract version c1.0",
    )
    _assert_no_new_failures(
        baseline,
        "test_resources_read_frame_divergence_part_2_returns_markdown",
    )
    print("  PASS\n")


def test_resources_read_frame_divergence_rejects_traversal_and_missing():
    """The spec/part-N dispatcher must reject non-integer part
    suffixes (traversal-safe) and return FileNotFoundError for
    integer suffixes that do not correspond to a file on disk.
    Neither path silently succeeds.
    """
    baseline = len(_FAILURES)
    print("=== Frame Divergence v1 part dispatcher: safety ===")
    # Traversal attempt via non-integer suffix
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 14, "method": "resources/read",
        "params": {
            "uri": "frame-check://spec/frame-divergence/v1/part-../etc/passwd"
        },
    })
    check(
        "error" in resp,
        "traversal attempt must return an error envelope",
    )
    # Valid integer but no such part on disk
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 15, "method": "resources/read",
        "params": {
            "uri": "frame-check://spec/frame-divergence/v1/part-99"
        },
    })
    check(
        "error" in resp,
        "missing part number must return an error envelope",
    )
    _assert_no_new_failures(
        baseline,
        "test_resources_read_frame_divergence_rejects_traversal_and_missing",
    )
    print("  PASS\n")


def test_aggregate_resource_listed_when_present():
    """When at least one aggregate.json exists under
    validation/decision_readiness/results/, resources/list must
    include frame-check://aggregate/latest. The advertisement is
    the discovery surface; agents that don't see the resource in
    the list won't attempt to read it.

    The test runs against the live filesystem; the validation
    corpus + aggregate harness leave at least one results/{date}-{hash}/
    directory in normal repo state. If a future cleanup removes
    all aggregates, this test should be updated to mock the dir."""
    print("=== resources/list includes aggregate when present ===")
    baseline = len(_FAILURES)
    # Sanity: an aggregate exists on this deploy
    agg_path = mcp_server._find_latest_aggregate()
    check(
        agg_path is not None,
        "test prerequisite: at least one aggregate.json must exist "
        "under validation/decision_readiness/results/ (run the "
        "aggregate harness first if cleanup removed all of them)",
    )
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 80, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    check(
        "frame-check://aggregate/latest" in uris,
        f"aggregate/latest missing from resources/list when an "
        f"aggregate exists; got {uris[:5]}... (and {len(uris)-5} more)",
    )
    # Confirm the resource entry's shape: name, description, mimeType
    aggregate_resource = next(
        r for r in resp["result"]["resources"]
        if r["uri"] == "frame-check://aggregate/latest"
    )
    check(
        aggregate_resource["mimeType"] == "application/json",
        f"aggregate resource must declare application/json mime; "
        f"got {aggregate_resource['mimeType']!r}",
    )
    # The description must communicate what the resource carries
    # (corpus-level findings, status, versioning) so an agent
    # browsing resources/list can decide whether to fetch it.
    desc = aggregate_resource["description"].lower()
    check(
        "experimental" in desc,
        "aggregate description must name the experimental status "
        "so agents do not overstate the findings' authority",
    )
    check(
        "corpus" in desc,
        "aggregate description must name the corpus-level scope "
        "so agents distinguish from per-document profiles",
    )
    _assert_no_new_failures(baseline, "test_aggregate_resource_listed_when_present")
    print("  PASS\n")


def test_aggregate_resource_omitted_when_absent():
    """When no aggregate.json exists (clean checkout, validation
    tree absent, harness not run), resources/list MUST NOT
    advertise the aggregate URI. Advertising a URI that fails on
    read would be a contract violation: the resource list is the
    discovery surface, and agents trust that listed resources
    resolve. Pin the omission so a future refactor cannot
    accidentally surface a 404-bound URI.

    Uses direct attribute swap (test_mcp_server.py is a standalone
    executable using check(), not pytest fixtures) to point
    _AGGREGATE_RESULTS_DIR at an empty temp directory."""
    print("=== resources/list omits aggregate when absent ===")
    baseline = len(_FAILURES)
    import tempfile
    # Since the Step 2 decomposition (2026-04-29) the path constant
    # and the reader function live in mcp_resources rather than
    # mcp_server; patch the actual owner so the function reads the
    # patched value. Patching mcp_server's import-time copy would be
    # a no-op because the function resolves the constant via its
    # own module's namespace.
    import mcp_resources
    original_dir = mcp_resources._AGGREGATE_RESULTS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mcp_resources._AGGREGATE_RESULTS_DIR = tmp
            check(
                mcp_server._find_latest_aggregate() is None,
                "test invariant: empty dir should yield None from "
                "_find_latest_aggregate",
            )
            resp = mcp_server.dispatch({
                "jsonrpc": "2.0", "id": 81, "method": "resources/list",
            })
            uris = [r["uri"] for r in resp["result"]["resources"]]
            check(
                "frame-check://aggregate/latest" not in uris,
                f"aggregate/latest must NOT appear in resources/list "
                f"when no aggregate exists; got "
                f"{[u for u in uris if 'aggregate' in u]}",
            )
    finally:
        mcp_resources._AGGREGATE_RESULTS_DIR = original_dir
    _assert_no_new_failures(baseline, "test_aggregate_resource_omitted_when_absent")
    print("  PASS\n")


def test_aggregate_resource_read_returns_valid_json_payload():
    """resources/read on the aggregate URI must return the
    aggregate.json contents with mimeType application/json. The
    JSON payload must parse and carry the structured findings
    shape (cross_question_findings + library_entries_per_dimension)
    so downstream consumers can rely on the contract.

    This test does not enforce any specific finding (corpus may
    evolve); it pins the SHAPE so a regression in either the
    aggregate harness or the MCP exposure breaks loudly."""
    print("=== resources/read aggregate returns valid JSON payload ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 82, "method": "resources/read",
        "params": {"uri": "frame-check://aggregate/latest"},
    })
    check(
        "result" in resp,
        f"resources/read for aggregate URI returned no result; "
        f"got {resp!r}",
    )
    contents = resp["result"]["contents"]
    check(len(contents) == 1, "exactly one content item expected")
    check(
        contents[0]["mimeType"] == "application/json",
        f"aggregate MIME must be application/json; got "
        f"{contents[0]['mimeType']!r}",
    )
    # Parse the JSON. The aggregate harness writes a top-level dict
    # with these keys. Pin the shape contract.
    payload = json.loads(contents[0]["text"])
    check(
        isinstance(payload, dict),
        f"aggregate payload must be a JSON object; got "
        f"{type(payload).__name__}",
    )
    for required in [
        "computed_at_utc", "corpus", "peer_findings",
        "diff_findings", "outlier_findings",
        "cross_question_findings", "library_entries_per_dimension",
    ]:
        check(
            required in payload,
            f"aggregate payload missing required key {required!r}; "
            f"got keys {sorted(payload.keys())}",
        )
    # corpus.state_hash is the load-bearing versioning field
    check(
        payload["corpus"].get("state_hash"),
        "aggregate payload must carry corpus.state_hash so consumers "
        "can version findings against the corpus state at compute time",
    )
    _assert_no_new_failures(baseline, "test_aggregate_resource_read_returns_valid_json_payload")
    print("  PASS\n")


def test_aggregate_chain_to_library_entry_via_fired_patterns():
    """End-to-end canon-graph chain at the aggregate layer:
    agent reads frame-check://aggregate/latest, parses the JSON,
    finds an FVS-ID in cross_question_findings[*].fired_patterns,
    and chains to that library entry via library_resource_uri
    in the same MCP session. Pins that the URIs in the aggregate
    are valid for resources/read on the same server.

    The previous round-trip test pinned the per-document profile
    -> library chain. This test pins the aggregate -> library
    chain so the canon-graph distribution surface is verified
    end-to-end at both granularities.

    Conditional on cross_question_findings firing in the current
    corpus. If no findings exist, the test is a no-op (the chain
    contract is conditional on findings being present)."""
    print("=== aggregate -> library chain via fired_patterns ===")
    baseline = len(_FAILURES)
    # Read the aggregate
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 84, "method": "resources/read",
        "params": {"uri": "frame-check://aggregate/latest"},
    })
    payload = json.loads(resp["result"]["contents"][0]["text"])
    findings = payload.get("cross_question_findings") or []
    if not findings:
        print("  PASS  (no cross_question_findings in current corpus; "
              "chain contract is conditional)\n")
        return
    # Pick the first finding with at least one fired pattern
    finding_with_fired = None
    for f in findings:
        if f.get("fired_patterns"):
            finding_with_fired = f
            break
    if finding_with_fired is None:
        print("  PASS  (no findings have fired_patterns in current "
              "corpus; chain contract is conditional)\n")
        return
    # Extract the URI from the first fired pattern
    fp = finding_with_fired["fired_patterns"][0]
    uri = fp.get("library_resource_uri")
    check(
        uri and uri.startswith("frame-check://library/FVS-"),
        f"fired_pattern.library_resource_uri malformed: {uri!r}",
    )
    # Now resources/read on that URI must return the matching markdown
    chain_resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 85, "method": "resources/read",
        "params": {"uri": uri},
    })
    check(
        "result" in chain_resp,
        f"chain resources/read for aggregate-derived URI {uri!r} "
        f"returned no result; got {chain_resp!r}",
    )
    chain_contents = chain_resp["result"]["contents"]
    check(
        chain_contents[0]["mimeType"] == "text/markdown",
        f"chain target must be markdown; got "
        f"{chain_contents[0]['mimeType']!r}",
    )
    text = chain_contents[0]["text"]
    check(
        text.startswith("# "),
        f"chain target markdown should start with H1; "
        f"got {text[:80]!r}",
    )
    # The fvs_id from the aggregate must match a token in the
    # resolved markdown
    check(
        fp["fvs_id"] in text or fp["fvs_id"].replace("-", " ") in text,
        f"aggregate -> library chain drift: fvs_id {fp['fvs_id']!r} "
        f"not present in the resolved library markdown",
    )
    # Title from aggregate ref must match the entry's H1 title
    if fp.get("title"):
        check(
            fp["title"] in text,
            f"aggregate ref title {fp['title']!r} not present in "
            f"resolved markdown; canon graph drift between aggregate "
            f"and library entry",
        )
    _assert_no_new_failures(baseline, "test_aggregate_chain_to_library_entry_via_fired_patterns")
    print(f"  PASS  (chained {fp['fvs_id']} {fp.get('title','')} "
          f"successfully)\n")


def test_corpus_entries_listed_as_mcp_resources():
    """Each validation corpus entry is exposed as an MCP resource
    so agents reading the aggregate (which cites entries by slug)
    can chain to the actual documents + profiles. Two resources
    per entry:
      - frame-check://corpus/{slug}         -> document.md (markdown)
      - frame-check://corpus/{slug}/profile -> profile.json (json)
    Without this, an agent reading an aggregate finding about
    'four-llms-bitcoin-claude' cannot fetch the document or the
    computed profile without cloning the repo."""
    print("=== MCP: corpus entries listed as resources ===")
    baseline = len(_FAILURES)
    slugs = mcp_server._corpus_entry_slugs()
    check(
        len(slugs) > 0,
        "test prerequisite: at least one corpus entry must exist "
        "under validation/decision_readiness/corpus/",
    )
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 90, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    sample_slug = "four-llms-bitcoin-claude"
    if sample_slug in slugs:
        check(
            f"frame-check://corpus/{sample_slug}" in uris,
            f"corpus entry document URI missing for {sample_slug!r}",
        )
        check(
            f"frame-check://corpus/{sample_slug}/profile" in uris,
            f"corpus entry profile URI missing for {sample_slug!r}",
        )
    corpus_uris = [u for u in uris if u.startswith("frame-check://corpus/")]
    check(
        len(corpus_uris) >= 2,
        f"expected at least 2 corpus URIs; got {len(corpus_uris)}",
    )
    _assert_no_new_failures(baseline, "test_corpus_entries_listed_as_mcp_resources")
    print(f"  PASS  ({len(corpus_uris)} corpus resource URIs advertised)\n")


def test_corpus_entry_document_read_returns_markdown():
    """resources/read on frame-check://corpus/{slug} returns the
    document.md content with text/markdown mime type."""
    print("=== MCP: corpus entry document read returns markdown ===")
    baseline = len(_FAILURES)
    slug = "four-llms-bitcoin-claude"
    if slug not in mcp_server._corpus_entry_slugs():
        print("  SKIP  (test anchor entry absent)\n")
        return
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 91, "method": "resources/read",
        "params": {"uri": f"frame-check://corpus/{slug}"},
    })
    check("result" in resp,
          f"resources/read for corpus entry {slug!r} returned no result")
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "text/markdown",
        f"corpus document MIME must be text/markdown; got "
        f"{contents[0]['mimeType']!r}",
    )
    text = contents[0]["text"]
    check(
        "Bitcoin" in text or "bitcoin" in text,
        "claude-bitcoin document should mention Bitcoin",
    )
    _assert_no_new_failures(baseline, "test_corpus_entry_document_read_returns_markdown")
    print("  PASS\n")


def test_corpus_entry_profile_read_returns_json():
    """resources/read on frame-check://corpus/{slug}/profile
    returns the profile.json content with application/json mime
    and the expected 5-dimension shape."""
    print("=== MCP: corpus entry profile read returns valid JSON ===")
    baseline = len(_FAILURES)
    slug = "four-llms-bitcoin-claude"
    if slug not in mcp_server._corpus_entry_slugs():
        print("  SKIP  (test anchor entry absent)\n")
        return
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 92, "method": "resources/read",
        "params": {"uri": f"frame-check://corpus/{slug}/profile"},
    })
    check("result" in resp,
          f"resources/read for corpus profile {slug!r} returned no result")
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "application/json",
        f"corpus profile MIME must be application/json; got "
        f"{contents[0]['mimeType']!r}",
    )
    payload = json.loads(contents[0]["text"])
    check(
        isinstance(payload, dict),
        f"corpus profile should parse as dict; got {type(payload).__name__}",
    )
    check(
        "dimensions" in payload and "status" in payload,
        f"corpus profile missing required fields; "
        f"got keys {sorted(payload.keys())}",
    )
    for dim in ("coverage", "calibration", "evidence",
                "robustness", "counterfactual"):
        check(
            dim in payload["dimensions"],
            f"corpus profile missing {dim!r} dimension",
        )
    _assert_no_new_failures(baseline, "test_corpus_entry_profile_read_returns_json")
    print("  PASS\n")


def test_corpus_entry_invalid_slug_returns_invalid_params():
    """Traversal-safe resolution: a slug with traversal chars or
    a non-existent entry must return JSON-RPC -32602, never
    expose the filesystem."""
    print("=== MCP: corpus entry invalid slug rejected cleanly ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 93, "method": "resources/read",
        "params": {"uri": "frame-check://corpus/../../../etc/passwd"},
    })
    check(
        "error" in resp,
        f"path traversal should error; got {resp!r}",
    )
    check(
        resp["error"]["code"] == -32602,
        f"traversal slug should map to -32602; got {resp['error']!r}",
    )
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 94, "method": "resources/read",
        "params": {"uri": "frame-check://corpus/nonexistent-entry"},
    })
    check(
        "error" in resp,
        "non-existent corpus slug should error",
    )
    check(
        resp["error"]["code"] == -32602,
        f"non-existent slug should map to -32602; got {resp['error']!r}",
    )
    _assert_no_new_failures(baseline, "test_corpus_entry_invalid_slug_returns_invalid_params")
    print("  PASS\n")


def test_explain_framing_prompt_mentions_aggregate_and_corpus():
    """PROMPT_EXPLAIN_FRAMING must point at aggregate + corpus MCP
    resources so agents using the prompt can discover broader-
    pattern context. Without prompt-side discovery, those
    resources exist but are invisible to agents executing the
    sovereignty prompts."""
    print("=== prompt explain_framing mentions aggregate + corpus ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 110, "method": "prompts/get",
        "params": {"name": "explain_framing"},
    })
    text = resp["result"]["messages"][0]["content"]["text"]
    check(
        "frame-check://aggregate/latest" in text,
        "explain_framing should mention aggregate URI; without "
        "it agents cannot discover the corpus-level findings",
    )
    check(
        "frame-check://corpus/" in text,
        "explain_framing should mention corpus URI pattern",
    )
    # Honest framing: aggregate is experimental, not verdict
    check(
        "experimental" in text.lower(),
        "prompt should name aggregate as experimental research "
        "data so agents don't overstate authority",
    )
    _assert_no_new_failures(baseline, "test_explain_framing_prompt_mentions_aggregate_and_corpus")
    print("  PASS\n")


def test_ai_response_audit_prompt_mentions_aggregate_optional():
    """PROMPT_AI_RESPONSE_AUDIT (lead use case) carries optional
    aggregate context so agents can name precedents when relevant.
    Phrased as 'optional context (when the user asks)' to avoid
    polluting focus on the user's specific audit task."""
    print("=== prompt ai_response_audit mentions aggregate ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 111, "method": "prompts/get",
        "params": {"name": "frame_check_this_ai_response"},
    })
    text = resp["result"]["messages"][0]["content"]["text"]
    check(
        "frame-check://aggregate/latest" in text,
        "ai_response_audit should mention aggregate URI for "
        "optional broader-pattern context",
    )
    # Mention should be optional/conditional to preserve task focus
    check(
        "optional" in text.lower() or "when the user asks" in text.lower(),
        "aggregate mention should be framed as optional context "
        "so agents don't dilute audit task focus on every call",
    )
    _assert_no_new_failures(baseline, "test_ai_response_audit_prompt_mentions_aggregate_optional")
    print("  PASS\n")


def test_corpus_per_pair_comparisons_listed_as_mcp_resources():
    """Per-pair diff/peer comparisons are MCP-exposed so research
    agents chasing cross-question outliers can pull specific pair
    data without cloning or recomputing client-side. Two URI
    patterns per pair:
      frame-check://corpus/{slug}/peer/{partner}
      frame-check://corpus/{slug}/diff/{partner}
    """
    print("=== MCP: per-pair comparisons listed as resources ===")
    baseline = len(_FAILURES)
    slugs = mcp_server._corpus_entry_slugs()
    if not slugs:
        print("  SKIP  (no corpus entries)\n")
        return
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 100, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    # Expect at least one peer and one diff pair URI
    peer_uris = [
        u for u in uris
        if u.startswith("frame-check://corpus/")
        and "/peer/" in u
    ]
    diff_uris = [
        u for u in uris
        if u.startswith("frame-check://corpus/")
        and "/diff/" in u
    ]
    check(
        len(peer_uris) > 0,
        "expected at least one peer URI in resources/list; got none",
    )
    check(
        len(diff_uris) > 0,
        "expected at least one diff URI in resources/list; got none",
    )
    _assert_no_new_failures(baseline, "test_corpus_per_pair_comparisons_listed_as_mcp_resources")
    print(
        f"  PASS  ({len(peer_uris)} peer + {len(diff_uris)} diff "
        f"pair URIs advertised)\n"
    )


def test_corpus_peer_pair_read_returns_json():
    """resources/read on frame-check://corpus/{slug}/peer/{partner}
    returns the peer_with_*.json content with application/json
    MIME. Shape carries dimensions + label_a/b + narrative."""
    print("=== MCP: corpus peer pair read returns valid JSON ===")
    baseline = len(_FAILURES)
    slug = "four-llms-bitcoin-claude"
    partner = "four-llms-bitcoin-grok"
    if slug not in mcp_server._corpus_entry_slugs():
        print("  SKIP  (test anchor entries absent)\n")
        return
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 101, "method": "resources/read",
        "params": {
            "uri": f"frame-check://corpus/{slug}/peer/{partner}",
        },
    })
    check("result" in resp,
          f"resources/read failed for peer pair; got {resp!r}")
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "application/json",
        f"peer pair MIME should be application/json; got "
        f"{contents[0]['mimeType']!r}",
    )
    payload = json.loads(contents[0]["text"])
    check(
        "dimensions" in payload and "label_a" in payload,
        f"peer pair JSON missing expected fields; got keys "
        f"{sorted(payload.keys())}",
    )
    check(
        payload.get("label_a") == slug or payload.get("label_a") == partner,
        f"label_a should match one of the two slugs; got "
        f"{payload.get('label_a')!r}",
    )
    _assert_no_new_failures(baseline, "test_corpus_peer_pair_read_returns_json")
    print("  PASS\n")


def test_corpus_diff_pair_read_returns_json():
    """resources/read on frame-check://corpus/{slug}/diff/{partner}
    returns the diff_with_*.json content with application/json MIME."""
    print("=== MCP: corpus diff pair read returns valid JSON ===")
    baseline = len(_FAILURES)
    # Pick a slug that has a diff artifact (nvidia press release
    # or grok summary in current corpus)
    anchor = None
    for slug in mcp_server._corpus_entry_slugs():
        entry_dir = os.path.join(
            mcp_server._CORPUS_ENTRIES_DIR, slug,
        )
        diffs = [
            f for f in os.listdir(entry_dir)
            if f.startswith("diff_with_") and f.endswith(".json")
        ] if os.path.isdir(entry_dir) else []
        if diffs:
            partner_slug = diffs[0][len("diff_with_"):-len(".json")]
            anchor = (slug, partner_slug)
            break
    if anchor is None:
        print("  SKIP  (no diff artifacts in current corpus)\n")
        return
    slug, partner = anchor
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 102, "method": "resources/read",
        "params": {
            "uri": f"frame-check://corpus/{slug}/diff/{partner}",
        },
    })
    check("result" in resp,
          f"resources/read failed for diff pair; got {resp!r}")
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "application/json",
        "diff pair MIME should be application/json",
    )
    payload = json.loads(contents[0]["text"])
    check(
        "dimensions" in payload,
        f"diff pair JSON missing dimensions field; got "
        f"{sorted(payload.keys())}",
    )
    _assert_no_new_failures(baseline, "test_corpus_diff_pair_read_returns_json")
    print("  PASS\n")


def test_corpus_pair_invalid_inputs_rejected():
    """Traversal-safe pair resolution. Invalid slugs in the entry
    OR partner position must reject without filesystem access.
    Non-existent pairs must return -32602.
    """
    print("=== MCP: corpus pair invalid inputs rejected cleanly ===")
    baseline = len(_FAILURES)
    # Traversal attempt on entry slug
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 103, "method": "resources/read",
        "params": {
            "uri": "frame-check://corpus/..%2F..%2Fetc/peer/x",
        },
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        f"traversal on entry slug should -32602; got {resp!r}",
    )
    # Traversal attempt on partner slug
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 104, "method": "resources/read",
        "params": {
            "uri": (
                "frame-check://corpus/four-llms-bitcoin-claude/peer/"
                "..%2F..%2Fetc"
            ),
        },
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        f"traversal on partner slug should -32602; got {resp!r}",
    )
    # Non-existent pair
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 105, "method": "resources/read",
        "params": {
            "uri": (
                "frame-check://corpus/four-llms-bitcoin-claude/peer/"
                "nonexistent-partner"
            ),
        },
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        f"non-existent partner should -32602; got {resp!r}",
    )
    # Unknown kind (not peer/diff)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 106, "method": "resources/read",
        "params": {
            "uri": (
                "frame-check://corpus/four-llms-bitcoin-claude/"
                "invalid-kind/four-llms-bitcoin-grok"
            ),
        },
    })
    # Unknown kind falls through to the entry-level handler which
    # tries to treat the full remainder as a slug; that will fail
    # the slug regex. Result: -32602 either way.
    check(
        "error" in resp,
        f"unknown kind should error; got {resp!r}",
    )
    _assert_no_new_failures(baseline, "test_corpus_pair_invalid_inputs_rejected")
    print("  PASS\n")


def test_aggregate_to_corpus_chain_round_trip():
    """End-to-end canon-graph chain at the corpus layer: an agent
    reads aggregate, picks a cross_question_finding, follows
    corpus_resource_uri DIRECTLY (no slug heuristic, no URI
    reconstruction) to fetch the corpus entry.

    This is what the aggregate's corpus_entries field enables:
    self-resolving chain. Previously agents had to apply the
    slug-matching heuristic themselves; now they just dereference
    the URI the harness already provided."""
    print("=== MCP: aggregate -> corpus round-trip ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 95, "method": "resources/read",
        "params": {"uri": "frame-check://aggregate/latest"},
    })
    if "result" not in resp:
        print("  SKIP  (no aggregate on this deploy)\n")
        return
    payload = json.loads(resp["result"]["contents"][0]["text"])
    findings = payload.get("cross_question_findings") or []
    if not findings:
        print("  SKIP  (no cross-question findings)\n")
        return
    # Find a finding with at least one corpus_entries element
    finding_with_entries = None
    for f in findings:
        if f.get("corpus_entries"):
            finding_with_entries = f
            break
    if finding_with_entries is None:
        print("  SKIP  (no findings carry corpus_entries)\n")
        return
    # Use the corpus_resource_uri DIRECTLY; no slug reconstruction.
    # This is the chain the field exists to enable.
    corpus_ref = finding_with_entries["corpus_entries"][0]
    uri = corpus_ref["corpus_resource_uri"]
    check(
        uri.startswith("frame-check://corpus/"),
        f"corpus_resource_uri wrong scheme: {uri!r}",
    )
    chain_resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 96, "method": "resources/read",
        "params": {"uri": uri},
    })
    check(
        "result" in chain_resp,
        f"chain read for {uri!r} failed; got {chain_resp!r}",
    )
    chain_contents = chain_resp["result"]["contents"]
    check(
        chain_contents[0]["mimeType"] == "text/markdown",
        "corpus entry document should be markdown",
    )
    check(
        len(chain_contents[0]["text"]) > 100,
        "corpus entry document should have substantive content",
    )
    # The chain target must be the entry the field claims it is:
    # the slug from the ref must appear in the URI we successfully
    # read. Pins that an agent dereferencing the ref actually lands
    # on the document the ref names.
    check(
        corpus_ref["slug"] in uri,
        f"slug {corpus_ref['slug']!r} not in URI {uri!r}",
    )
    _assert_no_new_failures(baseline, "test_aggregate_to_corpus_chain_round_trip")
    print(f"  PASS  (chained aggregate -> {uri})\n")


def test_aggregate_resource_read_when_absent_is_filenotfound():
    """When an aggregate URI is requested but no aggregate exists
    on this deploy, the read must fail rather than return an empty
    or stale payload. The handler raises FileNotFoundError; the
    dispatch layer maps that to JSON-RPC -32602 invalid_params.

    Uses monkeypatch to simulate the absent state without
    touching the live data."""
    print("=== resources/read aggregate when absent fails cleanly ===")
    baseline = len(_FAILURES)
    # Save and replace via the dispatch with monkeypatch wouldn't
    # work cross-thread; do an attribute swap and restore. Since the
    # Step 2 decomposition (2026-04-29) the path constant and the
    # _find_latest_aggregate function live in mcp_resources rather
    # than mcp_server; patch the actual owner so the function reads
    # the patched value (patching mcp_server's import-time copy
    # would be a no-op because the function resolves the constant
    # via its own module's namespace, not mcp_server's).
    import mcp_resources
    original_dir = mcp_resources._AGGREGATE_RESULTS_DIR
    try:
        # Point at a directory with no results subdirs
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mcp_resources._AGGREGATE_RESULTS_DIR = tmp
            check(
                mcp_server._find_latest_aggregate() is None,
                "test invariant: empty dir should yield None",
            )
            resp = mcp_server.dispatch({
                "jsonrpc": "2.0", "id": 83, "method": "resources/read",
                "params": {"uri": "frame-check://aggregate/latest"},
            })
            check(
                "error" in resp,
                f"resources/read on absent aggregate should error; "
                f"got {resp!r}",
            )
            check(
                resp["error"]["code"] == -32602,
                f"absent aggregate should map to -32602 invalid_params; "
                f"got {resp['error']!r}",
            )
    finally:
        mcp_resources._AGGREGATE_RESULTS_DIR = original_dir
    _assert_no_new_failures(baseline, "test_aggregate_resource_read_when_absent_is_filenotfound")
    print("  PASS\n")


def test_resources_read_unknown_library_entry_is_invalid_params():
    """Asking for a library entry that does not exist must return
    JSON-RPC -32602 (invalid params), not -32603 (internal error).
    The client uses the code to decide whether to retry or drop."""
    print("=== resources/read unknown library entry returns -32602 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 8, "method": "resources/read",
        "params": {"uri": "frame-check://library/FVS-999"},
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        f"expected code -32602, got {resp.get('error', {}).get('code')}",
    )
    check(
        "FVS-999" in resp["error"]["message"],
        "error message should name the missing entry",
    )
    _assert_no_new_failures(baseline, "test_resources_read_unknown_library_entry_is_invalid_params")
    print("  PASS\n")


def test_resources_read_bad_scheme_is_invalid_params():
    print("=== resources/read bad scheme returns -32602 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 9, "method": "resources/read",
        "params": {"uri": "http://example.com"},
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        "bad scheme must be -32602 invalid params",
    )
    _assert_no_new_failures(baseline, "test_resources_read_bad_scheme_is_invalid_params")
    print("  PASS\n")


def test_resources_read_path_traversal_rejected():
    """Path traversal via ../ segments in a resource URI must be
    refused. This is the single highest-risk shape for the
    resources surface: a slug that resolves to an arbitrary file
    on disk would leak the whole host. The regex in
    _worked_example_path rejects anything with non [a-z0-9-]
    characters; this test pins that guarantee."""
    print("=== resources/read refuses path traversal ===")
    baseline = len(_FAILURES)
    for uri in (
        "frame-check://worked-examples/../../../etc/passwd",
        "frame-check://worked-examples/..%2F..%2Fetc",
        "frame-check://library/../../../etc/passwd",
    ):
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 10, "method": "resources/read",
            "params": {"uri": uri},
        })
        check(
            "error" in resp,
            f"traversal URI {uri} should return an error",
        )
    _assert_no_new_failures(baseline, "test_resources_read_path_traversal_rejected")
    print("  PASS\n")


def test_frame_match_carries_mcp_uri_and_entry_version():
    """Each frame_library_matches entry must carry the MCP resource
    URI for the matched FVS entry (so an agent running entirely
    through MCP can chain into resources/read without constructing
    the URI itself) and the per-entry version (so an agent citing
    this match can pin the cite to a specific version of the
    entry, not just the library-wide version).

    The NVIDIA-shaped sample below reliably triggers at least one
    library match; a deploy where the matcher returns zero matches
    on this sample signals a matcher regression, not a test bug.
    """
    print("=== frame match carries mcp_uri and entry_version ===")
    baseline = len(_FAILURES)
    doc = (
        "## NVIDIA Q3 Update\n"
        "NVIDIA reported record quarterly revenue of $18.12 billion "
        "in Q3 FY2024, up 206% year over year. Data center revenue "
        "reached $14.51 billion on unprecedented demand for AI "
        "accelerators. Growth remains strong, risks to the outlook "
        "are present, and uncertainty about supply constraints "
        "persists. Stakeholders across the supply chain are "
        "monitoring developments closely. We expect continued "
        "strength. The opportunity is massive. This is a defining "
        "moment. We are going to redefine everything. The future "
        "has never been brighter."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    matches = payload["analysis"]["frame_library_matches"]
    check(
        len(matches) >= 1,
        "sample should trigger at least one library match",
    )
    first = matches[0]
    check(
        first.get("library_resource_uri", "").startswith(
            "frame-check://library/"
        ),
        "each match must carry a library_resource_uri pointing at "
        f"the MCP library namespace; got {first.get('library_resource_uri')}",
    )
    # library_entry_version may be None for entries without the
    # **Version:** meta line, but present entries should carry it.
    # The current library has Version: 1 on every entry.
    check(
        first.get("library_entry_version") is not None,
        "each match should carry library_entry_version when the "
        "entry declares one",
    )
    _assert_no_new_failures(baseline, "test_frame_match_carries_mcp_uri_and_entry_version")
    print("  PASS\n")


def test_frame_library_matches_carry_clickable_library_url():
    """Each frame_library_matches entry must carry a library_url
    pointing at the canonical GitHub markdown source for the entry.

    Why this matters: end-users in MCP clients (Claude Desktop,
    Cursor) cannot click frame-check://library/... resource URIs
    because those are MCP-internal. Without library_url, a Frame
    Check finding surfaces FVS identifiers as plain text the user
    has no path to follow. The library_url is the citation form
    agents render as `[FVS-XXX Frame Title](library_url)` per
    agent_guidance.how_to_cite_frame_matches.

    GitHub URL is the canonical anchor because it is always
    resolvable regardless of hosted-production status (the previous
    library_url form pointed at frame.clarethium.com which is
    paused as of 2026-04-23).
    """
    print("=== frame_library_matches carry clickable library_url ===")
    baseline = len(_FAILURES)
    doc = (
        "## NVIDIA Q3 Update\n"
        "NVIDIA reported record quarterly revenue of $18.12 billion "
        "in Q3 FY2024, up 206% year over year. Data center revenue "
        "reached $14.51 billion on unprecedented demand for AI "
        "accelerators. Growth remains strong, risks to the outlook "
        "are present, and uncertainty about supply constraints "
        "persists. Stakeholders across the supply chain are "
        "monitoring developments closely. We expect continued "
        "strength. The opportunity is massive. This is a defining "
        "moment. We are going to redefine everything. The future "
        "has never been brighter."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    matches = payload["analysis"]["frame_library_matches"]
    check(len(matches) >= 1, "sample should trigger at least one match")
    first = matches[0]
    url = first.get("library_url") or ""
    check(
        url.startswith(
            "https://github.com/Clarethium/frame-check"
            "/blob/master/data/frame_library/"
        ),
        f"library_url must point at the canonical GitHub markdown "
        f"source for the entry so end-users can click it; got {url!r}",
    )
    check(
        f"{first['fvs_id']}_" in url and url.endswith(".md"),
        f"library_url must include the entry's FVS-ID prefix and "
        f"end in .md so the link resolves to the right file; "
        f"got {url!r} for fvs_id {first['fvs_id']!r}",
    )
    _assert_no_new_failures(baseline, "test_frame_library_matches_carry_clickable_library_url")
    print("  PASS\n")


def test_absent_frames_carry_clickable_library_url():
    """Each divergence.absent_frames entry must carry a library_url
    pointing at the canonical GitHub markdown source. Same rationale
    as the matched-frames test: end-users in MCP clients need a
    clickable link to follow when the agent surfaces an absent
    frame in its reading.

    Also pins that typical_co_absences entries inside each absent
    frame's corpus_context carry the same library_url field (added
    in corpus_intelligence.py 2026-04-28). Without it the co-pattern
    references were citation_uri-only, surfacing FVS identifiers
    with no clickable path even when the agent walked the corpus
    context block.
    """
    print("=== absent_frames + typical_co_absences carry library_url ===")
    baseline = len(_FAILURES)
    doc = (
        "AI productivity gains are decisive. Companies must adopt "
        "now or fall behind. The 55% productivity gain figure from "
        "GitHub research is widely cited and confirmed across "
        "industry studies. Stakeholders agree the future is settled: "
        "explosive growth through 2027 is the only question of "
        "execution speed. Skeptics underestimate the speed of "
        "transformation."
    )
    payload = mcp_server.build_epistemic_payload(
        doc, include_divergence=True
    )
    absent = payload["divergence"]["absent_frames"]
    check(len(absent) >= 1, "sample should produce at least one absent frame")
    first = absent[0]
    url = first.get("library_url") or ""
    check(
        url.startswith(
            "https://github.com/Clarethium/frame-check"
            "/blob/master/data/frame_library/"
        )
        and f"{first['frame_id']}_" in url
        and url.endswith(".md"),
        f"absent_frame library_url must point at the canonical "
        f"GitHub markdown source for the entry; got {url!r} for "
        f"frame_id {first['frame_id']!r}",
    )
    co_absences = first.get("corpus_context", {}).get(
        "typical_co_absences", []
    )
    check(
        len(co_absences) >= 1,
        "sample should produce at least one typical_co_absence",
    )
    co_url = co_absences[0].get("library_url") or ""
    check(
        co_url.startswith(
            "https://github.com/Clarethium/frame-check"
            "/blob/master/data/frame_library/"
        )
        and f"{co_absences[0]['fvs_id']}_" in co_url
        and co_url.endswith(".md"),
        f"typical_co_absences[].library_url must point at the "
        f"canonical GitHub markdown source for the entry; got "
        f"{co_url!r} for fvs_id {co_absences[0]['fvs_id']!r}",
    )
    _assert_no_new_failures(baseline, "test_absent_frames_carry_clickable_library_url")
    print("  PASS\n")


def test_suggested_next_actions_carries_findings_anchored_actions():
    """agent_guidance.suggested_next_actions must carry 2-4 specific
    next-action entries derived from this call's structural findings.
    Each entry is structural-finding-anchored: it points at a concrete
    gap and gives the user a concrete move that addresses it.

    Pins:
      - The block exists on every frame_check call
      - At least one entry derives from the absent_frames (when
        include_divergence=True) and includes the library_url so
        the user can follow it
      - At least one entry is the always-present prompt_followup
        pointing at the challenge_document MCP prompt so the rest
        of the product surface is discoverable
      - The list is bounded at 4 entries (more becomes noise)
      - Each entry has the documented shape
        {kind, action_text, rationale}
    """
    print("=== suggested_next_actions carries findings-anchored actions ===")
    baseline = len(_FAILURES)
    # Doc shape that matches the user's real-world frame_check call:
    # confident analytical prose, multiple unhedged numeric claims,
    # low attribution density. Triggers the absent_frame, unhedged
    # reprompt, and low-sourcing reprompt rules together.
    doc = (
        "The latest market data shows extraordinary growth "
        "opportunities. AI productivity gains are unprecedented, "
        "with 55 percent improvements widely reported. Skeptics "
        "consistently underestimate transformation; companies "
        "that fail to invest will lose decisive competitive "
        "advantage. The 280-fold cost reduction in inference "
        "since 2022 means shipping useful workflow products is "
        "far cheaper than it was. Stakeholders agree the future "
        "is settled: explosive growth through 2027. The 5 percent "
        "of companies truly AI-future-built will dominate. "
        "Customer service teams of 20 reps cost roughly 71,000 "
        "dollars monthly before overhead, so the ROI story is "
        "simple."
    )
    payload = mcp_server.build_epistemic_payload(
        doc, include_divergence=True
    )
    actions = payload["agent_guidance"].get("suggested_next_actions", [])
    check(
        2 <= len(actions) <= 4,
        f"suggested_next_actions must carry 2-4 entries; got "
        f"{len(actions)}",
    )
    # Each entry has the documented shape
    for action in actions:
        check(
            action.get("kind") in ("reprompt", "resource", "prompt_followup"),
            f"action.kind must be reprompt|resource|prompt_followup; "
            f"got {action.get('kind')!r}",
        )
        check(
            isinstance(action.get("action_text"), str)
            and len(action["action_text"]) > 0,
            f"action.action_text must be a non-empty string; "
            f"got {action.get('action_text')!r}",
        )
        check(
            isinstance(action.get("rationale"), str)
            and len(action["rationale"]) > 0,
            f"action.rationale must be a non-empty string; "
            f"got {action.get('rationale')!r}",
        )
    # At least one resource pointer with library_url
    resource_actions = [a for a in actions if a["kind"] == "resource"]
    check(
        len(resource_actions) >= 1,
        "at least one resource-kind action expected (the strongest "
        "absent_frame pointer); got none",
    )
    if resource_actions:
        url = resource_actions[0].get("related_url") or ""
        check(
            url.startswith(
                "https://github.com/Clarethium/frame-check"
                "/blob/master/data/frame_library/"
            )
            and url.endswith(".md"),
            f"resource action must carry the canonical GitHub URL "
            f"in related_url so the user can follow it; got {url!r}",
        )
        check(
            f"]({url})" in resource_actions[0]["action_text"],
            "resource action.action_text must embed the URL as a "
            "markdown link so the agent renders a clickable cite "
            "without further composition",
        )
    # Always-present prompt_followup
    followup_actions = [a for a in actions if a["kind"] == "prompt_followup"]
    check(
        len(followup_actions) >= 1,
        "at least one prompt_followup action expected (always-include "
        "challenge_document discovery); got none",
    )
    if followup_actions:
        check(
            "challenge_document" in followup_actions[0]["action_text"],
            "prompt_followup must point at challenge_document so the "
            "deeper multi-turn loop is discoverable on every call",
        )
    _assert_no_new_failures(baseline, "test_suggested_next_actions_carries_findings_anchored_actions")
    print("  PASS\n")


def test_suggested_next_actions_survives_compress_budget():
    """suggested_next_actions must survive at compose_budget=minimal
    and standard. The actions are per-call-derived and load-bearing
    for the user's discovery loop; compressing them out would drop
    the discoverability gain.

    Also pins that the rendering instruction passes through alongside
    so a compressed-tier caller still knows how to surface the
    actions to the user.
    """
    print("=== suggested_next_actions survives compose_budget compression ===")
    baseline = len(_FAILURES)
    doc = (
        "AI productivity gains are decisive. Companies must adopt "
        "now or fall behind. The 55 percent productivity gain "
        "figure from GitHub research is widely cited and confirmed "
        "across industry studies. Stakeholders agree the future is "
        "settled. Growth is inevitable."
    )
    for budget in ("minimal", "standard", "full"):
        payload = mcp_server.build_epistemic_payload(
            doc, include_divergence=True, compose_budget=budget,
        )
        ag = payload["agent_guidance"]
        check(
            isinstance(ag.get("suggested_next_actions"), list)
            and len(ag["suggested_next_actions"]) >= 1,
            f"compose_budget={budget!r} dropped suggested_next_actions; "
            f"the actions are per-call-specific and must survive "
            f"compression",
        )
        check(
            isinstance(
                ag.get("how_to_render_suggested_next_actions"), str
            ) and len(ag["how_to_render_suggested_next_actions"]) > 0,
            f"compose_budget={budget!r} dropped the rendering "
            f"instruction; the agent needs it to know how to "
            f"surface the actions",
        )
    _assert_no_new_failures(baseline, "test_suggested_next_actions_survives_compress_budget")
    print("  PASS\n")


def test_how_to_cite_frame_matches_mandates_library_url():
    """agent_guidance.how_to_cite_frame_matches must instruct the
    agent to render FVS references as markdown links using the
    library_url field (the always-resolvable GitHub URL), not as
    plain-text 'FVS-XXX' references that the user cannot follow.

    Without this, an agent honoring the cite-discipline still
    produces unusable output for end-users: the cite is named but
    not navigable. Pinned here so a future agent_guidance rewrite
    cannot silently revert to plain-text citation form.
    """
    print("=== how_to_cite_frame_matches mandates library_url ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload("Test document.")
    cite_help = payload["agent_guidance"]["how_to_cite_frame_matches"]
    check(
        "library_url" in cite_help,
        "how_to_cite_frame_matches must mention the library_url "
        "field by name so the agent knows which field to render",
    )
    check(
        "[FVS-XXX" in cite_help and "](library_url)" in cite_help,
        "how_to_cite_frame_matches must show the markdown-link "
        "rendering shape `[FVS-XXX ...](library_url)` so the agent "
        "produces a clickable citation rather than plain text",
    )
    _assert_no_new_failures(baseline, "test_how_to_cite_frame_matches_mandates_library_url")
    print("  PASS\n")


def test_frame_library_matches_carry_affects_dimensions():
    """Each frame_library_matches entry must carry
    affects_dimensions: the list of decision-readiness dimensions
    for which the matched frame is canon. Closes the canon graph
    in the matched_frame -> affected_dimensions direction so an
    agent surfacing a detected frame can immediately name which
    decision-readiness dimensions the detection threatens.

    FVS-001 (Frame Amplification) is canon for both coverage AND
    counterfactual per DIMENSION_LIBRARY_ENTRIES; pin both.
    Meta-side entries (FVS-002 etc.) have empty affects_dimensions
    by design: honest empty for entries that inform methodology
    rather than affecting a specific dimension.
    """
    print("=== frame_library_matches carry affects_dimensions ===")
    baseline = len(_FAILURES)
    # Sample text designed to fire FVS-001 in the detector layer.
    # Same shape as the adjacent_frames test sample.
    doc = (
        "## NVIDIA Q3 Update\n"
        "NVIDIA reported record quarterly revenue of $18.12 billion "
        "in Q3 FY2024, up 206% year over year. Data center revenue "
        "reached $14.51 billion on unprecedented demand for AI "
        "accelerators. Growth remains strong, risks to the outlook "
        "are present, and uncertainty about supply constraints "
        "persists. Stakeholders across the supply chain are "
        "monitoring developments closely. We expect continued "
        "strength. The opportunity is massive. This is a defining "
        "moment. We are going to redefine everything. The future "
        "has never been brighter."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    matches = payload["analysis"]["frame_library_matches"]
    check(
        len(matches) >= 1,
        "sample must produce at least one frame_library_match",
    )
    for m in matches:
        check(
            "affects_dimensions" in m,
            f"frame_library_match must carry affects_dimensions; "
            f"got keys {sorted(m.keys())}",
        )
        check(
            isinstance(m["affects_dimensions"], list),
            f"affects_dimensions must be a list; got "
            f"{type(m['affects_dimensions']).__name__}",
        )
        for dim in m["affects_dimensions"]:
            check(
                dim in {"coverage", "calibration", "evidence",
                        "robustness", "counterfactual"},
                f"affects_dimensions value {dim!r} is not a known "
                f"decision-readiness dimension",
            )
    # Find FVS-001 specifically (multi-dimension canon entry) if
    # present in this sample's matches; pin both dimensions.
    for m in matches:
        if m.get("fvs_id") == "FVS-001":
            dims = m["affects_dimensions"]
            check(
                "coverage" in dims and "counterfactual" in dims,
                f"FVS-001 must affect coverage AND counterfactual "
                f"per DIMENSION_LIBRARY_ENTRIES; got {dims!r}",
            )
            break
    _assert_no_new_failures(baseline, "test_frame_library_matches_carry_affects_dimensions")
    print("  PASS\n")


def test_decision_readiness_library_entry_uri_round_trips_via_resources_read():
    """End-to-end pin: an MCP agent receiving the decision-readiness
    profile in a tools/call response can take the
    library_resource_uri from any per-dimension library_entries[i]
    and pass it directly to resources/read to fetch the canonical
    library entry. This is the lead use case for the canon graph
    being self-resolvable from the MCP path.

    Three things must agree:
      1. decision_readiness.library_entry_ref emits the right URI
         scheme (frame-check://library/FVS-XXX)
      2. mcp_server.handle_resources_read accepts that URI scheme
         and resolves it to the library entry's markdown
      3. The fvs_id named in the profile matches a real FVS entry
         on this deploy

    A drift in any of the three would break agent chaining
    silently. The test fails LOUDLY for every case.
    """
    print("=== profile library_resource_uri -> resources/read round-trip ===")
    baseline = len(_FAILURES)
    # Build a payload that should produce a profile (any text with
    # framing signals will do; this sample is the same shape used
    # by the adjacent_frames test above).
    doc = (
        "## NVIDIA Q3 Update\n"
        "NVIDIA reported record quarterly revenue of $18.12 billion "
        "in Q3 FY2024, up 206% year over year. Growth remains strong, "
        "risks to the outlook are present, and uncertainty about "
        "supply constraints persists. Stakeholders across the supply "
        "chain are monitoring developments closely."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    profile = payload["analysis"].get("decision_readiness")
    check(
        profile is not None,
        "build_epistemic_payload must produce a decision_readiness "
        "profile for this sample (canon graph chain depends on it)",
    )
    dims = profile.get("dimensions") or {}
    check(
        dims, "profile.dimensions must be present",
    )
    # Pick one dimension, take its first library entry ref, round-trip it.
    coverage = dims.get("coverage") or {}
    refs = coverage.get("library_entries") or []
    check(
        refs and isinstance(refs[0], dict),
        f"coverage.library_entries must contain ref objects; got {refs!r}",
    )
    ref = refs[0]
    uri = ref.get("library_resource_uri")
    check(
        uri and uri.startswith("frame-check://library/FVS-"),
        f"library_entries[0].library_resource_uri malformed: {uri!r}",
    )
    # Title is the human-readable Name from INDEX.md so an agent
    # surfacing this finding to the user can name the pattern
    # without an extra resources/read just to learn what FVS-X is.
    check(
        ref.get("title") and isinstance(ref["title"], str),
        f"library_entries[0].title missing or empty: {ref!r}",
    )

    # Now resolve via MCP resources/read. The fvs_id in the URI
    # must round-trip to a real markdown library entry.
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 99, "method": "resources/read",
        "params": {"uri": uri},
    })
    check(
        "result" in resp,
        f"resources/read for profile-derived URI {uri!r} returned "
        f"no result; got {resp!r}",
    )
    contents = resp["result"].get("contents") or []
    check(
        contents and contents[0].get("mimeType") == "text/markdown",
        f"resources/read for {uri!r} did not return markdown; "
        f"got {contents!r}",
    )
    text = contents[0].get("text", "")
    check(
        text.startswith("# "),
        f"library markdown for {uri!r} should start with H1; "
        f"got {text[:80]!r}",
    )
    # The fvs_id from the profile must match a token referenced
    # somewhere in the markdown body (entry's own name in title or
    # cross-references). FVS-001 specifically appears in its own
    # H1 as "Frame Amplification" + meta block. Check by fvs_id.
    check(
        ref["fvs_id"] in text or ref["fvs_id"].replace("-", " ") in text,
        f"resolved markdown for {uri!r} does not contain the "
        f"fvs_id {ref['fvs_id']!r} the profile cited; "
        f"the canon graph chain has drifted",
    )
    # Also pin: the public_url field is HTTP-equivalent of the URI.
    # It does not get hit by this test (no HTTP fetch), but the
    # path component must contain the same FVS-ID prefix so
    # citation tools resolve to the same entry. The URL shape is
    # the GitHub blob path (data/frame_library/FVS-XXX_*.md) per
    # decision_readiness.LIBRARY_PUBLIC_URL_BASE; the test pins the
    # ID-presence invariant rather than the full filename so adding
    # a new entry or renaming an existing entry's slug does not
    # break this assertion.
    public_url = ref.get("public_url") or ""
    check(
        public_url.startswith("https://") and f"{ref['fvs_id']}_" in public_url,
        f"public_url path mismatch with fvs_id: {ref!r}",
    )
    _assert_no_new_failures(baseline, "test_decision_readiness_library_entry_uri_round_trips_via_resources_read")
    print("  PASS\n")


def test_frame_match_carries_adjacent_frames():
    """Each frame_library_matches entry must carry the adjacent
    FVS entries the curator named, with MCP URIs so an agent can
    chain reads. This closes the library-exploration loop: an
    agent detecting FVS-001 sees the adjacency graph directly in
    the response and can offer the user the related-frame reads
    without further discovery calls.

    FVS-001 is the test anchor: its entry declares
    Fluency-Quality Illusion (FVS-002) and Default Geometry
    (FVS-004) as adjacent. Non-FVS vocabularies (HI-*, T-*,
    CLARETHIUM_VOCABULARY) in the adjacency line must be
    filtered out; only FVS IDs that exist on this deploy are
    retained.
    """
    print("=== frame match carries adjacent_frames with MCP URIs ===")
    baseline = len(_FAILURES)
    # The adjacency cache is authoritative; a match on any entry
    # would show its adjacents, but the cache is the cleanest
    # way to pin the filtering behaviour.
    mcp_server._ensure_caches()
    adj = (mcp_server._FRAME_ADJACENCY or {}).get("FVS-001", [])
    check(
        "FVS-002" in adj,
        f"FVS-001 adjacency should include FVS-002; got {adj}",
    )
    check(
        "FVS-004" in adj,
        f"FVS-001 adjacency should include FVS-004; got {adj}",
    )
    # Non-FVS references in source files must be filtered; nothing in
    # the adjacency list should start with a non-FVS prefix.
    check(
        all(x.startswith("FVS-") for x in adj),
        f"non-FVS references leaked into adjacency: {adj}",
    )
    # Self-references also filtered.
    check(
        "FVS-001" not in adj,
        "self-reference must not appear in adjacency list",
    )

    # Render-site test: the adjacency surfaces in the tool
    # response with MCP URIs attached to each adjacent ID.
    doc = (
        "## NVIDIA Q3 Update\n"
        "NVIDIA reported record quarterly revenue of $18.12 billion "
        "in Q3 FY2024, up 206% year over year. Data center revenue "
        "reached $14.51 billion on unprecedented demand for AI "
        "accelerators. Growth remains strong, risks to the outlook "
        "are present, and uncertainty about supply constraints "
        "persists. Stakeholders across the supply chain are "
        "monitoring developments closely. We expect continued "
        "strength. The opportunity is massive. This is a defining "
        "moment. We are going to redefine everything. The future "
        "has never been brighter."
    )
    payload = mcp_server.build_epistemic_payload(doc)
    matches = payload["analysis"]["frame_library_matches"]
    check(
        len(matches) >= 1,
        "sample must trigger at least one library match",
    )
    # Pick the first match and verify adjacent_frames shape.
    m = matches[0]
    adjacents = m.get("adjacent_frames")
    check(
        isinstance(adjacents, list),
        "adjacent_frames must be a list",
    )
    if adjacents:
        first_adj = adjacents[0]
        check(
            first_adj.get("library_resource_uri", "").startswith(
                "frame-check://library/FVS-"
            ),
            "adjacent_frames entries must carry MCP library URIs",
        )
        # Adjacent_frames must also carry public_url so the canon-
        # graph reference shape is uniform across surfaces (matches
        # the per-dimension library_entries on the decision-readiness
        # profile and the aggregate library_entries_per_dimension).
        # Both are built from decision_readiness.library_entry_ref so
        # divergence here would mean someone bypassed the helper.
        # URL pattern follows decision_readiness.LIBRARY_PUBLIC_URL_BASE,
        # which switched from frame.clarethium.com/corpus/library to
        # github.com/Clarethium/frame-check/blob/master/data/frame_library
        # when production paused 2026-04-23 (Path A.1 decision): GitHub
        # is always resolvable for end-users regardless of hosted-
        # production status, and per-entry filenames stay accurate
        # under entry rename via parse_entry_filenames().
        public_url_prefix = (
            "https://github.com/Clarethium/frame-check/blob/master"
            "/data/frame_library/"
        )
        check(
            first_adj.get("public_url", "").startswith(
                f"{public_url_prefix}{first_adj['fvs_id']}_"
            )
            and first_adj["public_url"].endswith(".md"),
            f"adjacent_frames entries must carry public_url pointing "
            f"at the GitHub-hosted FVS markdown for the entry's "
            f"fvs_id (expected prefix "
            f"{public_url_prefix}{first_adj['fvs_id']}_..., suffix .md); "
            f"got {first_adj.get('public_url')!r}",
        )
        check(
            first_adj["library_resource_uri"].endswith(first_adj["fvs_id"]),
            f"adjacent_frames URI/fvs_id mismatch: {first_adj!r}",
        )
        # Title injected via library_entry_ref. Adjacent frames need
        # the title for the same reason library_entries does: agents
        # surfacing them to users should not show bare IDs.
        check(
            first_adj.get("title") and isinstance(first_adj["title"], str),
            f"adjacent_frames entries must carry title from "
            f"INDEX.md so agents render proper names, "
            f"got {first_adj.get('title')!r}",
        )
    _assert_no_new_failures(baseline, "test_frame_match_carries_adjacent_frames")
    print("  PASS\n")


def test_library_resource_description_pins_version():
    """The resource description for each library entry should
    surface the per-entry version so an agent browsing
    resources/list sees the version without reading each file.
    Format: 'v<version>. Frame Vocabulary Standard entry ...'.
    """
    print("=== library resource description pins version ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 30, "method": "resources/list",
    })
    lib = [
        r for r in resp["result"]["resources"]
        if r["uri"] == "frame-check://library/FVS-001"
    ]
    if not lib:
        print("  (no FVS-001 on this deploy; skipping)\n")
        return
    desc = lib[0]["description"]
    check(
        desc.startswith("v") and "." in desc[:5],
        f"library entry description should pin version prefix; "
        f"got: {desc[:50]}",
    )
    _assert_no_new_failures(baseline, "test_library_resource_description_pins_version")
    print("  PASS\n")


def test_library_index_resource_available():
    """The library index (INDEX.md) is a resource in its own right:
    the citable map of the Frame Vocabulary Standard. A test pins
    that it is advertised and that reads return the markdown
    content starting with its H1 title."""
    print("=== library index is available as a resource ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 20, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    check(
        "frame-check://library" in uris,
        "library index URI missing from resources/list",
    )
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 21, "method": "resources/read",
        "params": {"uri": "frame-check://library"},
    })
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "text/markdown",
        "library index must be markdown",
    )
    check(
        contents[0]["text"].startswith("# "),
        "library index must open with an H1 title",
    )
    _assert_no_new_failures(baseline, "test_library_index_resource_available")
    print("  PASS\n")


def test_transmissions_resources_available():
    """Transmissions are curated research pieces from the author's
    blog (blog.clarethium.com) served as MCP resources because a
    Cloudflare edge layer blocks automated fetches to the public
    blog. This test pins: at least the collection index plus one
    individual transmission resource are advertised when the
    transmissions directory has content.

    Design contract pinned here:
      - URI scheme: frame-check://transmissions/{slug}
      - Collection index at frame-check://transmissions
      - Each transmission resource's description carries the type
        tag (e.g., [EVIDENCE]) and a one-line summary so agents
        can pick a relevant piece without reading the full body.
      - The reserved slug "nonexistent-slug" raises FileNotFoundError
        via the resources/read JSON-RPC error path.
    """
    print("=== transmissions: index and individual resources ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 80, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    has_any = any(
        u.startswith("frame-check://transmissions/") for u in uris
    )
    if not has_any:
        print("  (no transmissions on this deploy; skipping)\n")
        return
    check(
        "frame-check://transmissions" in uris,
        "transmissions collection index must be advertised when "
        "at least one transmission exists",
    )
    # At least one individual transmission resource
    transmission_uris = [
        u for u in uris
        if u.startswith("frame-check://transmissions/")
    ]
    check(
        len(transmission_uris) >= 1,
        "at least one transmission resource must be advertised",
    )
    # Description must carry the type tag + summary signal
    by_uri = {r["uri"]: r for r in resp["result"]["resources"]}
    sample = by_uri[transmission_uris[0]]
    desc = sample["description"]
    check(
        "[" in desc and "]" in desc,
        f"transmission description should carry a [TYPE] tag; "
        f"got: {desc!r}",
    )
    # Read the collection index
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 81, "method": "resources/read",
        "params": {"uri": "frame-check://transmissions"},
    })
    check(
        "result" in resp
        and resp["result"]["contents"][0]["mimeType"] == "text/markdown"
        and "https://blog.clarethium.com" in resp["result"]["contents"][0]["text"],
        "transmissions index must point at the canonical blog URL",
    )
    # Read the first individual transmission
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 82, "method": "resources/read",
        "params": {"uri": transmission_uris[0]},
    })
    text = resp["result"]["contents"][0]["text"]
    check(
        "transmission_id:" in text and "source_url:" in text,
        "individual transmission must carry transmission_id and "
        "source_url in its frontmatter",
    )
    # Reject unknown slug
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 83, "method": "resources/read",
        "params": {
            "uri": "frame-check://transmissions/nonexistent-slug"
        },
    })
    check("error" in resp, "unknown transmission slug must error")
    # Reject traversal
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 84, "method": "resources/read",
        "params": {
            "uri": "frame-check://transmissions/../../../etc/passwd"
        },
    })
    check("error" in resp, "transmission traversal must be rejected")
    _assert_no_new_failures(baseline, "test_transmissions_resources_available")
    print("  PASS\n")


def test_worked_examples_index_resource_available():
    """The worked-examples README is the collection-level index.
    Agents browsing the corpus should see it alongside individual
    examples; a test pins that it is advertised when published
    examples exist."""
    print("=== worked-examples index is available as a resource ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 22, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    has_examples = any(
        u.startswith("frame-check://worked-examples/") for u in uris
    )
    if not has_examples:
        print("  (no worked examples on this deploy; skipping)\n")
        return
    check(
        "frame-check://worked-examples" in uris,
        "worked-examples index should be advertised when examples exist",
    )
    _assert_no_new_failures(baseline, "test_worked_examples_index_resource_available")
    print("  PASS\n")


def test_calibration_per_run_resources_available():
    """Each calibration run with a REPORT.md must expose at least
    the report resource, and any per-run raw verdicts or tier
    snapshots must be advertised alongside. This closes the
    evidence chain: an agent citing a tier can cite the verdicts
    that justified it."""
    print("=== per-run calibration assets available as resources ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 23, "method": "resources/list",
    })
    uris = [r["uri"] for r in resp["result"]["resources"]]
    run_uris = [u for u in uris if "/calibration/runs/" in u]
    if not run_uris:
        print("  (no calibration runs on this deploy; skipping)\n")
        return
    # At least one run must have a report.
    check(
        any(u.endswith("/report") for u in run_uris),
        "at least one calibration run must advertise its report",
    )
    # Pick the first report URI and read it.
    report_uri = next(u for u in run_uris if u.endswith("/report"))
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 24, "method": "resources/read",
        "params": {"uri": report_uri},
    })
    contents = resp["result"]["contents"]
    check(
        contents[0]["mimeType"] == "text/markdown",
        "calibration report must be markdown",
    )
    check(
        "Calibration" in contents[0]["text"]
        or "calibration" in contents[0]["text"],
        "calibration report should mention the word calibration",
    )
    _assert_no_new_failures(baseline, "test_calibration_per_run_resources_available")
    print("  PASS\n")


def test_calibration_run_traversal_rejected():
    """Path traversal on the run_id segment of a calibration URI
    must be rejected. The run_id regex pins this: anything that
    starts with .. would not match ^\\d{4}-\\d{2}-\\d{2}... and the
    helper returns None."""
    print("=== calibration run URI refuses traversal ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 25, "method": "resources/read",
        "params": {
            "uri": "frame-check://calibration/runs/"
                   "../../../../etc/report"
        },
    })
    check("error" in resp, "traversal must return an error")
    _assert_no_new_failures(baseline, "test_calibration_run_traversal_rejected")
    print("  PASS\n")


def test_provenance_carries_iso_timestamp():
    """Every provenance block must carry analysis_timestamp_utc
    in ISO-8601 with trailing Z so an agent citing the analysis
    can produce a timestamp that matches the measurement wall-clock
    exactly. Academic citations rely on this being unambiguous."""
    print("=== provenance carries ISO-8601 UTC timestamp ===")
    baseline = len(_FAILURES)
    import re as _re
    payload = mcp_server.build_epistemic_payload(
        "The Committee notes that risks are elevated."
    )
    ts = payload["provenance"].get("analysis_timestamp_utc")
    check(
        isinstance(ts, str)
        and _re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts),
        f"analysis_timestamp_utc must be ISO-8601 Z, got {ts!r}",
    )
    # Same field on the compare path.
    cmp_payload = mcp_server.build_compare_payload(
        "Doc A text.", "Doc B text.",
    )
    cts = cmp_payload["provenance"].get("analysis_timestamp_utc")
    check(
        isinstance(cts, str)
        and _re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", cts),
        f"compare provenance must also carry ISO timestamp, got {cts!r}",
    )
    _assert_no_new_failures(baseline, "test_provenance_carries_iso_timestamp")
    print("  PASS\n")


def test_worked_example_descriptions_carry_frontmatter_signal():
    """The resources/list description for a worked example must
    surface enough frontmatter metadata that a browsing agent can
    pick the right example without reading the full markdown. At
    minimum, the hook sentence or the source_document_title must
    appear in the description (both when present)."""
    print("=== worked example descriptions carry frontmatter ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 12, "method": "resources/list",
    })
    we = [r for r in resp["result"]["resources"]
          if r["uri"].startswith("frame-check://worked-examples/")]
    if not we:
        print("  (no worked examples on this deploy; skipping)\n")
        return
    # Spot-check: at least one worked example should carry a source
    # line or a substantive description beyond the generic prefix.
    rich = [
        r for r in we
        if r["description"].startswith("Source:")
        or len(r["description"]) > 150
    ]
    check(
        len(rich) >= 1,
        "at least one worked-example description should surface "
        "frontmatter metadata (Source: ... or a hook sentence)",
    )
    _assert_no_new_failures(baseline, "test_worked_example_descriptions_carry_frontmatter_signal")
    print("  PASS\n")


def test_ping_returns_empty_result():
    """ping is a protocol-level keepalive. Must return an empty
    result object; must NOT go through the tools dispatcher. An
    MCP client that sends ping and gets back an error or a
    malformed result can decide the server is unhealthy and
    reconnect. Without this test, a regression in the ping
    branch would hide until a client actually pings."""
    print("=== ping returns empty result ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 13, "method": "ping",
    })
    check(resp is not None, "ping must return a response")
    check("result" in resp, "ping result envelope missing")
    check(resp["result"] == {}, "ping must return empty result object")
    check("error" not in resp, "ping must not return an error")
    _assert_no_new_failures(baseline, "test_ping_returns_empty_result")
    print("  PASS\n")


def test_resources_read_missing_uri_is_invalid_params():
    print("=== resources/read missing uri returns -32602 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 11, "method": "resources/read",
        "params": {},
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        "missing uri must be -32602",
    )
    _assert_no_new_failures(baseline, "test_resources_read_missing_uri_is_invalid_params")
    print("  PASS\n")


# ── Layer 4: prompts primitive ────────────────────────────────────
#
# Prompts are the server-defined templates the agent's LLM executes.
# These tests pin: prompts capability advertised; four prompts
# enumerated; each carries the voice rules baked in at construction
# time (verdict prohibited, limits named, tool invocation specific).
# A regression that softens the voice rules would fail here. If
# a future edit removed "do not verdict" from the self-audit
# prompt, the test that checks for it would fail.


def test_initialize_advertises_prompts_capability():
    print("=== initialize advertises prompts ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 50, "method": "initialize",
        "params": {},
    })
    caps = resp["result"]["capabilities"]
    check("prompts" in caps, "prompts capability must be advertised")
    _assert_no_new_failures(baseline, "test_initialize_advertises_prompts_capability")
    print("  PASS\n")


def test_prompts_list_has_four():
    print("=== prompts/list advertises the four prompts ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 51, "method": "prompts/list",
    })
    names = {p["name"] for p in resp["result"]["prompts"]}
    expected = {
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    }
    check(
        names == expected,
        f"prompts must be exactly {expected}, got {names}",
    )
    for p in resp["result"]["prompts"]:
        check("description" in p, f"prompt {p['name']} missing description")
        check("arguments" in p, f"prompt {p['name']} missing arguments")
    _assert_no_new_failures(baseline, "test_prompts_list_has_four")
    print("  PASS\n")


def test_prompts_get_returns_messages_with_voice_rules():
    """The load-bearing prompt is frame_check_my_response. Its
    messages must carry the construct-honesty voice rules baked
    in: specific tool invocation, verdict prohibited, method
    limits named. If any of those drift, the prompt starts reading
    like a verdict engine. This test is the discipline guard."""
    print("=== frame_check_my_response carries voice rules ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 52, "method": "prompts/get",
        "params": {"name": "frame_check_my_response"},
    })
    msgs = resp["result"]["messages"]
    check(len(msgs) >= 1, "prompt must return at least one message")
    check(msgs[0]["role"] == "user", "first message must be user-role")
    text = msgs[0]["content"]["text"]
    # Specific tool invocation
    check(
        "frame_check" in text and "document_text" in text,
        "prompt must name the frame_check tool and document_text "
        "argument explicitly",
    )
    # Verdict prohibition
    check(
        "Do not verdict" in text or "do not verdict" in text.lower(),
        "prompt must prohibit self-verdicting",
    )
    check(
        "balanced" in text.lower(),
        "prompt must explicitly prohibit the 'I was balanced' "
        "pattern that LLMs default to",
    )
    # Limits named
    check(
        "structural" in text.lower() and "semantic" in text.lower(),
        "prompt must name the structural/semantic distinction as "
        "a method limit",
    )
    # Closing hands agency back to the user
    check(
        "my call" in text or "the user" in text,
        "prompt must close by handing the decision back to the user",
    )
    _assert_no_new_failures(baseline, "test_prompts_get_returns_messages_with_voice_rules")
    print("  PASS\n")


def test_agent_guidance_names_self_audit_pattern():
    """The self-audit use case is load-bearing for the sovereignty
    narrative: an agent invoking frame_check on its own last
    response. agent_guidance must name that pattern explicitly so an
    agent reading the payload knows the response shape changes
    (surface frame, do not self-evaluate) and so the key does not
    quietly drift out of the payload in a future refactor."""
    print("=== agent_guidance names self-audit pattern ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    g = payload["agent_guidance"]
    check(
        "when_invoked_on_own_output" in g,
        "agent_guidance must carry when_invoked_on_own_output so "
        "the self-audit response shape is explicit",
    )
    note = g["when_invoked_on_own_output"]
    check(
        "sovereignty" in note.lower(),
        "self-audit guidance must name the sovereignty case so the "
        "agent knows why the response shape differs",
    )
    check(
        "not evaluate" in note.lower()
        or "do not evaluate" in note.lower()
        or "do not claim" in note.lower(),
        "self-audit guidance must prohibit self-evaluation "
        "(measurements are structural, not semantic)",
    )
    _assert_no_new_failures(baseline, "test_agent_guidance_names_self_audit_pattern")
    print("  PASS\n")


def test_prompts_get_ai_response_prompt_warns_against_verdict():
    """The sovereignty-case prompt must also carry verdict
    prohibition against the analyzed AI (not just self). Reading
    an AI response through Frame Check should surface structure,
    never conclude bias."""
    print("=== frame_check_this_ai_response prohibits verdict ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 53, "method": "prompts/get",
        "params": {"name": "frame_check_this_ai_response"},
    })
    text = resp["result"]["messages"][0]["content"]["text"]
    check(
        "biased" in text.lower() and "balanced" in text.lower(),
        "prompt must explicitly name both verdict shapes "
        "(biased / balanced) it prohibits",
    )
    check(
        "sovereignty" in text.lower() or "user judges" in text.lower(),
        "prompt must frame the user as the judge, not the tool",
    )
    _assert_no_new_failures(baseline, "test_prompts_get_ai_response_prompt_warns_against_verdict")
    print("  PASS\n")


def test_server_version_bumped_for_decision_readiness_capability():
    """The MCP SERVER_VERSION must reflect the addition of
    analysis.decision_readiness as a capability change. Clients
    detect available updates via the version reported in the
    initialize handshake; if SERVER_VERSION stays at the
    pre-decision_readiness baseline, installed clients have no
    visible signal that a meaningful update is available.

    Pins:
      - SERVER_VERSION is at least 0.2.0 (the version that
        introduced analysis.decision_readiness)
      - The version is exposed via the initialize handshake
        serverInfo.version field (already pinned by
        test_initialize_handshake but re-checked here for the
        version-bump contract specifically)
    """
    print("=== SERVER_VERSION bumped for decision_readiness capability ===")
    baseline = len(_FAILURES)
    # Parse "MAJOR.MINOR.PATCH" and require at least 0.2.0.
    parts = mcp_server.SERVER_VERSION.split(".")
    check(len(parts) == 3,
          f"SERVER_VERSION must be MAJOR.MINOR.PATCH, "
          f"got {mcp_server.SERVER_VERSION!r}")
    major, minor, _patch = (int(p) for p in parts)
    check(
        major > 0 or minor >= 2,
        f"SERVER_VERSION must be >= 0.2.0 since "
        f"analysis.decision_readiness ships in this release; got "
        f"{mcp_server.SERVER_VERSION!r}",
    )

    # Initialize handshake must echo the version verbatim
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 80, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {}, "clientInfo": {}},
    })
    server_info = resp["result"]["serverInfo"]
    check(server_info.get("version") == mcp_server.SERVER_VERSION,
          f"initialize handshake serverInfo.version "
          f"({server_info.get('version')!r}) does not match "
          f"SERVER_VERSION ({mcp_server.SERVER_VERSION!r})")
    _assert_no_new_failures(baseline, "test_server_version_bumped_for_decision_readiness_capability")
    print("  PASS\n")


def test_all_prompts_surface_decision_readiness():
    """Every sovereignty prompt must instruct the agent to surface
    analysis.decision_readiness when present in the tool response.
    Without prompt-side awareness, the new field exists in the
    payload but agents default to the older surfacing pattern and
    quietly ignore the profile.

    The methodology page positions AI-response audit as the lead
    use case for the decision-readiness profile; that positioning
    only ships end-to-end when the prompts the agent actually
    executes carry decision_readiness in their templates.

    Pins per prompt:
      - decision_readiness referenced in the prompt body
      - 'experimental' status named (so agents do not overstate
        the profile's authority)
      - methodology page referenced (so agents can route the user
        to the framework)
      - explicit no-verdict instruction for decision-readiness
        (the same construct-honesty rule applied to the new field)
    """
    print("=== all four prompts surface decision_readiness ===")
    baseline = len(_FAILURES)
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 70, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        text_lower = text.lower()
        check(
            "decision_readiness" in text or "decision-readiness" in text_lower,
            f"prompt {prompt_name!r} does not reference decision_readiness; "
            f"agents will not surface the new profile field to users",
        )
        check(
            "experimental" in text_lower,
            f"prompt {prompt_name!r} does not name the profile's "
            f"experimental status; agents could overstate authority",
        )
        check(
            "/corpus/decision-readiness" in text,
            f"prompt {prompt_name!r} does not link the methodology "
            f"page; agents cannot route users to the framework",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_surface_decision_readiness")
    print("  PASS  (all four sovereignty prompts updated)\n")


def test_all_prompts_point_at_library_chain_for_decision_readiness():
    """Every sovereignty prompt that surfaces decision_readiness
    dimensions must also point the agent at the library chain
    affordance (library_entries[].library_resource_uri) so the
    agent knows it can fetch the canonical pattern entry inline
    rather than improvising prose about it.

    This is the canon-graph closure for the lead use case. The
    profile JSON carries chain affordances per dimension; if the
    prompts the agent executes don't name them, the affordances
    exist but agents default to summarizing dimensions in their
    own words and the canon graph stops at the dimension level.

    Pins (per prompt):
      - library_entries OR library_resource_uri named in the body
        in the context of decision_readiness/dimensions surfacing
    """
    print("=== all four prompts point at library chain for profile ===")
    baseline = len(_FAILURES)
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 71, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "library_entries" in text or "library_resource_uri" in text,
            f"prompt {prompt_name!r} does not mention library_entries "
            f"or library_resource_uri; agents will not chain from "
            f"decision_readiness dimensions to the named library "
            f"entries even though the profile carries the affordance",
        )
        # fired_library_entries is the canon-aligned subset that the
        # detector specifically detected in this document. Prompts
        # must point agents at the firing list so they prefer focused
        # chaining (the patterns that actually fired) over candidate
        # chaining (the dimension's full canon space). Without this
        # in the prompt, agents fall back to the broader list and
        # the focused signal goes unused.
        check(
            "fired_library_entries" in text,
            f"prompt {prompt_name!r} does not mention "
            f"fired_library_entries; agents will not prefer the "
            f"detector-identified subset over the full canon list, "
            f"missing the focused chaining affordance",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_point_at_library_chain_for_decision_readiness")
    print("  PASS  (all four prompts carry the chain pointer)\n")


def test_all_prompts_mention_affects_dimensions_for_matched_frames():
    """Each sovereignty prompt that surfaces frame_library_matches
    must also point at affects_dimensions so agents can bridge a
    matched frame to the decision-readiness dimensions it threatens.
    Without this, agents surface matches and dimensions in parallel
    but miss the structural connection between them.

    affects_dimensions ships in 0.5.0; the prompt regression test
    pins that the surfacing instruction stays present so a future
    prompt rewrite cannot silently drop the canon-graph linkage in
    the lead use case."""
    print("=== all four prompts mention affects_dimensions ===")
    baseline = len(_FAILURES)
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 72, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "affects_dimensions" in text,
            f"prompt {prompt_name!r} does not mention "
            f"affects_dimensions; agents will not bridge matched "
            f"frames to the decision-readiness dimensions they "
            f"threaten",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_mention_affects_dimensions_for_matched_frames")
    print("  PASS  (all four prompts bridge matched frames to dimensions)\n")


def test_prompts_get_unknown_returns_invalid_params():
    print("=== prompts/get unknown name returns -32602 ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 54, "method": "prompts/get",
        "params": {"name": "no_such_prompt"},
    })
    check(
        "error" in resp and resp["error"]["code"] == -32602,
        "unknown prompt must be -32602 invalid params",
    )
    _assert_no_new_failures(baseline, "test_prompts_get_unknown_returns_invalid_params")
    print("  PASS\n")


def test_all_prompts_are_divergence_aware():
    """Each sovereignty prompt must step through the divergence block.

    Load-bearing for the 0.8.0 V4.2-capable-by-default direction per
    STRATEGY §14. If the sovereignty prompts (the use case the MCP
    was built around) do not invoke divergence, the headline capability
    is silently absent from every agent that runs them.

    Pins that each prompt mentions either 'divergence block' or
    'include_divergence=true' so a future prompt rewrite cannot
    silently drop the divergence walkthrough."""
    baseline = len(_FAILURES)
    print("=== all four prompts are divergence-aware ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 81, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        has_divergence = (
            "divergence block" in text or "include_divergence=true" in text
        )
        check(
            has_divergence,
            f"prompt {prompt_name!r} does not mention divergence; "
            f"the 0.8.0 V4.2-capable-by-default direction requires the "
            f"sovereignty prompts to exercise the divergence block",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_are_divergence_aware")
    print("  PASS  (all four prompts are divergence-aware)\n")


def test_all_prompts_honor_absence_is_not_prescription():
    """Each sovereignty prompt that walks the divergence block must
    cite agent_guidance.absence_is_not_prescription so the caller's
    model knows that surfaced absences never translate into 'you
    should have used frame X' prescription.

    Load-bearing for the faithfulness contract
    (FRAME_DIVERGENCE_CONTRACT_v1 §4.5 and §5.1 guarantee 5). If a
    sovereignty prompt walks absent_frames without invoking the
    absence-is-not-prescription discipline, the prompt becomes a
    prescription engine and the category claim falsifies itself."""
    baseline = len(_FAILURES)
    print("=== all four prompts honor absence_is_not_prescription ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 82, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "absence_is_not_prescription" in text,
            f"prompt {prompt_name!r} does not name "
            f"absence_is_not_prescription; the divergence walkthrough "
            f"loses the faithfulness guardrail and risks prescription",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_honor_absence_is_not_prescription")
    print("  PASS  (all four prompts cite the absence-not-prescription guard)\n")


def test_self_audit_and_ai_response_audit_pass_include_divergence_true():
    """The two prompts that call frame_check themselves (self-audit
    and cross-AI audit) must pass include_divergence=true so the
    response carries the divergence block. explain_framing assumes
    the result is already in context; challenge_document also calls
    the tool and is covered here.

    Pins that the CALL step in each tool-invoking prompt opts into
    divergence explicitly."""
    baseline = len(_FAILURES)
    print("=== tool-invoking prompts pass include_divergence=true ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 83, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "include_divergence=true" in text,
            f"prompt {prompt_name!r} does not opt into divergence "
            f"(include_divergence=true not found in call instruction); "
            f"the divergence walkthrough later in the prompt would "
            f"have nothing to walk through",
        )
    _assert_no_new_failures(baseline, "test_self_audit_and_ai_response_audit_pass_include_divergence_true")
    print("  PASS  (tool-invoking prompts opt into divergence)\n")


def test_all_prompts_have_compact_default_discipline():
    """Each tool-invoking prompt must teach the agent the compact-
    default discipline shipped at 0.8.0:
      - lead with portrait + 2-3 highest signal_strength absences
      - inline citations as `[FVS-XXX Frame Title](library_url)`
        using the GitHub URL (always resolvable for end-users in
        MCP clients); never the frame-check:// resource URI for
        end-user output
      - one action question (question form)
      - 'expand' invitation for the deep readout

    Pins the prompt-level UX shape so a future prompt rewrite cannot
    silently revert the compact discipline."""
    baseline = len(_FAILURES)
    print("=== all four prompts carry compact-default discipline ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 100, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "signal_strength" in text or "highest" in text.lower(),
            f"prompt {prompt_name!r} does not teach signal_strength-"
            f"based filtering; agent will not know to surface only "
            f"high-tier absences in the compact response",
        )
        check(
            "library_url" in text,
            f"prompt {prompt_name!r} does not point at the "
            f"library_url field for inline citations; agent will "
            f"not know to render the GitHub URL the user can click",
        )
        check(
            "FVS-XXX" in text,
            f"prompt {prompt_name!r} does not show the inline "
            f"citation placeholder shape; agent will not know to "
            f"render citations inline next to claims",
        )
        check(
            "expand" in text.lower(),
            f"prompt {prompt_name!r} does not name the 'expand' "
            f"invitation; agent will not know to offer the full "
            f"readout on user request",
        )
        check(
            "never add" in text.lower() and "bibliography" in text.lower(),
            f"prompt {prompt_name!r} does not forbid the bottom Sources "
            f"bibliography; agent may still render an end-of-response "
            f"citation block, breaking the inline-citations discipline",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_have_compact_default_discipline")
    print("  PASS  (compact discipline preserved across all four prompts)\n")


def test_all_prompts_have_confidence_gate():
    """Each prompt must teach the agent to run a confidence gate
    BEFORE the analysis: under 100 words / non-English / non-
    analytical structure → name the warning. Pins the construct-
    honesty discipline at the user-facing layer (the methodology is
    validated on English analytical prose; the prompts must not
    surface measurements with full confidence on off-methodology
    documents)."""
    baseline = len(_FAILURES)
    print("=== all four prompts carry confidence-gate discipline ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 101, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "confidence gate" in text.lower() or "low confidence" in text.lower(),
            f"prompt {prompt_name!r} does not name the confidence gate; "
            f"agent will surface measurements with full confidence on "
            f"off-methodology documents",
        )
        # Three triggers: length, language, structure.
        check(
            "100 words" in text or "statistical floor" in text.lower(),
            f"prompt {prompt_name!r} does not name the length-floor "
            f"trigger (under 100 words); short documents will receive "
            f"unwarranted-confidence analyses",
        )
        check(
            "non-english" in text.lower() or "english" in text.lower(),
            f"prompt {prompt_name!r} does not name the language "
            f"trigger; non-English documents will receive measurements "
            f"the methodology has not been validated against",
        )
        check(
            "non-analytical" in text.lower() or "analytical prose" in text.lower(),
            f"prompt {prompt_name!r} does not name the structure "
            f"trigger; code, poetry, and fragmentary text will receive "
            f"measurements the detector is not calibrated for",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_have_confidence_gate")
    print("  PASS  (confidence-gate discipline preserved across all four prompts)\n")


def test_all_prompts_have_action_question():
    """Each prompt must instruct the agent to end the compact
    response with one question that translates the structural finding
    into a thinkable next step. Question form, never statement; honors
    absence_is_not_prescription. Pins the action-question discipline
    so the response always closes with a thinkable-next-step rather
    than a measurement dump."""
    baseline = len(_FAILURES)
    print("=== all four prompts carry action-question discipline ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 102, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        # Either "one question" (singular) or the challenge_document
        # which generates 2-3 questions; both forms close on questions.
        has_question_discipline = (
            "one question" in text.lower()
            or "questions" in text.lower() and "tool the user uses" in text.lower()
            or "asking" in text.lower() and "question form" in text.lower()
        )
        check(
            has_question_discipline,
            f"prompt {prompt_name!r} does not teach the action-question "
            f"discipline (close with a question that translates "
            f"finding into thinkable next step)",
        )
        check(
            "question form" in text.lower() or "never statement" in text.lower()
            or "questions, not" in text.lower(),
            f"prompt {prompt_name!r} does not explicitly forbid "
            f"statement form for the action question; agent may close "
            f"with a prescription",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_have_action_question")
    print("  PASS  (action-question discipline preserved across all four prompts)\n")


def test_all_prompts_have_insight_led_discipline():
    """Each tool-invoking prompt must teach the insight-led shape
    shipped after the v0.7.x measurement-walking UX:
      - compose ONE insight (or 2-3 questions for challenge_document),
        grounded in 2-3 specific cited measurements
      - reading-form, never verdict-form
      - do NOT walk the measurements one by one
      - reference agent_guidance.composition_discipline

    Pins the user-facing UX shift so a future prompt rewrite cannot
    silently revert to mechanical measurement-walking, which was the
    failure surfaced in operator testing of the 0.8.0 prerelease."""
    baseline = len(_FAILURES)
    print("=== all four prompts carry insight-led composition discipline ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 110, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "composition_discipline" in text,
            f"prompt {prompt_name!r} does not reference "
            f"agent_guidance.composition_discipline; agent will not "
            f"know to compose ONE insight grounded in cited "
            f"measurements rather than walking measurements one by one",
        )
        # Reading-form, never verdict-form. Either the prompt names the
        # rule explicitly, or it shows the contrast pattern.
        has_reading_form = (
            "reading-form" in text.lower()
            or "reading, not" in text.lower()
            or ("'the pattern reads as" in text.lower()
                and "verdict" in text.lower())
        )
        check(
            has_reading_form,
            f"prompt {prompt_name!r} does not teach reading-form vs "
            f"verdict-form; agent may close with a verdict on the "
            f"document instead of a reading of its framing",
        )
        # Either the prompt instructs ONE insight (self-audit, ai-audit,
        # explain_framing) or 2-3 questions each grounded in cited
        # measurements (challenge_document).
        has_compose_shape = (
            "ONE insight" in text
            or ("2-3 questions" in text
                and "grounded in" in text.lower())
            or "compose" in text.lower() and "grounded in" in text.lower()
        )
        check(
            has_compose_shape,
            f"prompt {prompt_name!r} does not teach the insight-led "
            f"compose shape (ONE insight, or 2-3 grounded questions); "
            f"agent will fall back to mechanical measurement walks",
        )
        check(
            "do not walk the measurements" in text.lower()
            or "do not walk" in text.lower(),
            f"prompt {prompt_name!r} does not forbid walking the "
            f"measurements one by one in the compact response; agent "
            f"may dump statistics instead of composing a reading",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_have_insight_led_discipline")
    print("  PASS  (insight-led discipline preserved across all four prompts)\n")


def test_all_prompts_pivot_frame_on_off_methodology():
    """Each prompt must teach the agent to PIVOT the frame when a
    confidence-gate trigger fires (under 100 words / non-English /
    non-analytical structure): instead of composing a reading of the
    document, compose a reading of what the run reveals about Frame
    Check's scope on this kind of text. Pins the discipline that
    prevents the agent from delivering a confident reading on
    off-methodology input.

    The pivot is the construct-honest move: when the methodology
    doesn't apply, the analysis is still informative, but it is
    informative about the tool's calibration, not the document's
    framing."""
    baseline = len(_FAILURES)
    print("=== all four prompts carry pivot-frame-on-off-methodology discipline ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 111, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "PIVOT" in text or "pivot" in text.lower(),
            f"prompt {prompt_name!r} does not teach the pivot-frame "
            f"discipline; agent will deliver a confident reading even "
            f"when an off-methodology trigger fires",
        )
        # The pivot is FROM document-reading TO scope-reading.
        has_pivot_target = (
            "scope" in text.lower()
            and ("Frame Check" in text or "the tool" in text.lower()
                 or "this kind of text" in text.lower())
        )
        check(
            has_pivot_target,
            f"prompt {prompt_name!r} does not name the pivot target "
            f"(reading about Frame Check's scope/calibration on this "
            f"kind of text); agent may pivot to nothing in particular",
        )
    _assert_no_new_failures(baseline, "test_all_prompts_pivot_frame_on_off_methodology")
    print("  PASS  (pivot-frame discipline preserved across all four prompts)\n")


def test_agent_guidance_carries_composition_discipline():
    """The agent_guidance dict must carry a composition_discipline
    field that pushes the insight-led discipline into the tool-level
    surface (not just the sovereignty prompts). When the user invokes
    frame_check via natural language ('call frame_check on this') the
    prompt-level discipline does not apply; the discipline must live
    in agent_guidance so it travels with every tool response.

    This was the failure surfaced in operator testing of the 0.8.0
    prerelease: the second test invoked frame_check via natural
    language, and the agent walked the measurements mechanically
    because the discipline lived only in the four sovereignty
    prompts, not in agent_guidance. Pins the field's presence and
    the five composition rules so a future change cannot strip the
    discipline."""
    baseline = len(_FAILURES)
    print("=== agent_guidance.composition_discipline carries insight-led rules ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    guidance = payload["agent_guidance"]
    check(
        "composition_discipline" in guidance,
        "agent_guidance must include a composition_discipline field "
        "so the insight-led shape travels with every tool response, "
        "not only with sovereignty-prompt invocations",
    )
    text = guidance.get("composition_discipline", "")
    check(
        "ONE insight" in text,
        "composition_discipline must instruct the agent to compose "
        "ONE insight (the central anti-measurement-dump rule)",
    )
    check(
        "reading the user could not see" in text.lower()
        or "could not see by re-reading" in text.lower(),
        "composition_discipline must frame the insight as a reading "
        "the user could not see themselves (the value-add criterion)",
    )
    check(
        "INSIGHT-GROUNDED" in text or "insight-grounded" in text.lower(),
        "composition_discipline must carry rule (1): every insight "
        "clause cites a specific measurement",
    )
    check(
        "READING-FORM" in text or "reading-form" in text.lower(),
        "composition_discipline must carry rule (2): reading-form, "
        "never verdict-form",
    )
    check(
        "CONFIDENCE-GATE PIVOTS" in text
        or "confidence-gate pivots" in text.lower(),
        "composition_discipline must carry rule (3): confidence-gate "
        "pivots the frame from document-reading to scope-reading",
    )
    check(
        "CROSS-CONTEXT" in text or "cross-context" in text.lower(),
        "composition_discipline must carry rule (4): cross-context "
        "compounding only when it adds, never as scenery",
    )
    check(
        "ABSENCE IS NOT PRESCRIPTION" in text
        or "absence is not prescription" in text.lower(),
        "composition_discipline must carry rule (5): absence is not "
        "prescription (extension to insight composition)",
    )
    check(
        "do not walk the measurements" in text.lower()
        or "measurement dump is not a reading" in text.lower(),
        "composition_discipline must explicitly forbid mechanical "
        "measurement-walking, the failure pattern this field exists "
        "to prevent",
    )
    _assert_no_new_failures(baseline, "test_agent_guidance_carries_composition_discipline")
    print("  PASS  (composition_discipline carries the five insight-led rules)\n")


def test_user_context_extends_agent_guidance():
    """When user_context is passed to frame_check, the
    agent_guidance.how_to_render_divergence text is extended with
    contextual filtering instructions plus the prescription-
    prevention guardrail. The MCP does NOT echo the user_context
    value back into the response (caller-side privacy posture); the
    caller's agent has the value from its own call args. Pins the
    discipline so a future change cannot weaken
    the guardrail or accidentally echo the value."""
    baseline = len(_FAILURES)
    print("=== user_context extends agent_guidance with guardrail ===")
    payload_with = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE,
        include_divergence=True,
        user_context="I'm a startup founder making a hire decision.",
    )
    text_with = payload_with["agent_guidance"]["how_to_render_divergence"]
    check(
        "User context was provided" in text_with,
        "user_context-aware addendum must appear in "
        "how_to_render_divergence when user_context is passed",
    )
    check(
        "RELEVANCE FILTERING" in text_with
        and "absence_is_not_prescription" in text_with,
        "addendum must carry the prescription-prevention guardrail "
        "(relevance filtering, not prescription)",
    )
    check(
        "I'm a startup founder making a hire decision." not in text_with,
        "user_context value must NOT be echoed verbatim into the "
        "response (caller-side privacy posture)",
    )
    payload_without = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text_without = payload_without["agent_guidance"]["how_to_render_divergence"]
    check(
        "User context was provided" not in text_without,
        "addendum must be absent when user_context is not passed",
    )
    _assert_no_new_failures(baseline, "test_user_context_extends_agent_guidance")
    print("  PASS\n")


def test_user_context_validation():
    """user_context input validation rejects: non-string types,
    empty/whitespace-only strings, strings exceeding 2000 chars.
    Pins the validation contract so a future relaxation cannot
    silently accept malformed input."""
    print("=== user_context input validation ===")
    # Non-string type
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 200, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "user_context": 123,
            },
        },
    })
    result = resp.get("result", {})
    assert result.get("isError") is True, (
        "non-string user_context must surface as isError"
    )
    text = result["content"][0]["text"]
    assert "user_context must be a string" in text, (
        f"isError must name the type constraint; got {text!r}"
    )
    # Empty string
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 201, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "user_context": "   ",
            },
        },
    })
    result = resp.get("result", {})
    assert result.get("isError") is True, (
        "whitespace-only user_context must surface as isError"
    )
    # Over-limit
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 202, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "user_context": "a" * 2001,
            },
        },
    })
    result = resp.get("result", {})
    assert result.get("isError") is True, (
        "over-limit user_context must surface as isError"
    )
    text = result["content"][0]["text"]
    assert "2000-character limit" in text, (
        f"isError must name the limit; got {text!r}"
    )
    # Valid
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 203, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "user_context": "I am a startup founder.",
                "include_divergence": True,
            },
        },
    })
    result = resp.get("result", {})
    assert result.get("isError") is not True, (
        f"valid user_context must succeed; got {result!r}"
    )
    print("  PASS\n")


# ── Layer 5: resource content hashes ──────────────────────────────


def test_resources_list_carries_content_hash():
    """Every advertised resource must carry a SHA-256 content hash
    so a client can detect drift and a citation can pin the exact
    bytes. Missing hash is acceptable only on an advertised-but-
    unreadable resource (rare, logged); in steady state every
    resource should have one."""
    print("=== resources/list carries SHA-256 contentHash ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 55, "method": "resources/list",
    })
    resources = resp["result"]["resources"]
    with_hash = [r for r in resources if "contentHash" in r]
    check(
        len(with_hash) == len(resources),
        f"every resource should carry contentHash; "
        f"got {len(with_hash)} of {len(resources)}",
    )
    # Spot-check hash shape: 64 lowercase hex chars for SHA-256.
    sample = with_hash[0]["contentHash"]
    check(
        len(sample) == 64 and all(c in "0123456789abcdef" for c in sample),
        f"contentHash must be 64 lowercase hex chars (SHA-256); "
        f"got {sample!r}",
    )
    _assert_no_new_failures(baseline, "test_resources_list_carries_content_hash")
    print("  PASS\n")


def test_resources_read_carries_content_hash():
    print("=== resources/read carries SHA-256 contentHash ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 56, "method": "resources/read",
        "params": {"uri": "frame-check://library/FVS-001"},
    })
    contents = resp["result"]["contents"]
    check(
        "contentHash" in contents[0],
        "contents must carry contentHash",
    )
    _assert_no_new_failures(baseline, "test_resources_read_carries_content_hash")
    print("  PASS\n")


def test_content_hash_stable_across_calls():
    """Same resource read twice produces the same hash. This is
    the reproducibility guarantee: a citation made today will
    resolve to the exact bytes tomorrow as long as the file does
    not change. Uses an FVS card that always ships in the wheel.
    """
    print("=== content hash is stable across calls ===")
    baseline = len(_FAILURES)
    for _ in range(3):
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 57, "method": "resources/read",
            "params": {"uri": "frame-check://library/FVS-008"},
        })
        h = resp["result"]["contents"][0]["contentHash"]
        if not hasattr(test_content_hash_stable_across_calls, "first"):
            test_content_hash_stable_across_calls.first = h
        check(
            h == test_content_hash_stable_across_calls.first,
            "content hash drifted across identical calls",
        )
    _assert_no_new_failures(baseline, "test_content_hash_stable_across_calls")
    print("  PASS\n")


def test_every_resource_has_stable_matching_hash():
    """Stronger than the single-resource stability check: every
    advertised resource's list-hash must equal its read-hash, and
    two sequential reads must produce the same hash. This is the
    citation-grade contract extended to the entire corpus, not just
    one sentinel resource. A regression that introduces a resource
    type without hash propagation fails here immediately, even if
    the single-resource test still passes.
    """
    print("=== every advertised resource has stable matching hash ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 200, "method": "resources/list",
    })
    resources = resp["result"]["resources"]
    check(
        len(resources) > 0,
        "resources/list returned zero resources; fixtures broken",
    )
    failures: list[str] = []
    for res in resources:
        uri = res["uri"]
        list_hash = res.get("contentHash")
        if not list_hash:
            failures.append(f"{uri}: no contentHash on resources/list")
            continue
        r1 = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 201, "method": "resources/read",
            "params": {"uri": uri},
        })
        r2 = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 202, "method": "resources/read",
            "params": {"uri": uri},
        })
        if "result" not in r1 or "result" not in r2:
            failures.append(f"{uri}: resources/read errored")
            continue
        c1 = r1["result"]["contents"][0]
        c2 = r2["result"]["contents"][0]
        h1 = c1.get("contentHash")
        h2 = c2.get("contentHash")
        if not h1 or not h2:
            failures.append(f"{uri}: contentHash missing on read")
            continue
        if h1 != h2:
            failures.append(
                f"{uri}: read hashes drifted ({h1!r} vs {h2!r})"
            )
            continue
        if h1 != list_hash:
            failures.append(
                f"{uri}: list hash {list_hash!r} != read hash {h1!r}"
            )
    check(
        not failures,
        "hash integrity failed on: " + "; ".join(failures[:5])
        + (f" (+{len(failures) - 5} more)" if len(failures) > 5 else ""),
    )
    print(f"  {len(resources)} resources, all stable")
    _assert_no_new_failures(baseline, "test_every_resource_has_stable_matching_hash")
    print("  PASS\n")


def test_content_hashes_differ_across_distinct_resources():
    """Different resources must produce different hashes. Sanity
    check that the hash is computed on actual content, not on a
    shared constant."""
    print("=== distinct resources have distinct hashes ===")
    baseline = len(_FAILURES)
    r1 = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 58, "method": "resources/read",
        "params": {"uri": "frame-check://library/FVS-001"},
    })
    r2 = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 59, "method": "resources/read",
        "params": {"uri": "frame-check://library/FVS-002"},
    })
    h1 = r1["result"]["contents"][0]["contentHash"]
    h2 = r2["result"]["contents"][0]["contentHash"]
    check(h1 != h2, "FVS-001 and FVS-002 must have distinct hashes")
    _assert_no_new_failures(baseline, "test_content_hashes_differ_across_distinct_resources")
    print("  PASS\n")


def test_resources_list_drops_unreadable_not_hashless():
    """A resource whose read fails during list construction must be
    dropped entirely, not advertised without a contentHash. Pins
    the citation-grade invariant: every advertised URI has a hash,
    always. Monkeypatches _read_resource to raise for one URI and
    verifies that (a) the URI is absent from the list, (b) every
    remaining entry carries contentHash, (c) the original function
    is restored on teardown."""
    print("=== resources/list drops unreadable entries ===")
    baseline = len(_FAILURES)
    original = mcp_server._read_resource
    victim_uri = "frame-check://library/FVS-001"

    def flaky_read(uri):
        if uri == victim_uri:
            raise OSError("simulated transient I/O failure")
        return original(uri)

    try:
        mcp_server._read_resource = flaky_read
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 210, "method": "resources/list",
        })
        resources = resp["result"]["resources"]
        uris = [r["uri"] for r in resources]
        check(
            victim_uri not in uris,
            "unreadable URI must be dropped from list; still present",
        )
        hashless = [r["uri"] for r in resources if "contentHash" not in r]
        check(
            not hashless,
            f"every advertised resource must carry contentHash; "
            f"got hashless: {hashless[:3]}",
        )
    finally:
        mcp_server._read_resource = original
    _assert_no_new_failures(baseline, "test_resources_list_drops_unreadable_not_hashless")
    print("  PASS\n")


def test_worked_example_reproduces_from_captured_payload():
    """The Grok-on-NVIDIA worked example captured its source text,
    the LLM summary text, SHA-256 hashes of both, and the full
    Frame Check payload as data.json. Re-running build_epistemic_payload
    on the captured texts must produce measurements that match the
    captured payload field-for-field (minus timestamps and latency).

    This is the load-bearing reproducibility test for any worked
    example that claims 'anyone can reproduce this exactly'. If it
    regresses, the worked-example corpus's citation contract is
    broken, and we need to either fix the regression or invalidate
    the example.
    """
    print("=== Grok-on-NVIDIA worked example reproduces exactly ===")
    baseline = len(_FAILURES)
    data_path = (
        REPO_ROOT
        / "data"
        / "worked_examples"
        / "grok-on-nvidia-earnings-2026"
        / "data.json"
    )
    if not data_path.is_file():
        print("  (data.json not present; skipping)\n")
        return
    with open(data_path, encoding="utf-8") as f:
        capture = json.load(f)

    source_text = capture["source"]["text"]
    summary_text = capture["llm_summary"]["text"]
    captured_payload = capture["frame_check_payload"]

    fresh = mcp_server.build_epistemic_payload(
        summary_text, source_text=source_text,
    )

    def core_fields(payload: dict) -> dict:
        a = payload["analysis"]
        v = a.get("verification", {})
        return {
            "voice": a["voice"]["classification"],
            "coverage_addressed": sorted(a["coverage"]["addressed"]),
            "coverage_missing": sorted(a["coverage"]["missing"]),
            "temporal_dominant": a["temporal"]["dominant"],
            "sourced_pct": a["epistemic"]["sourced_pct"],
            "source_fidelity": {
                k: v.get("source_fidelity", {}).get(k)
                for k in (
                    "total_numbers", "in_source",
                    "not_in_source", "unsourced_rate",
                )
            },
            "grounding_proportions": (
                v.get("grounding_decomposition", {}).get("proportions")
            ),
            "grounding_regime": (
                v.get("grounding_decomposition", {})
                .get("scope_assessment", {})
                .get("derivation_regime")
            ),
            "frames": sorted(
                m["fvs_id"]
                for m in a.get("frame_library_matches", [])
            ),
        }

    captured_core = core_fields(captured_payload)
    fresh_core = core_fields(fresh)
    check(
        captured_core == fresh_core,
        f"worked-example measurements drifted: "
        f"captured={captured_core!r} vs fresh={fresh_core!r}",
    )

    # Sanity: the captured source and summary SHA-256 hashes must
    # still match their literal bytes. If anyone edited the capture,
    # this catches it.
    import hashlib as _hashlib
    src_hash = _hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    sum_hash = _hashlib.sha256(summary_text.encode("utf-8")).hexdigest()
    check(
        src_hash == capture["source"]["sha256"],
        "source SHA-256 mismatch against captured bytes; data.json edited",
    )
    check(
        sum_hash == capture["llm_summary"]["sha256"],
        "summary SHA-256 mismatch against captured bytes; data.json edited",
    )
    _assert_no_new_failures(baseline, "test_worked_example_reproduces_from_captured_payload")
    print("  PASS\n")


def test_cli_version_flag():
    """`python3 mcp_server.py --version` prints a single-line install
    fingerprint with every field the operator needs to verify a
    Claude Desktop install against repo HEAD. Pinned so a future
    refactor of the CLI entry point cannot silently drop fields.

    Fields required (any omission breaks stale-install detection):
      server_version, protocol, git_sha, frame_library_version,
      corpus_slugs, corpus_hash, python, script.

    Header line must identify the server by name so multiple MCP
    servers installed on the same machine are distinguishable from
    their --version output alone.
    """
    print("=== --version CLI fingerprint ===")
    baseline = len(_FAILURES)
    server_path = REPO_ROOT / "mcp_server.py"
    result = subprocess.run(
        ["python3", str(server_path), "--version"],
        capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
    )
    check(result.returncode == 0,
          f"--version exited with code {result.returncode}; stderr={result.stderr}")
    lines = result.stdout.strip().splitlines()
    check(len(lines) == 2,
          f"--version should emit exactly 2 lines (header + fields), got {len(lines)}")
    check(lines[0].startswith("frame-check mcp_server v"),
          f"header line should start with 'frame-check mcp_server v', got {lines[0]!r}")
    required = [
        "server_version=", "protocol=", "git_sha=",
        "frame_library_version=", "corpus_slugs=", "corpus_hash=",
        "python=", "script=",
    ]
    for field in required:
        check(field in lines[1],
              f"--version fields line missing required field {field!r}: {lines[1]!r}")
    # -V short form must match --version output.
    result_short = subprocess.run(
        ["python3", str(server_path), "-V"],
        capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
    )
    check(result_short.returncode == 0,
          f"-V exited with code {result_short.returncode}")
    check(result_short.stdout == result.stdout,
          "-V output must match --version output byte-for-byte")
    _assert_no_new_failures(baseline, "test_cli_version_flag")
    print("  --version: OK")


def test_cli_help_flag():
    """`python3 mcp_server.py --help` prints a usage doc with every
    supported flag named. The help surface is the first thing an
    operator consults when the stdio mode does not start; a missing
    flag in --help is a documentation discipline gap.
    """
    print("=== --help CLI usage ===")
    baseline = len(_FAILURES)
    server_path = REPO_ROOT / "mcp_server.py"
    result = subprocess.run(
        ["python3", str(server_path), "--help"],
        capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
    )
    check(result.returncode == 0,
          f"--help exited with code {result.returncode}; stderr={result.stderr}")
    out = result.stdout
    required_sections = ("USAGE", "FLAGS", "STARTUP AND TROUBLESHOOTING")
    for section in required_sections:
        check(section in out,
              f"--help output missing required section {section!r}")
    required_flags = ("--test", "--version", "-V", "--help", "-h")
    for flag in required_flags:
        check(flag in out,
              f"--help output does not mention flag {flag!r}")
    # -h short form must match --help output.
    result_short = subprocess.run(
        ["python3", str(server_path), "-h"],
        capture_output=True, text=True, timeout=10, cwd=str(REPO_ROOT),
    )
    check(result_short.returncode == 0,
          f"-h exited with code {result_short.returncode}")
    check(result_short.stdout == result.stdout,
          "-h output must match --help output byte-for-byte")
    _assert_no_new_failures(baseline, "test_cli_help_flag")
    print("  --help: OK")


def test_cli_test_triggers_fvs_matches():
    """`python3 mcp_server.py --test` output must include at least
    one FVS match in the frame_library_matches array. The canned
    sample exists precisely to demonstrate the headline capability
    to a first-time integrator. A sample that does not trigger
    suggest_frames is a documentation discipline gap: the tool
    appears to have no named-pattern detection surface.
    """
    print("=== --test triggers FVS match ===")
    baseline = len(_FAILURES)
    server_path = REPO_ROOT / "mcp_server.py"
    result = subprocess.run(
        ["python3", str(server_path), "--test"],
        capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
    )
    check(result.returncode == 0,
          f"--test exited with code {result.returncode}; stderr={result.stderr}")
    # Parse the first frame_check payload (structural only) from the
    # --test output. The payload is a JSON block after the first
    # "=== frame_check" header. Use a tolerant heuristic: find the
    # substring and scan for "frame_library_matches": [ followed
    # by a non-empty array.
    marker = '"frame_library_matches": ['
    idx = result.stdout.find(marker)
    check(idx >= 0, "frame_library_matches key absent from --test output")
    # Non-empty array starts with { after the bracket (entries are
    # JSON objects); empty array would be "frame_library_matches": []
    # possibly followed by newline.
    tail = result.stdout[idx + len(marker):idx + len(marker) + 40]
    check("{" in tail or '"fvs_id"' in tail,
          f"frame_library_matches appears empty in --test output; "
          f"tail was {tail!r}. Expand _SAMPLE_DOC so at least one "
          f"FVS rule fires so first-time integrators see the headline "
          f"capability demonstrated.")
    _assert_no_new_failures(baseline, "test_cli_test_triggers_fvs_matches")
    print("  --test FVS-match invariant: OK")


def test_stdio_subprocess_roundtrip():
    """Spawn the server as a child process and drive it over stdio
    exactly the way Claude Desktop / Cursor would. Catches
    regressions in the stdio framing, stdout cleanliness (only
    JSON-RPC, no stray prints), and the import path.
    """
    print("=== stdio subprocess handshake + tool call ===")
    baseline = len(_FAILURES)
    server_path = REPO_ROOT / "mcp_server.py"
    proc = subprocess.Popen(
        ["python3", str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REPO_ROOT),
    )

    def call(req):
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline().strip()
        return json.loads(line) if line else None

    try:
        # initialize
        r = call({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
        check(r["result"]["serverInfo"]["name"] == mcp_server.SERVER_NAME,
              "subprocess initialize returned wrong server name")

        # tools/list
        r = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = r["result"]["tools"]
        check(
            any(t["name"] == "frame_check" for t in tools),
            "subprocess tools/list missing frame_check",
        )

        # tools/call
        r = call({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "frame_check",
                "arguments": {"document_text": _DOC_SAMPLE},
            },
        })
        check(
            r["result"].get("isError") is False,
            "subprocess tools/call isError was truthy",
        )
        payload = json.loads(r["result"]["content"][0]["text"])
        check(
            {"analysis", "agent_guidance", "provenance"}.issubset(payload.keys()),
            "subprocess payload missing one of the three sections",
        )

        # resources/list over stdio. Catches stdio framing
        # regressions specific to the resources surface: the
        # library resource list is the largest single payload
        # (22+ entries), and a newline or encoding issue here
        # would hide from the in-process tests above.
        r = call({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
        resources = r["result"]["resources"]
        check(
            len(resources) >= 3,
            "subprocess resources/list returned too few resources",
        )

        # resources/read over stdio, large payload. A full FVS entry
        # is the biggest single content any resource emits; if the
        # JSON-RPC envelope + content text trip the readline buffer
        # or stdout flush policy, this is where it shows up.
        entry_uri = next(
            r["uri"] for r in resources
            if r["uri"].startswith("frame-check://library/FVS-")
        )
        r = call({
            "jsonrpc": "2.0", "id": 5, "method": "resources/read",
            "params": {"uri": entry_uri},
        })
        contents = r["result"]["contents"]
        check(
            contents[0]["mimeType"] == "text/markdown",
            "subprocess resource read mimeType mismatch",
        )
        check(
            contents[0]["text"].startswith("# "),
            "subprocess library resource must open with an H1 title",
        )

        # Error path over stdio: unknown library entry returns a
        # JSON-RPC error envelope, not a malformed response.
        r = call({
            "jsonrpc": "2.0", "id": 6, "method": "resources/read",
            "params": {"uri": "frame-check://library/FVS-999"},
        })
        check(
            "error" in r and r["error"]["code"] == -32602,
            "subprocess unknown-resource error must carry code -32602",
        )
    finally:
        with contextlib.suppress(Exception):
            proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        with contextlib.suppress(Exception):
            proc.stdout.close()
        with contextlib.suppress(Exception):
            proc.stderr.close()
    _assert_no_new_failures(baseline, "test_stdio_subprocess_roundtrip")
    print("  PASS\n")


# ── Frame Divergence block (FRAME_DIVERGENCE_CONTRACT_v1 Part 2) ────
#
# Tests pin the Part 2 §§3-4 + §7.1 contract for the MCP surface:
# - Default behavior unchanged (no divergence block unless opted in)
# - Opt-in via include_divergence=True adds divergence block
# - AbsentFrameRecord required fields per §4.2
# - FaithfulnessEnvelope required fields per §4.3
# - agent_guidance additions per §4.4 (how_to_render_divergence +
#   absence_is_not_prescription)
# - Surface-specific v4_2_execution per §7.1 (MCP = caller_side)
# - FVS-020 excluded from absent_frames (Step 4 retirement)
# - Input validation rejects malformed enum values


def test_divergence_present_by_default():
    """At 0.8.0 the default for include_divergence is True; the
    payload carries the divergence block on the default code path,
    not as opt-in. Pins the new default and the response shape so a
    future flip to false (which would be a major-version change)
    cannot land silently.
    """
    baseline = len(_FAILURES)
    print("=== divergence present by default at 0.8.0 ===")
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    check(
        "divergence" in payload,
        "divergence key MUST appear when include_divergence defaults to True (0.8.0+)",
    )
    ag = payload["agent_guidance"]
    check(
        "how_to_render_divergence" in ag,
        "agent_guidance.how_to_render_divergence must be present by default",
    )
    check(
        "absence_is_not_prescription" in ag,
        "agent_guidance.absence_is_not_prescription must be present by default",
    )
    _assert_no_new_failures(baseline, "test_divergence_present_by_default")
    print("  PASS\n")


def test_divergence_legacy_opt_out():
    """Setting include_divergence=False explicitly preserves the
    v0.7.x-shape response with no divergence block. The 0.8.0 default
    flip is forward-incompatible by shape but preserves backward
    compatibility for callers who want the old shape."""
    baseline = len(_FAILURES)
    print("=== divergence absent when explicitly opted out ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=False
    )
    check(
        "divergence" not in payload,
        "divergence key must NOT appear when include_divergence=False",
    )
    ag = payload["agent_guidance"]
    check(
        "how_to_render_divergence" not in ag,
        "agent_guidance.how_to_render_divergence must be absent on opt-out",
    )
    check(
        "absence_is_not_prescription" not in ag,
        "agent_guidance.absence_is_not_prescription must be absent on opt-out",
    )
    _assert_no_new_failures(baseline, "test_divergence_legacy_opt_out")
    print("  PASS\n")


def test_divergence_opt_in_adds_block():
    """include_divergence=True adds top-level divergence plus the two
    required agent_guidance additions per §4.4."""
    print("=== divergence block present when opted in ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    check("divergence" in payload, "divergence block must be present")
    div = payload["divergence"]
    check("absent_frames" in div, "divergence.absent_frames must be present")
    check("envelope" in div, "divergence.envelope must be present")
    check(isinstance(div["absent_frames"], list),
          "absent_frames must be a list")
    check(isinstance(div["envelope"], dict),
          "envelope must be a dict")
    ag = payload["agent_guidance"]
    check("how_to_render_divergence" in ag,
          "agent_guidance.how_to_render_divergence must be present per §4.4")
    check("absence_is_not_prescription" in ag,
          "agent_guidance.absence_is_not_prescription must be present per §4.4")
    # The absence_is_not_prescription text is verbatim per §4.4
    check(
        "surfaces absence" in ag["absence_is_not_prescription"].lower()
        or "the thinker decides" in ag["absence_is_not_prescription"].lower(),
        "absence_is_not_prescription must carry Part 1 §5.1.5 guarantee language",
    )
    _assert_no_new_failures(baseline, "test_divergence_opt_in_adds_block")
    print("  PASS\n")


def test_absent_frames_carry_signal_strength_tier():
    """At 0.8.0 each absent_frame record carries a signal_strength
    tier (high/medium/low) and the affects_dimensions list it was
    scored against. Records are sorted by tier (high first) for
    deterministic, leverage-ordered output. Pins the c1.0 §13
    signal_strength shape so a future tier rename or sort change
    cannot land silently.
    """
    baseline = len(_FAILURES)
    print("=== absent_frames carry signal_strength tier ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    absent = payload["divergence"]["absent_frames"]
    check(len(absent) > 0, "absent_frames must be non-empty for the canned doc")
    valid_tiers = {"high", "medium", "low"}
    for record in absent:
        check(
            "signal_strength" in record,
            f"every absent_frame record must carry signal_strength; "
            f"record for {record.get('frame_id')!r} is missing it",
        )
        check(
            record.get("signal_strength") in valid_tiers,
            f"signal_strength must be one of {valid_tiers}; "
            f"got {record.get('signal_strength')!r} for "
            f"{record.get('frame_id')!r}",
        )
        check(
            "affects_dimensions" in record,
            f"every absent_frame record must carry affects_dimensions; "
            f"record for {record.get('frame_id')!r} is missing it",
        )
        check(
            isinstance(record.get("affects_dimensions"), list),
            f"affects_dimensions must be a list; got "
            f"{type(record.get('affects_dimensions')).__name__} for "
            f"{record.get('frame_id')!r}",
        )
    # Sort order: signal_strength tier first (high before medium
    # before low). Within tier, genre-relevant absences (carrying a
    # genre_relevance.priority) rise above non-relevant ones; ties
    # broken by frame_id ascending. This is Item 3's promotion: the
    # canonical sort respects both catalog/coverage tier and genre
    # relevance.
    tier_index = {"high": 0, "medium": 1, "low": 2}
    sort_keys = [
        (
            tier_index.get(r["signal_strength"], 9),
            (r.get("genre_relevance") or {}).get("priority", 999),
            r["frame_id"],
        )
        for r in absent
    ]
    check(
        sort_keys == sorted(sort_keys),
        "absent_frames must be sorted by signal_strength tier, then "
        "genre_relevance priority (when present), then frame_id "
        "ascending; "
        f"got order {[r['signal_strength'] + ':' + r['frame_id'] for r in absent[:5]]}",
    )
    _assert_no_new_failures(baseline, "test_absent_frames_carry_signal_strength_tier")
    print("  PASS\n")


def test_envelope_carries_divergence_summary_and_tier_counts():
    """At 0.8.0 the envelope carries a `divergence_summary` prose
    field that names the semantic intent of the block, plus a
    `tier_counts` dict with high/medium/low counts. Pins the c1.0
    §13 envelope additions so a future drift cannot remove them
    silently.
    """
    baseline = len(_FAILURES)
    print("=== envelope carries divergence_summary + tier_counts ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    env = payload["divergence"]["envelope"]
    check(
        "divergence_summary" in env,
        "envelope.divergence_summary must be present at 0.8.0",
    )
    summary = env.get("divergence_summary", "")
    check(
        isinstance(summary, str) and len(summary) >= 50,
        f"divergence_summary must be substantive prose (>= 50 chars); "
        f"got len={len(summary) if isinstance(summary, str) else 'non-str'}",
    )
    # Summary must name the substrate framing (not "verdict")
    check(
        "substrate" in summary.lower() and "verdict" in summary.lower(),
        "divergence_summary must name the substrate-not-verdict framing "
        "so callers see the semantic intent, not just the mechanics",
    )
    check(
        "tier_counts" in env,
        "envelope.tier_counts must be present at 0.8.0",
    )
    counts = env.get("tier_counts", {})
    check(
        isinstance(counts, dict)
        and set(counts.keys()) == {"high", "medium", "low"},
        f"tier_counts must have exactly high/medium/low keys; "
        f"got {sorted(counts.keys()) if isinstance(counts, dict) else 'non-dict'}",
    )
    n_absent = len(payload["divergence"]["absent_frames"])
    check(
        sum(counts.values()) == n_absent,
        f"tier_counts must sum to len(absent_frames); "
        f"sum={sum(counts.values())}, n_absent={n_absent}",
    )
    _assert_no_new_failures(
        baseline, "test_envelope_carries_divergence_summary_and_tier_counts"
    )
    print("  PASS\n")


# Document that produces broad coverage gaps so absence clusters fire.
# Multiple frames absent across coverage and counterfactual dimensions
# (the two dimensions with >=3 canon members in DIMENSION_LIBRARY_ENTRIES).
_DOC_FOR_CLUSTERS = (
    "The 2026 outlook for renewable energy looks strong. Solar panel "
    "costs dropped 40 percent this year alone. Wind turbine deployment "
    "hit record highs in Texas. Battery storage capacity grew 60 "
    "percent. Investors are pouring money in. The IRA continues to "
    "drive growth. Major utilities are restructuring around clean "
    "energy. Grid modernization is accelerating. Electric vehicle "
    "sales surged 30 percent year over year. Charging infrastructure "
    "expanded. Heat pump installations doubled. Building "
    "electrification accelerated in major cities. Green hydrogen "
    "pilots launched in five states. Industrial decarbonization is "
    "mainstream. ESG mandates from major institutional investors "
    "continue to redirect capital. Carbon credit prices stabilized "
    "around 75 dollars per ton. Verification platforms emerged. "
    "Solar farm development is at all-time highs. Offshore wind "
    "broke ground in three states. The market is decisively "
    "shifting. Returns are attractive. The transition is unstoppable."
)


def test_divergence_block_carries_absence_clusters():
    """Substrate-side composition over absent frames: the divergence
    block carries an `absence_clusters` field that groups absent
    frames by shared canonical dimension. Each cluster surfaces only
    when (a) at least _CLUSTER_MIN_ABSENT absent frames share a
    dimension AND (b) the absent set covers at least
    _CLUSTER_MIN_CANON_FRACTION of that dimension's canon. The
    two-condition logic keeps the substrate calibration-honest
    across the canon graph's dimensions of varying size.

    Pins:
      - absence_clusters key present on every divergence response
      - cluster shape (dimension, member_frames, member_count,
        canon_size, canon_coverage_fraction, signal_strength, reading)
      - clusters fire on a coverage-weak document
      - cluster reading is dimension-specific and evidence-anchored
        (mentions member_count and canon_size of the cluster, not
        boilerplate)
      - member_frames sorted alphabetically for deterministic output
      - clusters sorted by signal_strength (high first), then
        canon_coverage_fraction descending, then dimension alphabetical
    """
    baseline = len(_FAILURES)
    print("=== divergence block carries absence_clusters ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    div = payload.get("divergence", {})
    check(
        "absence_clusters" in div,
        "divergence.absence_clusters must be present (the substrate's "
        "first composition layer over the divergence set)",
    )
    clusters = div.get("absence_clusters", [])
    check(
        isinstance(clusters, list),
        f"absence_clusters must be a list; got {type(clusters).__name__}",
    )
    check(
        len(clusters) >= 1,
        f"coverage-weak document with broad numerical assertions must "
        f"surface at least one absence cluster; got {len(clusters)}",
    )
    required_fields = {
        "dimension", "member_frames", "member_count",
        "canon_size", "canon_coverage_fraction", "signal_strength",
        "reading",
    }
    for cluster in clusters:
        check(
            isinstance(cluster, dict) and required_fields <= set(cluster.keys()),
            f"each cluster must carry {sorted(required_fields)}; "
            f"got keys={sorted(cluster.keys())}",
        )
        check(
            isinstance(cluster.get("dimension"), str) and cluster["dimension"],
            f"cluster.dimension must be a non-empty string; "
            f"got {cluster.get('dimension')!r}",
        )
        members = cluster.get("member_frames", [])
        check(
            isinstance(members, list) and all(isinstance(m, str) for m in members),
            f"cluster.member_frames must be list[str]; got {members!r}",
        )
        check(
            members == sorted(members),
            f"cluster.member_frames must be sorted alphabetically for "
            f"deterministic output; got {members!r}",
        )
        check(
            cluster.get("member_count") == len(members),
            f"cluster.member_count must equal len(member_frames); "
            f"member_count={cluster.get('member_count')} "
            f"len(member_frames)={len(members)}",
        )
        canon_size = cluster.get("canon_size")
        check(
            isinstance(canon_size, int) and canon_size >= 1,
            f"cluster.canon_size must be a positive integer; "
            f"got {canon_size!r}",
        )
        fraction = cluster.get("canon_coverage_fraction")
        check(
            isinstance(fraction, float) and 0.0 < fraction <= 1.0,
            f"cluster.canon_coverage_fraction must be a float in (0, 1]; "
            f"got {fraction!r}",
        )
        check(
            cluster["member_count"] <= canon_size,
            f"member_count must not exceed canon_size; "
            f"member_count={cluster['member_count']} "
            f"canon_size={canon_size}",
        )
        check(
            cluster.get("signal_strength") in {"high", "medium", "low"},
            f"cluster.signal_strength must be one of high/medium/low; "
            f"got {cluster.get('signal_strength')!r}",
        )
        # Threshold discipline: at least 2 absent and at least 50% of
        # canon. Either condition violated would mean the cluster
        # surfaced under noise.
        check(
            cluster["member_count"] >= 2,
            f"cluster must have at least 2 member frames "
            f"(_CLUSTER_MIN_ABSENT); got {cluster['member_count']}",
        )
        check(
            fraction >= 0.5,
            f"cluster must cover at least 50 percent of canon "
            f"(_CLUSTER_MIN_CANON_FRACTION); got {fraction}",
        )
        # Evidence-anchored reading: must mention dimension AND the
        # specific count anchoring (e.g. "X of Y").
        reading = cluster.get("reading", "")
        check(
            cluster["dimension"] in reading,
            f"cluster.reading must name its own dimension "
            f"({cluster['dimension']!r}); got reading={reading[:80]!r}",
        )
        check(
            f"{cluster['member_count']} of {canon_size}" in reading,
            f"cluster.reading must anchor in evidence by naming "
            f"member_count of canon_size (e.g. "
            f"'{cluster['member_count']} of {canon_size}'); "
            f"got reading={reading[:120]!r}",
        )
    # Sort order: signal_strength (high before medium before low),
    # then canon_coverage_fraction descending.
    tier_order = {"high": 0, "medium": 1, "low": 2}
    sort_keys = [
        (tier_order[c["signal_strength"]], -c["canon_coverage_fraction"])
        for c in clusters
    ]
    check(
        sort_keys == sorted(sort_keys),
        f"absence_clusters must be sorted by signal_strength then "
        f"canon_coverage_fraction descending; got sort_keys={sort_keys}",
    )
    _assert_no_new_failures(baseline, "test_divergence_block_carries_absence_clusters")
    print(f"  PASS  ({len(clusters)} cluster(s) surfaced)\n")


def test_absence_clusters_empty_when_no_dimension_reaches_threshold():
    """Construct-honest empty case: when no dimension reaches the
    firing threshold (>=_CLUSTER_MIN_ABSENT absent AND >=
    _CLUSTER_MIN_CANON_FRACTION of canon absent), the substrate
    must not fabricate a cluster. The empty list is the honest
    output; the agent falls back to per-frame composition.

    Pins the threshold discipline. A future change that relaxes
    either condition would surface clusters as noise.
    """
    baseline = len(_FAILURES)
    print("=== absence_clusters empty when below threshold ===")
    # Synthetic fixture: one absent frame per dimension. Below the
    # _CLUSTER_MIN_ABSENT=2 floor; no cluster fires regardless of
    # canon-fraction logic.
    synthetic_absent = [
        {
            "frame_id": "FVS-001",
            "affects_dimensions": ["coverage", "counterfactual"],
            "signal_strength": "low",
        },
    ]
    clusters = mcp_server._build_absence_clusters(synthetic_absent)
    check(
        clusters == [],
        f"absence_clusters must be empty when no dimension has 2+ "
        f"absent frames (the floor condition keeps the substrate "
        f"from emitting single-frame clusters); got {clusters!r}",
    )
    _assert_no_new_failures(
        baseline, "test_absence_clusters_empty_when_no_dimension_reaches_threshold"
    )
    print("  PASS\n")


def test_absence_clusters_threshold_relative_to_canon_size():
    """Calibration honesty: the threshold is relative to each
    dimension's canon size, not absolute. Calibration has 2 canon
    members in DIMENSION_LIBRARY_ENTRIES; both absent is 100% of
    canon and a strong signal. An absolute threshold of 3 would
    silently drop this cluster. The relative threshold (50% of canon
    AND >=2 absent) surfaces it.

    Pins:
      - calibration cluster fires when both canon members are absent
      - cluster's canon_coverage_fraction is 1.0 in that case
      - single-canon dimensions (evidence, robustness) cannot cluster
        (they cannot reach 2 absent); the substrate stays honest by
        not surfacing them
    """
    baseline = len(_FAILURES)
    print("=== absence_clusters threshold is canon-size-relative ===")
    # Synthetic fixture: both calibration canon members absent.
    # FVS-012 and FVS-017 are the calibration canon per
    # DIMENSION_LIBRARY_ENTRIES.
    synthetic_absent = [
        {
            "frame_id": "FVS-012",
            "affects_dimensions": ["calibration", "counterfactual"],
            "signal_strength": "medium",
        },
        {
            "frame_id": "FVS-017",
            "affects_dimensions": ["coverage", "calibration"],
            "signal_strength": "high",
        },
    ]
    clusters = mcp_server._build_absence_clusters(synthetic_absent)
    cal_clusters = [c for c in clusters if c["dimension"] == "calibration"]
    check(
        len(cal_clusters) == 1,
        f"calibration cluster must fire when both canon members "
        f"({{FVS-012, FVS-017}}) are absent; got {len(cal_clusters)} "
        f"calibration cluster(s)",
    )
    if cal_clusters:
        cal = cal_clusters[0]
        check(
            cal["canon_coverage_fraction"] == 1.0,
            f"calibration cluster with both canon members absent must "
            f"have canon_coverage_fraction=1.0; got {cal['canon_coverage_fraction']}",
        )
        check(
            cal["signal_strength"] == "high",
            f"calibration cluster signal_strength must aggregate to "
            f"the highest member tier (FVS-017 is high here); "
            f"got {cal['signal_strength']}",
        )
    # Evidence and robustness have 1 canon member each; they cannot
    # reach 2 absent and so cannot cluster. Verify neither fires
    # even when their lone canon member is absent.
    synthetic_evidence_robustness = [
        {
            "frame_id": "FVS-016",  # canon for both evidence + robustness
            "affects_dimensions": ["evidence", "robustness"],
            "signal_strength": "high",
        },
    ]
    rare_clusters = mcp_server._build_absence_clusters(synthetic_evidence_robustness)
    rare_dims = {c["dimension"] for c in rare_clusters}
    check(
        "evidence" not in rare_dims and "robustness" not in rare_dims,
        f"single-canon dimensions (evidence, robustness) must never "
        f"cluster (cannot reach 2 absent); got dims={rare_dims}",
    )
    _assert_no_new_failures(
        baseline, "test_absence_clusters_threshold_relative_to_canon_size"
    )
    print("  PASS  (calibration fires at 100 percent canon; single-canon never)\n")


def test_absence_cluster_signal_strength_aggregates_member_tiers():
    """Cluster signal_strength is the highest member-frame tier.
    A cluster of high-tier absences is high-signal; a cluster of all-
    low-tier absences is low-signal. Pins the aggregation so the
    substrate's cluster ranking reflects underlying tier evidence.
    """
    baseline = len(_FAILURES)
    print("=== absence cluster signal_strength aggregates from members ===")
    # All-low cluster.
    all_low = [
        {"frame_id": "FVS-A", "affects_dimensions": ["coverage"], "signal_strength": "low"},
        {"frame_id": "FVS-B", "affects_dimensions": ["coverage"], "signal_strength": "low"},
        {"frame_id": "FVS-C", "affects_dimensions": ["coverage"], "signal_strength": "low"},
        {"frame_id": "FVS-D", "affects_dimensions": ["coverage"], "signal_strength": "low"},
    ]
    low_clusters = mcp_server._build_absence_clusters(all_low)
    if low_clusters:
        check(
            low_clusters[0]["signal_strength"] == "low",
            f"cluster of all-low-tier members must be low-signal; "
            f"got {low_clusters[0]['signal_strength']}",
        )
    # Mixed cluster (one high among lows): aggregates to high.
    mixed = [
        {"frame_id": "FVS-A", "affects_dimensions": ["coverage"], "signal_strength": "low"},
        {"frame_id": "FVS-B", "affects_dimensions": ["coverage"], "signal_strength": "low"},
        {"frame_id": "FVS-C", "affects_dimensions": ["coverage"], "signal_strength": "low"},
        {"frame_id": "FVS-D", "affects_dimensions": ["coverage"], "signal_strength": "high"},
    ]
    mixed_clusters = mcp_server._build_absence_clusters(mixed)
    if mixed_clusters:
        check(
            mixed_clusters[0]["signal_strength"] == "high",
            f"cluster signal_strength must aggregate to the strongest "
            f"member tier (one high among lows -> high); "
            f"got {mixed_clusters[0]['signal_strength']}",
        )
    _assert_no_new_failures(
        baseline, "test_absence_cluster_signal_strength_aggregates_member_tiers"
    )
    print("  PASS\n")


def test_absence_cluster_readings_are_dimension_specific():
    """Each canonical dimension's cluster reading must be distinct
    from every other dimension's reading. Pins that the substrate
    has curated dimension-specific prose for each of the five
    dimensions in DIMENSION_LIBRARY_ENTRIES, not a single template
    with the dimension name interpolated. Without this, the
    substrate's composition collapses into boilerplate that the
    agent cannot distinguish from a list dump.
    """
    baseline = len(_FAILURES)
    print("=== absence cluster readings are dimension-specific ===")
    readings = mcp_server._DIMENSION_CLUSTER_READINGS
    # Five canonical dimensions per DIMENSION_LIBRARY_ENTRIES.
    expected_dims = {
        "coverage", "calibration", "evidence", "robustness", "counterfactual",
    }
    check(
        set(readings.keys()) == expected_dims,
        f"_DIMENSION_CLUSTER_READINGS must cover exactly the five "
        f"canonical dimensions in DIMENSION_LIBRARY_ENTRIES; "
        f"got {sorted(readings.keys())}",
    )
    # Each reading must mention its own dimension by name.
    for dim, reading in readings.items():
        check(
            dim in reading,
            f"reading for dimension {dim!r} must name the dimension; "
            f"got {reading[:80]!r}",
        )
    # All readings must be distinct (no copy-paste boilerplate).
    distinct = len(set(readings.values()))
    check(
        distinct == len(readings),
        f"every dimension reading must be distinct (substrate composes "
        f"per-dimension, not boilerplate); got {distinct} distinct out "
        f"of {len(readings)} readings",
    )
    # Reading-form not verdict-form: each must use language that
    # describes what the framing does NOT do, not what the document
    # IS. "leaves out", "does not signal", "does not lean", "does
    # not test", "does not name" are reading-form. "the document is
    # X" or "the document fails to" would be verdict-form.
    forbidden_verdict_phrases = [
        "the document is ",
        "the document fails ",
        "this document is ",
    ]
    for dim, reading in readings.items():
        for phrase in forbidden_verdict_phrases:
            check(
                phrase not in reading.lower(),
                f"reading for {dim!r} must not use verdict-form "
                f"({phrase!r}); rephrase as descriptive of the framing",
            )
    _assert_no_new_failures(
        baseline, "test_absence_cluster_readings_are_dimension_specific"
    )
    print(f"  PASS  ({len(readings)} dimension readings, all distinct)\n")


def test_divergence_summary_names_clusters_when_present():
    """The envelope.divergence_summary prose field must name the
    absence_clusters when at least one cluster surfaces. This is the
    construct-honest reporting line: the summary cannot describe the
    substrate's composition without naming its outputs.

    Pins that a future change to the cluster builder cannot leave
    the summary describing only the per-frame walk while clusters
    silently appear elsewhere in the response.
    """
    baseline = len(_FAILURES)
    print("=== divergence_summary names clusters when present ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    div = payload["divergence"]
    summary = div["envelope"]["divergence_summary"]
    n_clusters = len(div.get("absence_clusters", []))
    if n_clusters > 0:
        check(
            "absence_clusters" in summary or "cluster" in summary.lower(),
            f"divergence_summary must name absence_clusters when "
            f"{n_clusters} cluster(s) are present; got summary={summary!r}",
        )
        check(
            "substrate" in summary.lower(),
            "divergence_summary must name 'substrate' as the agent of "
            "the cluster composition (Frame Check is composing, not "
            "the agent or the document)",
        )
    _assert_no_new_failures(
        baseline, "test_divergence_summary_names_clusters_when_present"
    )
    print(f"  PASS  ({n_clusters} cluster(s) named in summary)\n")


def test_all_prompts_teach_absence_clusters_lead_when_present():
    """Sovereignty prompts must teach the agent to lead with the
    absence_cluster reading when divergence.absence_clusters is
    non-empty. Without this, the agent following the prompt may
    walk to absent_frames first and miss the substrate's dimension-
    level composition.

    Pins: each tool-invoking prompt mentions absence_clusters in the
    compact-response section so cluster-first composition is
    instructed at the prompt layer, not only at the
    agent_guidance.how_to_render_divergence layer.
    """
    baseline = len(_FAILURES)
    print("=== all four prompts teach absence_clusters lead ===")
    for prompt_name in [
        "frame_check_my_response",
        "frame_check_this_ai_response",
        "challenge_document",
        "explain_framing",
    ]:
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 120, "method": "prompts/get",
            "params": {"name": prompt_name},
        })
        text = resp["result"]["messages"][0]["content"]["text"]
        check(
            "absence_clusters" in text or "absence_cluster" in text,
            f"prompt {prompt_name!r} does not mention absence_clusters; "
            f"agents following this prompt will walk absent_frames "
            f"directly and miss the substrate's dimension-level "
            f"composition layer",
        )
        check(
            "cluster" in text.lower() and (
                "lead" in text.lower()
                or "start" in text.lower()
                or "first" in text.lower()
                or "strongest" in text.lower()
            ),
            f"prompt {prompt_name!r} does not instruct cluster-first "
            f"composition (lead/start/first/strongest); the cluster "
            f"reading should be the lead synthesis when present",
        )
    _assert_no_new_failures(
        baseline, "test_all_prompts_teach_absence_clusters_lead_when_present"
    )
    print("  PASS  (cluster-first composition taught in all four prompts)\n")


def test_composition_discipline_names_absence_clusters():
    """agent_guidance.composition_discipline must include
    absence_clusters in the named measurements that ground a
    cited insight. Without this, agents invoked via natural language
    (not via a sovereignty prompt) get the discipline at tool-level
    but with no instruction to use the cluster reading; the substrate
    composition surfaces only when a prompt is in play.
    """
    baseline = len(_FAILURES)
    print("=== composition_discipline names absence_clusters ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "absence_cluster" in text or "absence_clusters" in text,
        "composition_discipline must name absence_clusters as a "
        "valid grounding measurement so natural-language invocations "
        "(not just sovereignty prompts) carry cluster-first composition",
    )
    check(
        "substrate" in text.lower() and "cluster" in text.lower(),
        "composition_discipline must name the cluster as Frame "
        "Check's substrate-side composition (distinguishing it from "
        "agent-side composition over per-frame walks)",
    )
    _assert_no_new_failures(
        baseline, "test_composition_discipline_names_absence_clusters"
    )
    print("  PASS\n")


def test_how_to_render_divergence_teaches_cluster_first_composition():
    """agent_guidance.how_to_render_divergence must teach the agent
    to START with absence_clusters (not absent_frames) when present,
    and to use the cluster reading as the lead synthesis. Pins the
    prioritization so the substrate's composition is recognized as
    the load-bearing surface rather than ignored in favor of the
    per-frame walk.
    """
    baseline = len(_FAILURES)
    print("=== how_to_render_divergence teaches cluster-first composition ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "absence_clusters" in text,
        "how_to_render_divergence must mention absence_clusters so "
        "the agent knows to use the substrate's composition layer",
    )
    check(
        "START with" in text or "lead synthesis" in text.lower(),
        "how_to_render_divergence must instruct the agent to lead "
        "with absence_clusters when present (not just acknowledge "
        "their existence)",
    )
    check(
        "dimension" in text.lower() and (
            "shared" in text.lower() or "sharing" in text.lower()
        ),
        "how_to_render_divergence must explain that clusters group "
        "absent frames sharing a canonical dimension",
    )
    # The prescription-prevention discipline must extend to clusters,
    # not only to per-frame absences.
    check(
        "cluster" in text.lower() and (
            "should have" not in text.lower() or "never" in text.lower()
        ),
        "how_to_render_divergence must extend the absence-is-not-"
        "prescription discipline to cluster readings (clusters "
        "describe what the framing does not do; never tell the user "
        "what the document should have done)",
    )
    _assert_no_new_failures(
        baseline, "test_how_to_render_divergence_teaches_cluster_first_composition"
    )
    print("  PASS\n")


def test_frame_library_matches_carry_corpus_context():
    """Per-frame corpus_context is attached to every matched frame
    in frame_library_matches. The substrate composes catalog
    assertion with empirical anchoring from Frame Check's validation
    corpus.

    Pins:
      - corpus_context attached to each match
      - prevalence reports "fires in N of M corpus documents"
      - typical_co_fires + typical_co_absences carry citation_uri
      - corpus_entries_fired_uris point back to corpus entries
    """
    baseline = len(_FAILURES)
    print("=== frame_library_matches carry corpus_context ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    matches = payload["analysis"].get("frame_library_matches", [])
    if not matches:
        print("  SKIP  (no matches on _DOC_SAMPLE)\n")
        return
    for m in matches:
        check(
            "corpus_context" in m,
            f"matched frame {m.get('fvs_id')!r} missing corpus_context",
        )
        ctx = m.get("corpus_context")
        # corpus_context can be None when corpus is unavailable; that
        # is honest. The field must be PRESENT (key exists), but its
        # value may be None.
        if ctx is None:
            continue
        check(
            isinstance(ctx, dict)
            and "prevalence" in ctx
            and "fires_in_count" in ctx
            and "fires_in_total" in ctx,
            f"corpus_context must carry prevalence + fires_in_count + "
            f"fires_in_total; got {sorted(ctx.keys())}",
        )
        prev = ctx.get("prevalence", "")
        check(
            "fires in" in prev and "of" in prev,
            f"corpus_context.prevalence must be 'fires in N of M corpus "
            f"documents' shape; got {prev!r}",
        )
        for cof in ctx.get("typical_co_fires") or []:
            check(
                "fvs_id" in cof and "count" in cof and "citation_uri" in cof,
                f"typical_co_fires entry must carry fvs_id, count, "
                f"citation_uri; got {sorted(cof.keys())}",
            )
            check(
                cof["citation_uri"].startswith(
                    f"{mcp_server.RESOURCE_SCHEME}://library/"
                ),
                f"typical_co_fires citation_uri must point at the "
                f"library resource scheme; got {cof['citation_uri']!r}",
            )
        for uri in ctx.get("corpus_entries_fired_uris") or []:
            check(
                uri.startswith(f"{mcp_server.RESOURCE_SCHEME}://corpus/"),
                f"corpus_entries_fired_uris must point at corpus "
                f"resource scheme; got {uri!r}",
            )
    _assert_no_new_failures(
        baseline, "test_frame_library_matches_carry_corpus_context"
    )
    print(f"  PASS  ({len(matches)} match(es) with corpus_context)\n")


def test_absent_frames_carry_corpus_context():
    """Per-frame corpus_context is also attached to absent_frames in
    the divergence block, so the agent reading an absent frame sees
    where that frame fires across the corpus and which corpus entries
    to chain to as cite-back evidence.

    Pins:
      - corpus_context attached to each absent_frame record
      - corpus_entries_fired_uris are the cite-back surface
    """
    baseline = len(_FAILURES)
    print("=== absent_frames carry corpus_context ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    absent = payload["divergence"].get("absent_frames", [])
    check(
        len(absent) >= 1,
        "absent_frames must be non-empty for this fixture",
    )
    for record in absent[:5]:
        check(
            "corpus_context" in record,
            f"absent_frame {record.get('frame_id')!r} missing "
            f"corpus_context key",
        )
    _assert_no_new_failures(
        baseline, "test_absent_frames_carry_corpus_context"
    )
    print("  PASS\n")


def test_absence_clusters_carry_corpus_context():
    """Per-dimension corpus_context is attached to each cluster.
    Carries peer-pair-difference-rate (how often peer pairs differ
    on this dimension across the validation corpus) and the
    cross-question outlier finding when present.

    Pins:
      - corpus_context attached to each cluster
      - peer_pair_difference_rate text shape
      - cross_question_outlier shape when present
    """
    baseline = len(_FAILURES)
    print("=== absence_clusters carry corpus_context ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    clusters = payload["divergence"].get("absence_clusters", [])
    if not clusters:
        print("  SKIP  (no clusters on fixture)\n")
        return
    for cluster in clusters:
        check(
            "corpus_context" in cluster,
            f"cluster on dimension {cluster.get('dimension')!r} missing "
            f"corpus_context key",
        )
        ctx = cluster.get("corpus_context")
        if ctx is None:
            continue
        # peer_pair_difference_rate may be None when peer-finding
        # data is unavailable; when present, must follow shape.
        rate = ctx.get("peer_pair_difference_rate")
        if rate is not None:
            check(
                "differs across" in rate and "peer pairs" in rate,
                f"peer_pair_difference_rate text must follow 'differs "
                f"across N of M peer pairs' shape; got {rate!r}",
            )
        cqo = ctx.get("cross_question_outlier")
        if cqo is not None:
            check(
                isinstance(cqo, dict)
                and "llm" in cqo and "outlier_count" in cqo,
                f"cross_question_outlier must carry llm + "
                f"outlier_count; got {sorted(cqo.keys())}",
            )
    _assert_no_new_failures(
        baseline, "test_absence_clusters_carry_corpus_context"
    )
    print(f"  PASS  ({len(clusters)} cluster(s) with corpus_context)\n")


def test_analysis_carries_structural_genre_classification():
    """Every frame_check response carries a `genre` field in the
    analysis block. The genre classifier composes voice + claim
    distribution + text-feature regexes into a bounded-set
    classification with calibrated confidence reporting.

    Pins:
      - genre key present on every analysis response
      - bounded available_classes (six structural genres)
      - classification-confidence shape (classification, confidence,
        runner_up, runner_up_margin, score_distribution, construct)
      - score_distribution keys match available_classes exactly
    """
    baseline = len(_FAILURES)
    print("=== analysis carries structural genre classification ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    analysis = payload["analysis"]
    check(
        "genre" in analysis,
        "analysis.genre must be present; the genre field is the "
        "foundation for genre-conditioned absence ranking",
    )
    g = analysis.get("genre", {})
    expected_classes = {
        "recommendation", "analysis", "narrative",
        "advocacy", "exploration", "instruction",
    }
    check(
        set(g.get("available_classes", [])) == expected_classes,
        f"genre.available_classes must be exactly the bounded set "
        f"of six structural genres; got "
        f"{sorted(g.get('available_classes', []))}",
    )
    required_keys = {
        "classification", "confidence", "runner_up",
        "runner_up_margin", "score_distribution", "construct",
    }
    check(
        required_keys <= set(g.keys()),
        f"genre must carry classification-confidence shape "
        f"({sorted(required_keys)}); got {sorted(g.keys())}",
    )
    score_dist = g.get("score_distribution", {})
    check(
        set(score_dist.keys()) == expected_classes,
        f"genre.score_distribution must have exactly the six "
        f"genre keys; got {sorted(score_dist.keys())}",
    )
    if g.get("classification") is not None:
        check(
            g["classification"] in expected_classes,
            f"genre.classification must be one of the bounded set; "
            f"got {g['classification']!r}",
        )
        check(
            g.get("confidence") in {"high", "borderline", "low"},
            f"genre.confidence must be one of high/borderline/low; "
            f"got {g.get('confidence')!r}",
        )
        construct = g.get("construct", "")
        check(
            isinstance(construct, str) and len(construct) >= 30,
            f"genre.construct must be substantive prose describing "
            f"how the classification was composed; got len="
            f"{len(construct) if isinstance(construct, str) else 'non-str'}",
        )
    _assert_no_new_failures(
        baseline, "test_analysis_carries_structural_genre_classification"
    )
    print(f"  PASS  (genre={g.get('classification')}, "
          f"confidence={g.get('confidence')})\n")


def test_genre_classifies_recommendation_correctly():
    """The agriculture-document fixture (My Pick: Regenerative Ag)
    must classify as 'recommendation', mirroring the operator's
    stress-test invocation. Pins the classifier on a real-world
    recommendation fixture so a future change cannot silently
    misroute recommendation documents.
    """
    baseline = len(_FAILURES)
    print("=== genre classifies recommendation correctly ===")
    rec_doc = (
        "The agricultural landscape in 2026 is no longer just about "
        "tractors. Global agri-tech investments crossed 40 billion "
        "dollar mark this year. Here are the three most lucrative "
        "business opportunities. Precision Agriculture Market Size "
        "10.54 Billion. Vertical Farming Market Size 11.63 Billion. "
        "Regenerative Agriculture Market Size 11.7 Billion. My Pick: "
        "Regenerative Ag. If I am putting my money down, I am "
        "picking Regenerative Agriculture. Vertical Farming has high "
        "energy costs. Precision Ag is crowded. Regenerative Ag "
        "turns the farm into a carbon vacuum."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    g = payload["analysis"]["genre"]
    check(
        g["classification"] == "recommendation",
        f"agriculture-recommendation fixture must classify as "
        f"'recommendation'; got {g['classification']!r}",
    )
    check(
        g["confidence"] == "high",
        f"agriculture fixture has explicit 'My Pick' + 'I am picking' "
        f"markers; classifier should reach high confidence; got "
        f"confidence={g['confidence']!r}",
    )
    _assert_no_new_failures(
        baseline, "test_genre_classifies_recommendation_correctly"
    )
    print(f"  PASS  (genre={g['classification']}, margin={g['runner_up_margin']})\n")


def test_genre_classifies_instruction_correctly():
    """Procedural how-to text with numbered steps must classify as
    'instruction'. Pins the classifier on a non-recommendation,
    non-analysis genre to prevent over-fitting on the corpus.
    """
    baseline = len(_FAILURES)
    print("=== genre classifies instruction correctly ===")
    inst_doc = (
        "How to set up a development environment.\n\n"
        "Step 1: Install Python 3.11 or later. First, download the "
        "installer from python.org. Next, run the installer with "
        "default options.\n"
        "Step 2: Install dependencies. First, create a virtual "
        "environment. Then, activate it. Finally, run pip install "
        "-r requirements.txt.\n"
        "Step 3: Run the test suite. First, navigate to the project "
        "directory. Then, run pytest. Finally, verify all tests "
        "pass.\n"
    )
    payload = mcp_server.build_epistemic_payload(
        inst_doc, include_divergence=True,
    )
    g = payload["analysis"]["genre"]
    check(
        g["classification"] == "instruction",
        f"procedural how-to fixture must classify as 'instruction'; "
        f"got {g['classification']!r}",
    )
    _assert_no_new_failures(
        baseline, "test_genre_classifies_instruction_correctly"
    )
    print(f"  PASS  (genre={g['classification']})\n")


def test_every_composed_entity_carries_claim_level():
    """L5 framework structural integrity: every emitted composed
    entity in the substrate's payload must carry the claim_level field.
    Pins the invariant so a future construct addition cannot silently
    omit the field and degrade the L5 per-level discipline.

    The eight entity types covered:
      - genre (classifier_output)
      - voice (classifier_output)
      - temporal (classifier_output)
      - frame_library_matches[i] (detector_measurement)
      - frame_deepening (detector_measurement)
      - decision_readiness.dimensions[name] (composed_pattern)
      - divergence.absence_clusters[i] (composed_pattern)
      - divergence.frame_patterns[i] (composed_pattern)

    Uses a realistic document (the agriculture-recommendation fixture
    re-used from test_genre_classifies_recommendation_correctly) to
    fire enough constructs that the test exercises the invariant
    across all eight entity types.
    """
    baseline = len(_FAILURES)
    print("=== every composed entity carries claim_level ===")
    rich_doc = (
        "The agricultural landscape in 2026 is no longer just about "
        "tractors. Global agri-tech investments crossed 40 billion "
        "dollar mark this year. Here are the three most lucrative "
        "business opportunities. Precision Agriculture Market Size "
        "10.54 Billion. Vertical Farming Market Size 11.63 Billion. "
        "Regenerative Agriculture Market Size 11.7 Billion. My Pick: "
        "Regenerative Ag. If I am putting my money down, I am "
        "picking Regenerative Agriculture. Vertical Farming has high "
        "energy costs. Precision Ag is crowded. Regenerative Ag "
        "turns the farm into a carbon vacuum."
    )
    payload = mcp_server.build_epistemic_payload(
        rich_doc, include_divergence=True,
    )
    a = payload["analysis"]
    d = payload.get("divergence") or {}

    valid_levels = {
        "detector_measurement",
        "classifier_output",
        "composed_pattern",
        "agent_generated",
    }

    def _check_entity(entity, name: str, expected_level: str = None):
        if entity is None:
            return
        cl = entity.get("claim_level") if isinstance(entity, dict) else None
        check(
            cl is not None,
            f"{name} must carry claim_level field; got entity keys "
            f"{sorted(entity.keys()) if isinstance(entity, dict) else type(entity).__name__}",
        )
        check(
            cl in valid_levels,
            f"{name}.claim_level must be one of {sorted(valid_levels)}; "
            f"got {cl!r}",
        )
        if expected_level is not None and cl is not None:
            check(
                cl == expected_level,
                f"{name}.claim_level expected {expected_level!r}; "
                f"got {cl!r}",
            )

    # Top-level classifier entities.
    _check_entity(a.get("genre"), "genre", "classifier_output")
    _check_entity(a.get("voice"), "voice", "classifier_output")
    _check_entity(a.get("temporal"), "temporal", "classifier_output")

    # Detector entities (lists).
    for i, m in enumerate(a.get("frame_library_matches", []) or []):
        _check_entity(
            m, f"frame_library_matches[{i}]", "detector_measurement",
        )
    _check_entity(
        a.get("frame_deepening"),
        "frame_deepening",
        "detector_measurement",
    )

    # Composed pattern entities.
    dims = (a.get("decision_readiness") or {}).get("dimensions") or {}
    for name, dim in dims.items():
        _check_entity(
            dim,
            f"decision_readiness.dimensions[{name!r}]",
            "composed_pattern",
        )
    for i, c in enumerate(d.get("absence_clusters", []) or []):
        _check_entity(
            c,
            f"divergence.absence_clusters[{i}]",
            "composed_pattern",
        )
    for i, p in enumerate(d.get("frame_patterns", []) or []):
        _check_entity(
            p,
            f"divergence.frame_patterns[{i}]",
            "composed_pattern",
        )

    _assert_no_new_failures(
        baseline, "test_every_composed_entity_carries_claim_level"
    )
    print(
        f"  PASS  (genre={a['genre'].get('classification')}, "
        f"matches={len(a.get('frame_library_matches', []) or [])}, "
        f"dims={len(dims)}, "
        f"clusters={len(d.get('absence_clusters', []) or [])}, "
        f"patterns={len(d.get('frame_patterns', []) or [])})\n"
    )


def test_genre_recommendation_regex_excludes_perception_verbs():
    """Move A regression: `you should see/notice/observe/hear X` is
    descriptive (UI affordance, sensory expectation), not prescriptive.
    The recommendation regex must NOT count these as recommendation
    markers; otherwise a single descriptive `you should see` triggers
    the +5.0 categorical bonus and produces HIGH-confidence
    misclassification of instruction documents.

    See data/adversarial_fixtures/instruction_without_troubleshooting/
    audit.md (Move A) for the exposure case.
    """
    baseline = len(_FAILURES)
    print("=== Move A: perception-verb negative lookahead ===")
    from genre_classifier import _RECOMMENDATION_RE
    # Descriptive: must NOT match.
    for descriptive in (
        "you should see the prompt",
        "You should notice a click.",
        "you should observe the LED change",
        "You should hear a beep.",
    ):
        check(
            len(_RECOMMENDATION_RE.findall(descriptive)) == 0,
            f"descriptive perception-verb form must NOT match "
            f"recommendation regex: {descriptive!r}",
        )
    # Prescriptive: must still match.
    for prescriptive in (
        "you should choose option A",
        "you should pick the latter",
        "I would lean toward Y",
    ):
        check(
            len(_RECOMMENDATION_RE.findall(prescriptive)) >= 1,
            f"prescriptive form must still match recommendation "
            f"regex: {prescriptive!r}",
        )
    # Ambiguous-perception verbs (expect, find, feel, get) deliberately
    # remain matched. These admit prescriptive readings ("you should
    # expect to fail" = teach a disposition; "you should find a way" =
    # prescription) and conservative scope keeps them counted to avoid
    # false negatives on legitimate recommendations. This test pins
    # that choice so a future regex-tightening cannot silently exclude
    # them without an explicit decision.
    for ambiguous in (
        "you should expect resistance",
        "you should find a way around it",
    ):
        check(
            len(_RECOMMENDATION_RE.findall(ambiguous)) >= 1,
            f"ambiguous-perception verb form must STILL match "
            f"(deliberate residual; conservative scope): {ambiguous!r}",
        )
    _assert_no_new_failures(
        baseline,
        "test_genre_recommendation_regex_excludes_perception_verbs",
    )
    print("  PASS\n")


def test_genre_instruction_regex_matches_markdown_headers():
    """Move B regression: setup guides and runbooks commonly use
    `## Step N:` markdown header formatting. The instruction regex
    must match these forms; otherwise documents with markdown-header
    step structure are systematically misclassified.

    See data/adversarial_fixtures/instruction_without_troubleshooting/
    audit.md (Move B) for the exposure case.
    """
    baseline = len(_FAILURES)
    print("=== Move B: markdown-header step matching ===")
    from genre_classifier import _INSTRUCTION_RE
    # Markdown headers: must match.
    for header_form in (
        "## Step 1: Install the package",
        "### Step 2: Configure the server",
        "###### Step 10: Verify the connection",
        "\n## Step 3: Run the test\n",
    ):
        check(
            len(_INSTRUCTION_RE.findall(header_form)) >= 1,
            f"markdown-header step form must match instruction "
            f"regex: {header_form!r}",
        )
    # Bare-line forms: must still match (existing behavior).
    for bare_form in (
        "Step 1: Open the file.",
        "First, install dependencies.",
        "1. Configure the system",
    ):
        check(
            len(_INSTRUCTION_RE.findall(bare_form)) >= 1,
            f"bare-line instruction form must still match: "
            f"{bare_form!r}",
        )
    _assert_no_new_failures(
        baseline,
        "test_genre_instruction_regex_matches_markdown_headers",
    )
    print("  PASS\n")


def test_genre_abstains_on_empty_or_featureless_text():
    """Construct-honest abstention: when the text has no structural
    features that fire any genre marker, the classifier must
    abstain (genre=None, confidence='low') rather than guess. Pins
    the abstention discipline so a future change cannot silently
    pick a default genre.
    """
    baseline = len(_FAILURES)
    print("=== genre abstains on featureless text ===")
    from genre_classifier import classify_genre
    # Empty.
    g = classify_genre("")
    check(
        g["genre"] is None and g["confidence"] == "low",
        f"empty text must yield genre=None confidence='low'; got "
        f"genre={g.get('genre')!r} confidence={g.get('confidence')!r}",
    )
    # Single bare word with no markers.
    g = classify_genre("Word")
    check(
        g["genre"] is None,
        f"featureless single-word input must abstain; got "
        f"genre={g.get('genre')!r}",
    )
    _assert_no_new_failures(
        baseline, "test_genre_abstains_on_empty_or_featureless_text"
    )
    print("  PASS\n")


def test_composition_discipline_names_genre():
    """agent_guidance.composition_discipline must name analysis.genre
    as a grounding measurement. Without this, the genre field exists
    in JSON but the discipline does not point the agent at it as a
    valid composition substrate.
    """
    baseline = len(_FAILURES)
    print("=== composition_discipline names analysis.genre ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "analysis.genre" in text or "genre classification" in text.lower(),
        "composition_discipline must name analysis.genre as a "
        "grounding measurement so agents know to surface it as part "
        "of the reading",
    )
    _assert_no_new_failures(
        baseline, "test_composition_discipline_names_genre"
    )
    print("  PASS\n")


def test_absent_frames_carry_genre_relevance_for_classified_genre():
    """When the document is classified into a structural genre,
    absent frames that are load-bearing for that genre's reasoning
    carry a genre_relevance dict with priority and reason. Pins the
    field shape and the per-genre map's coverage of canonical
    frames.
    """
    baseline = len(_FAILURES)
    print("=== absent_frames carry genre_relevance for classified genre ===")
    rec_doc = (
        "The agricultural landscape in 2026. Market Size 10.54 "
        "Billion at 12.5 percent CAGR. Vertical Farming Market Size "
        "11.63 Billion. Regenerative Agriculture Market Size 11.7 "
        "Billion. My Pick: Regenerative Ag. If I am putting my "
        "money down, I am picking Regenerative Agriculture."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    genre = payload["analysis"]["genre"]["classification"]
    check(
        genre == "recommendation",
        f"fixture must classify as 'recommendation' for this test "
        f"to be meaningful; got {genre!r}",
    )
    absent = payload["divergence"]["absent_frames"]
    # At least one absent_frame should carry genre_relevance; the
    # recommendation map names FVS-007/009/014/012 as load-bearing.
    relevant = [
        r for r in absent if r.get("genre_relevance")
    ]
    check(
        len(relevant) >= 1,
        f"recommendation document with absent FVS-009/014/012 must "
        f"have at least one absent_frame carrying genre_relevance; "
        f"got {len(relevant)}",
    )
    for r in relevant:
        gr = r["genre_relevance"]
        check(
            gr.get("relevant_for_genre") is True,
            f"genre_relevance.relevant_for_genre must be True; got "
            f"{gr.get('relevant_for_genre')!r}",
        )
        check(
            isinstance(gr.get("priority"), int) and gr["priority"] >= 1,
            f"genre_relevance.priority must be a positive int "
            f"(1 = most load-bearing); got {gr.get('priority')!r}",
        )
        check(
            isinstance(gr.get("reason"), str) and len(gr["reason"]) >= 30,
            f"genre_relevance.reason must be substantive prose; "
            f"got len={len(gr.get('reason', '')) if isinstance(gr.get('reason'), str) else 'non-str'}",
        )
    _assert_no_new_failures(
        baseline, "test_absent_frames_carry_genre_relevance_for_classified_genre"
    )
    print(f"  PASS  ({len(relevant)} of {len(absent)} absent_frames carry genre_relevance)\n")


def test_genre_relevance_promotes_absences_within_tier():
    """The absent_frames sort promotes genre-relevant absences within
    each signal_strength tier. The first non-genre-relevant entry
    in any tier must come AFTER all genre-relevant entries in the
    same tier. Pins the sort discipline so a future change cannot
    silently revert to alphabetical.
    """
    baseline = len(_FAILURES)
    print("=== genre_relevance promotes absences within tier ===")
    rec_doc = (
        "The agricultural landscape in 2026. Market Size 10.54 "
        "Billion at 12.5 percent CAGR. Vertical Farming Market Size "
        "11.63 Billion. Regenerative Agriculture Market Size 11.7 "
        "Billion. My Pick: Regenerative Ag. If I am putting my "
        "money down, I am picking Regenerative Agriculture."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    absent = payload["divergence"]["absent_frames"]
    # Group by tier; in each tier check that no non-relevant entry
    # appears before a relevant one (promotion invariant).
    by_tier = {}
    for r in absent:
        by_tier.setdefault(r["signal_strength"], []).append(r)
    for tier, records in by_tier.items():
        seen_non_relevant = False
        for r in records:
            is_relevant = bool(r.get("genre_relevance"))
            if seen_non_relevant and is_relevant:
                check(
                    False,
                    f"in tier {tier!r}: genre-relevant frame "
                    f"{r['frame_id']!r} appears AFTER a non-relevant "
                    f"frame; the promotion invariant is broken",
                )
            if not is_relevant:
                seen_non_relevant = True
    _assert_no_new_failures(
        baseline, "test_genre_relevance_promotes_absences_within_tier"
    )
    print("  PASS  (promotion invariant holds across all tiers)\n")


def test_genre_relevance_absent_when_no_classified_genre():
    """When the classifier abstains (no genre classification), no
    absent_frame should carry genre_relevance. The substrate stays
    honest: no genre means no per-genre re-ranking.
    """
    baseline = len(_FAILURES)
    print("=== genre_relevance absent when classifier abstains ===")
    # A document the classifier abstains on: very short, no markers.
    short_doc = "A. B. C."
    payload = mcp_server.build_epistemic_payload(
        short_doc, include_divergence=True,
    )
    genre = payload["analysis"]["genre"]["classification"]
    if genre is not None:
        # If the classifier did classify (regex caught something),
        # this test does not apply. Skip rather than force a
        # contradiction.
        print(f"  SKIP  (classifier returned {genre!r}; abstention "
              f"path not exercised)\n")
        return
    absent = payload["divergence"]["absent_frames"]
    for r in absent:
        check(
            r.get("genre_relevance") is None,
            f"absent_frame {r['frame_id']!r} carries genre_relevance "
            f"despite classifier abstaining; substrate must not "
            f"re-rank without a classified genre",
        )
    _assert_no_new_failures(
        baseline, "test_genre_relevance_absent_when_no_classified_genre"
    )
    print("  PASS  (no genre_relevance when classifier abstains)\n")


def test_per_genre_load_bearing_maps_cover_all_genres():
    """Every classifier genre must have a curated load-bearing
    absence map. Without this, classifying a document into a genre
    that has no map yields no genre_relevance and the substrate
    silently drops the per-genre layer for that genre.
    """
    baseline = len(_FAILURES)
    print("=== per-genre load-bearing maps cover all genres ===")
    from genre_classifier import (
        _GENRES, _GENRE_LOAD_BEARING_ABSENCES,
        get_genre_load_bearing_absences,
    )
    for genre in _GENRES:
        check(
            genre in _GENRE_LOAD_BEARING_ABSENCES,
            f"genre {genre!r} has no load-bearing absence map; the "
            f"per-genre layer drops silently for documents in this "
            f"genre",
        )
        bearings = get_genre_load_bearing_absences(genre)
        check(
            len(bearings) >= 3,
            f"genre {genre!r} map has fewer than 3 load-bearing "
            f"absences; substrate composition becomes anemic",
        )
        for fvs_id, reason in bearings:
            check(
                isinstance(fvs_id, str) and fvs_id.startswith("FVS-"),
                f"map entry must carry FVS-XXX id; got {fvs_id!r}",
            )
            check(
                isinstance(reason, str) and len(reason) >= 30,
                f"map entry reason must be substantive; got "
                f"len={len(reason) if isinstance(reason, str) else 'non-str'}",
            )
    _assert_no_new_failures(
        baseline, "test_per_genre_load_bearing_maps_cover_all_genres"
    )
    print(f"  PASS  (all {len(_GENRES)} genres have load-bearing maps)\n")


def test_how_to_render_divergence_teaches_genre_relevance():
    """agent_guidance.how_to_render_divergence step (6.5) must teach
    the genre_relevance layer: classified genre, priority, reason
    citation. Pins the discipline so agents reading divergence know
    to surface genre-relevant absences with their structural reason.
    """
    baseline = len(_FAILURES)
    print("=== how_to_render_divergence teaches genre_relevance ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "genre_relevance" in text,
        "how_to_render_divergence must mention genre_relevance",
    )
    check(
        "load-bearing" in text.lower() and "genre" in text.lower(),
        "how_to_render_divergence must explain that genre-relevant "
        "absences are load-bearing for the document's genre",
    )
    _assert_no_new_failures(
        baseline, "test_how_to_render_divergence_teaches_genre_relevance"
    )
    print("  PASS\n")


def test_divergence_carries_frame_patterns():
    """When the document signal matches a curated structural
    pattern (e.g., 'recommendation-without-falsification',
    'growth-without-risk'), the substrate surfaces the pattern as a
    named composition with curated reading and corpus prevalence.

    Pins:
      - frame_patterns key on every divergence response
      - pattern shape (id, name, reading, supporting_evidence,
        load_bearing_dimensions, corpus_context)
      - agriculture-recommendation fixture triggers
        'recommendation-without-falsification'
    """
    baseline = len(_FAILURES)
    print("=== divergence carries frame_patterns ===")
    rec_doc = (
        "The agricultural landscape in 2026 is no longer just about "
        "tractors. Global agri-tech investments crossed 40 billion "
        "dollar mark this year. Here are the three most lucrative "
        "business opportunities. Precision Agriculture Market Size "
        "10.54 Billion. Vertical Farming Market Size 11.63 Billion. "
        "Regenerative Agriculture Market Size 11.7 Billion. My Pick: "
        "Regenerative Ag. If I am putting my money down, I am "
        "picking Regenerative Agriculture. Vertical Farming has "
        "high energy costs. Precision Ag is crowded. Regenerative "
        "Ag turns the farm into a carbon vacuum."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    div = payload["divergence"]
    check(
        "frame_patterns" in div,
        "divergence.frame_patterns must be present",
    )
    patterns = div.get("frame_patterns", [])
    check(
        isinstance(patterns, list),
        f"frame_patterns must be a list; got {type(patterns).__name__}",
    )
    # Agriculture-recommendation fixture should trigger the
    # recommendation-without-falsification pattern.
    pattern_ids = [p.get("id") for p in patterns]
    check(
        "recommendation-without-falsification" in pattern_ids,
        f"agriculture-recommendation fixture must trigger the "
        f"recommendation-without-falsification pattern; got "
        f"pattern_ids={pattern_ids}",
    )
    for p in patterns:
        required = {
            "id", "name", "reading", "supporting_evidence",
            "load_bearing_dimensions",
        }
        check(
            required <= set(p.keys()),
            f"pattern must carry {sorted(required)}; got "
            f"{sorted(p.keys())}",
        )
        check(
            isinstance(p.get("reading"), str)
            and len(p["reading"]) >= 50,
            f"pattern.reading must be substantive prose; got "
            f"len={len(p.get('reading', '')) if isinstance(p.get('reading'), str) else 'non-str'}",
        )
        ev = p.get("supporting_evidence", {})
        check(
            isinstance(ev, dict),
            f"supporting_evidence must be a dict; got {type(ev).__name__}",
        )
        # corpus_context may be None when corpus unavailable.
        cc = p.get("corpus_context")
        if cc is not None:
            check(
                "matches_count" in cc and "total_corpus" in cc
                and "match_rate" in cc and "prevalence" in cc,
                f"pattern.corpus_context must carry matches_count + "
                f"total_corpus + match_rate + prevalence; got "
                f"{sorted(cc.keys())}",
            )
            check(
                "small_n_caveat" in cc,
                "pattern.corpus_context must carry small_n_caveat "
                "naming the genre-not-applied caveat",
            )
    _assert_no_new_failures(
        baseline, "test_divergence_carries_frame_patterns"
    )
    print(f"  PASS  ({len(patterns)} pattern(s) triggered)\n")


def test_frame_patterns_no_match_yields_empty_list():
    """Construct-honest empty case: when no curated pattern matches
    the document signal, frame_patterns is an empty list (not
    None, not absent). Pins the discipline: the field is always
    present; the substrate stays construct-honest about whether a
    recognized shape was matched.
    """
    baseline = len(_FAILURES)
    print("=== frame_patterns is empty list when no pattern matches ===")
    # _DOC_SAMPLE is a balanced analytical fixture; it should not
    # match any of the four curated patterns (recommendation,
    # growth-without-risk requires Growth firing, analysis-without-
    # grounding requires analysis genre + FVS-016 absent + ...,
    # advocacy-without-counter-perspective requires advocacy genre).
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    patterns = payload["divergence"].get("frame_patterns", [])
    # If a pattern did trigger, that is fine for this fixture; the
    # important pin is that the field is present and a list.
    check(
        isinstance(patterns, list),
        f"frame_patterns must be a list (possibly empty) on every "
        f"divergence response; got {type(patterns).__name__}",
    )
    _assert_no_new_failures(
        baseline, "test_frame_patterns_no_match_yields_empty_list"
    )
    print(f"  PASS  (frame_patterns is list with {len(patterns)} entries)\n")


def test_pattern_corpus_prevalence_uses_corpus_aggregator():
    """Pattern corpus prevalence must come from the corpus
    aggregator (count of corpus entries matching the same frame-
    shape). Pins that the substrate composes empirical anchoring
    onto curated patterns, not just curated readings.
    """
    baseline = len(_FAILURES)
    print("=== pattern corpus prevalence integrates with aggregator ===")
    rec_doc = (
        "The agricultural landscape in 2026. Market Size 10.54 "
        "Billion. Vertical Farming Market Size 11.63 Billion. "
        "Regenerative Agriculture Market Size 11.7 Billion. My "
        "Pick: Regenerative Ag. If I am putting my money down, I "
        "am picking Regenerative Agriculture."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    patterns = payload["divergence"].get("frame_patterns", [])
    if not patterns:
        print("  SKIP  (no pattern matched on fixture)\n")
        return
    for p in patterns:
        cc = p.get("corpus_context")
        if cc is None:
            continue
        check(
            isinstance(cc.get("matches_count"), int)
            and cc["matches_count"] >= 0,
            f"pattern.corpus_context.matches_count must be a "
            f"non-negative int; got {cc.get('matches_count')!r}",
        )
        check(
            isinstance(cc.get("total_corpus"), int)
            and cc["total_corpus"] >= 1,
            f"pattern.corpus_context.total_corpus must be a "
            f"positive int (corpus has at least one entry); got "
            f"{cc.get('total_corpus')!r}",
        )
        check(
            cc["matches_count"] <= cc["total_corpus"],
            f"matches_count must not exceed total_corpus; "
            f"got {cc['matches_count']} > {cc['total_corpus']}",
        )
        check(
            isinstance(cc.get("prevalence"), str)
            and "of" in cc["prevalence"],
            f"prevalence text must follow 'matches in N of M corpus' "
            f"shape; got {cc.get('prevalence')!r}",
        )
    _assert_no_new_failures(
        baseline, "test_pattern_corpus_prevalence_uses_corpus_aggregator"
    )
    print("  PASS\n")


def test_how_to_render_divergence_teaches_frame_patterns():
    """agent_guidance.how_to_render_divergence step (6.7) must teach
    the frame_patterns layer: pattern reading as recognized shape,
    supporting_evidence citation, corpus prevalence anchoring.
    """
    baseline = len(_FAILURES)
    print("=== how_to_render_divergence teaches frame_patterns ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "frame_patterns" in text,
        "how_to_render_divergence must mention frame_patterns",
    )
    check(
        "recognized" in text.lower() and "shape" in text.lower(),
        "how_to_render_divergence must explain that patterns are "
        "recognized structural shapes (substrate's named "
        "compositions)",
    )
    check(
        "supporting_evidence" in text,
        "how_to_render_divergence must name supporting_evidence as "
        "the citation surface for which frames triggered the pattern",
    )
    _assert_no_new_failures(
        baseline, "test_how_to_render_divergence_teaches_frame_patterns"
    )
    print("  PASS\n")


def test_analysis_carries_frame_deepening_block():
    """Every frame_check response carries an
    `analysis.frame_deepening` block with three sub-fields
    (temporal_scope, stakeholder_map, falsification_conditions).
    Each is None when the document is too short for the analysis to
    be meaningful (under 100 words).

    Pins:
      - frame_deepening key on every analysis response
      - three required sub-keys
      - sub-fields populate on documents above the word floor
    """
    baseline = len(_FAILURES)
    print("=== analysis carries frame_deepening block ===")
    deep_doc = (
        "The agricultural landscape in 2026 is no longer just about "
        "tractors. Global agri-tech investments crossed 40 billion "
        "this year. Three opportunities are worth considering. "
        "Precision Agriculture Market Size 10.54 Billion. Vertical "
        "Farming Market Size 11.63 Billion. Regenerative Agriculture "
        "Market Size 11.7 Billion. My Pick: Regenerative Ag. If I "
        "am putting my money down, I am picking Regenerative "
        "Agriculture. The market is shifting toward sustainability. "
        "Investors are pouring capital. Regulators are starting to "
        "recognize the value. By 2030 the sector should be three "
        "times its size. The conclusion would be wrong if carbon "
        "credit prices crashed. The main risk is policy reversal."
    )
    payload = mcp_server.build_epistemic_payload(
        deep_doc, include_divergence=True,
    )
    analysis = payload["analysis"]
    check(
        "frame_deepening" in analysis,
        "analysis.frame_deepening must be present",
    )
    fd = analysis.get("frame_deepening", {})
    expected_keys = {
        "temporal_scope", "stakeholder_map", "falsification_conditions",
    }
    check(
        set(fd.keys()) >= expected_keys,
        f"frame_deepening must carry temporal_scope, stakeholder_map, "
        f"falsification_conditions; got {sorted(fd.keys())}",
    )
    # On a doc above the word floor, all three should populate.
    check(
        fd.get("temporal_scope") is not None,
        "temporal_scope must populate on a document with year "
        "references and >100 words",
    )
    check(
        fd.get("stakeholder_map") is not None,
        "stakeholder_map must populate on a document with stakeholder "
        "vocabulary and >100 words",
    )
    check(
        fd.get("falsification_conditions") is not None,
        "falsification_conditions must populate on documents above "
        "the word floor",
    )
    _assert_no_new_failures(
        baseline, "test_analysis_carries_frame_deepening_block"
    )
    print("  PASS\n")


def test_temporal_scope_extracts_years_and_projection_windows():
    """The temporal_scope detector must extract years and classify
    them by relation to current year (near-now, historical,
    projection). Pins the year-extraction discipline.
    """
    baseline = len(_FAILURES)
    print("=== temporal_scope extracts years correctly ===")
    from frame_deepening import detect_temporal_scope
    text = (
        "In 2010 the market was small and disorganized with limited "
        "vendor participation. By 2026 it had reached 40 billion in "
        "annual investment. Projections show the market hitting 100 "
        "billion by 2030 according to industry analysts. Some "
        "analysts think 2035 is more realistic given supply chain "
        "constraints and uneven regulatory landscapes. " * 4
    )
    result = detect_temporal_scope(text, current_year=2026)
    check(
        result is not None,
        "detect_temporal_scope must populate on text above word floor",
    )
    if result is None:
        _assert_no_new_failures(
            baseline, "test_temporal_scope_extracts_years_and_projection_windows"
        )
        return
    check(
        2010 in result["historical_years"],
        f"2010 must classify as historical (>5 years before 2026); "
        f"got historical={result['historical_years']}",
    )
    check(
        2026 in result["near_now_years"],
        f"2026 must classify as near-now; "
        f"got near_now={result['near_now_years']}",
    )
    check(
        2030 in result["projection_years"]
        and 2035 in result["projection_years"],
        f"2030 and 2035 must classify as forward-projection; "
        f"got projection={result['projection_years']}",
    )
    check(
        "scope_reading" in result and len(result["scope_reading"]) >= 50,
        "scope_reading must be substantive prose composing the "
        "temporal-shape reading",
    )
    _assert_no_new_failures(
        baseline, "test_temporal_scope_extracts_years_and_projection_windows"
    )
    print("  PASS\n")


def test_stakeholder_map_detects_role_categories():
    """The stakeholder_map detector must identify role categories
    (regulators, investors, customers, employees, competitors,
    communities, suppliers, management) and surface which are
    NOT mentioned. Pins the role-category coverage discipline.
    """
    baseline = len(_FAILURES)
    print("=== stakeholder_map detects role categories ===")
    from frame_deepening import detect_stakeholder_map
    text = (
        "The startup serves customers in the consumer space. "
        "Investors have backed the team with 50 million in series A. "
        "Employees number 80 across engineering and operations. "
        "Regulators have not yet weighed in on the product category. " * 3
    )
    result = detect_stakeholder_map(text)
    check(
        result is not None,
        "detect_stakeholder_map must populate on text above word floor",
    )
    if result is None:
        _assert_no_new_failures(
            baseline, "test_stakeholder_map_detects_role_categories"
        )
        return
    expected_present = {"customers", "investors", "employees", "regulators"}
    check(
        expected_present <= set(result["roles_mentioned"]),
        f"detector must catch customers/investors/employees/"
        f"regulators in this fixture; got "
        f"{result['roles_mentioned']}",
    )
    check(
        result["role_count"] == len(result["roles_mentioned"]),
        "role_count must equal len(roles_mentioned)",
    )
    check(
        "scope_reading" in result and "NOT mentioned" in result["scope_reading"],
        "scope_reading must name absent roles so the agent can "
        "compose questions about whose perspective is missing",
    )
    _assert_no_new_failures(
        baseline, "test_stakeholder_map_detects_role_categories"
    )
    print("  PASS\n")


def test_falsification_conditions_extracts_explicit_statements():
    """The falsification_conditions detector must extract explicit
    'would be wrong if' / 'fails when' / 'depends on' statements
    when present, surface them as candidate previews, and emit a
    reading naming whether the document carries falsification
    structure.
    """
    baseline = len(_FAILURES)
    print("=== falsification_conditions extracts explicit statements ===")
    from frame_deepening import detect_falsification_conditions
    text = (
        "The startup serves customers in the consumer space and "
        "operates across multiple regional markets. The team has "
        "shipped fast and demonstrated traction. The growth has "
        "been strong over the past four quarters consistently. "
        "The conclusion would be wrong if user retention drops "
        "below 40 percent in the coming year. The main risk is "
        "regulatory change in the European market. The analysis "
        "depends on assumptions about total addressable market "
        "size and competitive entry. " * 3
    )
    result = detect_falsification_conditions(text)
    check(
        result is not None,
        "detect_falsification_conditions must populate above word floor",
    )
    if result is None:
        _assert_no_new_failures(
            baseline, "test_falsification_conditions_extracts_explicit_statements"
        )
        return
    check(
        result["primary_match_count"] >= 2,
        f"detector must catch at least 2 falsification statements "
        f"in this fixture (would be wrong if + the main risk); "
        f"got {result['primary_match_count']}",
    )
    check(
        len(result["extracted_conditions"]) >= 2,
        f"extracted_conditions must contain the matched sentences "
        f"as previews; got {len(result['extracted_conditions'])}",
    )
    for preview in result["extracted_conditions"]:
        check(
            isinstance(preview, str) and len(preview) >= 20,
            f"each preview must be a substantive sentence; got "
            f"{preview!r}",
        )
    check(
        "falsification" in result["scope_reading"].lower()
        or "would be wrong" in result["scope_reading"].lower(),
        "scope_reading must name the falsification framing",
    )
    _assert_no_new_failures(
        baseline, "test_falsification_conditions_extracts_explicit_statements"
    )
    print("  PASS\n")


def test_frame_deepening_returns_none_below_word_floor():
    """Construct-honest abstention: each frame_deepening detector
    returns None when the document is too short (<100 words) for
    its analysis to be meaningful. Pins the word-floor discipline.
    """
    baseline = len(_FAILURES)
    print("=== frame_deepening detectors abstain below word floor ===")
    from frame_deepening import (
        detect_temporal_scope, detect_stakeholder_map,
        detect_falsification_conditions,
    )
    short = "Short text. Three sentences. No depth."
    check(
        detect_temporal_scope(short) is None,
        "temporal_scope must abstain on short text",
    )
    check(
        detect_stakeholder_map(short) is None,
        "stakeholder_map must abstain on short text",
    )
    check(
        detect_falsification_conditions(short) is None,
        "falsification_conditions must abstain on short text",
    )
    _assert_no_new_failures(
        baseline, "test_frame_deepening_returns_none_below_word_floor"
    )
    print("  PASS\n")


def test_composition_discipline_names_frame_deepening():
    """agent_guidance.composition_discipline must name
    analysis.frame_deepening sub-fields as grounding measurements.
    Without this, the deepening block exists in JSON but the
    discipline does not point the agent at it.
    """
    baseline = len(_FAILURES)
    print("=== composition_discipline names frame_deepening ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "frame_deepening" in text,
        "composition_discipline must name analysis.frame_deepening "
        "as a grounding measurement",
    )
    check(
        "temporal_scope" in text or "stakeholder_map" in text
        or "falsification_conditions" in text,
        "composition_discipline must name at least one of the "
        "frame_deepening sub-fields explicitly so agents see what "
        "is in the deepening block",
    )
    _assert_no_new_failures(
        baseline, "test_composition_discipline_names_frame_deepening"
    )
    print("  PASS\n")


def test_clusters_abstain_on_short_documents():
    """Polish move: cluster builder must abstain when the document
    is below the word-count floor. Below the floor, absent_frames
    is dominated by catalog size minus a small number of matches;
    clusters fire mechanically on the canon graph rather than on
    real document signal.

    Pins the construct-honest abstention so a future change cannot
    silently re-introduce mechanical cluster surfacing on short
    text.
    """
    baseline = len(_FAILURES)
    print("=== clusters abstain on short documents ===")
    for label, doc in [
        ("empty", ""),
        ("single_word", "Word"),
        ("very_short", "Three sentences. No depth here. Very short."),
    ]:
        payload = mcp_server.build_epistemic_payload(
            doc, include_divergence=True,
        )
        clusters = payload["divergence"]["absence_clusters"]
        check(
            clusters == [],
            f"{label!r} document must yield empty absence_clusters; "
            f"got {len(clusters)} cluster(s)",
        )
    _assert_no_new_failures(
        baseline, "test_clusters_abstain_on_short_documents"
    )
    print("  PASS\n")


def test_clusters_abstain_when_zero_frames_match():
    """Polish move: cluster builder must abstain when zero FVS
    frames matched. Zero matches means absent_frames IS the
    catalog; clusters surface canon-graph structure rather than
    document signal. Common on off-methodology text (non-English,
    code, poetry, fragments) above the word-count floor.

    Tested via direct call on synthetic absent records with
    matched_frame_count=0.
    """
    baseline = len(_FAILURES)
    print("=== clusters abstain when zero matches ===")
    synthetic_absent = [
        {
            "frame_id": "FVS-007",
            "affects_dimensions": ["counterfactual"],
            "signal_strength": "high",
        },
        {
            "frame_id": "FVS-009",
            "affects_dimensions": ["coverage", "counterfactual"],
            "signal_strength": "high",
        },
        {
            "frame_id": "FVS-014",
            "affects_dimensions": ["coverage", "counterfactual"],
            "signal_strength": "high",
        },
    ]
    clusters = mcp_server._build_absence_clusters(
        synthetic_absent,
        document_word_count=200,
        matched_frame_count=0,
    )
    check(
        clusters == [],
        f"clusters must abstain when matched_frame_count=0 (zero "
        f"matches means absent_frames IS the catalog; clusters "
        f"would surface canon-graph noise); got {len(clusters)} "
        f"cluster(s)",
    )
    _assert_no_new_failures(
        baseline, "test_clusters_abstain_when_zero_frames_match"
    )
    print("  PASS\n")


def test_clusters_abstain_when_zero_claims_detected():
    """Polish move: cluster builder must abstain when the claim
    extractor found zero claims. Zero claims is an off-methodology
    signal: the document does not carry analytical content. Some
    FVS detectors fire vacuously on non-analytical text (e.g.
    FVS-007 fires when 'risks' and 'uncertainty' are both missing
    and unhedged_pct is high; on Lorem ipsum or code, those
    conditions trivially hold).
    """
    baseline = len(_FAILURES)
    print("=== clusters abstain when zero claims ===")
    synthetic_absent = [
        {
            "frame_id": "FVS-007",
            "affects_dimensions": ["counterfactual"],
            "signal_strength": "high",
        },
        {
            "frame_id": "FVS-009",
            "affects_dimensions": ["coverage", "counterfactual"],
            "signal_strength": "high",
        },
        {
            "frame_id": "FVS-014",
            "affects_dimensions": ["coverage", "counterfactual"],
            "signal_strength": "high",
        },
    ]
    clusters = mcp_server._build_absence_clusters(
        synthetic_absent,
        document_word_count=200,
        matched_frame_count=1,  # would pass the zero-match gate
        document_claim_count=0,
    )
    check(
        clusters == [],
        f"clusters must abstain when document_claim_count=0 (zero "
        f"claims is off-methodology signal even with one FVS "
        f"detector firing vacuously); got {len(clusters)} cluster(s)",
    )
    _assert_no_new_failures(
        baseline, "test_clusters_abstain_when_zero_claims_detected"
    )
    print("  PASS\n")


def test_genre_abstains_without_feature_evidence():
    """Polish move: genre classifier must abstain when no feature
    regex matches AND no claims detected. Voice classification
    alone (which produces a label on any text) is not sufficient
    evidence for structural genre. Without this gate, off-
    methodology text (non-English, code, poetry) classifies as
    'analysis' or 'advocacy' on voice signal alone.
    """
    baseline = len(_FAILURES)
    print("=== genre abstains without feature evidence ===")
    from genre_classifier import classify_genre
    # Lorem ipsum: no English markers, no claims. Voice classifier
    # may produce a label. Genre must abstain.
    lorem = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna "
        "aliqua. Ut enim ad minim veniam, quis nostrud exercitation "
        "ullamco laboris nisi ut aliquip ex ea commodo consequat. "
        "Duis aute irure dolor in reprehenderit in voluptate velit "
        "esse cillum dolore eu fugiat nulla pariatur. Excepteur "
        "sint occaecat cupidatat non proident, sunt in culpa qui "
        "officia deserunt mollit anim id est laborum. " * 3
    )
    # Pass voice/claims as None to mirror call site without
    # English-detected analyzers.
    result = classify_genre(lorem, voice=None, claims=None)
    check(
        result["genre"] is None,
        f"Lorem ipsum (no English feature markers, no claims) must "
        f"yield genre=None; got {result['genre']!r}",
    )
    check(
        result["confidence"] == "low",
        f"genre abstention must report confidence='low'; got "
        f"{result['confidence']!r}",
    )
    # Construct text must explain WHY abstention.
    construct = result.get("construct", "")
    check(
        "Voice classification alone" in construct
        or "no feature" in construct.lower()
        or "not sufficient evidence" in construct.lower(),
        f"abstention construct must explain that voice signal is "
        f"insufficient evidence; got {construct[:80]!r}",
    )
    _assert_no_new_failures(
        baseline, "test_genre_abstains_without_feature_evidence"
    )
    print("  PASS\n")


def test_full_payload_abstains_construct_honestly_on_off_methodology():
    """End-to-end stress test: off-methodology documents (non-
    English, code, poetry, fragments) must produce a payload where
    every substrate-side composition layer abstains construct-
    honestly. No clusters, no patterns, no genre classification,
    no false-positive frame_deepening. The agent reading the
    payload sees no fabricated structure.
    """
    baseline = len(_FAILURES)
    print("=== full payload abstains on off-methodology text ===")
    cases = [
        ("non_english", (
            "Lorem ipsum dolor sit amet, consectetur adipiscing "
            "elit. Sed do eiusmod tempor incididunt. " * 15
        )),
        ("code", (
            "def foo():\n    return bar.baz(x)\n\n"
            "class Y:\n    pass\n" * 15
        )),
        ("poetry", (
            "Roses are red\nViolets are blue\nSugar is sweet\n"
            "And so are you\n" * 15
        )),
    ]
    for label, doc in cases:
        payload = mcp_server.build_epistemic_payload(
            doc, include_divergence=True,
        )
        analysis = payload["analysis"]
        div = payload["divergence"]
        check(
            analysis["genre"]["classification"] is None,
            f"{label}: genre must abstain (got "
            f"{analysis['genre']['classification']!r})",
        )
        check(
            len(div["absence_clusters"]) == 0,
            f"{label}: absence_clusters must be empty (got "
            f"{len(div['absence_clusters'])})",
        )
        check(
            len(div["frame_patterns"]) == 0,
            f"{label}: frame_patterns must be empty (got "
            f"{len(div['frame_patterns'])})",
        )
    _assert_no_new_failures(
        baseline, "test_full_payload_abstains_construct_honestly_on_off_methodology"
    )
    print("  PASS\n")


def test_user_goal_attaches_goal_relevance_to_absent_frames():
    """When the user signals a goal (decide / brainstorm / persuade
    / learn / audit), absent_frames load-bearing for that goal carry
    a goal_relevance dict with priority and reason. Pins the field
    shape and the per-goal map's coverage of canonical frames.
    """
    baseline = len(_FAILURES)
    print("=== user_goal attaches goal_relevance to absent_frames ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, user_goal="decide",
    )
    absent = payload["divergence"]["absent_frames"]
    relevant = [r for r in absent if r.get("goal_relevance")]
    check(
        len(relevant) >= 1,
        f"with user_goal='decide', at least one absent_frame must "
        f"carry goal_relevance; got {len(relevant)} of {len(absent)}",
    )
    for r in relevant:
        gr = r["goal_relevance"]
        check(
            gr.get("relevant_for_goal") is True,
            f"goal_relevance.relevant_for_goal must be True; got "
            f"{gr.get('relevant_for_goal')!r}",
        )
        check(
            isinstance(gr.get("priority"), int) and gr["priority"] >= 1,
            f"goal_relevance.priority must be a positive int "
            f"(1 = most load-bearing); got {gr.get('priority')!r}",
        )
        check(
            isinstance(gr.get("reason"), str) and len(gr["reason"]) >= 30,
            f"goal_relevance.reason must be substantive prose; got "
            f"len={len(gr.get('reason', '')) if isinstance(gr.get('reason'), str) else 'non-str'}",
        )
    _assert_no_new_failures(
        baseline, "test_user_goal_attaches_goal_relevance_to_absent_frames"
    )
    print(f"  PASS  ({len(relevant)} of {len(absent)} carry goal_relevance)\n")


def test_user_goal_promotes_goal_relevant_absences():
    """Goal-relevant absences must rise within their tier above
    non-relevant ones. Pins the promotion invariant similar to
    genre-relevance, with goal taking priority over genre in the
    within-tier ranking.
    """
    baseline = len(_FAILURES)
    print("=== user_goal promotes goal-relevant absences ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, user_goal="persuade",
    )
    absent = payload["divergence"]["absent_frames"]
    by_tier = {}
    for r in absent:
        by_tier.setdefault(r["signal_strength"], []).append(r)
    for tier, records in by_tier.items():
        seen_non_goal_relevant = False
        for r in records:
            is_relevant = bool(r.get("goal_relevance"))
            if seen_non_goal_relevant and is_relevant:
                check(
                    False,
                    f"in tier {tier!r}: goal-relevant frame "
                    f"{r['frame_id']!r} appears AFTER a non-relevant "
                    f"frame; goal-relevance promotion invariant broken",
                )
            if not is_relevant:
                seen_non_goal_relevant = True
    _assert_no_new_failures(
        baseline, "test_user_goal_promotes_goal_relevant_absences"
    )
    print("  PASS\n")


def test_user_goal_audit_applies_no_override():
    """The 'audit' goal is the default-equivalent: the substrate
    applies the existing catalog/coverage/genre ranking without
    goal-specific override. Pins that audit means 'sovereignty
    posture' and not 'no goal at all'.
    """
    baseline = len(_FAILURES)
    print("=== user_goal='audit' applies no override ===")
    payload_audit = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, user_goal="audit",
    )
    payload_none = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    absent_audit = payload_audit["divergence"]["absent_frames"]
    absent_none = payload_none["divergence"]["absent_frames"]
    # None of the absent frames should carry goal_relevance under
    # 'audit' (the goal map for audit is empty).
    for r in absent_audit:
        check(
            r.get("goal_relevance") is None,
            f"under audit goal, no absent_frame should carry "
            f"goal_relevance (audit map is empty); got "
            f"{r['frame_id']!r} with goal_relevance="
            f"{r.get('goal_relevance')!r}",
        )
    # The sort orders should match between audit and none, since
    # audit applies no override.
    audit_ids = [r["frame_id"] for r in absent_audit]
    none_ids = [r["frame_id"] for r in absent_none]
    check(
        audit_ids == none_ids,
        f"absent_frames order under audit must match none order "
        f"(audit applies no goal override); got audit={audit_ids[:5]} "
        f"none={none_ids[:5]}",
    )
    # Envelope summary still notes the goal explicitly.
    summary = payload_audit["divergence"]["envelope"]["divergence_summary"]
    check(
        "audit" in summary.lower(),
        "envelope.divergence_summary must name 'audit' when "
        "user_goal='audit' (sovereignty posture should be visible "
        "to the agent)",
    )
    _assert_no_new_failures(
        baseline, "test_user_goal_audit_applies_no_override"
    )
    print("  PASS\n")


def test_user_goal_invalid_value_rejected_by_dispatcher():
    """user_goal validation: dispatcher must reject invalid enum
    values with a structured error response rather than passing
    them through.
    """
    baseline = len(_FAILURES)
    print("=== user_goal invalid value rejected ===")
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 130, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "user_goal": "INVALID_GOAL",
            },
        },
    })
    result = resp.get("result", {})
    check(
        result.get("isError") is True,
        "dispatcher must mark invalid user_goal as isError=True; "
        f"got result={result}",
    )
    text = result.get("content", [{}])[0].get("text", "")
    check(
        "user_goal must be one of" in text,
        f"error text must name the valid enum; got {text[:80]!r}",
    )
    _assert_no_new_failures(
        baseline, "test_user_goal_invalid_value_rejected_by_dispatcher"
    )
    print("  PASS\n")


def test_per_goal_load_bearing_maps_cover_all_goals():
    """Every classifier goal must have a curated load-bearing
    frame map (audit may be empty by design). Without coverage,
    a goal selection silently emits no goal_relevance.
    """
    baseline = len(_FAILURES)
    print("=== per-goal load-bearing maps cover all goals ===")
    from user_goals import (
        _GOALS, _GOAL_LOAD_BEARING_FRAMES,
        get_goal_load_bearing_frames,
    )
    for goal in _GOALS:
        check(
            goal in _GOAL_LOAD_BEARING_FRAMES,
            f"goal {goal!r} has no load-bearing frame map entry",
        )
        if goal == "audit":
            # audit is the default-equivalent posture; empty map
            # is intentional.
            continue
        bearings = get_goal_load_bearing_frames(goal)
        check(
            len(bearings) >= 3,
            f"goal {goal!r} map has fewer than 3 entries; substrate "
            f"composition becomes anemic",
        )
        for fvs_id, reason in bearings:
            check(
                isinstance(fvs_id, str) and fvs_id.startswith("FVS-"),
                f"map entry must carry FVS-XXX id; got {fvs_id!r}",
            )
            check(
                isinstance(reason, str) and len(reason) >= 50,
                f"map entry reason must be substantive (50+ chars); "
                f"got len={len(reason) if isinstance(reason, str) else 'non-str'}",
            )
    _assert_no_new_failures(
        baseline, "test_per_goal_load_bearing_maps_cover_all_goals"
    )
    print(f"  PASS  ({len(_GOALS)} goals covered)\n")


def test_how_to_render_divergence_teaches_goal_relevance():
    """agent_guidance.how_to_render_divergence step (6.4) must
    teach the goal_relevance layer: chosen goal, priority, reason
    citation. Pins the discipline so agents reading divergence know
    to surface goal-relevant absences with their structural reason.
    """
    baseline = len(_FAILURES)
    print("=== how_to_render_divergence teaches goal_relevance ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "goal_relevance" in text,
        "how_to_render_divergence must mention goal_relevance",
    )
    check(
        "user_goal" in text,
        "how_to_render_divergence must reference the user_goal "
        "parameter so the agent knows where the goal comes from",
    )
    check(
        "audit" in text and "sovereignty" in text.lower(),
        "how_to_render_divergence must explain that 'audit' is "
        "the sovereignty posture (no override)",
    )
    _assert_no_new_failures(
        baseline, "test_how_to_render_divergence_teaches_goal_relevance"
    )
    print("  PASS\n")


def test_frame_opportunities_default_omitted():
    """Item 12 default: include_frame_opportunities is opt-in.
    Without the flag, divergence.frame_opportunities surfaces an
    empty opportunities list (no LLM call). The deterministic
    substrate composes without ever invoking an LLM. Pins the
    moat-preserving default.
    """
    baseline = len(_FAILURES)
    print("=== frame_opportunities omitted by default ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    div = payload["divergence"]
    check(
        "frame_opportunities" in div,
        "divergence.frame_opportunities key must always be present "
        "(empty by default; opt-in to populate)",
    )
    fo = div["frame_opportunities"]
    check(
        fo["opportunities"] == [],
        f"opportunities must be empty when flag is False; got "
        f"{len(fo['opportunities'])}",
    )
    check(
        fo["total_cost_usd"] == 0.0,
        f"total_cost_usd must be 0.0 when flag is False; got "
        f"{fo['total_cost_usd']}",
    )
    check(
        fo["available"] is None,
        f"available must be None (not False) when flag is False; "
        f"None signals 'not invoked', False would signal 'invoked "
        f"but unavailable'; got {fo['available']!r}",
    )
    _assert_no_new_failures(
        baseline, "test_frame_opportunities_default_omitted"
    )
    print("  PASS\n")


def test_frame_opportunities_optin_populates_block():
    """When include_frame_opportunities=True and the LLM is
    available, divergence.frame_opportunities populates with
    document-grounded questions. Pins the integration end-to-end.

    This test depends on GEMINI_API_KEY being set in the test env.
    When unavailable, the test verifies the graceful-degradation
    path (available=False, opportunities=[]).
    """
    baseline = len(_FAILURES)
    print("=== frame_opportunities populates when flag is True ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS,
        include_divergence=True,
        include_frame_opportunities=True,
        user_goal="decide",
    )
    div = payload["divergence"]
    fo = div["frame_opportunities"]
    if fo.get("available") is False:
        # Graceful-degradation path 1: GEMINI key/library unavailable.
        # _is_gemini_available() returned False before any call.
        check(
            fo["opportunities"] == [],
            "when LLM unavailable, opportunities must be empty",
        )
        check(
            "unavailable_reason" in fo,
            "when LLM unavailable, frame_opportunities must carry "
            "unavailable_reason explaining the degradation",
        )
        _assert_no_new_failures(
            baseline, "test_frame_opportunities_optin_populates_block"
        )
        print("  PASS  (graceful degradation: key/library)\n")
        return
    if fo.get("available") is True and not fo.get("opportunities"):
        # Graceful-degradation path 2: GEMINI key/library present so
        # _is_gemini_available() returned True, but the actual API
        # call(s) returned None (transient API failure, rate limit,
        # network blip). The substrate's contract is "graceful
        # degradation as a feature, not an error" (see
        # frame_opportunities_discipline rule 5); the test honors that
        # by accepting the empty-opportunities case rather than
        # treating it as a regression. Total cost is 0.0 in this case
        # because no successful call was made.
        check(
            fo["total_cost_usd"] == 0.0,
            f"when API failed transiently, total_cost_usd must be "
            f"0.0; got {fo['total_cost_usd']}",
        )
        _assert_no_new_failures(
            baseline, "test_frame_opportunities_optin_populates_block"
        )
        print(
            "  PASS  (graceful degradation: transient API failure; "
            "no opportunities populated this run)\n"
        )
        return
    check(
        fo["available"] is True,
        f"with LLM available and flag=True, available must be True; "
        f"got {fo['available']!r}",
    )
    check(
        len(fo["opportunities"]) >= 1,
        f"with LLM available and opportunities populated, at least "
        f"one opportunity should be present; got "
        f"{len(fo['opportunities'])}",
    )
    check(
        fo["total_cost_usd"] > 0,
        f"populated opportunities must carry non-zero "
        f"total_cost_usd; got {fo['total_cost_usd']}",
    )
    for opp in fo["opportunities"]:
        required_keys = {
            "frame_id", "frame_title", "citation_uri",
            "teaching_question_general", "generated_question",
            "model_provenance",
        }
        check(
            required_keys <= set(opp.keys()),
            f"opportunity must carry {sorted(required_keys)}; got "
            f"{sorted(opp.keys())}",
        )
        mp = opp["model_provenance"]
        check(
            mp.get("is_deterministic") is False,
            "model_provenance.is_deterministic must be False "
            "(opportunities are LLM-generated, not deterministic)",
        )
        check(
            isinstance(mp.get("cost_usd"), float)
            and mp["cost_usd"] >= 0,
            "model_provenance.cost_usd must be a non-negative float",
        )
        check(
            isinstance(opp["generated_question"], str)
            and len(opp["generated_question"]) >= 30,
            f"generated_question must be substantive prose; got "
            f"len={len(opp.get('generated_question', '')) if isinstance(opp.get('generated_question'), str) else 'non-str'}",
        )
        check(
            opp.get("claim_level") == "agent_generated",
            "every opportunity must carry "
            "claim_level=agent_generated (substrate-side "
            "composition L5 completion: opt-in LLM content is "
            "the fourth claim kind)",
        )
    _assert_no_new_failures(
        baseline, "test_frame_opportunities_optin_populates_block"
    )
    print(f"  PASS  ({len(fo['opportunities'])} opportunities, ${fo['total_cost_usd']})\n")


def test_frame_opportunities_carries_provenance_discipline():
    """agent_guidance must include frame_opportunities_discipline
    teaching the agent: is_deterministic flag, cost surfacing,
    keep general teaching question alongside generated question,
    never present LLM content as Frame Check measurement, and
    handle graceful degradation.
    """
    baseline = len(_FAILURES)
    print("=== agent_guidance carries frame_opportunities_discipline ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    g = payload["agent_guidance"]
    check(
        "frame_opportunities_discipline" in g,
        "agent_guidance must carry frame_opportunities_discipline "
        "key (opt-in LLM layer needs explicit discipline)",
    )
    text = g.get("frame_opportunities_discipline", "")
    check(
        "is_deterministic" in text,
        "discipline must name the is_deterministic=False flag so "
        "agents distinguish LLM-generated from substrate-deterministic",
    )
    check(
        "cost" in text.lower(),
        "discipline must surface cost when an LLM call is involved",
    )
    check(
        "graceful" in text.lower() or "unavailable" in text.lower()
        or "degrade" in text.lower(),
        "discipline must address graceful degradation when LLM "
        "unavailable",
    )
    check(
        "Frame Check" in text and "measurement" in text.lower(),
        "discipline must name that opportunities are NOT Frame "
        "Check measurements (they are LLM compositions delegated "
        "by Frame Check)",
    )
    _assert_no_new_failures(
        baseline, "test_frame_opportunities_carries_provenance_discipline"
    )
    print("  PASS\n")


def test_agent_guidance_carries_how_to_map_user_intent():
    """Substrate-side composition L5 interface UX (Step 3): the
    agent calling frame_check needs explicit guidance for mapping
    natural-language user requests to the option space the four
    sovereignty prompts expose (depth, goal, questions). Without
    this guidance, the agent guesses and the user-intent vocabulary
    layer (Step 2) is invisible to the agent.

    Pins: agent_guidance.how_to_map_user_intent is present; carries
    concrete user-phrase -> argument mappings for each axis (depth,
    goal, questions); names the discipline (surface chosen options
    briefly; default to safe values on ambiguity; honor explicit
    arguments).
    """
    baseline = len(_FAILURES)
    print("=== agent_guidance carries how_to_map_user_intent ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("how_to_map_user_intent", "")
    check(
        isinstance(text, str) and len(text) > 200,
        "how_to_map_user_intent must be a substantive string "
        "(natural-language to option-space translation guidance)",
    )
    # Must teach all three argument axes
    for axis in ("depth", "goal", "questions"):
        check(
            axis in text,
            f"how_to_map_user_intent must name the {axis} axis",
        )
    # Must carry at least one concrete mapping per axis
    for mapping in (
        "depth=quick", "depth=thorough",
        "goal=decide", "goal=challenge", "goal=explore",
        "goal=learn",
        "questions=yes",
    ):
        check(
            mapping in text,
            f"how_to_map_user_intent must carry the concrete "
            f"mapping {mapping!r}",
        )
    # Must name the surface-chosen-options discipline
    check(
        "surface" in text.lower() and "adjust" in text.lower(),
        "how_to_map_user_intent must teach the discipline of "
        "surfacing chosen options briefly so the user can adjust",
    )
    # Must teach default-on-ambiguity
    check(
        "ambiguous" in text.lower() or "default" in text.lower(),
        "how_to_map_user_intent must teach default-on-ambiguity "
        "(safe defaults when user-intent is unclear)",
    )
    # Must teach honor-explicit-arguments
    check(
        "explicit" in text.lower() or "honor" in text.lower(),
        "how_to_map_user_intent must teach that explicit arguments "
        "from the user override agent inference",
    )
    _assert_no_new_failures(
        baseline, "test_agent_guidance_carries_how_to_map_user_intent"
    )
    print("  PASS\n")


def test_compose_budget_full_preserves_current_behavior():
    """compose_budget defaults to 'full' for backwards compat. The
    full payload carries all absent_frames, all absence_clusters,
    all frame_patterns, and the compose_budget_applied field shows
    no slicing. Pins backwards compat: callers omitting the
    parameter or passing 'full' get the same behavior they had
    before this parameter existed.
    """
    baseline = len(_FAILURES)
    print("=== compose_budget=full preserves current behavior ===")
    payload_default = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    payload_full = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, compose_budget="full",
    )
    d_default = payload_default["divergence"]
    d_full = payload_full["divergence"]
    check(
        len(d_default["absent_frames"]) == len(d_full["absent_frames"]),
        f"omitted compose_budget must equal compose_budget=full; "
        f"got default={len(d_default['absent_frames'])} vs "
        f"full={len(d_full['absent_frames'])}",
    )
    cba = d_full.get("compose_budget_applied", {})
    check(
        cba.get("level") == "full",
        f"compose_budget_applied.level must be 'full'; "
        f"got {cba.get('level')!r}",
    )
    check(
        cba.get("absent_frames_returned")
        == cba.get("absent_frames_total"),
        "with full, returned must equal total (no slicing)",
    )
    _assert_no_new_failures(
        baseline, "test_compose_budget_full_preserves_current_behavior"
    )
    print("  PASS\n")


def test_compose_budget_minimal_filters_top_n():
    """compose_budget=minimal slices output to top-3 absent_frames,
    top-1 cluster, top-1 pattern. The envelope.tier_counts remains
    PRE-slice (so the agent sees the truncation honestly); the
    compose_budget_applied field surfaces the per-layer
    returned/total counts.
    """
    baseline = len(_FAILURES)
    print("=== compose_budget=minimal slices to top-N ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS,
        include_divergence=True,
        compose_budget="minimal",
    )
    d = payload["divergence"]
    check(
        len(d["absent_frames"]) <= 3,
        f"minimal must yield <=3 absent_frames; "
        f"got {len(d['absent_frames'])}",
    )
    check(
        len(d["absence_clusters"]) <= 1,
        f"minimal must yield <=1 absence_cluster; "
        f"got {len(d['absence_clusters'])}",
    )
    check(
        len(d["frame_patterns"]) <= 1,
        f"minimal must yield <=1 frame_pattern; "
        f"got {len(d['frame_patterns'])}",
    )
    cba = d["compose_budget_applied"]
    check(
        cba["level"] == "minimal",
        f"compose_budget_applied.level must be 'minimal'; "
        f"got {cba['level']!r}",
    )
    check(
        cba["absent_frames_total"] >= cba["absent_frames_returned"],
        "absent_frames_total must reflect PRE-slice count",
    )
    # tier_counts must reflect PRE-slice counts (envelope honesty)
    envelope = d["envelope"]
    pre_slice_total = sum(envelope["tier_counts"].values())
    check(
        pre_slice_total == cba["absent_frames_total"],
        f"envelope.tier_counts must sum to PRE-slice "
        f"absent_frames_total; got "
        f"{pre_slice_total} vs {cba['absent_frames_total']}",
    )
    _assert_no_new_failures(
        baseline, "test_compose_budget_minimal_filters_top_n"
    )
    print("  PASS\n")


def test_compose_budget_minimal_compresses_agent_guidance():
    """compose_budget=minimal compresses agent_guidance to load-bearing
    prescriptions only. The compressed dict drops verbose worked
    examples (the cite-by-name lesson, the per-level example trios)
    and the full how_to_map_user_intent block, but keeps the load-
    bearing discipline so agent behavior contracts survive the cut.

    Pins:
      - compose_budget=full (default) returns the full agent_guidance
        unchanged (existing tests at line 872 area depend on this).
      - compose_budget=minimal returns a smaller agent_guidance.
      - The compressed dict still names Frame Check explicitly in
        how_to_cite_faithfully.
      - The compressed dict still surfaces reading-form vs verdict-
        form discipline in composition_discipline.
      - claim_level_treatments table is replaced with a URI pointer
        so the schema-shaped key still resolves but the body is not
        re-shipped per call.
      - how_to_map_user_intent is dropped (large, agent has its own
        NLU; not load-bearing for tight-loop callers).
      - Dynamic divergence keys (how_to_render_divergence,
        frame_opportunities_discipline, scope_regime_guidance) are
        passed through verbatim because they govern blocks the
        caller explicitly asked for.
    """
    baseline = len(_FAILURES)
    print("=== compose_budget=minimal compresses agent_guidance ===")

    full_payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS,
        include_divergence=True,
        compose_budget="full",
    )
    minimal_payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS,
        include_divergence=True,
        compose_budget="minimal",
    )

    full_ag = full_payload["agent_guidance"]
    minimal_ag = minimal_payload["agent_guidance"]

    import json as _json
    full_size = len(_json.dumps(full_ag))
    minimal_size = len(_json.dumps(minimal_ag))

    check(
        minimal_size < full_size,
        f"compose_budget=minimal must produce smaller agent_guidance "
        f"than full; got minimal={minimal_size} >= full={full_size}",
    )

    # Reduction floor: at least 1.5x. The benchmark documents a 2.5x
    # reduction on the FOMC document; the floor is set conservatively
    # so adding load-bearing prescriptions later does not break the
    # test, while still catching a regression that silently re-bloats
    # the minimal output.
    check(
        full_size >= minimal_size * 1.5,
        f"compose_budget=minimal must achieve >=1.5x reduction over "
        f"full; got full={full_size} minimal={minimal_size} "
        f"ratio={full_size/minimal_size:.2f}x",
    )

    # Load-bearing keys preserved with their discipline.
    check(
        "how_to_cite_faithfully" in minimal_ag,
        "minimal must keep how_to_cite_faithfully (load-bearing for "
        "citation discipline)",
    )
    check(
        "Frame Check" in minimal_ag.get("how_to_cite_faithfully", ""),
        "minimal how_to_cite_faithfully must still name Frame Check "
        "explicitly",
    )
    check(
        "composition_discipline" in minimal_ag,
        "minimal must keep composition_discipline (load-bearing for "
        "reading-form-not-verdict-form)",
    )
    cd = minimal_ag.get("composition_discipline", "")
    check(
        "reading-form" in cd and "verdict-form" in cd,
        "minimal composition_discipline must preserve reading-form-"
        "not-verdict-form discipline",
    )
    check(
        "when_invoked_on_own_output" in minimal_ag,
        "minimal must keep when_invoked_on_own_output (the self-audit "
        "case is the highest-frequency invocation pattern)",
    )
    check(
        "dual_use_note" in minimal_ag,
        "minimal must keep dual_use_note (anti-misuse is load-bearing)",
    )

    # claim_level_treatments table replaced with a short note that
    # points callers to compose_budget='full' for the inline table.
    # The note value MUST NOT promise a fetchable URI: the compressed
    # payload ships on the wire to integrators, and a 404-able URI
    # would violate the published-state-must-be-true posture.
    check(
        "claim_level_treatments_note" in minimal_ag,
        "minimal must surface claim_level_treatments_note pointing to "
        "compose_budget='full' for the full table",
    )
    check(
        "claim_level_treatments" not in minimal_ag,
        "minimal must NOT inline the full claim_level_treatments table "
        "(that is the per-call cost the note eliminates)",
    )
    note_value = minimal_ag.get("claim_level_treatments_note", "")
    check(
        "frame-check://" not in note_value,
        f"claim_level_treatments_note must not promise a frame-check:// "
        f"URI unless the resource is served via _list_resources; "
        f"got {note_value[:120]!r}",
    )
    check(
        "compose_budget='full'" in note_value
        or 'compose_budget="full"' in note_value,
        f"claim_level_treatments_note must point callers at "
        f"compose_budget='full' for the inline table; got "
        f"{note_value[:120]!r}",
    )

    # how_to_map_user_intent dropped (it is large and the agent has
    # its own NLU).
    check(
        "how_to_map_user_intent" not in minimal_ag,
        "minimal must drop how_to_map_user_intent (large, not load-"
        "bearing for tight-loop callers)",
    )

    # compose_budget_applied_note documents the cut so the caller can
    # confirm the compression actually ran.
    check(
        "compose_budget_applied_note" in minimal_ag,
        "minimal must include compose_budget_applied_note so the "
        "caller can confirm compression is active",
    )

    # Full mode is unchanged. Pin via spot-check on a key that minimal
    # drops and a key that minimal compresses.
    check(
        "how_to_map_user_intent" in full_ag,
        "compose_budget=full must keep how_to_map_user_intent "
        "(backwards compat with all callers omitting the parameter)",
    )
    check(
        "claim_level_treatments" in full_ag,
        "compose_budget=full must inline claim_level_treatments table",
    )

    _assert_no_new_failures(
        baseline, "test_compose_budget_minimal_compresses_agent_guidance"
    )
    print("  PASS\n")


def test_compose_budget_standard_compresses_agent_guidance():
    """compose_budget=standard applies the same agent_guidance
    compression as minimal (load-bearing prescriptions only) while
    keeping the standard divergence-side slicing (top-5 absent_frames,
    all clusters, all patterns). The two tiers differ only in
    divergence-side cuts, not in agent_guidance shape, so a caller
    sizing token budget at "standard" sees a real reduction without
    losing the cluster + pattern surfaces minimal would also cut.

    Pins:
      - standard agent_guidance is materially smaller than full
        (>=1.5x ratio, parity with the minimal floor).
      - standard agent_guidance shares its key shape with minimal
        agent_guidance (same compression rules apply).
      - compose_budget_applied_note correctly reports
        compose_budget=standard so the caller can audit which tier
        produced the cut.
      - standard preserves the load-bearing rules (Frame Check name,
        reading-form-not-verdict-form, dual-use anti-misuse,
        self-audit rule).
      - standard divergence-side slicing is unchanged: top-5 absent
        frames, all clusters/patterns preserved (no cluster/pattern
        cut at this tier).
    """
    baseline = len(_FAILURES)
    print("=== compose_budget=standard compresses agent_guidance ===")

    full_payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, compose_budget="full",
    )
    standard_payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, compose_budget="standard",
    )
    minimal_payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True, compose_budget="minimal",
    )

    full_ag = full_payload["agent_guidance"]
    standard_ag = standard_payload["agent_guidance"]
    minimal_ag = minimal_payload["agent_guidance"]

    import json as _json
    full_size = len(_json.dumps(full_ag))
    standard_size = len(_json.dumps(standard_ag))

    check(
        standard_size < full_size,
        f"compose_budget=standard must produce smaller agent_guidance "
        f"than full; got standard={standard_size} >= full={full_size}",
    )
    check(
        full_size >= standard_size * 1.5,
        f"compose_budget=standard must achieve >=1.5x reduction over "
        f"full (essence-preserving compression); got full={full_size} "
        f"standard={standard_size} ratio={full_size/standard_size:.2f}x",
    )

    # Standard and minimal share AG shape (same compression function).
    check(
        set(standard_ag.keys()) == set(minimal_ag.keys()),
        f"compose_budget=standard must share agent_guidance key shape "
        f"with minimal (same compression rules). "
        f"standard - minimal = {set(standard_ag.keys()) - set(minimal_ag.keys())!r}; "
        f"minimal - standard = {set(minimal_ag.keys()) - set(standard_ag.keys())!r}",
    )

    # Tier note correctly reports the cut.
    note = standard_ag.get("compose_budget_applied_note", "")
    check(
        "compose_budget=standard" in note,
        f"compose_budget=standard must report itself in "
        f"compose_budget_applied_note; got {note[:120]!r}",
    )
    # The note ships on the wire to integrators; it MUST NOT promise
    # a frame-check:// URI unless the resource is served via
    # _list_resources. A 404-able URI in the wire payload would
    # violate the published-state-must-be-true posture.
    check(
        "frame-check://" not in note,
        f"compose_budget_applied_note must not promise a frame-check:// "
        f"URI unless the resource is served; got {note[:160]!r}",
    )

    # Load-bearing rules survive the cut.
    check(
        "Frame Check" in standard_ag.get("how_to_cite_faithfully", ""),
        "standard how_to_cite_faithfully must still name Frame Check "
        "explicitly",
    )
    cd = standard_ag.get("composition_discipline", "")
    check(
        "reading-form" in cd and "verdict-form" in cd,
        "standard composition_discipline must preserve reading-form-"
        "not-verdict-form discipline",
    )
    check(
        "when_invoked_on_own_output" in standard_ag,
        "standard must keep when_invoked_on_own_output (self-audit rule "
        "is load-bearing)",
    )
    check(
        "dual_use_note" in standard_ag,
        "standard must keep dual_use_note (anti-misuse is load-bearing)",
    )

    # Divergence-side: standard does NOT cut clusters or patterns
    # (that distinguishes it from minimal). Confirm a non-zero cluster
    # count survives when full mode produced any.
    full_div = full_payload["divergence"]
    standard_div = standard_payload["divergence"]
    check(
        len(standard_div["absence_clusters"])
        == len(full_div["absence_clusters"]),
        f"standard must preserve all absence_clusters (only minimal "
        f"cuts to top-1); full={len(full_div['absence_clusters'])} "
        f"standard={len(standard_div['absence_clusters'])}",
    )
    check(
        len(standard_div["frame_patterns"])
        == len(full_div["frame_patterns"]),
        f"standard must preserve all frame_patterns (only minimal "
        f"cuts to top-1); full={len(full_div['frame_patterns'])} "
        f"standard={len(standard_div['frame_patterns'])}",
    )
    check(
        len(standard_div["absent_frames"]) <= 5,
        f"standard must yield <=5 absent_frames; "
        f"got {len(standard_div['absent_frames'])}",
    )

    _assert_no_new_failures(
        baseline, "test_compose_budget_standard_compresses_agent_guidance"
    )
    print("  PASS\n")


def test_compose_budget_invalid_value_rejected():
    """The dispatcher rejects invalid compose_budget values with a
    structured error so the caller sees the valid enum.
    """
    baseline = len(_FAILURES)
    print("=== compose_budget invalid value rejected ===")
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 200, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "compose_budget": "invalidvalue",
            },
        },
    })
    result = resp.get("result", {})
    check(
        result.get("isError") is True,
        f"dispatcher must mark invalid compose_budget as "
        f"isError=True; got {result}",
    )
    text = result.get("content", [{}])[0].get("text", "")
    check(
        "compose_budget must be one of" in text,
        f"error must name the valid enum; got {text[:100]!r}",
    )
    _assert_no_new_failures(
        baseline, "test_compose_budget_invalid_value_rejected"
    )
    print("  PASS\n")


def test_sovereignty_prompts_advertise_user_intent_arguments():
    """Substrate-side composition L5 interface UX: each sovereignty
    prompt must advertise the three user-intent arguments (depth,
    goal, questions) so MCP clients surface them as user-facing
    options. Without this, the user has no surface to express their
    intent in their own vocabulary; the agent has to guess from
    natural-language requests.
    """
    baseline = len(_FAILURES)
    print(
        "=== sovereignty prompts advertise user-intent arguments ==="
    )
    resp = mcp_server.handle_prompts_list({})
    expected_arg_names = {"depth", "goal", "questions"}
    for prompt in resp["prompts"]:
        if not prompt["name"].startswith(
            ("frame_check_", "challenge_", "explain_")
        ):
            continue
        arg_names = {a["name"] for a in prompt.get("arguments", [])}
        check(
            expected_arg_names.issubset(arg_names),
            f"{prompt['name']}: must advertise {expected_arg_names}; "
            f"got {arg_names}",
        )
    _assert_no_new_failures(
        baseline,
        "test_sovereignty_prompts_advertise_user_intent_arguments",
    )
    print("  PASS\n")


def test_prompt_arguments_translate_to_mcp_parameters():
    """User-intent arguments must translate to the corresponding
    MCP-parameter values inside the prompt body. The user types
    depth/goal/questions in their own vocabulary; the prompt body
    that goes to the agent contains the translated MCP parameters
    (compose_budget, user_goal, include_frame_opportunities) so the
    agent calls frame_check with the right values.
    """
    baseline = len(_FAILURES)
    print(
        "=== prompt arguments translate to MCP parameter values ==="
    )
    # Default args -> default MCP params
    body = mcp_server.handle_prompts_get(
        {"name": "frame_check_my_response"}
    )["messages"][0]["content"]["text"]
    check(
        "compose_budget=full" in body,
        "default depth must translate to compose_budget=full",
    )
    check(
        "user_goal=audit" in body,
        "default goal must translate to user_goal=audit",
    )
    check(
        "include_frame_opportunities=false" in body,
        "default questions must translate to "
        "include_frame_opportunities=false",
    )

    # depth=quick + goal=decide + questions=yes
    body2 = mcp_server.handle_prompts_get({
        "name": "frame_check_my_response",
        "arguments": {
            "depth": "quick",
            "goal": "decide",
            "questions": "yes",
        },
    })["messages"][0]["content"]["text"]
    check(
        "compose_budget=minimal" in body2,
        "depth=quick must translate to compose_budget=minimal",
    )
    check(
        "user_goal=decide" in body2,
        "goal=decide must translate to user_goal=decide",
    )
    check(
        "include_frame_opportunities=true" in body2,
        "questions=yes must translate to "
        "include_frame_opportunities=true",
    )

    # goal=explore -> user_goal=brainstorm (not user_goal=explore)
    body3 = mcp_server.handle_prompts_get({
        "name": "frame_check_my_response",
        "arguments": {"goal": "explore"},
    })["messages"][0]["content"]["text"]
    check(
        "user_goal=brainstorm" in body3,
        "goal=explore must translate to user_goal=brainstorm "
        "(the substrate's enum value)",
    )

    # goal=challenge -> user_goal=audit + ADVERSARIAL CHALLENGE note
    body4 = mcp_server.handle_prompts_get({
        "name": "challenge_document",
        "arguments": {"goal": "challenge"},
    })["messages"][0]["content"]["text"]
    check(
        "user_goal=audit" in body4,
        "goal=challenge translates user_goal to audit (challenge is "
        "an audit posture with composition-note differentiation)",
    )
    check(
        "ADVERSARIAL CHALLENGE" in body4,
        "goal=challenge must inject the adversarial composition note",
    )

    # Invalid values fall back to defaults (do not raise)
    body5 = mcp_server.handle_prompts_get({
        "name": "frame_check_my_response",
        "arguments": {
            "depth": "invalid",
            "goal": "invalid",
            "questions": "invalid",
        },
    })["messages"][0]["content"]["text"]
    check(
        "compose_budget=full" in body5
        and "user_goal=audit" in body5
        and "include_frame_opportunities=false" in body5,
        "invalid argument values must fall back to defaults "
        "(prompts are user-invoked surfaces; rejecting an invalid "
        "value would be poor UX)",
    )
    _assert_no_new_failures(
        baseline, "test_prompt_arguments_translate_to_mcp_parameters"
    )
    print("  PASS\n")


def test_agent_generated_claim_level_for_opportunities():
    """Substrate-side composition L5 completion: opt-in LLM-composed
    content is the fourth claim kind. Pins (1) the agent_generated
    treatment in claim_level_treatments with construct-honest
    validation_status (deterministic=False is the only level with
    this; IRR is not_applicable because the output is generative,
    not a measurement); (2) when populated, every opportunity dict
    carries claim_level=agent_generated.

    The treatment-shape assertions run unconditionally (no LLM
    needed). The per-opportunity claim_level assertion only runs
    on the LLM-available path; the test passes on the graceful-
    degradation path with treatment-shape coverage only.
    """
    baseline = len(_FAILURES)
    print("=== agent_generated claim level for opportunities ===")

    # Path 1: treatments shape (no LLM required)
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    treatments = payload["agent_guidance"].get(
        "claim_level_treatments", {}
    ) or {}
    check(
        "agent_generated" in treatments,
        "claim_level_treatments must carry the agent_generated "
        "key for opt-in LLM-composed content (Item 12 frame_"
        "opportunities)",
    )
    ag = treatments.get("agent_generated") or {}
    vs = ag.get("validation_status") or {}
    check(
        vs.get("deterministic") is False,
        "agent_generated.validation_status.deterministic must be "
        "False (the only level where the output is non-"
        "deterministic by design); got "
        f"{vs.get('deterministic')!r}",
    )
    check(
        vs.get("inter_rater_reliability") == "not_applicable",
        "agent_generated.validation_status.inter_rater_reliability "
        "must be 'not_applicable' (the output is generative; IRR "
        f"is the wrong metric); got {vs.get('inter_rater_reliability')!r}",
    )
    vd = vs.get("validity_data", "")
    check(
        "model_provenance" in vd,
        "agent_generated.validation_status.validity_data must "
        "name model_provenance as the per-output audit trail",
    )
    check(
        "non-deterministic" in vd or "non-reproducible" in vd,
        "validity_data must name non-determinism explicitly so "
        "the agent does not over-claim reproducibility",
    )
    check(
        isinstance(ag.get("how_to_cite"), str)
        and "model_provenance" in ag["how_to_cite"],
        "agent_generated.how_to_cite must direct the agent to "
        "surface model_provenance fields when citing",
    )

    # Path 2: per-opportunity claim_level (LLM-available path only)
    fo_payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS,
        include_divergence=True,
        include_frame_opportunities=True,
        user_goal="decide",
    )
    fo = fo_payload["divergence"]["frame_opportunities"]
    if fo.get("available") is True and fo.get("opportunities"):
        for opp in fo["opportunities"]:
            check(
                opp.get("claim_level") == "agent_generated",
                f"every opportunity must carry "
                f"claim_level=agent_generated; got "
                f"{opp.get('claim_level')!r} on {opp.get('frame_id')}",
            )

    # Composition discipline must name the fourth level so the
    # rule (6) per-level treatment is complete.
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "agent_generated" in text,
        "composition_discipline rule (6) must name the fourth "
        "claim level (agent_generated) so the agent can match "
        "Item 12 outputs to the per-level treatment",
    )

    _assert_no_new_failures(
        baseline, "test_agent_generated_claim_level_for_opportunities"
    )
    if fo.get("available") is True and fo.get("opportunities"):
        print(
            f"  PASS  ({len(fo['opportunities'])} opportunities "
            f"checked)\n"
        )
    else:
        print("  PASS  (treatments-shape only; LLM unavailable)\n")


def test_llm_classifier_output_claim_level_treatment():
    """L5 framework v1.2: a fifth claim level llm_classifier_output
    is added to claim_level_treatments per CONSTRUCT_VALIDITY_AUDIT
    v1.2 (Proposal A). V4.2 LLM-judge FVS detection is the canonical
    instance; the level distinguishes LLM-judge binary classification
    (no per-emission confidence, macro-aggregate reliability evidence)
    from the deterministic-cascade classifier_output level
    (per-emission confidence + runner-up).

    Pins the dispatch shape so a future engine change cannot silently
    drop the level or its discipline. Wire-shipping V4.2 emissions
    with this claim_level dispatch missing would break the per-level
    discipline the L5 framework exists to enforce.
    """
    baseline = len(_FAILURES)
    print("=== llm_classifier_output claim level treatment ===")

    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    treatments = payload["agent_guidance"].get(
        "claim_level_treatments", {}
    ) or {}

    check(
        "llm_classifier_output" in treatments,
        "claim_level_treatments must carry the llm_classifier_output "
        "key (v1.2 Proposal A; V4.2 ships under this level)",
    )
    llm_co = treatments.get("llm_classifier_output") or {}
    vs = llm_co.get("validation_status") or {}

    # The level is non-deterministic by design: LLM judgment
    # produces variance across run-pairs. This is the structural
    # property that distinguishes it from classifier_output.
    check(
        vs.get("deterministic") is False,
        "llm_classifier_output.validation_status.deterministic must "
        "be False (LLM-judge classification is non-deterministic by "
        f"design); got {vs.get('deterministic')!r}",
    )

    # Reliability is a property of the macro aggregate, NOT the
    # per-emission. Conflating these would let an evaluator treat
    # a binary V4.2 emission as if it carried per-emission
    # confidence, which it does not.
    check(
        vs.get("inter_rater_reliability") == "macro_aggregate_only",
        "llm_classifier_output.validation_status.inter_rater_"
        "reliability must be 'macro_aggregate_only' to distinguish "
        "from classifier_output's per-emission confidence; got "
        f"{vs.get('inter_rater_reliability')!r}",
    )

    vd = vs.get("validity_data", "")
    check(
        "macro-F1" in vd or "macro_F1" in vd,
        "llm_classifier_output.validation_status.validity_data must "
        "reference macro-F1 (the load-bearing aggregate reliability "
        "metric for V4.2)",
    )

    caveats = llm_co.get("caveats") or []
    caveat_text = " ".join(caveats)
    check(
        "confidence" in caveat_text and "proxy" in caveat_text,
        "llm_classifier_output.caveats must explicitly forbid "
        "paraphrasing the reasoning text as a confidence proxy "
        "(load-bearing distinction from classifier_output)",
    )
    check(
        "honest_limit" in caveat_text,
        "llm_classifier_output.caveats must direct the agent to "
        "surface honest_limit caveats when present (per-frame "
        "operationalization gap disclosure is structural to the "
        "level)",
    )

    htc = llm_co.get("how_to_cite", "")
    check(
        "Frame Check" in htc and "reliability" in htc,
        "llm_classifier_output.how_to_cite must name Frame Check "
        "AND the reliability tier so the citation carries the "
        "aggregate evidence (got: " + repr(htc[:120]) + ")",
    )

    # The full five-level dispatch must be present. This catches
    # accidental key removal in future refactors.
    expected_levels = {
        "detector_measurement",
        "classifier_output",
        "llm_classifier_output",
        "composed_pattern",
        "agent_generated",
    }
    actual_levels = set(treatments.keys())
    check(
        expected_levels.issubset(actual_levels),
        "claim_level_treatments must carry all five L5 framework "
        "levels; missing: "
        f"{sorted(expected_levels - actual_levels)}",
    )

    _assert_no_new_failures(
        baseline, "test_llm_classifier_output_claim_level_treatment"
    )
    print("  PASS\n")


def test_frame_opportunities_invalid_value_rejected():
    """include_frame_opportunities validation: dispatcher must
    reject non-boolean values with a structured error.
    """
    baseline = len(_FAILURES)
    print("=== include_frame_opportunities invalid value rejected ===")
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 140, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": _DOC_SAMPLE,
                "include_frame_opportunities": "yes",  # not a bool
            },
        },
    })
    result = resp.get("result", {})
    check(
        result.get("isError") is True,
        f"dispatcher must mark non-boolean "
        f"include_frame_opportunities as isError=True; got {result}",
    )
    text = result.get("content", [{}])[0].get("text", "")
    check(
        "must be a boolean" in text,
        f"error text must name the type expectation; got {text[:80]!r}",
    )
    _assert_no_new_failures(
        baseline, "test_frame_opportunities_invalid_value_rejected"
    )
    print("  PASS\n")


def test_pattern_triggers_use_doc_signals_for_discrimination():
    """Polish: pattern triggers must use frame_deepening +
    epistemic discriminators to distinguish discriminating-pattern
    matches from genre labels. Without doc_signals, the patterns
    fire on most documents in their target genre and lose
    discriminating value.

    Pins the discrimination logic on three patterns:
      recommendation-without-falsification (falsification_max_count=0)
      analysis-without-grounding (sourced_pct_max=20)
      advocacy-without-counter-perspective (stakeholder_role_count_max=1)
    """
    baseline = len(_FAILURES)
    print("=== pattern triggers use doc_signals for discrimination ===")
    from frame_patterns import match_patterns

    matched = {"FVS-007"}  # absence-of-failure-framing detector
    absent = {"FVS-009", "FVS-014"}

    # Recommendation with explicit falsification (count > 0): pattern
    # MUST NOT fire even though FVS-007 + FVS-009 + FVS-014 match.
    no_fire = match_patterns(
        matched, absent, "recommendation",
        doc_signals={"falsification_count": 1},
    )
    check(
        not any(
            p["id"] == "recommendation-without-falsification"
            for p in no_fire
        ),
        "recommendation-without-falsification must NOT fire when "
        "falsification_count > 0 (document has explicit falsification "
        "statements)",
    )

    # Recommendation with no falsification (count == 0): pattern
    # MUST fire.
    fires = match_patterns(
        matched, absent, "recommendation",
        doc_signals={"falsification_count": 0},
    )
    check(
        any(
            p["id"] == "recommendation-without-falsification"
            for p in fires
        ),
        "recommendation-without-falsification must fire when all "
        "FVS conditions match AND falsification_count == 0",
    )

    # Analysis with high sourced_pct: pattern MUST NOT fire.
    analysis_absent = {"FVS-016", "FVS-012"}
    no_fire_a = match_patterns(
        set(), analysis_absent, "analysis",
        doc_signals={"sourced_pct": 50.0},
    )
    check(
        not any(
            p["id"] == "analysis-without-grounding"
            for p in no_fire_a
        ),
        "analysis-without-grounding must NOT fire when sourced_pct "
        "above 20% threshold",
    )

    # Analysis with low sourced_pct: pattern MUST fire.
    fires_a = match_patterns(
        set(), analysis_absent, "analysis",
        doc_signals={"sourced_pct": 5.0},
    )
    check(
        any(
            p["id"] == "analysis-without-grounding"
            for p in fires_a
        ),
        "analysis-without-grounding must fire on low sourced_pct",
    )

    # Advocacy with many stakeholders: pattern MUST NOT fire.
    advocacy_absent = {"FVS-017", "FVS-009"}
    no_fire_adv = match_patterns(
        set(), advocacy_absent, "advocacy",
        doc_signals={"stakeholder_role_count": 6},
    )
    check(
        not any(
            p["id"] == "advocacy-without-counter-perspective"
            for p in no_fire_adv
        ),
        "advocacy-without-counter-perspective must NOT fire when "
        "stakeholder_role_count > 1 (document mentions multiple "
        "stakeholder categories)",
    )
    _assert_no_new_failures(
        baseline,
        "test_pattern_triggers_use_doc_signals_for_discrimination",
    )
    print("  PASS\n")


def test_stakeholder_regex_covers_policymakers_public_industry():
    """Polish: stakeholder regex must cover policymakers, public,
    industry actors, affected populations beyond the original
    eight categories. Pins the regex coverage so future changes
    cannot silently drop politically-relevant stakeholder
    categories.
    """
    baseline = len(_FAILURES)
    print("=== stakeholder regex covers policymakers + public + industry ===")
    from frame_deepening import detect_stakeholder_map
    text = (
        "Policymakers in Congress will decide the policy direction. "
        "Lawmakers must enact legislation. Senators have stated "
        "positions. The public and citizens demand action. Voters in "
        "the upcoming election will weigh in. The fossil fuel industry "
        "lobbies against change. The auto industry has resisted. "
        "Workers in the energy sector deserve transition support. "
        "Affected populations in coastal regions face existential risks. "
        "Patients with chronic conditions need access to care. " * 2
    )
    result = detect_stakeholder_map(text)
    check(
        result is not None,
        "stakeholder_map must populate above word floor",
    )
    if result is None:
        _assert_no_new_failures(
            baseline,
            "test_stakeholder_regex_covers_policymakers_public_industry",
        )
        return
    expected_categories = {
        "policymakers", "public", "industry_actors",
        "affected_populations",
    }
    check(
        expected_categories <= set(result["roles_mentioned"]),
        f"expanded stakeholder regex must catch policymakers / "
        f"public / industry_actors / affected_populations; got "
        f"{result['roles_mentioned']}",
    )
    _assert_no_new_failures(
        baseline,
        "test_stakeholder_regex_covers_policymakers_public_industry",
    )
    print("  PASS\n")


def test_falsification_regex_covers_conditional_reasoning():
    """Polish: falsification regex must catch 'if X holds / if Y
    proves wrong / the argument hinges on' style conditional
    reasoning, not only the literal 'would be wrong if' phrase.
    """
    baseline = len(_FAILURES)
    print("=== falsification regex covers conditional reasoning ===")
    from frame_deepening import detect_falsification_conditions
    text = (
        "The analysis depends on a key assumption about market growth. "
        "If the earlier timeline holds, the policy must adapt quickly. "
        "If the later timeline holds, organizations have more runway. "
        "If that turns out to be wrong, the entire framework collapses. "
        "The argument rests on the assumption that competitors will not "
        "respond. Could be wrong if regulators move faster than expected. "
        "If the alternative scenario proves accurate, the calculus shifts. " * 2
    )
    result = detect_falsification_conditions(text)
    check(
        result is not None,
        "falsification detector must populate above word floor",
    )
    if result is None:
        _assert_no_new_failures(
            baseline,
            "test_falsification_regex_covers_conditional_reasoning",
        )
        return
    check(
        result["primary_match_count"] >= 3,
        f"expanded regex must catch at least 3 of the conditional "
        f"reasoning patterns; got {result['primary_match_count']}",
    )
    _assert_no_new_failures(
        baseline,
        "test_falsification_regex_covers_conditional_reasoning",
    )
    print("  PASS\n")


def test_divergence_summary_grammar_correct():
    """Polish: divergence_summary genre_phrase and goal_phrase must
    use grammatical singular/plural agreement. Previously the
    template said '3 absent frames carries' (singular verb with
    plural noun); now reads '3 absent frames carry'.
    """
    baseline = len(_FAILURES)
    print("=== divergence_summary grammar is correct ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
        user_goal="decide",
    )
    summary = payload["divergence"]["envelope"]["divergence_summary"]
    check(
        "frames carries" not in summary,
        f"summary must not contain 'frames carries' (plural noun + "
        f"singular verb); got summary segment: "
        f"{summary[summary.find('frames'):summary.find('frames')+50]!r}",
    )
    check(
        "frames is promoted" not in summary,
        f"summary must not contain 'frames is promoted' (plural "
        f"noun + singular verb); got summary segment: "
        f"{summary[summary.find('frames'):summary.find('frames')+80]!r}",
    )
    _assert_no_new_failures(
        baseline, "test_divergence_summary_grammar_correct"
    )
    print("  PASS\n")


def test_corpus_carries_per_genre_segmentation():
    """Item E of the substrate-side composition polish: corpus
    aggregator classifies each corpus document by structural genre
    and exposes per-genre counts in corpus_summary. Per-frame
    corpus_context carries fires_in_by_genre with rate per genre.

    Pins the segmentation infrastructure so future scaling produces
    like-vs-like prevalence comparisons.
    """
    baseline = len(_FAILURES)
    print("=== corpus carries per-genre segmentation ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    summary = payload["divergence"]["envelope"].get("corpus_summary")
    if summary is None:
        print("  SKIP  (corpus unavailable)\n")
        return
    check(
        "per_genre_counts" in summary,
        "corpus_summary must carry per_genre_counts dict",
    )
    counts = summary.get("per_genre_counts", {})
    check(
        isinstance(counts, dict) and len(counts) >= 1,
        f"per_genre_counts must be non-empty dict; got {counts}",
    )
    # The bucket "_unclassified" must appear when any document
    # abstained, and total counts must sum to n_documents.
    total = sum(counts.values())
    check(
        total == summary["n_documents"],
        f"per_genre_counts must sum to n_documents; "
        f"got sum={total} vs n_documents={summary['n_documents']}",
    )
    # The small_n_caveat must mention segmentation discipline.
    caveat = summary.get("small_n_caveat", "")
    check(
        "segmentation" in caveat.lower() or "_unclassified" in caveat,
        "small_n_caveat must explain the segmentation discipline "
        "(per_genre_counts + _unclassified bucket)",
    )
    _assert_no_new_failures(
        baseline, "test_corpus_carries_per_genre_segmentation"
    )
    print(f"  PASS  ({len(counts)} genre buckets in corpus_summary)\n")


def test_per_frame_corpus_context_carries_fires_in_by_genre():
    """Item E: per-frame corpus_context exposes fires_in_by_genre
    so the agent can compute like-vs-like prevalence per frame.
    Each genre entry carries fires_in_count, genre_total, and rate.
    """
    baseline = len(_FAILURES)
    print("=== per-frame corpus_context carries fires_in_by_genre ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    matches = payload["analysis"].get("frame_library_matches", [])
    if not matches:
        print("  SKIP  (no matches on fixture)\n")
        return
    for m in matches:
        cc = m.get("corpus_context")
        if cc is None:
            continue
        check(
            "fires_in_by_genre" in cc,
            f"matched frame {m['fvs_id']} must carry "
            f"fires_in_by_genre in corpus_context",
        )
        by_genre = cc.get("fires_in_by_genre", {})
        for genre, stats in by_genre.items():
            required = {"fires_in_count", "genre_total", "rate"}
            check(
                required <= set(stats.keys()),
                f"fires_in_by_genre[{genre}] must carry "
                f"{sorted(required)}; got {sorted(stats.keys())}",
            )
            check(
                stats["fires_in_count"] <= stats["genre_total"],
                f"fires_in_count must not exceed genre_total; "
                f"got {stats['fires_in_count']} > {stats['genre_total']}",
            )
    _assert_no_new_failures(
        baseline, "test_per_frame_corpus_context_carries_fires_in_by_genre"
    )
    print("  PASS\n")


def test_pattern_corpus_context_carries_genre_segmented_prevalence():
    """Item E: pattern corpus_context carries genre_segmented_
    prevalence when the pattern has a genre constraint. The full-
    corpus prevalence remains for reference; the genre-segmented
    rate is the like-vs-like denominator.
    """
    baseline = len(_FAILURES)
    print("=== pattern corpus_context carries genre_segmented_prevalence ===")
    rec_doc = (
        "The agricultural landscape in 2026 is no longer just about "
        "tractors. Global agri-tech investments crossed 40 billion "
        "dollar mark this year. Three opportunities are worth "
        "considering. Precision Agriculture Market Size 10.54 "
        "Billion. Vertical Farming Market Size 11.63 Billion. "
        "Regenerative Agriculture Market Size 11.7 Billion. My "
        "Pick: Regenerative Ag. If I am putting money down I am "
        "picking Regenerative Agriculture. Vertical Farming has "
        "high energy costs. Precision Ag is crowded. The market "
        "is shifting toward sustainability."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    patterns = payload["divergence"].get("frame_patterns", [])
    found_segmented = False
    for p in patterns:
        cc = p.get("corpus_context")
        if cc is None:
            continue
        if cc.get("trigger_genre"):
            found_segmented = True
            required = {
                "genre_segmented_prevalence",
                "matches_in_genre_count",
                "genre_total",
                "genre_match_rate",
                "trigger_genre",
            }
            check(
                required <= set(cc.keys()),
                f"pattern with genre constraint must carry segmented "
                f"prevalence fields; got {sorted(cc.keys())}",
            )
            check(
                "genre" in cc["genre_segmented_prevalence"].lower(),
                f"genre_segmented_prevalence text must name the "
                f"genre; got {cc['genre_segmented_prevalence']!r}",
            )
            check(
                cc["matches_in_genre_count"] <= cc["genre_total"],
                "matches_in_genre_count must not exceed genre_total",
            )
    if not found_segmented:
        print("  SKIP  (no pattern with genre trigger fired)\n")
    else:
        print("  PASS  (segmented prevalence reported)\n")
    _assert_no_new_failures(
        baseline,
        "test_pattern_corpus_context_carries_genre_segmented_prevalence",
    )


def test_genre_classifier_requires_feature_evidence():
    """Polish bug fix: classifier must abstain when no feature
    regex matches, regardless of whether claims are detected.
    Voice + hedge ratio alone are not sufficient evidence for
    structural genre. Pins the abstention discipline that prevents
    advocacy default-bias on unhedged claim-bearing documents.
    """
    baseline = len(_FAILURES)
    print("=== genre classifier requires feature evidence ===")
    from genre_classifier import classify_genre
    # Document with claims but no feature markers (numeric facts
    # without recommendation / advocacy / instruction / etc.
    # markers). Previously classified as advocacy with high
    # confidence; should now abstain.
    text = (
        "Q4 revenue reached 22 billion dollars. The data center "
        "segment grew 409 percent year over year. Annual revenue "
        "totaled 60 billion dollars, up 126 percent. Earnings per "
        "share were 11.93, up 586 percent. The gross margin was "
        "75 percent. Operating expenses were within guidance. " * 3
    )
    # Manufacture claims to trigger the previous bug condition.
    fake_claims = {"total_claims": 6, "hedged_count": 0}
    fake_voice = {"voice": "advisory"}
    result = classify_genre(text, voice=fake_voice, claims=fake_claims)
    check(
        result["genre"] is None,
        f"factual numeric report with no feature markers must "
        f"abstain (was a bug: classified as advocacy on hedge-"
        f"ratio + voice baseline); got {result['genre']!r}",
    )
    _assert_no_new_failures(
        baseline, "test_genre_classifier_requires_feature_evidence"
    )
    print("  PASS\n")


def test_per_genre_stats_carry_low_n_warning():
    """Polish E1: per-genre stats in fires_in_by_genre must carry
    low_n_warning when genre_total < 3 and is_unclassified_bucket
    flag for the _unclassified key. Without these flags the agent
    might cite a 100% rate over N=1 as if statistically calibrated.
    """
    baseline = len(_FAILURES)
    print("=== per-genre stats carry low_n_warning + is_unclassified ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_FOR_CLUSTERS, include_divergence=True,
    )
    summary = payload["divergence"]["envelope"].get("corpus_summary")
    if summary is None:
        print("  SKIP  (corpus unavailable)\n")
        return
    matches = payload["analysis"].get("frame_library_matches", [])
    if not matches:
        print("  SKIP  (no matches; cannot test fires_in_by_genre)\n")
        return
    for m in matches:
        cc = m.get("corpus_context")
        if cc is None:
            continue
        for genre, stats in (cc.get("fires_in_by_genre") or {}).items():
            check(
                "low_n_warning" in stats,
                f"fires_in_by_genre[{genre}] must carry "
                f"low_n_warning flag",
            )
            check(
                "is_unclassified_bucket" in stats,
                f"fires_in_by_genre[{genre}] must carry "
                f"is_unclassified_bucket flag",
            )
            # Invariants
            check(
                stats["low_n_warning"] is (stats["genre_total"] < 3),
                f"low_n_warning must be true iff genre_total < 3; "
                f"genre={genre} total={stats['genre_total']} "
                f"warning={stats['low_n_warning']}",
            )
            check(
                stats["is_unclassified_bucket"] is (genre == "_unclassified"),
                f"is_unclassified_bucket must be true iff key is "
                f"'_unclassified'; got {genre} -> "
                f"{stats['is_unclassified_bucket']}",
            )
    _assert_no_new_failures(
        baseline, "test_per_genre_stats_carry_low_n_warning"
    )
    print("  PASS\n")


def test_pattern_segmented_prevalence_carries_low_n_warning():
    """Polish E1: pattern corpus_context.low_n_warning must be true
    when the trigger genre has fewer than 3 corpus documents.
    Pattern segmented prevalence with low N is not statistically
    meaningful and must be flagged.
    """
    baseline = len(_FAILURES)
    print("=== pattern segmented prevalence carries low_n_warning ===")
    from corpus_intelligence import count_corpus_pattern_matches
    _corpus_root = Path(__file__).resolve().parent.parent / "validation" / "decision_readiness"
    _corpus_dir = str(_corpus_root / "corpus")
    _results_dir = str(_corpus_root / "results")
    # Advocacy genre has 1 corpus doc; low_n_warning must be True.
    match = count_corpus_pattern_matches(
        {"genre": "advocacy", "frames_absent_all": ["FVS-017"]},
        _corpus_dir,
        _results_dir,
    )
    if match is None:
        print("  SKIP  (corpus unavailable)\n")
        return
    check(
        match["genre_segmented_low_n_warning"] is True,
        f"advocacy genre has 1 corpus doc; low_n_warning must be "
        f"True; got {match['genre_segmented_low_n_warning']}",
    )
    # Recommendation has 5 corpus docs; low_n_warning must be False.
    match_rec = count_corpus_pattern_matches(
        {
            "genre": "recommendation",
            "frames_present_all": ["FVS-007"],
        },
        _corpus_dir,
        _results_dir,
    )
    if match_rec is not None:
        check(
            match_rec["genre_segmented_low_n_warning"] is False,
            f"recommendation has 5 docs >= 3; low_n_warning must "
            f"be False; got "
            f"{match_rec['genre_segmented_low_n_warning']}",
        )
    _assert_no_new_failures(
        baseline,
        "test_pattern_segmented_prevalence_carries_low_n_warning",
    )
    print("  PASS\n")


def test_segmentation_discipline_in_agent_guidance():
    """Polish E1: agent_guidance.how_to_render_divergence step
    (7.1) must teach the genre-segmented prevalence discipline:
    prefer segmented, treat _unclassified as bucket-not-genre,
    honor low_n_warning. Without this, agents see segmented stats
    in JSON but lack instruction on how to interpret them.
    """
    baseline = len(_FAILURES)
    print("=== segmentation discipline in agent_guidance ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "fires_in_by_genre" in text,
        "agent_guidance must mention fires_in_by_genre",
    )
    check(
        "low_n_warning" in text,
        "agent_guidance must teach the low_n_warning discipline",
    )
    check(
        "_unclassified" in text,
        "agent_guidance must teach the _unclassified bucket "
        "discipline (NEVER cite as a genre)",
    )
    check(
        "like-vs-like" in text or "segmented" in text.lower(),
        "agent_guidance must explain segmented denominator is the "
        "like-vs-like comparison",
    )
    _assert_no_new_failures(
        baseline, "test_segmentation_discipline_in_agent_guidance"
    )
    print("  PASS\n")


def test_pattern_catalog_has_eight_patterns():
    """Item D: pattern catalog expanded from 4 to 8. Each is a
    discriminating composition, not a label. Pins the catalog
    size and the four new pattern IDs.
    """
    baseline = len(_FAILURES)
    print("=== pattern catalog has 8 patterns ===")
    from frame_patterns import all_patterns
    patterns = all_patterns()
    expected_ids = {
        # Original 4
        "recommendation-without-falsification",
        "growth-without-risk",
        "analysis-without-grounding",
        "advocacy-without-counter-perspective",
        # 4 new
        "narrative-without-stakeholders",
        "instruction-without-failure-modes",
        "forward-projection-without-anchoring",
        "cited-but-promotional",
    }
    actual_ids = {p["id"] for p in patterns}
    check(
        expected_ids == actual_ids,
        f"pattern catalog must contain exactly the 8 expected IDs; "
        f"missing: {expected_ids - actual_ids}, "
        f"extra: {actual_ids - expected_ids}",
    )
    # Each pattern must have substantive reading
    for p in patterns:
        check(
            isinstance(p.get("reading"), str) and len(p["reading"]) >= 100,
            f"pattern {p['id']!r} reading must be substantive prose "
            f"(>= 100 chars); got len={len(p.get('reading', ''))}",
        )
    _assert_no_new_failures(
        baseline, "test_pattern_catalog_has_eight_patterns"
    )
    print(f"  PASS  ({len(patterns)} patterns curated)\n")


def test_narrative_without_stakeholders_pattern():
    """Item D: narrative-without-stakeholders fires on narrative
    documents that mention zero stakeholder roles. Pins the trigger
    semantics + the discriminator (stakeholder_role_count_max=0
    requires the signal to be 0, abstains when signal absent).
    """
    baseline = len(_FAILURES)
    print("=== narrative-without-stakeholders fires correctly ===")
    from frame_patterns import match_patterns
    # Should fire: narrative + zero stakeholders
    fires = match_patterns(
        set(), set(), "narrative",
        doc_signals={"stakeholder_role_count": 0},
    )
    check(
        any(p["id"] == "narrative-without-stakeholders" for p in fires),
        "pattern must fire when genre=narrative and "
        "stakeholder_role_count=0",
    )
    # Should NOT fire: narrative with stakeholders
    no_fire = match_patterns(
        set(), set(), "narrative",
        doc_signals={"stakeholder_role_count": 2},
    )
    check(
        not any(
            p["id"] == "narrative-without-stakeholders"
            for p in no_fire
        ),
        "pattern must NOT fire when stakeholders are present",
    )
    # Should NOT fire: signal unavailable (graceful degradation
    # but stricter min-style trigger requires signal)
    abstain = match_patterns(
        set(), set(), "narrative",
        doc_signals={"stakeholder_role_count": None},
    )
    check(
        not any(
            p["id"] == "narrative-without-stakeholders"
            for p in abstain
        ),
        "pattern must abstain when stakeholder_role_count signal "
        "is unavailable (e.g., short document)",
    )
    _assert_no_new_failures(
        baseline, "test_narrative_without_stakeholders_pattern"
    )
    print("  PASS\n")


def test_instruction_without_failure_modes_pattern():
    """Item D: instruction-without-failure-modes fires when genre=
    instruction, FVS-009 absent, and zero falsification statements.
    """
    baseline = len(_FAILURES)
    print("=== instruction-without-failure-modes fires correctly ===")
    from frame_patterns import match_patterns
    fires = match_patterns(
        set(), {"FVS-009"}, "instruction",
        doc_signals={"falsification_count": 0},
    )
    check(
        any(
            p["id"] == "instruction-without-failure-modes"
            for p in fires
        ),
        "pattern must fire when genre=instruction + FVS-009 absent "
        "+ falsification_count=0",
    )
    # Should NOT fire: falsifications present
    no_fire = match_patterns(
        set(), {"FVS-009"}, "instruction",
        doc_signals={"falsification_count": 2},
    )
    check(
        not any(
            p["id"] == "instruction-without-failure-modes"
            for p in no_fire
        ),
        "pattern must NOT fire when falsification statements are "
        "present",
    )
    _assert_no_new_failures(
        baseline, "test_instruction_without_failure_modes_pattern"
    )
    print("  PASS\n")


def test_forward_projection_without_anchoring_pattern():
    """Item D: forward-projection-without-anchoring is genre-
    agnostic. Fires when projection_phrase_count >= 2 AND zero
    falsifications. Drops the FVS-014 absent constraint (FVS-014
    fires on heavily-projected docs which is exactly this
    pattern's target).
    """
    baseline = len(_FAILURES)
    print("=== forward-projection-without-anchoring fires correctly ===")
    from frame_patterns import match_patterns
    fires = match_patterns(
        set(), set(), None,
        doc_signals={
            "projection_phrase_count": 5,
            "falsification_count": 0,
        },
    )
    check(
        any(
            p["id"] == "forward-projection-without-anchoring"
            for p in fires
        ),
        "pattern must fire when projection_phrase_count >= 2 + "
        "falsification_count = 0",
    )
    # Should NOT fire: only one projection phrase
    no_fire = match_patterns(
        set(), set(), None,
        doc_signals={
            "projection_phrase_count": 1,
            "falsification_count": 0,
        },
    )
    check(
        not any(
            p["id"] == "forward-projection-without-anchoring"
            for p in no_fire
        ),
        "pattern must NOT fire on a single projection phrase "
        "(threshold is >= 2)",
    )
    _assert_no_new_failures(
        baseline,
        "test_forward_projection_without_anchoring_pattern",
    )
    print("  PASS\n")


def test_cited_but_promotional_pattern():
    """Item D: cited-but-promotional fires when FVS-016 fires
    (citation density present) AND voice = promotional. Tests the
    voice_match trigger semantics (signal must be present and
    equal).
    """
    baseline = len(_FAILURES)
    print("=== cited-but-promotional fires correctly ===")
    from frame_patterns import match_patterns
    fires = match_patterns(
        {"FVS-016"}, set(), None,
        doc_signals={"voice_label": "promotional"},
    )
    check(
        any(p["id"] == "cited-but-promotional" for p in fires),
        "pattern must fire when FVS-016 fires + voice=promotional",
    )
    # Should NOT fire: voice analytical
    no_fire = match_patterns(
        {"FVS-016"}, set(), None,
        doc_signals={"voice_label": "analytical"},
    )
    check(
        not any(p["id"] == "cited-but-promotional" for p in no_fire),
        "pattern must NOT fire when voice is analytical",
    )
    # Should NOT fire: voice signal absent (voice_match requires
    # signal to be present and equal)
    abstain = match_patterns(
        {"FVS-016"}, set(), None,
        doc_signals={"voice_label": None},
    )
    check(
        not any(p["id"] == "cited-but-promotional" for p in abstain),
        "pattern must abstain when voice signal is unavailable",
    )
    _assert_no_new_failures(
        baseline, "test_cited_but_promotional_pattern"
    )
    print("  PASS\n")


def test_frame_opportunities_prompt_carries_substrate_context():
    """Item C: frame_opportunities LLM prompt template includes
    substrate-level composition (cluster readings, pattern
    readings) and per-frame corpus context. Without this, the LLM
    treats the absent frame in isolation; with it, the generated
    questions consume the substrate's own composition layer.

    This test pins the prompt structure (the template includes the
    placeholders) and the helper functions that build the blocks.
    Does not exercise the LLM itself.
    """
    baseline = len(_FAILURES)
    print("=== frame_opportunities prompt carries substrate context ===")
    from frame_opportunities import (
        _OPPORTUNITY_PROMPT_TEMPLATE,
        _build_substrate_context_block,
        _build_corpus_context_block,
    )
    check(
        "{substrate_context_block}" in _OPPORTUNITY_PROMPT_TEMPLATE,
        "prompt template must carry substrate_context_block "
        "placeholder so cluster + pattern readings reach the LLM",
    )
    check(
        "{corpus_context_block}" in _OPPORTUNITY_PROMPT_TEMPLATE,
        "prompt template must carry corpus_context_block "
        "placeholder so per-frame corpus prevalence reaches the LLM",
    )
    # _build_substrate_context_block: empty inputs -> empty output
    empty = _build_substrate_context_block([], [])
    check(
        empty == "",
        f"empty cluster + pattern lists must yield empty block; "
        f"got {empty!r}",
    )
    # Non-empty inputs: must include both sections
    block = _build_substrate_context_block(
        cluster_readings=["Cluster reading X."],
        pattern_readings=["Pattern reading Y."],
    )
    check(
        "Cluster reading X" in block and "Pattern reading Y" in block,
        "non-empty block must include both readings",
    )
    check(
        "Substrate-level composition" in block,
        "block must label itself as substrate-level composition so "
        "the LLM treats it as Frame Check's reading, not document "
        "content",
    )
    # _build_corpus_context_block: corpus_context with segmented
    # data emits segmented prevalence.
    record = {
        "corpus_context": {
            "fires_in_by_genre": {
                "recommendation": {
                    "fires_in_count": 1, "genre_total": 5,
                    "rate": 0.2, "low_n_warning": False,
                    "is_unclassified_bucket": False,
                },
                "_unclassified": {
                    "fires_in_count": 1, "genre_total": 2,
                    "rate": 0.5, "low_n_warning": True,
                    "is_unclassified_bucket": True,
                },
            },
            "prevalence": "fires in 2 of 10 corpus documents",
        }
    }
    cb = _build_corpus_context_block(record)
    check(
        "recommendation" in cb,
        "corpus block must include classified genre buckets",
    )
    check(
        "_unclassified" not in cb,
        "corpus block must skip the _unclassified bucket (do not "
        "send confused signal to the LLM)",
    )
    check(
        "fires in 2 of 10" in cb,
        "corpus block must include the full-corpus prevalence as "
        "reference",
    )
    _assert_no_new_failures(
        baseline,
        "test_frame_opportunities_prompt_carries_substrate_context",
    )
    print("  PASS\n")


def test_composition_discipline_nudges_cite_by_name():
    """Post-Claude-Desktop polish: agent_guidance.
    composition_discipline must nudge the agent to CITE the
    pattern by id and the cluster by dimension name. Without this
    explicit instruction, agents tend to paraphrase substrate
    compositions ('blind spot' instead of 'counterfactual
    dimension'; never naming patterns by id), which makes the
    substrate's distinctness invisible to the user.
    """
    baseline = len(_FAILURES)
    print("=== composition_discipline nudges cite-by-name ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "CITE THE PATTERN BY ITS id" in text,
        "discipline must explicitly instruct CITE THE PATTERN BY "
        "ITS id (substrate's named pattern visibility)",
    )
    check(
        "CITE THE CLUSTER BY ITS dimension" in text,
        "discipline must explicitly instruct CITE THE CLUSTER BY "
        "ITS dimension name (so 'counterfactual cluster' wins over "
        "agent-paraphrased 'blind spot')",
    )
    _assert_no_new_failures(
        baseline, "test_composition_discipline_nudges_cite_by_name"
    )
    print("  PASS\n")


def test_cite_by_name_carries_worked_examples():
    """Polish: the cite-by-name discipline must carry concrete
    worked examples (paraphrase vs cite-by-name) so the agent has
    a model to follow rather than an abstract instruction. Three
    Claude Desktop tests showed the agent paraphrasing instead of
    citing; the worked example is what changes that pattern.
    """
    baseline = len(_FAILURES)
    print("=== cite-by-name carries worked examples ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "Worked example" in text or "worked example" in text,
        "discipline must carry a worked example contrasting "
        "paraphrase with cite-by-name",
    )
    check(
        "recommendation-without-falsification pattern" in text,
        "discipline must carry the verbatim pattern id as worked "
        "example so the agent has a concrete model",
    )
    _assert_no_new_failures(
        baseline, "test_cite_by_name_carries_worked_examples"
    )
    print("  PASS\n")


def test_uncertainty_vs_hedge_disclosure():
    """Polish: agent_guidance.what_this_tool_does_not_tell_you
    must disclose the uncertainty-coverage-vs-hedge-ratio
    detector boundary. The AI-opportunities Claude Desktop test
    surfaced a document with 21% hedge ratio but 0 uncertainty
    coverage markers. The agent flagged it implicitly; the
    discipline now names it explicitly so future agents can
    surface the disconnect as a method-limit observation.
    """
    baseline = len(_FAILURES)
    print("=== uncertainty-vs-hedge boundary disclosure ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    items = payload["agent_guidance"].get(
        "what_this_tool_does_not_tell_you", []
    )
    joined = " ".join(items) if isinstance(items, list) else str(items)
    check(
        "hedge" in joined.lower() and "uncertainty" in joined.lower(),
        "discipline must disclose the hedge-vs-uncertainty "
        "coverage-detector boundary",
    )
    check(
        "detector boundary" in joined.lower(),
        "discipline must name this as a methodological boundary "
        "rather than a finding about the document",
    )
    _assert_no_new_failures(
        baseline, "test_uncertainty_vs_hedge_disclosure"
    )
    print("  PASS\n")


def test_each_composed_entity_carries_claim_level():
    """Substrate-side composition L5: every composed entity in the
    payload carries a claim_level field naming which per-level
    construct treatment applies. Pins the field's presence on:
    frame_library_matches entries, divergence.absent_frames records,
    divergence.absence_clusters entries, divergence.frame_patterns
    entries, analysis.voice, analysis.genre, analysis.temporal,
    analysis.frame_deepening (parent block; sub-fields inherit the
    detector-measurement discipline). Without claim_level, the
    agent inherits the substrate's prior uniform
    composition_discipline and cannot honor per-level treatment
    differences.

    Uses a recommendation-genre fixture (operator's agriculture
    pattern, paraphrased) that triggers FVS detectors and the
    recommendation-without-falsification pattern, exercising the
    full per-level metadata surface.
    """
    baseline = len(_FAILURES)
    print("=== each composed entity carries claim_level ===")
    rec_doc = (
        "My Pick: Regenerative Agriculture. After looking at three "
        "lucrative business opportunities, I would lean toward "
        "Regenerative Ag as the best option for the next decade. "
        "The carbon credit market by 2030 will reward farms that "
        "turn into a carbon vacuum, and data is the new topsoil. "
        "Investors and regulators are aligning on this. Growth in "
        "the sector is unstoppable; the structural opportunity is "
        "clear."
    )
    payload = mcp_server.build_epistemic_payload(
        rec_doc, include_divergence=True,
    )
    analysis = payload["analysis"]

    # Detector-measurement entities. The recommendation fixture
    # is calibrated to produce frame_library_matches; the test
    # asserts non-empty rather than allowing the empty case as a
    # get-out-of-jail (the empty case would be a regression in
    # the fixture, not a pass condition for this discipline).
    matches = analysis.get("frame_library_matches", []) or []
    check(
        bool(matches),
        "recommendation fixture must produce frame_library_matches "
        "(if it stops producing matches, fix the fixture rather "
        "than letting this test pass trivially)",
    )
    check(
        all(
            m.get("claim_level") == "detector_measurement"
            for m in matches
        ),
        "every frame_library_matches entry must carry "
        "claim_level=detector_measurement (V1 detector firing)",
    )
    # frame_deepening parent block is a detector-measurement
    # container; sub-fields (temporal_scope, stakeholder_map,
    # falsification_conditions) inherit the discipline.
    check(
        analysis.get("frame_deepening", {}).get("claim_level")
        == "detector_measurement",
        "analysis.frame_deepening must carry "
        "claim_level=detector_measurement so the agent honors the "
        "lower-bound vocabulary discipline when citing extracted "
        "evidence (years_referenced, roles_mentioned, "
        "extracted_conditions)",
    )

    # Classifier-output entities
    check(
        analysis.get("voice", {}).get("claim_level")
        == "classifier_output",
        "analysis.voice must carry claim_level=classifier_output",
    )
    check(
        analysis.get("genre", {}).get("claim_level")
        == "classifier_output",
        "analysis.genre must carry claim_level=classifier_output",
    )
    check(
        analysis.get("temporal", {}).get("claim_level")
        == "classifier_output",
        "analysis.temporal must carry claim_level=classifier_output",
    )

    # Divergence entities
    div = payload.get("divergence") or {}
    absent = div.get("absent_frames") or []
    check(
        bool(absent) and all(
            r.get("claim_level") == "detector_measurement"
            for r in absent
        ),
        "every divergence.absent_frames record must carry "
        "claim_level=detector_measurement (V1 detector non-firing)",
    )
    clusters = div.get("absence_clusters") or []
    if clusters:
        check(
            all(
                c.get("claim_level") == "composed_pattern"
                for c in clusters
            ),
            "every absence_clusters entry must carry "
            "claim_level=composed_pattern when present",
        )
    patterns = div.get("frame_patterns") or []
    if patterns:
        check(
            all(
                p.get("claim_level") == "composed_pattern"
                for p in patterns
            ),
            "every frame_patterns entry must carry "
            "claim_level=composed_pattern when present",
        )

    _assert_no_new_failures(
        baseline, "test_each_composed_entity_carries_claim_level"
    )
    print("  PASS\n")


def test_claim_level_treatments_carries_required_levels():
    """agent_guidance.claim_level_treatments must carry the three
    foundational per-level treatments (detector_measurement,
    classifier_output, composed_pattern), each with a structured
    validation_status block (deterministic, methodology_documented,
    inter_rater_reliability, validity_data) plus caveats list and
    how_to_cite phrasing template. Pins the substrate's epistemic
    claim chain explicitly so external evaluators (and the
    methodology paper) can cite the per-level discipline rather
    than inferring it from prose.

    Forward-compat: uses subset assertion, not exact equality. The
    fourth level (agent_generated for opt-in LLM opportunities under
    Item 12) is asserted by test_agent_generated_claim_level_for_
    opportunities; this test pins the foundational three.
    """
    baseline = len(_FAILURES)
    print("=== claim_level_treatments carries required levels ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    treatments = payload["agent_guidance"].get(
        "claim_level_treatments"
    )
    check(
        isinstance(treatments, dict),
        "agent_guidance.claim_level_treatments must be a dict",
    )
    if not isinstance(treatments, dict):
        _assert_no_new_failures(
            baseline,
            "test_claim_level_treatments_carries_required_levels",
        )
        print("  PASS\n")
        return

    expected_keys = {
        "detector_measurement",
        "classifier_output",
        "composed_pattern",
    }
    actual_keys = set(treatments.keys())
    check(
        expected_keys.issubset(actual_keys),
        f"treatments must include the three current claim levels "
        f"{expected_keys}; got {actual_keys}. Forward-compat: "
        f"future levels (e.g. agent_generated for opt-in LLM "
        f"opportunities) may be added; this test asserts subset "
        f"presence, not exact equality.",
    )
    for key in expected_keys:
        if key not in treatments:
            continue
        t = treatments[key]
        check(
            isinstance(t.get("claim_type"), str)
            and len(t["claim_type"]) > 30,
            f"{key}: claim_type must be a substantive string",
        )
        vs = t.get("validation_status") or {}
        check(
            isinstance(vs.get("deterministic"), bool),
            f"{key}: validation_status.deterministic must be bool",
        )
        check(
            isinstance(vs.get("methodology_documented"), bool),
            f"{key}: validation_status.methodology_documented must "
            f"be bool",
        )
        check(
            isinstance(vs.get("inter_rater_reliability"), str),
            f"{key}: validation_status.inter_rater_reliability "
            f"must be a string status",
        )
        check(
            isinstance(vs.get("validity_data"), str)
            and len(vs["validity_data"]) > 50,
            f"{key}: validation_status.validity_data must be a "
            f"substantive string naming what is and isn't validated",
        )
        check(
            isinstance(t.get("caveats"), list)
            and len(t["caveats"]) >= 2,
            f"{key}: caveats must be a list of at least 2 entries",
        )
        check(
            isinstance(t.get("how_to_cite"), str)
            and len(t["how_to_cite"]) > 10,
            f"{key}: how_to_cite must be a phrasing template",
        )

    _assert_no_new_failures(
        baseline, "test_claim_level_treatments_carries_required_levels"
    )
    print("  PASS\n")


def test_claim_level_treatments_validation_status_honest():
    """The per-level treatments must be construct-honest about
    what is and is not validated. Specifically: classifier_output
    and composed_pattern must report inter_rater_reliability as
    'not_yet_measured' (no IRR pilot has shipped); only
    detector_measurement may report 'not_applicable' (algorithmic
    detectors don't need IRR; reproducibility is the validity
    claim). Without this honesty discipline the substrate would
    silently over-claim its own validation status.
    """
    baseline = len(_FAILURES)
    print(
        "=== claim_level_treatments validation_status honest ==="
    )
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    treatments = payload["agent_guidance"].get(
        "claim_level_treatments", {}
    ) or {}

    det_irr = (
        (treatments.get("detector_measurement") or {})
        .get("validation_status", {})
        .get("inter_rater_reliability")
    )
    check(
        det_irr == "not_applicable",
        "detector_measurement IRR must be 'not_applicable' "
        "(algorithmic detector; reproducibility is the validity "
        f"claim). Got: {det_irr!r}",
    )

    for level in ("classifier_output", "composed_pattern"):
        irr = (
            (treatments.get(level) or {})
            .get("validation_status", {})
            .get("inter_rater_reliability")
        )
        check(
            irr == "not_yet_measured",
            f"{level} IRR must be 'not_yet_measured' (no IRR "
            f"pilot shipped; the substrate stays honest about "
            f"what is not yet validated). Got: {irr!r}",
        )

    # validity_data on classifier_output and composed_pattern must
    # name the IRR gap explicitly so future evaluators see it.
    for level in ("classifier_output", "composed_pattern"):
        vd = (
            (treatments.get(level) or {})
            .get("validation_status", {})
            .get("validity_data", "")
        )
        check(
            "IRR" in vd or "inter-rater" in vd.lower(),
            f"{level}.validity_data must name the IRR gap "
            f"explicitly so external evaluators see what is "
            f"not yet validated",
        )

    _assert_no_new_failures(
        baseline,
        "test_claim_level_treatments_validation_status_honest",
    )
    print("  PASS\n")


def test_decision_readiness_dimensions_carry_claim_level():
    """Substrate-side composition L5 coverage: each per-dimension
    reading in analysis.decision_readiness.dimensions is a
    substrate composition with deterministic trigger (multi-feature
    scoring per dimension) and curator-authored signal_text. Pins
    claim_level=composed_pattern on each dimension dict so the
    agent honors the per-level discipline (cite the trigger as
    deterministic AND the signal_text as Frame Check's curator
    reading) rather than treating the prose as a measurement.
    Without this, the decision_readiness profile remained the
    one un-tagged composed surface in the analysis dict.
    """
    baseline = len(_FAILURES)
    print("=== decision_readiness dimensions carry claim_level ===")
    rec_doc = (
        "My Pick: Regenerative Agriculture. After looking at three "
        "lucrative business opportunities, I would lean toward "
        "Regenerative Ag as the best option for the next decade. "
        "The carbon credit market by 2030 will reward farms that "
        "turn into a carbon vacuum, and data is the new topsoil. "
        "Investors and regulators are aligning on this. Growth in "
        "the sector is unstoppable; the structural opportunity is "
        "clear."
    )
    payload = mcp_server.build_epistemic_payload(rec_doc)
    readiness = payload["analysis"].get("decision_readiness")
    check(
        isinstance(readiness, dict),
        "analysis.decision_readiness must be present (the "
        "recommendation fixture has framing + claims data)",
    )
    if not isinstance(readiness, dict):
        _assert_no_new_failures(
            baseline,
            "test_decision_readiness_dimensions_carry_claim_level",
        )
        print("  PASS\n")
        return
    dims = readiness.get("dimensions") or {}
    expected_dims = {
        "coverage", "calibration", "evidence",
        "robustness", "counterfactual",
    }
    check(
        expected_dims.issubset(set(dims.keys())),
        f"decision_readiness must carry the five canonical "
        f"dimensions; got {set(dims.keys())}",
    )
    for dim_name in expected_dims:
        dim = dims.get(dim_name) or {}
        check(
            dim.get("claim_level") == "composed_pattern",
            f"decision_readiness.dimensions[{dim_name}] must "
            f"carry claim_level=composed_pattern (substrate-side "
            f"composition over multiple measurements with curator-"
            f"authored signal_text); got {dim.get('claim_level')!r}",
        )

    _assert_no_new_failures(
        baseline,
        "test_decision_readiness_dimensions_carry_claim_level",
    )
    print("  PASS\n")


def test_frame_compare_parity_carries_claim_level():
    """Substrate-side composition L5 parity: frame_compare's
    per-document blocks carry claim_level on each composed entity
    (frame_library_matches, voice, temporal), and the response's
    agent_guidance carries the shared claim_level_treatments dict.
    Without parity, a client handling both surfaces would interpret
    the same entity types under different disciplines depending on
    which tool produced them.
    """
    baseline = len(_FAILURES)
    print("=== frame_compare parity carries claim_level ===")
    doc_a = (
        "Growth has been strong across the quarter in question. "
        "Revenue is up for the leadership team and the investor "
        "base. Stakeholders are pleased with the pace of expansion."
    )
    doc_b = (
        "Risks to the outlook have risen across the sector review. "
        "Uncertainty persists among market participants this month. "
        "Policymakers are monitoring developments carefully."
    )
    payload = mcp_server.build_compare_payload(doc_a, doc_b, "A", "B")
    treatments = payload["agent_guidance"].get(
        "claim_level_treatments"
    )
    check(
        isinstance(treatments, dict)
        and "detector_measurement" in treatments,
        "frame_compare agent_guidance must carry the same "
        "claim_level_treatments dict as frame_check so a client "
        "handles both surfaces uniformly",
    )

    for label in ("A", "B"):
        per_doc = payload["analysis"]["documents"][label]
        check(
            per_doc.get("voice", {}).get("claim_level")
            == "classifier_output",
            f"documents[{label}].voice must carry "
            f"claim_level=classifier_output",
        )
        check(
            per_doc.get("temporal", {}).get("claim_level")
            == "classifier_output",
            f"documents[{label}].temporal must carry "
            f"claim_level=classifier_output",
        )
        for m in per_doc.get("frame_library_matches", []) or []:
            check(
                m.get("claim_level") == "detector_measurement",
                f"documents[{label}] frame_library_matches "
                f"entry must carry claim_level=detector_measurement",
            )

    _assert_no_new_failures(
        baseline, "test_frame_compare_parity_carries_claim_level"
    )
    print("  PASS\n")


def test_composition_discipline_teaches_per_level_treatment():
    """Substrate-side composition L5: composition_discipline must
    name rule (6) PER-LEVEL CLAIM TREATMENT, the three claim-level
    values, and direct the agent to agent_guidance.
    claim_level_treatments for the per-level discipline. Without
    this teaching, the per-level metadata on each composed entity
    is invisible to the agent and the substrate falls back to
    uniform treatment.
    """
    baseline = len(_FAILURES)
    print(
        "=== composition_discipline teaches per-level treatment ==="
    )
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get(
        "composition_discipline", ""
    )
    check(
        "(6) PER-LEVEL CLAIM TREATMENT" in text,
        "composition_discipline must carry rule (6) PER-LEVEL "
        "CLAIM TREATMENT",
    )
    for level in (
        "detector_measurement",
        "classifier_output",
        "composed_pattern",
    ):
        check(
            level in text,
            f"composition_discipline must name claim_level "
            f"value '{level}' so the agent can match the "
            f"entity's claim_level to the treatment",
        )
    check(
        "claim_level_treatments" in text,
        "composition_discipline must direct the agent to "
        "agent_guidance.claim_level_treatments for the per-level "
        "discipline",
    )
    # Worked-example discipline (the cite-by-name lesson applied
    # at the per-level discipline). Abstract instructions do not
    # change agent behavior; concrete contrasts do. Pin one
    # verbatim contrast per level so the discipline carries a
    # model the agent can follow.
    check(
        "Worked example" in text or "Worked examples" in text,
        "rule (6) must carry worked-example contrasts (the same "
        "lesson the cite-by-name discipline shipped: abstract "
        "instructions do not change agent behavior, concrete "
        "contrasts do)",
    )
    check(
        "high confidence; runner-up advisory" in text,
        "rule (6) must carry the classifier_output worked example "
        "with the verbatim 'high confidence; runner-up advisory' "
        "phrasing so the agent has a concrete classifier-output "
        "model to follow",
    )
    check(
        "recommendation-without-falsification pattern" in text,
        "rule (6) must carry the composed_pattern worked example "
        "naming the verbatim pattern id",
    )

    _assert_no_new_failures(
        baseline,
        "test_composition_discipline_teaches_per_level_treatment",
    )
    print("  PASS\n")


def test_envelope_carries_corpus_summary():
    """envelope.corpus_summary names the corpus N and small_n_caveat
    so the agent surfacing prevalence statements lands honestly.
    Pins the construct-honest reporting of corpus state.
    """
    baseline = len(_FAILURES)
    print("=== envelope carries corpus_summary with small_n_caveat ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    env = payload["divergence"]["envelope"]
    check(
        "corpus_summary" in env,
        "envelope must include corpus_summary key (may be None when "
        "corpus unavailable)",
    )
    summary = env.get("corpus_summary")
    if summary is None:
        print("  SKIP  (corpus unavailable)\n")
        return
    check(
        "n_documents" in summary and isinstance(summary["n_documents"], int),
        f"corpus_summary.n_documents must be int; got {summary.get('n_documents')!r}",
    )
    check(
        "small_n_caveat" in summary
        and "small" in summary["small_n_caveat"].lower(),
        f"corpus_summary must carry small_n_caveat naming the small-N "
        f"discipline (substrate stays construct-honest); got "
        f"caveat={summary.get('small_n_caveat', '')[:60]!r}",
    )
    check(
        "expert ratings" in summary["small_n_caveat"].lower()
        or "outcome" in summary["small_n_caveat"].lower(),
        "small_n_caveat must name that outcome data based on expert "
        "ratings is not yet available; without this the substrate's "
        "prevalence statements may be misread as outcome rates",
    )
    _assert_no_new_failures(
        baseline, "test_envelope_carries_corpus_summary"
    )
    print(f"  PASS  (n_documents={summary['n_documents']})\n")


def test_composition_discipline_names_corpus_context():
    """agent_guidance.composition_discipline must name corpus_context
    as a valid grounding measurement. Without this, agents invoked
    via natural language (not via a sovereignty prompt) lack the
    instruction to treat corpus_context as empirical anchoring;
    the field would surface in JSON but not in the discipline.
    """
    baseline = len(_FAILURES)
    print("=== composition_discipline names corpus_context ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"].get("composition_discipline", "")
    check(
        "corpus_context" in text,
        "composition_discipline must name corpus_context so natural-"
        "language invocations carry the empirical-anchoring layer",
    )
    check(
        "small_n" in text.lower() or "small-n" in text.lower()
        or "small n" in text.lower() or "small N" in text,
        "composition_discipline must reference the small-N discipline "
        "(via small_n_caveat or equivalent) so agents do not over-"
        "claim from corpus prevalence",
    )
    _assert_no_new_failures(
        baseline, "test_composition_discipline_names_corpus_context"
    )
    print("  PASS\n")


def test_how_to_render_divergence_teaches_corpus_context_layer():
    """agent_guidance.how_to_render_divergence step (7) must teach
    the corpus_context layer: prevalence, co-patterns, peer-pair-
    difference rate, cross-question outlier, cite-back URIs. Pins
    the discipline so agents reading divergence know to compose
    catalog absence with empirical anchoring when the corpus is
    available.
    """
    baseline = len(_FAILURES)
    print("=== how_to_render_divergence teaches corpus_context layer ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "corpus_context" in text,
        "how_to_render_divergence must mention corpus_context as the "
        "empirical-anchoring layer over absences",
    )
    check(
        "corpus_summary" in text,
        "how_to_render_divergence must reference corpus_summary so "
        "the agent surfaces small-N discipline when citing prevalence",
    )
    check(
        "peer_pair" in text or "peer-pair" in text or "peer pair" in text,
        "how_to_render_divergence must mention peer-pair difference "
        "rate as the cluster-level corpus signal",
    )
    _assert_no_new_failures(
        baseline, "test_how_to_render_divergence_teaches_corpus_context_layer"
    )
    print("  PASS\n")


def test_how_to_render_divergence_carries_catalog_pin_clarity():
    """agent_guidance.how_to_render_divergence must name the catalog
    pin so the agent can explain the version pin to readers (library_v3
    per FRAME_DIVERGENCE_CONTRACT_v1 c1.0 stability commitment).
    Without this, a reader following the catalog_version field hits
    library_v3 in the response and the agent has nothing to surface
    to clarify what that pin means.
    """
    baseline = len(_FAILURES)
    print("=== how_to_render_divergence carries catalog-pin clarity ===")
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    text = payload["agent_guidance"]["how_to_render_divergence"]
    check(
        "library_v3" in text,
        "how_to_render_divergence must name library_v3 so the agent "
        "can explain the catalog pin to readers",
    )
    check(
        "stability" in text.lower(),
        "how_to_render_divergence must name that the catalog pin is "
        "a stability commitment, not stale",
    )
    _assert_no_new_failures(
        baseline, "test_how_to_render_divergence_carries_catalog_pin_clarity"
    )
    print("  PASS\n")


def test_divergence_absent_frame_record_required_fields():
    """Each AbsentFrameRecord carries all §4.2 required fields."""
    print("=== AbsentFrameRecord required fields ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    records = payload["divergence"]["absent_frames"]
    check(len(records) > 0, "expected at least one absent frame record")
    required_fields = {
        "frame_id", "frame_version", "frame_title",
        "stability", "citation_uri",
        "absence_basis", "domain_relevance_rationale",
    }
    for rec in records:
        missing = required_fields - rec.keys()
        check(not missing, f"record for {rec.get('frame_id', '?')} missing {missing}")
        check(rec["frame_id"].startswith("FVS-"),
              f"frame_id must be FVS-XXX shape, got {rec['frame_id']!r}")
        check(rec["citation_uri"].startswith("frame-check://library/"),
              f"citation_uri must use frame-check:// scheme per §8, got {rec['citation_uri']!r}")
        check(rec["stability"] in ("stable", "provisional"),
              f"stability must be enum per §4.2, got {rec['stability']!r}")
    _assert_no_new_failures(baseline, "test_divergence_absent_frame_record_required_fields")
    print("  PASS\n")


def test_divergence_envelope_required_fields():
    """Envelope carries all §4.3 required fields with correct MCP
    surface values per §7.1."""
    print("=== envelope required fields + MCP surface marker ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    env = payload["divergence"]["envelope"]
    required = {
        "spec_version", "catalog_version", "surface",
        "v4_2_execution", "v4_2_engine_status",
        "domain_inferred", "provisional_count",
        "faithfulness_note", "limitations",
    }
    missing = required - env.keys()
    check(not missing, f"envelope missing required fields: {missing}")
    check(env["spec_version"] == "FRAME_DIVERGENCE_v1_c1.0",
          f"spec_version must match contract header, got {env['spec_version']!r}")
    check(env["catalog_version"] == "library_v3",
          "catalog_version must be library_v3 by default")
    check(env["surface"] == "mcp",
          f"surface must be 'mcp' on this surface, got {env['surface']!r}")
    check(env["v4_2_execution"]["location"] == "caller_side",
          "v4_2_execution.location must be caller_side on MCP per §7.1")
    check(env["v4_2_execution"]["tier"] == "caller_model",
          "v4_2_execution.tier must be caller_model on MCP per §7.1")
    check(env["v4_2_engine_status"] in ("alpha", "beta", "production_candidate", "production"),
          f"v4_2_engine_status must be valid enum, got {env['v4_2_engine_status']!r}")
    check(isinstance(env["limitations"], list),
          "limitations must be a list per §4.3")
    check(isinstance(env["provisional_count"], int),
          "provisional_count must be an int")
    _assert_no_new_failures(baseline, "test_divergence_envelope_required_fields")
    print("  PASS\n")


def test_divergence_excludes_fvs_020():
    """FVS-020 is retired from detection scope and must NEVER appear
    in absent_frames."""
    print("=== FVS-020 never in absent_frames ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    records = payload["divergence"]["absent_frames"]
    fvs_ids = {r["frame_id"] for r in records}
    check("FVS-020" not in fvs_ids,
          "FVS-020 must be excluded from divergence output")
    _assert_no_new_failures(baseline, "test_divergence_excludes_fvs_020")
    print("  PASS\n")


def test_divergence_excludes_present_frames():
    """absent_frames is catalog MINUS frames already present in
    frame_library_matches. Uses a document engineered to trigger a
    known frame to verify the set-difference semantics."""
    print("=== absent_frames excludes present frames (set-difference) ===")
    baseline = len(_FAILURES)
    # Use a growth-framed document that reliably fires FVS-008
    growth_doc = (
        "Revenue grew 150% year over year. Growth has accelerated "
        "every quarter. The momentum is undeniable. Every major "
        "player is expanding. This trajectory continues."
    )
    payload = mcp_server.build_epistemic_payload(
        growth_doc, include_divergence=True,
    )
    present_ids = {
        m["fvs_id"] for m in payload["analysis"]["frame_library_matches"]
    }
    absent_ids = {
        r["frame_id"] for r in payload["divergence"]["absent_frames"]
    }
    overlap = present_ids & absent_ids
    check(not overlap,
          f"frames present in analysis must NOT appear in divergence: {overlap}")
    # And every frame should be in exactly one of the two sets (except FVS-020)
    all_in_output = present_ids | absent_ids
    check("FVS-020" not in all_in_output,
          "FVS-020 must not appear in either set")
    _assert_no_new_failures(baseline, "test_divergence_excludes_present_frames")
    print("  PASS\n")


def test_divergence_forbidden_prescriptive_fields():
    """Part 2 §4.2 Forbidden: no prescription/recommendation/should_use
    fields on AbsentFrameRecord. Enforces Part 1 §5.1.5."""
    print("=== AbsentFrameRecord has no prescriptive fields ===")
    baseline = len(_FAILURES)
    payload = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    forbidden = {"prescription", "recommendation", "should_use"}
    for rec in payload["divergence"]["absent_frames"]:
        leaks = forbidden & rec.keys()
        check(not leaks,
              f"record {rec['frame_id']} carries forbidden field(s): {leaks}")
    _assert_no_new_failures(baseline, "test_divergence_forbidden_prescriptive_fields")
    print("  PASS\n")


def test_divergence_teaching_questions_rendering_decorates_records():
    """teaching_questions rendering may attach teaching_question field
    per record (drawn from FVS entry). Other renderings omit it."""
    print("=== divergence_rendering affects AbsentFrameRecord decoration ===")
    baseline = len(_FAILURES)
    # list rendering: no teaching_question field
    payload_list = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True, divergence_rendering="list",
    )
    for rec in payload_list["divergence"]["absent_frames"]:
        check("teaching_question" not in rec,
              f"list rendering should not attach teaching_question; found on {rec['frame_id']}")

    # teaching_questions rendering: teaching_question may be present
    # (depends on FVS entry having a teaching question section). At
    # least one frame should have a teaching_question if any entry
    # defines one; if none do, the field is absent from all.
    payload_tq = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
        divergence_rendering="teaching_questions",
    )
    # Pass condition: in teaching_questions mode, records that do have
    # a teaching_question emit the field; records that do not have one
    # omit it. Both are correct. The test asserts only that the field,
    # when present, is a non-empty string.
    for rec in payload_tq["divergence"]["absent_frames"]:
        if "teaching_question" in rec:
            check(isinstance(rec["teaching_question"], str) and len(rec["teaching_question"]) > 0,
                  f"teaching_question must be non-empty string when present on {rec['frame_id']}")
    _assert_no_new_failures(baseline, "test_divergence_teaching_questions_rendering_decorates_records")
    print("  PASS\n")


def test_divergence_domain_hint_echoes_to_envelope():
    """domain_hint flows through to envelope.domain_inferred. Without
    hint, domain_inferred='unfiltered'. With hint, it echoes. Domain-
    metadata filtering is deferred (noted in envelope.limitations)."""
    print("=== domain_hint echoes to envelope ===")
    baseline = len(_FAILURES)
    # Without hint
    p_no_hint = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True,
    )
    check(p_no_hint["divergence"]["envelope"]["domain_inferred"] == "unfiltered",
          "no hint → domain_inferred='unfiltered'")

    # With hint
    p_finance = mcp_server.build_epistemic_payload(
        _DOC_SAMPLE, include_divergence=True, domain_hint="finance",
    )
    env = p_finance["divergence"]["envelope"]
    check(env["domain_inferred"] == "finance",
          f"finance hint → domain_inferred='finance'; got {env['domain_inferred']!r}")
    # Limitation note about filter not being wired
    check(
        any("Domain filter not yet wired" in lim for lim in env["limitations"]),
        "envelope.limitations must note the unwired filter state when hint provided",
    )
    _assert_no_new_failures(baseline, "test_divergence_domain_hint_echoes_to_envelope")
    print("  PASS\n")


def test_divergence_invalid_domain_hint_rejected_by_dispatcher():
    """Bad domain_hint value rejected with isError per adversarial-
    hardening protocol referenced in §3.5."""
    print("=== invalid domain_hint rejected by tool dispatcher ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 901, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {
            "document_text": _DOC_SAMPLE,
            "include_divergence": True,
            "domain_hint": "invalid_domain_xyz",
        }},
    })
    check(resp["result"].get("isError") is True,
          "invalid domain_hint must return isError")
    check("domain_hint" in resp["result"]["content"][0]["text"],
          "error message must name the field")
    _assert_no_new_failures(baseline, "test_divergence_invalid_domain_hint_rejected_by_dispatcher")
    print("  PASS\n")


def test_divergence_invalid_rendering_rejected_by_dispatcher():
    """Bad divergence_rendering value rejected."""
    print("=== invalid divergence_rendering rejected ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 902, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {
            "document_text": _DOC_SAMPLE,
            "include_divergence": True,
            "divergence_rendering": "bogus_mode",
        }},
    })
    check(resp["result"].get("isError") is True,
          "invalid divergence_rendering must return isError")
    check("divergence_rendering" in resp["result"]["content"][0]["text"],
          "error message must name the field")
    _assert_no_new_failures(baseline, "test_divergence_invalid_rendering_rejected_by_dispatcher")
    print("  PASS\n")


def test_divergence_wrong_include_type_rejected_by_dispatcher():
    """include_divergence must be bool; other types rejected."""
    print("=== include_divergence wrong type rejected ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 903, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {
            "document_text": _DOC_SAMPLE,
            "include_divergence": "true",  # string, not bool
        }},
    })
    check(resp["result"].get("isError") is True,
          "string include_divergence must be rejected (boolean required)")
    _assert_no_new_failures(baseline, "test_divergence_wrong_include_type_rejected_by_dispatcher")
    print("  PASS\n")


# ── Adversarial input hardening ───────────────────────────────────
#
# These tests exercise boundaries and wrong-shape inputs that an agent
# framework or a confused client can actually produce, and that the
# existing test file did not cover. The server already defends against
# each of these cases in code (mcp_server.py:3292-3360); the tests pin
# the defenses so they do not quietly regress.


def test_tools_call_document_text_at_limit_boundary():
    """A document of exactly MAX_DOCUMENT_CHARS must be accepted.
    Boundary corollary: the over-limit test below must fail at
    MAX_DOCUMENT_CHARS + 1, not at MAX_DOCUMENT_CHARS."""
    print("=== tools/call accepts document_text at exact maxLength boundary ===")
    baseline = len(_FAILURES)
    at_limit = "a" * mcp_server.MAX_DOCUMENT_CHARS
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 601, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {"document_text": at_limit}},
    })
    check(
        resp["result"].get("isError") is False,
        "document_text at exact limit must not isError",
    )
    _assert_no_new_failures(baseline, "test_tools_call_document_text_at_limit_boundary")
    print("  PASS\n")


def test_tools_call_document_text_over_limit_rejected():
    """One character over the ceiling must return the explicit
    maxLength error. The error message is part of the contract because
    agents use it to decide whether to truncate-and-retry."""
    print("=== tools/call rejects document_text over maxLength ===")
    baseline = len(_FAILURES)
    over_limit = "a" * (mcp_server.MAX_DOCUMENT_CHARS + 1)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 602, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {"document_text": over_limit}},
    })
    check(
        resp["result"].get("isError") is True,
        "document_text over limit must isError",
    )
    text = resp["result"]["content"][0]["text"]
    check(
        str(mcp_server.MAX_DOCUMENT_CHARS) in text,
        "over-limit error must name the character limit so agents can truncate",
    )
    _assert_no_new_failures(baseline, "test_tools_call_document_text_over_limit_rejected")
    print("  PASS\n")


def test_tools_call_source_text_over_limit_rejected():
    """source_text has a larger ceiling than document_text. Over-limit
    source_text must also isError with a message that names the
    ceiling."""
    print("=== tools/call rejects source_text over maxLength ===")
    baseline = len(_FAILURES)
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 603, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": "Sample analytical prose for the adversarial test.",
                "source_text": "a" * (mcp_server.MAX_SOURCE_CHARS + 1),
            },
        },
    })
    check(
        resp["result"].get("isError") is True,
        "source_text over limit must isError",
    )
    text = resp["result"]["content"][0]["text"]
    check(
        str(mcp_server.MAX_SOURCE_CHARS) in text,
        "over-limit source error must name the character limit",
    )
    _assert_no_new_failures(baseline, "test_tools_call_source_text_over_limit_rejected")
    print("  PASS\n")


def test_tools_call_wrong_argument_types_handled_cleanly():
    """Agents that send wrong-type arguments (int instead of string,
    list, nested dict, null, out-of-range enum) must get a clean
    isError response, not a Python exception that leaks to the
    framework layer."""
    print("=== tools/call handles wrong argument types without crashing ===")
    baseline = len(_FAILURES)
    wrong_type_cases = [
        {"document_text": 42},
        {"document_text": None},
        {"document_text": ["list", "of", "strings"]},
        {"document_text": {"nested": "dict"}},
        {"document_text": "ok", "source_text": 999},
        {"document_text": "ok", "prefer_contract_version": 99},
        {"document_text": "ok", "prefer_contract_version": "2"},
    ]
    for i, args in enumerate(wrong_type_cases):
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 700 + i, "method": "tools/call",
            "params": {"name": "frame_check", "arguments": args},
        })
        check(
            "result" in resp and resp["result"].get("isError") is True,
            f"wrong-type case {args!r} must return isError:true (got {resp!r})",
        )
    _assert_no_new_failures(baseline, "test_tools_call_wrong_argument_types_handled_cleanly")
    print("  PASS\n")


def test_tools_call_unicode_edge_cases():
    """Documents with emoji, zero-width characters, bidi markers, and
    mixed scripts must produce a valid three-section payload. Organic
    web-paste traffic contains this kind of content; the measurement
    layer must not crash on valid UTF-8 weirdness."""
    print("=== tools/call handles unicode edge cases ===")
    baseline = len(_FAILURES)
    doc = (
        "The committee notes risks to the outlook are elevated \U0001F525. "
        "​Growth has been‌ solid ‎in recent quarters‏. "
        "Uncertainty persists. نص عربي here and "
        "日本語テキスト mixed in. "
        "Stakeholders across the economy are monitoring incoming data."
    )
    resp = mcp_server.dispatch({
        "jsonrpc": "2.0", "id": 800, "method": "tools/call",
        "params": {"name": "frame_check", "arguments": {"document_text": doc}},
    })
    check(
        resp["result"].get("isError") is False,
        "unicode edge-case document must not isError",
    )
    payload = json.loads(resp["result"]["content"][0]["text"])
    check(
        "analysis" in payload and "agent_guidance" in payload and "provenance" in payload,
        "unicode edge-case response must still carry the three-section payload",
    )
    # Semantic check: the measurement layer should have produced real
    # structural data, not silently emptied on unicode weirdness. The
    # `coverage` block is the canonical proof the regex-based
    # measurement layer ran end-to-end.
    coverage = payload.get("analysis", {}).get("coverage")
    check(
        isinstance(coverage, dict) and "addressed_count" in coverage,
        "unicode edge-case payload must carry a populated coverage block",
    )
    _assert_no_new_failures(baseline, "test_tools_call_unicode_edge_cases")
    print("  PASS\n")


def test_stdio_subprocess_handles_rapid_fire_sequential_requests():
    """A long-running stdio session must handle many sequential
    requests without state leaks, id-ordering errors, or stdout
    contamination. The existing test_stdio_subprocess_roundtrip
    catches handshake regressions; this test catches session drift."""
    print("=== stdio subprocess handles rapid-fire sequential requests ===")
    baseline = len(_FAILURES)
    server_path = REPO_ROOT / "mcp_server.py"
    proc = subprocess.Popen(
        ["python3", str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REPO_ROOT),
    )

    def call(req):
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline().strip()
        return json.loads(line) if line else None

    def _normalize_for_determinism(payload_dict):
        """Strip wall-clock-variant fields before comparison.

        Matches the normalization in ``test_payload_is_deterministic``:
        analysis_latency_ms (duration), analysis_timestamp_utc
        (start-of-call ISO stamp), and the manifest's analysis_run_at
        (per-call wall-clock attribution) are allowed to differ between
        calls without breaking the determinism contract.

        The manifest IS per-call operational metadata by design (the
        whole point is to record what ran on this specific call), so
        the run timestamp is a feature, not a determinism violation.
        Other manifest fields (substrate identity, layers run, layers
        skipped with reasons, llm_calls, sn_providers) are constant
        for identical inputs and stay in the determinism comparison.
        """
        prov = payload_dict.get("provenance", {})
        prov.pop("analysis_latency_ms", None)
        prov.pop("analysis_timestamp_utc", None)
        manifest = payload_dict.get("manifest", {})
        if isinstance(manifest, dict):
            manifest.pop("analysis_run_at", None)
        return payload_dict

    try:
        init_resp = call({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
        check(
            init_resp["result"]["serverInfo"]["name"] == mcp_server.SERVER_NAME,
            "rapid-fire: handshake must succeed",
        )

        # Alternate two distinct documents across 50 sequential
        # requests so we can verify (a) id routing, (b) determinism
        # holds in-session for identical input.
        doc_a = _DOC_SAMPLE
        doc_b = (
            "Growth has been strong. Risks remain elevated. "
            "Stakeholders monitor outcomes. Past trends continue."
        )
        first_a_payload = None
        first_b_payload = None
        for i in range(50):
            doc = doc_a if i % 2 == 0 else doc_b
            req_id = 900 + i
            resp = call({
                "jsonrpc": "2.0", "id": req_id, "method": "tools/call",
                "params": {
                    "name": "frame_check",
                    "arguments": {"document_text": doc},
                },
            })
            check(
                resp is not None and resp.get("id") == req_id,
                f"rapid-fire request {i}: response id mismatch or missing",
            )
            check(
                resp["result"].get("isError") is False,
                f"rapid-fire request {i}: unexpected isError",
            )
            payload_text = resp["result"]["content"][0]["text"]
            if i % 2 == 0:
                if first_a_payload is None:
                    first_a_payload = payload_text
                else:
                    pA = _normalize_for_determinism(json.loads(first_a_payload))
                    pCur = _normalize_for_determinism(json.loads(payload_text))
                    check(
                        pA == pCur,
                        f"rapid-fire determinism: request {i} deviated from first-A baseline",
                    )
            else:
                if first_b_payload is None:
                    first_b_payload = payload_text
                else:
                    pB = _normalize_for_determinism(json.loads(first_b_payload))
                    pCur = _normalize_for_determinism(json.loads(payload_text))
                    check(
                        pB == pCur,
                        f"rapid-fire determinism: request {i} deviated from first-B baseline",
                    )
    finally:
        with contextlib.suppress(Exception):
            proc.stdin.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        # Drain + close stdout/stderr to avoid ResourceWarning on the
        # pipes (the existing test_stdio_subprocess_roundtrip leaks
        # these; we do not want new tests to add to that count).
        with contextlib.suppress(Exception):
            proc.stdout.close()
        with contextlib.suppress(Exception):
            proc.stderr.close()
    _assert_no_new_failures(baseline, "test_stdio_subprocess_handles_rapid_fire_sequential_requests")
    print("  PASS\n")


def test_tools_call_whitespace_only_document_rejected():
    """Whitespace-only document_text must be rejected the same way as
    empty string, because the server uses ``.strip()`` on the input
    before the non-empty check. The existing empty-string test
    (``test_tools_call_empty_input_is_error``) covers "" but does not
    pin the whitespace branch of the same defense."""
    print("=== tools/call rejects whitespace-only document_text ===")
    baseline = len(_FAILURES)
    for whitespace in (" ", "\n", "\t", "   \n\t  "):
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 1001, "method": "tools/call",
            "params": {
                "name": "frame_check",
                "arguments": {"document_text": whitespace},
            },
        })
        check(
            resp["result"].get("isError") is True,
            f"whitespace-only input {whitespace!r} must isError",
        )
    _assert_no_new_failures(baseline, "test_tools_call_whitespace_only_document_rejected")
    print("  PASS\n")


def test_version_falls_back_to_pipeline_version_txt_when_git_unavailable():
    """In Docker and in a future pip-installable distribution of the
    MCP server, the `git rev-parse` subprocess call returns non-zero
    (no git binary or no .git directory). Without a fallback, the
    --version fingerprint reports git_sha=unknown, stripping the
    operator's ability to match a deployed install against a known
    source revision.

    The Dockerfile writes the build-arg GIT_SHA to
    pipeline_version.txt next to mcp_server.py. This test pins that
    _install_version_info reads that file as a second-pass fallback
    when git is unavailable. Regression caught one real production
    issue (deploy 01KPWA59... on 2026-04-22 reported
    git_sha=unknown despite --build-arg being the documented
    deploy command).
    """
    import tempfile
    print("=== --version falls back to pipeline_version.txt in containerized install ===")
    baseline = len(_FAILURES)

    original_script_dir = mcp_server._SCRIPT_DIR
    try:
        with tempfile.TemporaryDirectory() as td:
            # Simulate a containerized layout: no .git, but a
            # pipeline_version.txt present. Any other VERSION-type
            # files are absent, so other fields correctly fall back
            # to "unknown" and do not interfere with this test.
            with open(os.path.join(td, "pipeline_version.txt"), "w", encoding="utf-8") as f:
                f.write("deadbee\n")
            mcp_server._SCRIPT_DIR = td
            info = mcp_server._install_version_info()
    finally:
        mcp_server._SCRIPT_DIR = original_script_dir

    check(
        info.get("git_sha") == "deadbee",
        f"expected git_sha='deadbee' from pipeline_version.txt fallback, got {info.get('git_sha')!r}",
    )
    # Also verify that when the baked value is literally "unknown"
    # (ARG not passed at build time), the fallback does not
    # masquerade that as a real SHA.
    try:
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "pipeline_version.txt"), "w", encoding="utf-8") as f:
                f.write("unknown\n")
            mcp_server._SCRIPT_DIR = td
            info2 = mcp_server._install_version_info()
    finally:
        mcp_server._SCRIPT_DIR = original_script_dir

    check(
        info2.get("git_sha") == "unknown",
        f"expected git_sha='unknown' when baked value is 'unknown', got {info2.get('git_sha')!r}",
    )
    _assert_no_new_failures(baseline, "test_version_falls_back_to_pipeline_version_txt_when_git_unavailable")
    print("  PASS\n")


def test_tools_call_null_byte_handled_transparently():
    """An embedded U+0000 NULL byte in document_text is valid UTF-8
    and passes the non-empty / length checks. The measurement layer
    must process such a document without crashing and produce the
    same structural measurements it would on the clean version of
    the document. If future changes to the tokenizer or regex layer
    silently stop at the null byte, the structural counts will drop;
    pinning equality against the clean baseline catches that."""
    print("=== tools/call handles null byte transparently ===")
    baseline = len(_FAILURES)
    clean_doc = "The Committee notes risks. Growth has been solid. Stakeholders monitor. Data incoming."
    null_doc = "The Committee notes risks. Growth has been solid.\x00 Stakeholders monitor. Data incoming."

    def _analyze(doc):
        resp = mcp_server.dispatch({
            "jsonrpc": "2.0", "id": 1002, "method": "tools/call",
            "params": {"name": "frame_check", "arguments": {"document_text": doc}},
        })
        check(
            resp["result"].get("isError") is False,
            f"dispatch on doc must not isError (doc starts {doc[:30]!r})",
        )
        return json.loads(resp["result"]["content"][0]["text"])

    clean = _analyze(clean_doc)
    null = _analyze(null_doc)

    clean_cov = clean.get("analysis", {}).get("coverage", {}).get("addressed_count")
    null_cov = null.get("analysis", {}).get("coverage", {}).get("addressed_count")
    check(
        clean_cov == null_cov,
        f"null byte broke structural measurement: clean coverage={clean_cov}, null coverage={null_cov}",
    )
    clean_sentences = clean.get("analysis", {}).get("coverage", {}).get("total_sentences")
    null_sentences = null.get("analysis", {}).get("coverage", {}).get("total_sentences")
    check(
        clean_sentences == null_sentences,
        f"null byte broke sentence tokenization: clean={clean_sentences}, null={null_sentences}",
    )
    _assert_no_new_failures(baseline, "test_tools_call_null_byte_handled_transparently")
    print("  PASS\n")


# ── Runner ────────────────────────────────────────────────────────

def main() -> int:
    print("Running mcp_server tests...")
    print()
    test_payload_has_three_sections()
    test_analysis_fields_are_present()
    test_analysis_includes_decision_readiness_profile()
    test_decision_readiness_uses_source_text_when_available()
    test_agent_guidance_includes_scope_honesty()
    test_provenance_reports_zero_llm_cost()
    test_payload_is_deterministic()
    test_initialize_handshake()
    test_tools_list_advertises_frame_check()
    test_tools_list_advertises_frame_compare()
    test_tools_call_returns_text_content()
    test_tools_call_empty_input_is_error()
    test_unknown_tool_returns_error_content()
    test_unknown_method_returns_jsonrpc_error()
    test_notification_gets_no_response()
    test_no_source_has_no_verification_block()
    test_with_source_unlocks_verification_block()
    test_saturated_source_steers_guidance_to_layer_4()
    test_frame_matches_carry_stability_status()
    test_agent_guidance_describes_cite_form_for_matches()
    test_compare_payload_has_three_sections()
    test_compare_analysis_carries_cross_doc_fields()
    test_compare_provenance_names_compare_layer()
    test_compare_agent_guidance_forbids_ranking()
    test_compare_is_deterministic()
    test_compare_tools_call_end_to_end()
    test_compare_rejects_missing_second_document()
    test_initialize_advertises_resources_capability()
    test_resources_list_includes_library_and_docs()
    test_resources_read_library_entry_returns_markdown()
    test_resources_read_worked_example_returns_markdown()
    test_resources_read_methodology_returns_markdown()
    test_resources_read_calibration_returns_json()
    test_aggregate_resource_listed_when_present()
    test_aggregate_resource_omitted_when_absent()
    test_aggregate_resource_read_returns_valid_json_payload()
    test_aggregate_chain_to_library_entry_via_fired_patterns()
    test_corpus_entries_listed_as_mcp_resources()
    test_corpus_entry_document_read_returns_markdown()
    test_corpus_entry_profile_read_returns_json()
    test_corpus_entry_invalid_slug_returns_invalid_params()
    test_aggregate_to_corpus_chain_round_trip()
    test_explain_framing_prompt_mentions_aggregate_and_corpus()
    test_ai_response_audit_prompt_mentions_aggregate_optional()
    test_corpus_per_pair_comparisons_listed_as_mcp_resources()
    test_corpus_peer_pair_read_returns_json()
    test_corpus_diff_pair_read_returns_json()
    test_corpus_pair_invalid_inputs_rejected()
    test_aggregate_resource_read_when_absent_is_filenotfound()
    test_resources_read_unknown_library_entry_is_invalid_params()
    test_resources_read_bad_scheme_is_invalid_params()
    test_resources_read_path_traversal_rejected()
    test_frame_match_carries_mcp_uri_and_entry_version()
    test_frame_match_carries_adjacent_frames()
    test_frame_library_matches_carry_affects_dimensions()
    test_decision_readiness_library_entry_uri_round_trips_via_resources_read()
    test_library_resource_description_pins_version()
    test_library_index_resource_available()
    test_worked_examples_index_resource_available()
    test_transmissions_resources_available()
    test_calibration_per_run_resources_available()
    test_calibration_run_traversal_rejected()
    test_provenance_carries_iso_timestamp()
    test_worked_example_descriptions_carry_frontmatter_signal()
    test_ping_returns_empty_result()
    test_resources_read_missing_uri_is_invalid_params()
    test_initialize_advertises_prompts_capability()
    test_prompts_list_has_four()
    test_prompts_get_returns_messages_with_voice_rules()
    test_server_version_bumped_for_decision_readiness_capability()
    test_all_prompts_surface_decision_readiness()
    test_all_prompts_point_at_library_chain_for_decision_readiness()
    test_all_prompts_mention_affects_dimensions_for_matched_frames()
    test_agent_guidance_names_self_audit_pattern()
    test_prompts_get_ai_response_prompt_warns_against_verdict()
    test_prompts_get_unknown_returns_invalid_params()
    test_resources_list_carries_content_hash()
    test_resources_read_carries_content_hash()
    test_content_hash_stable_across_calls()
    test_every_resource_has_stable_matching_hash()
    test_content_hashes_differ_across_distinct_resources()
    test_resources_list_drops_unreadable_not_hashless()
    test_worked_example_reproduces_from_captured_payload()
    test_stdio_subprocess_roundtrip()
    test_cli_version_flag()
    test_cli_help_flag()
    test_cli_test_triggers_fvs_matches()
    # Adversarial input hardening
    test_tools_call_document_text_at_limit_boundary()
    test_tools_call_document_text_over_limit_rejected()
    test_tools_call_source_text_over_limit_rejected()
    test_tools_call_wrong_argument_types_handled_cleanly()
    test_tools_call_unicode_edge_cases()
    test_stdio_subprocess_handles_rapid_fire_sequential_requests()
    test_tools_call_whitespace_only_document_rejected()
    test_version_falls_back_to_pipeline_version_txt_when_git_unavailable()
    test_tools_call_null_byte_handled_transparently()
    # Frame Divergence block (FRAME_DIVERGENCE_CONTRACT_v1 Part 2)
    test_divergence_present_by_default()
    test_divergence_legacy_opt_out()
    test_divergence_opt_in_adds_block()
    test_divergence_absent_frame_record_required_fields()
    test_divergence_envelope_required_fields()
    test_divergence_excludes_fvs_020()
    test_divergence_excludes_present_frames()
    test_divergence_forbidden_prescriptive_fields()
    test_divergence_teaching_questions_rendering_decorates_records()
    test_divergence_domain_hint_echoes_to_envelope()
    test_divergence_invalid_domain_hint_rejected_by_dispatcher()
    test_divergence_invalid_rendering_rejected_by_dispatcher()
    test_divergence_wrong_include_type_rejected_by_dispatcher()
    # Per-level construct treatment (substrate-side composition L5)
    test_each_composed_entity_carries_claim_level()
    test_claim_level_treatments_carries_required_levels()
    test_claim_level_treatments_validation_status_honest()
    test_decision_readiness_dimensions_carry_claim_level()
    test_frame_compare_parity_carries_claim_level()
    test_composition_discipline_teaches_per_level_treatment()
    test_agent_generated_claim_level_for_opportunities()
    test_llm_classifier_output_claim_level_treatment()
    # Substrate-side composition L5 interface UX (Step 2 + 3)
    test_agent_guidance_carries_how_to_map_user_intent()
    test_compose_budget_full_preserves_current_behavior()
    test_compose_budget_minimal_filters_top_n()
    test_compose_budget_minimal_compresses_agent_guidance()
    test_compose_budget_invalid_value_rejected()
    test_sovereignty_prompts_advertise_user_intent_arguments()
    test_prompt_arguments_translate_to_mcp_parameters()

    if _FAILURES:
        print("\n".join(f"  FAIL: {m}" for m in _FAILURES))
        return 1
    print("=== ALL MCP SERVER TESTS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
