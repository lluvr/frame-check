"""
Shared parsers for the Frame Library canonical index.

INDEX.md at data/frame_library/INDEX.md and VERSION at
data/frame_library/VERSION are the source of truth for per-entry
status (canon / draft / aspirational / retired) and for the library's
SemVer.

mcp_server.py decorates frame_library_matches with status and carries
the library version in provenance. This module is the one place the
INDEX.md format is understood, so any consumer that needs status or
version reads through here.

Responsibilities:
  read_library_version() -> str
      Library SemVer from VERSION, 'unversioned' on miss. Never raises.
  parse_entry_statuses() -> dict[str, str]
      Map of {FVS-XXX: status} from INDEX.md, {} on miss. Never raises.

Both functions are tolerant of missing files so repo consumers (corpus
builder, MCP server, tests) work on clean checkouts with or without
the data/frame_library/ tree populated.
"""

from __future__ import annotations

import re
from pathlib import Path

# Resolve the library directory relative to this module so consumers
# do not need to pass it. In a fresh repo clone, mcp_server.py lives
# at the repo root alongside this module and the data/frame_library/
# tree. In a pip-installed wheel, the package data is bundled under
# a `framecheck_mcp/` directory next to this module. Probe for the
# populated package
# data subtree first; fall back to repo-layout if not found. Probing
# for the populated subtree (not just the package directory) handles
# the dev case where `framecheck_mcp/` exists with only __init__.py
# because build-time copies have not been staged. This mirrors
# mcp_server.py's _DATA_ROOT resolution.
_REPO_ROOT = Path(__file__).resolve().parent
_PKG_DATA_DIR = _REPO_ROOT / "framecheck_mcp"
if (_PKG_DATA_DIR / "data").is_dir():
    _DATA_ROOT = _PKG_DATA_DIR
else:
    _DATA_ROOT = _REPO_ROOT
_LIBRARY_DIR = _DATA_ROOT / "data" / "frame_library"


# Pipe-table row pattern for INDEX.md: captures the FVS ID, the
# Name (column 2), and the Status (column 5). Column order in
# INDEX.md is (ID | Name | Class | Detection | Status | Curated).
# The non-greedy [^|]* between pipes tolerates whitespace and leaves
# detail parsing to dedicated tools; this parser only cares about
# the three values it extracts.
#
# If the column order changes, this regex must change. Pin that in
# the INDEX.md header (documented in CONTRIBUTING.md next to the
# library format spec) so the dependency is visible.
_INDEX_ROW_RE = re.compile(
    r'^\|\s*(FVS-\d+)\s*\|\s*([^|]+?)\s*\|[^|]*\|[^|]*\|\s*(\w+)\s*\|',
    re.MULTILINE,
)

# Extended row regex that ALSO captures column 4 (Detection). Used by
# parse_detection_states. Keeping _INDEX_ROW_RE narrow (three captures)
# preserves the existing parse_entry_statuses / parse_entry_titles
# contract; this extended form just adds one more capture for the
# detection column (retired / yes / n/a / gap).
_INDEX_ROW_RE_WITH_DETECTION = re.compile(
    r'^\|\s*(FVS-\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|',
    re.MULTILINE,
)


def read_library_version() -> str:
    """Library-wide SemVer from data/frame_library/VERSION.

    The frame taxonomy is a citable artifact. The library version
    pins a specific snapshot so a downstream reference continues
    resolving to the data it resolved to at citation time even after
    subsequent revisions.

    Returns the stripped VERSION file content, or 'unversioned' if
    the file is missing, unreadable, or empty. Never raises.
    """
    version_path = _LIBRARY_DIR / "VERSION"
    try:
        v = version_path.read_text(encoding="utf-8").strip()
        return v or "unversioned"
    except (FileNotFoundError, OSError):
        return "unversioned"


