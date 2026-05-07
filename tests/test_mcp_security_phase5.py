"""Phase 5 tests for mcp_server.py security hardening (items 7-MCP,
8-MCP per V4_2_GAP_INVENTORY_v1.md).

Two concerns:

  1. Provenance engine identity. MCP provenance must carry
     framing_engine == "layer_a" and engine_version in its own
     semver space so saved-analysis readers can branch on the
     engine family without knowing every point release. This
     matches the web surface's fallback-path convention (both
     emit framing_engine="layer_a" when running the deterministic
     regex stack).

  2. Attacker-hardened exception responses. The frame_check and
     frame_compare tool error paths previously interpolated
     `f"{type(exc).__name__}: {exc}"` directly into the response,
     which could leak document content (if a downstream detector
     embedded a snippet in its exception message), internal paths,
     or class hierarchy to any caller. Sanitized responses carry
     only a stable error code plus a generic user-safe message.

Both items are closed for Phase 5 of the V4.2-default launch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import mcp_server  # noqa: E402


_DOC_SAMPLE = (
    "The Committee notes that risks to the outlook are elevated. "
    "Growth has been solid in recent quarters. Uncertainty about "
    "supply-side developments persists."
)


# ── Item 8-MCP: engine identity fields in provenance ───────────────

def test_provenance_carries_framing_engine_layer_a():
    """MCP server runs only Layer A server-side (regex detectors +
    clarethium_measure). The V4.2 step is caller-side per Rec I. So
    the MCP provenance block must name framing_engine="layer_a" for
    symmetry with the web surface's Layer A fallback path.
    """
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    p = payload["provenance"]
    assert p.get("framing_engine") == "layer_a", (
        f"framing_engine must be 'layer_a' for MCP server-side output, "
        f"got {p.get('framing_engine')!r}"
    )


def test_provenance_carries_engine_version_layer_a_semver():
    """Layer A has its own semver space (independent of V4.2's 4.2.x).
    Current value is 1.0.0; this test pins the value so a silent
    drift is caught."""
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    p = payload["provenance"]
    assert p.get("engine_version") == "1.0.0", (
        f"engine_version must be '1.0.0' (Layer A semver), "
        f"got {p.get('engine_version')!r}"
    )
    # Strict semver format: MAJOR.MINOR.PATCH, all non-negative ints,
    # no 'v' prefix in the value.
    parts = p["engine_version"].split(".")
    assert len(parts) == 3
    for part in parts:
        assert part.isdigit()
    assert not p["engine_version"].startswith("v")


def test_provenance_engine_identity_is_consistent_with_web_fallback():
    """Both surfaces emit framing_engine='layer_a' when running the
    deterministic Layer A stack: MCP server-side (always, by design)
    and web (only during V4.2 fallback). A saved-analysis reader that
    branches on framing_engine sees identical values across the two
    surfaces when Layer A is in effect.
    """
    framing_sdk = pytest.importorskip(
        "framing_sdk",
        reason="framing_sdk is the web-side fallback wrapper; absent on the public mirror",
    )
    payload = mcp_server.build_epistemic_payload(_DOC_SAMPLE)
    web_fallback = framing_sdk._build_fallback_response("llm_unavailable")
    assert (
        payload["provenance"]["framing_engine"]
        == web_fallback["meta"]["framing_engine"]
        == "layer_a"
    )
    assert (
        payload["provenance"]["engine_version"]
        == web_fallback["meta"]["engine_version"]
        == "1.0.0"
    )


# ── Item 7-MCP: attacker-hardened exception responses ──────────────

def test_frame_check_tool_error_response_is_sanitized():
    """When build_epistemic_payload raises an unexpected exception
    inside _call_frame_check / handle_tools_call, the client response
    must NOT include the exception type name, message, or any
    interpolated internal state. Stable error code + generic message
    only."""
    sensitive_message = (
        "Document contained </user_document> at position 1234. "
        "Context snippet: 'OFFENDING-USER-CONTENT-SHOULD-NOT-LEAK'. "
        "File path: /home/llucic/frame-check/engine_internal.py"
    )

    def boom(*args, **kwargs):
        raise RuntimeError(sensitive_message)

    with patch.object(mcp_server, "build_epistemic_payload", side_effect=boom):
        response = mcp_server.handle_tools_call({
            "name": "frame_check",
            "arguments": {"document_text": "short document"},
        })

    assert response.get("isError") is True
    response_text = response["content"][0]["text"]
    # Sanitized response must NOT contain the leaked content in ANY form
    assert "OFFENDING-USER-CONTENT-SHOULD-NOT-LEAK" not in response_text
    assert "engine_internal.py" not in response_text
    assert "position 1234" not in response_text
    assert "RuntimeError" not in response_text
    # Must carry the stable error code and a user-safe message
    parsed = json.loads(response_text)
    assert parsed.get("error") == "frame_check_internal_error"
    assert "message" in parsed
    assert len(parsed["message"]) > 0


def test_frame_compare_tool_error_response_is_sanitized():
    """Same sanitization invariant applies to the frame_compare tool."""
    sensitive_message = (
        "Comparison internal state: {'doc_a_content': 'LEAK_CONTENT_A', "
        "'doc_b_content': 'LEAK_CONTENT_B'}"
    )

    def boom(*args, **kwargs):
        raise ValueError(sensitive_message)

    with patch.object(mcp_server, "build_compare_payload", side_effect=boom):
        response = mcp_server._call_frame_compare({
            "document_a_text": "document a",
            "document_b_text": "document b",
        })

    assert response.get("isError") is True
    response_text = response["content"][0]["text"]
    assert "LEAK_CONTENT_A" not in response_text
    assert "LEAK_CONTENT_B" not in response_text
    assert "ValueError" not in response_text
    parsed = json.loads(response_text)
    assert parsed.get("error") == "frame_compare_internal_error"
    assert "message" in parsed


def test_sanitize_tool_exception_has_stable_error_code_and_generic_message():
    """Unit test the helper directly: for each known error code the
    response carries that code plus a hardcoded message from the
    _MCP_TOOL_ERROR_MESSAGES table, never interpolating anything from
    the exception itself."""
    evil = KeyError("user-submitted-key-with-content-shouldnt-leak")
    for code in ("frame_check_internal_error", "frame_compare_internal_error"):
        resp = mcp_server._sanitize_tool_exception(evil, code)
        assert resp.get("isError") is True
        text = resp["content"][0]["text"]
        assert "user-submitted-key-with-content-shouldnt-leak" not in text
        parsed = json.loads(text)
        assert parsed["error"] == code
        assert parsed["message"] == mcp_server._MCP_TOOL_ERROR_MESSAGES[code]


def test_sanitize_tool_exception_unknown_code_still_safe():
    """Defense-in-depth: an unknown error code still produces a
    content-free response. A future caller using a code that isn't
    in the table must not cause us to fall through to unsafe
    interpolation."""
    resp = mcp_server._sanitize_tool_exception(
        RuntimeError("leaky-content"), "unknown_code_xyz",
    )
    text = resp["content"][0]["text"]
    assert "leaky-content" not in text
    assert "RuntimeError" not in text
    parsed = json.loads(text)
    assert parsed["error"] == "unknown_code_xyz"
    assert "internal error" in parsed["message"].lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
