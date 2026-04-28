"""Regression tests for adversarial fixtures.

Each fixture in data/adversarial_fixtures/{slug}/ has:
  document.md  - the deceptive document
  expected.json - captured substrate reading (regression baseline)
  audit.md     - per-level catch-vs-miss analysis

This test loads each fixture, runs build_epistemic_payload, and
compares specific captured fields against expected.json. A failing
test means the substrate's reading on this fixture has changed;
the operator decides whether the change is deliberate (update
expected.json + note in audit.md) or a regression to fix.

Discipline: see data/adversarial_fixtures/README.md. The captured
fields are deliberately a SUBSET of the full payload to keep the
expected.json reviewable when the substrate evolves and to ensure
the test fails on per-level discipline changes, not on every minor
field addition.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import mcp_server


_REPO_ROOT = Path(__file__).parent
_FIXTURES_DIR = _REPO_ROOT / "data" / "adversarial_fixtures"


def _list_fixtures() -> list[Path]:
    """Return fixture subdirectories. A fixture directory is one
    that contains document.md + expected.json. Subdirectories
    without those files are skipped (e.g., the README's data dir).
    """
    if not _FIXTURES_DIR.exists():
        return []
    fixtures = []
    for entry in sorted(_FIXTURES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / "document.md").exists() and (
            entry / "expected.json"
        ).exists():
            fixtures.append(entry)
    return fixtures


def _capture_reading(payload: dict) -> dict:
    """Build the captured-reading dict from a frame_check payload.
    Mirrors the structure used at fixture composition time so the
    regression comparison is stable. See data/adversarial_fixtures/
    README.md for the rationale on which fields are pinned.
    """
    a = payload["analysis"]
    d = payload.get("divergence") or {}
    return {
        "genre": a.get("genre", {}),
        "voice": a.get("voice", {}),
        "temporal": a.get("temporal", {}),
        "frame_library_matches": [
            {
                "fvs_id": m.get("fvs_id"),
                "claim_level": m.get("claim_level"),
            }
            for m in a.get("frame_library_matches", []) or []
        ],
        "frame_deepening": a.get("frame_deepening", {}),
        "epistemic_sourced_pct": a.get("epistemic", {}).get(
            "sourced_pct"
        ),
        "decision_readiness_dims": {
            name: {
                "signal_text": dim.get("signal_text"),
                "claim_level": dim.get("claim_level"),
            }
            for name, dim in (
                a.get("decision_readiness", {}).get("dimensions") or {}
            ).items()
        },
        "absence_clusters": [
            {
                "dimension": c.get("dimension"),
                "signal_strength": c.get("signal_strength"),
                "member_frames": c.get("member_frames"),
                "claim_level": c.get("claim_level"),
            }
            for c in d.get("absence_clusters", []) or []
        ],
        "frame_patterns": [
            {
                "id": fp.get("id"),
                "claim_level": fp.get("claim_level"),
            }
            for fp in d.get("frame_patterns", []) or []
        ],
    }


@pytest.mark.parametrize(
    "fixture_dir",
    _list_fixtures(),
    ids=lambda p: p.name,
)
def test_adversarial_fixture_reading_matches_baseline(
    fixture_dir: Path,
) -> None:
    """The substrate's reading on this fixture must match the
    captured baseline. A failing test means the substrate has
    changed its reading; the operator updates expected.json and
    notes the change in audit.md when the change is deliberate,
    or fixes the regression when not.
    """
    document_text = (fixture_dir / "document.md").read_text()
    with open(fixture_dir / "expected.json") as f:
        expected = json.load(f)

    payload = mcp_server.build_epistemic_payload(
        document_text,
        include_divergence=True,
        user_goal="decide",
    )
    actual = _capture_reading(payload)

    # Field-by-field comparison so the failure message names which
    # field diverged. Direct dict equality would obscure where the
    # regression is.
    for key in sorted(expected.keys()):
        assert key in actual, (
            f"{fixture_dir.name}: captured reading is missing "
            f"key {key!r}; substrate may have removed the field"
        )
        assert actual[key] == expected[key], (
            f"{fixture_dir.name}: substrate's reading for "
            f"{key!r} differs from baseline.\n"
            f"  expected: {json.dumps(expected[key], sort_keys=True, indent=2)[:500]}\n"
            f"  actual:   {json.dumps(actual[key], sort_keys=True, indent=2)[:500]}"
        )


def test_adversarial_fixture_suite_has_at_least_one_fixture() -> None:
    """The suite must carry at least one fixture. Pinning this
    so a future cleanup that accidentally drops all fixtures
    surfaces immediately.
    """
    fixtures = _list_fixtures()
    assert len(fixtures) >= 1, (
        f"adversarial fixture suite must have at least one "
        f"fixture in {_FIXTURES_DIR}; found {len(fixtures)}"
    )


def test_recapture_helper_is_idempotent_on_unchanged_substrate() -> None:
    """The recapture.py helper script must be idempotent: running it
    against fixtures whose substrate behavior has not changed must
    produce byte-identical expected.json files. Pins the helper so a
    future refactor of `_capture_reading` or the recapture script
    cannot silently drift the expected.json shape.

    Approach: snapshot every fixture's expected.json bytes; invoke
    the helper via subprocess; compare bytes; restore on mismatch.
    Subprocess invocation rather than direct import so the test
    exercises the actual CLI entry point.
    """
    import subprocess

    snapshots: dict[Path, bytes] = {}
    for fixture_dir in _list_fixtures():
        expected_path = fixture_dir / "expected.json"
        snapshots[expected_path] = expected_path.read_bytes()

    try:
        result = subprocess.run(
            [
                "python3",
                str(_REPO_ROOT / "data" / "adversarial_fixtures" / "recapture.py"),
                "--all",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"recapture.py --all exited with {result.returncode}; "
            f"stderr: {result.stderr[:500]}"
        )

        for expected_path, original_bytes in snapshots.items():
            current_bytes = expected_path.read_bytes()
            assert current_bytes == original_bytes, (
                f"{expected_path.relative_to(_REPO_ROOT)} differs after "
                f"recapture (substrate hasn't changed; recapture should "
                f"be idempotent). Diff size: original "
                f"{len(original_bytes)} bytes, recaptured "
                f"{len(current_bytes)} bytes."
            )
    finally:
        for expected_path, original_bytes in snapshots.items():
            expected_path.write_bytes(original_bytes)


def test_each_fixture_has_required_files() -> None:
    """Each fixture directory must carry document.md + expected.json
    + audit.md. The audit is part of the discipline; without it the
    fixture is not load-bearing.
    """
    for fixture_dir in _list_fixtures():
        for required in ("document.md", "expected.json", "audit.md"):
            path = fixture_dir / required
            assert path.exists(), (
                f"{fixture_dir.name}: missing required file "
                f"{required} (per data/adversarial_fixtures/"
                f"README.md discipline)"
            )


if __name__ == "__main__":
    # Script-mode runner for parity with other test_*.py modules.
    failures = []
    for fixture_dir in _list_fixtures():
        try:
            test_adversarial_fixture_reading_matches_baseline(fixture_dir)
            print(f"  PASS   {fixture_dir.name}")
        except AssertionError as e:
            failures.append((fixture_dir.name, str(e)))
            print(f"  FAIL   {fixture_dir.name}: {str(e)[:200]}")
    try:
        test_adversarial_fixture_suite_has_at_least_one_fixture()
        print("  PASS   suite has at least one fixture")
    except AssertionError as e:
        failures.append(("suite_has_at_least_one_fixture", str(e)))
        print(f"  FAIL   suite_has_at_least_one_fixture: {e}")
    try:
        test_each_fixture_has_required_files()
        print("  PASS   each fixture has required files")
    except AssertionError as e:
        failures.append(("each_fixture_has_required_files", str(e)))
        print(f"  FAIL   each_fixture_has_required_files: {e}")
    if failures:
        print(f"\n=== {len(failures)} FAILED ===")
        raise SystemExit(1)
    print(f"\n=== ALL ADVERSARIAL FIXTURE TESTS PASSED ===")
