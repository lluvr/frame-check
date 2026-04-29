"""
Frame Check MCP server.

Exposes Frame Check's deterministic structural framing analysis as a
Model Context Protocol tool so AI agents (Claude Desktop, Cursor, any
MCP-compatible client) can invoke framing analysis directly instead
of paraphrasing documents as their own LLM-generated interpretation.

What makes this MCP server different from a plain tool wrapper
---------------------------------------------------------------
Most MCP tools return raw data. This one returns a structured
epistemic payload with three sections:

  1. analysis        - the measurements themselves (coverage,
                       voice, temporal, epistemic, frame matches,
                       extracted claims)
  2. agent_guidance  - what this tool can and cannot tell the
                       agent, and how to cite its output faithfully
                       instead of paraphrasing it as the agent's
                       own reading
  3. provenance      - methodology version, frame-library version,
                       license, cost (always 0 USD; the analysis
                       layer is deterministic), citation string,
                       tool URL

The agent_guidance and provenance blocks exist because an agent
passing Frame Check's output to a user without attribution would
strip the reproducibility that makes the measurement worth citing.
Surfacing "how to cite faithfully" in the tool response is the
structure that carries the integrity forward to the user.

Protocol
--------
Implements the Model Context Protocol over stdio using JSON-RPC 2.0
line-delimited. No external dependency on an MCP SDK. The protocol
surface is small enough (initialize, tools/list, tools/call, ping,
notifications) that implementing it in-repo keeps Frame Check
self-contained: no extra install step, no SDK version drift.

Install in Claude Desktop
-------------------------
Add to `claude_desktop_config.json`:

    {
      "mcpServers": {
        "frame-check": {
          "command": "python3",
          "args": ["/absolute/path/to/frame-check/mcp_server.py"]
        }
      }
    }

Then ask Claude: "Can you frame-check this document?"

License: Apache-2.0. See LICENSE at repo root.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Any

# Import the Frame Check pipeline from the sibling modules. The script
# is meant to be invoked with its directory as the working context
# (Claude Desktop does this automatically). Adding the script's
# directory to sys.path is defensive: covers the case where the MCP
# client launches the server from an unrelated CWD.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# Data root resolution: on a fresh repo clone, data files (frame
# library, worked examples, transmissions, methodology, calibration,
# validation corpus, divergence spec) sit alongside this file at the
# repo root. On a pip-installed wheel, the same files are bundled
# under a `framecheck_mcp/` package directory next to this file. We
# probe for the data subtree under the package directory; fall back
# to repo-layout if not found. The probe checks for a populated
# subtree (not just the package directory itself) because the dev
# repo may have an empty `framecheck_mcp/` directory containing only
# __init__.py (build-time copies are not staged in dev mode; see
# setup.py for the cross-platform staging hook).
_PKG_DATA_DIR = os.path.join(_SCRIPT_DIR, "framecheck_mcp")
if os.path.isdir(os.path.join(_PKG_DATA_DIR, "data")):
    _DATA_ROOT = _PKG_DATA_DIR
else:
    _DATA_ROOT = _SCRIPT_DIR


# ── Protocol constants ────────────────────────────────────────────

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "frame-check"
# SERVER_VERSION is exposed via the MCP initialize handshake;
# clients see it on connect. Bump on EVERY user-visible
# capability change so installed clients can detect that an
# update is available. Semver convention here:
#   - patch: bug fix, no schema change, no prompt content change
#   - minor: new optional field in tool responses, new prompt
#     guidance, methodology refinement
#   - major: schema-breaking change to existing fields
# Full release history lives in CHANGELOG.md at the repo root
# (Keep-a-Changelog format). Releases prior to 0.8.0 are
# internal; 0.8.0 is the first planned public PyPI release per
# the release arc documented in MCP_SERVER.md.
#
# Coherence discipline with packaging: this string is the
# underlying semver M.m.p that PEP 440 pre-release markers in
# pyproject.toml decorate (`0.8.0` here vs `0.8.0.dev0` in
# pyproject during the dev-build window). At lift, pyproject's
# `.dev0` suffix drops and the two strings align character-for-
# character. PyPI publish lift sequence: see RELEASE_PREP_v1.md.
# Strict M.m.p form is enforced by
# test_server_version_bumped_for_decision_readiness_capability;
# adding suffixes here would break that pin and the handshake
# parser shape downstream consumers may rely on.
SERVER_VERSION = "0.8.3"

# Defensive ceiling against pathological multi-GB inputs that would
# hang the stdio loop. Not a product constraint on legitimate use:
# 1,000,000 chars is roughly 200,000 words (book-length analytical
# documents, long research reports, transcripts). Bumped from 10,000
# (doc) / 20,000 (source) in 2026-04-24 for the 0.8.0 release arc;
# the prior cap was inherited from the web surface's shorter-text
# posture and was too restrictive for the MCP agent-facing use case
# (full papers, briefings, multi-page analyses). The web surface
# still carries its own MAX_DOC_CHARS; these constants govern MCP
# only.
MAX_DOCUMENT_CHARS = 1_000_000
MAX_SOURCE_CHARS = 2_000_000  # source can be longer than the doc under analysis

# Production-hosting status. The provenance block emitted by every
# frame_check response carries `tool_url`, `methodology_paper`, and
# similar URLs pointing at https://frame.clarethium.com. Production
# hosting was paused 2026-04-23 (`fly scale count 0` on
# fabrication-profiler) with resume as the default trajectory; the
# URLs forward-point to the canonical production site that resumes
# per operator decision. Until then, those URLs may not resolve.
# Surfacing this status inline in provenance lets agents avoid
# treating non-resolution as a tool defect, and lets downstream
# tooling distinguish "URL canonicalized but currently paused" from
# "URL malformed or wrong." Flip to "active" on production resume;
# the resume protocol is documented in RUNBOOK.md.
PRODUCTION_STATUS = "paused"
PRODUCTION_STATUS_NOTE = (
    "Production hosting at frame.clarethium.com paused 2026-04-23; "
    "resume is the default trajectory. The tool_url, "
    "methodology_paper, frame_library, and calibration_corpus "
    "fields in this provenance block forward-point to the canonical "
    "production site and may not currently resolve; this reflects "
    "hosting state, not a tool defect. Live alternates while the "
    "site is paused: GitHub repository "
    "https://github.com/lluvr/frame-check-mcp; PyPI package "
    "frame-check-mcp (this server)."
)

# Lazy-loaded INDEX.md derivatives. build_epistemic_payload populates
# these on first call so startup stays fast and repeated calls avoid
# re-reading the same file. None signals "not loaded yet"; an empty
# dict or "unversioned" signals "loaded, no data found."
_FRAME_STATUSES: dict | None = None
_FRAME_LIBRARY_VERSION: str | None = None
_FRAME_VERSIONS: dict | None = None
# Per-entry adjacency: fvs_id -> list of fvs_ids that the entry
# explicitly names as adjacent / related frames. Parsed from the
# **Adjacent frames:** line in each entry's meta block. Only FVS
# IDs that exist on this deploy are retained; other vocabularies
# (HI-*, T-*, CLARETHIUM_VOCABULARY references) are dropped
# because they are not reachable via the MCP library namespace.
_FRAME_ADJACENCY: dict | None = None


# ── Logging ────────────────────────────────────────────────────────

_LOG_CONTROL_CHAR_RE = None  # lazily compiled in _sanitize_log_message


def _sanitize_log_message(msg: str) -> str:
    """Replace ASCII control characters (except CR, LF, TAB) with their
    Python escape representation before writing to stderr.

    A hostile request (e.g. a resource URI containing ANSI escape
    sequences) reaches `log()` via the dispatcher's exception path
    and the resolver's not-found path. Without this filter, the raw
    bytes render in an operator's terminal viewer if logs are tailed
    live, which is a terminal-injection vector against the operator
    even though the wire JSON-RPC response is safe (JSON encodes
    control chars per RFC 8259). Closes the deferred residual from
    the 0.8.0 publish-readiness audit (D2 / D3 conformance docs).

    CR, LF, and TAB are preserved because they are legitimate
    newline / indentation in multi-line log messages
    (e.g. traceback.format_exc()).
    """
    global _LOG_CONTROL_CHAR_RE
    if _LOG_CONTROL_CHAR_RE is None:
        import re as _re
        # All ASCII C0 controls except \t (0x09), \n (0x0A), \r (0x0D),
        # plus DEL (0x7F).
        _LOG_CONTROL_CHAR_RE = _re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    return _LOG_CONTROL_CHAR_RE.sub(
        lambda m: f"\\x{ord(m.group(0)):02x}", msg,
    )


def log(msg: str) -> None:
    """Write a log line to stderr.

    stdout is reserved for the JSON-RPC channel. Anything printed to
    stdout that is not valid JSON-RPC will break the client connection.
    Keep all diagnostics on stderr; MCP clients collect and display
    server stderr in their logs.

    Control characters (except CR/LF/TAB) are escaped to protect an
    operator who tails the log live from a terminal-injection vector
    via hostile request content (e.g. a resource URI containing ANSI
    escape sequences). The escape format is `\\xNN` so the original
    byte is recoverable for forensic analysis.
    """
    print(
        f"[frame-check-mcp] {_sanitize_log_message(msg)}",
        file=sys.stderr, flush=True,
    )


# ── JSON-RPC envelope helpers ──────────────────────────────────────

def _send(message: dict) -> None:
    """Write one JSON-RPC message to stdout, line-delimited."""
    print(json.dumps(message), flush=True)


def _response(req_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


# JSON-RPC standard error codes; MCP does not add its own.
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603


# ── Epistemic-payload builder ─────────────────────────────────────

def _parse_frame_adjacency() -> dict:
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
    import re as _re
    adjacency: dict = {}
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
        m = _re.search(
            r'^\*\*Adjacent frames:\*\*\s*([^\n]+)',
            text, _re.IGNORECASE | _re.MULTILINE,
        )
        if not m:
            adjacency[fvs_id] = []
            continue
        line = m.group(1)
        found: list = []
        for match in _re.finditer(r'\bFVS-(\d{3})\b', line):
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


def _build_provenance(
    analysis_layer: str,
    elapsed_ms: int,
    determinism_note: str | None = None,
) -> dict:
    """Build the provenance block shared by every MCP tool response.

    Keeping construction in one place means a version bump,
    license correction, or citation update propagates to every
    tool automatically. Callers pass the analysis_layer they are
    producing (deterministic_structural_only / _plus_verification
    / _comparison) and, when the default determinism claim is not
    right for the shape of the response, an explicit override.
    The default phrasing is singular ("identical input"); the
    compare tool uses "identical input pair" because two documents
    are the unit of determinism there.
    """
    _ensure_caches()
    from version import FRAME_CHECK_VERSION
    from clarethium_measure import __version__ as CLARETHIUM_VERSION
    import datetime as _dt

    note = determinism_note or (
        "Identical input produces identical output. No LLM is "
        "invoked in this response."
    )
    # UTC timestamp of the response, in ISO-8601 with a trailing Z.
    # Academic citations frequently want wall-clock precision
    # ("as of 2026-04-17T15:32:00Z, Frame Check v1.3 found X");
    # without this field an agent quoting the analysis would have to
    # generate the timestamp separately and race the actual analysis
    # time. The format is seconds-precision because sub-second
    # resolution would add apparent precision that the measurement
    # does not carry.
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    timestamp_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "tool_name": "Frame Check",
        "tool_url": "https://frame.clarethium.com",
        "tool_author": "Lovro Lucic",
        "methodology_paper": "https://frame.clarethium.com/corpus/methodology/",
        "frame_library": "https://frame.clarethium.com/corpus/library/",
        "calibration_corpus": "https://frame.clarethium.com/corpus/calibration/",
        "production_status": PRODUCTION_STATUS,
        "production_status_note": PRODUCTION_STATUS_NOTE,
        "license": {
            "code": "Apache-2.0",
            "corpus": "CC-BY-4.0",
            "analysis_output": (
                "CC-BY-4.0 - this response may be reproduced with "
                "attribution to Frame Check."
            ),
        },
        "frame_check_version": FRAME_CHECK_VERSION,
        # The MCP server's wheel version. Distinct axis from
        # frame_check_version above (which is the brand/methodology
        # version, also stamped into telemetry events and CITATION.cff;
        # see version.py for the two-axes rationale). server_version
        # is the version an MCP integrator sees in the initialize
        # handshake's serverInfo.version; surfacing it in provenance
        # lets agents and bug reports cross-reference the wheel without
        # having to re-issue an initialize handshake. Both fields are
        # legitimate; an integrator running frame-check-mcp 0.8.x
        # against a Frame Check methodology snapshot at brand version Y
        # will see server_version=0.8.x and frame_check_version=Y.
        "server_version": SERVER_VERSION,
        # clarethium_measure is the measurement stack. Its version
        # is pinned independently from the app version so MCP
        # clients can verify the measurement contract separately
        # from the site.
        "clarethium_measure_version": CLARETHIUM_VERSION,
        "frame_library_version": _FRAME_LIBRARY_VERSION,
        # Engine identity (Phase 5 item 8-MCP per V4_2_GAP_INVENTORY_v1.md
        # gap #22). MCP surface runs only the deterministic Layer A stack
        # server-side (regex detectors + clarethium_measure verification).
        # The V4.2 LLM-judge step is delegated to the caller's agent per
        # FRAME_DIVERGENCE_CONTRACT_v1 §7 "caller_side V4.2" regime; see
        # ENGINE_TIER_RECOMMENDATIONS_v1.md Rec I. Saved-analysis readers
        # branch on framing_engine == "layer_a" for the MCP-produced
        # server-side block, same as the web surface uses for its Layer A
        # fallback path. engine_version is the Layer A version space
        # (independent of V4.2's semver).
        "engine_version": "1.0.0",
        "framing_engine": "layer_a",
        "analysis_cost_usd": 0.0,
        "analysis_latency_ms": elapsed_ms,
        "analysis_timestamp_utc": timestamp_iso,
        "analysis_layer": analysis_layer,
        "analysis_determinism": note,
        "citation": (
            f"Lucic, L. ({now.year}). Frame Check: a research "
            f"instrument for framing and verification in documents. "
            f"https://frame.clarethium.com"
        ),
    }


# Library-index parsers live in frame_library_index so the MCP server
# and the corpus builder both consume the same canonical source of
# truth for INDEX.md row format and VERSION file location. Before
# unification, both carried duplicate regex copies, a silent
# drift risk if the INDEX.md format changed. See
# frame_library_index.py.
from frame_library_index import (
    read_library_version as _read_frame_library_version,
    parse_entry_statuses as _parse_frame_statuses,
)


# ── Resources: library, methodology, calibration ─────────────────
#
# Tools are verbs, resources are nouns. The MCP spec separates the
# two for a reason: an agent should be able to READ the Frame
# Vocabulary Standard, the methodology paper, and the calibration
# corpus directly, as static content, without invoking an analysis.
# That capability closes the "Frame Check as canonical reference"
# loop documented in the strategy: an agent that detects FVS-008
# in a document can follow up by reading the library entry
# verbatim rather than invoking a second tool or scraping the
# public site over HTTP. Every resource URI is stable; the URIs
# are the citation targets agents can hand back to a user.

RESOURCE_SCHEME = "frame-check"

# Canon-graph reference shape is owned by decision_readiness.py so
# the per-dimension library_entries on the profile, the
# adjacent_frames on each matched frame, and the aggregate
# library_entries_per_dimension all emit the same object form
# {fvs_id, library_resource_uri, public_url}. A test in
# test_decision_readiness.py pins LIBRARY_RESOURCE_SCHEME ==
# RESOURCE_SCHEME so the two cannot drift.
from decision_readiness import (
    library_entry_ref as _library_entry_ref,
    dimensions_affecting as _dimensions_affecting,
)

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

# Corpus intelligence aggregator. Reads the validation corpus
# (10 entries today) once at first query, builds per-frame and
# per-dimension stats, and exposes them as `corpus_context` blocks
# attached to matched frames, absent frames, and absence clusters.
# Substrate stays deterministic: aggregation is read-only over
# existing profile.json files; no LLM is invoked. When the corpus
# is unavailable (e.g., wheel without bundled corpus), every
# context lookup returns None and the MCP response simply omits
# the corpus_context fields rather than carrying empty placeholders.
import corpus_intelligence as _corpus_intel


def _frame_corpus_context_or_none(fvs_id: str) -> dict | None:
    """Return per-frame corpus_context or None if unavailable.
    Centralizes the path arguments so call sites stay terse."""
    if not fvs_id:
        return None
    return _corpus_intel.get_frame_corpus_context(
        fvs_id, _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
    )


def _dimension_corpus_context_or_none(dimension: str) -> dict | None:
    """Return per-dimension corpus_context or None if unavailable.
    Used by the cluster builder so each cluster can carry empirical
    dimension-level evidence."""
    if not dimension:
        return None
    return _corpus_intel.get_dimension_corpus_context(
        dimension, _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
    )


def _corpus_summary_or_none() -> dict | None:
    """Return whole-corpus summary for the divergence envelope, or
    None if unavailable. Carries the small-N caveat so the agent
    surfacing prevalence stays construct-honest."""
    return _corpus_intel.get_corpus_summary(
        _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
    )


def _build_document_signals(analysis: dict) -> dict:
    """Assemble doc_signals dict for pattern matching. Pulls from
    frame_deepening (temporal_scope, stakeholder_map,
    falsification_conditions), epistemic (sourced_pct), voice
    (classification), and claims_extracted (hedge ratio).

    Signals that are unavailable (None or missing in analysis)
    pass through as None; pattern triggers degrade to FVS-only
    logic when their discriminator signal is absent (graceful
    degradation discipline)."""
    fd = analysis.get("frame_deepening", {}) or {}
    ts = fd.get("temporal_scope") or {}
    sm = fd.get("stakeholder_map") or {}
    fc = fd.get("falsification_conditions") or {}
    epist = analysis.get("epistemic", {}) or {}
    voice = analysis.get("voice", {}) or {}
    claims = analysis.get("claims_extracted", {}) or {}
    total = claims.get("total") or 0
    hedged = claims.get("hedged_count") or 0
    hedge_ratio = (
        round(hedged / total, 3) if total > 0 else None
    )
    return {
        "falsification_count": fc.get("primary_match_count"),
        "stakeholder_role_count": sm.get("role_count"),
        "projection_phrase_count": ts.get("projection_phrase_count"),
        "sourced_pct": epist.get("sourced_pct"),
        "voice_label": voice.get("classification"),
        "hedge_ratio": hedge_ratio,
    }


# Frame Divergence v1 spec. Parts are authored canonical references per
# FRAME_DIVERGENCE_CONTRACT_v1.md §8 (MCP resource URIs). Exposed as:
#   frame-check://spec/frame-divergence/v1         -> generated index
#   frame-check://spec/frame-divergence/v1/part-1  -> FRAME_DIVERGENCE_v1.md
#   frame-check://spec/frame-divergence/v1/part-2  -> FRAME_DIVERGENCE_CONTRACT_v1.md
# Parts 3-4 pending per contract §11; will slot in by the same pattern
# when authored. Deploys without the spec files (e.g., minimal MCP
# package builds) simply do not advertise the spec index or parts.
_SPEC_FD_V1_PART1_PATH = os.path.join(_DATA_ROOT, "FRAME_DIVERGENCE_v1.md")
_SPEC_FD_V1_PART2_PATH = os.path.join(
    _DATA_ROOT, "FRAME_DIVERGENCE_CONTRACT_v1.md"
)


def _spec_fd_v1_parts() -> list[tuple[int, str, str]]:
    """List (part_num, part_title, absolute_path) tuples for Frame
    Divergence v1 spec parts present on disk.

    Part 3 (V4.2 integration) and Part 4 (self-red-team and
    competitive map) are pending per FRAME_DIVERGENCE_CONTRACT_v1.md
    §11 and will surface here when their files land. The list-based
    shape lets _list_resources and _read_resource walk the same
    source of truth rather than hard-coding part numbers twice.
    """
    parts: list[tuple[int, str, str]] = []
    if os.path.isfile(_SPEC_FD_V1_PART1_PATH):
        parts.append((
            1,
            "Category definition and non-negotiables",
            _SPEC_FD_V1_PART1_PATH,
        ))
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
        "Author: Lovro Lucic. Canonical reference for the frame "
        "divergence category as defined by Frame Check.",
        "",
        "## Parts",
        "",
    ]
    scheme = RESOURCE_SCHEME
    part_descriptions = [
        (1, "Category definition and non-negotiables",
         "category and sovereignty argument; "
         "the non-negotiables any implementation must honor"),
        (2, "Contract (c1.0)",
         "interface contract: operations, inputs, outputs, "
         "faithfulness guarantees, MCP-vs-web tier split, "
         "versioning commitments"),
        (3, "V4.2 integration",
         "per-tier implementation details; pending NEW panel "
         "re-validation landing"),
        (4, "Self-red-team and competitive map",
         "failure scenarios paired with minimum-surviving "
         "artifacts; adjacent-category positioning"),
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


def _library_entries() -> list[tuple]:
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
    import re as _re
    out: list[tuple] = []
    if not os.path.isdir(_LIBRARY_DIR):
        return out
    for fname in sorted(os.listdir(_LIBRARY_DIR)):
        if not _re.match(r"^FVS-\d{3}_.+\.md$", fname):
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
                        vm = _re.match(
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


def _library_v3_entries() -> list[tuple]:
    """Same shape as _library_entries() but reads `data/frame_library_v3/`
    (the Step-4 frozen snapshot from commit `9abeb3d`). library_v3 is
    the FRAME_DIVERGENCE_CONTRACT_v1 c1.0 pinned catalog; callers of
    the MCP divergence block get library_v3's 19-entry catalog for
    contract-stability reasons even though library_v4 is the current
    engine canonical (per LIBRARY_V3_TO_V4_RATIFICATION_v1.md). Future
    c1.1 contract will add library_v4 support as an additive pin
    option. MCP resource handlers (/library/FVS-X) serve `_LIBRARY_DIR`
    = data/frame_library/ (working library = library_v4 content) for
    reviewer-facing reads; only the divergence catalog stays on v3 for
    contract stability.

    Parallel helper rather than shared implementation to keep the
    existing `_library_entries()` behavior identical.

    Returns list of (fvs_id, title, absolute_md_path, version) tuples.
    Skips FVS-020 because library_v3 retired it from detection scope
    per Step 4 ratification; divergence never surfaces FVS-020.
    """
    import re as _re
    out: list[tuple] = []
    if not os.path.isdir(_LIBRARY_V3_DIR):
        return out
    for fname in sorted(os.listdir(_LIBRARY_V3_DIR)):
        if not _re.match(r"^FVS-\d{3}_.+\.md$", fname):
            continue
        fvs_id = fname.split("_", 1)[0]
        # FVS-020 excluded from divergence emission per library_v3
        # ratification (Step 4 Path B: retired from detection scope).
        if fvs_id == "FVS-020":
            continue
        path = os.path.join(_LIBRARY_V3_DIR, fname)
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
                        vm = _re.match(
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


def _worked_example_entries() -> list[tuple]:
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
    import re as _re
    out: list[tuple] = []
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
        metadata: dict = {
            "source_document_url": None,
            "source_document_title": None,
            "hook": None,
        }
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            m = _re.search(
                r'^---\s*\n(.*?)\n---\s*\n', text, _re.DOTALL,
            )
            if m:
                fm = m.group(1)

                def _get(key):
                    km = _re.search(
                        rf'^{_re.escape(key)}:\s*(.+)$',
                        fm, _re.MULTILINE,
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


def _transmission_entries() -> list[tuple]:
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
    import re as _re
    out: list[tuple] = []
    if not os.path.isdir(_TRANSMISSIONS_DIR):
        return out
    for fname in sorted(os.listdir(_TRANSMISSIONS_DIR)):
        if not fname.endswith(".md"):
            continue
        if fname.startswith("_") or fname == "README.md":
            continue
        slug = fname[:-3]
        path = os.path.join(_TRANSMISSIONS_DIR, fname)
        metadata: dict = {
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
            m = _re.search(
                r'^---\s*\n(.*?)\n---\s*\n', text, _re.DOTALL,
            )
            if m:
                fm = m.group(1)

                def _get(key):
                    km = _re.search(
                        rf'^{_re.escape(key)}:\s*(.+)$',
                        fm, _re.MULTILINE,
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


def _transmission_path(slug: str) -> str | None:
    """Resolve a transmission slug to its absolute .md path, or
    None if the slug is not published here. Slug matching is
    case-sensitive and rejects filesystem traversal characters
    so an agent cannot use the resource URI to read arbitrary
    files."""
    import re as _re
    if not _re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
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
    import re as _re
    if not _re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        return None
    candidate = os.path.join(_WORKED_EXAMPLES_DIR, f"{slug}.md")
    if os.path.isfile(candidate):
        return candidate
    return None


def _library_entry_path(fvs_id: str) -> str | None:
    """Resolve an FVS ID (e.g. 'FVS-008') to its absolute .md path,
    or None if the entry is not present on this deploy.

    Withdrawn entries are still served because the markdown files
    stay on disk; matching the build_corpus_site convention means
    an agent that reads frame-check://library/FVS-004 gets the
    same text whether or not the entry is published on the web
    surface.
    """
    import re as _re
    if not _re.match(r"^FVS-\d{3}$", fvs_id):
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


def _calibration_runs() -> list[tuple]:
    """List (run_id, absolute_dir_path) for every calibration run
    directory that has at least a REPORT.md. Sorted newest first
    (lexicographic on the ISO-date prefix). A run without a REPORT
    is treated as in-progress and not exposed as a resource."""
    import re as _re
    out: list[tuple] = []
    if not os.path.isdir(_CALIBRATION_RESULTS_DIR):
        return out
    for name in sorted(os.listdir(_CALIBRATION_RESULTS_DIR), reverse=True):
        if not _re.match(r"^\d{4}-\d{2}-\d{2}", name):
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
    import re as _re
    if not _re.match(r"^\d{4}-\d{2}-\d{2}[a-z0-9\-]*$", run_id):
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
    import re as _re
    if not os.path.isdir(_CALIBRATION_RESULTS_DIR):
        return None
    candidates: list[str] = []
    for d in sorted(os.listdir(_CALIBRATION_RESULTS_DIR), reverse=True):
        full = os.path.join(_CALIBRATION_RESULTS_DIR, d)
        if not os.path.isdir(full):
            continue
        if not _re.match(r"^\d{4}-\d{2}-\d{2}", d):
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
    import re as _re
    slugs: list[str] = []
    if not os.path.isdir(_CORPUS_ENTRIES_DIR):
        return slugs
    # Traversal-safe slug pattern: lowercase alphanumeric + hyphens,
    # same convention as worked-example slugs. Rejects anything
    # that could be a path-traversal attempt.
    _SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9\-]*$")
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
    import re as _re
    _SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9\-]*$")
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
    import re as _re
    _SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9\-]*$")
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
    import re as _re
    if not os.path.isdir(_AGGREGATE_RESULTS_DIR):
        return None
    candidates: list[tuple[float, str]] = []
    for name in os.listdir(_AGGREGATE_RESULTS_DIR):
        if not _re.match(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]+$", name):
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
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://library/{fvs_id}",
            "name": f"{fvs_id}: {title}",
            "description": (
                f"{version_note}Frame Vocabulary Standard entry "
                f"{fvs_id}. Markdown source. Includes "
                f"identification cues, generation affordances, and "
                f"worked examples."
            ),
            "mimeType": "text/markdown",
        })

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
        parts: list[str] = []
        type_tag = meta.get("type")
        if type_tag:
            parts.append(f"[{type_tag}]")
        summary = meta.get("summary")
        if summary:
            parts.append(summary.rstrip(".") + ".")
        tid = meta.get("transmission_id")
        pub = meta.get("published")
        if tid and pub:
            parts.append(f"({tid}, published {pub}.)")
        elif tid:
            parts.append(f"({tid}.)")
        description = " ".join(parts) or (
            "Published research transmission from "
            "blog.clarethium.com."
        )
        resources.append({
            "uri": f"{RESOURCE_SCHEME}://transmissions/{slug}",
            "name": title,
            "description": description,
            "mimeType": "text/markdown",
        })

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
        import re as _re
        _SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9\-]*$")
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

    return resources


def _read_resource(uri: str) -> dict:
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


# =============================================================================
# MCP contract v2 builders
# =============================================================================
# Per MCP_CONTRACT_V2_PROPOSAL.md, v2 exposes per-dimension evidence (matched
# tokens, vocabulary sample, signal strength) so agent-framework serializers
# produce honest prose by default. v2 emits alongside v1 during the Phase 1
# compatibility window.

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
    Thresholds are pre-registered in MCP_CONTRACT_V2_PROPOSAL.md §3.3.
    """
    density = max(0.0, float(density_per_1kw))
    for upper, label in _SIGNAL_STRENGTH_THRESHOLDS:
        if density < upper:
            return label
    return "substantive"


