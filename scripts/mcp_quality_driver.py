"""MCP quality driver.

Companion to scripts/mcp_conformance_driver.py. The conformance driver
verifies JSON-RPC envelope shape (initialize handshake, capabilities,
tools/list shape, error codes). This driver verifies output CONTENT:
the analytical fields frame_check actually returns, the
FRAME_DIVERGENCE_CONTRACT_v1 c1.0 invariants on the divergence block,
reproducibility, adversarial-input graceful degradation, and a real-
corpus drive against curated documents from fvs_eval and worked_examples.

Run modes:

    python3 scripts/mcp_quality_driver.py [--source | --wheel]
                                          [--corpus N]
                                          [--report-md PATH]
                                          [--report-json PATH]

  --source (default): drives mcp_server.py from the local source tree.
                      Fast iteration; requires the source tree's
                      Python deps installed.
  --wheel:            drives the installed wheel at /tmp/fc-target,
                      matching the conformance driver's setup. Use to
                      validate the released artifact.

Exit code: 0 if every layer passed; 1 otherwise.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
WHEEL_TARGET = "/tmp/fc-target"
# Subprocess CWD set to /tmp to defeat the CWD-trap where Python's
# import system finds a sibling mcp_server.py in REPO_ROOT before
# resolving the WHEEL_TARGET copy via PYTHONPATH (manually verified
# 2026-04-28: cwd=REPO_ROOT silently shadowed wheel-target imports).
_SUBPROC_CWD = "/tmp"
# Brief grace after notifications/initialized so the server processes
# the notification before the next request. Empirically sufficient
# at 50ms; tightening below 25ms produced sporadic stdout-readahead
# desync in dev iteration.
_POST_INIT_GRACE_S = 0.05

# FRAME_DIVERGENCE_CONTRACT_v1 c1.0 canonical strings. Verified against
# mcp_server.py at lines 3103-3109 (faithfulness_note) and 3373-3380
# (absence_is_not_prescription) on 2026-04-28. Implementation embeds
# the contract substring verbatim plus may extend with descriptive
# context (e.g. the "descriptive vs prescriptive" nuance on
# absence_is_not_prescription); the harness checks for the canonical
# substring, not equality, so additive extensions do not false-positive.
CONTRACT_FAITHFULNESS_NOTE = (
    "Absent frames are named from the FVS catalog as not "
    "detected in the supplied document. Domain relevance is "
    "the tool's best judgment. Whether any absent frame is "
    "useful is the thinker's call. This is not a list of "
    "frames that should have been used."
)
CONTRACT_ABSENCE_NOT_PRESCRIPTION = (
    "Divergence output never implies the user should have used "
    "the absent frames. The tool surfaces absence, the thinker "
    "decides relevance."
)
CONTRACT_SPEC_VERSION = "FRAME_DIVERGENCE_v1_c1.0"
CONTRACT_CATALOG_DEFAULT = "library_v3"

# §4.2 forbidden field names on AbsentFrameRecord; presence is a
# contract violation regardless of their value.
FORBIDDEN_ABSENT_FRAME_FIELDS = (
    "prescription", "recommendation", "should_use", "must_use",
)

# §4.2 required fields on every AbsentFrameRecord.
REQUIRED_ABSENT_FRAME_FIELDS = (
    "frame_id", "frame_version", "frame_title", "stability",
    "citation_uri", "absence_basis", "domain_relevance_rationale",
)

# §4.3 required fields on the envelope.
REQUIRED_ENVELOPE_FIELDS = (
    "spec_version", "catalog_version", "surface", "v4_2_execution",
    "v4_2_engine_status", "domain_inferred", "provisional_count",
    "faithfulness_note", "limitations",
)

# §3.3 valid divergence_rendering enum values. teaching_questions mode
# is the only one that adds the teaching_question field per record.
DIVERGENCE_RENDERINGS = (
    "list", "completeness_check", "teaching_questions", "narrative",
)

# Wall-clock fields stripped before reproducibility comparison. Names
# verified against mcp_server.py::_build_provenance (analysis_latency_ms,
# analysis_timestamp_utc) and the divergence-block builder
# (request_id, invocation_timestamp on the envelope). Also strips
# elapsed_ms in case that name resurfaces in a future provenance shape;
# pop is a no-op if the key is absent.
_WALL_CLOCK_KEYS = (
    "analysis_latency_ms", "analysis_timestamp_utc",
    "elapsed_ms", "invocation_timestamp", "request_id",
)

# Top-level analysis sub-blocks frame_check is documented to ship.
# Verified against mcp_server.py::build_epistemic_payload around lines
# 3540-3760. Required = always present; Conditional = present only
# when source_text supplied (verification block).
REQUIRED_ANALYSIS_KEYS = (
    "document", "coverage", "coverage_v2", "voice", "genre",
    "frame_deepening", "temporal", "epistemic",
    "frame_library_matches",
)


# ── Findings + reporter ───────────────────────────────────────────


@dataclasses.dataclass
class Finding:
    layer: str
    name: str
    ok: bool
    note: str = ""


class Driver:
    """Holds the harness state across layers."""

    def __init__(self, mode: str, corpus_size: int) -> None:
        self.mode = mode
        self.corpus_size = corpus_size
        self.findings: list[Finding] = []
        self.proc: subprocess.Popen | None = None
        self._next_id = 0
        self.server_info: dict[str, Any] = {}

    # ── subprocess control ────────────────────────────────────────

    def start(self) -> None:
        env = os.environ.copy()
        if self.mode == "wheel":
            env["PYTHONPATH"] = WHEEL_TARGET
            script = f"{WHEEL_TARGET}/mcp_server.py"
        else:
            # Source-tree mode. Repo root must be on PYTHONPATH so the
            # mcp_server module's siblings (framing, frame_library,
            # claim_analysis, etc.) import correctly.
            env["PYTHONPATH"] = str(REPO_ROOT)
            script = str(REPO_ROOT / "mcp_server.py")
        # Suppress optional API key warning paths.
        env.setdefault("GEMINI_API_KEY", "test-dummy-key")
        env.setdefault("XAI_API_KEY", "test-dummy-key")

        self.proc = subprocess.Popen(
            [sys.executable, script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,
            cwd=_SUBPROC_CWD,
        )

    def stop(self) -> str:
        if not self.proc:
            return ""
        try:
            self.proc.stdin.close()  # type: ignore[union-attr]
        except OSError:
            # Pipe already closed or broken; idempotent cleanup proceeds.
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        try:
            self.proc.stdout.close()  # type: ignore[union-attr]
        except OSError:
            # stdout already closed or broken; idempotent cleanup proceeds.
            pass
        stderr_tail = ""
        try:
            stderr_tail = self.proc.stderr.read()  # type: ignore[union-attr]
        except Exception:
            # stderr drain failed; the tail message stays empty.
            pass
        try:
            self.proc.stderr.close()  # type: ignore[union-attr]
        except OSError:
            # stderr already closed or broken; idempotent cleanup proceeds.
            pass
        return stderr_tail

    def call(self, method: str, params: dict | None = None,
             timeout_s: float = 30.0) -> dict:
        """Send a JSON-RPC request, return the parsed response. Raises
        on subprocess death or stdin write failure."""
        assert self.proc is not None
        self._next_id += 1
        req: dict[str, Any] = {
            "jsonrpc": "2.0", "id": self._next_id, "method": method,
        }
        if params is not None:
            req["params"] = params
        try:
            self.proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]
        except (BrokenPipeError, OSError) as e:
            raise RuntimeError(f"stdin write failed: {e}") from e
        # Server is line-delimited JSON; read one line.
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                if self.proc.poll() is not None:
                    raise RuntimeError(
                        f"server exited with code {self.proc.returncode}"
                    )
                continue
            return json.loads(line.strip())
        raise TimeoutError(f"no response within {timeout_s}s")

    def initialize(self) -> None:
        resp = self.call("initialize", {"protocolVersion": "2024-11-05"})
        if "error" in resp:
            raise RuntimeError(f"initialize failed: {resp['error']}")
        # Capture serverInfo for cross-version-consistency checks
        # (Layer 1 verifies this matches provenance.frame_check_version).
        self.server_info = resp["result"]["serverInfo"]
        # Send the notifications/initialized notification per protocol.
        self._next_id += 1
        try:
            self.proc.stdin.write(json.dumps({  # type: ignore[union-attr]
                "jsonrpc": "2.0", "method": "notifications/initialized",
            }) + "\n")
            self.proc.stdin.flush()  # type: ignore[union-attr]
        except (BrokenPipeError, OSError):
            # Pipe broken; subsequent read surfaces the failure.
            pass
        time.sleep(_POST_INIT_GRACE_S)

    # ── frame_check helper ────────────────────────────────────────

    def frame_check(self, document_text: str,
                    *,
                    source_text: str | None = None,
                    include_divergence: bool = False,
                    domain_hint: str | None = None,
                    catalog_version_pin: str | None = None,
                    timeout_s: float = 30.0) -> dict:
        """Call frame_check and return the parsed payload. Raises on
        tools/call error envelope."""
        args: dict[str, Any] = {"document_text": document_text}
        if source_text is not None:
            args["source_text"] = source_text
        if include_divergence:
            args["include_divergence"] = True
        if domain_hint is not None:
            args["domain_hint"] = domain_hint
        if catalog_version_pin is not None:
            args["catalog_version_pin"] = catalog_version_pin
        resp = self.call("tools/call", {
            "name": "frame_check", "arguments": args,
        }, timeout_s=timeout_s)
        if "error" in resp:
            raise RuntimeError(f"tools/call error: {resp['error']}")
        result = resp["result"]
        if result.get("isError"):
            raise RuntimeError(
                f"frame_check returned isError: "
                f"{result['content'][0]['text'][:200]}"
            )
        return json.loads(result["content"][0]["text"])

    def resources_read(self, uri: str) -> dict | None:
        """Call resources/read. Returns the first content dict or None
        on -32602 / -32603."""
        resp = self.call("resources/read", {"uri": uri})
        if "error" in resp:
            return None
        return resp["result"]["contents"][0]

    # ── findings ──────────────────────────────────────────────────

    def record(self, layer: str, name: str, ok: bool,
               note: str = "") -> None:
        self.findings.append(Finding(layer, name, ok, note))
        flag = "PASS" if ok else "FAIL"
        suffix = f"  -- {note}" if note else ""
        print(f"  [{layer}] {flag}  {name}{suffix}")


# ── Helpers ───────────────────────────────────────────────────────


def _strip_wall_clock(payload: dict) -> dict:
    """Return a deep-ish copy of payload with wall-clock fields stripped
    from both provenance and (when present) divergence.envelope so two
    payloads from the same input can be compared for byte-equivalence
    without false-positives on second-boundary crossings.

    Both blocks carry their own request_id / timestamp pair per
    FRAME_DIVERGENCE_CONTRACT_v1 §6.5; stripping only provenance was
    the v0.1 bug that this v0.2 helper closes.
    """
    out = dict(payload)
    prov = dict(out.get("provenance", {}) or {})
    for k in _WALL_CLOCK_KEYS:
        prov.pop(k, None)
    out["provenance"] = prov
    if "divergence" in out and isinstance(out["divergence"], dict):
        diverg = dict(out["divergence"])
        env = dict(diverg.get("envelope", {}) or {})
        for k in _WALL_CLOCK_KEYS:
            env.pop(k, None)
        diverg["envelope"] = env
        out["divergence"] = diverg
    return out


def _check_l1_invariants(driver: "Driver", label: str,
                         payload: dict) -> list[str]:
    """Apply Layer 1 structural invariants to an arbitrary payload and
    return a list of human-readable violation strings (empty if all
    invariants hold). Used by Layer 5 to apply the same depth as
    Layer 1 across the corpus, not just the canned doc."""
    violations: list[str] = []
    analysis = payload.get("analysis", {}) or {}
    missing = [k for k in REQUIRED_ANALYSIS_KEYS if k not in analysis]
    if missing:
        violations.append(f"missing analysis sub-blocks: {missing}")
    voice = analysis.get("voice", {}) or {}
    if voice.get("classification") not in (
        "promotional", "prescriptive", "analytical",
        "descriptive", "advisory",
    ):
        violations.append(
            f"voice.classification={voice.get('classification')!r} "
            f"not in documented enum"
        )
    temp = analysis.get("temporal", {}) or {}
    dist = temp.get("distribution_pct", {}) or {}
    if all(isinstance(dist.get(k), (int, float))
           for k in ("past", "present", "future")):
        total = dist["past"] + dist["present"] + dist["future"]
        if abs(total - 100.0) >= 1.0:
            violations.append(
                f"temporal sum={total:.1f}, not ~100 ({dist})"
            )
    else:
        violations.append(f"temporal.distribution_pct missing keys: {dist}")
    if not isinstance(analysis.get("frame_library_matches"), list):
        violations.append("frame_library_matches is not a list")
    prov = payload.get("provenance", {}) or {}
    for k in (
        "frame_check_version", "analysis_layer", "analysis_latency_ms",
        "analysis_cost_usd", "engine_version", "framing_engine", "license",
    ):
        if k not in prov:
            violations.append(f"provenance missing {k}")
    return violations


# ── Layer 1: structural invariants ────────────────────────────────


def layer1_structural(driver: Driver) -> None:
    """frame_check returns the documented top-level + sub-block fields
    on minimal inputs. Catches silent-empty regressions where a section
    is dropped or returns None unexpectedly."""
    print("\n--- Layer 1: structural invariants ---")
    doc = (
        "The Committee notes that risks to the outlook are elevated. "
        "Growth has been solid in recent quarters. Uncertainty about "
        "supply-side developments persists. Stakeholders across the "
        "economy are monitoring incoming data."
    )
    try:
        payload = driver.frame_check(doc)
    except RuntimeError as e:
        driver.record("L1", "frame_check minimal call", False, str(e))
        return

    # Top-level keys.
    expected_top = {"analysis", "agent_guidance", "provenance"}
    actual_top = set(payload.keys())
    driver.record(
        "L1", "top-level keys (analysis/agent_guidance/provenance)",
        expected_top.issubset(actual_top),
        f"missing={sorted(expected_top - actual_top) or 'none'}",
    )

    # Analysis sub-blocks.
    analysis = payload.get("analysis", {}) or {}
    missing_analysis = [
        k for k in REQUIRED_ANALYSIS_KEYS if k not in analysis
    ]
    driver.record(
        "L1", f"analysis carries {len(REQUIRED_ANALYSIS_KEYS)} sub-blocks",
        not missing_analysis,
        f"missing={missing_analysis or 'none'}",
    )

    # Document sub-block has the three counts and they are integers.
    document = analysis.get("document", {}) or {}
    doc_keys_ok = (
        isinstance(document.get("word_count_estimate"), int)
        and isinstance(document.get("char_count"), int)
        and isinstance(document.get("sentence_count"), int)
    )
    driver.record(
        "L1", "analysis.document carries int counts", doc_keys_ok,
        f"keys={sorted(document)}",
    )

    # Coverage v2 is the forward contract; verify it is present and
    # has at least an 'addressed' or 'covered' list.
    cov_v2 = analysis.get("coverage_v2", {}) or {}
    cov_v2_ok = (
        isinstance(cov_v2, dict)
        and len(cov_v2) > 0
    )
    driver.record(
        "L1", "analysis.coverage_v2 is a non-empty dict", cov_v2_ok,
        f"keys={sorted(cov_v2)[:6]}",
    )

    # Coverage v2 dimensions contract: exactly the five canonical
    # analytical perspectives. Pinning this so a regression that
    # silently drops one (e.g., a refactor that splits 'risks' into
    # two but forgets to keep the original key) fails here. The
    # presence-only check above passes if any dimension exists; this
    # check pins the SET. Doc-level content audits in
    # CONSTRUCT_VALIDITY_AUDIT_v1 §1 named the five dimensions as the
    # construct's load-bearing contract; that contract is wire-shipped
    # via this block and must not silently drift.
    expected_dimensions = {
        "causes", "risks", "stakeholders", "trends", "uncertainty",
    }
    dimensions = cov_v2.get("dimensions", {}) or {}
    actual_dimensions = set(dimensions) if isinstance(dimensions, dict) else set()
    dimensions_ok = actual_dimensions == expected_dimensions
    driver.record(
        "L1", "coverage_v2.dimensions == 5 canonical perspectives",
        dimensions_ok,
        f"expected={sorted(expected_dimensions)} "
        f"actual={sorted(actual_dimensions)}",
    )

    # Voice classification non-null when input has > 50 words.
    voice = analysis.get("voice", {}) or {}
    voice_ok = (
        voice.get("classification") is not None
        and isinstance(voice.get("signals"), dict)
    )
    driver.record(
        "L1", "voice.classification + voice.signals populated",
        voice_ok,
        f"classification={voice.get('classification')}",
    )

    # Temporal distribution percentages sum to ~100 (within float epsilon).
    # Verified against framing.py::temporal_orientation: emission is
    # always 0..100 scale, never 0..1; tolerate 1pp slack for rounding.
    temporal = analysis.get("temporal", {}) or {}
    dist = temporal.get("distribution_pct", {}) or {}
    if (isinstance(dist.get("past"), (int, float))
            and isinstance(dist.get("present"), (int, float))
            and isinstance(dist.get("future"), (int, float))):
        total = dist["past"] + dist["present"] + dist["future"]
        sum_ok = abs(total - 100.0) < 1.0
    else:
        sum_ok = False
    driver.record(
        "L1", "temporal.distribution_pct sums to 100", sum_ok,
        f"dist={dist}",
    )

    # frame_library_matches is a list (possibly empty).
    matches = analysis.get("frame_library_matches", None)
    matches_ok = isinstance(matches, list)
    driver.record(
        "L1", "analysis.frame_library_matches is a list",
        matches_ok, f"type={type(matches).__name__} len={len(matches) if matches_ok else 'n/a'}",
    )

    # agent_guidance is a non-empty dict.
    guidance = payload.get("agent_guidance", {}) or {}
    driver.record(
        "L1", "agent_guidance is a non-empty dict",
        isinstance(guidance, dict) and len(guidance) > 0,
        f"keys_count={len(guidance)}",
    )

    # provenance carries the documented sub-fields. Keys verified
    # against mcp_server.py::_build_provenance (lines 346-389): version
    # is `frame_check_version`, latency is `analysis_latency_ms`,
    # layer is `analysis_layer`, plus engine_version + framing_engine
    # + cost + timestamp + license. Missing any of these is a
    # contract regression; the harness names them explicitly so a
    # rename surfaces here as a finding.
    provenance = payload.get("provenance", {}) or {}
    required_prov = (
        "frame_check_version", "server_version", "analysis_layer",
        "analysis_latency_ms", "analysis_cost_usd", "engine_version",
        "framing_engine", "license",
    )
    missing_prov = [k for k in required_prov if k not in provenance]
    driver.record(
        "L1", f"provenance carries {len(required_prov)} required fields",
        not missing_prov,
        f"missing={missing_prov or 'none'}; "
        f"version={provenance.get('frame_check_version')!r}",
    )

    # Cross-source version consistency. serverInfo.version (initialize
    # handshake) and provenance.server_version (response payload) both
    # report the MCP wheel's version (SERVER_VERSION); drift between
    # them means an integrator filing a bug report sees one wheel
    # version on connect and another in the analysis they paste, which
    # is genuinely confusing. Both fields read from mcp_server.py's
    # SERVER_VERSION so they should always match by construction; the
    # driver pins this as a real invariant.
    #
    # provenance.frame_check_version is a SEPARATE axis: the brand /
    # methodology version (also stamped into telemetry events and
    # CITATION.cff; see version.py docstring). It is intentionally not
    # tied to SERVER_VERSION because an MCP wheel patch can ship without
    # bumping the methodology brand, and a brand bump (rare) does not
    # require re-cutting the wheel. The driver does not assert any
    # relation between frame_check_version and server_version; that is
    # by design.
    server_version = (driver.server_info or {}).get("version")
    prov_server_version = provenance.get("server_version")
    driver.record(
        "L1", "serverInfo.version matches provenance.server_version",
        server_version == prov_server_version,
        f"serverInfo={server_version!r} "
        f"provenance.server_version={prov_server_version!r}",
    )


# ── Layer 2: divergence contract invariants ───────────────────────


def layer2_divergence(driver: Driver) -> None:
    """FRAME_DIVERGENCE_CONTRACT_v1 c1.0 contract invariants when
    include_divergence=true."""
    print("\n--- Layer 2: divergence contract (c1.0) ---")
    doc = (
        "Revenue grew 50% to $200M in Q3. Growth has been steady. "
        "The strategy is delivering. Customers love the product. "
        "We see continued momentum into Q4."
    )
    try:
        payload = driver.frame_check(doc, include_divergence=True)
    except RuntimeError as e:
        driver.record("L2", "frame_check include_divergence=true", False, str(e))
        return

    # §2.2 / §4.1: divergence block present.
    divergence = payload.get("divergence")
    if not isinstance(divergence, dict):
        driver.record(
            "L2", "divergence block present and is a dict", False,
            f"got type={type(divergence).__name__}",
        )
        return
    driver.record(
        "L2", "divergence block present", True,
        f"keys={sorted(divergence)}",
    )

    # §4.2 absent_frames is an array.
    absent = divergence.get("absent_frames")
    if not isinstance(absent, list):
        driver.record(
            "L2", "divergence.absent_frames is a list", False,
            f"type={type(absent).__name__}",
        )
        return
    driver.record(
        "L2", "divergence.absent_frames is a list",
        True, f"count={len(absent)}",
    )

    # §4.2 required fields per record + forbidden fields absent.
    if not absent:
        driver.record(
            "L2", "absent_frames has at least one record on this doc",
            False, "empty list",
        )
    else:
        missing_required: list[str] = []
        forbidden_present: list[str] = []
        for i, rec in enumerate(absent):
            if not isinstance(rec, dict):
                missing_required.append(f"[{i}]: not a dict")
                continue
            for k in REQUIRED_ABSENT_FRAME_FIELDS:
                if k not in rec:
                    missing_required.append(f"[{i}].{k}")
            for k in FORBIDDEN_ABSENT_FRAME_FIELDS:
                if k in rec:
                    forbidden_present.append(f"[{i}].{k}")
        driver.record(
            "L2", f"every AbsentFrameRecord has {len(REQUIRED_ABSENT_FRAME_FIELDS)} required fields",
            not missing_required,
            f"missing={missing_required[:5] or 'none'}",
        )
        driver.record(
            "L2", f"no record carries forbidden fields {list(FORBIDDEN_ABSENT_FRAME_FIELDS)}",
            not forbidden_present,
            f"present={forbidden_present or 'none'}",
        )

    # §4.3 envelope.
    envelope = divergence.get("envelope")
    if not isinstance(envelope, dict):
        driver.record(
            "L2", "divergence.envelope is a dict", False,
            f"type={type(envelope).__name__}",
        )
    else:
        missing_env = [
            k for k in REQUIRED_ENVELOPE_FIELDS if k not in envelope
        ]
        driver.record(
            "L2", f"envelope carries {len(REQUIRED_ENVELOPE_FIELDS)} required fields",
            not missing_env, f"missing={missing_env or 'none'}",
        )
        # spec_version canonical value.
        driver.record(
            "L2", f"envelope.spec_version == '{CONTRACT_SPEC_VERSION}'",
            envelope.get("spec_version") == CONTRACT_SPEC_VERSION,
            f"got={envelope.get('spec_version')!r}",
        )
        # catalog_version default.
        driver.record(
            "L2", f"envelope.catalog_version == '{CONTRACT_CATALOG_DEFAULT}' (default)",
            envelope.get("catalog_version") == CONTRACT_CATALOG_DEFAULT,
            f"got={envelope.get('catalog_version')!r}",
        )
        # surface == 'mcp' on this stdio invocation.
        driver.record(
            "L2", "envelope.surface == 'mcp'",
            envelope.get("surface") == "mcp",
            f"got={envelope.get('surface')!r}",
        )
        # v4_2_execution.location == 'caller_side' (Contract §7.1).
        v4 = envelope.get("v4_2_execution", {}) or {}
        driver.record(
            "L2", "envelope.v4_2_execution.location == 'caller_side' (MCP)",
            v4.get("location") == "caller_side",
            f"got={v4.get('location')!r}",
        )
        # faithfulness_note carries the canonical contract substring.
        note = envelope.get("faithfulness_note", "") or ""
        driver.record(
            "L2", "envelope.faithfulness_note matches contract canonical text",
            CONTRACT_FAITHFULNESS_NOTE in note,
            f"len={len(note)}",
        )

    # §4.4 agent_guidance additions.
    guidance = payload.get("agent_guidance", {}) or {}
    driver.record(
        "L2", "agent_guidance.how_to_render_divergence present",
        isinstance(guidance.get("how_to_render_divergence"), str)
        and len(guidance.get("how_to_render_divergence", "")) > 100,
        f"len={len(guidance.get('how_to_render_divergence', '')) if isinstance(guidance.get('how_to_render_divergence'), str) else 'n/a'}",
    )
    absence_str = guidance.get("absence_is_not_prescription", "") or ""
    driver.record(
        "L2", "agent_guidance.absence_is_not_prescription carries contract canonical substring",
        CONTRACT_ABSENCE_NOT_PRESCRIPTION in absence_str,
        f"len={len(absence_str)}",
    )

    # §5.2 every citation_uri is resolvable via resources/read.
    if isinstance(absent, list) and absent:
        unresolved: list[str] = []
        # Limit the resource fetches to the first 5 records to keep
        # the harness fast; broken citations are detected from a
        # sample, not by exhaustive verification.
        for rec in absent[:5]:
            uri = rec.get("citation_uri", "") if isinstance(rec, dict) else ""
            if not isinstance(uri, str) or not uri:
                unresolved.append("(empty)")
                continue
            content = driver.resources_read(uri)
            if content is None or not content.get("text"):
                unresolved.append(uri)
        driver.record(
            "L2", "every citation_uri resolves via resources/read (first 5 sampled)",
            not unresolved,
            f"unresolved={unresolved or 'none'}",
        )


# ── Layer 3: reproducibility ──────────────────────────────────────


def layer3_reproducibility(driver: Driver) -> None:
    """Same input → same output, modulo provenance.elapsed_ms /
    analysis_latency_ms (wall-clock fields)."""
    print("\n--- Layer 3: reproducibility ---")
    doc = (
        "The Federal Reserve held rates steady. Inflation has moderated. "
        "Risks remain elevated. The Committee judges that the appropriate "
        "stance of monetary policy is data-dependent."
    )
    try:
        a = driver.frame_check(doc)
        b = driver.frame_check(doc)
    except RuntimeError as e:
        driver.record("L3", "twin frame_check calls", False, str(e))
        return

    a_clean = _strip_wall_clock(a)
    b_clean = _strip_wall_clock(b)
    same = a_clean == b_clean
    diff_summary = ""
    if not same:
        # Find the first differing top-level key.
        for k in set(a_clean) | set(b_clean):
            if a_clean.get(k) != b_clean.get(k):
                diff_summary = f"first_differing_key={k}"
                break
    driver.record(
        "L3", "frame_check is deterministic (same input -> same output mod wall-clock)",
        same, diff_summary,
    )


# ── Layer 4: adversarial inputs at the analytical layer ───────────


def layer4_adversarial(driver: Driver) -> None:
    """Adversarial inputs at the analytical layer: empty, oversized,
    control chars, JSON-shaped. Every case should either return a
    structured error envelope or degrade gracefully (no crash, no
    silent success on garbage)."""
    print("\n--- Layer 4: analytical-layer adversarial inputs ---")

    # Empty document. Server may return error or graceful zero-coverage;
    # both are acceptable. Crashing is not.
    try:
        empty_resp = driver.call("tools/call", {
            "name": "frame_check",
            "arguments": {"document_text": ""},
        })
        ok = (
            "error" in empty_resp
            or empty_resp.get("result", {}).get("isError") is True
            or "result" in empty_resp  # graceful degradation acceptable
        )
        driver.record(
            "L4", "empty document_text handled (error or graceful)",
            ok, str(empty_resp.get("error", empty_resp.get("result", {}).get("isError", "ok")))[:80],
        )
    except RuntimeError as e:
        driver.record("L4", "empty document_text", False, str(e))

    # Oversized: 200 KB of repeated text. Should either degrade or
    # error structurally; should not crash the server.
    big = ("The committee notes risks. " * 8000)[:200_000]
    try:
        big_resp = driver.call("tools/call", {
            "name": "frame_check",
            "arguments": {"document_text": big},
        }, timeout_s=60.0)
        ok = "result" in big_resp or "error" in big_resp
        driver.record(
            "L4", "oversized document (200 KB) handled",
            ok,
            f"isError={big_resp.get('result', {}).get('isError', 'n/a')}",
        )
    except (RuntimeError, TimeoutError) as e:
        driver.record("L4", "oversized document (200 KB)", False, str(e))

    # Control characters: ASCII C0 + DEL embedded in document.
    cc_doc = "\x01\x02\x07Risks are elevated.\x1b[31mGrowth is steady.\x7f"
    try:
        cc_resp = driver.call("tools/call", {
            "name": "frame_check",
            "arguments": {"document_text": cc_doc},
        })
        ok = "result" in cc_resp or "error" in cc_resp
        driver.record(
            "L4", "control-character document handled",
            ok, "no crash",
        )
    except RuntimeError as e:
        driver.record("L4", "control-character document", False, str(e))

    # JSON-shaped string as document_text (not malformed at the JSON-
    # RPC layer; a string that LOOKS like JSON inside the analytical
    # surface). Should be analyzed as text, not parsed.
    json_doc = (
        '{"market_state": "bullish", "risks": ["macro", "fx"], '
        '"summary": "Growth has been steady; outlook remains favorable."}'
    )
    try:
        js_resp = driver.call("tools/call", {
            "name": "frame_check",
            "arguments": {"document_text": json_doc},
        })
        ok = "result" in js_resp and js_resp["result"].get("isError") is False
        driver.record(
            "L4", "JSON-shaped string analyzed as text",
            ok,
            f"isError={js_resp.get('result', {}).get('isError', 'n/a')}",
        )
    except RuntimeError as e:
        driver.record("L4", "JSON-shaped string", False, str(e))


# ── Layer 5: real corpus drive ────────────────────────────────────


def _gather_corpus(corpus_size: int) -> list[tuple[str, str]]:
    """Return a list of (label, text) pairs from real curated corpora.
    Mixes worked_examples (curated demos) and validation_study/corpus
    (sha256-verified manifest)."""
    pairs: list[tuple[str, str]] = []
    we_dir = REPO_ROOT / "data" / "worked_examples"
    if we_dir.is_dir():
        for p in sorted(we_dir.glob("*.md")):
            if p.name.startswith("_") or p.name in ("README.md",):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if len(text) < 200:
                continue
            pairs.append((f"worked_examples/{p.stem}", text))
    vs_corpus = REPO_ROOT / "fvs_eval" / "validation_study" / "corpus"
    if vs_corpus.is_dir():
        for p in sorted(vs_corpus.glob("*.txt")):
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if len(text) < 200:
                continue
            pairs.append((f"validation_study/{p.stem}", text))
    return pairs[:corpus_size]


def layer5_corpus(driver: Driver) -> None:
    """Drive N real corpus documents through frame_check and verify
    the structural invariants hold across the corpus, not just the
    canned doc from Layer 1."""
    print("\n--- Layer 5: real-corpus drive ---")
    pairs = _gather_corpus(driver.corpus_size)
    if not pairs:
        driver.record(
            "L5", "corpus available", False,
            "no documents found in worked_examples or validation_study",
        )
        return
    driver.record(
        "L5", f"corpus available ({driver.corpus_size} requested)",
        True, f"loaded={len(pairs)}",
    )

    structural_failures: list[str] = []
    divergence_failures: list[str] = []
    for label, text in pairs:
        try:
            payload = driver.frame_check(text, include_divergence=True)
        except RuntimeError as e:
            structural_failures.append(f"{label}: {str(e)[:80]}")
            continue
        # Run the FULL Layer 1 invariant set per doc, not just a
        # weaker "sub-blocks present" check. v0.1 of this layer
        # was weaker than Layer 1; v0.2 closes that gap.
        violations = _check_l1_invariants(driver, label, payload)
        if violations:
            structural_failures.append(
                f"{label}: {'; '.join(violations[:3])}"
            )
            continue
        # Divergence block present + envelope spec_version correct.
        divergence = payload.get("divergence", {}) or {}
        envelope = divergence.get("envelope", {}) or {}
        if envelope.get("spec_version") != CONTRACT_SPEC_VERSION:
            divergence_failures.append(
                f"{label}: spec_version={envelope.get('spec_version')!r}"
            )

    driver.record(
        "L5", f"L1 invariants hold across {len(pairs)} corpus docs",
        not structural_failures,
        f"failures={len(structural_failures)}: {structural_failures[:3]}",
    )
    driver.record(
        "L5", f"divergence spec_version stable across {len(pairs)} corpus docs",
        not divergence_failures,
        f"failures={len(divergence_failures)}: {divergence_failures[:3]}",
    )


# ── Layer 6: frame_compare quality ────────────────────────────────


def layer6_frame_compare(driver: Driver) -> None:
    """frame_compare is the second tool the MCP server ships and is
    used by the divergence-on-pair surface. The conformance driver
    only verifies it does not error; this layer verifies it returns
    the documented output structure on a real bullish-vs-bearish
    pair, and that the same input pair produces byte-equivalent
    output (modulo wall-clock)."""
    print("\n--- Layer 6: frame_compare quality ---")
    bullish = (
        "Q3 results were strong. Revenue grew 50% to $200M. The strategy "
        "is delivering across all segments. Customers love the product. "
        "We see continued momentum into Q4 and into 2027."
    )
    bearish = (
        "Q3 revenue missed expectations. The 50% growth headline masks "
        "softening unit economics. Risks to the outlook are elevated. "
        "Stakeholders are reassessing the strategic case."
    )
    args = {
        "document_a_text": bullish, "document_b_text": bearish,
        "document_a_label": "Bullish memo", "document_b_label": "Bearish memo",
    }
    try:
        resp_a = driver.call("tools/call",
                             {"name": "frame_compare", "arguments": args})
        resp_b = driver.call("tools/call",
                             {"name": "frame_compare", "arguments": args})
    except RuntimeError as e:
        driver.record("L6", "frame_compare twin call", False, str(e))
        return

    if resp_a.get("result", {}).get("isError") is not False:
        driver.record(
            "L6", "frame_compare returns isError=false",
            False, str(resp_a.get("result", {}).get("content", ""))[:80],
        )
        return
    driver.record(
        "L6", "frame_compare returns isError=false", True, "",
    )

    payload_a = json.loads(resp_a["result"]["content"][0]["text"])
    payload_b = json.loads(resp_b["result"]["content"][0]["text"])

    # Documented top-level shape: per-doc summaries + comparison +
    # agent_guidance + provenance. mcp_server.py::build_compare_payload
    # is the source of truth; verify its top-level keys are present.
    expected_compare_keys = {"agent_guidance", "provenance"}
    actual_keys = set(payload_a.keys())
    driver.record(
        "L6", "frame_compare payload carries agent_guidance + provenance",
        expected_compare_keys.issubset(actual_keys),
        f"missing={sorted(expected_compare_keys - actual_keys) or 'none'}; "
        f"all_keys={sorted(actual_keys)[:8]}",
    )

    # Reproducibility: byte-equivalent modulo wall-clock.
    a_clean = _strip_wall_clock(payload_a)
    b_clean = _strip_wall_clock(payload_b)
    same = a_clean == b_clean
    diff_summary = ""
    if not same:
        for k in set(a_clean) | set(b_clean):
            if a_clean.get(k) != b_clean.get(k):
                diff_summary = f"first_differing_key={k}"
                break
    driver.record(
        "L6", "frame_compare is deterministic mod wall-clock",
        same, diff_summary,
    )


# ── Layer 7: divergence_rendering enum ────────────────────────────


def layer7_rendering(driver: Driver) -> None:
    """Contract §3.3 enumerates four divergence_rendering values:
    list, completeness_check, teaching_questions, narrative.
    teaching_questions is the only mode that adds a teaching_question
    field to each AbsentFrameRecord per §4.2 optional fields. This
    layer drives all four and verifies the contract-promised
    decoration."""
    print("\n--- Layer 7: divergence_rendering enum ---")
    doc = (
        "Revenue grew 50% to $200M in Q3. Growth has been steady. "
        "The strategy is delivering. Customers love the product."
    )
    by_rendering: dict[str, dict] = {}
    for rendering in DIVERGENCE_RENDERINGS:
        try:
            resp = driver.call("tools/call", {
                "name": "frame_check",
                "arguments": {
                    "document_text": doc,
                    "include_divergence": True,
                    "divergence_rendering": rendering,
                },
            })
        except RuntimeError as e:
            driver.record(
                "L7", f"frame_check rendering={rendering}", False, str(e),
            )
            continue
        if resp.get("result", {}).get("isError") is not False:
            driver.record(
                "L7", f"frame_check rendering={rendering}",
                False, "isError=true",
            )
            continue
        payload = json.loads(resp["result"]["content"][0]["text"])
        by_rendering[rendering] = payload

    driver.record(
        "L7", f"all {len(DIVERGENCE_RENDERINGS)} renderings accepted",
        len(by_rendering) == len(DIVERGENCE_RENDERINGS),
        f"accepted={sorted(by_rendering)}",
    )

    # teaching_questions adds a teaching_question field per record;
    # the other three modes do not. Verified against contract §4.2.
    tq_payload = by_rendering.get("teaching_questions", {})
    list_payload = by_rendering.get("list", {})
    if tq_payload and list_payload:
        tq_records = (tq_payload.get("divergence", {}) or {}).get(
            "absent_frames", []) or []
        list_records = (list_payload.get("divergence", {}) or {}).get(
            "absent_frames", []) or []
        tq_with_field = sum(
            1 for r in tq_records
            if isinstance(r, dict) and "teaching_question" in r
        )
        list_with_field = sum(
            1 for r in list_records
            if isinstance(r, dict) and "teaching_question" in r
        )
        driver.record(
            "L7",
            "teaching_questions mode adds teaching_question per record",
            tq_with_field == len(tq_records) and tq_with_field > 0,
            f"tq={tq_with_field}/{len(tq_records)}",
        )
        driver.record(
            "L7",
            "list mode does NOT add teaching_question per record",
            list_with_field == 0,
            f"list_with_field={list_with_field}/{len(list_records)}",
        )


# ── Layer 8: resource contentHash integrity ───────────────────────


def layer8_content_hash(driver: Driver) -> None:
    """Every advertised resource carries a contentHash (per
    conformance driver test 11). The contract implies this is the
    SHA256 of the content; an integrator using the hash as a cache
    key (which is the documented use case) gets stale bytes if the
    hash does not actually match. This layer fetches a sample of
    resources and verifies hash matches."""
    print("\n--- Layer 8: resource contentHash integrity ---")
    try:
        resp = driver.call("resources/list")
    except RuntimeError as e:
        driver.record("L8", "resources/list", False, str(e))
        return
    resources = resp["result"]["resources"]
    # Sample across resource types (library, methodology, spec,
    # transmissions, worked-examples) so the check is not biased to
    # one URI prefix.
    seen_prefixes: set[str] = set()
    sample: list[dict] = []
    for r in resources:
        prefix = "/".join((r.get("uri", "") or "").split("/")[:4])
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        sample.append(r)
        if len(sample) >= 6:
            break
    mismatches: list[str] = []
    for r in sample:
        uri = r.get("uri", "")
        advertised = r.get("contentHash", "")
        content = driver.resources_read(uri)
        if content is None:
            mismatches.append(f"{uri}: read failed")
            continue
        text = content.get("text", "")
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if advertised != actual:
            mismatches.append(
                f"{uri}: advertised={advertised[:12]}... actual={actual[:12]}..."
            )
    driver.record(
        "L8",
        f"contentHash matches sha256(text) on {len(sample)} sampled resources",
        not mismatches,
        f"mismatches={mismatches[:2] or 'none'}",
    )


# ── Reporter ──────────────────────────────────────────────────────


def write_report_md(findings: list[Finding], path: Path,
                    summary: dict) -> None:
    by_layer: dict[str, list[Finding]] = {}
    for f in findings:
        by_layer.setdefault(f.layer, []).append(f)
    lines: list[str] = []
    lines.append("# MCP Quality Driver Report")
    lines.append("")
    lines.append(f"**Mode:** {summary['mode']}  ")
    lines.append(f"**Generated:** {summary['generated_at']}  ")
    lines.append(f"**Result:** {summary['passed']}/{summary['total']} passed")
    lines.append("")
    for layer in sorted(by_layer):
        layer_findings = by_layer[layer]
        layer_pass = sum(1 for f in layer_findings if f.ok)
        lines.append(f"## {layer}: {layer_pass}/{len(layer_findings)}")
        lines.append("")
        for f in layer_findings:
            flag = "PASS" if f.ok else "FAIL"
            note = f"  -- {f.note}" if f.note else ""
            lines.append(f"- **{flag}**  {f.name}{note}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report_json(findings: list[Finding], path: Path,
                      summary: dict) -> None:
    out = {
        **summary,
        "findings": [dataclasses.asdict(f) for f in findings],
    }
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


# ── main ──────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", action="store_true",
                    help="Drive mcp_server.py from the source tree (default).")
    ap.add_argument("--wheel", action="store_true",
                    help=f"Drive the wheel installed at {WHEEL_TARGET}.")
    ap.add_argument("--corpus", type=int, default=6,
                    help="Number of real-corpus documents to drive (default: 6).")
    ap.add_argument("--report-md", type=Path, default=None,
                    help="Write markdown report to PATH.")
    ap.add_argument("--report-json", type=Path, default=None,
                    help="Write JSON report to PATH.")
    args = ap.parse_args()

    if args.wheel and args.source:
        print("ERROR: --wheel and --source are mutually exclusive", file=sys.stderr)
        return 2
    mode = "wheel" if args.wheel else "source"

    driver = Driver(mode=mode, corpus_size=args.corpus)
    print(f"=== mcp_quality_driver mode={mode} corpus={args.corpus} ===")
    driver.start()
    stderr_tail = ""
    try:
        try:
            driver.initialize()
        except RuntimeError as e:
            print(f"FATAL: initialize failed: {e}", file=sys.stderr)
            return 2

        layer1_structural(driver)
        layer2_divergence(driver)
        layer3_reproducibility(driver)
        layer4_adversarial(driver)
        layer5_corpus(driver)
        layer6_frame_compare(driver)
        layer7_rendering(driver)
        layer8_content_hash(driver)
    finally:
        stderr_tail = driver.stop()

    passed = sum(1 for f in driver.findings if f.ok)
    total = len(driver.findings)
    print(f"\n=== summary: {passed}/{total} passed ===")
    if stderr_tail.strip():
        print(f"\n--- server stderr tail (last 1500 bytes) ---")
        print(stderr_tail[-1500:])

    summary = {
        "mode": mode,
        "corpus_size": args.corpus,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": passed,
        "total": total,
    }
    if args.report_md:
        write_report_md(driver.findings, args.report_md, summary)
        print(f"wrote markdown report to {args.report_md}")
    if args.report_json:
        write_report_json(driver.findings, args.report_json, summary)
        print(f"wrote JSON report to {args.report_json}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
