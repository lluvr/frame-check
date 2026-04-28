"""Discipline-boundary tests for the V4.2 engine + library_v4.

These tests protect five structural claims that the library_v3 -> library_v4
ratification rests on. All claims are documented in METHODOLOGY.md
section 2.4.4 and in fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md.

If a future engine refactor or library edit silently breaks any claim,
these tests fail loudly and tell the author which discipline clause to
re-read before proceeding.

Claim 1 (engine boundary). The V4.2 labeling judge reads only
``## Identification`` sections from each library entry. No other
section content reaches the LLM judge prompt.

Claim 2 (entry framing line). Every FVS-XXX entry in
``data/frame_library/`` carries the post-stress-test ratification
framing line at the top of its ``## Cross-family reliability`` section.

Claim 3 (Generation-affordances byte-equivalence). The reframe LLM
path (reframe.py) reads ``## Generation affordances`` and feeds the
counter-document prompt to Grok. Library_v4 is byte-equivalent to
library_v3 on this section per the ratification's reframe-null-risk
claim.

Claim 4 (engine-emit disclosure consistency). Each FVS-XXX entry's
Cross-family block carries an "Engine-emit disclosure" paragraph that
names the V4.2 engine's emitted ``library_consensus_ac1`` for that
frame. The cited number must match the value in
``fvs_eval/v4/library_v4_reliability.json`` exactly. This protects
against drift between the engine artifact and what a reviewer reads
on the entry page.

Claim 5 (VERSION sync between snapshot and living library). At
ratification time the frozen snapshot at ``data/frame_library_v4/``
and the living library at ``data/frame_library/`` carry matching
VERSION values. The next ratification bumps both in lockstep; a drift
between them indicates a forgotten bump or a snapshot-without-
ratification.

Run via pytest or via ``python3 run_tests.py`` (this file is
auto-discovered by the canonical runner).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "fvs_eval" / "v4"))

# Section markers that should NEVER appear in the V4.2 labeling-judge
# prompt. ``## Identification`` itself is excluded from this list
# because ``_extract_identification`` strips that header line and only
# returns the body content.
FORBIDDEN_SECTION_MARKERS = (
    "## Cross-family reliability",
    "## Adjacent frames",
    "## Honest limits",
    "## Worked examples",
    "## Decision-readiness implication",
    "## Generation affordances",
)

# Substrings that satisfy the entry framing-line requirement. Either
# matches, since the bespoke FVS-001 and FVS-008 entries phrase the
# claim differently from the 18 templated entries but say the same
# thing structurally.
ACCEPTED_FRAMING_PHRASES = (
    "library_v4 ratified 2026-04-24",
    "Engine canonical is now library_v4",
    "Under library_v4",
)

LIVING_LIBRARY = REPO_ROOT / "data" / "frame_library"


def test_v4_2_labeling_prompt_only_uses_identification_sections():
    """Engine boundary: the V4.2 labeling-judge prompt must not contain
    text from any non-Identification section of any library entry.

    If this test fails, the library_v3 -> library_v4 ratification's
    byte-equivalence-on-judge-visible-content argument has silently
    broken. Either revert the engine change or update METHODOLOGY
    section 2.4.4 plus the LIBRARY_V3_TO_V4_RATIFICATION_v1.md
    byte-equivalence proof to name the new engine-LLM-facing sections
    (and re-run the section 2.4.3 ablation against the broader content
    set).
    """
    from v4_2_engine import build_library_reference

    lib_ref = build_library_reference(strip_revision_notes=True)

    leaks = [m for m in FORBIDDEN_SECTION_MARKERS if m in lib_ref]
    assert not leaks, (
        f"V4.2 labeling-judge library reference contains "
        f"non-Identification section markers: {leaks}. "
        f"This breaks METHODOLOGY section 2.4.4's Identification-only "
        f"engine-LLM-facing boundary and invalidates the library_v4 "
        f"ratification's byte-equivalence argument. Read "
        f"fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md section 2.4 "
        f"and METHODOLOGY section 2.4.4 before proceeding."
    )


def _discover_entry_files() -> list[Path]:
    """Discover all FVS-XXX_*.md entry files in the living library by
    scanning the directory rather than hardcoding range(1, 21). This
    keeps the test correct when a future ratification adds FVS-021 or
    higher; the new entry is automatically subject to the discipline
    checks below.
    """
    pattern = re.compile(r"^FVS-\d{3}_.+\.md$")
    return sorted(
        p for p in LIVING_LIBRARY.iterdir()
        if p.is_file() and pattern.match(p.name)
    )


def test_every_entry_has_post_ratification_framing_line():
    """Each FVS-XXX entry in data/frame_library/ must carry a top-of-
    Cross-family-section framing line that names library_v4 and the
    library_v3 byte-equivalence. The line was added across all 20
    entries during the 2026-04-24 post-ratification stress-test pass
    so that a reviewer reading any single entry top-to-bottom is told
    which library state the cross-family numbers describe.

    If this test fails, an edit removed or restructured the framing
    away from one or more entries, or a new entry was added without
    one. Restore the framing line (template in fvs_eval/v4_2/
    LIBRARY_V3_TO_V4_RATIFICATION_v1.md section 8b) or write an
    entry-specific equivalent that mentions either "library_v4
    ratified 2026-04-24", "Engine canonical is now library_v4", or
    "Under library_v4".
    """
    missing: list[str] = []
    entry_files = _discover_entry_files()
    assert entry_files, (
        f"No FVS-XXX entry files found in {LIVING_LIBRARY}. The living "
        f"library is empty or this test is running from the wrong "
        f"working directory."
    )
    for path in entry_files:
        fid = path.name.split("_", 1)[0]
        text = path.read_text(encoding="utf-8")
        # Find the Cross-family reliability section and check the
        # framing phrase appears within it. Section spans from header
        # to next ``## `` heading or end-of-file.
        section_match = re.search(
            r"## Cross-family reliability\s*\n(.*?)(?=\n## |\Z)",
            text, flags=re.DOTALL,
        )
        if not section_match:
            missing.append(f"{fid}: no Cross-family reliability section")
            continue
        section_body = section_match.group(1)
        if not any(
            phrase in section_body for phrase in ACCEPTED_FRAMING_PHRASES
        ):
            missing.append(
                f"{fid}: Cross-family section lacks ratification framing "
                f"line (expected one of: "
                f"{', '.join(repr(p) for p in ACCEPTED_FRAMING_PHRASES)})"
            )

    assert not missing, (
        f"{len(missing)} of {len(entry_files)} entries lack the "
        f"post-ratification framing line in their Cross-family "
        f"reliability section: {missing}. Restore per fvs_eval/v4_2/"
        f"LIBRARY_V3_TO_V4_RATIFICATION_v1.md section 8b."
    )


def test_each_entry_engine_emit_disclosure_matches_artifact():
    """Each FVS-XXX entry's Cross-family block carries an "Engine-emit
    disclosure" paragraph. For frames present in
    ``fvs_eval/v4/library_v4_reliability.json``, the disclosure cites a
    numeric ``library_consensus_ac1`` that MUST match the artifact
    exactly. For frames not yet in the artifact (a freshly-added entry
    awaiting Step 4 measurement), the disclosure must explicitly say
    so via "pending Step 4 measurement" or equivalent acknowledgment.
    For FVS-020 (excluded from V4.2 emission per Step 4
    ``vocabulary_only`` status), the disclosure names the exclusion.

    Why this test exists: before the 2026-04-24 post-stress-test pass,
    the engine emitted (e.g.) ``library_consensus_ac1: 0.495`` for
    FVS-016 while the entry page showed ``library_v3 MG AC1 0.633`` as
    "engine-canonical." A user comparing engine output to the entry
    page saw two different numbers with no in-entry explanation. The
    disclosure paragraph closed the gap by naming the engine-emitted
    number explicitly. This test catches future drift on either side.

    The "pending Step 4 measurement" path exists so that adding a new
    frame (e.g. FVS-021) does not require completing the next library
    ratification cycle before merging the entry; the new entry can ship
    with an honest "no measurement yet" disclosure that this test
    accepts. The pending state is intentionally explicit (not a silent
    skip) so reviewers reading the entry know the reliability is
    un-measured rather than mistakenly absent.
    """
    artifact_path = (
        REPO_ROOT / "fvs_eval" / "v4" / "library_v4_reliability.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact_frames = artifact["frames"]

    measured_re = re.compile(
        r"\*\*Engine-emit disclosure\.\*\*[^\n]*?"
        r"`library_consensus_ac1`\s*=\s*\*\*([0-9.]+)\*\*",
    )
    pending_re = re.compile(
        r"\*\*Engine-emit disclosure\.\*\*[^\n]*?"
        r"pending Step 4 measurement",
        flags=re.IGNORECASE,
    )
    excluded_re = re.compile(
        r"FVS-020 is excluded from V4\.2 engine emission",
    )

    mismatches: list[str] = []
    missing: list[str] = []
    for path in _discover_entry_files():
        fid = path.name.split("_", 1)[0]
        text = path.read_text(encoding="utf-8")

        if fid == "FVS-020":
            if not excluded_re.search(text):
                missing.append(
                    f"{fid}: missing excluded-frame disclosure "
                    "(should name FVS-020 as excluded from V4.2 emission)"
                )
            continue

        artifact_value = artifact_frames.get(fid, {}).get("ac1_avg")

        if artifact_value is None:
            # Frame is not yet in the reliability artifact (typical for
            # a freshly-added FVS-XXX entry awaiting next Step 4
            # measurement). Accept either pending-state disclosure or
            # numeric disclosure that the artifact has not caught up
            # to. Pending-state is the expected shape; numeric without
            # artifact backing is treated as an inconsistency.
            if pending_re.search(text):
                continue
            if measured_re.search(text):
                mismatches.append(
                    f"{fid}: entry cites a numeric "
                    "`library_consensus_ac1` but the artifact has no "
                    "ac1_avg for this frame. Either add the frame to "
                    "fvs_eval/v4/library_v4_reliability.json (after "
                    "Step 4 measurement under METHODOLOGY section "
                    "2.4.3) or rewrite the disclosure to say "
                    "'pending Step 4 measurement'."
                )
                continue
            missing.append(
                f"{fid}: missing engine-emit disclosure. New entries "
                "without measured reliability should use a 'pending "
                "Step 4 measurement' disclosure paragraph; entries "
                "with measured reliability should cite "
                "`library_consensus_ac1` = **X.XXX**."
            )
            continue

        # Measured frame: require numeric disclosure matching artifact.
        m = measured_re.search(text)
        if not m:
            if pending_re.search(text):
                mismatches.append(
                    f"{fid}: disclosure says 'pending Step 4 "
                    "measurement' but the artifact already has "
                    f"ac1_avg = {artifact_value}. Update the entry "
                    "to cite the measured value."
                )
                continue
            missing.append(
                f"{fid}: missing engine-emit disclosure paragraph "
                "(expected text matching '**Engine-emit disclosure.** "
                "... `library_consensus_ac1` = **X.XXX**')"
            )
            continue
        cited = float(m.group(1))
        # Allow trailing-zero formatting differences by comparing to
        # 3 decimal places (the format the disclosure prints).
        if round(cited, 3) != round(float(artifact_value), 3):
            mismatches.append(
                f"{fid}: entry cites {cited}, artifact has "
                f"{artifact_value}"
            )

    problems = missing + mismatches
    assert not problems, (
        f"Engine-emit disclosure issues across {len(problems)} entries: "
        f"{problems}. The library_v4 ratification's construct-honesty "
        f"depends on each entry naming the engine-emitted number "
        f"correctly. If the artifact intentionally changed, regenerate "
        f"the disclosures via the helper in the post-stress-test commit "
        f"history. If the disclosures intentionally changed, update "
        f"the artifact under METHODOLOGY section 2.4.3 + 2.4.4 "
        f"discipline first."
    )


def test_living_library_version_matches_snapshot_version():
    """The frozen ratified snapshot at data/frame_library_v4/ and the
    living library at data/frame_library/ share a VERSION value at
    ratification time. The next library version (library_v5) bumps
    both in lockstep at its ratification commit.

    A drift between the two indicates one of:
    - the living library was bumped without a snapshot ratification;
    - the snapshot was retroactively edited (violating the snapshot-
      frozen-after-ratification discipline);
    - or someone forgot to bump one of the two during a ratification.

    Any of these breaks the snapshot vs living-library discipline
    documented in METHODOLOGY section 2.4.4 and in this directory's
    POST_RATIFICATION_DIVERGENCE.md sidecar.
    """
    living_version_path = LIVING_LIBRARY / "VERSION"
    snapshot_version_path = (
        REPO_ROOT / "data" / "frame_library_v4" / "VERSION"
    )
    if not snapshot_version_path.is_file():
        pytest.skip(
            "frame_library_v4 snapshot VERSION not present; this test "
            "only runs in repos that retain the ratified snapshot."
        )

    living_version = living_version_path.read_text(encoding="utf-8").strip()
    snapshot_version = snapshot_version_path.read_text(encoding="utf-8").strip()
    assert living_version == snapshot_version, (
        f"VERSION drift: living library at {living_version_path} reads "
        f"'{living_version}' but ratified snapshot at "
        f"{snapshot_version_path} reads '{snapshot_version}'. Either "
        f"a ratification only bumped one (re-bump the other) or the "
        f"snapshot was retroactively edited (revert per snapshot-"
        f"frozen-after-ratification discipline; corrections live in the "
        f"living library, not the snapshot)."
    )


def test_each_entry_has_intra_rater_disclosure():
    """Each FVS-XXX emitting entry's Cross-family block carries an
    "Intra-rater stability" paragraph naming
    ``detector_intra_rater_ac1`` (the second engine-emitted reliability
    metric beyond ``library_consensus_ac1``). Without this paragraph,
    a user seeing both numbers in V4.2 results gets no entry-level
    explanation of why the two are independent.

    FVS-020 is excluded from V4.2 emission per Step 4 vocabulary_only
    status; its entry carries an excluded-frame intra-rater note
    instead and is checked separately.
    """
    intra_re = re.compile(
        r"\*\*Intra-rater stability[^*]*\*\*[^\n]*?"
        r"`detector_intra_rater_ac1`",
    )
    excluded_intra_re = re.compile(
        r"\*\*Intra-rater stability\.\*\* FVS-020 is excluded from V4\.2 "
        r"engine emission",
    )

    missing: list[str] = []
    for path in _discover_entry_files():
        fid = path.name.split("_", 1)[0]
        text = path.read_text(encoding="utf-8")
        if fid == "FVS-020":
            if not excluded_intra_re.search(text):
                missing.append(
                    f"{fid}: missing excluded-frame intra-rater note"
                )
            continue
        if not intra_re.search(text):
            missing.append(
                f"{fid}: missing intra-rater stability paragraph "
                "(expected '**Intra-rater stability ...** ... "
                "`detector_intra_rater_ac1`')"
            )

    assert not missing, (
        f"{len(missing)} entries lack intra-rater stability "
        f"disclosure: {missing}. The V4.2 engine emits two distinct "
        "reliability metrics (library_consensus_ac1 cross-family and "
        "detector_intra_rater_ac1 single-family Grok stability); both "
        "should be visible at entry level. See pass-5 stress-test "
        "additions for the canonical paragraph shape."
    )


def test_each_entry_has_construct_validity_caveat():
    """Each FVS-XXX entry's Cross-family block carries a
    "Construct-validity caveat" paragraph naming what
    ``library_consensus_ac1`` measures (LLM-to-LLM consensus) and
    what it does NOT measure (validation against human readers).
    The caveat protects against entry readers silently assuming
    cross-family AC1 = validated reliability against human-derived
    ground truth; per METHODOLOGY section 1.3, the V1 external-
    validation study against human labelers returned macro-F1 0.157
    (chance-level) and library_v4 has not been re-validated against
    human labelers.
    """
    # Spirit-match: caveat must name "NOT" + "human" within the same
    # paragraph. Wording can vary (post-pass-9 editorial pass shortened
    # the caveat from "does NOT measure agreement with human reader
    # labels" to "NOT agreement with human reader labels"; both are
    # honest expressions of the same construct-validity claim).
    caveat_re = re.compile(
        r"\*\*Construct-validity caveat\.\*\*[^\n]*?"
        r"NOT[^\n]*?human[^\n]*?label",
    )
    missing: list[str] = []
    for path in _discover_entry_files():
        fid = path.name.split("_", 1)[0]
        text = path.read_text(encoding="utf-8")
        if not caveat_re.search(text):
            missing.append(
                f"{fid}: missing construct-validity caveat "
                "(expected '**Construct-validity caveat.** ... "
                "NOT measure agreement with human reader labels')"
            )

    assert not missing, (
        f"{len(missing)} entries lack the construct-validity caveat "
        f"paragraph: {missing}. Without it, an entry reader can "
        "silently assume cross-family AC1 = validated reliability "
        "against human-derived ground truth, which the library does "
        "not claim. See METHODOLOGY section 1.3 for the H3 "
        "falsification context that motivates the caveat."
    )


def test_per_corpus_reliability_supplement_reproduces_from_labels():
    """The per-corpus reliability supplement at
    ``fvs_eval/v4/library_v4_per_corpus_reliability.json`` must
    reproduce exactly when ``compute_per_corpus_reliability.py`` is
    re-run against on-disk labels. This guards against the same
    reproducibility gap that the engine's primary
    ``library_v4_reliability.json`` artifact suffers from per the
    2026-04-24 audit at
    ``fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md``.

    The supplement is shipped with explicit per-corpus values (mg_v3,
    mg2_v1, mg2_v2) so reviewers and future auditors have a verifiable
    baseline. If the labels change or the supplement is hand-edited,
    this test catches the drift loudly and points at the regenerator
    script.

    Skipped when the supplement or its source labels are absent (e.g.
    partial checkouts).
    """
    supplement_path = (
        REPO_ROOT / "fvs_eval" / "v4" / "library_v4_per_corpus_reliability.json"
    )
    script_path = (
        REPO_ROOT / "fvs_eval" / "v4" / "compute_per_corpus_reliability.py"
    )
    if not supplement_path.is_file() or not script_path.is_file():
        pytest.skip(
            "per_corpus_reliability supplement or regenerator script "
            "not present; supplement-reproducibility test skipped."
        )

    sys.path.insert(0, str(REPO_ROOT / "fvs_eval" / "v4"))
    try:
        import compute_per_corpus_reliability as ccr
    except ImportError:
        pytest.skip("compute_per_corpus_reliability importable failure")

    # Required label files for the assertion to run.
    mg_v3_files = list(
        (REPO_ROOT / "fvs_eval" / "mixed_genre_v1" / "labels").glob(
            "*_new_library_v3.json"
        )
    )
    if len(mg_v3_files) < 4:
        pytest.skip(
            f"Insufficient MG library_v3 label files "
            f"({len(mg_v3_files)} < 4 families); test cannot verify "
            "supplement reproducibility."
        )

    fresh = ccr.build_artifact()
    on_disk = json.loads(supplement_path.read_text(encoding="utf-8"))

    # Compare the measurement frames structures only; ignore
    # computed_at_utc which always differs.
    mismatches: list[str] = []
    for corpus_key in ("mg_v3", "mg2_v1", "mg2_v2"):
        fresh_meas = fresh["measurements"].get(corpus_key)
        disk_meas = on_disk["measurements"].get(corpus_key)
        if fresh_meas is None and disk_meas is None:
            continue
        if (fresh_meas is None) != (disk_meas is None):
            mismatches.append(
                f"{corpus_key}: presence mismatch "
                f"(fresh={fresh_meas is not None}, "
                f"disk={disk_meas is not None})"
            )
            continue
        if fresh_meas["n_docs"] != disk_meas["n_docs"]:
            mismatches.append(
                f"{corpus_key}: n_docs differs "
                f"(fresh={fresh_meas['n_docs']}, "
                f"disk={disk_meas['n_docs']})"
            )
        for fid in fresh_meas["frames"]:
            f_rec = fresh_meas["frames"][fid]
            d_rec = disk_meas["frames"].get(fid)
            if d_rec is None:
                mismatches.append(f"{corpus_key}/{fid}: missing on disk")
                continue
            if f_rec["ac1_mean"] != d_rec["ac1_mean"]:
                mismatches.append(
                    f"{corpus_key}/{fid}: ac1_mean fresh="
                    f"{f_rec['ac1_mean']} disk={d_rec['ac1_mean']}"
                )

    assert not mismatches, (
        f"Per-corpus reliability supplement does not reproduce from "
        f"on-disk labels via compute_per_corpus_reliability.py. "
        f"{len(mismatches)} mismatches: {mismatches[:10]}"
        + (
            f" (and {len(mismatches) - 10} more)"
            if len(mismatches) > 10 else ""
        )
        + ". Either re-run the regenerator script to refresh the "
        "supplement, or investigate why labels and supplement disagree "
        "(supplement may have been hand-edited; labels may have been "
        "updated). See "
        "fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md "
        "for the audit context."
    )


def test_generation_affordances_byte_equivalent_v3_to_v4():
    """The library_v4 ratification's reframe-behavior null-risk claim
    rests on Generation affordances being byte-identical between
    library_v3 and library_v4 across all 20 entries. Reframe at
    reframe.py reads ## Generation affordances and feeds the counter-
    document prompt into a Grok call. Drift on this section between
    snapshot versions silently changes reframe LLM behavior.

    METHODOLOGY section 2.4.4 corollary names Generation affordances
    as the second engine-LLM-facing section; a future revision that
    changes them must run a reframe-behavior smoke test before
    ratification (not section 2.4.3 ablation; reframe behavior is not
    a cross-family-AC1 quantity).

    This test guards that the snapshot pair (v3 vs v4) remains the
    way the ratification documented it. Future library_v5 ratification
    can update or remove this assertion if Generation affordances
    intentionally evolve under that ratification's discipline.
    """
    v3_dir = REPO_ROOT / "data" / "frame_library_v3"
    v4_dir = REPO_ROOT / "data" / "frame_library_v4"

    if not (v3_dir.is_dir() and v4_dir.is_dir()):
        pytest.skip(
            "frame_library_v3 or frame_library_v4 snapshot not present; "
            "this test only runs in repos that retain both snapshots."
        )

    section_re = re.compile(
        r"## Generation affordances\s*\n(.*?)(?=\n## |\Z)",
        flags=re.DOTALL,
    )

    drifted: list[str] = []
    for i in range(1, 21):
        fid = f"FVS-{i:03d}"
        v3_files = sorted(v3_dir.glob(f"{fid}_*.md"))
        v4_files = sorted(v4_dir.glob(f"{fid}_*.md"))
        if not (v3_files and v4_files):
            continue
        v3_text = v3_files[0].read_text(encoding="utf-8")
        v4_text = v4_files[0].read_text(encoding="utf-8")
        v3_match = section_re.search(v3_text)
        v4_match = section_re.search(v4_text)
        v3_body = v3_match.group(1).strip() if v3_match else ""
        v4_body = v4_match.group(1).strip() if v4_match else ""
        if v3_body != v4_body:
            drifted.append(fid)

    assert not drifted, (
        f"Generation affordances differ between library_v3 and "
        f"library_v4 for: {drifted}. The library_v4 ratification's "
        f"reframe-behavior null-risk claim relied on byte-equivalence "
        f"on this section across all 20 entries. Either revert the "
        f"drift, run a reframe-behavior smoke test per METHODOLOGY "
        f"section 2.4.4 corollary and update the ratification doc, or "
        f"open a library_v5 ratification under the new discipline."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