def _build_coverage_v2(cov: dict) -> dict:
    """Build the MCP contract v2 coverage payload from detect_coverage output.

    cov is the dict returned by framing.detect_coverage (v1 shape, unchanged).
    The v2 shape reorganizes the same information to carry the vocabulary-based
    construct through structure: per-dimension evidence (markers_matched),
    vocabulary samples, and a first-class construct block.

    See MCP_CONTRACT_V2_PROPOSAL.md §3.2 for the full shape specification.
    """
    from framing import ANALYTICAL_VOCAB_SAMPLES

    categories = cov.get("categories", {}) or {}
    dimensions: dict[str, dict] = {}
    for cat_name in ("causes", "risks", "stakeholders", "trends", "uncertainty"):
        cat_entry = categories.get(cat_name, {}) or {}
        density = cat_entry.get("density_per_1kw", 0) or 0
        markers = list(cat_entry.get("markers_matched", []) or [])
        truncated = bool(cat_entry.get("markers_matched_truncated", False))
        covered = bool(cat_entry.get("covered", False))
        dim_entry = {
            "status": "detected" if covered else "not_detected",
            "markers_matched": markers,
            "markers_matched_truncated_at_20": truncated,
            "marker_count": int(cat_entry.get("count", 0) or 0),
            "density_per_1kw": float(density),
            "signal_strength": _signal_strength_for(density),
            "vocabulary_searched_sample": ANALYTICAL_VOCAB_SAMPLES.get(cat_name, []),
            "vocabulary_source": (
                f"framing.py::ANALYTICAL_CATEGORIES[\"{cat_name}\"]"
            ),
        }
        # Sentence-level attribution, when detect_coverage was called with
        # include_attribution=True. Passes through the per-match sentence
        # mapping so agents can cite WHERE the marker fired, not just that
        # it did. Empty list when attribution was not computed.
        sentence_matches = cat_entry.get("sentence_matches")
        if sentence_matches is not None:
            dim_entry["sentence_matches"] = sentence_matches
            dim_entry["distinct_sentences_detected"] = int(
                cat_entry.get("distinct_sentences_detected", 0) or 0
            )
        # Candidate-miss surfacing, when detect_coverage was called with
        # include_candidates=True. Only populated for not-detected
        # dimensions per framing.detect_coverage contract. Construct-
        # honest: each candidate carries an explicit caveat field.
        candidate_sentences = cat_entry.get("candidate_sentences")
        if candidate_sentences is not None:
            dim_entry["candidate_sentences"] = candidate_sentences
        dimensions[cat_name] = dim_entry

    detected_count = sum(1 for d in dimensions.values() if d["status"] == "detected")
    total_count = len(dimensions)
    return {
        "contract_version": 2,
        "dimensions": dimensions,
        "summary": {
            "dimensions_with_detected_markers": detected_count,
            "dimensions_without_detected_markers": total_count - detected_count,
            "total_dimensions": total_count,
            "coverage_balance": cov.get("coverage_balance"),
        },
        "construct": {
            "signal_type": "vocabulary_and_pattern_detector",
            "statement": (
                "The coverage signal is vocabulary-and-pattern based. Each "
                "dimension has a regex expressing the lexical markers the "
                "detector counts as evidence. 'detected' means the detector "
                "matched at least one marker; 'not_detected' means it "
                "matched none. Both directions carry measurement error: "
                "'detected' may be substantive or nominal (see "
                "signal_strength and density_per_1kw), and 'not_detected' "
                "may reflect vocabulary the detector does not recognize "
                "rather than absence of coverage in the document. The "
                "measurement is a lower-bound claim about vocabulary, not "
                "an upper-bound claim about the document."
            ),
            "reference": (
                "https://frame.clarethium.com/corpus/methodology/"
            ),
            "how_to_serialize": (
                "When restating this analysis to a user, say 'the detector "
                "found markers for X, Y, Z' rather than 'the document covers "
                "X, Y, Z.' Say 'no markers detected for X' rather than 'the "
                "document does not address X.' Under-detection is a known "
                "failure mode and this construct statement is the "
                "authoritative phrasing."
            ),
        },
    }


def _build_voice_construct(voice: dict) -> dict:
    """Build the Phase B voice construct-honesty block for MCP v2.

    Unlike the under-detection construct (coverage/epistemic/claims),
    voice is a cascade classification signal: every document is
    classified; there is no 'not_detected' state. The analogous
    construct-honesty posture is classification-confidence: expose the
    margin to the winning rule's thresholds, the runner-up class, and
    a borderline flag when a small feature change could flip the
    classification.

    Returns a dict suitable for embedding as `voice.construct` in the
    MCP payload. Parallels the `coverage_v2.construct` block shape.
    """
    return {
        "signal_type": "cascade_classification",
        "statement": (
            "Voice classification is a 7-rule deterministic cascade. "
            "The winning class is the first rule whose threshold "
            "conditions are satisfied. margin_to_threshold is the best "
            "margin across the winning class's firing rules (positive "
            "= decisively crossed; near zero = barely crossed). "
            "runner_up is the next cascade class (different from "
            "winner) that would be evaluated if the winner's rule had "
            "not fired; runner_up_margin is that class's best rule "
            "margin (positive = it would fire too, preempted by "
            "cascade; negative = missed activation by that much). "
            "confidence is 'borderline' when margin_to_threshold < 2 "
            "or runner_up_margin > -2 (small feature change could "
            "flip the classification); 'high' otherwise. This is the "
            "classification-confidence construct: the analogue for "
            "categorical signals of the under-detection construct "
            "used for presence/absence signals (coverage, epistemic, "
            "claims)."
        ),
        "reference": (
            "https://frame.clarethium.com/corpus/methodology/"
        ),
        "how_to_serialize": (
            "When restating this classification to a user, say "
            "'classified as X' rather than 'the document is X.' "
            "When confidence is 'borderline', name the runner-up "
            "class explicitly: 'classified as X, borderline; Y nearly "
            "fired.' Do not restate a borderline classification as "
            "decisive. When confidence is 'high' AND voice is NOT "
            "'analytical', the classification is safe to restate "
            "without the margin caveat. When voice is 'analytical', "
            "note that analytical is the cascade RESIDUAL: no "
            "prescriptive/promotional/descriptive/advisory rule fired, "
            "so the label reflects absence of positive voice evidence "
            "rather than decisive analytical detection. Restate as "
            "'classified as analytical (no other voice markers "
            "detected)' rather than 'the document is analytical.' "
            "This mirrors the under-detection discipline applied to "
            "the coverage signal (see METHODOLOGY §1.3 and §1.3.1)."
        ),
    }


def _build_temporal_construct(temp: dict) -> dict:
    """Build the Phase B temporal construct-honesty block for MCP v2.

    Temporal is a distribution signal (past/present/future percentages
    summing to 100). The construct-honesty posture surfaces
    `dominant_margin` (lead over runner-up tense) and a `balanced` flag
    (no tense reaches 50% and dominant margin < 10 points). A balanced
    document should not be read as time-anchored regardless of the
    dominant label.

    Returns a dict suitable for embedding as `temporal.construct`.
    """
    return {
        "signal_type": "distribution_with_dominant",
        "statement": (
            "Temporal orientation is the distribution of past, "
            "present, and future tense markers across sentences "
            "(summing to approximately 100%). The dominant tense is "
            "the highest percentage; dominant_margin is the lead over "
            "the second-place tense. balanced is True when no tense "
            "reaches 50% and dominant_margin is under 10 points; in "
            "that state the document is temporally spread and the "
            "dominant label does not signal time-anchoring. A "
            "high-margin dominant (e.g., past at 75%) is a genuine "
            "time-anchor; a low-margin dominant (e.g., past at 38%, "
            "present at 35%) is not. Reader judgment integrates the "
            "dominant label with the margin."
        ),
        "reference": (
            "https://frame.clarethium.com/corpus/methodology/"
        ),
        "how_to_serialize": (
            "When restating, say 'X-oriented with a Y-point margin "
            "over the runner-up tense' rather than 'the document is "
            "X-oriented.' When balanced is True, say 'temporally "
            "balanced; no tense dominates' rather than restating the "
            "dominant label. The dominant field is still populated "
            "when balanced=True but should be treated as a weak "
            "signal."
        ),
    }


# ── Per-level construct treatment (substrate-side composition L5) ────
#
# The substrate produces three qualitatively different kinds of claim:
# detector measurements, classifier outputs, and composed patterns.
# Evidence discipline applies differently at each level: a
# detector firing is a lower-bound vocabulary claim; a classifier
# output is a margin-aware classification with no IRR data; a composed
# pattern's trigger is deterministic but its reading is a single-curator
# normative claim about what the trigger means.
#
# Each composed entity in the substrate carries a `claim_level` field
# pointing at one of the three treatments. Agents (and external
# evaluators) read agent_guidance.claim_level_treatments for the
# per-level discipline, then cite each entity per the matching
# treatment. This makes the substrate's epistemic claim chain explicit
# instead of inheriting one composition_discipline across all levels.

_CLAIM_LEVEL_DETECTOR = "detector_measurement"
_CLAIM_LEVEL_CLASSIFIER = "classifier_output"
# Added 2026-04-28 per CONSTRUCT_VALIDITY_AUDIT_v1 v1.2 / OPEN_DECISIONS
# v1 D1 Proposal A. Names the LLM-judge binary classification shape
# distinct from `classifier_output`'s deterministic-cascade-with-
# confidence shape. V4.2 emissions are the canonical instance: binary
# `exhibits` value with reasoning text and per-frame reliability tier
# but no per-emission confidence or runner-up. The borderline-vs-
# decisive distinction is a property of the macro aggregate (macro-F1
# across the validation corpus, intra-rater AC1 across run-pairs)
# rather than the per-emission. As of 2026-04-28 V4.2 ships only on
# the evaluation engine surface; the first MCP wheel that ships V4.2
# emissions on the wire MUST tag them with this claim_level.
_CLAIM_LEVEL_LLM_CLASSIFIER = "llm_classifier_output"
_CLAIM_LEVEL_COMPOSED = "composed_pattern"
_CLAIM_LEVEL_AGENT_GENERATED = "agent_generated"

# Module-level constant: the per-level construct treatments. Built
# once at import (no inputs, no per-call variation). Each treatment
# carries:
#   claim_type: one-line description of the claim shape at this level
#   validation_status: structured honesty about what is / isn't
#     validated (deterministic, methodology_documented,
#     inter_rater_reliability, validity_data)
#   caveats: list of specific things the agent must surface when citing
#   how_to_cite: phrasing template (used in tandem with the per-signal
#     construct.how_to_serialize fields where present)
#
# The treatments are keyed by claim_level value so the agent can look
# up the discipline from the entity's claim_level. The substrate stays
# construct-honest: validation_status names what is NOT yet measured
# (no inter-rater reliability pilot on the classifier or pattern
# catalog; no precision/recall against labeled gold-standard) so the
# agent does not over-claim on the user's behalf.
_CLAIM_LEVEL_TREATMENTS: dict = {
        _CLAIM_LEVEL_DETECTOR: {
            "claim_type": (
                "Deterministic feature/regex detector firing or "
                "non-firing on the document text."
            ),
            "validation_status": {
                "deterministic": True,
                "methodology_documented": True,
                "inter_rater_reliability": "not_applicable",
                "validity_data": (
                    "Vocabulary-and-pattern detection with documented "
                    "under-detection construct (METHODOLOGY §1.3 and "
                    "§1.3.1). Per-signal construct blocks "
                    "(analysis.coverage_v2.construct, "
                    "analysis.epistemic.note, candidate-miss surfacing "
                    "on coverage / epistemic / claims) carry the "
                    "detector-specific caveats. IRR is not applicable "
                    "to algorithmic detectors; reproducibility is the "
                    "validity claim and is documented per signal."
                ),
            },
            "caveats": [
                "Detector firing is a lower-bound vocabulary claim, "
                "not an upper-bound document claim.",
                "Non-firing may reflect vocabulary the detector does "
                "not recognize rather than absence of the dimension "
                "in the document.",
                "Cite as 'Frame Check's detector found markers for "
                "X' or 'no markers detected for X' rather than 'the "
                "document covers X' or 'the document does not "
                "address X'.",
            ],
            "how_to_cite": (
                "Frame Check's detector found markers for X / no "
                "markers detected for X."
            ),
        },
        _CLAIM_LEVEL_LLM_CLASSIFIER: {
            "claim_type": (
                "LLM-judge binary or categorical classification with "
                "curated definition + reasoning text but WITHOUT "
                "per-emission confidence/runner-up structure. V4.2 "
                "FVS detection is the canonical instance."
            ),
            "validation_status": {
                "deterministic": False,
                "methodology_documented": True,
                "inter_rater_reliability": "macro_aggregate_only",
                "validity_data": (
                    "Reliability is reported at the macro aggregate "
                    "level (macro-F1 across the validation corpus, "
                    "intra-rater AC1 across run-pairs), not at the "
                    "per-emission level. The borderline-vs-decisive "
                    "distinction is a property of the aggregate, not "
                    "the per-emission. F-2026-035 macro-F1 = 0.732 on "
                    "the mg_v2 n=26 corpus; per-frame F1 documented "
                    "in result JSONs. Two named per-frame chronic "
                    "gaps (FVS-007 over-fire, FVS-001 low-recall) "
                    "diagnosed at substrate level in "
                    "FVS_007_001_SHIP_READINESS_v1.md."
                ),
            },
            "caveats": [
                "The reasoning text is the engine's rationale for "
                "the binary judgment, not a confidence proxy. Do not "
                "paraphrase it as 'Frame Check is X% confident'.",
                "Per-emission borderline-vs-decisive distinction is "
                "unavailable. Cite the per-frame reliability tier as "
                "the macro-aggregate evidence; do not treat any "
                "single emission as decisive without disclosing the "
                "intra-rater variance.",
                "Surface honest_limit caveats verbatim when the "
                "engine emits one. The honest_limit text is per-"
                "frame and names the operationalization gap in "
                "single-emission terms.",
                "The construct is LLM-judged, not deterministic. "
                "Two engine runs on the same document at temperature "
                "0 can disagree on individual binary judgments at "
                "rates consistent with F-2026-032's MODERATE-NOISE "
                "band; aggregate reliability is the load-bearing "
                "evidence.",
            ],
            "how_to_cite": (
                "Frame Check's V4.2 engine judged the document as "
                "exhibiting X (tier Y reliability; honest_limit Z "
                "when present)."
            ),
        },
        _CLAIM_LEVEL_CLASSIFIER: {
            "claim_type": (
                "Deterministic cascade or scoring classifier with "
                "margin-aware confidence and runner-up reporting."
            ),
            "validation_status": {
                "deterministic": True,
                "methodology_documented": True,
                "inter_rater_reliability": "not_yet_measured",
                "validity_data": (
                    "Classifier uses deterministic feature scoring "
                    "with documented thresholds; abstains without "
                    "feature evidence (post-2026-04 fix on the genre "
                    "classifier closes the no-features-but-claims "
                    "advocacy artifact). No precision/recall against "
                    "labeled gold-standard yet; no inter-rater "
                    "reliability pilot. Per-signal construct blocks "
                    "(voice.construct cascade-classification, "
                    "temporal.construct distribution-with-dominant, "
                    "genre.construct per-genre description) carry the "
                    "classifier-specific caveats."
                ),
            },
            "caveats": [
                "Classifier confidence is margin-to-runner-up, not "
                "external validity data.",
                "Borderline classifications must surface the "
                "runner-up explicitly so the cascade's hesitation is "
                "visible to the reader.",
                "Single-author calibrated; no IRR data; treat the "
                "classification as Frame Check's reading rather than "
                "a measured property of the document.",
            ],
            "how_to_cite": (
                "Frame Check classified as X (confidence Y; "
                "runner-up Z when borderline)."
            ),
        },
        _CLAIM_LEVEL_COMPOSED: {
            "claim_type": (
                "Substrate-side composition over detector and "
                "classifier outputs. Trigger conditions are "
                "deterministic; the reading text inside the "
                "composition is a single-curator normative claim "
                "about what the trigger means."
            ),
            "validation_status": {
                "deterministic": True,
                "methodology_documented": True,
                "inter_rater_reliability": "not_yet_measured",
                "validity_data": (
                    "Trigger conditions deterministic and "
                    "reproducible (canon-graph set membership for "
                    "absence_clusters; multi-frame plus doc-signal "
                    "discriminators for frame_patterns). The reading "
                    "text and the curator's pattern catalog (eight "
                    "named patterns in frame_patterns._PATTERNS; "
                    "five canonical dimension cluster readings in "
                    "_DIMENSION_CLUSTER_READINGS) are single-author "
                    "authored. No IRR pilot has measured whether "
                    "other readers compose the same patterns from "
                    "the same triggers; no precision/recall against "
                    "an external rater set."
                ),
            },
            "caveats": [
                "The trigger match is reproducible; the reading "
                "inside is the curator's normative claim about what "
                "the trigger means.",
                "Cite the reading as Frame Check's reading, not as "
                "a measured property of the document.",
                "No inter-rater reliability data on whether other "
                "readers would compose the same pattern from the "
                "same triggers; treat the named composition as "
                "Frame Check's recognition of a structural shape, "
                "not a verdict on the document.",
            ],
            "how_to_cite": (
                "Frame Check identified pattern X (composed "
                "deterministically by trigger Y); the substrate's "
                "reading of pattern X is: ..."
            ),
        },
        _CLAIM_LEVEL_AGENT_GENERATED: {
            "claim_type": (
                "Opt-in LLM-composed content. The substrate "
                "delegates the composition to an external model "
                "(provider + model + cost tracked per-output in "
                "model_provenance). Distinct from the other three "
                "levels because the output is non-deterministic: "
                "different runs by different model versions can "
                "produce different content from the same inputs."
            ),
            "validation_status": {
                "deterministic": False,
                "methodology_documented": True,
                "inter_rater_reliability": "not_applicable",
                "validity_data": (
                    "LLM-composed content; reproducibility is not "
                    "the validity claim because the output is "
                    "non-deterministic by design (Item 12 strategic "
                    "discipline). Each output carries "
                    "model_provenance with provider, model, cost in "
                    "USD, input/output token counts, and "
                    "is_deterministic=false. The substrate-"
                    "deterministic identity is preserved: when the "
                    "opt-in flag is omitted, the substrate composes "
                    "without LLM (clusters, patterns, absences with "
                    "goal/genre relevance) and the agent gets the "
                    "deterministic substrate alone. IRR is not "
                    "applicable because the output is generative; "
                    "different models or different runs producing "
                    "different content is the design, not a "
                    "validity gap."
                ),
            },
            "caveats": [
                "Generated content is non-reproducible across "
                "model versions and runs; cite the model_"
                "provenance fields (provider, model, cost) as the "
                "audit trail.",
                "The frame's general teaching_question_general is "
                "the stable catalog reference; the generated_"
                "question is one document-specific application "
                "composed by the LLM, not a measurement.",
                "Never present LLM-generated content as Frame "
                "Check's measurement; the construct-honest cite "
                "is 'Frame Check requested an LLM-composed "
                "question (provider X, model Y, cost Z; "
                "is_deterministic=false in model_provenance); the "
                "generated application is: ...'.",
            ],
            "how_to_cite": (
                "Frame Check requested an LLM-composed question "
                "(provider X, model Y, cost Z USD; "
                "is_deterministic=false in model_provenance); the "
                "generated application of FVS-N's general teaching "
                "question to this document is: ..."
            ),
        },
}


def _apply_v2_only_preference(payload: dict) -> None:
    """Remove the legacy v1 coverage block when the client prefers v2.

    Leaves coverage_v2 as the only coverage field. Intended for clients
    that have migrated to v2 and want to avoid payload duplication.
    Keeps all other signals (voice, temporal, epistemic, claims) in
    their v1 shape since the v2 redesign for those is deferred to v3.

    Per MCP_CONTRACT_V2_PROPOSAL.md §4.1 Phase 1: additive emission is
    the default. Phase 2 (future release) adds deprecation notice to v1.
    Phase 3 (conditional) stops emitting v1 regardless of preference.
    """
    analysis = payload.get("analysis") or {}
    if "coverage" in analysis and "coverage_v2" in analysis:
        # Drop v1 coverage; promote v2 by keeping it under its current key.
        del analysis["coverage"]


# ── Frame Divergence block (FRAME_DIVERGENCE_CONTRACT_v1 Part 2) ─────
#
# Per the contract: when `include_divergence=true` is passed to
# frame_check, the response carries a top-level `divergence` block
# alongside analysis / agent_guidance / provenance, plus two
# agent_guidance additions. This function builds that block.
#
# MCP-surface semantics (Contract §7.1): Frame Check's MCP server
# does NOT invoke an external LLM. absent_frames are computed from
# the library_v3 catalog minus frames present in V1 frame_library_matches;
# `absence_basis` is scaffolding text describing what the caller's
# model should verify; `agent_guidance.how_to_render_divergence`
# carries V4.2 judge prompt scaffolding so the caller's own agent
# model can complete the composition.
#
# Contract §2.3 reserves the names `frame_divergence`, `frame_inventory`,
# `frame_gap` in the MCP tool namespace. This implementation honors
# Rec II (enhance `frame_check`, no separate tool).


_DOMAIN_HINT_ENUM = (
    "finance", "founder_decision", "investment_research",
    "product_announcement", "policy", "health_biomedical",
    "tech_science", "humanities", "general",
)
_DIVERGENCE_RENDERING_ENUM = (
    "list", "completeness_check", "teaching_questions", "narrative",
)
_SPEC_VERSION = "FRAME_DIVERGENCE_v1_c1.0"


def _signal_strength_for_absent_frame(
    affects_dims: list[str],
    cov_missing: list[str],
) -> str:
    """Score an absent frame's reader-relevance for THIS document.

    Three tiers:
      - high: frame is canon for ≥2 decision-readiness dimensions
        AND the coverage dimension is canon for the frame AND the
        document is weak on coverage (any missing categories).
      - medium: frame is canon for ≥1 decision-readiness dimension.
      - low: frame is not canon for any decision-readiness dimension
        (e.g., FVS-013 Oracle, FVS-014 Temporal Anchoring,
        FVS-019 Narrative Coherence as meta-level frames).

    The heuristic uses only the canon-graph (DIMENSION_LIBRARY_ENTRIES
    in decision_readiness.py) plus the coverage-missing signal. It is
    deliberately conservative: a future move (per the §12 extension
    pattern) can layer in domain applicability metadata, full
    decision_readiness profile signals across all five dimensions,
    and document-content semantics. The current heuristic produces a
    defensible baseline that the caller's V4.2 model can override.
    """
    n_dims = len(affects_dims)
    coverage_canon = "coverage" in affects_dims
    coverage_weak = bool(cov_missing)
    if n_dims >= 2 and coverage_canon and coverage_weak:
        return "high"
    if n_dims >= 1:
        return "medium"
    return "low"


# Substrate-side composition over absent frames. Where the agent
# previously had to discover patterns across the absent_frames list
# (e.g., "these four absent frames cluster on the counterfactual
# dimension"), the substrate now surfaces the pattern directly with
# a dimension-specific reading. Each reading is curated, reading-
# form (not verdict-form), and tied to the canon-graph dimension
# definition. The five dimensions match DIMENSION_LIBRARY_ENTRIES in
# decision_readiness.py; new dimensions added there must add a
# matching reading here or get the construct-honest placeholder.
_DIMENSION_CLUSTER_READINGS = {
    "coverage": (
        "Load-bearing absences cluster on the coverage dimension: "
        "the document's framing leaves out perspectives that would "
        "broaden how it sees its subject. The reader cannot stress-"
        "test the analysis against viewpoints the framing does not "
        "carry."
    ),
    "calibration": (
        "Load-bearing absences cluster on the calibration dimension: "
        "the document does not signal where its confidence is "
        "provisional, where its claims are hedged, or where the "
        "evidence under-determines the conclusion."
    ),
    "evidence": (
        "Load-bearing absences cluster on the evidence dimension: "
        "the document's claims do not lean on citable sources, "
        "named authorities, or independent grounding the reader "
        "can verify."
    ),
    "robustness": (
        "Load-bearing absences cluster on the robustness dimension: "
        "the document does not test its claims against alternative "
        "interpretations, methodologies, or counter-evidence the "
        "framing would resist."
    ),
    "counterfactual": (
        "Load-bearing absences cluster on the counterfactual "
        "dimension: the document does not name conditions under "
        "which its conclusion would be wrong, alternative scenarios "
        "where the pattern shifts, or risks that would invalidate "
        "the framing."
    ),
}

# Cluster firing threshold. A cluster surfaces when at least
# _CLUSTER_MIN_ABSENT absent frames share a dimension AND the
# absent set covers at least _CLUSTER_MIN_CANON_FRACTION of that
# dimension's canon membership. The two-condition logic is
# calibration-honest: an absolute threshold of three would silently
# bias the substrate to surface only multi-canon dimensions
# (coverage, counterfactual) and never small-canon dimensions
# (calibration with 2 canon members; both absent is 100% of canon
# and a strong signal that an absolute threshold misses).
# Single-canon dimensions (evidence, robustness in DIMENSION_LIBRARY
# _ENTRIES) cannot reach 2 absent and so cannot cluster; that is
# honest, since "cluster" is meaningless for a one-element canon.
_CLUSTER_MIN_ABSENT = 2
_CLUSTER_MIN_CANON_FRACTION = 0.5

# Document word-count floor below which the cluster builder
# abstains. Below this floor, absent_frames is largely a function
# of catalog size minus a handful of matches (or zero matches);
# clusters fire mechanically on the canon graph rather than on a
# document signal worth surfacing. Mirrors frame_deepening's
# 100-word floor for analogous construct honesty.
_CLUSTER_MIN_DOCUMENT_WORDS = 100

# Tier order for cluster signal_strength aggregation.
_CLUSTER_TIER_ORDER = {"high": 0, "medium": 1, "low": 2}


def _build_absence_clusters(
    absent_records: list[dict],
    *,
    document_word_count: int | None = None,
    matched_frame_count: int | None = None,
    document_claim_count: int | None = None,
) -> list[dict]:
    """Group absent frames by shared canonical dimensions and surface
    clusters that meet the firing threshold.

    The cluster is the substrate's composition over the divergence
    set. Replaces agent-side cluster discovery with substrate-side
    cluster surfacing while staying deterministic (no LLM, no
    document-content semantics; only canon-graph set membership and
    aggregation of per-frame signal_strength).

    Each cluster carries:
      - dimension: canonical dimension name
      - member_frames: sorted FVS IDs that are absent and canon for
        this dimension
      - member_count: integer count of member frames
      - canon_size: total canon members for this dimension
      - canon_coverage_fraction: member_count / canon_size, rounded
        to two decimals
      - signal_strength: highest member-frame tier (high > medium >
        low); the cluster is at least as strong as its strongest
        member
      - reading: dimension-specific prose composition with member-
        count and canon-coverage anchoring

    Returns a list sorted by signal_strength (high first), then
    canon_coverage_fraction descending (most under-attended first),
    then dimension alphabetical for stable tiebreaking. Empty list
    when no dimension meets the firing threshold OR when the
    document is below the word-count floor (the substrate stays
    construct-honest about whether the absences carry document
    signal).
    """
    # Construct-honest abstention: below the word-count floor, the
    # absent set is dominated by catalog size minus a small number
    # of matches; clusters would fire on the canon graph rather
    # than on real document signal. Surface no clusters.
    if (
        document_word_count is not None
        and document_word_count < _CLUSTER_MIN_DOCUMENT_WORDS
    ):
        return []
    # Construct-honest abstention: when zero frames match, the
    # absent_records list IS the catalog. Clusters then surface
    # canon-graph structure rather than document signal. This
    # commonly fires on off-methodology text (non-English, code,
    # poetry, fragments) above the word-count floor; the matched-
    # frames count distinguishes those cases from documents whose
    # framing is genuinely under-attended on multiple dimensions.
    # Threshold is 1: a single match is enough to indicate the
    # detector found analytical signal.
    if matched_frame_count is not None and matched_frame_count == 0:
        return []
    # Construct-honest abstention: zero claims detected is a
    # second-line off-methodology signal. Some FVS detectors fire
    # vacuously on non-analytical text (e.g. FVS-007 fires when
    # 'risks' and 'uncertainty' are both missing and unhedged_pct
    # is high; on Lorem ipsum or code, all of those conditions
    # trivially hold). When the claim extractor found zero claims,
    # the document does not carry analytical content; clusters
    # would surface canon-graph noise.
    if (
        document_claim_count is not None
        and document_claim_count == 0
    ):
        return []

    from decision_readiness import DIMENSION_LIBRARY_ENTRIES

    # Index absent frames by dimension and capture each member's
    # signal_strength tier so the cluster can aggregate.
    by_dimension: dict[str, list[tuple[str, str]]] = {}
    for record in absent_records:
        affects_dims = record.get("affects_dimensions") or []
        fvs_id = record.get("frame_id")
        tier = record.get("signal_strength", "low")
        if not fvs_id:
            continue
        for dim in affects_dims:
            by_dimension.setdefault(dim, []).append((fvs_id, tier))

    clusters: list[dict] = []
    for dim, members in by_dimension.items():
        canon_size = len(DIMENSION_LIBRARY_ENTRIES.get(dim, []))
        if canon_size <= 0:
            # Unknown dimension; canon size unavailable. Skip to
            # avoid surfacing a cluster we cannot honestly anchor.
            continue
        member_count = len(members)
        if member_count < _CLUSTER_MIN_ABSENT:
            continue
        coverage_fraction = member_count / canon_size
        if coverage_fraction < _CLUSTER_MIN_CANON_FRACTION:
            continue

        # Aggregate signal_strength as the highest member tier; the
        # cluster is at least as strong as its strongest absence.
        member_tiers = [tier for _, tier in members]
        cluster_signal = min(
            member_tiers,
            key=lambda t: _CLUSTER_TIER_ORDER.get(t, 9),
        )

        sorted_frames = sorted(fvs_id for fvs_id, _ in members)
        reading_template = _DIMENSION_CLUSTER_READINGS.get(dim)
        if not reading_template:
            # Unknown dimension. Emit a construct-honest placeholder
            # so the agent sees the grouping; do not fabricate prose
            # for a dimension whose reading was not curated.
            reading_template = (
                f"Load-bearing absences cluster on the {dim} "
                f"dimension; a dimension-specific reading is not "
                f"yet curated for this canonical dimension."
            )
        # Anchor the curated reading in the cluster's evidence: how
        # many member frames out of canon are absent. This is the
        # smallest move from generic dimension prose to evidence-
        # specific reading while staying deterministic.
        reading = (
            f"{reading_template} "
            f"{member_count} of {canon_size} {dim}-canon frames "
            f"are absent in this document."
        )

        # corpus_context for this dimension cluster: empirical
        # dimension-level evidence from the aggregate (peer-pair
        # difference rate; cross-question outlier finding when
        # available). The cluster reading composes catalog assertion
        # ("the dimension is under-attended") with corpus evidence
        # ("and that dimension differs across N of M peer pairs in
        # our validation corpus"). None when aggregate unavailable.
        dim_corpus_ctx = _dimension_corpus_context_or_none(dim)

        clusters.append({
            "dimension": dim,
            "member_frames": sorted_frames,
            "member_count": member_count,
            "canon_size": canon_size,
            "canon_coverage_fraction": round(coverage_fraction, 2),
            "signal_strength": cluster_signal,
            # Per-level construct treatment: the cluster is a
            # substrate-side composition (canon-graph set membership
            # over absent_frames; threshold-firing). Trigger is
            # deterministic; the reading text below is curator-
            # authored. Cite per agent_guidance.claim_level_treatments
            # [composed_pattern].
            "claim_level": _CLAIM_LEVEL_COMPOSED,
            "reading": reading,
            "corpus_context": dim_corpus_ctx,
        })

    # Sort: signal_strength first (high before medium before low),
    # then canon_coverage_fraction descending (most under-attended
    # first), then dimension alphabetical for stable tiebreaking.
    clusters.sort(
        key=lambda c: (
            _CLUSTER_TIER_ORDER.get(c["signal_strength"], 9),
            -c["canon_coverage_fraction"],
            c["dimension"],
        )
    )
    return clusters


