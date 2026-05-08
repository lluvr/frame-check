"""
Frame Check version constants.

Two version axes:

  FRAME_CHECK_VERSION
    The Frame Check methodology brand version. Tied to the
    FRAME_DIVERGENCE_CONTRACT_v1 c1.0 spec: bumps when the methodology
    contract version bumps (c1.1 -> 1.1.0; c2.0 -> 2.0.0; etc.).
    Stamped into telemetry events, CITATION.cff, and the MCP
    provenance.frame_check_version field so an agent or academic
    citation resolves against the methodology snapshot that produced
    the analysis.

    Decoupled from MCP wheel SERVER_VERSION (mcp_server.py): a wheel
    patch (bug fix, perf improvement, schema-additive change) bumps
    SERVER_VERSION without bumping the brand; a brand bump (rare,
    happens on contract revisions) does not require re-cutting the
    wheel.

    Decoupled from pyproject [project] version: pyproject is the
    packaging artifact version (per-release), independent of brand
    semantic. A wheel can ship `frame-check-mcp 0.8.x` against
    methodology brand `1.0.0`; the two strings answer different
    questions.

    Pre-2026-04-28 stayed at 0.1.0 across the dev arc; bumped to
    1.0.0 on 2026-04-28 when FRAME_DIVERGENCE_CONTRACT_v1 c1.0 + FVS
    library v3 + calibration corpus + worked-examples + methodology
    paper + public PyPI lift + SECURITY v2 + DCO + leakage audit
    closed the 1.0-discipline bar. Telemetry events carry a clean
    discontinuity at this commit; longitudinal queries that span the
    boundary should pivot on PIPELINE_VERSION (which always uniquely
    identifies the running code) rather than treating
    FRAME_CHECK_VERSION as continuous across the bump.

  PIPELINE_VERSION
    Short git commit SHA of the running code. Bumps on every commit.
    Lets telemetry queries correlate schema changes with code changes:
    longitudinal queries that compare framing or verification values
    across time must filter by this field.

Detection precedence for PIPELINE_VERSION:
  1. PIPELINE_VERSION env var (set explicitly, e.g., by a deploy script).
  2. A pipeline_version.txt file alongside this module (baked at build time).
  3. `git rev-parse --short HEAD` from the module directory (works in dev).
  4. The literal string "unknown" (last resort, marks events as un-correlatable).

The fallback chain matters because the production Dockerfile does not
install git and Fly's image build runs from a context that may or may
not include .git. Step 2 (a baked file) is the production-ready answer
for Phase 1.3 deployment; until then, dev environments use step 3 and
production deploys log "unknown" until the deploy script writes the
file.

SCHEMA_VERSION belongs to the corpus event schema. Bumps on breaking
changes only; additive changes do not bump.

API_SCHEMA_VERSION belongs to the public HTTP/JSON API envelope (the
shape returned by /api/profile and the SSE `start` event from
/api/compare-stream). It is the contract programmatic consumers
(MCP server, agent frameworks, CI bots) branch on. Same bump
discipline as SCHEMA_VERSION: additive changes (new optional fields)
do not bump; breaking changes (renames, removals, type changes,
semantic shifts of existing fields) bump the integer.

Deliberately separate from FRAME_CHECK_VERSION so an application
release can ship without forcing API consumers to recompute their
parsers, and so an API contract bump (rare) can happen without
suggesting that every other surface changed.
"""

import os
import subprocess
from pathlib import Path

FRAME_CHECK_VERSION = "1.0.0"

SCHEMA_VERSION = 1

API_SCHEMA_VERSION = 1


def _detect_pipeline_version() -> str:
    """Resolve the pipeline version using the documented fallback chain.

    Called once at module import time. The result is cached in
    PIPELINE_VERSION below; callers should read that constant instead
    of re-running the detection.
    """
    env = os.environ.get("PIPELINE_VERSION", "").strip()
    if env:
        return env

    here = Path(__file__).resolve().parent
    baked = here / "pipeline_version.txt"
    if baked.is_file():
        try:
            text = baked.read_text(encoding="utf-8").strip()
            if text:
                return text
        except OSError:
            pass

    # Last resort: ask git directly. Works in dev where .git is present
    # and the git binary is installed. Times out fast so a missing or
    # broken git installation cannot delay startup noticeably.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if sha:
                return sha
    except (OSError, subprocess.SubprocessError):
        pass

    return "unknown"


PIPELINE_VERSION = _detect_pipeline_version()
