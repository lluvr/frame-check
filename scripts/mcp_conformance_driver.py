"""Conformance driver for D3.

Drives the installed `frame-check-mcp` wheel as an MCP client would
(subprocess + stdio + JSON-RPC line-delimited frames) and reports
every primitive's pass/fail status with one-line summaries.

Run from any cwd; the wheel is loaded from /tmp/fc-target via
PYTHONPATH and the entry script is /tmp/fc-target/mcp_server.py.

Output: structured report to stdout. Captured into
MCP_CLIENT_CONFORMANCE_v1.md as the D3 deliverable evidence.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import Any

WHEEL_TARGET = "/tmp/fc-target"
SCRIPT = f"{WHEEL_TARGET}/mcp_server.py"

results: list[tuple[str, bool, str]] = []


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def record(name: str, ok: bool, note: str = "") -> None:
    results.append((name, ok, note))
    flag = "PASS" if ok else "FAIL"
    print(f"  {flag}  {name}" + (f"  -- {note}" if note else ""))


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = WHEEL_TARGET
    env.setdefault("GEMINI_API_KEY", "test-dummy-key")

    proc = subprocess.Popen(
        [sys.executable, SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        bufsize=1,
    )

    next_id = [0]

    def call(method: str, params: dict | None = None) -> dict:
        next_id[0] += 1
        req: dict[str, Any] = {
            "jsonrpc": "2.0", "id": next_id[0], "method": method,
        }
        if params is not None:
            req["params"] = params
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline().strip()
        return json.loads(line) if line else {}

    try:
        # 1. initialize handshake
        # Version assertion: verify the field is a valid M.m.p semver.
        # Pinning to a specific number ("0.8.0", "0.8.2") was the prior
        # shape and required driver edits on every release; pinning is
        # now lift_dry_run.py's job (pre-release) so this driver stays
        # release-agnostic.
        resp = call("initialize", {"protocolVersion": "2024-11-05"})
        info = resp["result"]["serverInfo"]
        version_str = info.get("version", "")
        version_ok = (
            isinstance(version_str, str)
            and bool(_SEMVER_RE.match(version_str))
        )
        ok = (
            resp.get("result", {}).get("protocolVersion") == "2024-11-05"
            and info["name"] == "frame-check"
            and version_ok
        )
        record("initialize handshake", ok,
               f"protocol={resp['result']['protocolVersion']} "
               f"server={info['name']}/{version_str}")

        # 2. capabilities advertised
        caps = resp["result"]["capabilities"]
        record(
            "capabilities advertise tools/resources/prompts",
            "tools" in caps and "resources" in caps and "prompts" in caps,
            f"keys={sorted(caps)}",
        )

        # 3. ping primitive
        resp = call("ping", {})
        record("ping returns empty result",
               resp.get("result") == {}, str(resp.get("result")))

        # 4. tools/list
        resp = call("tools/list")
        tools = resp["result"]["tools"]
        names = [t["name"] for t in tools]
        record("tools/list advertises frame_check + frame_compare",
               set(names) == {"frame_check", "frame_compare"},
               f"names={names}")

        # 5. tools/call frame_check (minimal)
        resp = call("tools/call", {
            "name": "frame_check",
            "arguments": {
                "document_text": (
                    "The Committee notes that risks to the outlook "
                    "are elevated. Growth has been solid in recent "
                    "quarters. Uncertainty about supply-side "
                    "developments persists. Stakeholders across "
                    "the economy are monitoring incoming data."
                ),
            },
        })
        result = resp["result"]
        ok = (
            result.get("isError") is False
            and result["content"][0]["type"] == "text"
        )
        if ok:
            payload = json.loads(result["content"][0]["text"])
            ok = (
                "analysis" in payload
                and "agent_guidance" in payload
                and "provenance" in payload
            )
        record("tools/call frame_check returns 3-section payload", ok)

        # 6. tools/call frame_check with source
        resp = call("tools/call", {
            "name": "frame_check",
            "arguments": {
                "document_text": "Revenue grew 50% to $200M.",
                "source_text": "Revenue grew 50% to $200M in Q3.",
            },
        })
        ok = resp["result"].get("isError") is False
        record("tools/call frame_check with source_text", ok)

        # 7. tools/call frame_compare
        resp = call("tools/call", {
            "name": "frame_compare",
            "arguments": {
                "document_a_text": "Growth has been steady.",
                "document_b_text": "Risks are elevated.",
                "document_a_label": "Bullish memo",
                "document_b_label": "Bearish memo",
            },
        })
        ok = resp["result"].get("isError") is False
        record("tools/call frame_compare basic", ok)

        # 8. tools/call malformed (sanity: error path round-trips)
        resp = call("tools/call", {"name": "no_such_tool", "arguments": {}})
        ok = resp["result"].get("isError") is True
        record("tools/call unknown tool returns isError",
               ok, str(resp["result"]["content"][0]["text"][:80]))

        # 9. tools/call with non-Object arguments (D2 fix verification)
        resp = call("tools/call", {"name": "frame_check", "arguments": [1, 2]})
        ok = (
            "error" in resp
            and resp["error"]["code"] == -32602
            and "object" in resp["error"]["message"].lower()
        )
        record(
            "tools/call non-Object arguments -> -32602 (D2 fix)",
            ok, resp.get("error", {}).get("message", "")[:80],
        )

        # 10. resources/list
        resp = call("resources/list")
        resources = resp["result"]["resources"]
        record("resources/list returns resources",
               len(resources) > 0, f"count={len(resources)}")

        # 11. every resource carries contentHash
        all_hashed = all("contentHash" in r for r in resources)
        record("every advertised resource has contentHash",
               all_hashed,
               f"{sum(1 for r in resources if 'contentHash' in r)}/{len(resources)}")

        # 12. every URI uses frame-check:// scheme
        all_scheme = all(r["uri"].startswith("frame-check://") for r in resources)
        record("every URI uses frame-check:// scheme", all_scheme)

        # 13. every mimeType is in the safe whitelist
        safe_mimes = {"text/markdown", "application/json"}
        all_safe = all(r.get("mimeType") in safe_mimes for r in resources)
        record(f"every mimeType in {sorted(safe_mimes)}",
               all_safe,
               f"unique mimes={sorted({r.get('mimeType') for r in resources})}")

        # 14. resources/read on one of each kind
        kinds = {
            "library/INDEX": "frame-check://library",
            "library/FVS-008": "frame-check://library/FVS-008",
        }
        # Sample slugs that are present on this deploy. methodology and
        # spec/frame-divergence/v1 part-1 were retired from the wheel
        # on 2026-05-08 per PUBLIC_CANON_DISCIPLINE.md §3c (the source
        # documents carried maintainer-internal vocabulary; public-canon-
        # clean reconstruction is queued separately). The kinds are now
        # all conditional on appearing in the listed resources.
        for r in resources:
            uri = r["uri"]
            if uri.startswith("frame-check://worked-examples/") and "/" in uri[27:]:
                continue  # skip secondary slugs
            if uri == "frame-check://methodology":
                kinds.setdefault("methodology", uri)
            if uri.startswith("frame-check://transmissions/") and "/transmissions/" in uri:
                kinds.setdefault("transmissions/sample", uri)
            if uri.startswith("frame-check://corpus/") and uri.count("/") == 3:
                kinds.setdefault("corpus/sample", uri)
            if uri == "frame-check://aggregate/latest":
                kinds["aggregate/latest"] = uri
            if uri.startswith("frame-check://spec/frame-divergence/v1"):
                kinds.setdefault("spec/frame-divergence/v1", uri)
            if uri.startswith("frame-check://calibration/"):
                kinds.setdefault("calibration/sample", uri)

        for label, uri in kinds.items():
            resp = call("resources/read", {"uri": uri})
            res = resp.get("result")
            if res is None:
                record(f"resources/read {label}", False,
                       f"uri={uri} error={resp.get('error')}")
                continue
            content = res["contents"][0]
            ok = (
                "text" in content
                and content.get("mimeType") in safe_mimes
                and content.get("contentHash") is not None
                and len(content["contentHash"]) == 64
            )
            record(f"resources/read {label}", ok,
                   f"len={len(content['text'])} mime={content['mimeType']}")

        # 15. resources/read with bad URI returns -32602 (not -32603)
        resp = call("resources/read", {"uri": "frame-check://library/FVS-999"})
        ok = (
            "error" in resp
            and resp["error"]["code"] == -32602
        )
        record("resources/read bad URI -> -32602", ok,
               resp.get("error", {}).get("message", "")[:60])

        # 16. resources/read path traversal -> -32602
        resp = call("resources/read",
                    {"uri": "frame-check://library/../../etc/passwd"})
        ok = (
            "error" in resp
            and resp["error"]["code"] == -32602
        )
        record("resources/read path traversal -> -32602", ok,
               resp.get("error", {}).get("message", "")[:60])

        # 17. resources/read with file:// scheme -> -32602
        resp = call("resources/read", {"uri": "file:///etc/passwd"})
        ok = (
            "error" in resp
            and resp["error"]["code"] == -32602
        )
        record("resources/read file:// scheme -> -32602", ok)

        # 18. prompts/list
        resp = call("prompts/list")
        prompts = resp["result"]["prompts"]
        names = [p["name"] for p in prompts]
        expected_prompts = {
            "frame_check_my_response", "frame_check_this_ai_response",
            "challenge_document", "explain_framing",
        }
        record(f"prompts/list advertises {sorted(expected_prompts)}",
               set(names) == expected_prompts, f"names={names}")

        # 19. prompts/get for each prompt
        for pname in expected_prompts:
            resp = call("prompts/get", {
                "name": pname,
                "arguments": {"depth": "thorough", "goal": "audit",
                              "questions": "no"},
            })
            res = resp.get("result")
            if res is None:
                record(f"prompts/get {pname}", False,
                       str(resp.get("error", {}).get("message", ""))[:60])
                continue
            ok = (
                "messages" in res
                and len(res["messages"]) > 0
                and res["messages"][0]["content"]["type"] == "text"
                and len(res["messages"][0]["content"]["text"]) > 100
            )
            record(f"prompts/get {pname}", ok,
                   f"body_len={len(res['messages'][0]['content']['text'])}")

        # 20. prompts/get with unknown name -> -32602
        resp = call("prompts/get", {"name": "no_such_prompt"})
        ok = (
            "error" in resp
            and resp["error"]["code"] == -32602
        )
        record("prompts/get unknown name -> -32602", ok)

        # 21. unknown method -> -32601
        resp = call("does/not/exist")
        ok = (
            "error" in resp
            and resp["error"]["code"] == -32601
        )
        record("unknown method -> -32601", ok)

        # 22. notification (no id) -> no response
        # We send a notification and then a normal request to verify
        # the loop continues without emitting a response for the
        # notification.
        next_id[0] += 1
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }) + "\n")
        proc.stdin.flush()
        # Small grace, then send a real ping; only the ping should
        # produce a response.
        time.sleep(0.05)
        resp = call("ping")
        ok = resp.get("result") == {}
        record("notification suppressed; subsequent ping responds", ok)

    finally:
        try:
            proc.stdin.close()
        except OSError:
            # Pipe already closed or broken; idempotent cleanup proceeds.
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc.stdout.close()
        stderr_tail = ""
        try:
            stderr_tail = proc.stderr.read()
        except Exception:
            # stderr drain failed; the tail message stays empty.
            pass
        proc.stderr.close()

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n=== summary: {passed}/{total} passed ===")
    if stderr_tail.strip():
        print(f"\n--- server stderr tail ---")
        print(stderr_tail[-1500:])

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