def _build_divergence_block(
    frame_library_matches: list[dict],
    *,
    domain_hint: str | None,
    rendering: str,
    catalog_version_pin: str | None,
    engine_status: str = "beta",
    cov_missing: list[str] | None = None,
    user_context_present: bool = False,
    document_genre: str | None = None,
    document_word_count: int | None = None,
    document_claim_count: int | None = None,
    user_goal: str | None = None,
    document_text_for_opportunities: str | None = None,
    include_frame_opportunities: bool = False,
    document_signals: dict | None = None,
    compose_budget: str = "full",
) -> dict:
    """Build the FRAME_DIVERGENCE_CONTRACT_v1 Part 2 `divergence` block.

    Signature is minimal but takes enough document signal (cov_missing)
    to score each absent frame's reader-relevance per the c1.0 §13
    signal_strength tier. Does NOT invoke any LLM (MCP surface per
    Contract §7.1).

    `rendering` affects only AbsentFrameRecord decoration
    (teaching_question present when "teaching_questions"). All other
    rendering variants are caller-rendered presentation layers over the
    same data.

    Returns the {divergence, agent_guidance_additions} pair; caller
    integrates both into the frame_check response.
    """
    # Pin catalog version (only library_v3 supported in c1.0)
    catalog_version = catalog_version_pin or "library_v3"
    if catalog_version != "library_v3":
        # Contract §9.1 CATALOG_VERSION_NOT_FOUND would be the error
        # code; for this initial integration we coerce to library_v3
        # and add a limitation. When additional catalog versions ship,
        # this path becomes an error.
        catalog_version = "library_v3"

    cov_missing = cov_missing or []

    library = _library_v3_entries()
    present_ids = {
        m.get("fvs_id") for m in frame_library_matches
        if isinstance(m, dict) and m.get("fvs_id")
    }

    # Pull the canon-graph (FVS -> decision-readiness dimensions) once
    # so each absent frame's tier can be computed in O(1).
    from decision_readiness import dimensions_affecting

    absent_records: list[dict] = []
    provisional_count = 0
    tier_counts = {"high": 0, "medium": 0, "low": 0}
    for fvs_id, title, md_path, version in library:
        if fvs_id in present_ids:
            continue

        # Contract §5.3: after library_v3 ratification, no frames
        # currently flagged provisional. FVS-010 kept library_v1 text
        # stable with honest_limit disclosure; FVS-020 already excluded
        # in _library_v3_entries(). The stability field is retained so
        # future library revisions can flag frames without a contract
        # change.
        stability = "stable"

        affects_dims = list(dimensions_affecting(fvs_id))
        signal = _signal_strength_for_absent_frame(affects_dims, cov_missing)
        tier_counts[signal] += 1

        affects_str = ", ".join(affects_dims) if affects_dims else None
        if signal == "high":
            relevance_rationale = (
                f"{fvs_id} is canon for {len(affects_dims)} decision-"
                f"readiness dimensions ({affects_str}); the document "
                f"is weak on coverage "
                f"({len(cov_missing)} of 5 categories not detected). "
                f"High reader-relevance signal."
            )
        elif signal == "medium" and affects_str:
            relevance_rationale = (
                f"{fvs_id} is canon for {len(affects_dims)} decision-"
                f"readiness dimension(s) ({affects_str}). Medium "
                f"reader-relevance signal; the caller's model decides "
                f"whether the absence matters for this document."
            )
        elif signal == "medium":
            relevance_rationale = (
                f"{fvs_id} has a domain-level signal but no canon-"
                f"graph link to decision-readiness dimensions. Medium "
                f"reader-relevance signal."
            )
        else:
            relevance_rationale = (
                f"{fvs_id} is a meta-level frame; not canon for any "
                f"decision-readiness dimension. Low reader-relevance "
                f"signal; consider only in cross-cutting analyses."
            )
        if domain_hint:
            relevance_rationale += f" Hinted domain: '{domain_hint}'."

        # corpus_context for this absent frame: empirical evidence
        # of how this frame behaves across the validation corpus.
        # Substrate-side cite-back (Item 7 of the substrate-side
        # composition roadmap): the agent reading an absent frame
        # gets prevalence, typical co-absences, and corpus_resource
        # _uris pointing at corpus entries where THIS frame fires.
        # The agent can chain to those entries to see the frame in
        # use and contrast with the current document's absence.
        # None when corpus unavailable.
        frame_corpus_ctx = _frame_corpus_context_or_none(fvs_id)

        # goal_relevance for this absent frame: substrate-side
        # composition Item 11. When the user (or agent) signals a
        # goal (decide / brainstorm / persuade / learn / audit),
        # absences load-bearing for that goal carry priority +
        # reason. None when no goal is set or goal is 'audit'.
        from user_goals import get_goal_relevance as _get_goal_rel
        frame_goal_relevance = _get_goal_rel(fvs_id, user_goal)

        # genre_relevance for this absent frame: substrate-side
        # composition Item 3. When the document is classified into
        # a structural genre (recommendation, analysis, narrative,
        # advocacy, exploration, instruction), some absences are
        # load-bearing for that genre's reasoning. The substrate
        # promotes those absences with a curated reason. None when
        # the document genre is unknown or this frame is not in the
        # genre's load-bearing list. Substrate stays deterministic;
        # the relevance map is curated per genre.
        from genre_classifier import get_genre_relevance as _get_gr
        frame_genre_relevance = _get_gr(fvs_id, document_genre)

        record = {
            "frame_id": fvs_id,
            "frame_version": f"v{version}" if version else "v?",
            "frame_title": title,
            "stability": stability,
            "signal_strength": signal,
            # Per-level construct treatment (substrate-side composition
            # L5): the absent_frame record is a non-firing of the V1
            # detector. Cite per agent_guidance.claim_level_treatments
            # [detector_measurement]. signal_strength inside the record
            # is itself a classifier_output (canon-graph + coverage
            # weakness composition); the agent reading the tier should
            # honor classifier_output discipline (margin / runner-up /
            # IRR-not-yet) when surfacing the tier label.
            "claim_level": _CLAIM_LEVEL_DETECTOR,
            "affects_dimensions": affects_dims,
            "citation_uri": f"{RESOURCE_SCHEME}://library/{fvs_id}",
            # GitHub URL pointing at the entry's markdown source on
            # the public repository (lluvr/frame-check-mcp). End-users
            # in MCP clients (Claude Desktop, Cursor) cannot click
            # frame-check://library/... resource URIs because those
            # are MCP-internal; the library_url gives them an HTTP
            # link they can follow. Always-resolvable regardless of
            # hosted-production status. None when no canonical
            # filename is known for the ID.
            "library_url": (
                _library_entry_ref(fvs_id).get("public_url")
                if fvs_id else None
            ),
            "corpus_context": frame_corpus_ctx,
            "genre_relevance": frame_genre_relevance,
            "goal_relevance": frame_goal_relevance,
            # Contract §4.2 absence_basis on MCP: scaffolding string
            # for the caller's model to verify. Not prescriptive.
            "absence_basis": (
                f"Caller's model must confirm no {fvs_id} identification "
                f"cues fired in the supplied document. V1 rule-based "
                f"detection on this document did not match {fvs_id}. "
                f"See frame-check://library/{fvs_id} for identification "
                f"cues and counter-examples that inform the judgment."
            ),
            "domain_relevance_rationale": relevance_rationale,
        }

        # Contract §4.2 optional teaching_question: only emitted when
        # rendering is "teaching_questions". The FVS entry's teaching
        # question is extracted from the markdown body if present;
        # absent when the entry does not define one.
        if rendering == "teaching_questions":
            teaching_question = _extract_teaching_question(md_path)
            if teaching_question:
                record["teaching_question"] = teaching_question

        absent_records.append(record)

    # Sort absent_records by signal_strength tier (high first), then
    # frame_id ascending within tier. Stable, deterministic ordering
    # so a caller can take the first N entries and get the highest-
    # leverage absences without further filtering.
    _tier_order = {"high": 0, "medium": 1, "low": 2}
    # Sort: signal_strength tier first (catalog + coverage logic;
    # objective document signal). Within tier, goal_relevance
    # priority promotes (the user's stated intent). Within same
    # goal priority, genre_relevance priority promotes (the
    # document's structural shape). Within same genre priority,
    # frame_id alphabetical for stability.
    #
    # The composition: signal is empirical (catalog + coverage),
    # goal is user intent, genre is document state. Goal precedes
    # genre because the user's stated goal is more direct than
    # inferred document classification; signal precedes goal
    # because empirical signal cannot be overridden by user
    # preference. Records without a relevance entry sort with
    # priority 999 so they fall after curated entries.
    def _sort_key(r):
        gr = r.get("goal_relevance") or {}
        gnr = r.get("genre_relevance") or {}
        return (
            _tier_order.get(r["signal_strength"], 9),
            gr.get("priority", 999),
            gnr.get("priority", 999),
            r["frame_id"],
        )
    absent_records.sort(key=_sort_key)

    # Contract §4.3 envelope
    if domain_hint is None:
        domain_inferred = "unfiltered"
    else:
        # v1 implementation: pass-through hint; actual FVS-metadata-based
        # filtering is flagged as a limitation and deferred.
        domain_inferred = domain_hint

    limitations: list[str] = [
        "V4.2 caller-side composition: absence_basis fields are "
        "scaffolding for the caller's agent model. Caller's model "
        "determines the final absence verdict per "
        "FRAME_DIVERGENCE_CONTRACT_v1 §7.1.",
    ]
    if domain_hint is not None:
        limitations.append(
            "Domain filter not yet wired to FVS entry metadata; "
            "all absent frames returned and envelope.domain_inferred "
            "echoes the hint without field-level filtering. Future "
            "contract minor version will add applicability metadata "
            "per FVS entry."
        )

    # Substrate-side composition: cluster absent frames by shared
    # canonical dimension. Where the agent previously had to discover
    # patterns across the absent_frames list, the substrate surfaces
    # the dimension-level theme directly. Stays deterministic; canon-
    # graph set membership only.
    absence_clusters = _build_absence_clusters(
        absent_records,
        document_word_count=document_word_count,
        matched_frame_count=len(frame_library_matches or []),
        document_claim_count=document_claim_count,
    )

    # Substrate-side composition Item 4: named structural patterns
    # over present-frame + absent-frame + genre combinations, with
    # corpus prevalence as empirical anchoring. Where clusters
    # surface dimension-level themes over absences alone, patterns
    # surface RECOGNIZED structural shapes that the substrate names
    # as load-bearing (e.g., "recommendation-without-falsification",
    # "growth-without-risk"). Stays deterministic.
    from frame_patterns import match_patterns as _match_patterns
    matched_ids_set = {
        m.get("fvs_id") for m in (frame_library_matches or [])
        if isinstance(m, dict) and m.get("fvs_id")
    }
    absent_ids_set = {r["frame_id"] for r in absent_records}
    # doc_signals are passed through so pattern triggers can use
    # frame_deepening + epistemic discriminators beyond raw FVS
    # membership. Without these, patterns fire on most documents in
    # their target genre and lose discriminating value (a label
    # rather than a pattern). With them, patterns require document-
    # content evidence confirming the structural shape.
    # Forward all keys from document_signals so new pattern
    # discriminators (projection_phrase_count, voice_label,
    # hedge_ratio) are visible to the matcher. Dropping any key
    # silently degrades patterns that depend on it to FVS-only.
    doc_signals = dict(document_signals or {})
    triggered_patterns = _match_patterns(
        matched_ids_set, absent_ids_set, document_genre,
        doc_signals=doc_signals,
    )
    # For each triggered pattern, attach corpus_context with the
    # prevalence count over the validation corpus's frame-shape
    # match (genre constraint not applied to corpus matching at
    # this contract version; documented in count_corpus_pattern_
    # matches docstring). Also attach claim_level for the per-level
    # construct treatment: each pattern is a composed_pattern
    # (deterministic trigger over present + absent frames + doc
    # signals; curator-authored reading inside).
    for p in triggered_patterns:
        p["claim_level"] = _CLAIM_LEVEL_COMPOSED
        # Reconstruct the trigger from the pattern definition for
        # the corpus prevalence call. We have the pattern's
        # supporting_evidence but the original trigger is in
        # frame_patterns._PATTERNS; re-derive by looking up the id.
        from frame_patterns import _PATTERNS as _ALL_PATTERNS
        trigger = next(
            (pat["trigger"] for pat in _ALL_PATTERNS
             if pat["id"] == p["id"]),
            None,
        )
        if trigger is None:
            p["corpus_context"] = None
            continue
        from corpus_intelligence import (
            count_corpus_pattern_matches as _count_pattern,
        )
        corpus_match = _count_pattern(
            trigger, _CORPUS_ENTRIES_DIR, _AGGREGATE_RESULTS_DIR,
        )
        if corpus_match is None:
            p["corpus_context"] = None
        else:
            n = corpus_match["matches"]
            tot = corpus_match["total"]
            tg = corpus_match.get("trigger_genre")
            n_in_genre = corpus_match.get("matches_in_genre")
            genre_tot = corpus_match.get("genre_total")
            ctx = {
                "prevalence": (
                    f"matches the frame-shape trigger of this "
                    f"pattern in {n} of {tot} corpus documents"
                ),
                "matches_count": n,
                "total_corpus": tot,
                "match_rate": corpus_match["match_rate"],
            }
            if tg and n_in_genre is not None and genre_tot:
                # Segmented prevalence (Item E): the more
                # statistically meaningful denominator. Only emit
                # when genre_total > 0 to avoid divide-by-zero noise.
                ctx["genre_segmented_prevalence"] = (
                    f"matches in {n_in_genre} of {genre_tot} "
                    f"corpus {tg}-genre documents"
                )
                ctx["matches_in_genre_count"] = n_in_genre
                ctx["genre_total"] = genre_tot
                ctx["genre_match_rate"] = corpus_match[
                    "genre_match_rate"
                ]
                ctx["trigger_genre"] = tg
                ctx["low_n_warning"] = corpus_match.get(
                    "genre_segmented_low_n_warning", False
                )
                if ctx["low_n_warning"]:
                    ctx["small_n_caveat"] = (
                        f"The trigger genre is '{tg}' but the "
                        f"corpus has only {genre_tot} document"
                        f"{'s' if genre_tot != 1 else ''} in that "
                        f"genre (low_n_warning=true). The segmented "
                        f"rate is not statistically meaningful at "
                        f"this denominator; cite as a corpus "
                        f"observation, not a population estimate. "
                        f"Full-corpus prevalence is included for "
                        f"reference but mixes genres."
                    )
                else:
                    ctx["small_n_caveat"] = (
                        f"The trigger genre is '{tg}'; segmented "
                        f"prevalence (matches_in_genre_count of "
                        f"genre_total) is the like-vs-like "
                        f"comparison and the more meaningful "
                        f"denominator. Full-corpus prevalence is "
                        f"included for reference. Both numbers are "
                        f"small-N; treat as corpus signals not "
                        f"population estimates."
                    )
            else:
                ctx["small_n_caveat"] = (
                    "Frame-shape match across the full corpus. "
                    "Pattern has no genre constraint, so segmented "
                    "prevalence is not applicable. Treat as small-N "
                    "corpus signal, not a population estimate."
                )
            p["corpus_context"] = ctx

    n_absent = len(absent_records)
    n_clusters = len(absence_clusters)
    catalog_size = len(library)
    if n_clusters > 0:
        cluster_dims = ", ".join(c["dimension"] for c in absence_clusters)
        cluster_phrase = (
            f" Substrate composes {n_clusters} absence cluster"
            f"{'s' if n_clusters != 1 else ''} on the {cluster_dims} "
            f"dimension{'s' if n_clusters != 1 else ''} (see "
            f"divergence.absence_clusters); each cluster names a "
            f"shared theme across multiple absent frames and is the "
            f"recommended composition starting point."
        )
    else:
        cluster_phrase = (
            f" No absence cluster met the minimum threshold "
            f"({_CLUSTER_MIN_ABSENT} or more absent frames sharing a "
            f"canonical dimension at >="
            f"{int(_CLUSTER_MIN_CANON_FRACTION * 100)} percent canon "
            f"coverage); the substrate did not compose a "
            f"dimension-level theme for this document."
        )
    # Genre-relative ranking phrase (Item 3). When the document is
    # classified into a genre, name how many absent_frames carry
    # genre_relevance; the sort already promotes those entries
    # within their tier.
    n_genre_relevant = sum(
        1 for r in absent_records if r.get("genre_relevance")
    )
    if document_genre and n_genre_relevant > 0:
        plural = n_genre_relevant != 1
        genre_phrase = (
            f" Document genre is '{document_genre}'; "
            f"{n_genre_relevant} absent frame{'s' if plural else ''} "
            f"{'carry' if plural else 'carries'} genre_relevance "
            f"(load-bearing for this genre's reasoning per the "
            f"curated per-genre map) and "
            f"{'are' if plural else 'is'} promoted within "
            f"{'their' if plural else 'its'} tier in the sort."
        )
    else:
        genre_phrase = ""
    n_goal_relevant = sum(
        1 for r in absent_records if r.get("goal_relevance")
    )
    if user_goal and user_goal != "audit" and n_goal_relevant > 0:
        plural_g = n_goal_relevant != 1
        goal_phrase = (
            f" User goal is '{user_goal}'; "
            f"{n_goal_relevant} absent frame"
            f"{'s' if plural_g else ''} "
            f"{'carry' if plural_g else 'carries'} goal_relevance "
            f"and {'are' if plural_g else 'is'} promoted within "
            f"{'their' if plural_g else 'its'} tier in the sort "
            f"(goal precedes genre in the within-tier ranking)."
        )
    elif user_goal == "audit":
        goal_phrase = (
            " User goal is 'audit'; the substrate applies the "
            "default catalog/coverage/genre ranking with no "
            "goal-specific override (audit is sovereignty posture: "
            "see the frame the document chose)."
        )
    else:
        goal_phrase = ""
    n_patterns = len(triggered_patterns)
    if n_patterns > 0:
        pattern_names = ", ".join(
            f"'{p['name']}'" for p in triggered_patterns
        )
        pattern_phrase = (
            f" Substrate matches {n_patterns} named structural "
            f"pattern{'s' if n_patterns != 1 else ''} on this "
            f"document: {pattern_names} (see "
            f"divergence.frame_patterns). Each pattern is a "
            f"recognized substrate composition over present and "
            f"absent frames; the curated reading is the substrate's "
            f"reading."
        )
    else:
        pattern_phrase = ""
    divergence_summary = (
        f"Catalog-driven perspective absence with faithfulness "
        f"constraints. {n_absent} of {catalog_size} catalog frames "
        f"not detected by V1 rule-based detection: "
        f"{tier_counts['high']} high-signal "
        f"({tier_counts['medium']} medium, "
        f"{tier_counts['low']} low). Records are sorted by "
        f"signal_strength so callers can take the first N and get "
        f"the highest-leverage absences.{cluster_phrase}{genre_phrase}{goal_phrase}{pattern_phrase} The reader's "
        f"model composes the perspective-widening interpretation per "
        f"agent_guidance.how_to_render_divergence; this block is the "
        f"substrate, not the verdict."
    )

    # Whole-corpus summary for envelope-level provenance. Carries
    # the small-N caveat so any prevalence statement on a per-frame
    # or per-dimension corpus_context lands honestly. None when
    # corpus is unavailable; envelope still emits, just without
    # the corpus_summary key (caller-side serializer drops Nones).
    corpus_summary = _corpus_summary_or_none()

    envelope = {
        "spec_version": _SPEC_VERSION,
        "catalog_version": catalog_version,
        "surface": "mcp",
        "divergence_summary": divergence_summary,
        "corpus_summary": corpus_summary,
        "v4_2_execution": {
            "location": "caller_side",
            "tier": "caller_model",
            "note": (
                "V4.2 judge step delegated to caller's agent model per "
                "Rec I. Frame Check's MCP server does not invoke an "
                "external LLM. See agent_guidance.how_to_render_divergence "
                "for composition instructions."
            ),
        },
        "v4_2_engine_status": engine_status,
        "v4_2_engine_status_reference": (
            "V4_2_GAP_INVENTORY_v1.md §5 for full status "
            "disclosure and remaining Tier 2-4 gaps."
        ),
        "domain_inferred": domain_inferred,
        "provisional_count": provisional_count,
        "tier_counts": dict(tier_counts),
        "faithfulness_note": (
            "Absent frames are named from the FVS catalog as not "
            "detected in the supplied document. Domain relevance is "
            "the tool's best judgment. Whether any absent frame is "
            "useful is the thinker's call. This is not a list of "
            "frames that should have been used."
        ),
        "limitations": limitations,
    }

    # Item 12: opt-in LLM-augmented frame-opportunity composition.
    # When include_frame_opportunities=True, generate document-
    # specific questions for the top absent frames using the
    # absent frame's teaching question + document content + genre +
    # goal as the LLM prompt. Substrate-deterministic discipline:
    # each opportunity carries is_deterministic=False; total cost
    # is tracked; LLM unavailability degrades gracefully (empty
    # opportunities list with available=False).
    frame_opportunities_block: dict = {
        "opportunities": [],
        "total_cost_usd": 0.0,
        "available": None,
        "note": (
            "Frame-opportunity composition is opt-in via "
            "include_frame_opportunities=true. The deterministic "
            "substrate (clusters, patterns, absences with goal and "
            "genre relevance) provides the same insights without "
            "LLM cost when this flag is omitted. See "
            "agent_guidance.frame_opportunities_discipline for the "
            "evidence discipline that applies when "
            "opportunities are surfaced."
        ),
    }
    if include_frame_opportunities and document_text_for_opportunities:
        # Pre-populate teaching_question on the top N candidates,
        # regardless of rendering mode, so the LLM prompt has the
        # frame's curated teaching question as context. Source of
        # truth is frame_library.TEACHING_QUESTIONS (mirrors the
        # questions the firing rules emit; available for absent
        # frames that never fire).
        from frame_library import (
            get_teaching_question as _get_tq,
        )
        from frame_opportunities import (
            generate_frame_opportunities as _generate_opps,
        )
        candidates = []
        for record in absent_records[:3]:
            tq = record.get("teaching_question") or _get_tq(
                record["frame_id"]
            )
            enriched = dict(record)
            if tq:
                enriched["teaching_question"] = tq
            candidates.append(enriched)
        # Item C: pass substrate-level composition (cluster readings,
        # pattern readings) into the LLM prompt so the generated
        # questions consume the substrate's own composition rather
        # than treating absent frames in isolation.
        cluster_readings = [
            c.get("reading") for c in absence_clusters
            if c.get("reading")
        ]
        pattern_readings = [
            p.get("reading") for p in triggered_patterns
            if p.get("reading")
        ]
        result = _generate_opps(
            candidates,
            document_text_for_opportunities,
            document_genre=document_genre,
            user_goal=user_goal,
            cluster_readings=cluster_readings,
            pattern_readings=pattern_readings,
        )
        frame_opportunities_block.update({
            "opportunities": result["opportunities"],
            "total_cost_usd": result["total_cost_usd"],
            "available": result["available"],
        })
        if "unavailable_reason" in result:
            frame_opportunities_block["unavailable_reason"] = (
                result["unavailable_reason"]
            )

    # Apply compose_budget slicing (substrate-side composition L5
    # interface UX): bound the substrate's output volume so an agent
    # with a tight working-memory budget can request a compact reading
    # without losing structural shape. The envelope's tier_counts
    # remain PRE-slice (they reflect what the substrate found) so the
    # agent sees the truncation honestly rather than thinking the
    # substrate found fewer absences. The compose_budget_applied
    # field surfaces the slice level + per-layer truncation counts.
    #
    # Slice levels:
    #   minimal: top-3 absent_frames, top-1 cluster, top-1 pattern.
    #     agent_guidance compressed (downstream block). For agents in
    #     tight working-memory budgets (quick responses).
    #   standard: top-5 absent_frames, all clusters, all patterns.
    #     agent_guidance compressed (same compression as minimal).
    #     Middle ground; preserves full cluster + pattern surfaces
    #     while halving guidance token cost.
    #   full (default): unfiltered output, full inline guidance.
    #     Backwards-compatible with prior callers who omit the
    #     parameter; suitable for first-time orientation and
    #     methodology demos where worked examples earn their tokens.
    pre_slice_absent = len(absent_records)
    pre_slice_clusters = len(absence_clusters)
    pre_slice_patterns = len(triggered_patterns)
    if compose_budget == "minimal":
        absent_records = absent_records[:3]
        absence_clusters = absence_clusters[:1]
        triggered_patterns = triggered_patterns[:1]
    elif compose_budget == "standard":
        absent_records = absent_records[:5]
    # full: no slice

    compose_budget_applied = {
        "level": compose_budget,
        "absent_frames_returned": len(absent_records),
        "absent_frames_total": pre_slice_absent,
        "absence_clusters_returned": len(absence_clusters),
        "absence_clusters_total": pre_slice_clusters,
        "frame_patterns_returned": len(triggered_patterns),
        "frame_patterns_total": pre_slice_patterns,
        "note": (
            "compose_budget bounds output volume; envelope.tier_counts "
            "reflects PRE-slice counts. The agent should surface the "
            "truncation when relevant ('Frame Check identified N "
            "absences; showing top M')."
            if compose_budget != "full"
            else "compose_budget=full; no slicing applied."
        ),
    }

    divergence = {
        "absent_frames": absent_records,
        "absence_clusters": absence_clusters,
        "frame_patterns": triggered_patterns,
        "frame_opportunities": frame_opportunities_block,
        "envelope": envelope,
        "compose_budget_applied": compose_budget_applied,
    }

    # Contract §4.4: two required agent_guidance additions.
    agent_guidance_additions = {
        "how_to_render_divergence": (
            "To complete the divergence composition on the caller side: "
            "(1) START with divergence.absence_clusters when present. "
            "Each cluster groups absent frames sharing a canonical "
            "decision-readiness dimension (coverage, calibration, "
            "evidence, robustness, counterfactual) and carries a "
            "dimension-specific reading composed by the substrate. The "
            "cluster reading is Frame Check's composition over the "
            "divergence set; cite it as Frame Check's reading and use "
            "it as the lead synthesis ('the substrate reads the "
            "absences as concentrated on the X dimension because Y'). "
            "Then walk the supporting absent_frames entries that share "
            "the cluster's dimension. Clusters are prioritized over "
            "per-frame walks because they carry the dimension-level "
            "theme; the per-frame walk is supporting evidence. When "
            "absence_clusters is empty, fall back to per-frame "
            "composition over absent_frames. "
            "(2) For each entry in divergence.absent_frames, verify the "
            "absence_basis claim by inspecting the document with your "
            "own model's judgment. Records are sorted by signal_strength "
            "(high first); for most readers the high-tier entries are "
            "the load-bearing surface. "
            "(3) If you agree the frame is absent and reader-relevant, "
            "render it per the requested "
            f"divergence_rendering ('{rendering}'): 'list' = flat list "
            "with citations; 'completeness_check' = checklist with "
            "domain-relevance rationale; 'teaching_questions' = "
            "per-frame teaching question (already attached to records "
            "when requested); 'narrative' = single prose paragraph "
            "naming absent frames with citations inline. "
            "(4) NEVER restate absent frames or clusters as 'missing "
            "frames you should consider' or equivalent prescriptive "
            "language (contract §4.5). Say 'not detected in the "
            "current framing' or 'absent from the document'. The "
            "cluster reading describes what the framing does not do; "
            "it never tells the user what the document should have "
            "done. "
            "(5) Cite each absent frame by frame_id and citation_uri. "
            "Cite cluster readings as 'Frame Check's substrate-"
            "composition of the divergence set on the X dimension'. "
            "(6) Catalog version note: "
            "the divergence catalog is library_v3 per "
            "FRAME_DIVERGENCE_CONTRACT_v1 c1.0 contract stability; the "
            "engine-current working library is library_v4, byte-"
            "equivalent on the ## Identification sections that drive "
            "divergence detection. The pin is intentional, not stale. "
            "(6.4) Goal-relative ranking (Item 11): when the user "
            "(or agent on behalf of the user) has signalled a goal "
            "via the user_goal parameter (decide / brainstorm / "
            "persuade / learn / audit), absent frames load-bearing "
            "for that goal carry a goal_relevance dict with "
            "priority and reason. The absent_frames sort puts "
            "goal-relevance ahead of genre-relevance within tier; "
            "the agent surfacing absences should cite "
            "goal_relevance.reason as the structural basis ('for "
            "the goal of deciding, FVS-009 absent is load-bearing "
            "because risk-frame absence at decision time leaves "
            "downside structurally invisible'). The 'audit' goal "
            "applies no override (sovereignty posture); "
            "goal_relevance is None on every absent_frame. When "
            "user_goal is omitted, behavior matches 'audit'. "
            "(6.5) Genre-relative ranking (Item 3): when the "
            "document is classified into a structural genre "
            "(analysis.genre.classification), absent frames that "
            "are load-bearing for that genre's reasoning carry a "
            "genre_relevance dict with priority and reason. The "
            "absent_frames sort promotes genre-relevant entries "
            "within their tier; the agent surfacing absences "
            "should cite genre_relevance.reason as the structural "
            "basis ('for recommendation genre, FVS-007 absent is "
            "load-bearing because recommendations without "
            "falsification conditions cannot be stress-tested'). "
            "Genre-relevance is curated per genre; reasons are "
            "reading-form not verdict-form. "
            "(6.7) Named structural patterns (Item 4): when "
            "divergence.frame_patterns is non-empty, the substrate "
            "has matched one or more recognized structural shapes "
            "(e.g., 'recommendation-without-falsification', "
            "'growth-without-risk'). Each pattern carries a curated "
            "reading composing present and absent frames into a "
            "named composition, plus corpus_context with prevalence "
            "(how often the same frame-shape appears in the "
            "validation corpus). Patterns are stronger evidence "
            "than per-frame walks because they name a recognized "
            "shape; lead with the pattern reading when present, "
            "before walking individual absent_frames or clusters. "
            "Cite the pattern's id and the frames in "
            "supporting_evidence inline. The same prescription-"
            "prevention discipline applies: pattern readings name "
            "what the framing does, never what the document should "
            "have done. "
            "(7) Corpus context layer: when "
            "envelope.corpus_summary is non-null, every frame and "
            "cluster carries an empirical context block. For matched "
            "and absent frames, corpus_context.prevalence reports "
            "firing rate across Frame Check's validation corpus "
            "(small N; honor the small_n_caveat). typical_co_fires "
            "and typical_co_absences name structural patterns the "
            "corpus has surfaced. corpus_entries_fired_uris point "
            "back to specific corpus entries; cite as 'in our "
            "validation corpus, X fires alongside Y at rate Z; see "
            "frame-check://corpus/{slug}'. For clusters, "
            "corpus_context.peer_pair_difference_rate is empirical "
            "evidence the dimension is consequential under peer "
            "comparison; cross_question_outlier names a specific "
            "model-by-dimension outlier finding from validation. "
            "Cite corpus context only when it sharpens the reading; "
            "small-N data should not become rhetorical scenery. "
            "(7.1) Genre-segmented prevalence discipline. Per-frame "
            "corpus_context.fires_in_by_genre carries one stat per "
            "genre bucket (recommendation, analysis, narrative, "
            "advocacy, exploration, instruction, plus _unclassified "
            "for documents the genre classifier abstained on). For "
            "each: fires_in_count, genre_total, rate, "
            "low_n_warning (true when genre_total < 3), and "
            "is_unclassified_bucket. Discipline: prefer the "
            "segmented denominator over the full-corpus rate when "
            "available; cite as 'fires in N of M Y-genre documents' "
            "rather than 'fires in N of total documents'. When "
            "low_n_warning=true on a genre, do NOT cite the rate "
            "as if statistically calibrated; the substrate is "
            "construct-honest about per-genre denominators. NEVER "
            "cite the _unclassified bucket as if it were a genre; "
            "it is documents whose structural shape couldn't be "
            "inferred. For frame_patterns, "
            "corpus_context.genre_segmented_prevalence is the "
            "like-vs-like rate; use it as the primary citation, "
            "with the full-corpus prevalence as reference."
        ),
        "absence_is_not_prescription": (
            "Divergence output never implies the user should have used "
            "the absent frames. The tool surfaces absence, the thinker "
            "decides relevance. A user explicitly asking 'what's "
            "missing?' may be answered descriptively (naming absences); "
            "the discipline forbids prescription (telling them they "
            "should have used X), not description."
        ),
    }

    if user_context_present:
        # The caller passed a user_context string in the frame_check
        # call args. The MCP does NOT echo the user_context value into
        # the response (privacy posture: caller-side context never
        # round-trips through the server); the caller's agent has
        # the value from its own call args. Extend
        # how_to_render_divergence to instruct the agent on contextual
        # filtering with the prescription-prevention guardrail.
        agent_guidance_additions["how_to_render_divergence"] += (
            "\n\nUser context was provided in the frame_check call (the "
            "caller's agent has it from the call args; the MCP does not "
            "echo the value back). Use that context to filter divergence "
            "relevance for the user's specific situation: surface "
            "absences that matter for the context first; deprioritize "
            "catalog-true but contextually irrelevant absences. "
            "Discipline: NEVER use the user_context to prescribe what "
            "the user should have used. The context personalizes "
            "RELEVANCE FILTERING; the absence_is_not_prescription "
            "guarantee extends to contextual surfacing. A user "
            "explicitly asking 'what is missing for my situation?' may "
            "be answered descriptively (naming context-relevant "
            "absences); the discipline forbids prescription, not "
            "context-aware description."
        )

    return {
        "divergence": divergence,
        "agent_guidance_additions": agent_guidance_additions,
    }


