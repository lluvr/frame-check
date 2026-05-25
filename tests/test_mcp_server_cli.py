"""Tests for the ``mcp_server.py`` CLI surfaces and main loop.

The MCP-protocol primitives (initialize, tools/*, resources/*,
prompts/*) are exercised in ``test_mcp_server.py`` and the
adversarial harness. This file targets the lower-coverage entry
points that wrap the protocol layer:

  - ``cli()``: argv dispatch (--help / --version / --test / default).
  - ``_cli_help()``: prints usage banner.
  - ``_cli_version()``: prints install fingerprint.
  - ``_install_version_info()``: gathers the fingerprint dict with
    graceful fallback for missing .git / VERSION / corpus.
  - ``main()``: JSON-RPC stdio loop.
  - ``__getattr__``: late-binding proxy to mcp_resources cache state.

Each is exercised directly with monkeypatch + capsys; no
subprocess spawn so the tests stay fast and deterministic.
"""

from __future__ import annotations

import io
import json
import sys
from unittest.mock import patch

import pytest

import mcp_server


# ================================================================
# CLI dispatch
# ================================================================


class TestCli:
    """``cli()`` parses sys.argv and routes to the right subcommand
    or falls through to the JSON-RPC stdio loop in ``main()``."""

    def test_help_long(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr(sys, "argv", ["mcp_server.py", "--help"])
        rc = mcp_server.cli()
        out = capsys.readouterr().out
        assert rc == 0
        # Help banner header line is "frame-check MCP server".
        assert "frame-check MCP server" in out

    def test_help_short(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr(sys, "argv", ["mcp_server.py", "-h"])
        rc = mcp_server.cli()
        out = capsys.readouterr().out
        assert rc == 0
        assert "frame-check MCP server" in out

    def test_version_long(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr(sys, "argv", ["mcp_server.py", "--version"])
        rc = mcp_server.cli()
        out = capsys.readouterr().out
        assert rc == 0
        assert "server_version=" in out
        assert "protocol=" in out

    def test_version_short(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        monkeypatch.setattr(sys, "argv", ["mcp_server.py", "-V"])
        rc = mcp_server.cli()
        assert rc == 0

    def test_default_dispatches_to_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # No subcommand -> cli() returns main()'s exit code. Patch
        # main() to confirm dispatch reaches it without spawning the
        # full stdio loop.
        monkeypatch.setattr(sys, "argv", ["mcp_server.py"])
        with patch.object(mcp_server, "main", return_value=0) as mock_main:
            rc = mcp_server.cli()
        assert rc == 0
        mock_main.assert_called_once()


# ================================================================
# Subcommand bodies
# ================================================================


class TestCliHelp:
    """``_cli_help()`` prints the usage banner and returns 0."""

    def test_returns_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = mcp_server._cli_help()
        assert rc == 0

    def test_banner_mentions_resources_section(self, capsys: pytest.CaptureFixture[str]) -> None:
        mcp_server._cli_help()
        out = capsys.readouterr().out
        assert "RESOURCES" in out
        assert "frame.clarethium.com/corpus/methodology/" in out


class TestCliVersion:
    """``_cli_version()`` prints the install-fingerprint header line
    plus a single space-delimited key=value line."""

    def test_returns_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = mcp_server._cli_version()
        assert rc == 0

    def test_emits_two_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        mcp_server._cli_version()
        lines = capsys.readouterr().out.strip().split("\n")
        # Header line + key=value line.
        assert len(lines) == 2
        assert lines[0].startswith("frame-check mcp_server v")

    def test_key_value_line_carries_required_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        mcp_server._cli_version()
        lines = capsys.readouterr().out.strip().split("\n")
        kv_line = lines[1]
        for required in (
            "server_version=",
            "protocol=",
            "git_sha=",
            "frame_library_version=",
            "corpus_slugs=",
            "corpus_hash=",
            "python=",
            "script=",
        ):
            assert required in kv_line, f"missing field {required} in {kv_line!r}"


class TestInstallVersionInfo:
    """``_install_version_info()`` gathers the fingerprint dict with
    graceful fallback for missing .git / VERSION / corpus."""

    def test_returns_required_keys(self) -> None:
        info = mcp_server._install_version_info()
        for key in (
            "server_version", "protocol_version", "script_path",
            "python_version", "git_sha", "frame_library_version",
            "corpus_slugs", "corpus_hash",
        ):
            assert key in info, f"missing key {key} in info dict"

    def test_server_version_matches_constant(self) -> None:
        info = mcp_server._install_version_info()
        assert info["server_version"] == mcp_server.SERVER_VERSION

    def test_protocol_version_matches_constant(self) -> None:
        info = mcp_server._install_version_info()
        assert info["protocol_version"] == mcp_server.PROTOCOL_VERSION

    def test_script_path_is_absolute(self) -> None:
        info = mcp_server._install_version_info()
        assert info["script_path"].startswith("/") or ":" in info["script_path"]

    def test_git_status_failure_falls_back_to_dirty_false(self) -> None:
        # subprocess.run raising OSError on the `git status --porcelain`
        # call falls through to git_dirty=False (graceful degradation
        # for missing git binary or shallow clone).
        import subprocess as sp_mod
        real_run = sp_mod.run
        call_count = [0]

        def fake_run(args, **kwargs):
            call_count[0] += 1
            # First call is `git rev-parse --short HEAD`; let it
            # succeed via real_run. Second call is `git status
            # --porcelain`; raise OSError to hit the except branch.
            if call_count[0] >= 2:
                raise OSError("git binary missing")
            return real_run(args, **kwargs)

        with patch("subprocess.run", side_effect=fake_run):
            info = mcp_server._install_version_info()
        assert info["git_dirty"] is False

    def test_missing_version_file_falls_back_to_unknown(self) -> None:
        # Patch the open() call for the VERSION path to raise OSError.
        real_open = open

        def fake_open(path, *args, **kwargs):
            if "frame_library/VERSION" in str(path):
                raise OSError("VERSION file missing")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=fake_open):
            info = mcp_server._install_version_info()
        assert info["frame_library_version"] == "unknown"

    def test_missing_corpus_dir_falls_back_to_no_corpus(self) -> None:
        # Patch os.path.isdir for the corpus directory only.
        real_isdir = mcp_server.os.path.isdir

        def fake_isdir(path: str) -> bool:
            if "decision_readiness" in path and "corpus" in path:
                return False
            return real_isdir(path)

        with patch.object(mcp_server.os.path, "isdir", side_effect=fake_isdir):
            info = mcp_server._install_version_info()
        assert info["corpus_hash"] == "no-corpus"
        assert info["corpus_slugs"] == 0


# ================================================================
# dispatch() unhandled-exception branch
# ================================================================


class TestDispatchUnhandledException:
    """``dispatch()`` catches Exception subclasses other than
    ValueError / FileNotFoundError and returns ERR_INTERNAL with a
    safe message (no traceback in the wire response)."""

    def test_handler_runtime_error_returns_internal_error(self) -> None:
        # Patch a handler in _HANDLERS to raise RuntimeError.
        def boom(_params):
            raise RuntimeError("synthetic crash")

        with patch.dict(mcp_server._HANDLERS, {"tools/list": boom}):
            req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            response = mcp_server.dispatch(req)
        assert response is not None
        assert response["error"]["code"] == mcp_server.ERR_INTERNAL
        # The wire message is bounded: type name only, no traceback.
        assert "RuntimeError" in response["error"]["message"]
        assert "synthetic crash" not in response["error"]["message"]


# ================================================================
# main() JSON-RPC stdio loop
# ================================================================


def _drive_main(input_lines: list[str]) -> str:
    """Run mcp_server.main() with synthetic stdin, return captured
    stdout. Each input line is a JSON-RPC request body (no trailing
    newlines needed; the helper joins with newlines)."""
    fake_stdin = io.StringIO("\n".join(input_lines) + "\n")
    fake_stdout = io.StringIO()
    with patch.object(sys, "stdin", fake_stdin), patch.object(sys, "stdout", fake_stdout):
        rc = mcp_server.main()
    assert rc == 0
    return fake_stdout.getvalue()


class TestMainLoop:
    """``main()`` reads JSON-RPC line by line, dispatches, writes
    responses. Returns 0 when stdin closes."""

    def test_blank_line_skipped(self) -> None:
        # Empty lines should not produce a response.
        out = _drive_main([""])
        # No real request -> no response written.
        assert out == ""

    def test_malformed_json_returns_parse_error(self) -> None:
        out = _drive_main(["not valid json {"])
        # Parse error response per JSON-RPC spec is code -32700.
        assert out
        resp = json.loads(out.strip())
        assert resp["error"]["code"] == -32700

    def test_missing_jsonrpc_returns_invalid_request(self) -> None:
        # Valid JSON but missing jsonrpc=2.0 -> invalid-request error.
        out = _drive_main([json.dumps({"id": 1, "method": "ping"})])
        resp = json.loads(out.strip())
        assert resp["error"]["code"] == -32600

    def test_non_dict_request_returns_invalid_request(self) -> None:
        # Top-level array (not an object) -> invalid-request.
        out = _drive_main([json.dumps([1, 2, 3])])
        resp = json.loads(out.strip())
        assert resp["error"]["code"] == -32600

    def test_initialize_returns_server_info(self) -> None:
        req = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        out = _drive_main([json.dumps(req)])
        resp = json.loads(out.strip())
        assert resp["result"]["serverInfo"]["name"] == mcp_server.SERVER_NAME
        assert resp["result"]["serverInfo"]["version"] == mcp_server.SERVER_VERSION

    def test_ping_returns_empty_result(self) -> None:
        req = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        out = _drive_main([json.dumps(req)])
        resp = json.loads(out.strip())
        assert resp["result"] == {}


# ================================================================
# Module-level __getattr__ proxy
# ================================================================


class TestModuleGetattr:
    """``__getattr__`` forwards reads of the four cache-state symbols
    (_FRAME_STATUSES, _FRAME_LIBRARY_VERSION, _FRAME_VERSIONS,
    _FRAME_ADJACENCY) to mcp_resources at call time. Any other
    name raises AttributeError."""

    @pytest.mark.parametrize("name", [
        "_FRAME_STATUSES",
        "_FRAME_LIBRARY_VERSION",
        "_FRAME_VERSIONS",
        "_FRAME_ADJACENCY",
    ])
    def test_proxied_names_resolve(self, name: str) -> None:
        # The reads succeed and the value matches what mcp_resources
        # holds. (The exact value depends on cache state; just verify
        # the lookup chain works.)
        import mcp_resources
        # Trigger cache population so the attr is non-None.
        mcp_resources._ensure_caches()
        proxied = getattr(mcp_server, name)
        direct = getattr(mcp_resources, name)
        assert proxied == direct

    def test_unknown_name_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError, match="no attribute"):
            mcp_server.__getattr__("DEFINITELY_NOT_A_REAL_ATTRIBUTE")