def parse_entry_statuses() -> dict[str, str]:
    """Per-entry status from data/frame_library/INDEX.md.

    INDEX.md is the source of truth for which frames are canon /
    draft / aspirational / retired. Downstream citations and MCP
    responses use this status to communicate the stability
    guarantee: canon entries have stable ID + name + identification;
    draft entries have stable ID only.

    Returns a {FVS-XXX: status} map lowercased for consistent key
    comparison. Missing INDEX.md, unreadable file, or empty index
    returns an empty dict. Never raises.

    Status values are not validated here because the INDEX.md status
    taxonomy is defined in that file, not here. Callers that need
    the taxonomy should default unknown values to 'draft' (the
    conservative fallback that never over-promises stability).
    """
    index_path = _LIBRARY_DIR / "INDEX.md"
    try:
        text = index_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    return {
        m.group(1): m.group(3).strip().lower()
        for m in _INDEX_ROW_RE.finditer(text)
    }


def parse_detection_states() -> dict[str, str]:
    """Per-entry detection state from data/frame_library/INDEX.md.

    Returns {FVS-XXX: detection_state} where detection_state is the
    value in the 4th pipe-column of INDEX.md row (after the Class
    column). Canonical values per INDEX.md:

      - ``yes``    : active detection rule fires in `frame_library.suggest_frames`
      - ``gap``    : text-side entry, no rule yet wired
      - ``n/a``    : meta-side entry, no rule expected
      - ``retired``: rule previously wired, retired after validation
                     (FVS-001, FVS-008, FVS-015 as of 2026-04-18;
                     library version bumped to signal the state change)

    Returns a {FVS-XXX: state} map lowercased for consistent key
    comparison. Missing INDEX.md, unreadable file, or empty index
    returns an empty dict. Never raises.
    """
    index_path = _LIBRARY_DIR / "INDEX.md"
    try:
        text = index_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    return {
        m.group(1): m.group(4).strip().lower()
        for m in _INDEX_ROW_RE_WITH_DETECTION.finditer(text)
    }


def parse_entry_titles() -> dict[str, str]:
    """Per-entry display title (Name column) from INDEX.md.

    Used by canon-graph reference shapes (decision_readiness.
    library_entry_ref) so MCP responses, profile JSON, and
    aggregate findings carry human-readable names alongside the
    FVS-ID. Without this an agent surfacing a finding has to
    look up names elsewhere or render bare IDs.

    Returns {FVS-XXX: title} preserving the case from INDEX.md
    (proper-case names like "Failure Framing"). Missing INDEX.md,
    unreadable file, or empty index returns an empty dict. Never
    raises; callers should fall back to the bare fvs_id when a
    title is missing.
    """
    index_path = _LIBRARY_DIR / "INDEX.md"
    try:
        text = index_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    return {
        m.group(1): m.group(2).strip()
        for m in _INDEX_ROW_RE.finditer(text)
    }


# Filename pattern: every entry in data/frame_library/ follows
# FVS-XXX_snake_case_title.md (e.g., FVS-001_frame_amplification.md).
# parse_entry_filenames() returns {FVS-XXX: filename} so callers that
# need the canonical source-tree path (e.g., to build a clickable
# GitHub URL pointing at the entry's markdown) can resolve the slug
# without each carrying their own directory-scan logic.
_ENTRY_FILENAME_RE = re.compile(r"^(FVS-\d{3})_.+\.md$")


def parse_entry_filenames() -> dict[str, str]:
    """Per-entry source filename from data/frame_library/.

    Used by canon-graph reference shapes that need to construct a
    URL pointing at the entry's markdown source (e.g., a GitHub blob
    link an end-user can click). The filename carries the human-
    readable slug after the FVS-ID prefix, which the
    {FVS-ID -> title} map alone does not give us in a slugified form
    suitable for a URL path.

    Returns {FVS-XXX: filename} for every file in
    data/frame_library/ that matches the canonical naming pattern.
    Missing directory or empty listing returns an empty dict. Never
    raises; callers should treat a missing entry as "no canonical
    URL available" and fall back to the resource URI or bare fvs_id.
    """
    if not _LIBRARY_DIR.is_dir():
        return {}
    out: dict[str, str] = {}
    try:
        for fname in _LIBRARY_DIR.iterdir():
            m = _ENTRY_FILENAME_RE.match(fname.name)
            if m:
                out[m.group(1)] = fname.name
    except OSError:
        return {}
    return out