def _compress_agent_guidance_to_load_bearing(
    full_guidance: dict, level: str = "minimal",
) -> dict:
    """Compress agent_guidance to load-bearing prescriptions only.

    Used when compose_budget is "standard" or "minimal" to reduce
    per-call token cost for agents that invoke frame_check at high
    frequency (per-turn self-audit loops, batch document processing).
    Default compose_budget is "full" which preserves the complete
    agent_guidance; this function runs on explicit opt-in to either
    compressed tier.

    The compression is identical at the "standard" and "minimal" tiers;
    the two tiers differ in their divergence-side slicing (top-5 vs
    top-3 absent_frames; all clusters/patterns vs top-1). The `level`
    parameter only flows into compose_budget_applied_note so callers
    sizing token budgets can confirm which tier produced the cut.

    Compression rules:
      - composition_discipline: keep the discipline points as a
        compressed list, drop worked examples (the cite-by-name
        lesson, the per-level example trios). Worked examples teach
        the discipline at first read; once the agent has seen them
        in `full` mode, repeating on every call is dead weight.
      - how_to_cite_faithfully: condense to one sentence per rule
        (name Frame Check, no paraphrase, no "fails to address",
        no quality-score use).
      - when_invoked_on_own_output: keep (load-bearing for the self-
        audit case which is the most frequent per-turn invocation).
      - claim_level_treatments: replaced with a short note because
        the table is identical across calls; an agent can fetch it
        once via a compose_budget="full" call and cache for
        subsequent compose_budget="standard"/"minimal" calls.
        Surfaced as claim_level_treatments_note so the schema-shaped
        key survives and consumers parse around it.
      - what_this_tool_tells_you / what_this_tool_does_not_tell_you:
        replaced with a single inline pair of sentences. The full
        text is for first-time orientation, not per-call discipline.
      - how_to_map_user_intent: dropped. The agent has its own NLU;
        the guidance was for surface-level prompts and is not load-
        bearing for tight-loop callers.
      - how_to_cite_frame_matches / how_to_cite_claims: rolled into
        how_to_cite_faithfully.
      - dual_use_note: kept (anti-misuse is load-bearing).
      - scope_regime_guidance: passed through verbatim if present
        (it is verification-conditional and already concise).
      - frame_opportunities_discipline / how_to_render_divergence /
        any other divergence-merged keys: passed through verbatim
        because they govern dynamic blocks the caller asked for.

    Measured reduction on a representative document: agent_guidance
    drops from ~31 KB to ~12 KB (roughly 2.6x). The actual cut is
    reported in compose_budget_applied.note in the divergence
    envelope so a caller sizing token budget can confirm it.
    """
    compressed = {
        "composition_discipline": (
            "Compose ONE insight grounded in cited measurements, in "
            "reading-form ('the pattern reads as X'), never verdict-"
            "form ('the document is X'). Cite measurements as Frame "
            "Check's; the reading is the agent's. Do not walk the "
            "measurements one by one. Discipline: "
            "(1) every clause cites a measurement; "
            "(2) reading-form, never verdict-form; "
            "(3) confidence-gate (under 100 words, non-English, non-"
            "analytical structure) pivots the frame to a reading of "
            "Frame Check's scope, not a reading of the document; "
            "(4) cross-context compounding only when it sharpens the "
            "reading, never as scenery; "
            "(5) absence is not prescription (name what the framing "
            "does, never what the document should have done); "
            "(6) per-level claim treatment per the claim_level field "
            "on each entity; "
            "(7) when divergence.frame_patterns is non-empty, lead "
            "with the pattern reading and cite the pattern by its id "
            "verbatim; when frame_patterns is empty and "
            "divergence.absence_clusters is non-empty, lead with the "
            "cluster reading and cite by dimension name."
        ),
        "claim_level_treatments_note": (
            "Full per-level claim discipline is available inline at "
            "compose_budget='full' under "
            "agent_guidance.claim_level_treatments. The table is "
            "identical across calls; an agent can fetch once via a "
            "compose_budget='full' invocation and cache the result "
            "for subsequent compose_budget='standard'/'minimal' calls."
        ),
        "what_this_tool_tells_you": (
            "Structural framing of the document: coverage across five "
            "analytical perspectives, voice classification, temporal "
            "orientation, epistemic basis, named pattern matches from "
            "the Frame Vocabulary Standard, claim-density and hedge "
            "calibration, and (with source_text) source-fidelity."
        ),
        "what_this_tool_does_not_tell_you": (
            "Whether the document is correct, balanced, or rigorous. "
            "Whether the framing is appropriate for the user's goal. "
            "Verdicts, rankings, or pass/fail judgments. The "
            "construct-honest posture is structural-shape only."
        ),
        "how_to_cite_faithfully": (
            "Name Frame Check explicitly as the source of "
            "measurements. Do not paraphrase measurements as the "
            "agent's own reading. Do not restate 'missing' as 'fails "
            "to address' (the detector may have under-detected). Do "
            "not use coverage gaps, voice classifications, or FVS "
            "matches as a quality score, truthfulness verdict, or "
            "editing rule that suppresses minority framings. "
            "frame_library_matches: 'draft' entries cite as 'per the "
            "draft Frame Vocabulary Standard entry FVS-XXX'; 'canon' "
            "entries cite by id verbatim. claims block: cite COUNTS "
            "(detector-reported), never paraphrase individual claim "
            "sentences as if Frame Check surfaced them."
        ),
        "when_invoked_on_own_output": (
            "If document_text is the agent's own response (self-"
            "audit), do not evaluate correctness or claim balance, "
            "rigor, or caveats the measurements did not detect. "
            "Surface the structural frame, name FVS matches with "
            "their teaching_question, stop. Under 100 words: "
            "density-based detectors are noisy; name that limit."
        ),
        "dual_use_note": (
            "Frame Check expands the reader's view of one document; "
            "do not rank documents against each other. Surface the "
            "structural observation; the reader's judgment is the "
            "interpretive layer, not the agent's."
        ),
        "compose_budget_applied_note": (
            f"compose_budget={level}: agent_guidance compressed to "
            "load-bearing prescriptions only (Frame Check naming, "
            "reading-form discipline, dual-use note, self-audit rule, "
            "citation discipline). Worked examples in "
            "composition_discipline, the full claim_level_treatments "
            "table, and how_to_map_user_intent are dropped at this "
            "tier. Pass compose_budget='full' for the complete "
            "guidance inline."
        ),
    }

    # Preserve dynamic / context-conditional keys verbatim. These are
    # generated per-request, are concise, and govern blocks the caller
    # explicitly asked for (divergence rendering, opt-in opportunities,
    # verification-regime guidance). Compressing them would silently
    # change the caller's contract for those blocks.
    for key in (
        "scope_regime_guidance",
        "how_to_render_divergence",
        "frame_opportunities_discipline",
        "absence_is_not_prescription",
        # suggested_next_actions is per-call-derived from the call's
        # specific structural findings (highest-signal absent_frame,
        # claim hedge rate, sourced_pct). It is concise (4 entries
        # max) and is the load-bearing affordance for the user's
        # next move; compressing it would drop the discovery loop
        # into the rest of the product surface (the four MCP prompts,
        # the FVS catalog via library_url). The rendering instruction
        # passes through alongside so a compressed-tier caller still
        # knows how to surface the actions to the user.
        "suggested_next_actions",
        "how_to_render_suggested_next_actions",
    ):
        if key in full_guidance:
            compressed[key] = full_guidance[key]

    return compressed


