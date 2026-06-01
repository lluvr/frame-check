"""Worked-example fixtures as regression-test ground truth.

Each ``data/worked_examples/<slug>/data.json`` is a tested specimen:
the builder captured a real document (or LLM summary), ran it
through Frame Check, and bundled the resulting payload alongside
the source text. The bundled ``frame_check_payload`` is the
builder's claim about what the wheel produces for that document.

This test loads each fixture, runs the live wheel against the same
inputs, and asserts the live payload matches the bundled snapshot
on a per-field allowlist that names the load-bearing structural
fields. Detector drift on those fields fails the test, surfacing
the divergence as a deliberate decision (refresh the snapshot)
rather than silent regression in adopter-facing demo material.

The allowlist is intentional: the entire payload contains
runtime-varying fields (analysis_run_at timestamp,
analysis_latency_ms, pipeline_version SHA depending on build) and
text fields whose exact wording is allowed to evolve under
refactoring. Pinning the full payload would create a maintenance
treadmill. Pinning the load-bearing structural fields catches
real regressions of the kind that would surface in adopter
output.

Backlog: only ``grok-on-nvidia-earnings-2026`` carries a
``data.json`` snapshot today. Three other worked-example
directories exist as bare slugs (the writeup MDs reference them)
but have no machine-readable inputs + payload; capturing those
is builder-driven follow-on work (re-run the LLM summarization,
capture bytes + SHA, save).
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKED_EXAMPLES_DIR = REPO_ROOT / "data" / "worked_examples"

sys.path.insert(0, str(REPO_ROOT))
import mcp_server  # type: ignore  # noqa: E402


def _fixture_paths():
    """Discover worked-example data.json files (those that exist)."""
    return sorted(WORKED_EXAMPLES_DIR.glob("*/data.json"))


@pytest.mark.parametrize(
    "fixture_path",
    _fixture_paths(),
    ids=lambda p: p.parent.name,
)
def test_worked_example_fixture_matches_live_payload(fixture_path):
    """Live frame_check payload matches the bundled snapshot on the
    allowlisted structural fields.

    The allowlist is the load-bearing surface that adopters and the
    worked-example MDs reference. A change to any of these fields is
    visible adopter behavior; locking them here surfaces detector
    drift as a deliberate snapshot-refresh decision.
    """
    fixture = json.loads(fixture_path.read_text())

    # Derive the inputs the snapshot was produced from.
    document_text = (
        fixture.get("llm_summary", {}).get("text")
        or fixture.get("document_text")
        or ""
    )
    source_text = (
        fixture.get("source", {}).get("text")
        or fixture.get("source_text")
        or None
    )
    snapshot = fixture.get("frame_check_payload")

    # Skip fixtures that don't carry both the inputs and a bundled
    # snapshot. Some worked-example data.json files exist as
    # input-only specimens (no captured payload); builder-driven
    # follow-on work captures the payload when ready. A skip surfaces
    # the gap as visible work-to-do without failing the suite.
    if not document_text:
        pytest.skip(
            f"fixture {fixture_path.parent.name}: no document_text "
            f"input (checked llm_summary.text + document_text). "
            f"Capture the input + payload to enable regression coverage."
        )
    if not snapshot:
        pytest.skip(
            f"fixture {fixture_path.parent.name}: no bundled "
            f"frame_check_payload. Run mcp_server.build_epistemic_payload "
            f"on the inputs and add the result to data.json under "
            f"'frame_check_payload' to enable regression coverage."
        )

    # Reproduce the payload the snapshot was captured from.
    live = mcp_server.build_epistemic_payload(
        document_text,
        source_text=source_text,
        include_divergence=True,
        domain_hint=fixture.get("domain", "finance"),
    )

    # Allowlist: load-bearing fields the worked-example MD writeups
    # reference + the differentiator capability fields + the construct-
    # confidence fields adopters depend on for restatement discipline.
    # Each entry is a dotted path into the payload; the value at that
    # path must match snapshot exactly. Adding a new field is a
    # deliberate widening of the contract.
    ALLOWLIST = [
        # Voice (cascade classification + confidence + runner-up)
        "analysis.voice.classification",
        "analysis.voice.confidence",
        "analysis.voice.runner_up",
        # Genre (parallel cascade)
        "analysis.genre.classification",
        "analysis.genre.confidence",
        # Coverage v1 (deprecated; pinned until v2.0 cut removes it)
        "analysis.coverage.addressed",
        "analysis.coverage.missing",
        "analysis.coverage.addressed_count",
        "analysis.coverage.total_categories",
        # Coverage v2 (forward contract per ROADMAP v2.0 entry).
        # contract_version + per-dimension status are the load-bearing
        # adopter fields; markers_matched count + density are the
        # quantitative fields. Pinning these here ensures v2 cannot
        # silently drift before the v2.0 cut promotes it to sole
        # coverage block.
        "analysis.coverage_v2.contract_version",
        "analysis.coverage_v2.dimensions.causes.status",
        "analysis.coverage_v2.dimensions.risks.status",
        "analysis.coverage_v2.dimensions.stakeholders.status",
        "analysis.coverage_v2.dimensions.trends.status",
        "analysis.coverage_v2.dimensions.uncertainty.status",
        # Temporal
        "analysis.temporal.dominant",
        # Epistemic
        "analysis.epistemic.numeric_sentences",
        "analysis.epistemic.sourced_pct",
        # Claims (counts; per-claim items are not pinned, extractor
        # evolution stays open as long as the headline counts hold)
        "analysis.claims_extracted.total",
        "analysis.claims_extracted.hedged_count",
        "analysis.claims_extracted.unhedged_count",
        "analysis.claims_extracted.prediction_count",
        # Decision-readiness (status string + dimensions present)
        "analysis.decision_readiness.status",
    ]

    # Source-fidelity + grounding-decomposition fields (only present
    # when source_text supplied). The grounding fields carry adopter-
    # facing recommendation text + classification proportions; an
    # unannounced shift in either is a real adopter regression.
    if source_text is not None:
        ALLOWLIST += [
            "analysis.verification.source_fidelity.total_numbers",
            "analysis.verification.source_fidelity.in_source",
            "analysis.verification.source_fidelity.not_in_source",
            "analysis.verification.source_fidelity.unsourced_rate",
            "analysis.verification.grounding_decomposition.proportions",
            "analysis.verification.grounding_decomposition.has_projection",
            "analysis.verification.grounding_decomposition.recommendation",
            "analysis.verification.grounding_decomposition.status",
        ]

    def _resolve(payload, path):
        node = payload
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return _MISSING
            node = node[part]
        return node

    drift = []
    for path in ALLOWLIST:
        s = _resolve(snapshot, path)
        v = _resolve(live, path)
        if s != v:
            drift.append((path, s, v))

    # Frame library matches: lock the FVS IDs as a set (order may
    # legitimately vary per detector revision).
    snap_frames = sorted(
        m["fvs_id"]
        for m in snapshot.get("analysis", {}).get("frame_library_matches", [])
        if "fvs_id" in m
    )
    live_frames = sorted(
        m["fvs_id"]
        for m in live.get("analysis", {}).get("frame_library_matches", [])
        if "fvs_id" in m
    )
    if snap_frames != live_frames:
        drift.append(("analysis.frame_library_matches[*].fvs_id (set)",
                      snap_frames, live_frames))

    # Per-claim source-fidelity diagnostics (v1.0.9+): the unsourced
    # values themselves are the actionable diagnostic. Lock them as a
    # set of values; context strings are allowed to wobble under
    # extractor evolution.
    if source_text is not None:
        snap_unsourced = sorted(
            it.get("value")
            for it in snapshot.get("analysis", {})
            .get("verification", {})
            .get("source_fidelity", {})
            .get("unsourced_items", [])
        )
        live_unsourced = sorted(
            it.get("value")
            for it in live.get("analysis", {})
            .get("verification", {})
            .get("source_fidelity", {})
            .get("unsourced_items", [])
        )
        if snap_unsourced != live_unsourced:
            drift.append(("verification.source_fidelity.unsourced_items[*].value",
                          snap_unsourced, live_unsourced))

    if drift:
        msg = [
            f"\nFixture {fixture_path.parent.name}: "
            f"{len(drift)} field(s) drifted from bundled snapshot.",
            "Either the detector regressed (fix the detector) or this is",
            "a deliberate behavior evolution (refresh the snapshot via",
            "the procedure documented in the fixture's frame_check_",
            "payload_refresh_reason field, then bump it again here).",
            "",
        ]
        for path, snap, live_v in drift:
            msg.append(f"  {path}")
            msg.append(f"    snapshot: {snap!r}")
            msg.append(f"    live:     {live_v!r}")
        pytest.fail("\n".join(msg))


# Sentinel for "field not present", distinguished from None so the
# allowlist comparison flags missing-vs-explicit-None as drift.
class _MISSING_TYPE:
    def __repr__(self):
        return "<missing>"


_MISSING = _MISSING_TYPE()
