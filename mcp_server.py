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
SERVER_VERSION = "0.8.5"

# ── Logging ────────────────────────────────────────────────────────
#
# The logging primitives moved to `mcp_log.py` 2026-04-29 as Step 1
# of the mcp_server decomposition (Item 4 follow-up plan). Re-imported
# here so existing tests that read `mcp_server.log` or
# `mcp_server._sanitize_log_message` continue to resolve without
# modification. New code should import directly from `mcp_log`
# (`from mcp_log import log`).
from mcp_log import (
    log,
    _sanitize_log_message,
)


# ── Resource layer (moved to mcp_resources.py 2026-04-29) ─────────
#
# The resource-discovery, path-resolution, library/example/transmission
# entry listings, _list_resources, _read_resource, signal-strength
# classification, and content-hash primitives all live in
# `mcp_resources.py` since the Step 2 decomposition. mcp_server.py
# imports them back so existing callers (compose-layer functions
# still here, tests that read `mcp_server.<symbol>`) continue to
# resolve.
#
# Module-attribute access pattern for mutable cache state: the four
# caches `_FRAME_STATUSES`, `_FRAME_LIBRARY_VERSION`, `_FRAME_VERSIONS`,
# `_FRAME_ADJACENCY` are populated lazily by `_ensure_caches`. They
# are MUTATED post-import. Compose code reads them via the
# `_resources_mod` reference below so attribute lookup happens late
# (at the point of read, not at import time). A direct
# `from mcp_resources import _FRAME_VERSIONS` would capture None.
import mcp_resources as _resources_mod
from mcp_resources import (
    RESOURCE_SCHEME,
    _LIBRARY_DIR,
    _LIBRARY_V3_DIR,
    _WORKED_EXAMPLES_DIR,
    _TRANSMISSIONS_DIR,
    _METHODOLOGY_PATH,
    _CALIBRATION_RESULTS_DIR,
    _AGGREGATE_RESULTS_DIR,
    _CORPUS_ENTRIES_DIR,
    _SPEC_FD_V1_PART1_PATH,
    _SPEC_FD_V1_PART2_PATH,
    _SIGNAL_STRENGTH_THRESHOLDS,
    _signal_strength_for,
    _content_hash,
    _ensure_caches,
    _parse_frame_adjacency,
    _spec_fd_v1_parts,
    _spec_fd_v1_index_markdown,
    _library_entries,
    _library_v3_entries,
    _worked_example_entries,
    _transmission_entries,
    _transmission_path,
    _transmissions_readme_path,
    _worked_example_path,
    _library_entry_path,
    _library_index_path,
    _worked_examples_readme_path,
    _calibration_runs,
    _calibration_run_path,
    _best_calibration_run,
    _corpus_entry_slugs,
    _find_corpus_entry_path,
    _find_corpus_pair_path,
    _find_latest_aggregate,
    _list_resources,
    _read_resource,
    _read_frame_library_version,
    _parse_frame_statuses,
    _library_entry_ref,
    _dimensions_affecting,
)


# ── Schema layer (moved to mcp_schema.py 2026-04-29) ──────────────
#
# Tool definitions, prompt templates, and the small helpers that
# translate user-intent prompt arguments into MCP-parameter values
# now live in `mcp_schema.py`. The schema layer has no runtime
# dependencies on other Frame Check modules; the protocol layer
# (still in mcp_server.py at Step 3 boundary) imports the
# definitions for tools/list, prompts/list, and prompts/get
# dispatch, plus MAX_DOCUMENT_CHARS / MAX_SOURCE_CHARS for input
# validation in handle_tools_call.
from mcp_schema import (
    MAX_DOCUMENT_CHARS,
    MAX_SOURCE_CHARS,
    _DOMAIN_HINT_ENUM,
    _DIVERGENCE_RENDERING_ENUM,
    _SPEC_VERSION,
    _PROMPT_DEPTH_VALUES,
    _PROMPT_GOAL_VALUES,
    _PROMPT_QUESTIONS_VALUES,
    _prompt_messages,
    _translate_prompt_arguments,
    _populate_prompt_body,
    _PROMPT_SELF_AUDIT,
    _PROMPT_AI_RESPONSE_AUDIT,
    _PROMPT_CHALLENGE_DOCUMENT,
    _PROMPT_EXPLAIN_FRAMING,
    _USER_INTENT_PROMPT_ARGS,
    _PROMPTS,
    _FRAME_CHECK_TOOL,
    _FRAME_COMPARE_TOOL,
    _TOOLS,
)