def _extract_teaching_question(md_path: str) -> str | None:
    """Extract the first "Teaching question" line from an FVS entry
    markdown file. Returns None if the entry does not define one.
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    import re as _re
    m = _re.search(
        r'(?:^|\n)(?:\*\*)?Teaching question(?:\*\*)?[:\s]+(.+?)(?=\n\n|\n\*\*|\Z)',
        text, flags=_re.IGNORECASE | _re.DOTALL,
    )
    if not m:
        return None
    return m.group(1).strip()[:400]


def _build_suggested_next_actions(
    analysis: dict,
    divergence: dict | None,
) -> list[dict]:
    """Derive 2-4 specific next-action suggestions from this call's
    findings. Each action is structural-finding-anchored: it points
    at a concrete gap in the analysis and gives the user (via the
    agent) a concrete move that addresses it.

    The actions surface the rest of the product surface (the
    challenge_document MCP prompt, the FVS catalog via library_url)
    so an end-user reading a Frame Check result has a discoverable
    path forward, not just a static reading. Prior to this block
    being shipped, the tool surfaced findings without telling the
    user what to do about them; the discovery loop into the four
    MCP prompts and the 100+ resources was invisible.

    Each entry shape:
      kind            "reprompt" | "resource" | "prompt_followup"
      action_text     human-readable description; agent renders
                      verbatim or near-verbatim
      rationale       one sentence on why this action is suggested
                      for THIS specific call's findings (so the
                      reader can judge relevance)
      related_url     library_url for "resource" kind, optional
      related_fvs_id  FVS-ID for "resource" kind, optional

    Capped at 4 entries: more becomes noise. Ordering:
      1. Highest signal_strength absent_frame resource pointer
         (most actionable, most specific to the document)
      2-3. Up to two reprompt suggestions derived from claim/
         epistemic/coverage findings when the thresholds fire
      Last. Always-include prompt_followup pointing at
         challenge_document so the deeper multi-turn loop is
         discoverable on every call

    Deterministic: same input produces same output, same order.
    """
    actions: list[dict] = []

    # Rule 1: highest-signal absent_frame -> resource pointer.
    # absent_frames are sorted by signal_strength tier (high first)
    # then frame_id ascending; absent_frames[0] is the strongest
    # absence-shaped finding for this document.
    if divergence:
        absent_frames = divergence.get("absent_frames", []) or []
        if absent_frames:
            top = absent_frames[0]
            fvs_id = top.get("frame_id", "")
            title = top.get("frame_title", "")
            url = top.get("library_url")
            if fvs_id and title and url:
                actions.append({
                    "kind": "resource",
                    "action_text": (
                        f"Read the entry for the strongest absent frame "
                        f"in this reading: [{fvs_id} {title}]({url})."
                    ),
                    "rationale": (
                        f"{fvs_id} ({title}) is the highest signal_strength "
                        f"absent_frame in the divergence block; reading "
                        f"the catalog entry grounds the absence in the "
                        f"frame's identification cues and worked examples, "
                        f"not the agent's paraphrase."
                    ),
                    "related_fvs_id": fvs_id,
                    "related_url": url,
                })

    # Rule 2: high unhedged claim rate -> reprompt for hedging.
    # Threshold 0.5 picks documents where the majority of numeric
    # claims operate in the confidence register; below that the
    # signal does not justify a prompt for the user.
    claims = analysis.get("claims_extracted", {}) or {}
    total_claims = claims.get("total", 0) or 0
    unhedged_count = claims.get("unhedged_count", 0) or 0
    if total_claims >= 5 and unhedged_count / total_claims >= 0.5:
        unhedged_pct = round(100 * unhedged_count / total_claims)
        actions.append({
            "kind": "reprompt",
            "action_text": (
                "Ask the source AI: \"For each numeric claim in your "
                "analysis, what is the confidence interval, and where "
                "does the figure come from?\""
            ),
            "rationale": (
                f"{unhedged_count} of {total_claims} numeric claims "
                f"({unhedged_pct} percent) carry no hedging language. "
                f"A hedge-by-claim pass surfaces the uncertainty the "
                f"original draft did not name."
            ),
        })

    # Rule 3: very low sourced_pct -> reprompt for attribution.
    # Threshold 10 percent picks documents whose claims read as the
    # author's own knowledge rather than measurements someone made.
    epistemic = analysis.get("epistemic", {}) or {}
    sourced_pct = epistemic.get("sourced_pct", 100)
    total_sentences = epistemic.get("total_sentences", 0) or 0
    if total_sentences >= 5 and sourced_pct < 10:
        actions.append({
            "kind": "reprompt",
            "action_text": (
                "Ask the source AI: \"For the claims in this analysis, "
                "what specific sources support each one? Cite per "
                "claim, not in a closing footnote.\""
            ),
            "rationale": (
                f"Only {sourced_pct} percent of sentences carry "
                f"detector-recognized attribution markers; the claims "
                f"read as facts the author knows rather than "
                f"measurements someone made."
            ),
        })

    # Always-include: prompt_followup pointing at the
    # challenge_document MCP prompt so the deeper multi-turn loop
    # is discoverable on every call. The user can invoke it by
    # asking the agent to "use the challenge_document prompt"; the
    # prompt derives adversarial questions traced to the structural
    # gaps in this reading.
    actions.append({
        "kind": "prompt_followup",
        "action_text": (
            "Use the `challenge_document` MCP prompt for an "
            "adversarial-questions readout traced directly to the "
            "structural gaps surfaced here."
        ),
        "rationale": (
            "challenge_document derives questions from the absent_frames "
            "and weakest dimensions in this reading; running it gives "
            "a structured list of follow-up questions the user can put "
            "back to the source AI."
        ),
    })

    # Cap at 4. Resource pointer (if present) wins position 1;
    # prompt_followup always wins last position; the middle is
    # filled with reprompt suggestions in derivation order.
    return actions[:4]


def build_epistemic_payload(
    document_text: str, source_text: str | None = None,
    *,
    include_divergence: bool = True,
    domain_hint: str | None = None,
    divergence_rendering: str = "list",
    catalog_version_pin: str | None = None,
    user_context: str | None = None,
    user_goal: str | None = None,
    include_frame_opportunities: bool = False,
    compose_budget: str = "full",
) -> dict:
    """Run Frame Check's deterministic analyzers on the document and
    return the full epistemic payload: analysis, agent_guidance,
    provenance.

    When source_text is provided, the payload also includes a
    verification block (Layer 4 source_fidelity + Layer 11
    grounding_decomposition with scope_assessment regime). The
    agent_guidance narrative adapts to the regime so a client agent
    is told WHICH signal to trust on number-dense sources.

    All measurements in the analysis block are reproducible. Calling
    this twice with the same inputs returns an identical payload
    except for analysis_latency_ms in provenance (wall-clock).
    """
    # Import lazily so server startup stays fast. Heavy modules pull
    # in numpy / regex machinery we do not want to load on handshake.
    # Version constants live in _build_provenance, not here: the
    # function uses the analyzers but not the version strings.
    from clarethium_measure import measure
    from claim_analysis import analyze_claims
    from framing import (
        detect_coverage,
        temporal_orientation,
        detect_voice,
        detect_epistemic_basis,
        framing_portrait,
        framing_headline,
    )
    from frame_library import suggest_frames

    t_start = time.perf_counter()

    ca = analyze_claims(document_text)
    # Request sentence-level attribution and candidate-miss surfacing
    # for the MCP v2 coverage payload. Enables per-dimension
    # sentence_matches (where markers fired) and candidate_sentences
    # (where primary detector may have under-detected on the dimension).
    # suggest_frames uses only legacy fields and is unaffected.
    cov = detect_coverage(
        document_text,
        include_attribution=True,
        include_candidates=True,
    )
    voice = detect_voice(document_text)
    # Request candidate-attribution surfacing to expose scholarly-style
    # attribution the primary _is_sourced pipeline misses (VISITOR_AUDIT
    # Failure 3; DETECTION_RULE_AUDIT §5.2). Additive; legacy fields
    # unchanged.
    epist = detect_epistemic_basis(document_text, include_candidates=True)
    temp = temporal_orientation(document_text)
    # Pass raw text to enable text-dependent rules (FVS-006). Rules
    # without text dependency are unaffected.
    frames = suggest_frames(cov, voice, temp, epist, text=document_text)

    # Populate library-info caches (status map, version) on first
    # use. See _ensure_caches docstring for rationale.
    _ensure_caches()

    # Verification layer (only runs when the caller supplied source_text).
    # measure() composes source_fidelity + grounding_decomposition + the
    # scope_assessment regime classification in a single pass. Skipped
    # when no source is provided so the deterministic-only promise in
    # provenance stays honest for the no-source case.
    profile_with_source = None
    if source_text and source_text.strip():
        profile_with_source = measure(document_text, source=source_text)

    # Portrait and headline synthesize the raw coverage/voice/temporal/
    # epistemic signals into a single readable narrative. An agent
    # surfacing the portrait verbatim carries Frame Check's measurement
    # shape forward; surfacing the raw category lists without the
    # portrait risks reducing to a score the tool does not emit.
    portrait = framing_portrait(cov, temp, voice, epist, ca)
    headline = framing_headline(cov, temp, voice, epist, ca)
    # Substrate-side composition Items 8 / 9 / 10: per-frame
    # deepening. Three deterministic regex-based detectors that
    # give the agent specific document-content evidence beyond
    # the FVS firing/absence signals.
    from frame_deepening import (
        detect_temporal_scope as _detect_temporal_scope,
        detect_stakeholder_map as _detect_stakeholder_map,
        detect_falsification_conditions as _detect_falsification,
    )
    temporal_scope_data = _detect_temporal_scope(document_text)
    stakeholder_map_data = _detect_stakeholder_map(document_text)
    falsification_data = _detect_falsification(document_text)
    # Substrate-side composition Item 2: structural genre
    # classification. Composes voice + claim distribution + text-
    # feature regexes into a bounded-set classification with
    # construct-honest confidence reporting (mirrors voice). The
    # foundational primitive for Item 3 (per-genre absence ranking)
    # and Item 4 (pattern composition with prevalence). Deterministic.
    from genre_classifier import classify_genre as _classify_genre
    genre_data = _classify_genre(document_text, voice=voice, claims=ca)

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    coverage_cats = cov.get("categories", {}) or {}

    analysis = {
        "document": {
            "word_count_estimate": len(document_text.split()),
            "char_count": len(document_text),
            "sentence_count": voice.get("total_sentences", 0),
        },
        "coverage": {
            "addressed": cov.get("covered", []),
            "missing": cov.get("missing", []),
            "addressed_count": cov.get("coverage_count", 0),
            "total_categories": cov.get("total_categories", 5),
            "per_category_density_per_1kw": {
                cat: coverage_cats.get(cat, {}).get("density_per_1kw", 0)
                for cat in coverage_cats
            },
            "caveat": (
                "Coverage is keyword-and-pattern based. The 'addressed' "
                "list names categories where the detector found its "
                "vocabulary; the 'missing' list names categories where "
                "it did not. Both directions carry measurement error: "
                "a category flagged as addressed may be covered "
                "substantively or only nominally, and a category flagged "
                "as missing may be discussed using vocabulary the "
                "detector does not recognize. Reader judgement is "
                "required to distinguish. Density per 1,000 words is a "
                "rough proxy: higher density correlates with substantive "
                "coverage but does not prove it. DEPRECATION NOTICE "
                "(Phase 2, 2026-04-21): coverage (v1) is deprecated. "
                "coverage_v2 is the forward contract; new integrations "
                "MUST read coverage_v2. The v1 block is retained during "
                "the compatibility window and will be removed in a future "
                "Phase 3 release. See MCP_CONTRACT_V2_PROPOSAL.md."
            ),
        },
        "coverage_v2": _build_coverage_v2(cov),
        "voice": {
            "classification": voice.get("voice"),
            "signals": {
                "first_person_plural_pct": voice.get("we_pct"),
                "second_person_pct": voice.get("you_pct"),
                "imperative_count": voice.get("imperative_count"),
                "speculative_pct": voice.get("spec_pct"),
            },
            "available_classes": [
                "promotional", "prescriptive", "analytical",
                "descriptive", "advisory",
            ],
            # Phase B classification-confidence construct. Parallels
            # the coverage_v2 construct block shape: data fields +
            # first-class construct sub-block with serialize guidance.
            # See framing.py::detect_voice and
            # MCP_CONTRACT_V2_PROPOSAL.md §12 (appended).
            "confidence": voice.get("confidence"),
            "margin_to_threshold": voice.get("margin_to_threshold"),
            "runner_up": voice.get("runner_up"),
            "runner_up_margin": voice.get("runner_up_margin"),
            "construct": _build_voice_construct(voice),
            # Per-level construct treatment (substrate-side composition
            # L5): voice is a 7-rule cascade classifier with margin-
            # aware confidence. Cite per
            # agent_guidance.claim_level_treatments[classifier_output];
            # honor the existing construct.how_to_serialize for the
            # voice-specific phrasing (e.g., the analytical-residual
            # caveat).
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        # Genre is a higher-order classification composed from voice
        # + claim distribution + text-feature regexes. Bounded set:
        # recommendation, analysis, narrative, advocacy, exploration,
        # instruction. Construct-honest classification-confidence
        # shape (mirrors voice). Substrate-side composition Item 2:
        # foundational primitive that Item 3 (per-genre absence
        # ranking) and Item 4 (pattern composition) build on.
        "genre": {
            "classification": genre_data.get("genre"),
            "confidence": genre_data.get("confidence"),
            "runner_up": genre_data.get("runner_up"),
            "runner_up_margin": genre_data.get("runner_up_margin"),
            "score_distribution": genre_data.get(
                "score_distribution", {}
            ),
            "available_classes": [
                "recommendation", "analysis", "narrative",
                "advocacy", "exploration", "instruction",
            ],
            "construct": genre_data.get("construct"),
            # Per-level construct treatment: genre is a deterministic
            # scoring classifier with feature-evidence gate (post-
            # 2026-04 fix). Cite per
            # agent_guidance.claim_level_treatments[classifier_output];
            # surface runner_up when confidence is borderline.
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        # Per-frame deepening: surgical additions to FVS-014
        # (temporal_scope), FVS-011 (stakeholder_map), and
        # FVS-007/009 (falsification_conditions). Items 8 / 9 / 10
        # of the substrate-side composition roadmap. Each sub-field
        # is None when the document is too short for the analysis
        # to be meaningful (under 100 words).
        "frame_deepening": {
            "temporal_scope": temporal_scope_data,
            "stakeholder_map": stakeholder_map_data,
            "falsification_conditions": falsification_data,
            # Per-level construct treatment (substrate-side
            # composition L5): each sub-field is a regex/feature
            # detector emitting structural document evidence
            # (years referenced, stakeholder roles, falsification
            # statements). The detector-measurement discipline
            # applies to the cited evidence inside each sub-field
            # (e.g. 'years_referenced: [2026, 2030]' is a
            # lower-bound claim about explicit year markers; the
            # document may carry temporal anchoring via vocabulary
            # the detector does not match). Cite per
            # agent_guidance.claim_level_treatments
            # [detector_measurement].
            "claim_level": _CLAIM_LEVEL_DETECTOR,
        },
        "temporal": {
            "dominant": temp.get("dominant"),
            "distribution_pct": {
                "past": temp.get("past_pct"),
                "present": temp.get("present_pct"),
                "future": temp.get("future_pct"),
            },
            # Phase B distribution-with-dominant construct. Exposes
            # dominant_margin (lead over runner-up tense) and balanced
            # flag so agents can distinguish genuine time-anchoring
            # from near-tied distributions.
            "dominant_margin": temp.get("dominant_margin"),
            "balanced": temp.get("balanced"),
            "construct": _build_temporal_construct(temp),
            # Per-level construct treatment: temporal is a
            # distribution classifier (past/present/future percentages
            # with dominant + balanced flag). Cite per
            # agent_guidance.claim_level_treatments[classifier_output];
            # honor the balanced flag (low-margin dominants must not
            # be restated as time-anchoring).
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        "epistemic": {
            "sourced_pct": epist.get("sourced_pct"),
            "sourced_sentences": epist.get("sourced"),
            "numeric_sentences": epist.get("numeric_sentences"),
            "unsupported_numeric": epist.get("unsupported_numeric"),
            "total_sentences": epist.get("total_sentences"),
            # Candidate-attribution surfacing extends the Fix A
            # under-detection construct from coverage (Phase A) to
            # the epistemic signal. Sentences where EPISTEMIC_CANDIDATE_
            # ATTRIBUTION fires but the primary _is_sourced pipeline
            # did not. Each carries an explicit caveat. See
            # framing.py::EPISTEMIC_CANDIDATE_ATTRIBUTION.
            "candidate_attribution_sentences": epist.get(
                "candidate_attribution_sentences", []
            ),
            "candidate_attribution_count": epist.get(
                "candidate_attribution_count", 0
            ),
            "note": (
                "sourced_pct is the share of sentences where the "
                "detector matched an attribution or external-reference "
                "pattern (e.g., 'according to X', 'X reported', named "
                "entity with reporting verb). Low values are common in "
                "essayistic writing; high values are typical of academic "
                "or regulatory text. This is a signal, not a quality "
                "judgement. Under-detection is a known failure mode: "
                "scholarly-style attribution ('observers raise', "
                "'analysts argue') and passive constructions may not "
                "fire the regex, so a low sourced_pct is a lower-bound "
                "claim about attribution-marker density, not an "
                "upper-bound claim about whether the document is "
                "attributed."
            ),
        },
        "claims_extracted": {
            "total": ca.get("total_claims", 0),
            # Bug fix 2026-04-20: previously the sum used c.get("hedged"),
            # but claim dicts from analyze_claims carry framing="hedged"
            # as a string, not a hedged boolean. The .get("hedged")
            # always returned None, so hedged_count was always 0 and
            # unhedged_count was always total_claims. The correct values
            # live at the top of analyze_claims' return dict, already
            # computed from the framing classifier.
            "hedged_count": ca.get("hedged_count", 0),
            "unhedged_count": ca.get("unhedged_count", 0),
            "prediction_count": ca.get("prediction_count", 0),
            "by_type": ca.get("claims_by_type", {}),
            # Candidate-hedge surfacing extends the Fix A under-detection
            # construct from coverage (Phase A) and epistemic (Phase A-
            # extended) to the claims signal, completing the same-class-
            # signal trilogy. Each sample carries an explicit caveat.
            # See claim_analysis.py::CANDIDATE_HEDGE_RE.
            "candidate_hedge_count": ca.get("candidate_hedge_count", 0),
            "candidate_hedge_samples": [
                {
                    "sentence_preview": (
                        c["sentence"][:120]
                        + ("..." if len(c["sentence"]) > 120 else "")
                    ),
                    "candidate_hedge_marker": c.get("candidate_hedge_marker"),
                    "caveat": c.get("candidate_hedge_caveat"),
                }
                for c in ca.get("claims", [])
                if c.get("candidate_hedge_marker") is not None
            ][:10],
        },
        "portrait": portrait,
        "headline": headline,
        "frame_library_matches": [
            {
                "fvs_id": f.get("fvs_id"),
                "name": f.get("name"),
                # GitHub URL pointing at the entry's markdown source
                # on the public repository (lluvr/frame-check-mcp).
                # End-users can click this to read the entry directly;
                # GitHub is always resolvable regardless of hosted-
                # production status (frame.clarethium.com is paused
                # 2026-04-23, so the previous-form library_url
                # pointing at the corpus site has been retired).
                # None when no canonical filename is known for the ID.
                "library_url": (
                    _library_entry_ref(f.get("fvs_id", "")).get("public_url")
                    if f.get("fvs_id") else None
                ),
                # MCP resource URI for the same library entry.
                # Agents running entirely through MCP (no web
                # access) can chain this tool response into
                # resources/read on the matching FVS entry directly,
                # without having to construct the URI themselves.
                "library_resource_uri": (
                    f"{RESOURCE_SCHEME}://library/{f.get('fvs_id')}"
                    if f.get("fvs_id") else None
                ),
                # Per-entry version pinned from the entry's
                # **Version:** meta line. Cites this match against
                # a specific version of the entry, not the library-
                # wide version in provenance. None when the entry
                # predates per-entry versioning.
                "library_entry_version": (
                    (_FRAME_VERSIONS or {}).get(f.get("fvs_id", ""))
                ),
                "teaching_question": f.get("question"),
                "definition": f.get("definition"),
                "signal": f.get("signal"),
                # Stability status from INDEX.md. 'draft' means ID is
                # stable but name/identification may revise; 'canon'
                # means full stability. Agents surfacing this match to
                # a user should communicate the status.
                "status": _FRAME_STATUSES.get(f.get("fvs_id", ""), "draft"),
                # Related FVS entries the curator named as adjacent
                # to this one. Each carries its MCP resource URI so
                # an agent can pull the adjacent entry in one
                # resources/read call. Order follows the source
                # file's Adjacent-frames line. Empty list when the
                # entry declares no adjacents or references only
                # non-FVS vocabularies.
                "adjacent_frames": [
                    _library_entry_ref(adj_id)
                    for adj_id in (_FRAME_ADJACENCY or {}).get(
                        f.get("fvs_id", ""), []
                    )
                ],
                # affects_dimensions: which decision-readiness
                # dimensions this matched frame is canon for.
                # Lets an agent surfacing the match name the
                # downstream impact ("FVS-001 detected; affects
                # Coverage and Counterfactual on the
                # decision-readiness profile") without needing
                # to consult DIMENSION_LIBRARY_ENTRIES separately.
                # Empty list for meta-side entries (FVS-002,
                # FVS-005, FVS-006, FVS-013, FVS-020) that do
                # not map to a specific dimension; honest empty.
                "affects_dimensions": _dimensions_affecting(
                    f.get("fvs_id", "")
                ),
                # corpus_context: empirical anchoring from Frame
                # Check's validation corpus. Carries this frame's
                # firing prevalence, typical co-fires and co-
                # absences, and corpus_resource_uris pointing at
                # corpus entries where this frame fires. The
                # substrate stays deterministic (read-only
                # aggregation over corpus profile.json files).
                # None when the corpus is unavailable.
                "corpus_context": _frame_corpus_context_or_none(
                    f.get("fvs_id", "")
                ),
                # Per-level construct treatment (substrate-side
                # composition L5): a frame_library_matches entry is
                # a V1 detector firing on the document. Cite per
                # agent_guidance.claim_level_treatments
                # [detector_measurement]. The detector uses
                # vocabulary-and-pattern matching; under-detection
                # construct applies (firing is a lower-bound
                # vocabulary claim, not an upper-bound document
                # claim).
                "claim_level": _CLAIM_LEVEL_DETECTOR,
            }
            for f in frames or []
        ],
    }

    # Verification block. Present only when source_text was supplied.
    # Keeps the schema stable: clients that never pass a source get the
    # analysis-only shape; clients that pass a source get the full
    # epistemic picture including the Monte-Carlo-verified scope regime.
    if profile_with_source is not None:
        sf = profile_with_source.get("source_fidelity", {}) or {}
        gd = profile_with_source.get("grounding_decomposition", {}) or {}
        scope = gd.get("scope_assessment", {}) or {}
        analysis["verification"] = {
            "source_fidelity": {
                "total_numbers": sf.get("total_numbers", 0),
                "in_source": sf.get("in_source", 0),
                "not_in_source": sf.get("not_in_source", 0),
                "unsourced_rate": sf.get("unsourced_rate", 0.0),
                "note": (
                    "Digit-level match. A number 'in_source' appears as "
                    "an exact digit substring in the source text. "
                    "'not_in_source' does not; those claims may be "
                    "derived, rounded, or fabricated."
                ),
            },
            "grounding_decomposition": {
                "proportions": gd.get("proportions"),
                "has_projection": gd.get("has_projection"),
                "recommendation": gd.get("recommendation"),
                "status": gd.get("status"),
                "scope_assessment": {
                    "source_num_count": scope.get("source_num_count"),
                    "derivation_regime": scope.get("derivation_regime"),
                    "cross_reference_layer_4_for_numbers": scope.get(
                        "cross_reference_layer_4_for_numbers",
                    ),
                    "note_user_facing": scope.get("note_user_facing"),
                },
            },
        }

    # Decision-readiness profile (Phase 1.5: experimental, validation
    # in progress per /corpus/decision-readiness/). Composes the
    # existing structural + claims + verification signals into the
    # five-dimension profile. Lead use case per the methodology page
    # is AI-response audit at the moment of conversation, which is
    # the MCP path; the profile MUST be reachable from MCP responses
    # for that positioning to be implemented, not just documented.
    #
    # Synthetic source_network when source_text was supplied: the
    # MCP context uses Layer 4 source_fidelity (digit-substring
    # presence) rather than the web flow's Source Network claim
    # verification. The mapping is approximate: 'in_source' is a
    # weaker positive signal than full claim verification, but it is
    # the only verification data available in the MCP context. The
    # decision_readiness output documents this in its evidence
    # dimension explanation.
    try:
        from decision_readiness import compute_decision_readiness as _cdr
        synth_source_network = {
            "checked": 0, "verified": 0, "contradicted": 0,
            "disputed": 0, "verified_providers": [],
        }
        if profile_with_source is not None:
            sf2 = profile_with_source.get("source_fidelity", {}) or {}
            synth_source_network = {
                "checked": int(sf2.get("total_numbers", 0)),
                "verified": int(sf2.get("in_source", 0)),
                "contradicted": 0,
                "disputed": 0,
                "verified_providers": [],
            }
        synth_display = {
            "framing": {
                "coverage": cov,
                "voice": voice,
                "temporal": temp,
                "epistemic": epist,
                "frame_suggestions": frames,
            },
            "claims": {
                "total_claims": ca.get("total_claims", 0),
                # Bug fix 2026-04-20: see build_epistemic_payload for the
                # parallel fix. Same root cause (framing string vs hedged
                # boolean). Using analyze_claims' pre-computed totals.
                "hedged_count": ca.get("hedged_count", 0),
                "unhedged_count": ca.get("unhedged_count", 0),
                "prediction_count": ca.get("prediction_count", 0),
            },
            "source_network": synth_source_network,
        }
        readiness = _cdr(synth_display)
        if readiness is not None:
            # Per-level construct treatment (substrate-side
            # composition L5): each per-dimension reading is a
            # substrate composition over multiple measurements
            # with a curated signal_text. Trigger conditions are
            # deterministic (multi-feature scoring per dimension);
            # signal_text is single-curator authored. Same shape
            # as absence_clusters and frame_patterns; mark each
            # dimension dict with claim_level=composed_pattern so
            # the agent honors the per-level discipline (cite
            # the trigger as deterministic AND the signal_text as
            # Frame Check's curator reading) rather than treating
            # the prose as a measurement.
            dims_block = readiness.get("dimensions") or {}
            for dim_name, dim_data in dims_block.items():
                if isinstance(dim_data, dict):
                    dim_data["claim_level"] = _CLAIM_LEVEL_COMPOSED
            analysis["decision_readiness"] = readiness
    except Exception as exc:
        # Decision-readiness must never break the MCP response. If
        # the composition raises (future signal change broke the
        # mapping), the rest of the analysis still ships and the
        # log records the failure for follow-up.
        log(
            f"decision_readiness composition raised "
            f"{type(exc).__name__}: {exc}"
        )

    what_this_tells_you = [
        "Structural framing patterns detected in the document",
        "Which of five analytical perspectives are keyword-present and which are absent",
        "Voice classification (promotional, prescriptive, analytical, descriptive, advisory)",
        "Temporal orientation (past, present, future distribution)",
        "Epistemic basis (share of sentences with external attribution)",
        "Named matches from the Frame Vocabulary Standard with teaching questions",
        "Adjacency hints for each matched frame (MCP URIs of related library entries, for in-session chaining)",
        "Extracted numeric claims with hedging status",
        "A synthesized portrait and headline describing what the document does to reader perception",
        "A decision-readiness profile across five dimensions (coverage, calibration, evidence, robustness, counterfactual) with explicit experimental status pending Phase 2 expert validation",
        "Structural genre classification (recommendation / analysis / narrative / advocacy / exploration / instruction) with construct-honest confidence",
        "Per-frame deepening: temporal_scope (years referenced + projection windows), stakeholder_map (regulators / investors / customers / employees / etc. mentioned vs absent), falsification_conditions (explicit 'would be wrong if' statements when present)",
        "Optional opt-in (include_frame_opportunities=true): LLM-augmented frame opportunities, document-specific questions composed from absent frame teaching questions + document content. Carries cost + non-determinism flag in provenance. Default: not surfaced (deterministic substrate works without LLM).",
    ]
    what_this_does_not_tell_you = [
        "Whether perspectives flagged as addressed are covered substantively or only nominally",
        "Whether perspectives flagged as missing are truly absent, or discussed using vocabulary the detector does not recognize (under-detection is a known failure mode)",
        "Reasoning quality, logical validity, or causal inference errors",
        "Human-perceived quality; structural measurements are roughly orthogonal (r approx 0.1) to reader-perceived quality",
        "Whether the document is persuasive, useful, or correct for the reader's purpose",
        "Whether hedge markers in claims activate the uncertainty coverage dimension. Coverage detection for the uncertainty dimension uses vocabulary markers (uncertain, unknown, contested, range, depends, varies) rather than hedge markers in claim positions (might, could, expected to, projected to). A document can carry a high hedge ratio (e.g., 21% of claims hedged) while uncertainty coverage shows zero markers; this is a detector boundary, not a contradiction. When you observe this disconnect, name it as a methodological observation about Frame Check's measurement layers rather than as a finding about the document.",
    ]

    if profile_with_source is None:
        what_this_does_not_tell_you.append(
            "Whether the numeric claims are factually correct. Pass "
            "source_text to enable Layer 4 source_fidelity and Layer 11 "
            "grounding_decomposition."
        )
        regime_guidance = (
            "No source provided. The portrait and frame matches describe "
            "structure only. If the user needs a truth check, ask them "
            "for the source material and re-invoke with source_text."
        )
    else:
        scope = (
            profile_with_source.get("grounding_decomposition", {})
            .get("scope_assessment", {})
        )
        regime = scope.get("derivation_regime")
        if regime == "saturated":
            regime_guidance = (
                "Source is number-dense (scope_assessment.derivation_regime "
                "= 'saturated'). The Layer 11 sentence-level P-signal is "
                "effectively disabled here: fabricated numbers can pass via "
                "coincidental arithmetic match. For numerical claims, cite "
                "verification.source_fidelity.unsourced_rate (Layer 4), NOT "
                "verification.grounding_decomposition.has_projection."
            )
        elif regime == "transition":
            regime_guidance = (
                "Source is moderately number-dense (scope_assessment."
                "derivation_regime = 'transition'). Layer 11 is noisy; "
                "cross-reference Layer 4 source_fidelity for numerical "
                "claims."
            )
        elif regime == "diagnostic":
            regime_guidance = (
                "Source is not number-dense (scope_assessment."
                "derivation_regime = 'diagnostic'). Layer 11's primary "
                "P-signal is reliable; both layers can be cited."
            )
        else:
            regime_guidance = (
                "Verification ran; regime classification unavailable "
                "(likely pre-v1.5 profile). Prefer Layer 4 source_fidelity "
                "for numerical claims."
            )

    agent_guidance = {
        "composition_discipline": (
            "The measurements are Frame Check's; the reading is the "
            "agent's. Compose ONE insight that is a reading the user "
            "could not see by re-reading their own document, grounded "
            "in specific cited measurements (analysis.genre "
            "classification, analysis.frame_deepening sub-fields "
            "(temporal_scope / stakeholder_map / "
            "falsification_conditions), frame_library_matches "
            "entries, voice classification, divergence "
            "frame_patterns, absence_clusters, and absent_frames "
            "(with goal_relevance and genre_relevance fields when "
            "present), decision_readiness dimension readings, and "
            "any corpus_context fields where present). "
            "When divergence.frame_patterns is non-empty, the "
            "substrate has matched a recognized structural shape "
            "(e.g., 'recommendation-without-falsification'); the "
            "pattern reading is the strongest substrate composition "
            "available and should be the lead synthesis. CITE THE "
            "PATTERN BY ITS id verbatim, not paraphrased. Worked "
            "example: instead of 'the pick gets a one-sided "
            "defense pattern' (paraphrase, substrate invisible), "
            "write 'this matches Frame Check's "
            "recommendation-without-falsification pattern' "
            "(substrate identified, user can chain to definition). "
            "The substantive observation can follow the cite, but "
            "the cite must come first. When frame_patterns is "
            "empty and divergence.absence_clusters is non-empty, "
            "the cluster reading is Frame Check's substrate-side "
            "composition over multiple absent frames; cite it as Frame "
            "Check's reading and use it as the lead synthesis (the "
            "cluster names a dimension-level theme the per-frame walk "
            "cannot). CITE THE CLUSTER BY ITS dimension name "
            "verbatim. Worked example: instead of 'four high-"
            "signal absent frames cluster on the same blind spot' "
            "(paraphrase), write 'Frame Check identified the "
            "counterfactual cluster (FVS-007, FVS-009, FVS-014, "
            "FVS-017)' (substrate's dimension name + member "
            "frames). The dimension name is canon-graph anchored "
            "and lets the user trace the cluster to "
            "decision-readiness methodology. When corpus_context "
            "fields are attached to "
            "matched frames, absent frames, or clusters, treat the "
            "prevalence and co-pattern fields as empirical anchoring "
            "from Frame Check's validation corpus (small N; honor the "
            "small_n_caveat in envelope.corpus_summary when present). "
            "Cross-context compounding rule (4) applies: cite corpus "
            "context only when it sharpens the reading, never as "
            "scenery. Do NOT walk the measurements one by one; a "
            "measurement dump is not a reading. Discipline: "
            "(1) INSIGHT-GROUNDED. Every insight clause must cite a "
            "specific measurement. If you cannot cite, do not assert. "
            "(2) READING-FORM, NEVER VERDICT-FORM. 'The pattern reads "
            "as X' is a reading. 'The document is X' is a verdict. "
            "Frame Check does not verdict; do not verdict on its "
            "behalf. "
            "(3) CONFIDENCE-GATE PIVOTS THE FRAME. When an off-"
            "methodology signal fires (under 100 words / non-English "
            "/ non-analytical structure), pivot the insight from 'a "
            "reading of the document' to 'what this run reveals about "
            "Frame Check's scope'. The user still gets a reading; it "
            "is now about the tool's calibration, not the document's "
            "framing. "
            "(4) CROSS-CONTEXT COMPOUNDING ONLY WHEN IT ADDS. Cite the "
            "validation aggregate or prior measurements only when they "
            "sharpen the reading; never as scenery. "
            "(5) ABSENCE IS NOT PRESCRIPTION. Compose insights that "
            "name what the framing does, never what the document "
            "should have done. The reader decides what to do with the "
            "seeing; that is the sovereignty case this tool serves. "
            "(6) PER-LEVEL CLAIM TREATMENT. The substrate produces "
            "four qualitatively different kinds of claim, each with "
            "its own construct discipline: detector_measurement (a "
            "regex/feature firing or non-firing; lower-bound "
            "vocabulary claim, not upper-bound document claim); "
            "classifier_output (a deterministic cascade or scoring "
            "classifier with margin-aware confidence; surface "
            "runner_up when borderline; no IRR data); "
            "composed_pattern (a substrate-side composition with "
            "deterministic trigger and a curator-authored reading; "
            "trigger is reproducible, reading is single-author "
            "normative claim about what the trigger means; no IRR "
            "data on whether other readers compose the same pattern "
            "from the same triggers); agent_generated (opt-in LLM-"
            "composed content from Item 12 frame_opportunities; "
            "non-deterministic by design; each output carries "
            "model_provenance with provider, model, and cost; the "
            "absent frame's general teaching_question_general "
            "remains the stable catalog reference, the "
            "generated_question is one document-specific "
            "application). Every composed entity in this "
            "payload carries a claim_level field naming which "
            "treatment applies; agent_guidance.claim_level_treatments "
            "carries the per-level discipline keyed by claim_level "
            "value. When citing an entity, honor the treatment for "
            "its claim_level: detector measurements get the "
            "lower-bound vocabulary phrasing; classifier outputs "
            "surface confidence and runner-up with the no-IRR "
            "caveat; composed patterns cite the trigger as "
            "deterministic AND the reading as Frame Check's curator "
            "reading; agent_generated content surfaces the model "
            "provenance and cost AND is never presented as Frame "
            "Check's measurement. Worked examples (the same lesson the "
            "cite-by-name discipline shipped: abstract instructions "
            "do not change agent behavior, concrete contrasts do): "
            "for a detector_measurement entity, instead of 'the "
            "document covers risks' (verdict, ignores under-detection "
            "construct), write 'Frame Check's detector found markers "
            "for risks (vocabulary-and-pattern based; lower-bound "
            "claim about marker density)'; for a classifier_output "
            "entity, instead of 'the document is promotional' "
            "(verdict, drops confidence and runner-up), write 'Frame "
            "Check classified voice as promotional (high confidence; "
            "runner-up advisory)' OR for borderline cases 'classified "
            "as promotional, borderline; advisory nearly fired'; for "
            "a composed_pattern entity, instead of 'this is a "
            "recommendation without falsification' (verdict, treats "
            "the curator's reading as a measurement), write 'Frame "
            "Check identified the recommendation-without-"
            "falsification pattern (deterministic trigger over "
            "FVS-007 firing plus FVS-009 absence plus zero "
            "falsification statements); the substrate's reading: "
            "recommendations without falsification conditions cannot "
            "be stress-tested by the reader'. This per-level "
            "discipline replaces the prior uniform construct "
            "treatment that conflated the four epistemic claim "
            "levels under one composition rule set."
        ),
        "claim_level_treatments": _CLAIM_LEVEL_TREATMENTS,
        "what_this_tool_tells_you": what_this_tells_you,
        "what_this_tool_does_not_tell_you": what_this_does_not_tell_you,
        "how_to_cite_faithfully": (
            "When passing this analysis to the user, name Frame Check "
            "explicitly as the source of the measurements. For example: "
            "\"Frame Check's structural analysis found markers for 3 of "
            "5 analytical perspectives and classified the voice as "
            "promotional.\" Do not paraphrase these measurements as "
            "your own reading of the document, and do not restate "
            "'missing' as 'the document fails to address' (the detector "
            "may have missed vocabulary it does not recognize). The "
            "measurements are deterministic and reproducible; "
            "paraphrasing breaks that reproducibility and strips the "
            "provenance the reader needs to evaluate the claim."
        ),
        "how_to_cite_frame_matches": (
            "Render every FVS reference as a clickable markdown link "
            "using the entry's library_url field: "
            "`[FVS-XXX Frame Title](library_url)`. The library_url "
            "points at the entry's markdown source on the public "
            "GitHub repository, which is always resolvable for the "
            "end-user. Plain-text 'FVS-XXX' references give the "
            "reader an identifier they cannot follow; the markdown "
            "link gives them the full identification text, worked "
            "examples, and adjacent-frames graph in one click. "
            "Apply this to frame_library_matches entries, to "
            "absent_frames entries inside the divergence block, and "
            "to typical_co_fires / typical_co_absences inside each "
            "absent_frames entry's corpus_context. Each carries the "
            "same library_url field. "
            "Stability discipline: each frame_library_matches entry "
            "carries a status field. 'canon' entries have stable "
            "ID, name, and identification. 'draft' entries have a "
            "stable ID but name or identification may revise. When "
            "surfacing a draft match, prefix the link with 'per the "
            "draft entry' so the stability guarantee is carried "
            "forward; canon matches need no prefix."
        ),
        "how_to_cite_claims": (
            "The claims block reports per-type COUNTS extracted from "
            "the document (total, hedged, unhedged, prediction, by "
            "numerical type). It does NOT report individual claim "
            "text. When restating, say 'Frame Check's claim extractor "
            "identified N numerical claims, M of which carried hedging "
            "language.' Do not synthesize or paraphrase individual "
            "claim sentences as if Frame Check surfaced them; the "
            "block is a distribution summary, not a quote list. "
            "candidate_hedge_samples carries up to 10 preview "
            "sentences for construct-honesty surfacing (hedges the "
            "primary detector did not recognize); these are clearly "
            "labeled as candidates and should be cited as such, not "
            "as verified hedges. Verification verdicts (if present) "
            "should be cited with the specific verifier and f1 tier "
            "as per how_to_cite_faithfully."
        ),
        "when_to_invoke_again": (
            "frame_check is deterministic for the same inputs. Calling "
            "it twice on identical (document_text, source_text) returns "
            "identical measurements. Re-invoke only if the text changed."
        ),
        "how_to_map_user_intent": (
            "When the user invokes Frame Check via natural language "
            "(not by typing prompt arguments directly), translate "
            "their intent to the option space the four sovereignty "
            "prompts expose (depth, goal, questions). The user does "
            "NOT need to know what compose_budget or "
            "include_frame_opportunities are; those are MCP-layer "
            "names. The user types in their own vocabulary; you "
            "translate. Concrete mappings:\n"
            " - 'quick check' / 'TL;DR' / 'fast read' / 'just a "
            "summary' -> depth=quick (compact response).\n"
            " - 'careful audit' / 'deep dive' / 'thorough review' / "
            "(no qualifier) -> depth=thorough (default).\n"
            " - 'I'm trying to decide whether to' / 'should I' / "
            "'help me decide' / 'figure out if' -> goal=decide.\n"
            " - 'what am I missing' / 'what's not addressed' / "
            "'gaps in this' / 'check for blind spots' -> goal=audit "
            "(default; explicit naming is fine when the user asks for "
            "audit-shaped reading).\n"
            " - 'challenge this' / 'play devil's advocate' / "
            "'adversarial review' / 'questions to push back' -> "
            "goal=challenge (the response composes structural-"
            "weakness questions rather than a portrait).\n"
            " - 'help me explore options' / 'what perspectives am I "
            "missing' / 'broaden my thinking' -> goal=explore.\n"
            " - 'teach me about the framing' / 'walk me through' / "
            "'help me understand' -> goal=learn.\n"
            " - 'questions to think about' / 'help me question this' "
            "/ 'what should I ask' -> questions=yes (opt-in LLM-"
            "composed document-specific questions; the substrate's "
            "deterministic patterns + clusters work without this).\n"
            "\n"
            "Discipline: surface the chosen options briefly to the "
            "user before invoking ('I'll do a thorough decision-"
            "focused audit') so the user can adjust before the call "
            "lands. Never silently default to the maximal option "
            "set; that wastes the user's attention budget. When the "
            "user request is ambiguous about depth, default to "
            "thorough; ambiguous about goal, default to audit; "
            "ambiguous about questions, default to no (opportunities "
            "are opt-in for cost reasons; do not invoke them without "
            "user signal). When the user explicitly types prompt "
            "arguments, honor those values verbatim; do not override "
            "with your inference."
        ),
        "scope_regime_guidance": regime_guidance,
        "suggested_response_shape": (
            "Surface the portrait first (what kind of document this is), "
            "then name any frame_library_matches with their "
            "teaching_question so the reader has a question to ask of "
            "the document themselves. If verification is present, state "
            "the source_fidelity ratio verbatim and apply "
            "scope_regime_guidance. Close with the method's own limits "
            "from what_this_tool_does_not_tell_you so the reader knows "
            "where your response stops being grounded."
        ),
        "when_invoked_on_own_output": (
            "If document_text is your own last response to the user "
            "(the self-audit pattern surfaced by the "
            "frame_check_my_response prompt), the response shape "
            "changes. Do not evaluate whether you were correct. Do "
            "not claim balance, rigor, or caveats the measurements "
            "did not detect. Surface the structural frame you chose "
            "(coverage, voice, temporal, sourced_pct), name any FVS "
            "matches with their teaching_question, and stop. The "
            "user sees the frame you chose and decides what to do "
            "with the seeing; that is the sovereignty case this "
            "tool exists to serve. One bound: if your response is "
            "under about 100 words, the density-based detectors are "
            "noisy and category coverage flags should be treated as "
            "weak signal. Name that limit to the user rather than "
            "overstating what the measurements can tell them."
        ),
        "frame_opportunities_discipline": (
            "frame_opportunities is the opt-in LLM-augmented "
            "composition layer (Item 12 of the substrate-side "
            "composition roadmap). When the caller passes "
            "include_frame_opportunities=true, divergence."
            "frame_opportunities.opportunities carries 0-3 "
            "document-specific questions composed by the LLM from "
            "an absent frame's teaching question + the document's "
            "content + the user's goal. Discipline: "
            "(1) Each opportunity carries model_provenance with "
            "is_deterministic=false; cite this clearly when "
            "surfacing the question to the user. The deterministic "
            "substrate (clusters, patterns, absences) is "
            "reproducible across runs; opportunities are not. "
            "(2) Carry the cost. divergence.frame_opportunities."
            "total_cost_usd is the spend for this invocation; "
            "include it in audit trails. "
            "(3) Surface the generated_question alongside the "
            "frame's general teaching_question, not as a "
            "replacement. The general teaching question is the "
            "stable catalog reference; the generated question is "
            "the document-specific application. "
            "(4) Never present LLM-generated content as Frame "
            "Check's measurement. Frame Check's measurements are "
            "the deterministic substrate; opportunities are agent-"
            "side composition delegated to an LLM by Frame Check. "
            "(5) When opportunities is empty and available=false, "
            "the LLM was unavailable; surface this as graceful "
            "degradation (the deterministic substrate still works) "
            "and do not retry without explicit user request."
        ),
        "dual_use_note": (
            "Frame Check is designed to expand the reader's view of a "
            "document, not to rank documents against each other. Agent "
            "integrators who consume this payload should NOT use "
            "coverage gaps, voice classifications, or FVS matches as a "
            "quality score, a truthfulness verdict, or an editing rule "
            "that suppresses minority framings. The construct-honest "
            "posture (METHODOLOGY §1.3 and §1.3.1) surfaces what the "
            "detector measures and what it does not, precisely so that "
            "a downstream agent cannot reduce the measurements to a "
            "pass/fail judgment. If you find yourself producing prose "
            "like 'this document is biased' or 'this document lacks "
            "rigor' from Frame Check's output, you are using the tool "
            "outside its design scope. Surface the structural observation "
            "and the teaching question; the reader's judgment is the "
            "interpretive layer, not yours."
        ),
    }

    provenance = _build_provenance(
        analysis_layer=(
            "deterministic_structural_plus_verification"
            if profile_with_source is not None
            else "deterministic_structural_only"
        ),
        elapsed_ms=elapsed_ms,
    )

    # FRAME_DIVERGENCE_CONTRACT_v1 Part 2 integration. When
    # include_divergence=True: compute absent-frame records from the
    # library_v3 catalog minus the V1 frame_library_matches, build
    # the faithfulness envelope, and extend agent_guidance with the
    # two required divergence keys. MCP surface per Contract §7.1:
    # zero LLM invoked; caller's agent model completes the composition
    # using agent_guidance.how_to_render_divergence.
    payload: dict[str, object] = {
        "analysis": analysis,
        "agent_guidance": agent_guidance,
        "provenance": provenance,
    }
    if include_divergence:
        # Pass cov_missing so the divergence builder can compute
        # signal_strength tiers per absent frame; "coverage weakness"
        # is the document-side signal that distinguishes high-tier
        # absences (catalog-multi-dim AND coverage canon AND coverage
        # weak) from medium and low.
        cov_missing_for_signal = list(cov.get("missing", []) or [])
        # Item 3: pass the classified genre so absent_frames can
        # carry genre_relevance and the sort can promote load-bearing
        # absences for this document's genre.
        document_genre = (
            analysis.get("genre", {}) or {}
        ).get("classification")
        divergence_bundle = _build_divergence_block(
            frame_library_matches=analysis.get("frame_library_matches", []) or [],
            domain_hint=domain_hint,
            rendering=divergence_rendering,
            catalog_version_pin=catalog_version_pin,
            engine_status="beta",  # per V4_2_GAP_INVENTORY §5 after Tier 1 complete
            cov_missing=cov_missing_for_signal,
            user_context_present=bool(user_context),
            document_genre=document_genre,
            document_word_count=analysis.get(
                "document", {},
            ).get("word_count_estimate"),
            document_claim_count=analysis.get(
                "claims_extracted", {},
            ).get("total"),
            user_goal=user_goal,
            document_text_for_opportunities=document_text,
            include_frame_opportunities=include_frame_opportunities,
            document_signals=_build_document_signals(analysis),
            compose_budget=compose_budget,
        )
        payload["divergence"] = divergence_bundle["divergence"]
        # Merge the two required agent_guidance additions per §4.4.
        for key, value in divergence_bundle["agent_guidance_additions"].items():
            agent_guidance[key] = value

    # Suggested next actions: 2-4 specific moves the user can take
    # based on this call's findings. Surfaces the rest of the
    # product (challenge_document MCP prompt, FVS catalog via
    # library_url) so a Frame Check finding has a discoverable
    # path forward, not a static reading. Built AFTER divergence
    # because the highest-leverage action draws on the strongest
    # absent_frame, which only exists when include_divergence=True.
    # When divergence is off, the action list still includes the
    # findings-based reprompts and the always-present prompt
    # followup.
    agent_guidance["suggested_next_actions"] = (
        _build_suggested_next_actions(
            analysis,
            payload.get("divergence"),
        )
    )
    agent_guidance["how_to_render_suggested_next_actions"] = (
        "When composing the response, present "
        "suggested_next_actions as a small explicit list at the end "
        "of the reading (after the insight + question), introduced "
        "with one sentence like 'Things you can do next:'. Render "
        "the action_text verbatim or near-verbatim; do not paraphrase "
        "the rationale. The list is bounded (max 4 entries); render "
        "all entries the tool returned. Each 'resource' kind action "
        "already carries a clickable markdown link in its action_text "
        "(library_url-shaped); preserve the link form so the user "
        "can follow it. The 'reprompt' kind actions give the user a "
        "ready-made follow-up question for the source AI; render the "
        "quoted question verbatim. The 'prompt_followup' kind action "
        "names a Frame Check MCP prompt the user can ask you to "
        "invoke; surface it so the multi-turn loop is discoverable."
    )

    # compose_budget="standard" and "minimal" both compress
    # agent_guidance to load-bearing prescriptions only. The two tiers
    # differ in their divergence-side slicing (handled in the slicing
    # block above), not in the agent_guidance shape. Compression runs
    # AFTER the divergence merge so any divergence-specific keys
    # (how_to_render_divergence, frame_opportunities_discipline) are
    # preserved verbatim. compose_budget="full" keeps the rich
    # agent_guidance unchanged for first-time orientation, methodology
    # demos, or any case where the inline worked examples + claim-
    # level table earn their tokens. See
    # _compress_agent_guidance_to_load_bearing for compression rules.
    if compose_budget in ("standard", "minimal"):
        payload["agent_guidance"] = _compress_agent_guidance_to_load_bearing(
            agent_guidance, level=compose_budget,
        )
    return payload


# ── Compare payload builder ───────────────────────────────────────

def _per_document_core(text: str) -> dict:
    """Run the per-document deterministic analyzers and return the
    dict shape comparison.py's _build_structural_framing_data
    expects (coverage, voice, epistemic, temporal, claim_count,
    hedged/unhedged counts). Used by build_compare_payload; keeps
    the per-doc analysis call site in one place.
    """
    from claim_analysis import analyze_claims
    from framing import (
        detect_coverage,
        temporal_orientation,
        detect_voice,
        detect_epistemic_basis,
    )
    from frame_library import suggest_frames

    ca = analyze_claims(text)
    # Same attribution + candidate-miss treatment as the single-doc tool.
    cov = detect_coverage(
        text, include_attribution=True, include_candidates=True,
    )
    voice = detect_voice(text)
    epist = detect_epistemic_basis(text, include_candidates=True)
    temp = temporal_orientation(text)
    frames = suggest_frames(cov, voice, temp, epist, text=text)

    return {
        "coverage": cov,
        "voice": voice,
        "epistemic": epist,
        "temporal": temp,
        "claims_raw": ca,
        "frames": frames or [],
        # Keys _build_structural_framing_data reads directly:
        "claim_count": ca.get("total_claims", 0),
        # Bug fix 2026-04-20: claim dicts carry framing="hedged" string,
        # not a hedged boolean. Previous sum always returned 0 (hedged)
        # and total (unhedged). Using analyze_claims' top-level totals.
        "unhedged_count": ca.get("unhedged_count", 0),
        "hedged_count": ca.get("hedged_count", 0),
    }


def _summarize_per_document(doc: dict, text: str) -> dict:
    """Shape the per-document analysis for the compare payload.
    Smaller than the single-document frame_check payload because the
    point of compare is the cross-document signal; per-document
    detail is available by calling frame_check on each document
    individually.
    """
    cov = doc["coverage"]
    coverage_cats = cov.get("categories", {}) or {}
    return {
        "document": {
            "word_count_estimate": len(text.split()),
            "char_count": len(text),
            "sentence_count": doc["voice"].get("total_sentences", 0),
        },
        "coverage": {
            "addressed": cov.get("covered", []),
            "missing": cov.get("missing", []),
            "addressed_count": cov.get("coverage_count", 0),
            "total_categories": cov.get("total_categories", 5),
            "per_category_density_per_1kw": {
                cat: coverage_cats.get(cat, {}).get("density_per_1kw", 0)
                for cat in coverage_cats
            },
        },
        "coverage_v2": _build_coverage_v2(cov),
        "voice": {
            "classification": doc["voice"].get("voice"),
            "signals": {
                "first_person_plural_pct": doc["voice"].get("we_pct"),
                "second_person_pct": doc["voice"].get("you_pct"),
                "imperative_count": doc["voice"].get("imperative_count"),
            },
            # Phase B classification-confidence construct (see single-
            # doc endpoint for full construct commentary).
            "confidence": doc["voice"].get("confidence"),
            "margin_to_threshold": doc["voice"].get("margin_to_threshold"),
            "runner_up": doc["voice"].get("runner_up"),
            "runner_up_margin": doc["voice"].get("runner_up_margin"),
            "construct": _build_voice_construct(doc["voice"]),
            # Per-level construct treatment (substrate-side
            # composition L5): parity with the frame_check tool
            # response so a client can handle both surfaces
            # uniformly. See agent_guidance.claim_level_treatments
            # in the frame_check payload (same payload shape on
            # frame_compare's agent_guidance).
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        "temporal": {
            "dominant": doc["temporal"].get("dominant"),
            "distribution_pct": {
                "past": doc["temporal"].get("past_pct"),
                "present": doc["temporal"].get("present_pct"),
                "future": doc["temporal"].get("future_pct"),
            },
            # Phase B distribution-with-dominant construct.
            "dominant_margin": doc["temporal"].get("dominant_margin"),
            "balanced": doc["temporal"].get("balanced"),
            "construct": _build_temporal_construct(doc["temporal"]),
            # Per-level construct treatment: parity with frame_check.
            "claim_level": _CLAIM_LEVEL_CLASSIFIER,
        },
        "epistemic": {
            "sourced_pct": doc["epistemic"].get("sourced_pct"),
        },
        "claims_extracted": {
            "total": doc["claim_count"],
            "hedged_count": doc["hedged_count"],
            "unhedged_count": doc["unhedged_count"],
            "by_type": doc["claims_raw"].get("claims_by_type", {}),
        },
        "frame_library_matches": [
            {
                "fvs_id": f.get("fvs_id"),
                "name": f.get("name"),
                # GitHub URL pointing at the entry's markdown source
                # on the public repository (lluvr/frame-check-mcp).
                # See the frame_check tool's matching field for the
                # full rationale; same shape, same resolution
                # behavior, so a client can handle both surfaces
                # uniformly.
                "library_url": (
                    _library_entry_ref(f.get("fvs_id", "")).get("public_url")
                    if f.get("fvs_id") else None
                ),
                # MCP resource URI and per-entry version (same
                # fields as the frame_check tool response so a
                # client can handle both surfaces uniformly).
                "library_resource_uri": (
                    f"{RESOURCE_SCHEME}://library/{f.get('fvs_id')}"
                    if f.get("fvs_id") else None
                ),
                "library_entry_version": (
                    (_FRAME_VERSIONS or {}).get(f.get("fvs_id", ""))
                ),
                "teaching_question": f.get("question"),
                "status": (
                    (_FRAME_STATUSES or {}).get(f.get("fvs_id"))
                    if _FRAME_STATUSES is not None else None
                ),
                "adjacent_frames": [
                    _library_entry_ref(adj_id)
                    for adj_id in (_FRAME_ADJACENCY or {}).get(
                        f.get("fvs_id", ""), []
                    )
                ],
                # affects_dimensions: same field as in the
                # frame_check tool response so a client can
                # handle both surfaces uniformly. See the
                # frame_check construction for full rationale.
                "affects_dimensions": _dimensions_affecting(
                    f.get("fvs_id", "")
                ),
                # Per-level construct treatment (substrate-side
                # composition L5): parity with frame_check. Each
                # frame match is a V1 detector firing.
                "claim_level": _CLAIM_LEVEL_DETECTOR,
            }
            for f in doc["frames"]
        ],
    }


def build_compare_payload(
    doc_a_text: str, doc_b_text: str,
    a_name: str = "Document A", b_name: str = "Document B",
) -> dict:
    """Run Frame Check's structural comparison on two documents and
    return the three-section epistemic payload.

    The analysis section carries (a) per-document summaries and (b)
    the cross-document comparison: shared blind spots, unique blind
    spots, voice / temporal match flags, coverage and sourcing
    deltas, and the structural framing differences built from the
    same comparison.py._build_structural_framing_data that powers
    the /compare page. Zero LLM. Deterministic for identical inputs.

    The agent_guidance and provenance sections mirror frame_check
    so a client agent handling either tool can rely on the same
    integrity contract. The comparison-specific guidance names the
    interpretive pitfalls that are unique to the compare surface:
    agreement does not mean truth, divergence does not name which
    side is correct, the tool does not rank documents.
    """
    from comparison import _build_structural_framing_data

    _ensure_caches()

    t_start = time.perf_counter()

    a = _per_document_core(doc_a_text)
    b = _per_document_core(doc_b_text)

    missing_a = set(a["coverage"].get("missing", []))
    missing_b = set(b["coverage"].get("missing", []))
    shared_blind = sorted(missing_a & missing_b)
    only_a_blind = missing_a - missing_b
    only_b_blind = missing_b - missing_a

    framing_data = _build_structural_framing_data(
        a_name, a, b_name, b,
        shared_blind, only_a_blind, only_b_blind,
    )

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    analysis = {
        "documents": {
            a_name: _summarize_per_document(a, doc_a_text),
            b_name: _summarize_per_document(b, doc_b_text),
        },
        "comparison": {
            "coverage": {
                "shared_blind_spots": shared_blind,
                "only_a_misses": sorted(only_a_blind),
                "only_b_misses": sorted(only_b_blind),
                "addressed_count_delta": (
                    b["coverage"].get("coverage_count", 0)
                    - a["coverage"].get("coverage_count", 0)
                ),
            },
            "voice": {
                "match": (
                    a["voice"].get("voice") == b["voice"].get("voice")
                ),
                "a_classification": a["voice"].get("voice"),
                "b_classification": b["voice"].get("voice"),
                # Phase B cross-document classification-confidence
                # comparison. Both a and b are cascade-classified;
                # each carries a confidence label. Surfacing both
                # confidences lets the consumer distinguish "same
                # class, both decisive" (strong match) from "same
                # class, one borderline" (weaker match).
                "a_confidence": a["voice"].get("confidence"),
                "b_confidence": b["voice"].get("confidence"),
                "a_runner_up": a["voice"].get("runner_up"),
                "b_runner_up": b["voice"].get("runner_up"),
                "both_borderline": (
                    a["voice"].get("confidence") == "borderline"
                    and b["voice"].get("confidence") == "borderline"
                ),
                "construct_note": (
                    "Voice match/mismatch does not fully capture "
                    "classification agreement: two documents both "
                    "classified as the same class can differ in "
                    "confidence. Agents should surface a_confidence "
                    "and b_confidence when either is borderline."
                ),
            },
            "temporal": {
                "match": (
                    a["temporal"].get("dominant")
                    == b["temporal"].get("dominant")
                ),
                "a_dominant": a["temporal"].get("dominant"),
                "b_dominant": b["temporal"].get("dominant"),
                # Phase B cross-document distribution comparison.
                # dominant_margin + balanced exposed per side so the
                # consumer can distinguish "both past-dominant with
                # large margin" from "both past-dominant but a is
                # balanced" (different structural reads).
                "a_dominant_margin": a["temporal"].get("dominant_margin"),
                "b_dominant_margin": b["temporal"].get("dominant_margin"),
                "a_balanced": a["temporal"].get("balanced"),
                "b_balanced": b["temporal"].get("balanced"),
                "both_balanced": (
                    bool(a["temporal"].get("balanced"))
                    and bool(b["temporal"].get("balanced"))
                ),
                "construct_note": (
                    "Temporal match/mismatch on dominant tense does "
                    "not capture distribution shape. Agents should "
                    "surface a_balanced and b_balanced when either is "
                    "True, and the dominant_margin on both sides when "
                    "match=True to distinguish decisive co-orientation "
                    "from near-tied co-orientation."
                ),
            },
            "epistemic": {
                "a_sourced_pct": a["epistemic"].get("sourced_pct", 0),
                "b_sourced_pct": b["epistemic"].get("sourced_pct", 0),
                "sourced_pct_delta": (
                    (b["epistemic"].get("sourced_pct", 0) or 0)
                    - (a["epistemic"].get("sourced_pct", 0) or 0)
                ),
            },
            "framing_differences": framing_data,
        },
    }

    agent_guidance = {
        "what_this_tool_tells_you": [
            "Where two documents on the same subject diverge structurally",
            "Blind spots shared by both (perspectives where neither document shows detected markers)",
            "Coverage, voice, temporal, and epistemic deltas",
            "A structured framing-differences narrative with per-dimension reader implications",
            "Which named frame patterns each document activates",
        ],
        "what_this_tool_does_not_tell_you": [
            "Which document is more correct (agreement on a claim does not mean the claim is true; two documents can cite the same wrong training data)",
            "Which document the reader should trust more",
            "Whether structural differences translate to decision-relevant differences for the reader's purpose",
            "Reasoning quality, logical validity, or causal inference",
            "Numeric claim verification against external sources is not invoked in this response",
            "Whether perspectives flagged as missing in either document are truly absent, or discussed using vocabulary the detector does not recognize (under-detection is a known failure mode; 'missing' is a lower-bound claim)",
        ],
        "how_to_cite_faithfully": (
            "When surfacing this comparison to the user, name Frame "
            "Check and distinguish structural comparison from "
            "evaluative judgement. \"Frame Check's structural "
            "comparison found markers for 2 more analytical "
            "perspectives in Document A than in Document B\" is the "
            "right shape. \"Frame Check determined Document A is "
            "better than Document B\" is wrong: Frame Check does not "
            "rank documents. The measurements are deterministic and "
            "reproducible; paraphrasing them as your own ranking "
            "strips the method's scope."
        ),
        "how_to_surface_framing_differences": (
            "The framing_differences block has a headline (if one "
            "dimension dominates the divergence), per-dimension "
            "cards with a_value/b_value/note, and a shared_blind_note "
            "when both documents leave the same perspective unsaid. "
            "Surface the headline first, then the cards, then the "
            "shared_blind_note as closing. Each card's note is a "
            "reader implication, not a verdict."
        ),
        "when_to_invoke_again": (
            "frame_compare is deterministic for the same input pair. "
            "Calling it twice on identical (doc_a_text, doc_b_text) "
            "returns identical measurements. Re-invoke only when "
            "either document changes."
        ),
        # Per-level construct treatment (substrate-side composition
        # L5): frame_compare's per-document blocks carry claim_level
        # on each composed entity (frame_library_matches, voice,
        # temporal). The treatments dict is shared with frame_check
        # so a client handles both surfaces uniformly.
        "claim_level_treatments": _CLAIM_LEVEL_TREATMENTS,
    }

    # Provenance mirrors frame_check so a client can treat either
    # tool's output with the same integrity contract. The
    # analysis_layer names the compare path so downstream telemetry
    # and citations can distinguish the two surfaces; the
    # determinism note uses "input pair" because the unit of
    # determinism here is two documents, not one.
    provenance = _build_provenance(
        analysis_layer="deterministic_structural_comparison",
        elapsed_ms=elapsed_ms,
        determinism_note=(
            "Identical input pair produces identical output. No "
            "LLM is invoked in this response."
        ),
    )

    return {
        "analysis": analysis,
        "agent_guidance": agent_guidance,
        "provenance": provenance,
    }


# ── MCP method handlers ───────────────────────────────────────────

def handle_initialize(_params: dict) -> dict:
    """Handshake. Advertise the three MCP primitives this server
    supports: tools (frame_check, frame_compare), resources
    (library, worked examples, methodology, calibration) and
    prompts (self-audit, sovereignty case, challenge, walkthrough).
    The clientInfo in params is accepted but not used; if future
    versions want to gate features by client, it is available
    here.

    The top-level `instructions` field carries server-orientation
    prose to the agent: when to use Frame Check, default invocation
    shape, and the four-prompt workflow surface. Per the MCP
    protocol this is the canonical place for cross-tool guidance
    (per-tool descriptions are delivered separately via tools/list);
    surfacing the orientation here is what lets a client whose UI
    shows the InitializeResult give the user a one-line answer to
    'what is this server.'
    """
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
            "resources": {},
            "prompts": {},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
        "instructions": (
            "Frame Check is a structural framing-analysis tool for "
            "any English analytical document. Use it when the user "
            "wants to read a document with a structural lens (which "
            "perspectives it covers, which it omits, how confidently "
            "it speaks) or when you want to self-audit your own "
            "response before the user acts on it.\n\n"
            "Default invocation is zero-arg: "
            "`frame_check(document_text=<text>)`. The defaults "
            "produce the full output, including the divergence block "
            "(perspectives the document does not use) and a per-call "
            "suggested_next_actions block. Pass the optional "
            "parameters only when the user has provided the relevant "
            "context (source material, decision goal, working-memory "
            "budget).\n\n"
            "Two tools: `frame_check` (single document) and "
            "`frame_compare` (two documents on the same subject).\n\n"
            "Four prompts surface the common workflows: "
            "`frame_check_my_response` (self-audit your last reply), "
            "`frame_check_this_ai_response` (the user pastes another "
            "AI's reply), `challenge_document` (adversarial questions "
            "traced to structural gaps), `explain_framing` (guided "
            "walkthrough of a completed result). The user can ask "
            "you to use any of them by name.\n\n"
            "Cite each measurement as Frame Check's; frame your "
            "reading as a reading ('the pattern reads as X'), never "
            "as a verdict ('the document is X'). The deterministic "
            "path returns identical measurements on identical "
            "inputs at zero LLM cost."
        ),
    }


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


def handle_resources_list(_params: dict) -> dict:
    """Enumerate every resource this deploy can serve. Each entry
    carries the content hash of the served text so a client can
    detect drift against a previously cited resource without a
    second read. The `contentHash` field is an extension beyond
    the MCP resources/list base shape; clients that do not know
    about it ignore it.

    Advertised-but-unreadable invariant: a resource whose read fails
    during list construction (transient I/O, race with the
    filesystem, partial deploy) is dropped from the list entirely,
    not advertised hash-less. The citation-grade claim requires
    every advertised URI to resolve to concrete bytes and a
    stable hash; an entry without a hash is worse than no entry
    because a client cannot pin it. Failures are logged to stderr
    so operators see the drop. Enforced by three tests in
    test_mcp_server.py::test_resources_list_carries_content_hash,
    test_every_resource_has_stable_matching_hash, and
    test_resources_list_drops_unreadable_not_hashless.
    """
    resources = _list_resources()
    # Attach the content hash to every resource by reading each one
    # once. List construction is O(resources * content-size) in
    # bytes; for the current deploy (~100 resources, median 2 KB)
    # this is under 200 KB per call. Small enough that we do not
    # cache. If the catalogue grows, a per-session hash cache keyed
    # by file path + mtime is the obvious next step.
    out = []
    for resource in resources:
        uri = resource["uri"]
        try:
            contents = _read_resource(uri)
            text = contents["contents"][0]["text"]
            resource = dict(resource)
            resource["contentHash"] = _content_hash(text)
        except (ValueError, FileNotFoundError, OSError) as exc:
            sys.stderr.write(
                f"[frame-check-mcp] resources/list dropping {uri}: "
                f"{type(exc).__name__}: {exc}\n"
            )
            continue
        out.append(resource)
    return {"resources": out}


def handle_resources_read(params: dict) -> dict:
    """Return the content of a specific resource URI. Unknown or
    unresolvable URIs surface as JSON-RPC errors rather than empty
    results so the client can distinguish 'resource does not exist'
    from 'resource is empty'. The response carries a contentHash on
    each content item for citation and drift-detection."""
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError("uri parameter is required")
    result = _read_resource(uri)
    for content in result.get("contents", []):
        if "text" in content and "contentHash" not in content:
            content["contentHash"] = _content_hash(content["text"])
    return result


# ── Prompts primitive ─────────────────────────────────────────────
#
# MCP prompts are server-defined templates the agent's LLM executes.
# This server ships four. The two load-bearing ones encode the
# novel use case: an agent using Frame Check to audit AI-generated
# text. Either its own last response (frame_check_my_response) or
# a response from a different AI that the user pasted in
# (frame_check_this_ai_response). The other two cover common
# user-facing shapes: adversarial questioning of an arbitrary
# document and a walkthrough of a completed frame_check result.
#
# Voice rules for the prompt content:
#   - Declarative, not hortative. "Call the tool" not "please try."
#   - Specific tool invocations named by argument, not described.
#   - Every prompt names what the method cannot see.
#   - Verdict patterns prohibited explicitly ("do not call it biased").
#   - Teaching-question shape; surface structure, do not conclude.
#   - Terse. Fifteen lines beats thirty.
#
# These rules show up in every prompt body below. If a future
# prompt drifts from them, the discipline breaks and the tool
# starts to read like a verdict engine.


def _prompt_messages(text: str) -> list:
    """Wrap a single prompt body string in the MCP prompts/get
    messages shape. A single user-role message with text content is
    the minimum the client needs to populate a chat context.
    Multi-message shapes (user/assistant priming) are available if
    a future prompt needs them.
    """
    return [
        {"role": "user", "content": {"type": "text", "text": text}}
    ]


# Per-prompt argument valid values (substrate-side composition L5
# interface UX). Each sovereignty prompt accepts user-intent
# arguments that translate to MCP-parameter values inside the prompt
# body. The user types in their own vocabulary (depth: quick/thorough,
# goal: decide/explore/audit/challenge/learn, questions: yes/no);
# the prompt body then directs the agent to call frame_check with
# the corresponding MCP-layer values.
_PROMPT_DEPTH_VALUES = {"quick", "thorough"}
_PROMPT_GOAL_VALUES = {"decide", "explore", "audit", "challenge", "learn"}
_PROMPT_QUESTIONS_VALUES = {"yes", "no"}


def _translate_prompt_arguments(args: dict | None) -> dict:
    """Translate user-intent prompt arguments into MCP-parameter
    placeholder values that get interpolated into the prompt body.

    Argument vocabulary (user-facing):
      depth: "quick" | "thorough" (default "thorough"). Quick maps
        to compose_budget=minimal; thorough maps to full. The user's
        mental model is "fast read" vs "deep audit"; the substrate's
        compose_budget parameter is the implementation.
      goal: "decide" | "explore" | "audit" | "challenge" | "learn"
        (default "audit"). Maps to user_goal (decide -> decide;
        explore -> brainstorm; challenge -> audit + an additional
        composition note for adversarial reading; learn -> learn;
        audit -> audit). The user's mental model is "what am I trying
        to do with this reading"; the substrate's user_goal parameter
        is the implementation.
      questions: "yes" | "no" (default "no"). Maps to
        include_frame_opportunities (yes -> true; no -> false). The
        user's mental model is "do I want LLM-generated questions
        about my document"; the substrate's
        include_frame_opportunities parameter is the implementation.

    Invalid values fall back to defaults (do not raise; the prompts
    are user-invoked surfaces and rejecting an invalid argument would
    be a poor UX). Returns a dict of placeholder strings to values.
    The placeholder format is `<<KEY>>` to avoid colliding with the
    literal `{slug}` placeholder in _PROMPT_EXPLAIN_FRAMING.
    """
    args = args or {}
    depth = args.get("depth") if isinstance(args.get("depth"), str) else None
    if depth not in _PROMPT_DEPTH_VALUES:
        depth = "thorough"
    goal = args.get("goal") if isinstance(args.get("goal"), str) else None
    if goal not in _PROMPT_GOAL_VALUES:
        goal = "audit"
    questions = (
        args.get("questions") if isinstance(args.get("questions"), str)
        else None
    )
    if questions not in _PROMPT_QUESTIONS_VALUES:
        questions = "no"

    compose_budget = "minimal" if depth == "quick" else "full"
    user_goal_map = {
        "decide": "decide",
        "explore": "brainstorm",
        "audit": "audit",
        "challenge": "audit",
        "learn": "learn",
    }
    user_goal = user_goal_map.get(goal, "audit")
    include_opportunities = "true" if questions == "yes" else "false"

    if goal == "challenge":
        challenge_note = (
            "\n\nUser asked for an ADVERSARIAL CHALLENGE reading. "
            "Compose the insight as one or more questions that "
            "surface the document's structural weaknesses; lead "
            "with the strongest absent_frames and absence_clusters "
            "(what a critical reader would ask the document to "
            "address). Per agent_guidance.composition_discipline "
            "rule (5), the questions are reading-form not "
            "prescriptive ('what does this not address?', not "
            "'you should have addressed X')."
        )
    else:
        challenge_note = ""

    return {
        "<<COMPOSE_BUDGET>>": compose_budget,
        "<<USER_GOAL>>": user_goal,
        "<<INCLUDE_OPPORTUNITIES>>": include_opportunities,
        "<<DEPTH>>": depth,
        "<<GOAL>>": goal,
        "<<QUESTIONS>>": questions,
        "<<CHALLENGE_NOTE>>": challenge_note,
    }


def _populate_prompt_body(body: str, args: dict | None) -> str:
    """Substitute `<<PLACEHOLDER>>` tokens in the prompt body with
    values derived from the user-intent arguments. Substrate-side
    composition L5 interface UX: the user types in their own
    vocabulary (depth/goal/questions); the prompt body directs the
    agent to call frame_check with the corresponding MCP-parameter
    values."""
    placeholders = _translate_prompt_arguments(args)
    for key, value in placeholders.items():
        body = body.replace(key, value)
    return body


_PROMPT_SELF_AUDIT = (
    "Run a Frame Check self-audit on your last response to me.\n\n"
    "Call frame_check(document_text=<your last response verbatim>, "
    "include_divergence=true, compose_budget=<<COMPOSE_BUDGET>>, "
    "user_goal=<<USER_GOAL>>, "
    "include_frame_opportunities=<<INCLUDE_OPPORTUNITIES>>). If I "
    "gave you a user_context (situation, role, decision I'm "
    "facing), pass it. No source_text.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect document-scope mismatches BEFORE "
    "composing: under 100 words = 'below statistical floor; low "
    "confidence'; non-English = 'methodology validated on English; "
    "low confidence'; non-analytical structure (code, poetry, "
    "fragments) = 'calibrated for analytical prose; low confidence'. "
    "If any gate fires, PIVOT the frame: the insight becomes a "
    "reading of what the run reveals about Frame Check's scope, not "
    "a reading of my response. Name the gate in one sentence, then "
    "compose the pivoted reading.\n\n"
    "Compact response (default), insight-led:\n"
    "1. ONE insight, ~2-4 sentences. A reading I could not see by "
    "re-reading my own response. Lead with the strongest "
    "absence_cluster reading when divergence.absence_clusters is "
    "non-empty: the cluster names a dimension-level theme across "
    "multiple absent frames (e.g., 'load-bearing absences cluster "
    "on the counterfactual dimension'). Cite the cluster as Frame "
    "Check's substrate composition. Then ground in 1-2 supporting "
    "measurements (voice classification, frame_library_matches "
    "entry, individual high signal_strength absent_frame, "
    "decision_readiness dimension reading). When absence_clusters "
    "is empty, fall back to per-frame composition. Reading-form, "
    "not verdict-form: 'the pattern reads as X', never 'your "
    "response is X'. Cite inline as `[FVS-XXX Frame Title]("
    "library_url)` using each frame's library_url field (the "
    "GitHub markdown URL, always resolvable for the user); "
    "never use the frame-check:// resource URI for end-user "
    "citations because users in MCP clients cannot click it. "
    "Never add a bottom Sources "
    "bibliography. Do NOT walk the measurements one by one; the "
    "measurement walk is the expand path. When corpus_context "
    "fields are present (on matched frames, absent frames, or "
    "clusters), anchor the reading in their prevalence and "
    "peer-pair-difference signals; honor "
    "envelope.corpus_summary.small_n_caveat. Honor "
    "agent_guidance.composition_discipline.\n"
    "2. ONE question this insight is asking me. Question form, "
    "never statement. Honor agent_guidance."
    "absence_is_not_prescription: name what the framing does, "
    "never what I should have done. If user_context is present, "
    "the question may filter for situational relevance; never "
    "prescribe from the context.\n"
    "3. \"I see the frame you chose. What I do with that is my "
    "call.\"\n"
    "4. \"Say 'expand' for the full structural readout.\"\n\n"
    "On expand: walk the deep analysis (coverage with density per "
    "category, voice with confidence + runner-up, temporal with "
    "balanced flag, epistemic, all FVS matches with teaching_question "
    "and affects_dimensions, decision-readiness across five dimensions "
    "with status 'experimental' verbatim, the per-dimension "
    "library_entries[].library_resource_uri chain plus the "
    "fired_library_entries focused subset so the canon graph is "
    "traversable from each dimension, /corpus/decision-readiness/ "
    "as the methodology page, agent_guidance."
    "what_this_tool_does_not_tell_you). Inline citations throughout; "
    "never add a bibliography. Do not verdict (no 'balanced', no "
    "'biased', no 'rigorous'). Frame Check measures structural "
    "shape, not semantic correctness; name that limit if relevant. "
    "Do not rewrite unless I ask."
)

_PROMPT_AI_RESPONSE_AUDIT = (
    "Frame Check on an AI-generated response the user will paste.\n\n"
    "The user is using Frame Check to see what another AI did to "
    "them, not to be told whether to trust it.\n\n"
    "Ask the user to paste the AI response if they have not. Then "
    "call frame_check(document_text=<that text>, "
    "include_divergence=true, compose_budget=<<COMPOSE_BUDGET>>, "
    "user_goal=<<USER_GOAL>>, "
    "include_frame_opportunities=<<INCLUDE_OPPORTUNITIES>>). If the "
    "user gave a user_context (their situation, role, decision "
    "they're facing), pass it. No source_text unless the user "
    "supplies the original material the AI's response was supposed "
    "to ground in.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect document-scope mismatches BEFORE "
    "composing: under 100 words = 'below statistical floor; low "
    "confidence'; non-English = 'methodology validated on English; "
    "low confidence'; non-analytical structure (code, poetry, "
    "fragments) = 'calibrated for analytical prose; low "
    "confidence'. If any gate fires, PIVOT the frame: the insight "
    "becomes a reading of what the run reveals about Frame Check's "
    "scope on this kind of text, not a reading of the AI's "
    "response. Name the gate in one sentence, then compose the "
    "pivoted reading.\n\n"
    "Compact response (default), insight-led:\n"
    "1. ONE insight, ~2-4 sentences. A reading the user could not "
    "see by re-reading the AI's response themselves. Lead with the "
    "strongest absence_cluster reading when "
    "divergence.absence_clusters is non-empty: the cluster names a "
    "dimension-level theme across multiple absent frames. Cite the "
    "cluster as Frame Check's substrate composition. Then ground "
    "in 1-2 supporting measurements (voice classification, "
    "frame_library_matches entry, individual high signal_strength "
    "absent_frame, decision_readiness dimension reading). When "
    "absence_clusters is empty, fall back to per-frame composition. "
    "Reading-form, not verdict-form: 'the pattern reads as X', "
    "never 'the AI is X'. Cite inline as `[FVS-XXX Frame Title]("
    "library_url)` using each frame's library_url field (the "
    "GitHub markdown URL, always resolvable for the user); "
    "never use the frame-check:// resource URI for end-user "
    "citations because users in MCP clients cannot click it. "
    "Never add a bottom Sources "
    "bibliography. Do NOT walk the measurements one by one; the "
    "measurement walk is the expand path. When corpus_context "
    "fields are present (on matched frames, absent frames, or "
    "clusters), anchor the reading in their prevalence and "
    "peer-pair-difference signals; honor "
    "envelope.corpus_summary.small_n_caveat. Honor "
    "agent_guidance.composition_discipline.\n"
    "2. ONE question this insight is asking the user. Question "
    "form, never statement. Honor agent_guidance."
    "absence_is_not_prescription: name what the framing does, "
    "never tell the user the AI should have done X. If "
    "user_context is present, the question may filter for "
    "situational relevance; never prescribe from the context.\n"
    "3. \"Say 'expand' for the full structural readout.\"\n\n"
    "On expand: walk the deep analysis (coverage with density per "
    "category and the under-detection caveat, voice with "
    "confidence + runner-up, temporal with balanced flag, "
    "epistemic with sourced_pct, all FVS matches with "
    "teaching_question and affects_dimensions, decision-readiness "
    "across five dimensions with status 'experimental' verbatim, "
    "the per-dimension library_entries[].library_resource_uri "
    "chain plus the fired_library_entries focused subset so the "
    "canon graph is traversable from each dimension, "
    "/corpus/decision-readiness/ as the methodology page, "
    "agent_guidance.what_this_tool_does_not_tell_you). Inline "
    "citations everywhere; never add a bibliography. Do not "
    "verdict the analyzed AI: no 'balanced', no 'biased', no "
    "'rigorous'. Surface structural shape; the user judges.\n\n"
    "Optional context (only when the user asks 'how does this "
    "compare to other AI responses' or 'is this typical'): "
    "frame-check://aggregate/latest carries cross-question "
    "outlier findings across the validation corpus. Cite as "
    "\"Frame Check's validation corpus has found...\", and only "
    "when the cross-context comparison sharpens THIS reading; "
    "honor composition_discipline rule (4) on cross-context "
    "compounding. Not a verdict on the user's specific document.\n\n"
    "Do not verdict the analyzed AI. Compose the reading; the "
    "user judges."
)

_PROMPT_CHALLENGE_DOCUMENT = (
    "Challenge a document using Frame Check's structural "
    "measurements.\n\n"
    "The user gives you a document. Call frame_check("
    "document_text=<that text>, include_divergence=true, "
    "compose_budget=<<COMPOSE_BUDGET>>, user_goal=<<USER_GOAL>>, "
    "include_frame_opportunities=<<INCLUDE_OPPORTUNITIES>>). If the "
    "user gave a user_context, pass it. No source_text unless they "
    "supplied source material.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect document-scope mismatches "
    "BEFORE composing: under 100 words = 'below statistical floor; "
    "low confidence'; non-English = 'methodology validated on "
    "English; low confidence'; non-analytical structure (code, "
    "poetry, fragments) = 'calibrated for analytical prose; low "
    "confidence'. If any gate fires, PIVOT the frame: instead of "
    "challenging the document, surface ONE question about what "
    "this run reveals about Frame Check's scope on this kind of "
    "text. Name the gate in one sentence, then ask the pivoted "
    "question.\n\n"
    "Compact response (default), insight-led: compose 2-3 "
    "questions, each a compressed reading-as-question grounded in "
    "specific cited measurements. Honor "
    "agent_guidance.composition_discipline: each question is a "
    "reading the user could not see by re-reading their own "
    "document, expressed in question form.\n\n"
    "Top 2-3 highest-leverage questions, with INLINE citations "
    "`[FVS-XXX Frame Title](library_url)` (the library_url field "
    "on each frame entry; never the frame-check:// resource URI "
    "in end-user output, since users cannot click MCP URIs):\n"
    "- When divergence.absence_clusters is non-empty, the strongest "
    "cluster's reading is the source of the lead question: translate "
    "the dimension-level theme into a question (e.g., counterfactual "
    "cluster: 'What would have to be true about [document subject] "
    "for the conclusion to be wrong?'). Cite the cluster's dimension "
    "and the cluster's strongest member frame inline.\n"
    "- Highest signal_strength absent frame in divergence: cite "
    "the frame and ask the question that frame would surface "
    "(e.g., FVS-011 Stakeholder Frame absent: \"Who does this "
    "document not mention, and what would they say?\"; FVS-012 "
    "Uncertainty Frame absent: \"What would have to be true for "
    "the conclusion to be wrong?\"; FVS-016 Authority by Citation "
    "absent: \"Which claims lean on the author's register rather "
    "than on citable sources?\"). Filter for reader-relevance per "
    "agent_guidance.how_to_render_divergence. Do NOT walk "
    "medium/low tiers unless asked.\n"
    "- FVS match present (not absent): the library entry's "
    "teaching_question verbatim, with the citation_uri inline. "
    "affects_dimensions tells you which decision-readiness "
    "dimensions the pattern threatens.\n"
    "- Low sourced_pct (when relevant): \"What is this claim "
    "grounded in that I can independently verify?\"\n"
    "- When a frame or cluster carries a corpus_context (peer-pair "
    "difference rate, cross-question outlier, or empirical "
    "prevalence), the question may anchor in that empirical signal "
    "(e.g., 'Frame Check's validation corpus shows the "
    "counterfactual dimension differs across 10 of 12 peer pairs; "
    "what would falsify your conclusion here?'). Honor "
    "envelope.corpus_summary.small_n_caveat; cite as Frame Check's "
    "validation corpus, not as a population estimate.\n\n"
    "Each question is a tool the user uses; never a verdict. "
    "Reading-form, not verdict-form: 'the pattern reads as X, so "
    "what does Y look like?', never 'the document is X'. Question "
    "form, never statement. Honor "
    "agent_guidance.absence_is_not_prescription: questions, not "
    "'you should have done X'. If user_context is present, filter "
    "questions for situational relevance; never prescribe from "
    "the context. Cite inline; never add a bottom bibliography.\n\n"
    "End with: \"Say 'expand' for more questions across all weak "
    "structural signals.\"\n\n"
    "On expand: walk every weak signal (every missing coverage "
    "category, every voice mismatch, every fired FVS match, every "
    "absent_frame at any tier the user wants surfaced, every "
    "decision-readiness dimension with weak signal_text, its "
    "fired_library_entries chain, and the per-dimension "
    "library_entries[].library_resource_uri pointers so the canon "
    "graph is traversable). Generate one question per signal, all "
    "inline-cited. The decision_readiness profile is experimental "
    "(status 'experimental' verbatim); link "
    "/corpus/decision-readiness/ for the framework.\n\n"
    "The method does not generate novel insight from nothing; it "
    "composes readings-as-questions grounded in cited "
    "measurements. The questions are the reading."
)

_PROMPT_EXPLAIN_FRAMING = (
    "Walk the user through a Frame Check result they have just "
    "seen. Assume frame_check was already called and the response "
    "is in context.\n\n"
    "User intent for this walkthrough: depth=<<DEPTH>>, "
    "goal=<<GOAL>>, questions=<<QUESTIONS>>. Adapt the response "
    "shape: 'quick' depth means surface only the compact response "
    "below (one insight + one question + closing); 'thorough' "
    "means also offer the expand path. 'challenge' goal emphasizes "
    "adversarial reading (compose questions surfacing the "
    "document's structural weaknesses); 'learn' goal emphasizes "
    "taxonomy walks for understanding-building. 'questions=yes' "
    "means surface any opt-in frame_opportunities the original "
    "call captured.<<CHALLENGE_NOTE>>\n\n"
    "Confidence gate first. Detect off-methodology signals in the "
    "result before composing: analysis.document.word_count_estimate "
    "under 100 words = 'below statistical floor; low confidence'; "
    "non-English text in the document_text = 'methodology validated "
    "on English; low confidence'; non-analytical structure (code, "
    "poetry, fragmentary text) = 'calibrated for analytical prose; "
    "low confidence'. If any gate fires, PIVOT the frame: the "
    "insight becomes a reading of what this run reveals about "
    "Frame Check's scope, not a reading of the document. Name the "
    "gate in one sentence, then compose the pivoted reading.\n\n"
    "Compact response (default), insight-led:\n"
    "1. ONE insight, ~2-4 sentences. A reading of the analysis "
    "the user could not see by re-reading the analysis output "
    "themselves. analysis.portrait is a starting fact, not the "
    "insight. Lead with the strongest absence_cluster reading "
    "when divergence.absence_clusters is non-empty: the cluster "
    "names a dimension-level theme the per-frame walk cannot. "
    "Compose the portrait with 1-2 cited supporting measurements "
    "(highest signal_strength absent_frame from the divergence "
    "block, voice classification, the weakest decision_readiness "
    "dimension by signal_text reading) into a reading of what the "
    "document is doing structurally. When absence_clusters is "
    "empty, fall back to per-frame composition. Do NOT walk the "
    "measurements one by one in the compact response; that "
    "mechanical readout is the expand path. Reading-form, not "
    "verdict-form: 'the pattern reads as X', never 'the document "
    "is X'. Cite inline as `[FVS-XXX Frame Title](library_url)` "
    "using each frame's library_url field (the GitHub markdown URL, "
    "always resolvable for the user); never use the frame-check:// "
    "resource URI for end-user citations because users in MCP "
    "clients cannot click it. Never add a bottom Sources "
    "bibliography. When "
    "corpus_context fields are present (on matched frames, absent "
    "frames, or clusters), anchor the reading in their prevalence "
    "and peer-pair-difference signals; honor "
    "envelope.corpus_summary.small_n_caveat. Honor "
    "agent_guidance.composition_discipline.\n"
    "2. ONE question this insight is asking the user. Question "
    "form, never statement. Honor agent_guidance."
    "absence_is_not_prescription. If user_context was passed to "
    "the original call, the question may filter for situational "
    "relevance; never prescribes from the context.\n"
    "3. \"Say 'expand' for the full structural readout.\"\n\n"
    "On expand: walk every section. Coverage with density "
    "per category and the under-detection caveat. Voice with "
    "confidence + runner-up + balanced flag if applicable. "
    "Temporal with balanced flag. Epistemic with sourced_pct. "
    "All FVS matches with teaching_question and "
    "affects_dimensions; chain via "
    "fired_library_entries[].library_resource_uri to the named "
    "patterns. Full divergence walk including medium-tier "
    "absences. Decision-readiness across all five dimensions "
    "with status 'experimental' verbatim and link to "
    "/corpus/decision-readiness/. scope_regime guidance for "
    "number-saturated sources. Close with "
    "agent_guidance.what_this_tool_does_not_tell_you.\n\n"
    "Optional context (when the user asks 'how does this compare "
    "to other AI responses' or 'is this typical'): the validation "
    "corpus aggregate at frame-check://aggregate/latest carries "
    "cross-question consistency findings (e.g., 'claude is the "
    "counterfactual outlier across multiple peer groups'). Each "
    "finding includes corpus_entries with corpus_resource_uri so "
    "you can read specific corpus entries via "
    "frame-check://corpus/{slug}. Cite sparingly, only when the "
    "cross-context comparison sharpens THIS reading "
    "(composition_discipline rule 4). Not a verdict on the user's "
    "specific document.\n\n"
    "Compose the reading. Do not conclude from the measurements."
)


# Standard user-intent argument specs shared across the four
# sovereignty prompts (substrate-side composition L5 interface UX).
# All three arguments are optional with defaults; omitting them
# preserves prior behavior (thorough / audit / no questions).
_USER_INTENT_PROMPT_ARGS = [
    {
        "name": "depth",
        "description": (
            "How thorough a reading you want. 'quick' = top-3 "
            "absences, top-1 cluster, top-1 named pattern (compact "
            "response, maps to compose_budget=minimal). 'thorough' "
            "(default) = full divergence + all clusters + all "
            "patterns (deeper read, more substrate composition to "
            "work with). Use 'quick' when you want a fast check; "
            "'thorough' when you want a careful audit."
        ),
        "required": False,
    },
    {
        "name": "goal",
        "description": (
            "What you are trying to do with this reading. 'decide' "
            "= you are about to make a decision based on this "
            "document; ranking favors falsification + risk + "
            "temporal anchoring. 'explore' = you are surveying "
            "options; ranking favors perspective diversity. 'audit' "
            "(default) = you are checking the framing without a "
            "specific intent; the substrate's catalog/coverage/genre "
            "ranking applies. 'challenge' = you want adversarial "
            "questions surfacing the document's structural "
            "weaknesses (composes the insight as questions). "
            "'learn' = you are building understanding of the "
            "framing; ranking favors full taxonomy walks."
        ),
        "required": False,
    },
    {
        "name": "questions",
        "description": (
            "'yes' = include up to 3 LLM-composed document-specific "
            "questions per absent frame (Item 12 frame_opportunities; "
            "opt-in; ~$0.001 cost; non-deterministic; cite as "
            "LLM-generated). 'no' (default) = deterministic substrate "
            "only (clusters, patterns, absences with goal and genre "
            "relevance). The deterministic substrate is reproducible "
            "across runs; opportunities are not."
        ),
        "required": False,
    },
]


_PROMPTS = [
    {
        "name": "frame_check_my_response",
        "description": (
            "Self-audit: agent calls frame_check on its own last "
            "response and surfaces the structural framing to the "
            "user without verdict or defensive rewriting. Load-"
            "bearing for the sovereignty use case: the user sees "
            "what frame their agent chose. Optional arguments: "
            "depth (quick / thorough), goal (decide / explore / "
            "audit / challenge / learn), questions (yes / no)."
        ),
        "body": _PROMPT_SELF_AUDIT,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
    {
        "name": "frame_check_this_ai_response",
        "description": (
            "Frame Check on a response from a DIFFERENT AI that "
            "the user pastes in. Structured analysis of what that "
            "AI did to the user. The sovereignty case: the user "
            "is using their own agent to see another AI's framing. "
            "Optional arguments: depth, goal, questions."
        ),
        "body": _PROMPT_AI_RESPONSE_AUDIT,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
    {
        "name": "challenge_document",
        "description": (
            "Generate adversarial questions from the structural "
            "weaknesses of a document. Each question traces to a "
            "specific Frame Check measurement. Questions, not "
            "verdicts; the user answers. Optional arguments: depth, "
            "goal (defaults to 'challenge' for this prompt), "
            "questions."
        ),
        "body": _PROMPT_CHALLENGE_DOCUMENT,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
    {
        "name": "explain_framing",
        "description": (
            "Walkthrough template for a completed frame_check "
            "result. Teaches the measurements in reading order "
            "and closes with what the method could not see. "
            "Optional arguments: depth, goal (defaults to 'learn' "
            "for this prompt), questions."
        ),
        "body": _PROMPT_EXPLAIN_FRAMING,
        "arguments": _USER_INTENT_PROMPT_ARGS,
    },
]


def handle_prompts_list(_params: dict) -> dict:
    """Advertise every prompt this server exposes. Clients use the
    list to offer named prompts to end users (slash-commands in a
    chat UI, command-palette entries, etc.)."""
    return {
        "prompts": [
            {
                "name": p["name"],
                "description": p["description"],
                "arguments": p["arguments"],
            }
            for p in _PROMPTS
        ]
    }


def handle_prompts_get(params: dict) -> dict:
    """Return the populated messages for a named prompt. Arguments
    are user-intent values (depth, goal, questions) that get
    translated into MCP-parameter values inside the prompt body via
    _populate_prompt_body. Invalid or omitted argument values fall
    back to defaults (thorough / audit / no). Unknown prompt names
    raise ValueError which the dispatcher turns into a -32602
    invalid-params error."""
    name = params.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name parameter is required")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    for p in _PROMPTS:
        if p["name"] == name:
            populated_body = _populate_prompt_body(p["body"], args)
            return {
                "description": p["description"],
                "messages": _prompt_messages(populated_body),
            }
    raise ValueError(f"Unknown prompt: {name}")


_FRAME_CHECK_TOOL = {
    "name": "frame_check",
    "description": (
        "Read a document with a structural lens: which analytical "
        "perspectives it covers, which it omits, how confidently it "
        "speaks, and which framing patterns from the Frame Vocabulary "
        "Standard fire on it.\n\n"
        "Use this when the user pastes a document and asks for a "
        "structural read, when you want to self-audit your own last "
        "response before the user acts on it, or when the user pastes "
        "another AI's reply and asks what that AI did structurally.\n\n"
        "Zero-arg invocation works for any English analytical document: "
        "`frame_check(document_text=<text>)`. The defaults produce the "
        "full output, including the divergence block (perspectives the "
        "document does not use) and a per-call suggested_next_actions "
        "block. Pass the optional parameters only when the user has "
        "provided the relevant context (source material, decision "
        "goal, working-memory budget).\n\n"
        "Compose ONE insight grounded in the cited measurements (a "
        "reading the user could not see by reading the document "
        "themselves), not a walk through the measurements one by one. "
        "The measurements are Frame Check's; the reading is yours. "
        "Cite each measurement as Frame Check's; frame the reading as "
        "a reading ('the pattern reads as X'), never as a verdict "
        "('the document is X'). Repeated calls with identical inputs "
        "return identical measurements; zero LLM cost on the "
        "deterministic path."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_text": {
                "type": "string",
                "description": (
                    "The document to analyse. English. 300 to 10,000 "
                    "words is the validated range; under 100 words "
                    "the analysis carries a low-confidence note, over "
                    "1,000,000 characters returns a truncation guidance. "
                    "Markdown accepted. This is the text whose framing "
                    "you want named."
                ),
                "maxLength": MAX_DOCUMENT_CHARS,
            },
            "source_text": {
                "type": "string",
                "description": (
                    "Pass when the user has the source material the "
                    "document was supposed to ground in (research "
                    "report, SEC filing, primary source). Unlocks "
                    "digit-level source-fidelity verification "
                    "(Layer 4) plus a sentence-level grounded / "
                    "fabricated / paraphrased decomposition (Layer "
                    "11) with a scope regime telling you which layer "
                    "to trust on number-dense sources. Skip when no "
                    "source material is available; the structural "
                    "framing analysis runs either way."
                ),
                "maxLength": MAX_SOURCE_CHARS,
            },
            "include_divergence": {
                "type": "boolean",
                "description": (
                    "Default true. You do not need to pass this. The "
                    "divergence block (frame patterns the document "
                    "does not use, sorted by signal_strength) is the "
                    "headline output and ships by default. Set "
                    "explicitly to false only if you need the legacy "
                    "0.7.x-shape response with no divergence block "
                    "(rare; use only when an integrator pinned the "
                    "older shape)."
                ),
            },
            "user_context": {
                "type": "string",
                "description": (
                    "Pass when the user has stated their situation, "
                    "role, or decision context in the conversation "
                    "(for example, 'I am a startup founder making a "
                    "hire decision in healthcare AI', 'reviewing a "
                    "research paper on language-model alignment'). "
                    "When provided, the rendering guidance is "
                    "extended so divergence relevance is filtered "
                    "for this context. The context personalizes "
                    "RELEVANCE FILTERING; never PRESCRIPTION (the "
                    "absence-is-not-prescription guarantee holds). "
                    "The MCP does not echo the value back in the "
                    "response. Skip when no role or decision context "
                    "is established. Maximum length 2000 chars."
                ),
                "maxLength": 2000,
            },
            "user_goal": {
                "type": "string",
                "description": (
                    "Pass when the user has stated a goal for "
                    "invoking Frame Check. One of: 'decide' (working "
                    "through a choice), 'brainstorm' (exploring "
                    "options), 'persuade' (writing to influence), "
                    "'learn' (understanding the topic), 'audit' "
                    "(default-equivalent: structural read with no "
                    "goal-specific override). When provided, "
                    "absent_frames carry a goal_relevance dict for "
                    "goal-load-bearing frames, and the absent_frames "
                    "sort promotes goal-relevant entries within "
                    "their signal_strength tier. Skip when the user "
                    "has not named a goal; behavior matches 'audit'."
                ),
                "enum": [
                    "decide", "brainstorm", "persuade",
                    "learn", "audit",
                ],
            },
            "compose_budget": {
                "type": "string",
                "description": (
                    "Default 'full'. Switch to 'standard' or "
                    "'minimal' when in a tight working-memory "
                    "budget (per-turn self-audit loops, batch "
                    "document processing).\n"
                    "  'minimal' = top-3 absent_frames, top-1 "
                    "cluster, top-1 pattern; agent_guidance "
                    "compressed to load-bearing prescriptions only "
                    "(the inline claim_level_treatments table and "
                    "worked examples drop; the compressed shape "
                    "carries a claim_level_treatments_note pointing "
                    "you to compose_budget='full' for the full "
                    "table).\n"
                    "  'standard' = top-5 absent_frames, all "
                    "clusters, all patterns; agent_guidance "
                    "compressed (same rules as minimal).\n"
                    "  'full' = unfiltered output, full inline "
                    "agent_guidance.\n"
                    "The suggested_next_actions block survives at "
                    "all tiers (per-call-derived, load-bearing for "
                    "the user's discovery loop)."
                ),
                "enum": ["minimal", "standard", "full"],
            },
            "include_frame_opportunities": {
                "type": "boolean",
                "description": (
                    "Default false. Set true when the user wants up "
                    "to 3 LLM-augmented document-specific questions "
                    "composed from absent-frame teaching questions "
                    "plus the document's content. Adds "
                    "frame_opportunities to the divergence block "
                    "with model_provenance per opportunity. Cost "
                    "bounded at roughly 0.001 USD per invocation "
                    "(3 Gemini Flash calls maximum). Falls back to "
                    "an empty list with available=false if "
                    "GEMINI_API_KEY is not set or the google.genai "
                    "library is unavailable. Skip for the "
                    "deterministic-only path."
                ),
            },
            "divergence_rendering": {
                "type": "string",
                "description": (
                    "Default 'list'. Switch to 'teaching_questions' "
                    "when the absent-frame records should carry a "
                    "teaching_question field for surfacing as "
                    "questions rather than identifiers. All other "
                    "modes return the same data; this only affects "
                    "record decoration."
                ),
                "enum": list(_DIVERGENCE_RENDERING_ENUM),
            },
        },
        "required": ["document_text"],
    },
}


_FRAME_COMPARE_TOOL = {
    "name": "frame_compare",
    "description": (
        "Compare the framing of two documents on the same subject. "
        "Surfaces shared blind spots, unique coverage gaps, voice / "
        "temporal / epistemic deltas, and a structured framing-"
        "differences narrative with per-dimension reader "
        "implications.\n\n"
        "Use this when the user has two documents on the same "
        "subject (two AI responses to the same prompt, two analyst "
        "memos, an earnings release versus a press summary) and "
        "wants to see how they frame the same question differently.\n\n"
        "Pass `document_a_label` and `document_b_label` only when "
        "the user has named the documents (for example 'Gemini "
        "response' and 'Claude response'). Otherwise the comparison "
        "narrative falls back to 'Document A' and 'Document B'.\n\n"
        "Cite each measurement as Frame Check's; never imply that "
        "one document is better, more rigorous, or more biased "
        "than the other. The structural comparison surfaces what "
        "differs; the reader judges what the difference means. "
        "Repeated calls with identical inputs return identical "
        "results. No LLM is invoked."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "document_a_text": {
                "type": "string",
                "description": (
                    "The first document to compare. English. "
                    "300-10,000 words."
                ),
                "maxLength": MAX_DOCUMENT_CHARS,
            },
            "document_b_text": {
                "type": "string",
                "description": (
                    "The second document to compare. English. "
                    "300-10,000 words. Should be on the same "
                    "subject as document_a_text for the comparison "
                    "to be meaningful."
                ),
                "maxLength": MAX_DOCUMENT_CHARS,
            },
            "document_a_label": {
                "type": "string",
                "description": (
                    "Optional short label for document A (e.g. "
                    "'Industry view' or 'Gemini response'). Used in "
                    "the comparison narrative. Defaults to "
                    "'Document A'."
                ),
                "maxLength": 60,
            },
            "document_b_label": {
                "type": "string",
                "description": (
                    "Optional short label for document B. Defaults "
                    "to 'Document B'."
                ),
                "maxLength": 60,
            },
        },
        "required": ["document_a_text", "document_b_text"],
    },
}


# Tools advertised over tools/list. Keeping the list as a module-level
# constant mirrors the MCP idiom (tools are a registry) and keeps the
# dispatcher readable: adding a third tool is one entry here plus one
# branch in handle_tools_call.
_TOOLS = [_FRAME_CHECK_TOOL, _FRAME_COMPARE_TOOL]


def handle_tools_list(_params: dict) -> dict:
    return {"tools": _TOOLS}


def _tool_error(message: str) -> dict:
    """Standard isError response shape used by handle_tools_call. MCP
    distinguishes 'tool-level errors' (isError: true in the result)
    from 'protocol errors' (JSON-RPC error object). Tool-level errors
    let the client surface the error to the user as tool output,
    which is almost always what we want for bad arguments or
    recoverable pipeline failures."""
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


# Sanitized user-facing messages for unexpected tool-layer failures.
# Phase 5 item 7-MCP (attacker-hardened error wrappers) per
# V4_2_GAP_INVENTORY_v1.md. Stable error codes let MCP clients
# program against the failure modes without parsing exception text;
# sanitized messages prevent leak of internal state, stack traces,
# or user document content via exception message interpolation.
_MCP_TOOL_ERROR_MESSAGES = {
    "frame_check_internal_error": (
        "Frame Check analysis could not complete. The server logged the "
        "failure for follow-up; retry in a minute. If the problem "
        "persists, the document may have unusual structure."
    ),
    "frame_compare_internal_error": (
        "Frame Check comparison could not complete. The server logged "
        "the failure for follow-up; retry in a minute."
    ),
}


def _sanitize_tool_exception(exc: BaseException, error_code: str) -> dict:
    """Map an unexpected tool-layer exception to a sanitized isError
    response. The full exception (type, message, traceback) is logged
    server-side via `log()`; the client receives only the stable error
    code and a generic user-safe message.

    This closes the attacker-hardened-messages requirement for the MCP
    surface. Prior behaviour interpolated `{type(exc).__name__}: {exc}`
    directly into the response, which could leak document content (if
    a downstream detector embedded a snippet in its exception message),
    file paths, or internal class hierarchy to any caller.

    Callers should still perform their own `log()` before calling this
    to preserve maintainer-side observability; the sanitizer does NOT
    double-log, it only builds the response.
    """
    message = _MCP_TOOL_ERROR_MESSAGES.get(
        error_code,
        # Defensive: an unknown code still yields a content-free message.
        "An internal error occurred. The server logged it for follow-up."
    )
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "error": error_code,
                "message": message,
            }),
        }],
        "isError": True,
    }


def handle_tools_call(params: dict) -> dict:
    tool_name = params.get("name")
    raw_arguments = params.get("arguments")

    # arguments MUST be a JSON object (dict) when present. A
    # non-dict (list, string, scalar) would crash the handler with
    # AttributeError on the next .get(...). Surface as ValueError
    # so the dispatcher returns ERR_INVALID_PARAMS rather than
    # ERR_INTERNAL: the request was malformed, the server did not
    # crash. Mirrors the dispatch-level params shape validation.
    if raw_arguments is None:
        arguments = {}
    elif isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        raise ValueError(
            f"arguments must be a JSON object; got "
            f"{type(raw_arguments).__name__}"
        )

    if tool_name == "frame_compare":
        return _call_frame_compare(arguments)
    if tool_name != "frame_check":
        return _tool_error(
            f"Unknown tool: {tool_name}. "
            f"Available tools: frame_check, frame_compare."
        )

    document_text = arguments.get("document_text")
    if not isinstance(document_text, str) or not document_text.strip():
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "document_text is required and must be a "
                        "non-empty string."
                    ),
                }
            ],
            "isError": True,
        }

    if len(document_text) > MAX_DOCUMENT_CHARS:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"document_text exceeds the "
                        f"{MAX_DOCUMENT_CHARS}-character limit. "
                        f"Truncate the document before calling."
                    ),
                }
            ],
            "isError": True,
        }

    source_text = arguments.get("source_text")
    if source_text is not None:
        if not isinstance(source_text, str):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "source_text must be a string if provided."
                        ),
                    }
                ],
                "isError": True,
            }
        if len(source_text) > MAX_SOURCE_CHARS:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"source_text exceeds the "
                            f"{MAX_SOURCE_CHARS}-character limit. "
                            f"Truncate the source before calling."
                        ),
                    }
                ],
                "isError": True,
            }

    prefer_contract_version = arguments.get("prefer_contract_version")
    if prefer_contract_version is not None and prefer_contract_version not in (1, 2):
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "prefer_contract_version must be 1 or 2 if provided."
                    ),
                }
            ],
            "isError": True,
        }

    # FRAME_DIVERGENCE_CONTRACT_v1 Part 2 §3 inputs: validated here
    # so build_epistemic_payload receives clean values. Default is
    # True at 0.8.0 (was False at 0.7.x); the divergence block is the
    # headline capability and shipping it by default removes the
    # opt-in friction. Callers who explicitly set false continue to
    # get the v0.7.x-shape response with no divergence block.
    include_divergence = arguments.get("include_divergence", True)
    if not isinstance(include_divergence, bool):
        return {
            "content": [{"type": "text", "text": (
                "include_divergence must be a boolean if provided."
            )}],
            "isError": True,
        }

    domain_hint = arguments.get("domain_hint")
    if domain_hint is not None:
        if not isinstance(domain_hint, str) or domain_hint not in _DOMAIN_HINT_ENUM:
            return {
                "content": [{"type": "text", "text": (
                    f"domain_hint must be one of {list(_DOMAIN_HINT_ENUM)} "
                    f"if provided (got {domain_hint!r})."
                )}],
                "isError": True,
            }

    divergence_rendering = arguments.get("divergence_rendering", "list")
    if not isinstance(divergence_rendering, str) or divergence_rendering not in _DIVERGENCE_RENDERING_ENUM:
        return {
            "content": [{"type": "text", "text": (
                f"divergence_rendering must be one of "
                f"{list(_DIVERGENCE_RENDERING_ENUM)} if provided "
                f"(got {divergence_rendering!r})."
            )}],
            "isError": True,
        }

    catalog_version_pin = arguments.get("catalog_version_pin")
    if catalog_version_pin is not None and not isinstance(catalog_version_pin, str):
        return {
            "content": [{"type": "text", "text": (
                "catalog_version_pin must be a string if provided."
            )}],
            "isError": True,
        }

    # user_context (optional, max 2000 chars). When provided, the MCP
    # extends agent_guidance.how_to_render_divergence with the
    # contextual filtering instruction; the value itself is NOT echoed
    # in the response (privacy posture: caller-side context never
    # round-trips through the server).
    user_context = arguments.get("user_context")
    if user_context is not None:
        if not isinstance(user_context, str):
            return {
                "content": [{"type": "text", "text": (
                    "user_context must be a string if provided."
                )}],
                "isError": True,
            }
        if not user_context.strip():
            return {
                "content": [{"type": "text", "text": (
                    "user_context must be non-empty if provided "
                    "(omit the parameter for unfiltered behavior)."
                )}],
                "isError": True,
            }
        if len(user_context) > 2000:
            return {
                "content": [{"type": "text", "text": (
                    f"user_context exceeds the 2000-character limit "
                    f"(received {len(user_context)})."
                )}],
                "isError": True,
            }

    # include_frame_opportunities (optional, boolean). Item 12
    # opt-in: when true, generate LLM-augmented document-specific
    # questions for top absent frames. Bounded; cost-tracked.
    include_frame_opportunities = arguments.get(
        "include_frame_opportunities", False,
    )
    if not isinstance(include_frame_opportunities, bool):
        return {
            "content": [{"type": "text", "text": (
                "include_frame_opportunities must be a boolean if "
                "provided."
            )}],
            "isError": True,
        }

    # user_goal (optional, enum-bounded). Substrate-side composition
    # Item 11: when provided, absent_frames carry goal_relevance and
    # the sort promotes goal-relevant entries within their tier.
    user_goal = arguments.get("user_goal")
    if user_goal is not None:
        from user_goals import get_user_goals as _user_goals_enum
        valid_goals = set(_user_goals_enum())
        if not isinstance(user_goal, str) or user_goal not in valid_goals:
            return {
                "content": [{"type": "text", "text": (
                    f"user_goal must be one of {sorted(valid_goals)} "
                    f"if provided (got {user_goal!r})."
                )}],
                "isError": True,
            }

    # compose_budget (optional, enum-bounded). Bounds the substrate's
    # output volume so an agent with a tight working-memory budget can
    # request a compact reading without losing structural shape. The
    # tier_counts in the divergence envelope still reflect the
    # PRE-slice counts so the agent sees how many absences/clusters/
    # patterns were truncated; a new compose_budget_applied field
    # surfaces the slice level + per-layer truncation counts. Default
    # is "full" so existing callers see no change.
    compose_budget = arguments.get("compose_budget", "full")
    valid_budgets = {"minimal", "standard", "full"}
    if not isinstance(compose_budget, str) or compose_budget not in valid_budgets:
        return {
            "content": [{"type": "text", "text": (
                f"compose_budget must be one of {sorted(valid_budgets)} "
                f"if provided (got {compose_budget!r})."
            )}],
            "isError": True,
        }

    try:
        payload = build_epistemic_payload(
            document_text, source_text=source_text,
            include_divergence=include_divergence,
            domain_hint=domain_hint,
            divergence_rendering=divergence_rendering,
            catalog_version_pin=catalog_version_pin,
            user_context=user_context,
            user_goal=user_goal,
            include_frame_opportunities=include_frame_opportunities,
            compose_budget=compose_budget,
        )
        if prefer_contract_version == 2:
            _apply_v2_only_preference(payload)
    except Exception as exc:
        # Log full detail for operator debugging; return sanitized
        # response to the client. Phase 5 item 7-MCP: the previous
        # response interpolated `{type(exc).__name__}: {exc}` and
        # could leak document content via downstream exception text.
        log(f"frame_check failed: {type(exc).__name__}")
        log(traceback.format_exc())
        return _sanitize_tool_exception(exc, "frame_check_internal_error")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2, ensure_ascii=False),
            }
        ],
        "isError": False,
    }


def _call_frame_compare(arguments: dict) -> dict:
    """Argument validation + dispatch for the frame_compare tool.
    Separated from handle_tools_call so the frame_check validation
    stays short and the compare path can grow its own guards (e.g.
    future: reject near-identical documents that would produce a
    trivially-matching comparison).
    """
    a_text = arguments.get("document_a_text")
    b_text = arguments.get("document_b_text")

    for label, text in (("document_a_text", a_text), ("document_b_text", b_text)):
        if not isinstance(text, str) or not text.strip():
            return _tool_error(
                f"{label} is required and must be a non-empty string."
            )
        if len(text) > MAX_DOCUMENT_CHARS:
            return _tool_error(
                f"{label} exceeds the {MAX_DOCUMENT_CHARS}-character "
                f"limit. Truncate the document before calling."
            )

    a_label = (arguments.get("document_a_label") or "Document A").strip()
    b_label = (arguments.get("document_b_label") or "Document B").strip()
    if len(a_label) > 60 or len(b_label) > 60:
        return _tool_error(
            "Labels must be 60 characters or fewer."
        )
    if not a_label:
        a_label = "Document A"
    if not b_label:
        b_label = "Document B"

    try:
        payload = build_compare_payload(
            a_text, b_text, a_name=a_label, b_name=b_label,
        )
    except Exception as exc:
        # Same Phase 5 item 7-MCP hardening as frame_check: sanitized
        # response to client, full detail in operator logs only.
        log(f"frame_compare failed: {type(exc).__name__}")
        log(traceback.format_exc())
        return _sanitize_tool_exception(exc, "frame_compare_internal_error")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2, ensure_ascii=False),
            }
        ],
        "isError": False,
    }


# ── Dispatch loop ─────────────────────────────────────────────────

_HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
    "resources/list": handle_resources_list,
    "resources/read": handle_resources_read,
    "prompts/list": handle_prompts_list,
    "prompts/get": handle_prompts_get,
}


def dispatch(request: dict) -> dict | None:
    """Return the response dict for a JSON-RPC request, or None for
    notifications (no response expected).

    Per JSON-RPC 2.0 §4.2 params MUST be Structured (Array or
    Object) when present. This server accepts Object only because
    every method on the surface expects named parameters. A
    non-Object params is rejected with ERR_INVALID_PARAMS so a
    misbehaving client gets a precise diagnosis (the dispatcher
    surfaces the shape violation directly) instead of an internal-
    error reply that would mask the real cause downstream in the
    handler.
    """
    req_id = request.get("id")
    method = request.get("method")
    raw_params = request.get("params")

    # Notifications have no id. Standard MCP notifications the client
    # may send during the session. We acknowledge and do nothing.
    if req_id is None:
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        # Unknown notification: silent drop (per JSON-RPC spec).
        return None

    # Method must be a non-empty string. A non-string method (list,
    # dict, int) is unhashable or unindexable against _HANDLERS;
    # surfacing it as METHOD_NOT_FOUND keeps the dispatcher's wire
    # contract clean (no -32603 leak for malformed requests).
    if not isinstance(method, str):
        return _error(
            req_id, ERR_METHOD_NOT_FOUND,
            f"Method not found: {method!r}",
        )

    # Validate params shape: Object (dict) only, or absent (None).
    # An Array or scalar would crash the handler's params.get(...)
    # downstream; reject early with the precise JSON-RPC code.
    if raw_params is None:
        params = {}
    elif isinstance(raw_params, dict):
        params = raw_params
    else:
        return _error(
            req_id, ERR_INVALID_PARAMS,
            f"params must be a JSON object; got "
            f"{type(raw_params).__name__}",
        )

    if method == "ping":
        return _response(req_id, {})

    handler = _HANDLERS.get(method)
    if handler is None:
        return _error(
            req_id,
            ERR_METHOD_NOT_FOUND,
            f"Method not found: {method}",
        )

    try:
        result = handler(params)
    except ValueError as exc:
        # Caller-side error: bad URI, bad argument, unknown scheme.
        # ERR_INVALID_PARAMS (not ERR_INTERNAL) so a client can
        # distinguish "I asked for something that does not exist" from
        # "the server crashed."
        log(f"handler {method} invalid params: {exc}")
        return _error(req_id, ERR_INVALID_PARAMS, str(exc))
    except FileNotFoundError as exc:
        # Caller asked for a resource that this deploy does not have
        # (for example, calibration results absent on a fresh clone).
        # Surfaced as invalid-params with the specific filename so the
        # client can decide whether to retry, re-list, or give up.
        log(f"handler {method} not found: {exc}")
        return _error(req_id, ERR_INVALID_PARAMS, str(exc))
    except Exception as exc:
        log(f"handler {method} raised: {exc}")
        log(traceback.format_exc())
        return _error(
            req_id, ERR_INTERNAL,
            f"Internal error in {method}: {type(exc).__name__}",
        )
    return _response(req_id, result)


def main() -> int:
    """Read JSON-RPC messages from stdin line by line, dispatch, write
    responses to stdout. Runs until stdin closes.
    """
    log(
        f"starting on protocol {PROTOCOL_VERSION}, "
        f"server {SERVER_NAME} v{SERVER_VERSION}"
    )
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"malformed JSON: {exc}")
            _send(_error(None, ERR_PARSE, "Parse error"))
            continue

        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            _send(_error(
                request.get("id") if isinstance(request, dict) else None,
                ERR_INVALID_REQUEST,
                "Invalid JSON-RPC request (missing jsonrpc=2.0)",
            ))
            continue

        response = dispatch(request)
        if response is not None:
            _send(response)

    log("stdin closed, exiting")
    return 0


# ── CLI version mode ──────────────────────────────────────────────

def _install_version_info() -> dict:
    """Gather one-line install fingerprint for `--version`.

    Returns a dict with SERVER_VERSION, git SHA, FVS library version,
    validation-corpus hash, Python version, and the absolute script
    path. Every field has a graceful fallback so running this on a
    partial clone (no .git, no VERSION file, no validation tree)
    still produces useful output rather than a traceback.
    """
    import subprocess
    import hashlib
    import platform

    info: dict = {
        "server_version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "script_path": os.path.abspath(__file__),
        "python_version": platform.python_version(),
    }

    # git SHA (short). Detection chain:
    #   1. `git rev-parse` from _SCRIPT_DIR: works in dev clones.
    #   2. pipeline_version.txt in _SCRIPT_DIR: works in Docker and
    #      in any pip-installable package that bakes the SHA at
    #      build time (Dockerfile lines 67-75 already write this
    #      file via ARG GIT_SHA=$(git rev-parse --short HEAD)).
    #   3. "unknown" for shallow clones or packages without bake-time SHA.
    # Without step 2, every containerized or pip-installed run
    # reports git_sha=unknown even though the build knew the SHA.
    info["git_sha"] = "unknown"
    try:
        result = subprocess.run(
            ["git", "-C", _SCRIPT_DIR, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            info["git_sha"] = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if info["git_sha"] == "unknown":
        pipeline_version_path = os.path.join(_SCRIPT_DIR, "pipeline_version.txt")
        try:
            with open(pipeline_version_path, "r", encoding="utf-8") as f:
                baked = f.read().strip()
            if baked and baked != "unknown":
                info["git_sha"] = baked
        except OSError:
            pass

    # Check for uncommitted changes. A stale install running against
    # a repo with uncommitted work should surface that state.
    try:
        result = subprocess.run(
            ["git", "-C", _SCRIPT_DIR, "status", "--porcelain"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        info["git_dirty"] = bool(result.stdout.strip()) if result.returncode == 0 else False
    except (OSError, subprocess.TimeoutExpired):
        info["git_dirty"] = False

    # FVS library version from the VERSION file. Falls back to
    # "unknown" when the file is missing (shallow clone scenarios).
    version_path = os.path.join(
        _DATA_ROOT, "data", "frame_library", "VERSION",
    )
    try:
        with open(version_path, "r", encoding="utf-8") as f:
            info["frame_library_version"] = f.read().strip() or "unknown"
    except OSError:
        info["frame_library_version"] = "unknown"

    # Validation-corpus hash. Matches the formula used by
    # validation/decision_readiness/aggregate_corpus_findings.py
    # _corpus_state_hash so this `--version` field lines up with
    # the hash suffix on aggregate run directories. Inlined (not
    # imported) to keep the CLI lightweight and decoupled from the
    # validation package.
    if os.path.isdir(_CORPUS_ENTRIES_DIR):
        h = hashlib.sha256()
        slug_count = 0
        for root, dirs, files in os.walk(_CORPUS_ENTRIES_DIR):
            dirs.sort()
            for name in sorted(files):
                if name == "document.md":
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, _CORPUS_ENTRIES_DIR)
                h.update(rel.encode("utf-8"))
                h.update(b"\0")
                try:
                    with open(full, "rb") as f:
                        h.update(f.read())
                except OSError:
                    pass
                h.update(b"\0")
            if root == _CORPUS_ENTRIES_DIR:
                slug_count = sum(
                    1 for d in dirs
                    if os.path.isdir(os.path.join(root, d))
                )
        info["corpus_hash"] = h.hexdigest()[:12]
        info["corpus_slugs"] = slug_count
    else:
        info["corpus_hash"] = "no-corpus"
        info["corpus_slugs"] = 0

    return info


_HELP_TEXT = """\
frame-check MCP server

