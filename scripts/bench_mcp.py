#!/usr/bin/env python3
"""Latency and token-cost benchmark for the frame_check MCP tool.

Calls handle_tools_call(frame_check, document_text) N times for each
of three fixed-size benchmark documents and reports:

  - p50 / p95 wall-clock latency per document (ms)
  - char count of the agent_guidance block (token-cost proxy)
  - char count of the analysis block (substrate size proxy)
  - total response size

Output is a markdown table written to docs/BENCHMARK_v0.md so the
README can link to a stable snapshot. Run before each release to
keep the table current; CI integration is a follow-up.

Methodology:

  - The three documents are real worked examples, sized small / medium
    / large in word count. Same documents on each release so deltas
    are interpretable.
  - N=10 iterations per document with the first-iteration warm-up
    discarded so cold-start cost does not dominate.
  - Wall-clock measured around handle_tools_call only. Network and
    JSON-RPC framing are excluded; integrators should add their own
    transport-layer overhead estimate.
  - Token cost is reported as character count, not BPE token count,
    to avoid a tiktoken dependency. Rule of thumb: divide by 4 for an
    approximate token count on Anthropic / OpenAI tokenizers.

Usage:
  python3 scripts/bench_mcp.py            # writes docs/BENCHMARK_v0.md
  python3 scripts/bench_mcp.py --stdout   # also prints to stdout
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# Add repo root to sys.path so this script is runnable from anywhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import mcp_server  # noqa: E402  (after sys.path mutation)


# Three worked examples of varied size. Picked because they exist on
# disk in the repo, are stable across runs, and span a reasonable
# range of analytical-prose word counts.
BENCH_DOCS = [
    ("small", "data/worked_examples/fomc-statement-march-2026.md"),
    ("medium", "data/worked_examples/ai-on-life-decisions-startup-2026.md"),
    ("large", "data/worked_examples/divergence-on-claude-bitcoin-retirement-2026.md"),
]

ITERATIONS = 10  # First iteration discarded as warm-up.


def _measure_one_call(document_text: str) -> tuple[float, dict]:
    """Run a single frame_check call, return (elapsed_ms, response).

    Wall-clock spans handle_tools_call only; transport-layer cost is
    excluded so the number reflects the engine, not the framing.
    """
    t0 = time.perf_counter()
    response = mcp_server.handle_tools_call({
        "name": "frame_check",
        "arguments": {"document_text": document_text},
    })
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return elapsed_ms, response


def _extract_block_sizes(response: dict) -> dict[str, int]:
    """Pull the load-bearing block sizes out of the response.

    handle_tools_call returns an MCP-shape dict with the analysis
    payload serialized into content[0].text as JSON. Parse it back so
    we can size each block independently. Failure modes return -1 for
    the broken size so the table surfaces the breakage instead of
    silently zeroing it.
    """
    content = response.get("content")
    if not isinstance(content, list) or not content:
        return {"total": -1, "agent_guidance": -1, "analysis": -1}
    body = content[0].get("text", "")
    total_chars = len(body)
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return {"total": total_chars, "agent_guidance": -1, "analysis": -1}
    ag = parsed.get("agent_guidance")
    an = parsed.get("analysis")
    return {
        "total": total_chars,
        "agent_guidance": len(json.dumps(ag)) if ag else 0,
        "analysis": len(json.dumps(an)) if an else 0,
    }


def _bench_doc(label: str, path: str) -> dict:
    """Benchmark one document. Returns a row dict for the markdown table."""
    full_path = _REPO_ROOT / path
    document_text = full_path.read_text(encoding="utf-8")
    word_count = len(document_text.split())
    char_count = len(document_text)

    latencies = []
    last_sizes = {"total": 0, "agent_guidance": 0, "analysis": 0}

    for i in range(ITERATIONS):
        ms, response = _measure_one_call(document_text)
        if i == 0:
            # Discard cold-start; subsequent iterations measure warm
            # behavior, which is closer to integrator steady-state.
            continue
        latencies.append(ms)
        last_sizes = _extract_block_sizes(response)

    p50 = statistics.median(latencies) if latencies else 0.0
    # statistics.quantiles with n=20 gives p95 as the 19th cut on a
    # 9-sample list; on 9 samples we approximate with index-based pick.
    sorted_lat = sorted(latencies)
    p95_index = max(0, int(len(sorted_lat) * 0.95) - 1)
    p95 = sorted_lat[p95_index] if sorted_lat else 0.0

    return {
        "label": label,
        "path": path,
        "word_count": word_count,
        "char_count": char_count,
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "agent_guidance_chars": last_sizes["agent_guidance"],
        "analysis_chars": last_sizes["analysis"],
        "total_response_chars": last_sizes["total"],
    }


def _render_markdown(rows: list[dict]) -> str:
    """Render the benchmark rows as a markdown table.

    Char counts have an approximate token-count column (chars / 4) so
    integrators sizing token budget see both numbers. The /4 ratio is
    a documented rule-of-thumb for Anthropic and OpenAI tokenizers on
    English analytical prose; actual token count varies.
    """
    lines = []
    lines.append(f"# frame_check MCP benchmark (v{mcp_server.SERVER_VERSION})")
    lines.append("")
    lines.append(
        f"Benchmark snapshot. Methodology in `scripts/bench_mcp.py`. "
        f"Wall-clock measures `handle_tools_call` only; integrators "
        f"add their own transport-layer overhead. Token-count column "
        f"is `chars / 4` rule-of-thumb for English on Anthropic and "
        f"OpenAI tokenizers; actual token count varies."
    )
    lines.append("")
    lines.append(f"Iterations per document: {ITERATIONS} (first discarded as warm-up).")
    lines.append("")
    lines.append("## Latency")
    lines.append("")
    lines.append("| Doc | Words | Chars | p50 (ms) | p95 (ms) |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['word_count']:,} | {r['char_count']:,} | "
            f"{r['p50_ms']} | {r['p95_ms']} |"
        )
    lines.append("")
    lines.append("## Response size and approximate token budget")
    lines.append("")
    lines.append(
        "| Doc | analysis (chars) | analysis (~tokens) | "
        "agent_guidance (chars) | agent_guidance (~tokens) | "
        "total response (chars) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in rows:
        ag_chars = r['agent_guidance_chars']
        an_chars = r['analysis_chars']
        total_chars = r['total_response_chars']
        ag_tokens = ag_chars // 4 if ag_chars > 0 else 0
        an_tokens = an_chars // 4 if an_chars > 0 else 0
        lines.append(
            f"| {r['label']} | {an_chars:,} | ~{an_tokens:,} | "
            f"{ag_chars:,} | ~{ag_tokens:,} | {total_chars:,} |"
        )
    lines.append("")
    lines.append("## Reading the numbers")
    lines.append("")
    lines.append(
        "**Latency.** p50 is the typical case; p95 catches occasional "
        "garbage-collection or cache-miss spikes. The numbers above "
        "are single-thread on the benchmark machine; production "
        "latency depends on hardware and concurrent load."
    )
    lines.append("")
    lines.append(
        "**`analysis` size** scales with the document. The substrate "
        "is the structural measurement (coverage, voice, temporal, "
        "frame_library_matches, divergence). An integrator who only "
        "wants the structural numbers can extract `analysis` and "
        "ignore the rest."
    )
    lines.append("")
    lines.append(
        "**`agent_guidance` size** is roughly fixed per call: the "
        "composition discipline, the citation rules, the scope-regime "
        "guidance. An integrator with a tight token budget can request "
        "a smaller `agent_guidance` via the `compose_budget` parameter "
        "(see the tool's `inputSchema`)."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Also print the rendered markdown to stdout.",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "docs" / "BENCHMARK_v0.md"),
        help="Output path. Default: docs/BENCHMARK_v0.md.",
    )
    args = parser.parse_args()

    print(f"Benchmarking frame_check (server v{mcp_server.SERVER_VERSION})...",
          file=sys.stderr)
    rows = []
    for label, path in BENCH_DOCS:
        print(f"  {label}: {path}", file=sys.stderr)
        rows.append(_bench_doc(label, path))

    markdown = _render_markdown(rows)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)

    if args.stdout:
        print(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
