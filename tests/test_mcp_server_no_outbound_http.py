"""MCP tool surface boundary discipline: zero outbound HTTP.

Pins the agent-server design boundary that Framecheck's MCP tools
(frame_check + frame_compare) make zero outbound network calls
during their runtime traversal. The server's job is deterministic
structural analysis (regex/feature detection, frame library, claim
extraction, cross-document framing comparison); the agent's job is
adaptive work that may include external source fetching. A future
refactor that re-couples I/O into the server-side path (e.g., adds
a verify_via_brave call inside a substrate detector, or accidentally
imports a module that opens a socket at import-time) fails this
test at PR time rather than via runtime surprise on a pipx-installed
wheel where the user has no API keys configured.

The test patches the lowest common HTTP path -- `socket.socket.connect`
-- so any TCP connection attempt (urllib, requests, urllib3, raw
socket, anything that ultimately calls connect()) is captured. The
patch is a no-op replacement (records the address tuple but does
NOT raise) so the test fails cleanly with the call list rather
than with a confusing exception traceback that obscures which
code path attempted the connection.

The boundary holds today because mcp_compose.build_epistemic_payload
and build_compare_payload route through deterministic substrate
modules (frame_library.suggest_frames, framing.detect_*,
claim_analysis.analyze_claims, comparison._build_structural_framing_data)
none of which call out to external services. The wheel bundles
source_network.py transitively (because comparison.analyze_model
imports it at module load) but neither MCP tool entry point reaches
that code; the bundling is dead-import weight, not runtime leakage.

When `verification_handoff` lands (FRAME_DIVERGENCE_CONTRACT_v1
c1.0 -> c1.1 minor bump), the new top-level field carries
candidate provider hints for the agent to fetch from --
but the SERVER does NOT fetch; the agent does. So this test also
covers verification_handoff after Phase 1 lands without
modification.

Per the discipline pattern in MCP_SERVER.md (line 369: "not invoke
any LLM for divergence; V4.2 judgment is delegated to the caller's
agent model"; line 417: "Framecheck's MCP server does not invoke
an external LLM"): the LLM-judgment delegation is the same
architectural pattern as the verification delegation; this test
extends the pin from LLM-only to all-network-I/O.
"""

import socket
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent


def _read_fixture(slug: str) -> str:
    """Read an adversarial-fixture document by slug. Used by the
    boundary tests below to keep the assertions readable; if a
    fixture moves or is renamed, this helper raises FileNotFoundError
    instead of yielding a confusing AssertionError downstream.

    Falls back to `data/worked_examples/<slug>.md` when the adversarial
    fixture is absent: `data/adversarial_fixtures/` is upstream-only
    (excluded from the public extract per `setup.py::_should_skip` as
    a research-snapshot subdirectory; not a runtime resource), but
    `data/worked_examples/` ships publicly. The two corpora are
    structurally similar for substrate-traversal purposes, so the
    fallback preserves the architectural-boundary invariant the test
    pins on both surfaces. Caller passes the upstream slug; the
    fallback names a public-shipping document.
    """
    primary = REPO / "data" / "adversarial_fixtures" / slug / "document.md"
    if primary.exists():
        return primary.read_text()
    fallback_map = {
        "sales_pitch_as_analysis": "grok-on-nvidia-earnings-2026.md",
        "instruction_without_troubleshooting": "fomc-statement-march-2026.md",
    }
    fallback_name = fallback_map.get(slug)
    if fallback_name is None:
        raise FileNotFoundError(f"No public fallback registered for slug {slug!r}")
    fallback = REPO / "data" / "worked_examples" / fallback_name
    return fallback.read_text()


def _make_capturing_connect():
    """Build a no-op `socket.socket.connect` replacement that
    records every call's address argument. Returns (replacement,
    captured_list); the caller asserts captured_list is empty
    after running the MCP tool path.

    Why no-op (vs raise): if the patched function raises, the
    underlying MCP code path crashes with a confusing exception
    traceback that may obscure which substrate detector tried to
    connect. The capture-list pattern lets the test fail with a
    precise message naming the address tuple(s) and lets the test
    author add a print before the assertion to introspect call
    sites if needed.
    """
    captured: list = []

    def _capture(self, address):
        captured.append(address)

    return _capture, captured