USAGE
  python3 mcp_server.py [FLAG]

FLAGS
  (no flag)       Run as MCP server over stdio (JSON-RPC 2.0,
                  protocol version 2024-11-05). Expected usage from
                  Claude Desktop, Cursor, or any MCP-compatible
                  client that speaks stdio.
  --test          Offline sanity check. Bypasses stdio; runs the
                  deterministic analysis pipeline on a canned
                  finance-domain sample and pretty-prints the full
                  epistemic payload plus a frame_compare example,
                  a resources/list sample, and a prompts/list
                  sample. Useful for verifying pipeline wiring
                  without an MCP client. Triggers FVS match
                  detection on the sample so install-verification
                  sees the headline capability demonstrated.
  --version, -V   Print a one-line install fingerprint with
                  server_version, protocol, git_sha (+dirty flag
                  when the working tree has uncommitted changes),
                  frame_library_version, corpus_slugs, corpus_hash,
                  python version, and absolute script path. Use
                  before a session that depends on recent repo
                  changes to confirm the configured MCP server is
                  the expected one. The corpus_hash matches the
                  suffix on the most recent
                  validation/decision_readiness/results/{date}-{hash}/
                  run directory when the validation tree is present.
  --help, -h      Print this help and exit.

STARTUP AND TROUBLESHOOTING
  If the server does not respond or does not show up in the MCP
  client: run `python3 mcp_server.py --test` first. A working test
  run means the pipeline wiring is correct; a failed test run
  means no MCP client will succeed either. See
  MCP_SERVER.md for troubleshooting:
  - config path per platform (macOS / Windows / Linux)
  - absolute paths required (relative paths and `~` do not expand)
  - Python 3.10+ required (`str | None` syntax)
  - stderr logs labeled `[frame-check-mcp]`
  - empty log means the server never started (check the command path)

