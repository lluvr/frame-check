"""Resource discovery and reads for the Frame Check MCP server.

Sits one layer above `mcp_log` in the module layer cake: depends on
`mcp_log` for stderr diagnostics and on path helpers it computes
from its own `__file__`, but does not import any of the higher
layers (compose, schema, protocol, cli). `mcp_server.py` re-exports
the public symbols for backward compatibility.

What lives here:

  Module-level state:
    _DATA_ROOT, _SCRIPT_DIR, _PKG_DATA_DIR (path detection)
    RESOURCE_SCHEME (`frame-check`)
    All directory and file path constants for the bundled corpus
    Cache state populated lazily by `_ensure_caches`:
      _FRAME_VERSIONS, _FRAME_ADJACENCY, _FRAME_STATUSES,
      _FRAME_LIBRARY_VERSION

  Discovery / enumeration:
    _library_entries, _library_v3_entries
    _worked_example_entries, _transmission_entries
    _calibration_runs, _corpus_entry_slugs

  Path resolution (traversal-safe):
    _library_entry_path, _library_index_path
    _worked_example_path, _worked_examples_readme_path
    _transmission_path, _transmissions_readme_path
    _calibration_run_path, _best_calibration_run
    _find_corpus_entry_path, _find_corpus_pair_path
    _find_latest_aggregate

  Spec assembly:
    _spec_fd_v1_parts, _spec_fd_v1_index_markdown

  Cache primitives:
    _parse_frame_adjacency, _ensure_caches

  MCP-shape resource handlers:
    _list_resources, _read_resource

  Shared utilities:
    _signal_strength_for (used by both resource builders and
      compose-layer signal classification)
    _content_hash (sha256 of resource text; pinned in resources/list
      metadata so clients can detect drift)

The compose layer (still in `mcp_server.py` during Step 2) imports
the constants and helpers it needs (`_LIBRARY_DIR`,
`_CORPUS_ENTRIES_DIR`, `_AGGREGATE_RESULTS_DIR`,
`_signal_strength_for`, `_ensure_caches`, the cache state via
module-attribute access for late-binding) directly from this
module. Tests that read `mcp_server.<symbol>` continue to resolve
via re-exports in `mcp_server.py`.
"""

from __future__ import annotations

from typing import Any

import json
import os
import re


# ── Path detection ─────────────────────────────────────────────────
#
# On a fresh repo clone, data files (frame library, worked examples,
# transmissions, methodology, calibration, validation corpus,
# divergence spec) sit alongside this file at the repo root. On a
# pip-installed wheel, the same files are bundled under a
# `framecheck_mcp/` package directory next to this file. Probe for
# the data subtree under the package directory; fall back to repo-
# layout if not found. The probe checks for a populated subtree
# (not just the package directory itself) because the dev repo may
# have an empty `framecheck_mcp/` directory containing only
# __init__.py (build-time copies are not staged in dev mode; see
# setup.py for the cross-platform staging hook).

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PKG_DATA_DIR = os.path.join(_SCRIPT_DIR, "framecheck_mcp")
if os.path.isdir(os.path.join(_PKG_DATA_DIR, "data")):
    _DATA_ROOT = _PKG_DATA_DIR
else:
    _DATA_ROOT = _SCRIPT_DIR


# ── Resource scheme + canon-graph reference shape ─────────────────

RESOURCE_SCHEME = "frame-check"

# Canon-graph reference shape is owned by decision_readiness.py so
# the per-dimension library_entries on the profile, the
# adjacent_frames on each matched frame, and the aggregate
# library_entries_per_dimension all emit the same object form
# {fvs_id, library_resource_uri, public_url}. A test in
# test_decision_readiness.py pins LIBRARY_RESOURCE_SCHEME ==
# RESOURCE_SCHEME so the two cannot drift.
from decision_readiness import (  # noqa: F401, E402  (re-exported via __all__; module-level after section comment)
    library_entry_ref as _library_entry_ref,
    dimensions_affecting as _dimensions_affecting,
)
# These two are re-exported as private names so mcp_compose can import
# them from a single source of truth (this module). Listed in
# __all__ at the end of the module.

# Frame library status + version readers (single source of truth
# for INDEX.md row format and VERSION file location).
from frame_library_index import (  # noqa: E402
    read_library_version as _read_frame_library_version,
    parse_entry_statuses as _parse_frame_statuses,
)


# ── Public surface ────────────────────────────────────────────────
#
# Declares the names downstream callers (mcp_server, mcp_compose,
# tests under ``tests/``) read out of this module via ``from
# mcp_resources import <name>``. Listing them in ``__all__`` makes
# the re-export pattern (``_library_entry_ref``, ``_dimensions_affecting``,
# ``_read_frame_library_version``, ``_parse_frame_statuses`` are all
# imported here for downstream consumption rather than internal use)
# visible to ``ruff F401`` and ``CodeQL py/unused-import`` so those
# checks no longer flag the imports as dead.
__all__ = [
    "RESOURCE_SCHEME",
    "_LIBRARY_DIR", "_LIBRARY_V3_DIR", "_WORKED_EXAMPLES_DIR",
    "_TRANSMISSIONS_DIR", "_METHODOLOGY_PATH",
    "_CALIBRATION_RESULTS_DIR", "_AGGREGATE_RESULTS_DIR",
    "_CORPUS_ENTRIES_DIR", "_SPEC_FD_V1_PART2_PATH",
    "_SIGNAL_STRENGTH_THRESHOLDS",
    "_signal_strength_for", "_content_hash",
    "_ensure_caches", "_parse_frame_adjacency",
    "_spec_fd_v1_parts", "_spec_fd_v1_index_markdown",
    "_library_entries", "_library_v3_entries",
    "_worked_example_entries", "_transmission_entries",
    "_transmission_path", "_transmissions_readme_path",
    "_worked_example_path", "_library_entry_path",
    "_library_index_path", "_worked_examples_readme_path",
    "_calibration_runs", "_calibration_run_path",
    "_best_calibration_run", "_corpus_entry_slugs",
    "_find_corpus_entry_path", "_find_corpus_pair_path",
    "_find_latest_aggregate", "_list_resources", "_read_resource",
    "_library_entry_ref", "_dimensions_affecting",
    "_read_frame_library_version", "_parse_frame_statuses",
    "_FRAME_STATUSES", "_FRAME_LIBRARY_VERSION",
    "_FRAME_VERSIONS", "_FRAME_ADJACENCY",
    "_get_frame_statuses", "_get_frame_library_version",
    "_get_frame_versions", "_get_frame_adjacency",
]


# ── Bundled-corpus path constants ─────────────────────────────────

