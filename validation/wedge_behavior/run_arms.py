"""Execute the two arms of the wedge_behavior pilot via Anthropic API.

Per PROTOCOL_v1: same agent (Claude Sonnet 4.6), fixed temperature
0.7, fixed system prompt, separate sessions per arm (no carryover —
each API call is a fresh session by definition), same user prompt
across arms (only the with-tool-frame-check-output is the
manipulated variable).

Reads `without_tool_prompt.txt` and `with_tool_prompt.txt` from the
results_v1/<slug>/ directory (produced by run_pilot.py) and writes
`without.md` and `with.md` with the agent responses + a metadata
header naming model + temperature + token usage + arm-execution-order.

Requires ANTHROPIC_API_KEY in the environment. Cost ~$0.02 per call,
~$0.08 per document run, well under the protocol's $1 ceiling.

Usage:
    ANTHROPIC_API_KEY=... python3 \\
        validation/wedge_behavior/run_arms.py <doc-slug>
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import anthropic  # type: ignore

PILOT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PILOT_DIR / "results_v1"

# Pre-registered model + temp per PROTOCOL_v1.md (sec "Treatment design")
MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.7
MAX_TOKENS = 4000  # bumped from 2000 after pilot showed with-tool arm
                   # truncating; both arms held to same cap so the
                   # comparison stays paired.
SYSTEM_PROMPT = "You are a helpful assistant."


def _call_claude(client, prompt_text):
    t0 = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_text}],
    )
    elapsed = time.perf_counter() - t0
    text = "".join(b.text for b in response.content if b.type == "text")
    return {
        "text": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "elapsed_s": round(elapsed, 2),
        "model": response.model,
        "id": response.id,
    }


def _save_arm(slug_dir, arm_name, prompt_text, result, order_position):
    """Write the arm response with a metadata header for the rater."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    md = (
        f"# {arm_name.replace('_', '-')}-tool arm response\n\n"
        f"<!--\n"
        f"  Pilot execution metadata (per validation/wedge_behavior/PROTOCOL_v1.md):\n"
        f"    - model:           {result['model']}\n"
        f"    - temperature:     {TEMPERATURE}\n"
        f"    - system_prompt:   {SYSTEM_PROMPT!r}\n"
        f"    - max_tokens:      {MAX_TOKENS}\n"
        f"    - input_tokens:    {result['input_tokens']}\n"
        f"    - output_tokens:   {result['output_tokens']}\n"
        f"    - elapsed_s:       {result['elapsed_s']}\n"
        f"    - response_id:     {result['id']}\n"
        f"    - executed_utc:    {timestamp}\n"
        f"    - arm_order:       {order_position} of 2 in this doc-slug run\n"
        f"-->\n\n"
        f"{result['text']}\n"
    )
    out = slug_dir / f"{arm_name}.md"
    out.write_text(md, encoding="utf-8")
    print(f"  saved {arm_name}.md ({result['input_tokens']} in / {result['output_tokens']} out / {result['elapsed_s']}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="doc-slug under results_v1/")
    ap.add_argument(
        "--order",
        choices=("without_first", "with_first"),
        default="without_first",
        help="Arm execution order. Pre-reg says randomize per doc; "
             "operator picks per invocation.",
    )
    args = ap.parse_args()

    slug_dir = RESULTS_DIR / args.slug
    if not slug_dir.is_dir():
        print(f"slug dir not found: {slug_dir}", file=sys.stderr)
        return 1

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    without_prompt = (slug_dir / "without_tool_prompt.txt").read_text()
    with_prompt = (slug_dir / "with_tool_prompt.txt").read_text()

    client = anthropic.Anthropic()
    print(f"== {args.slug} (order={args.order}) ==")
    print(f"  model={MODEL}, temp={TEMPERATURE}, max_tokens={MAX_TOKENS}")

    arms = [
        ("without", without_prompt),
        ("with", with_prompt),
    ]
    if args.order == "with_first":
        arms = list(reversed(arms))

    for i, (name, prompt) in enumerate(arms, start=1):
        print(f"\n  arm {i}/2: {name}-tool")
        result = _call_claude(client, prompt)
        _save_arm(slug_dir, name, prompt, result, i)

    print(f"\n  done. responses in {slug_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