RESOURCES
  Public docs:   https://frame.clarethium.com
  Methodology:   https://frame.clarethium.com/corpus/methodology/
  Repo:          https://github.com/lluvr/frame-check-mcp
"""


def _cli_help() -> int:
    """Print usage and exit. No stdio side effects."""
    print(_HELP_TEXT, end="")
    return 0


def _cli_version() -> int:
    """Print a one-line install fingerprint for stale-install checks.

    The operator runs `python3 mcp_server.py --version` before a
    Claude Desktop session they care about, compares against repo
    HEAD, and knows whether the configured server is current. The
    single-line format is grep-friendly; the header line names the
    server for disambiguation when multiple MCP servers are
    installed.
    """
    info = _install_version_info()
    # Header line plus a single space-delimited key=value line so
    # the output is both human-readable and scriptable.
    print(f"frame-check mcp_server v{info['server_version']}")
    dirty = "+dirty" if info.get("git_dirty") else ""
    fields = [
        f"server_version={info['server_version']}",
        f"protocol={info['protocol_version']}",
        f"git_sha={info['git_sha']}{dirty}",
        f"frame_library_version={info['frame_library_version']}",
        f"corpus_slugs={info['corpus_slugs']}",
        f"corpus_hash={info['corpus_hash']}",
        f"python={info['python_version']}",
        f"script={info['script_path']}",
    ]
    print(" ".join(fields))
    return 0


# ── CLI test mode ─────────────────────────────────────────────────

_SAMPLE_DOC = (
    "## NVIDIA Q3 Update\n\n"
    "NVIDIA reported record quarterly revenue of $18.12 billion "
    "in Q3 FY2024, up 206% year over year. Data center revenue "
    "reached $14.51 billion on unprecedented demand for AI "
    "accelerators. Gaming segment revenue expanded 15% as the "
    "installed base continues its upward trajectory. Hyperscaler "
    "customers, enterprise AI buyers, and sovereign-cloud "
    "operators are driving orders across every product line. "
    "Industry analysts attribute the expansion to the company's "
    "CUDA ecosystem lock-in and platform-level moat. The "
    "automotive and robotics segments accelerated quarter over "
    "quarter, with design wins compounding through the pipeline. "
    "Continued adoption across hyperscalers remains the dominant "
    "theme. Forward demand visibility has never been stronger, "
    "and the installed base continues to grow."
)

_SAMPLE_SOURCE = (
    "## Q3 FY2024 Results\n"
    "Revenue: $18.12 billion, up 206% YoY. Data Center: "
    "$14.51 billion, up 279%. Gaming: $2.86 billion, up 15%. "
    "Gross margin: 74.0%. Operating income: $10.42 billion."
)

_SAMPLE_COMPARE_B = (
    "## Fed Outlook\n\n"
    "The Committee notes that risks to the outlook are elevated. "
    "Growth has moderated in recent months. Inflation remains "
    "somewhat elevated and uncertainty about the outlook persists. "
    "The Committee will carefully assess incoming data."
)


def _cli_test() -> int:
    """Offline sanity check. Bypasses stdio; exercises every MCP
    surface the server exposes (frame_check without source,
    frame_check with source, frame_compare, resources/list,
    resources/read on one sample from each family) and
    pretty-prints the results.

    An operator installing Frame Check into an MCP client runs
    this first. If any of these surfaces fail here, no client
    will succeed either; the failure location is the first debug
    hint. The sections are headed so the output is skimmable.
    """
    print("=== frame_check (default mode: divergence-included, no source_text) ===")
    print(json.dumps(
        build_epistemic_payload(_SAMPLE_DOC), indent=2,
        ensure_ascii=False,
    ))
    print()

    print("=== frame_check (default mode + verification, with source_text) ===")
    print(json.dumps(
        build_epistemic_payload(_SAMPLE_DOC, source_text=_SAMPLE_SOURCE),
        indent=2, ensure_ascii=False,
    ))
    print()

    print("=== frame_compare (NVIDIA vs Fed) ===")
    compare = build_compare_payload(
        _SAMPLE_DOC, _SAMPLE_COMPARE_B,
        a_name="NVIDIA", b_name="Fed",
    )
    # Full compare payload is large; summarise to keep --test scan-
    # able. The full payload is still reachable through tools/call
    # over stdio when a complete inspection is needed.
    print(json.dumps({
        "comparison_summary": {
            "coverage": compare["analysis"]["comparison"]["coverage"],
            "voice_match": compare["analysis"]["comparison"]["voice"]["match"],
            "temporal_match": compare["analysis"]["comparison"]["temporal"]["match"],
            "sourced_pct_delta": (
                compare["analysis"]["comparison"]["epistemic"]
                .get("sourced_pct_delta")
            ),
            "framing_diff_headline": (
                (compare["analysis"]["comparison"]
                 ["framing_differences"] or {}).get("headline")
            ),
        },
        "provenance_layer": compare["provenance"]["analysis_layer"],
        "provenance_cost_usd": compare["provenance"]["analysis_cost_usd"],
    }, indent=2, ensure_ascii=False))
    print()

    # Divergence opt-in path. Exercises FRAME_DIVERGENCE_CONTRACT_v1
    # Part 2 c1.0: include_divergence=True unlocks a top-level
    # `divergence` block plus two `agent_guidance` additions. The
    # operator running --test sees the divergence shape work end-to-
    # end without having to craft a custom JSON-RPC call. Summarised
    # to keep the output scannable; full block is reachable via
    # tools/call over stdio.
    print("=== frame_check (divergence with domain_hint='finance', rendering='list') ===")
    div_payload = build_epistemic_payload(
        _SAMPLE_DOC,
        include_divergence=True,
        domain_hint="finance",
        divergence_rendering="list",
    )
    divergence = div_payload.get("divergence", {}) or {}
    absent = divergence.get("absent_frames", []) or []
    envelope = divergence.get("envelope", {}) or {}
    ag = div_payload.get("agent_guidance", {}) or {}
    print(json.dumps({
        "divergence_summary": {
            "absent_frame_count": len(absent),
            "sample_absent_frame": absent[0] if absent else None,
            "envelope": envelope,
        },
        "agent_guidance_added_keys": [
            k for k in ("how_to_render_divergence", "absence_is_not_prescription")
            if k in ag
        ],
        "provenance_cost_usd": div_payload["provenance"]["analysis_cost_usd"],
    }, indent=2, ensure_ascii=False))
    print()

    print("=== resources/list (URIs advertised on this deploy) ===")
    resources = _list_resources()
    for r in resources:
        print(f"  {r['uri']}  ({r['mimeType']})  {r['name']}")
    print(f"Total resources: {len(resources)}")
    print()

    # Sample one read from each family so the read path is
    # exercised for every URI shape, not just the one the tool
    # tests already cover.
    print("=== resources/read samples (first 120 chars of each) ===")
    sample_uris: list[str] = []
    seen_families: set = set()
    for r in resources:
        family = r["uri"].rsplit("/", 1)[0]
        if family in seen_families:
            continue
        seen_families.add(family)
        sample_uris.append(r["uri"])
    for uri in sample_uris:
        try:
            contents = _read_resource(uri)["contents"][0]
            text = contents["text"].replace("\n", " ")
            print(f"  {uri}")
            print(f"    ({contents['mimeType']}) {text[:120]}...")
        except Exception as exc:
            print(f"  {uri}")
            print(f"    FAILED: {type(exc).__name__}: {exc}")
    print()

    print("=== prompts/list (templates the agent's LLM executes) ===")
    for p in _PROMPTS:
        print(f"  {p['name']}")
        print(f"    {p['description']}")
    print()

    print("=== prompts/get frame_check_my_response (first 200 chars) ===")
    audit = handle_prompts_get({"name": "frame_check_my_response"})
    body = audit["messages"][0]["content"]["text"]
    print(f"  {body[:200]}...")
    print()
    print(
        "=== next ===\n"
        "  If everything above printed without error, the pipeline "
        "wiring is correct and the server will start successfully "
        "when launched over stdio.\n"
        "  Run `python3 mcp_server.py --version` for the one-line "
        "install fingerprint.\n"
        "  Run `python3 mcp_server.py --help` for the full flag "
        "reference.\n"
        "  If you saw an error above, see MCP_SERVER.md "
        "troubleshooting (config path per platform, absolute paths, "
        "Python version, stderr logs)."
    )
    return 0


def cli() -> int:
    """Console-script entry point.

    Parses sys.argv for the optional subcommand flags (--help, --version,
    --test) and dispatches accordingly; falls through to the JSON-RPC
    stdio loop in main() when no subcommand is given. This is the entry
    point pyproject.toml registers as `frame-check-mcp` so an installed
    user can run `frame-check-mcp --version` and get the install
    fingerprint without spawning the stdio server. Direct invocation via
    `python3 mcp_server.py` still goes through the same dispatch via the
    `if __name__ == "__main__"` block below.
    """
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        return _cli_help()
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        return _cli_version()
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        return _cli_test()
    return main()


if __name__ == "__main__":
    sys.exit(cli())
