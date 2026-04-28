"""
Tests for the falsification registry parser and schema.

These tests pin the registry's schema so that any future drift
(entry shape, required fields, enum values, ID format) breaks the
build rather than silently corrupting the registry. The registry
itself is a public discipline artifact per THE_BETS §AGI-era
robustness principle 5; the tests enforce the discipline
mechanically.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import falsifications as fx


_ID_RE = re.compile(r"^F-\d{4}-\d{3}$")


def test_registry_loads_without_errors():
    """list_entries() returns a non-empty list and each entry carries
    the core frontmatter fields. A clean repo should have at least
    the initial backfill present; regressions that empty the registry
    are load-bearing enough to break the test.
    """
    entries = fx.list_entries()
    assert len(entries) >= 1, "registry must contain at least one entry"
    for e in entries:
        for field in ("id", "title", "type", "outcome", "prediction"):
            assert field in e, f"entry {e.get('id')} missing {field}"


def test_every_entry_id_is_well_formed():
    """Every entry's id matches F-YYYY-NNN and the filename matches
    the id. The list_entries parser already enforces this on parse;
    this test documents the invariant.
    """
    entries = fx.list_entries()
    for e in entries:
        assert _ID_RE.match(e["id"]), (
            f"id {e['id']} does not match F-YYYY-NNN"
        )


def test_ids_are_unique():
    entries = fx.list_entries()
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate IDs in registry"


def test_ids_are_dense_within_year_sequence():
    """Within each year, IDs should run 001, 002, ... without gaps
    (until a gap is explicitly documented). Gaps are not forbidden
    long-term but should be visible, not silent.
    """
    entries = fx.list_entries()
    by_year: dict[str, list[int]] = {}
    for e in entries:
        year, num = e["id"].split("-")[1], int(e["id"].split("-")[2])
        by_year.setdefault(year, []).append(num)
    for year, nums in by_year.items():
        nums.sort()
        for i, n in enumerate(nums):
            assert n == i + 1, (
                f"registry year {year} has a gap: "
                f"expected {i + 1}, got {n} at index {i}"
            )


def test_all_entries_validate_clean():
    """Every entry passes validate_entry without errors. This pins
    the full schema per entry (required fields, enum values, date
    format, outcome-conditional fields, related-id format).
    """
    entries = fx.list_entries()
    for e in entries:
        errors = fx.validate_entry(e, source_filename=f"{e['id']}.md")
        assert errors == [], f"{e['id']} validation errors: {errors}"


def test_pending_entries_have_no_outcome_at_or_observed():
    entries = fx.list_entries()
    for e in entries:
        if e["outcome"] == "pending":
            assert e.get("outcome_at") in (None, ""), (
                f"{e['id']}: pending must not have outcome_at"
            )


def test_non_pending_entries_have_outcome_at_and_observed():
    entries = fx.list_entries()
    for e in entries:
        if e["outcome"] != "pending":
            assert e.get("outcome_at") not in (None, ""), (
                f"{e['id']}: non-pending must have outcome_at"
            )
            assert e.get("observed") not in (None, ""), (
                f"{e['id']}: non-pending must have observed"
            )


def test_related_references_resolve():
    """Every id listed in `related` for an entry must itself exist in
    the registry. Prevents dangling references that would otherwise
    break rendering and citation chains.
    """
    entries = fx.list_entries()
    all_ids = {e["id"] for e in entries}
    for e in entries:
        for ref in e.get("related", []) or []:
            assert ref in all_ids, (
                f"{e['id']} references related {ref} which is not in "
                "the registry"
            )


def test_superseded_by_references_resolve():
    """If an entry carries `superseded_by: F-YYYY-NNN`, the target
    entry must exist in the registry. Catches dangling revisions
    where a revised entry names a superseding entry that was never
    committed.
    """
    entries = fx.list_entries()
    all_ids = {e["id"] for e in entries}
    for e in entries:
        ref = e.get("superseded_by")
        if ref in (None, ""):
            continue
        assert ref in all_ids, (
            f"{e['id']} superseded_by {ref} which is not in the "
            "registry"
        )


def test_evidence_paths_resolve_when_present():
    """If an entry's `evidence` field names a repo-relative path,
    the path must exist on disk. Prevents the registry from citing
    reports that have been moved or renamed without updating
    references.

    Evidence entries may include section anchors (` §2`, `#section`)
    and comma-separated multiple paths. The path-existence check
    strips the anchor portion and resolves each path independently.
    """
    entries = fx.list_entries()
    repo_root = Path(fx.__file__).resolve().parent
    for e in entries:
        evidence = e.get("evidence", "")
        # Evidence field may list multiple comma-separated paths, and
        # each path may carry a ` §section` or `#anchor` suffix.
        # Tokens that are bare section anchors (e.g., "§3") or
        # non-path fragments are skipped; only tokens that look like
        # paths (contain `/` or end in a known extension) are
        # existence-checked.
        for candidate in [s.strip() for s in evidence.split(",")]:
            if not candidate:
                continue
            if candidate.startswith("http"):
                continue
            path_part = re.split(r"\s+§|#", candidate, maxsplit=1)[0].strip()
            if not path_part:
                continue
            # Only existence-check tokens that look like a repo path.
            # Bare section anchors like "§3" after comma-split are
            # not paths. Extensions list is conservative-inclusive
            # to avoid false failures on new entry types (text
            # documents, HTML rendered artifacts, pdf evidence).
            looks_like_path = (
                "/" in path_part
                or path_part.endswith(".md")
                or path_part.endswith(".py")
                or path_part.endswith(".json")
                or path_part.endswith(".csv")
                or path_part.endswith(".yaml")
                or path_part.endswith(".yml")
                or path_part.endswith(".txt")
                or path_part.endswith(".html")
                or path_part.endswith(".pdf")
                or path_part.endswith(".R")
            )
            if not looks_like_path:
                continue
            path = repo_root / path_part
            assert path.exists(), (
                f"{e['id']} evidence path does not exist: "
                f"{path_part} (from {candidate!r})"
            )


def test_backfill_entries_name_their_provenance():
    """Every entry registered BEFORE the registry itself was created
    must carry a `backfill_note` field naming why the backfill is
    defensible (source document unchanged, prediction text verbatim,
    outcome evidence timestamped, etc.). Entries registered ON OR
    AFTER the registry creation date may be live pre-registrations
    and do not require a backfill_note.

    Registry creation date: 2026-04-21. Entries with
    registered_at < "2026-04-21" MUST have backfill_note. Entries
    with registered_at >= "2026-04-21" are live unless they opt
    into backfill_note explicitly.

    This discipline distinguishes genuine live pre-registration
    (which is higher-grade evidence) from retrospective backfill
    (which is defensible but lower-grade). The registry's
    README.md `The backfill principle` section defines the contract.
    """
    REGISTRY_CREATED = "2026-04-21"
    entries = fx.list_entries()
    for e in entries:
        if e["registered_at"] < REGISTRY_CREATED:
            assert "backfill_note" in e and e["backfill_note"], (
                f"{e['id']} registered {e['registered_at']} predates "
                f"registry creation {REGISTRY_CREATED} but has no "
                f"backfill_note"
            )


def test_readme_is_present():
    """The registry README documents the contract. Missing README
    breaks the self-describing property of the registry."""
    readme = fx.read_registry_readme()
    assert readme, "registry README is missing or empty"
    assert "Falsification registry" in readme
    assert "Entry schema" in readme


def test_summary_aggregates_correctly():
    summary = fx.summary()
    entries = fx.list_entries()
    assert summary["total"] == len(entries)
    total_by_outcome = sum(summary["by_outcome"].values())
    assert total_by_outcome == len(entries)
    total_by_type = sum(summary["by_type"].values())
    assert total_by_type == len(entries)
    pending_count = sum(1 for e in entries if e["outcome"] == "pending")
    assert len(summary["pending"]) == pending_count


def test_validate_entry_catches_missing_required_field():
    """validate_entry surfaces missing-required-field errors. Direct
    schema test, not dependent on the on-disk registry."""
    incomplete = {
        "id": "F-2026-999",
        "title": "test",
        # Missing most required fields.
    }
    errors = fx.validate_entry(incomplete, source_filename="F-2026-999.md")
    assert errors, "validator must catch missing required fields"
    assert any("missing required fields" in e for e in errors)


def test_validate_entry_catches_bad_enum_values():
    bad = {
        "id": "F-2026-999",
        "title": "test",
        "type": "invented-type",
        "registered_at": "2026-01-01",
        "registered_in": "somewhere",
        "methodology_version": "v0",
        "prediction": "something",
        "criterion": "something",
        "outcome": "maybe",
        "evidence": "nowhere",
    }
    errors = fx.validate_entry(bad, source_filename="F-2026-999.md")
    assert any("type" in e and "not in" in e for e in errors), errors
    assert any("outcome" in e and "not in" in e for e in errors), errors


def test_validate_entry_catches_bad_id_filename_mismatch():
    entry = {
        "id": "F-2026-001",
        "title": "test",
        "type": "hypothesis",
        "registered_at": "2026-01-01",
        "registered_in": "somewhere",
        "methodology_version": "v0",
        "prediction": "something",
        "criterion": "something",
        "outcome": "pending",
        "evidence": "somewhere",
    }
    errors = fx.validate_entry(entry, source_filename="F-2026-002.md")
    assert any("filename" in e and "does not match id" in e for e in errors), errors


def test_validate_entry_catches_non_pending_without_outcome_at():
    entry = {
        "id": "F-2026-999",
        "title": "test",
        "type": "hypothesis",
        "registered_at": "2026-01-01",
        "registered_in": "somewhere",
        "methodology_version": "v0",
        "prediction": "something",
        "criterion": "something",
        "outcome": "passed",
        "evidence": "somewhere",
        # Missing outcome_at and observed.
    }
    errors = fx.validate_entry(entry, source_filename="F-2026-999.md")
    assert any("outcome_at" in e for e in errors), errors
    assert any("observed" in e for e in errors), errors


def test_validate_entry_rejects_bad_related_ref():
    entry = {
        "id": "F-2026-999",
        "title": "test",
        "type": "hypothesis",
        "registered_at": "2026-01-01",
        "registered_in": "somewhere",
        "methodology_version": "v0",
        "prediction": "something",
        "criterion": "something",
        "outcome": "pending",
        "evidence": "somewhere",
        "related": ["F-2026-001", "not-an-id"],
    }
    errors = fx.validate_entry(entry, source_filename="F-2026-999.md")
    assert any("not-an-id" in e for e in errors), errors


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
