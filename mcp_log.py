"""Stderr logging primitives for the Framecheck MCP server.

The logging surface has zero internal dependencies on other Frame
Check modules so it sits cleanly at the bottom of the layer cake;
`mcp_server.py` re-exports the public symbols for backward
compatibility.

Stdout is reserved for the JSON-RPC channel on the MCP server;
any diagnostic that prints to stdout breaks the client connection
mid-stream. All diagnostics route through `log()` to stderr. MCP
clients (Claude Desktop, Cursor, etc.) collect and display server
stderr in their per-session log surface, so the operator sees the
diagnostic without it corrupting the JSON-RPC protocol.

The control-character sanitizer is a defense-in-depth fix from the
0.8.0 publish-readiness audit (D2 / D3 conformance docs): a hostile
request (e.g. a resource URI containing ANSI escape sequences)
reaches `log()` via the dispatcher's exception path and the
resolver's not-found path; without escaping, the raw bytes would
render in an operator's terminal viewer if logs are tailed live,
giving the operator a terminal-injection surface even though the
wire JSON-RPC response is safe (JSON encodes control chars per
RFC 8259).
"""

from __future__ import annotations

import sys


# Lazily compiled regex matching ASCII C0 control characters that
# would render as terminal-injection vectors if a log line is
# tailed live in an operator's terminal. CR (0x0D), LF (0x0A), and
# TAB (0x09) are preserved because they are legitimate newline /
# indentation in multi-line log messages (e.g.
# `traceback.format_exc()` output). DEL (0x7F) is included in the
# escape set per the same threat model.
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
        f"[framecheck-mcp] {_sanitize_log_message(msg)}",
        file=sys.stderr, flush=True,
    )


__all__ = ["log", "_sanitize_log_message"]
