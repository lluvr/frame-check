"""
Tests for the shared frame library index parser.

frame_library_index.py is the single source of truth for INDEX.md row
format and VERSION file location. It is consumed by mcp_server.py
(frame match status decoration). These tests lock the format contract
so a future change to INDEX.md must be visible to a test run.
"""


import pytest

import frame_library_index as fli


# ── Contract tests on the live INDEX.md / VERSION ────────────────────


class TestLiveIndexContract:
    """Exercise the parser against the actual committed INDEX.md so a
    format change anywhere in the file triggers a test failure. This
    is the contract the corpus builder and MCP server rely on."""

    def test_version_is_semver_shaped(self):
        v = fli.read_library_version()
        # Not asserting a specific version; that drifts. Asserting
        # the shape: non-empty and either 'unversioned' (fallback
        # signal) or looks like a SemVer.
        assert v
        assert v == "unversioned" or v[0].isdigit()

    def test_all_20_entries_parse(self):
        """INDEX.md currently tracks 20 FVS entries. Every one must
        come out of the parser so downstream citations carry status
        for every entry."""
        s = fli.parse_entry_statuses()
        assert len(s) == 20
        for i in range(1, 21):
            fvs_id = f"FVS-{i:03d}"
            assert fvs_id in s, f"{fvs_id} not parsed from INDEX.md"

    def test_statuses_are_lowercased(self):
        """Callers compare against 'canon' / 'draft' / 'aspirational' /
        'retired' in lowercase. If INDEX.md uses any other case, the
        parser must normalize before emitting."""
        s = fli.parse_entry_statuses()
        for fvs_id, status in s.items():
            assert status == status.lower(), (
                f"{fvs_id} status {status!r} is not lowercased"
            )

    def test_statuses_are_valid_taxonomy(self):
        """Every parsed status must be one of the four defined by
        INDEX.md's status taxonomy. If a new status appears, the
        taxonomy documentation and downstream consumers must update
        deliberately, not silently."""
        valid = {"canon", "draft", "aspirational", "retired"}
        s = fli.parse_entry_statuses()
        for fvs_id, status in s.items():
            assert status in valid, (
                f"{fvs_id} has unknown status {status!r}; "
                f"extend the taxonomy in INDEX.md + downstream "
                f"consumers before adding a new value"
            )

    def test_all_20_titles_parse(self):
        """parse_entry_titles must extract a non-empty title for every
        FVS-ID in INDEX.md. Titles flow into canon-graph reference
        objects (decision_readiness.library_entry_ref) so the MCP
        responses, profile JSON, and aggregate findings can render
        proper names without falling back to bare IDs."""
        t = fli.parse_entry_titles()
        assert len(t) == 20
        for i in range(1, 21):
            fvs_id = f"FVS-{i:03d}"
            assert fvs_id in t, f"{fvs_id} title not parsed from INDEX.md"
            assert t[fvs_id], (
                f"{fvs_id} has empty title; canon-graph rendering "
                f"would fall back to bare ID"
            )

    def test_titles_preserve_proper_case(self):
        """Titles in INDEX.md are proper-case ('Failure Framing',
        'Authority by Citation'). Unlike statuses (which the parser
        lowercases for consistent key comparison), titles must
        round-trip with original capitalization for human-readable
        rendering."""
        t = fli.parse_entry_titles()
        # Pin two anchor titles whose proper case is canon
        assert t.get("FVS-007") == "Failure Framing", (
            f"FVS-007 title proper case wrong: {t.get('FVS-007')!r}"
        )
        assert t.get("FVS-016") == "Authority by Citation", (
            f"FVS-016 title proper case wrong: {t.get('FVS-016')!r}"
        )


# ── Behavior tests on synthetic inputs ───────────────────────────────


class TestParserBehavior:
    """Test the parser against synthetic INDEX.md variations to lock
    down edge cases without touching the live file."""

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fli, "_LIBRARY_DIR", tmp_path)
        assert fli.parse_entry_statuses() == {}
        assert fli.parse_entry_titles() == {}
        assert fli.read_library_version() == "unversioned"

    def test_empty_version_file_returns_fallback(self, tmp_path, monkeypatch):
        (tmp_path / "VERSION").write_text("", encoding="utf-8")
        monkeypatch.setattr(fli, "_LIBRARY_DIR", tmp_path)
        assert fli.read_library_version() == "unversioned"

    def test_version_file_trimmed(self, tmp_path, monkeypatch):
        """VERSION files may end with a trailing newline. The parser
        must return the semver alone, not the raw bytes."""
        (tmp_path / "VERSION").write_text("0.2.0\n", encoding="utf-8")
        monkeypatch.setattr(fli, "_LIBRARY_DIR", tmp_path)
        assert fli.read_library_version() == "0.2.0"

    def test_pipe_table_parsed(self, tmp_path, monkeypatch):
        """Minimal synthetic INDEX.md exercising the row pattern:
        surrounding prose is ignored, only the pipe-table rows count."""
        index = tmp_path / "INDEX.md"
        index.write_text(
            "# Frame Library Index\n\n"
            "Some prose here.\n\n"
            "| ID | Name | Class | Detection | Status | Curated |\n"
            "|----|------|-------|-----------|--------|---------|\n"
            "| FVS-001 | Test A | text-side | yes | canon | 2026-04-17 |\n"
            "| FVS-042 | Test B | meta-side | n/a | draft | 2026-04-17 |\n"
            "| FVS-099 | Test C | text-side | gap | retired | 2026-04-17 |\n"
            "\nMore prose.\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(fli, "_LIBRARY_DIR", tmp_path)
        s = fli.parse_entry_statuses()
        assert s == {
            "FVS-001": "canon",
            "FVS-042": "draft",
            "FVS-099": "retired",
        }

    def test_rows_outside_pipe_format_ignored(self, tmp_path, monkeypatch):
        """Plain-text mentions of FVS IDs in prose must NOT be parsed
        as rows. Only the pipe-table format counts."""
        (tmp_path / "INDEX.md").write_text(
            "FVS-001 is mentioned here in prose. Nothing to see.\n"
            "See also FVS-002 (a reference).\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(fli, "_LIBRARY_DIR", tmp_path)
        assert fli.parse_entry_statuses() == {}

    def test_whitespace_tolerance(self, tmp_path, monkeypatch):
        """The parser tolerates irregular column spacing (common in
        hand-edited markdown)."""
        (tmp_path / "INDEX.md").write_text(
            "|FVS-001| Name| c |d|canon|x|\n"
            "|  FVS-002  |  Name  |  c  |  d  |  draft  |  x  |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(fli, "_LIBRARY_DIR", tmp_path)
        assert fli.parse_entry_statuses() == {
            "FVS-001": "canon",
            "FVS-002": "draft",
        }


if __name__ == "__main__":
    # Wire pytest invocation into the file so the standard
    # run_tests.py runner (which executes `python3 <test_file>`)
    # can include this suite. Without this block the tests are
    # only reachable via `python3 -m pytest`, which the SUITES
    # manifest does not invoke. Using pytest from __main__ keeps
    # the fixtures (tmp_path, monkeypatch) working and stays
    # consistent with the other pytest-style test files.
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