# ── Compose layer (moved to mcp_compose.py 2026-04-29) ────────────
#
# The full compose layer moved to `mcp_compose.py` across Steps 4a +
# 4b + 4c of the mcp_server decomposition: leaf helpers (provenance,
# corpus-context lookups, document-signal aggregator, MCP contract v2
# dimension builders, production-status constants) in 4a; per-level
# construct treatments and the Frame Divergence block in 4b; and the
# top-level payload builders (`build_epistemic_payload`,
# `build_compare_payload`, `_compress_agent_guidance_to_load_bearing`,
# `_build_suggested_next_actions`, `_per_document_core`,
# `_summarize_per_document`) in 4c. After 4c, mcp_server.py retains
# only the JSON-RPC envelope, MCP method handlers, dispatch loop, CLI
# version / test modes, and the test-mode module-attribute proxy. All
# 30 compose-layer names are re-exported here so existing call sites
# and tests that read `mcp_server.<symbol>` continue to resolve.
#
# mcp_compose reads SERVER_VERSION lazily inside _build_provenance,
# not at module top, to avoid a `python mcp_server.py` re-entry
# cycle (mcp_server runs as __main__ in that path; a top-level
# `from mcp_server import SERVER_VERSION` in mcp_compose would
# re-load mcp_server as a second module). See mcp_compose.py module
# docstring for the import-cycle note.
from mcp_compose import (
    PRODUCTION_STATUS,
    PRODUCTION_STATUS_NOTE,
    _build_provenance,
    _frame_corpus_context_or_none,
    _dimension_corpus_context_or_none,
    _corpus_summary_or_none,
    _build_document_signals,
    _build_coverage_v2,
    _build_voice_construct,
    _build_temporal_construct,
    _CLAIM_LEVEL_DETECTOR,
    _CLAIM_LEVEL_CLASSIFIER,
    _CLAIM_LEVEL_LLM_CLASSIFIER,
    _CLAIM_LEVEL_COMPOSED,
    _CLAIM_LEVEL_AGENT_GENERATED,
    _CLAIM_LEVEL_TREATMENTS,
    _apply_v2_only_preference,
    _signal_strength_for_absent_frame,
    _DIMENSION_CLUSTER_READINGS,
    _CLUSTER_MIN_ABSENT,
    _CLUSTER_MIN_CANON_FRACTION,
    _CLUSTER_MIN_DOCUMENT_WORDS,
    _CLUSTER_TIER_ORDER,
    _extract_teaching_question,
    _build_absence_clusters,
    _build_divergence_block,
    _compress_agent_guidance_to_load_bearing,
    _build_suggested_next_actions,
    build_epistemic_payload,
    _per_document_core,
    _summarize_per_document,
    build_compare_payload,
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


# Resources (library, methodology, calibration, Frame Divergence
# v1 spec) live in mcp_resources.py since Step 2 of the
# decomposition; the architectural rationale (tools are verbs,
# resources are nouns; resource URIs are stable citation targets
# agents can hand back to a user) is documented there.


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
    # surfaces the slice level + per-layer truncation counts.
    #
    # Default is "standard": empirical measurement showed full=111KB,
    # standard=61KB (45% smaller), minimal=53KB on the same call. The
    # 4 agent_guidance keys dropped at standard (composition_discipline,
    # how_to_render_divergence, how_to_map_user_intent, suggested_response_shape)
    # are large prose surfaces the agent rarely re-reads per call; their
    # load-bearing content survives via shorter sibling notes. Callers
    # that need the full inline tables (claim_level_treatments, etc.)
    # opt in via compose_budget="full". Tight-loop callers stay at
    # "standard" without paying the full-mode tax on every invocation.
    compose_budget = arguments.get("compose_budget", "standard")
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


# ── Module-attribute proxy for tests ──────────────────────────────
#
# A handful of tests read `mcp_server._FRAME_ADJACENCY`,
# `mcp_server._FRAME_VERSIONS`, etc. directly. After the Step 2
# decomposition the four cache-state symbols live on
# `mcp_resources` and are populated lazily by `_ensure_caches`.
# A plain `from mcp_resources import _FRAME_ADJACENCY` would
# capture None at import time and never see the populated value.
#
# Module-level `__getattr__` (PEP 562, Python 3.7+) gives tests
# late-binding attribute access without a heavier descriptor or
# proxy object. Reading `mcp_server._FRAME_ADJACENCY` resolves
# `__getattr__("_FRAME_ADJACENCY")` which forwards to
# `mcp_resources._FRAME_ADJACENCY` (the live value).
def __getattr__(name: str):
    if name in {
        "_FRAME_STATUSES",
        "_FRAME_LIBRARY_VERSION",
        "_FRAME_VERSIONS",
        "_FRAME_ADJACENCY",
    }:
        return getattr(_resources_mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


if __name__ == "__main__":
    sys.exit(cli())