_LIBRARY_DIR = os.path.join(_DATA_ROOT, "data", "frame_library")
_LIBRARY_V3_DIR = os.path.join(_DATA_ROOT, "data", "frame_library_v3")
_WORKED_EXAMPLES_DIR = os.path.join(_DATA_ROOT, "data", "worked_examples")
_TRANSMISSIONS_DIR = os.path.join(_DATA_ROOT, "data", "transmissions")
_METHODOLOGY_PATH = os.path.join(_DATA_ROOT, "METHODOLOGY.md")
_CALIBRATION_RESULTS_DIR = os.path.join(
    _DATA_ROOT, "calibration", "results",
)
# Aggregate findings live under validation/decision_readiness/results/.
# Each run writes {date}-{corpus_state_hash}/aggregate.json + .md.
# The MCP server exposes the most recent aggregate.json as a resource
# (frame-check://aggregate/latest) so agents can query corpus-level
# findings without fetching from the corpus_site.
_AGGREGATE_RESULTS_DIR = os.path.join(
    _DATA_ROOT, "validation", "decision_readiness", "results",
)
# Validation corpus: per-entry document.md + metadata.yaml +
# profile.json. Exposed via MCP so agents reading the aggregate
# (which cites corpus entries by slug) can chain to the actual
# documents. Resource URIs:
#   frame-check://corpus/{slug}  -> document.md (text/markdown)
#   frame-check://corpus/{slug}/profile -> profile.json (json)
# See _find_corpus_entry_path for the traversal-safe resolver.
_CORPUS_ENTRIES_DIR = os.path.join(
    _DATA_ROOT, "validation", "decision_readiness", "corpus",
)

# Frame Divergence v1 spec. Part 2 (the interface contract) is the
# authored canonical reference per FRAME_DIVERGENCE_CONTRACT_v1.md §8
# (MCP resource URIs). Exposed as:
#   frame-check://spec/frame-divergence/v1         -> generated index
#   frame-check://spec/frame-divergence/v1/part-2  -> FRAME_DIVERGENCE_CONTRACT_v1.md
# Deploys without the spec files (e.g., minimal MCP package builds)
# simply do not advertise the spec index or parts.
_SPEC_FD_V1_PART2_PATH = os.path.join(
    _DATA_ROOT, "FRAME_DIVERGENCE_CONTRACT_v1.md"
)


# ── Module-level cache state (populated lazily by _ensure_caches) ─
#
# These are MUTATED post-import (None at module load; populated on
# first MCP request). Consumers in other modules MUST access via
# module-attribute lookup, e.g.:
#
#     import mcp_resources as _resources_mod
#     versions = _resources_mod._FRAME_VERSIONS or {}
#
# A `from mcp_resources import _FRAME_VERSIONS` would capture the
# value at IMPORT time (None) and never see the population.

_FRAME_STATUSES: dict[str, Any] | None = None
_FRAME_LIBRARY_VERSION: str | None = None
_FRAME_VERSIONS: dict[str, Any] | None = None
_FRAME_ADJACENCY: dict[str, Any] | None = None


def _get_frame_statuses() -> dict[str, Any] | None:
    """Return the live ``_FRAME_STATUSES`` cache.

    Accessor wrapper so consumers (mcp_compose, mcp_server) can read
    the post-``_ensure_caches`` value without importing the module
    object solely for late attribute lookup. ``from mcp_resources
    import _FRAME_STATUSES`` would capture ``None`` at import time;
    ``_get_frame_statuses()`` always returns the current value.
    """
    return _FRAME_STATUSES


def _get_frame_library_version() -> str | None:
    """Return the live ``_FRAME_LIBRARY_VERSION`` cache. See
    ``_get_frame_statuses`` for the late-binding rationale."""
    return _FRAME_LIBRARY_VERSION


def _get_frame_versions() -> dict[str, Any] | None:
    """Return the live ``_FRAME_VERSIONS`` cache. See
    ``_get_frame_statuses`` for the late-binding rationale."""
    return _FRAME_VERSIONS


def _get_frame_adjacency() -> dict[str, Any] | None:
    """Return the live ``_FRAME_ADJACENCY`` cache. See
    ``_get_frame_statuses`` for the late-binding rationale."""
    return _FRAME_ADJACENCY


# ── Signal-strength classification (shared by resources + compose) ─

_SIGNAL_STRENGTH_THRESHOLDS = (
    # (density_upper_exclusive, label)
    (0.01, "none"),
    (3.0, "nominal"),
    (10.0, "moderate"),
    (float("inf"), "substantive"),
)


def _signal_strength_for(density_per_1kw: float) -> str:
    """Derive signal-strength label from density per 1K words.

    Thresholds: none (0), nominal (<3), moderate (<10), substantive (>=10).
    """
    density = max(0.0, float(density_per_1kw))
    for upper, label in _SIGNAL_STRENGTH_THRESHOLDS:
        if density < upper:
            return label
    return "substantive"


# ── Content hashing ───────────────────────────────────────────────

def _content_hash(text: str) -> str:
    """SHA-256 of the literal bytes of a resource's served text.
    Attached to every resource in both resources/list metadata and
    resources/read contents so a citation made today resolves to
    the exact bytes that supported it, and a cached client can
    detect drift without re-reading. The hash is the hex digest of
    the UTF-8-encoded text; content on disk that is bit-identical
    produces an identical hash across calls and processes.
    """
    import hashlib as _hashlib
    return _hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Frame Divergence v1 spec assembly ──────────────────────────────

def _spec_fd_v1_parts() -> list[tuple[int, str, str]]:
    """List (part_num, part_title, absolute_path) tuples for Frame
    Divergence v1 spec parts present on disk.

    The list-based shape lets _list_resources and _read_resource walk
    the same source of truth rather than hard-coding part numbers
    twice.
    """
    parts: list[tuple[int, str, str]] = []
    if os.path.isfile(_SPEC_FD_V1_PART2_PATH):
        parts.append((
            2,
            "Contract (c1.0)",
            _SPEC_FD_V1_PART2_PATH,
        ))
    return parts


def _spec_fd_v1_index_markdown() -> str:
    """Render the Frame Divergence v1 spec index as markdown.

    Generated at read time (not cached) so the index reflects which
    parts are actually present on this deploy. Parts pending per
    contract §11 are named with their status; parts landed are
    linked via their resource URIs.
    """
    present = {num for (num, _title, _path) in _spec_fd_v1_parts()}
    lines = [
        "# Frame Divergence v1: spec index",
        "",
        ("Author: Lovro Lucic. Canonical reference for the frame "
        "divergence category as defined by Frame Check."),
        "",
        "## Parts",
        "",
    ]
    scheme = RESOURCE_SCHEME
    part_descriptions = [
        (1, "Category definition and non-negotiables",
         ("category and sovereignty argument; "
         "the non-negotiables any implementation must honor")),
        (2, "Contract (c1.0)",
         ("interface contract: operations, inputs, outputs, "
         "faithfulness guarantees, MCP-vs-web tier split, "
         "versioning commitments")),
        (3, "V4.2 integration",
         ("per-tier implementation details; pending NEW panel "
         "re-validation landing")),
        (4, "Self-red-team and competitive map",
         ("failure scenarios paired with minimum-surviving "
         "artifacts; adjacent-category positioning")),
    ]
    for num, title, blurb in part_descriptions:
        if num in present:
            uri = f"{scheme}://spec/frame-divergence/v1/part-{num}"
            lines.append(f"- **Part {num}: {title}** ({uri}). {blurb}.")
        else:
            lines.append(f"- **Part {num}: {title}** (pending). {blurb}.")
    lines.append("")
    lines.append(
        "Parts shipped so far bind the others: every contract "
        "claim honors Part 1's non-negotiables, and the pending "
        "parts will honor Parts 1-2."
    )
    lines.append("")
    return "\n".join(lines)


# ── Library, worked-example, transmission entry listings ───────────