def test_frame_check_makes_zero_outbound_socket_connect():
    """frame_check (MCP single-document tool entry point) makes
    no `socket.socket.connect` calls during its substrate
    traversal. Pins the boundary against future refactors that
    accidentally re-couple agent-side work (verification, web
    fetching) into the server-side deterministic path.

    Test fixture: `sales_pitch_as_analysis` (fires FVS-011
    Stakeholder Frame, exercises the full
    coverage/voice/temporal/epistemic substrate path plus the
    frame_library suggest_frames lookup with a non-empty match
    set; representative typical-flow coverage).
    """
    import mcp_compose

    capture_fn, captured = _make_capturing_connect()
    text = _read_fixture("sales_pitch_as_analysis")

    with mock.patch.object(socket.socket, "connect", capture_fn):
        payload = mcp_compose.build_epistemic_payload(document_text=text)

    assert payload is not None, "build_epistemic_payload returned None"
    assert payload.get("analysis"), (
        "frame_check payload missing `analysis` block; sanity check "
        "that the substrate path actually ran"
    )
    assert not captured, (
        f"frame_check attempted {len(captured)} outbound socket "
        f"connection(s); the agent-server boundary is broken. "
        f"Connection target(s): {captured!r}. Investigate which "
        f"substrate detector (or transitively-imported module) "
        f"is making the call; the MCP server's runtime path is "
        f"meant to be deterministic structural analysis only, "
        f"with verification/source-fetching delegated to the "
        f"caller's agent."
    )


def test_frame_compare_makes_zero_outbound_socket_connect():
    """frame_compare (MCP two-document tool entry point) makes
    no `socket.socket.connect` calls during its substrate
    traversal. Same boundary as frame_check above; covers the
    cross-document path (`_per_document_core` x 2 +
    `_build_structural_framing_data`) that does NOT reuse
    `comparison.analyze_model` (which DOES call SN; web-only).
    Pins the architectural separation between the two compare
    paths so a future "DRY" refactor that consolidates them does
    not accidentally pull SN into the MCP path.

    Test fixture pair: sales_pitch_as_analysis (FVS-011 fires) +
    instruction_without_troubleshooting (FVS-007 absence-pattern
    fires). Cross-document fires both present-detected and
    absence-detected emission shapes; representative typical-flow
    coverage of the compare substrate.
    """
    import mcp_compose

    capture_fn, captured = _make_capturing_connect()
    doc_a = _read_fixture("sales_pitch_as_analysis")
    doc_b = _read_fixture("instruction_without_troubleshooting")

    with mock.patch.object(socket.socket, "connect", capture_fn):
        payload = mcp_compose.build_compare_payload(
            doc_a, doc_b,
            a_name="adv:sales_pitch_as_analysis",
            b_name="adv:instruction_without_troubleshooting",
        )

    assert payload is not None, "build_compare_payload returned None"
    assert payload.get("analysis", {}).get("documents"), (
        "frame_compare payload missing `analysis.documents`; sanity "
        "check that the cross-document substrate path actually ran"
    )
    assert payload.get("analysis", {}).get("comparison"), (
        "frame_compare payload missing `analysis.comparison`; sanity "
        "check that the cross-document framing builder ran"
    )
    assert not captured, (
        f"frame_compare attempted {len(captured)} outbound socket "
        f"connection(s); the agent-server boundary is broken. "
        f"Connection target(s): {captured!r}. Investigate which "
        f"substrate detector (or transitively-imported module) "
        f"is making the call. The compare path uses "
        f"`mcp_compose._per_document_core` rather than "
        f"`comparison.analyze_model` precisely to avoid the SN "
        f"call; a regression here likely means the consolidation "
        f"was reverted."
    )