def _library_entries() -> list[tuple[Any, ...]]:
    """List (fvs_id, title, absolute_md_path, version) for every FVS
    entry present under data/frame_library/.

    Titles come from the first H1 line. Versions come from the
    **Version:** line in the entry's meta block (typically "1",
    "2", etc; not semver). None when the line is missing.

    Per-entry version matters for citation precision: library_version
    is library-wide and does not disambiguate which version of a
    specific entry an agent saw. An agent citing FVS-008 today
    should be able to pin the cite to version 1 and re-run the
    same analysis against the same version in future without
    having to reconstruct the text manually.
    """
    out: list[tuple[Any, ...]] = []
    if not os.path.isdir(_LIBRARY_DIR):
        return out
    for fname in sorted(os.listdir(_LIBRARY_DIR)):
        if not re.match(r"^FVS-\d{3}_.+\.md$", fname):
            continue
        fvs_id = fname.split("_", 1)[0]
        path = os.path.join(_LIBRARY_DIR, fname)
        title = fvs_id
        version: str | None = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Read the head of the file (meta block is always in
                # the first few lines). Avoids loading full file when
                # only the title + version are needed.
                for _ in range(20):
                    line = f.readline()
                    if not line:
                        break
                    stripped = line.strip()
                    if title == fvs_id and stripped.startswith("# "):
                        title = stripped[2:].strip()
                    if version is None:
                        vm = re.match(
                            r'^\*\*Version:\*\*\s*(\S+)', stripped,
                        )
                        if vm:
                            version = vm.group(1).strip()
                    if title != fvs_id and version is not None:
                        break
        except OSError:
            continue
        out.append((fvs_id, title, path, version))
    return out


def _library_v3_entries() -> list[tuple[Any, ...]]:
    """Catalog used by the MCP divergence block: 19 entries, FVS-020
    excluded.

    Reads `data/frame_library_v3/` when present; otherwise falls back
    to `data/frame_library/` (the working catalog). FVS-020 is always
    excluded from this list so the divergence block never surfaces
    it. The fallback keeps the divergence catalog defined whenever
    the working catalog is shipped, even when only one library
    directory is present on disk.

    Returns list of (fvs_id, title, absolute_md_path, version) tuples.
    """
    src_dir = _LIBRARY_V3_DIR if os.path.isdir(_LIBRARY_V3_DIR) else _LIBRARY_DIR
    out: list[tuple[Any, ...]] = []
    if not os.path.isdir(src_dir):
        return out
    for fname in sorted(os.listdir(src_dir)):
        if not re.match(r"^FVS-\d{3}_.+\.md$", fname):
            continue
        fvs_id = fname.split("_", 1)[0]
        if fvs_id == "FVS-020":
            continue
        path = os.path.join(src_dir, fname)
        title = fvs_id
        version: str | None = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                for _ in range(20):
                    line = f.readline()
                    if not line:
                        break
                    stripped = line.strip()
                    if title == fvs_id and stripped.startswith("# "):
                        title = stripped[2:].strip()
                    if version is None:
                        vm = re.match(
                            r'^\*\*Version:\*\*\s*(\S+)', stripped,
                        )
                        if vm:
                            version = vm.group(1).strip()
                    if title != fvs_id and version is not None:
                        break
        except OSError:
            continue
        out.append((fvs_id, title, path, version))
    return out


def _worked_example_entries() -> list[tuple[Any, ...]]:
    """List (slug, title, path, metadata) for every published worked
    example. Files prefixed with an underscore (_TEMPLATE.md) or named
    README.md are excluded: the template is a scaffold, not a
    published example, and the README is directory-level documentation.

    metadata is a dict extracted from the frontmatter with keys
    source_document_url, source_document_title, and hook. Surfacing
    these in the resources/list description lets an agent choose
    which example to fetch (by source type or by the one-sentence
    hook) without pulling the full markdown first. Missing keys
    default to None so the caller can test presence.
    """
    out: list[tuple[Any, ...]] = []
    if not os.path.isdir(_WORKED_EXAMPLES_DIR):
        return out
    for fname in sorted(os.listdir(_WORKED_EXAMPLES_DIR)):
        if not fname.endswith(".md"):
            continue
        if fname.startswith("_") or fname == "README.md":
            continue
        slug = fname[:-3]
        path = os.path.join(_WORKED_EXAMPLES_DIR, fname)
        title = slug
        metadata: dict[str, Any] = {
            "source_document_url": None,
            "source_document_title": None,
            "hook": None,
        }
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            m = re.search(
                r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL,
            )
            if m:
                fm = m.group(1)

                def _get(key):
                    km = re.search(
                        rf'^{re.escape(key)}:\s*(.+)$',
                        fm, re.MULTILINE,
                    )
                    return km.group(1).strip().strip('"') if km else None

                title = _get("title") or slug
                metadata["source_document_url"] = _get("source_document_url")
                metadata["source_document_title"] = _get("source_document_title")
                metadata["hook"] = _get("hook")
        except OSError:
            continue
        out.append((slug, title, path, metadata))
    return out


def _transmission_entries() -> list[tuple[Any, ...]]:
    """List (slug, display_title, path, metadata) for every
    transmission curated under data/transmissions/. Files named
    README.md or starting with an underscore are excluded (the
    README is the collection index; underscored files are
    drafts by convention).

    metadata captures the frontmatter fields the blog registry
    carries: transmission_id, type, summary, published, models,
    source_url. Surfacing these in resources/list lets an agent
    pick a relevant transmission by topic or by one-line summary
    without fetching the full body first.
    """
    out: list[tuple[Any, ...]] = []
    if not os.path.isdir(_TRANSMISSIONS_DIR):
        return out
    for fname in sorted(os.listdir(_TRANSMISSIONS_DIR)):
        if not fname.endswith(".md"):
            continue
        if fname.startswith("_") or fname == "README.md":
            continue
        slug = fname[:-3]
        path = os.path.join(_TRANSMISSIONS_DIR, fname)
        metadata: dict[str, Any] = {
            "transmission_id": None,
            "type": None,
            "summary": None,
            "published": None,
            "models": None,
            "source_url": None,
        }
        title = slug
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            m = re.search(
                r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL,
            )
            if m:
                fm = m.group(1)

                def _get(key):
                    km = re.search(
                        rf'^{re.escape(key)}:\s*(.+)$',
                        fm, re.MULTILINE,
                    )
                    if not km:
                        return None
                    return km.group(1).strip().strip('"')

                title = _get("display_title") or slug
                metadata["transmission_id"] = _get("transmission_id")
                metadata["type"] = _get("type")
                metadata["summary"] = _get("summary")
                metadata["published"] = _get("published")
                metadata["models"] = _get("models")
                metadata["source_url"] = _get("source_url")
        except OSError:
            continue
        out.append((slug, title, path, metadata))
    return out


# ── Cache primitives ──────────────────────────────────────────────

def _parse_frame_adjacency() -> dict[str, Any]:
    """Parse the **Adjacent frames:** line from every library entry
    and return {fvs_id: [adjacent_fvs_id, ...]} with a stable order.

    The canonical format in each entry is a line like:

        **Adjacent frames:** Fluency-Quality Illusion (FVS-002,
        the surface mechanism...), Default Geometry (FVS-004, ...)

    Only FVS IDs that exist on this deploy are retained; other
    vocabularies (HI-*, T-*) are dropped because the MCP library
    namespace does not serve them. Self-references are also
    dropped so an entry never claims itself as adjacent. The order
    is the order in the source file, which is the curator-chosen
    reading order; not sorted alphabetically.

    Cached at module scope by _ensure_caches so the parse runs at
    most once per server process.
    """
    adjacency: dict[str, Any] = {}
    valid_ids = {
        fvs_id for fvs_id, _t, _p, _v in _library_entries()
    }
    for fvs_id, _title, path, _version in _library_entries():
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        # Find the Adjacent frames line. Case-insensitive so an
        # entry with slight capitalisation variance still parses.
        m = re.search(
            r'^\*\*Adjacent frames:\*\*\s*([^\n]+)',
            text, re.IGNORECASE | re.MULTILINE,
        )
        if not m:
            adjacency[fvs_id] = []
            continue
        line = m.group(1)
        found: list[Any] = []
        for match in re.finditer(r'\bFVS-(\d{3})\b', line):
            ref_id = f"FVS-{match.group(1)}"
            if ref_id == fvs_id:
                continue
            if ref_id not in valid_ids:
                continue
            if ref_id not in found:
                found.append(ref_id)
        adjacency[fvs_id] = found
    return adjacency


def _ensure_caches() -> None:
    """Populate the module-level library-info caches if not yet
    populated. Lazy so MCP server startup stays fast; module-scope
    so repeated tool calls do not re-read INDEX.md, the VERSION
    file, or every per-entry meta block. Callers just call this;
    the globals become populated on first use and stay for the
    lifetime of the process.
    """
    global _FRAME_STATUSES, _FRAME_LIBRARY_VERSION
    global _FRAME_VERSIONS, _FRAME_ADJACENCY
    if _FRAME_STATUSES is None:
        _FRAME_STATUSES = _parse_frame_statuses()
    if _FRAME_LIBRARY_VERSION is None:
        _FRAME_LIBRARY_VERSION = _read_frame_library_version()
    if _FRAME_VERSIONS is None:
        _FRAME_VERSIONS = {
            fvs_id: version
            for fvs_id, _title, _path, version in _library_entries()
            if version is not None
        }
    if _FRAME_ADJACENCY is None:
        _FRAME_ADJACENCY = _parse_frame_adjacency()


# ── Path resolvers (traversal-safe) ───────────────────────────────

def _transmission_path(slug: str) -> str | None:
    """Resolve a transmission slug to its absolute .md path, or
    None if the slug is not published here. Slug matching is
    case-sensitive and rejects filesystem traversal characters
    so an agent cannot use the resource URI to read arbitrary
    files."""
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        return None
    candidate = os.path.join(_TRANSMISSIONS_DIR, f"{slug}.md")
    if os.path.isfile(candidate):
        return candidate
    return None


def _transmissions_readme_path() -> str | None:
    """Absolute path to data/transmissions/README.md if present.
    The README is the curator-facing index for the transmissions
    directory; exposing it as a resource lets an agent browsing
    the corpus see the curation intent without enumerating
    every individual transmission."""
    candidate = os.path.join(_TRANSMISSIONS_DIR, "README.md")
    return candidate if os.path.isfile(candidate) else None


def _worked_example_path(slug: str) -> str | None:
    """Resolve a worked-example slug to its absolute .md path, or
    None if the slug is not present. Slug matching is case-sensitive
    and rejects filesystem traversal characters so an agent cannot
    use the resource URI to read arbitrary files."""
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        return None
    candidate = os.path.join(_WORKED_EXAMPLES_DIR, f"{slug}.md")
    if os.path.isfile(candidate):
        return candidate
    return None


def _library_entry_path(fvs_id: str) -> str | None:
    """Resolve an FVS ID (e.g. 'FVS-008') to its absolute .md path,
    or None if the entry is not present on this deploy.

    Withdrawn entries are still served because the markdown files
    stay on disk; an agent that reads frame-check://library/FVS-004
    gets the same text regardless of canon status.
    """
    if not re.match(r"^FVS-\d{3}$", fvs_id):
        return None
    if not os.path.isdir(_LIBRARY_DIR):
        return None
    for fname in os.listdir(_LIBRARY_DIR):
        if fname.startswith(f"{fvs_id}_") and fname.endswith(".md"):
            return os.path.join(_LIBRARY_DIR, fname)
    return None


def _library_index_path() -> str | None:
    """Absolute path to data/frame_library/INDEX.md if it exists.
    None on a clean checkout where the index has not been curated
    yet. Used by the library index resource so agents can read the
    full map (entry IDs plus status plus adjacency) without
    enumerating individual entries."""
    candidate = os.path.join(_LIBRARY_DIR, "INDEX.md")
    return candidate if os.path.isfile(candidate) else None


def _worked_examples_readme_path() -> str | None:
    """Absolute path to data/worked_examples/README.md if present.
    The README is the curator-facing index for the worked-examples
    directory; exposing it as a resource lets an agent browsing the
    corpus see the editorial intent and submission format without
    fetching the published web surface."""
    candidate = os.path.join(_WORKED_EXAMPLES_DIR, "README.md")
    return candidate if os.path.isfile(candidate) else None


def _calibration_runs() -> list[tuple[Any, ...]]:
    """List (run_id, absolute_dir_path) for every calibration run
    directory that has at least a REPORT.md. Sorted newest first
    (lexicographic on the ISO-date prefix). A run without a REPORT
    is treated as in-progress and not exposed as a resource."""
    out: list[tuple[Any, ...]] = []
    if not os.path.isdir(_CALIBRATION_RESULTS_DIR):
        return out
    for name in sorted(os.listdir(_CALIBRATION_RESULTS_DIR), reverse=True):
        if not re.match(r"^\d{4}-\d{2}-\d{2}", name):
            continue
        run_dir = os.path.join(_CALIBRATION_RESULTS_DIR, name)
        if not os.path.isdir(run_dir):
            continue
        if not os.path.isfile(os.path.join(run_dir, "REPORT.md")):
            continue
        out.append((name, run_dir))
    return out


def _calibration_run_path(run_id: str, asset: str) -> str | None:
    """Resolve a calibration run's asset (REPORT, verdicts, tiers)
    to an absolute path, or None if missing. Rejects traversal in
    the run_id the same way _worked_example_path does: run IDs must
    match a strict date-prefixed slug pattern."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}[a-z0-9\-]*$", run_id):
        return None
    if asset not in ("report", "verdicts", "tiers"):
        return None
    filename = {
        "report": "REPORT.md",
        "verdicts": "raw_verdicts.json",
        "tiers": "reliability_tiers.json",
    }[asset]
    path = os.path.join(_CALIBRATION_RESULTS_DIR, run_id, filename)
    return path if os.path.isfile(path) else None


def _best_calibration_run() -> str | None:
    """Return the absolute path to the reliability_tiers.json file
    from the 'best' calibration run, or None if no run exists.

    'Best' matches app.py's _load_reliability_tiers: the run whose
    reliability_tiers.json names the most providers. A full-keys
    sweep with 7 providers wins over a single-provider sweep even
    if the single-provider sweep is lexicographically later. Keeps
    the MCP resource view of reliability aligned with what the
    web surface shows when it draws tier badges.
    """
    if not os.path.isdir(_CALIBRATION_RESULTS_DIR):
        return None
    candidates: list[str] = []
    for d in sorted(os.listdir(_CALIBRATION_RESULTS_DIR), reverse=True):
        full = os.path.join(_CALIBRATION_RESULTS_DIR, d)
        if not os.path.isdir(full):
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}", d):
            continue
        tiers = os.path.join(full, "reliability_tiers.json")
        if os.path.isfile(tiers):
            candidates.append(tiers)
    best: str | None = None
    best_count = -1
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and len(data) > best_count:
                best_count = len(data)
                best = path
        except (OSError, json.JSONDecodeError):
            continue
    return best


def _corpus_entry_slugs() -> list[str]:
    """Returns the list of validation corpus entry slugs that have
    a readable document.md, alphabetically sorted. Empty list on
    clean checkouts without the validation tree. Used by
    _list_resources to advertise one resource per entry.

    Skip-rules mirror the corpus_site builder: directory must
    carry document.md (incomplete entries are not advertised)."""
    slugs: list[str] = []
    if not os.path.isdir(_CORPUS_ENTRIES_DIR):
        return slugs
    # Traversal-safe slug pattern: lowercase alphanumeric + hyphens,
    # same convention as worked-example slugs. Rejects anything
    # that could be a path-traversal attempt.
    _SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
    for name in sorted(os.listdir(_CORPUS_ENTRIES_DIR)):
        if not _SLUG_RE.match(name):
            continue
        entry_dir = os.path.join(_CORPUS_ENTRIES_DIR, name)
        if not os.path.isdir(entry_dir):
            continue
        if not os.path.isfile(os.path.join(entry_dir, "document.md")):
            continue
        slugs.append(name)
    return slugs


def _find_corpus_entry_path(slug: str, asset: str) -> str | None:
    """Resolve a corpus entry's asset to an absolute path. Returns
    None on missing entry or unknown asset.

    Traversal guard: slug must match the same pattern used in
    _corpus_entry_slugs. asset whitelist is "document" or "profile";
    anything else returns None without touching the filesystem.

    For pair artifacts (diff_with_*, peer_with_*) use
    _find_corpus_pair_path instead; that helper has an extra
    slug validator for the partner side.
    """
    _SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
    if not _SLUG_RE.match(slug):
        return None
    if asset == "document":
        filename = "document.md"
    elif asset == "profile":
        filename = "profile.json"
    else:
        return None
    path = os.path.join(_CORPUS_ENTRIES_DIR, slug, filename)
    return path if os.path.isfile(path) else None


def _find_corpus_pair_path(
    slug: str, kind: str, partner_slug: str,
) -> str | None:
    """Resolve a corpus entry's per-pair comparison JSON (diff or
    peer) to an absolute path. Returns None on invalid slug/partner
    or missing file.

    URI pattern: frame-check://corpus/{slug}/peer/{partner_slug}
    resolves to validation/decision_readiness/corpus/{slug}/
    peer_with_{partner_slug}.json (similarly for diff).

    Traversal guard: both slugs must match the slug regex; kind
    must be "peer" or "diff". Strict validation before filesystem
    access.
    """
    _SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
    if not _SLUG_RE.match(slug):
        return None
    if not _SLUG_RE.match(partner_slug):
        return None
    if kind == "peer":
        filename = f"peer_with_{partner_slug}.json"
    elif kind == "diff":
        filename = f"diff_with_{partner_slug}.json"
    else:
        return None
    path = os.path.join(_CORPUS_ENTRIES_DIR, slug, filename)
    return path if os.path.isfile(path) else None


def _find_latest_aggregate() -> str | None:
    """Return the absolute path to the most recent aggregate.json
    under validation/decision_readiness/results/, or None if no
    aggregate run is present on this deploy.

    Run directory naming pattern: {YYYY-MM-DD}-{12hex_corpus_hash}
    (set by aggregate_corpus_findings.py main()). The directory
    name carries the date but the hash suffix has NO temporal
    ordering within a date (each regeneration of the corpus
    produces a new hash; alphabetical order across hashes is
    arbitrary). Sorting by directory name alone would pick the
    alphabetically-largest hash, not the most recent run.

    Selection rule: pick the aggregate.json whose mtime is
    largest. mtime is set when the file is written (the harness
    writes the aggregate.json fresh on each run), so this is the
    most-recently-generated aggregate. Across days the date prefix
    naturally dominates because newer files always have larger
    mtimes; within a day, the actual generation order wins.

    Stale-aggregate caveat: the corpus may have evolved between
    aggregate runs. The aggregate.json itself carries
    corpus.state_hash and computed_at_utc so consumers can check
    freshness against the current corpus state if they care.

    Skips directories that exist but lack aggregate.json (an
    aborted or in-progress run is not a valid resource target).
    Returns None when no candidate has a readable aggregate.json.
    """
    if not os.path.isdir(_AGGREGATE_RESULTS_DIR):
        return None
    candidates: list[tuple[float, str]] = []
    for name in os.listdir(_AGGREGATE_RESULTS_DIR):
        if not re.match(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]+$", name):
            continue
        run_dir = os.path.join(_AGGREGATE_RESULTS_DIR, name)
        if not os.path.isdir(run_dir):
            continue
        candidate = os.path.join(run_dir, "aggregate.json")
        if not os.path.isfile(candidate):
            continue
        try:
            mtime = os.path.getmtime(candidate)
        except OSError:
            # Race with cleanup; skip rather than crash
            continue
        candidates.append((mtime, candidate))
    if not candidates:
        return None
    # Most recent first
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


# ── MCP-shape resource handlers ────────────────────────────────────

def _list_resources() -> list[dict]:
    """Enumerate every resource the server can hand to an agent.

    Conservative: only advertises URIs whose content is present on
    disk right now. A deploy without frame-library entries would
    not advertise library URIs; a deploy without calibration data
    would not advertise the calibration URI. Agents should treat
    the list as authoritative for this deploy rather than assuming
    a stable superset.
    """
    resources: list[dict] = []

    # Library index: the full map (IDs + status + adjacency) an
    # agent would otherwise reconstruct by reading every entry.
    if _library_index_path() is not None:
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://library",
            "name": "Frame Vocabulary Standard: full index",
            "description": (
                "Index of every Frame Vocabulary Standard entry "
                "with status (canon / draft / withdrawn) and "
                "adjacency hints. Markdown source; the citable "
                "map of the library as a whole."
            ),
            "mimeType": "text/markdown",
        })

    for fvs_id, title, _path, version in _library_entries():
        # Resource description pins the per-entry version when the
        # file declares one. An agent browsing the list can
        # distinguish current from stale entries without reading
        # each file.
        version_note = f"v{version}. " if version else ""
        entry: dict[str, Any] = {
            "uri": f"{RESOURCE_SCHEME}://library/{fvs_id}",
            "name": f"{fvs_id}: {title}",
            "description": (
                f"{version_note}Frame Vocabulary Standard entry "
                f"{fvs_id}. Markdown source. Includes "
                f"identification cues, generation affordances, and "
                f"worked examples."
            ),
            "mimeType": "text/markdown",
        }
        # Per-entry version surfaced as a machine-parseable _meta
        # field so an agent citing FVS-NNN can pin to the version it
        # saw without regex-extracting from the description prose.
        if version:
            entry["_meta"] = {"clarethium.com/version": str(version)}
        resources.append(entry)

    # Worked-examples index: the curator-facing README that
    # documents the collection and its submission format. Only
    # advertised when there is also at least one published example
    # so an empty corpus deploy does not advertise a lonely index.
    if (_worked_examples_readme_path() is not None
            and _worked_example_entries()):
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://worked-examples",
            "name": "Worked examples: collection index",
            "description": (
                "The worked-examples directory README. Documents "
                "the collection's editorial intent and the "
                "submission format for future contributions."
            ),
            "mimeType": "text/markdown",
        })

    for slug, title, _path, meta in _worked_example_entries():
        # Compose a description that tells a browsing agent enough
        # to pick the right worked example without reading the full
        # file. source_document_title + hook is the minimum useful
        # identity pair; the URL makes the underlying artefact
        # reachable; the generic closing line keeps the description
        # readable when either field is missing.
        parts: list[str] = []
        src_title = meta.get("source_document_title")
        if src_title:
            parts.append(f"Source: {src_title}.")
        hook = meta.get("hook")
        if hook:
            parts.append(hook.rstrip(".") + ".")
        parts.append(
            "Applied analysis of a specific public document; runs "
            "Frame Check at depth and links each detected frame "
            "back to the library."
        )
        description = " ".join(parts)
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://worked-examples/{slug}",
            "name": title,
            "description": description,
            "mimeType": "text/markdown",
        })

    # Transmissions: curated research pieces from the author's blog,
    # advertised only when at least one published transmission is
    # present. Each carries a one-line summary in its description so
    # an agent can pick a relevant one without reading the full body.
    # The collection README gates visibility: no README means the
    # curation pass has not been run on this deploy.
    if (_transmissions_readme_path() is not None
            and _transmission_entries()):
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://transmissions",
            "name": "Transmissions: collection index",
            "description": (
                "The transmissions directory README. Documents the "
                "curation intent (which blog posts from "
                "blog.clarethium.com are exposed as MCP resources) "
                "and lists every published transmission on this "
                "deploy."
            ),
            "mimeType": "text/markdown",
        })

    for slug, title, _path, meta in _transmission_entries():
        # Description leads with the type tag and the one-line
        # summary from the registry so an agent can pick the
        # relevant transmission without fetching the full body.
        # transmission_id and published date close the description
        # so the identity pair an agent needs to cite (id plus
        # date) is visible in the resource list itself.
        tx_parts: list[str] = []
        type_tag = meta.get("type")
        if type_tag:
            tx_parts.append(f"[{type_tag}]")
        summary = meta.get("summary")
        if summary:
            tx_parts.append(summary.rstrip(".") + ".")
        tid = meta.get("transmission_id")
        pub = meta.get("published")
        if tid and pub:
            tx_parts.append(f"({tid}, published {pub}.)")
        elif tid:
            tx_parts.append(f"({tid}.)")
        description = " ".join(tx_parts) or (
            "Published research transmission from "
            "blog.clarethium.com."
        )
        # Per-transmission attribution metadata. citation-uri sources
        # from the YAML frontmatter source_url (the curator's
        # canonical published URL) rather than being inferred from
        # the slug, so the metadata reflects the curator's explicit
        # choice. published date is exposed as an MCP-spec annotation
        # (lastModified) for drift-detection at the protocol level.
        entry_meta: dict[str, Any] = {}
        source_url = meta.get("source_url")
        if isinstance(source_url, str) and source_url.startswith(
            "https://blog.clarethium.com/"
        ):
            entry_meta["clarethium.com/citation-uri"] = source_url
        annotations: dict[str, Any] = {}
        if isinstance(pub, str) and pub:
            annotations["lastModified"] = pub
        tx_entry: dict[str, Any] = {
            "uri": f"{RESOURCE_SCHEME}://transmissions/{slug}",
            "name": title,
            "description": description,
            "mimeType": "text/markdown",
        }
        if entry_meta:
            tx_entry["_meta"] = entry_meta
        if annotations:
            tx_entry["annotations"] = annotations
        resources.append(tx_entry)

    if os.path.isfile(_METHODOLOGY_PATH):
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://methodology",
            "name": "Frame Check Methodology",
            "description": (
                "The complete methodology specification. Names every "
                "detector, the calibration protocol, and the known "
                "limits. Apache-2.0 / CC-BY-4.0. This is the citation "
                "target for the measurement contract."
            ),
            "mimeType": "text/markdown",
        })

    # Frame Divergence v1 spec (index + available parts). The index
    # is generated content; parts are authored markdown files. Only
    # advertised when at least one part exists on disk.
    _fd_v1_parts = _spec_fd_v1_parts()
    if _fd_v1_parts:
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://spec/frame-divergence/v1",
            "name": "Frame Divergence v1: spec index",
            "description": (
                "Canonical reference for the frame divergence category. "
                "Index lists the parts currently shipped and those "
                "pending. Author: Lovro Lucic. The citation target for "
                "consumers who want to bind against the category "
                "claim and contract rather than any single part."
            ),
            "mimeType": "text/markdown",
        })
        for part_num, part_title, _part_path in _fd_v1_parts:
            resources.append({
                "uri": (
                    f"{RESOURCE_SCHEME}://spec/frame-divergence/v1/"
                    f"part-{part_num}"
                ),
                "name": f"Frame Divergence v1, Part {part_num}: {part_title}",
                "description": (
                    f"Part {part_num} of the Frame Divergence v1 spec. "
                    f"Authored canonical reference. Bound by Part 1's "
                    f"non-negotiables; Parts 2-4 compose on top. The "
                    f"citation target for consumers binding against a "
                    f"specific part."
                ),
                "mimeType": "text/markdown",
            })

    if _best_calibration_run() is not None:
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://calibration/reliability_tiers",
            "name": "Reliability tiers (current calibration)",
            "description": (
                "Per-provider F1, precision, recall, and tier "
                "(strong / moderate / weak / uncalibrated) from the "
                "most comprehensive calibration run on this deploy. "
                "An agent citing a verification verdict can cite "
                "the reliability tier from this resource."
            ),
            "mimeType": "application/json",
        })

    # Per-run calibration artifacts. Each run exposes up to three
    # resources: REPORT.md (narrative), raw_verdicts.json (per-claim
    # evidence), and reliability_tiers.json (that run's tiers).
    # Exposing all three lets an agent cite the tier AND the
    # per-claim evidence that justified it, rather than relying on
    # a single aggregated file.
    for run_id, run_dir in _calibration_runs():
        base = f"{RESOURCE_SCHEME}://calibration/runs/{run_id}"
        resources.append({
            "uri": f"{base}/report",
            "name": f"Calibration {run_id}: report",
            "description": (
                f"Narrative calibration report for run {run_id}. "
                f"Describes the corpus, the verdict distribution, "
                f"and the per-provider F1 values."
            ),
            "mimeType": "text/markdown",
        })
        if os.path.isfile(os.path.join(run_dir, "raw_verdicts.json")):
            resources.append({
                "uri": f"{base}/verdicts",
                "name": f"Calibration {run_id}: per-claim verdicts",
                "description": (
                    f"Raw per-claim verdicts from calibration run "
                    f"{run_id}. The evidence chain behind this "
                    f"run's tier assignments."
                ),
                "mimeType": "application/json",
            })
        if os.path.isfile(
            os.path.join(run_dir, "reliability_tiers.json")
        ):
            resources.append({
                "uri": f"{base}/tiers",
                "name": f"Calibration {run_id}: reliability tiers",
                "description": (
                    f"Per-provider reliability tiers for run "
                    f"{run_id}. Scoped to this run; see the "
                    f"default reliability_tiers resource for the "
                    f"current best."
                ),
                "mimeType": "application/json",
            })

    # Decision-readiness corpus aggregate (latest). Structured
    # corpus-level findings derived from the per-document profiles
    # under validation/decision_readiness/corpus/. An agent that
    # has been chaining to per-document profiles can ALSO query
    # this resource to ask "what does the corpus aggregate say
    # about LLM patterns" without iterating every document. The
    # resource is the same JSON written to disk by the
    # aggregate_corpus_findings.py harness, exposed read-only.
    #
    # Only advertised when at least one aggregate run has produced
    # a readable aggregate.json. A clean checkout without the
    # validation tree (or one where the harness has not been run)
    # gets no aggregate resource; agents see resources/list
    # without it and know not to attempt a read.
    if _find_latest_aggregate() is not None:
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://aggregate/latest",
            "name": "Decision-readiness corpus aggregate (latest)",
            "description": (
                "Structured corpus-level findings: per-dimension "
                "divergence rates across peer pairs, transformation "
                "diff rates, per-LLM outlier counts, "
                "cross-question consistency findings (LLMs that are "
                "the outlier in EVERY comparable peer group, with "
                "the canon-aligned named patterns that fired in "
                "their outlier documents), and library_entries_per_"
                "dimension as the canon-graph projection. JSON "
                "carries computed_at_utc and a corpus state hash "
                "that versions findings against the corpus state "
                "at compute time. Status: experimental (Phase 2 "
                "validation pending); see /corpus/decision-readiness/."
            ),
            "mimeType": "application/json",
        })

    # Validation corpus entries. Per-entry document + profile
    # advertised so an MCP agent reading the aggregate (which
    # cites corpus entries by slug) can chain to the actual
    # document and computed profile. Each entry produces two
    # resources: the document (markdown) and the profile (JSON).
    # Only entries with document.md are advertised (incomplete
    # entries skipped).
    for slug in _corpus_entry_slugs():
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://corpus/{slug}",
            "name": f"Corpus entry: {slug}",
            "description": (
                f"Decision-readiness validation corpus document "
                f"for entry {slug}. Plain markdown. Cited by "
                f"aggregate findings; used as input to the Phase 2 "
                f"validation harness. Profile.json available "
                f"separately at frame-check://corpus/{slug}/profile."
            ),
            "mimeType": "text/markdown",
        })
        profile_path = os.path.join(
            _CORPUS_ENTRIES_DIR, slug, "profile.json",
        )
        if os.path.isfile(profile_path):
            resources.append({
                "uri": f"{RESOURCE_SCHEME}://corpus/{slug}/profile",
                "name": f"Corpus entry profile: {slug}",
                "description": (
                    f"Computed decision-readiness profile for "
                    f"corpus entry {slug}. JSON with 5-dimension "
                    f"signals, fired_library_entries per dimension, "
                    f"experimental status. Consumed by the validation "
                    f"harness and the aggregate."
                ),
                "mimeType": "application/json",
            })
        # Per-pair comparison artifacts: diff_with_*.json (source
        # -> derived) and peer_with_*.json (non-directional). Let
        # research agents who found an LLM in an aggregate
        # cross-question finding pull the specific pair that
        # contributed to the outlier signal, without having to
        # fetch both profiles and diff them client-side.
        _SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
        entry_dir = os.path.join(_CORPUS_ENTRIES_DIR, slug)
        if os.path.isdir(entry_dir):
            for filename in sorted(os.listdir(entry_dir)):
                # Parse kind + partner from filename. Diff and peer
                # artifacts follow a strict naming convention set by
                # the harness; anything else is ignored defensively.
                if filename.startswith("peer_with_") and filename.endswith(".json"):
                    kind = "peer"
                    partner_slug = filename[len("peer_with_"):-len(".json")]
                elif filename.startswith("diff_with_") and filename.endswith(".json"):
                    kind = "diff"
                    partner_slug = filename[len("diff_with_"):-len(".json")]
                else:
                    continue
                # Traversal guard: partner slug must match the
                # same pattern as the entry slug. Defensive:
                # directory contents are curator-controlled, but
                # the URI advertisement should only include slugs
                # that would round-trip through the read handler.
                if not _SLUG_RE.match(partner_slug):
                    continue
                resources.append({
                    "uri": (
                        f"{RESOURCE_SCHEME}://corpus/{slug}/"
                        f"{kind}/{partner_slug}"
                    ),
                    "name": (
                        f"Corpus entry {kind}: {slug} vs {partner_slug}"
                    ),
                    "description": (
                        f"Per-pair {kind} comparison between corpus "
                        f"entries {slug} and {partner_slug}. JSON with "
                        f"per-dimension comparison_text, differs / "
                        f"moved flags, fired-pattern asymmetry "
                        f"(only_a/only_b for peer; gained/lost for "
                        f"diff). Agents chasing cross-question "
                        f"outliers can pull the specific pair data "
                        f"without fetching both profiles separately."
                    ),
                    "mimeType": "application/json",
                })

    # Attribution metadata (CC-BY-4.0 chain). Most resources
    # advertised here are CC-BY-4.0 data artifacts authored by Lovro
    # Lucic per NOTICE. The MCP Resource interface carries an
    # `_meta` field (spec 2025-06-18, schema.ts) that servers use to
    # attach additional metadata under reverse-DNS-prefixed keys.
    # Without per-resource attribution, an agent that consumes a
    # resource has no in-band way to know the license, the author,
    # or the canonical citation URL, so the attribution chain breaks
    # at the agent boundary.
    #
    # The exception is `frame-check://corpus/<slug>` (the document
    # URI itself, not /profile, /peer/, or /diff/). Corpus documents
    # are bundled third-party text (e.g., a verbatim NVIDIA press
    # release) or AI-generated outputs, included under fair-use for
    # research analysis. The document file's own header carries the
    # accurate origin and copyright; the analytical commentary at
    # the sibling /profile, /peer/, and /diff/ URIs is what is
    # licensed CC-BY-4.0. Claiming CC-BY-4.0 over the verbatim
    # bundled text would overreach.
    #
    # Schema (clarethium.com/* prefix per MCP _meta key naming rules):
    #   license:       SPDX identifier (CC-BY-4.0) for analytical artifacts
    #   license-uri:   full license URL
    #   author:        canonical author for citation
    #   year:          publication year (currently 2026 across the corpus)
    #   citation-uri:  human-readable canonical URL when one exists
    #                  (sourced from per-resource construction sites,
    #                  e.g. transmissions read source_url from YAML
    #                  frontmatter; library entries and the methodology
    #                  paper are not yet published to the public web)
    #   version:       per-entry version when the entry declares one
    #                  (FVS library entries surface this)
    #   content-type:  set to "bundled-document" on corpus document URIs
    #                  to signal mixed origin
    #   license-note:  free-text override pointing the consumer at the
    #                  document's in-file header for accurate origin
    #                  (set on bundled-document URIs only)
    _CORPUS_DOC_RE = re.compile(
        rf"^{re.escape(RESOURCE_SCHEME)}://corpus/[^/]+$"
    )
    for r in resources:
        uri = r.get("uri", "")
        meta = r.setdefault("_meta", {})
        if _CORPUS_DOC_RE.match(uri):
            # Bundled document URI. Do not claim CC-BY-4.0 or
            # author over text that may be third-party. Point the
            # consumer at the document's own header instead.
            meta.setdefault(
                "clarethium.com/content-type", "bundled-document"
            )
            meta.setdefault(
                "clarethium.com/license-note",
                "Bundled documents may contain verbatim third-party "
                "text under fair-use posture for research analysis, "
                "or AI-generated outputs from third-party services. "
                "See the document's in-file header for the accurate "
                "origin and copyright. Frame Check's analytical "
                "commentary on this document (CC-BY-4.0, Lovro Lucic) "
                "lives at the sibling /profile, /peer/<partner>, and "
                "/diff/<partner> URIs.",
            )
            continue
        meta.setdefault("clarethium.com/license", "CC-BY-4.0")
        meta.setdefault(
            "clarethium.com/license-uri",
            "https://creativecommons.org/licenses/by/4.0/",
        )
        meta.setdefault("clarethium.com/author", "Lovro Lucic")
        meta.setdefault("clarethium.com/year", "2026")

    return resources


def _read_resource(uri: str) -> dict[str, Any]:
    """Resolve a URI to its content in the shape resources/read
    returns. Raises ValueError for unknown URIs and FileNotFoundError
    when the resource is advertised but unreadable at call time
    (race with the filesystem)."""
    if not uri.startswith(f"{RESOURCE_SCHEME}://"):
        raise ValueError(f"Unknown URI scheme: {uri}")
    path = uri[len(f"{RESOURCE_SCHEME}://"):]

    # Library index takes priority over the /library/ entry path
    # so "library" and "library/" both resolve (the former to
    # INDEX.md, the latter would be an empty entry ID which falls
    # through to the not-found branch).
    if path == "library":
        index_path = _library_index_path()
        if index_path is None:
            raise FileNotFoundError(
                "No library index on this deploy"
            )
        with open(index_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path.startswith("library/"):
        fvs_id = path[len("library/"):]
        entry_path = _library_entry_path(fvs_id)
        if entry_path is None:
            raise FileNotFoundError(f"No library entry for {fvs_id}")
        with open(entry_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path == "worked-examples":
        readme_path = _worked_examples_readme_path()
        if readme_path is None:
            raise FileNotFoundError(
                "No worked-examples index on this deploy"
            )
        with open(readme_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path.startswith("worked-examples/"):
        slug = path[len("worked-examples/"):]
        entry_path = _worked_example_path(slug)
        if entry_path is None:
            raise FileNotFoundError(
                f"No worked example for slug {slug!r}"
            )
        with open(entry_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path == "transmissions":
        readme_path = _transmissions_readme_path()
        if readme_path is None:
            raise FileNotFoundError(
                "No transmissions index on this deploy"
            )
        with open(readme_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path.startswith("transmissions/"):
        slug = path[len("transmissions/"):]
        entry_path = _transmission_path(slug)
        if entry_path is None:
            raise FileNotFoundError(
                f"No transmission for slug {slug!r}"
            )
        with open(entry_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path == "methodology":
        if not os.path.isfile(_METHODOLOGY_PATH):
            raise FileNotFoundError("Methodology not available on this deploy")
        with open(_METHODOLOGY_PATH, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    # Frame Divergence v1 spec resources.
    # Path patterns:
    #   spec/frame-divergence/v1         -> generated index
    #   spec/frame-divergence/v1/part-N  -> authored part file
    # Check exact index path before the /part-N prefix so a stray
    # trailing slash does not silently match the wrong branch.
    if path == "spec/frame-divergence/v1":
        if not _spec_fd_v1_parts():
            raise FileNotFoundError(
                "Frame Divergence v1 spec not available on this deploy"
            )
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": _spec_fd_v1_index_markdown(),
                }
            ]
        }

    if path.startswith("spec/frame-divergence/v1/part-"):
        part_suffix = path[len("spec/frame-divergence/v1/part-"):]
        # Whitelist the suffix: must be a small positive integer, no
        # separators, no traversal. Rejecting early keeps the dispatch
        # traversal-safe even as new parts land.
        if not part_suffix.isdigit():
            raise ValueError(
                f"Spec part must be an integer suffix; got {uri}"
            )
        part_num = int(part_suffix)
        parts_map = {num: p for (num, _title, p) in _spec_fd_v1_parts()}
        if part_num not in parts_map:
            raise FileNotFoundError(
                f"Frame Divergence v1 Part {part_num} not available "
                f"on this deploy"
            )
        with open(parts_map[part_num], "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        }

    if path == "calibration/reliability_tiers":
        tiers_path = _best_calibration_run()
        if tiers_path is None:
            raise FileNotFoundError(
                "No calibration reliability tiers available on this deploy"
            )
        with open(tiers_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": text,
                }
            ]
        }

    # Per-run calibration artifact: calibration/runs/{run_id}/{asset}
    if path.startswith("calibration/runs/"):
        remainder = path[len("calibration/runs/"):]
        parts = remainder.split("/", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Calibration run URI must be "
                f"{RESOURCE_SCHEME}://calibration/runs/<run-id>/<asset>; "
                f"got {uri}"
            )
        run_id, asset = parts
        asset_path = _calibration_run_path(run_id, asset)
        if asset_path is None:
            raise FileNotFoundError(
                f"Calibration run {run_id!r} asset {asset!r} "
                f"not available on this deploy"
            )
        with open(asset_path, "r", encoding="utf-8") as f:
            text = f.read()
        mime = (
            "text/markdown"
            if asset == "report"
            else "application/json"
        )
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": mime,
                    "text": text,
                }
            ]
        }

    if path.startswith("corpus/"):
        # Corpus entry resources. URI patterns:
        #   corpus/{slug}                         -> document.md (markdown)
        #   corpus/{slug}/profile                 -> profile.json (json)
        #   corpus/{slug}/peer/{partner_slug}     -> peer_with_*.json
        #   corpus/{slug}/diff/{partner_slug}     -> diff_with_*.json
        # Order-sensitive: check pair paths BEFORE /profile because
        # /profile would mis-match a future slug containing "profile".
        remainder = path[len("corpus/"):]
        parts = remainder.split("/")
        # Pair URI: corpus/{slug}/{kind}/{partner}
        if len(parts) == 3 and parts[1] in ("peer", "diff"):
            slug, kind, partner_slug = parts[0], parts[1], parts[2]
            pair_path = _find_corpus_pair_path(slug, kind, partner_slug)
            if pair_path is None:
                raise FileNotFoundError(
                    f"No corpus {kind} artifact found for "
                    f"{slug!r} vs {partner_slug!r}"
                )
            with open(pair_path, "r", encoding="utf-8") as f:
                text = f.read()
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": text,
                    }
                ]
            }
        # Entry-level URI: corpus/{slug} or corpus/{slug}/profile
        if remainder.endswith("/profile"):
            slug = remainder[:-len("/profile")]
            asset = "profile"
        else:
            slug = remainder
            asset = "document"
        # Traversal-safe resolution via _find_corpus_entry_path,
        # which validates the slug pattern and whitelists the
        # asset name before touching the filesystem.
        entry_path = _find_corpus_entry_path(slug, asset)
        if entry_path is None:
            raise FileNotFoundError(
                f"No corpus entry found for slug {slug!r} "
                f"asset {asset!r}"
            )
        with open(entry_path, "r", encoding="utf-8") as f:
            text = f.read()
        mime = "application/json" if asset == "profile" else "text/markdown"
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": mime,
                    "text": text,
                }
            ]
        }

    if path == "aggregate/latest":
        # Resolve the most recent aggregate.json. Recompute the path
        # at read time rather than caching the list-time value: an
        # aggregate run between resources/list and resources/read
        # is rare but legal, and the read should reflect actual
        # current state, not a stale snapshot.
        agg_path = _find_latest_aggregate()
        if agg_path is None:
            raise FileNotFoundError(
                "No decision-readiness corpus aggregate available "
                "on this deploy"
            )
        with open(agg_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": text,
                }
            ]
        }

    raise ValueError(f"Unknown resource: {uri}")
