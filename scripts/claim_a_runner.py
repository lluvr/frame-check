#!/usr/bin/env python3
"""Claim A experimental runner: chain-output vs single-frame-output on decision quality.

Executes the experiment per CLAIM_A_PROTOCOL_v1.md sections 4 (treatments) and 6.1
(generation phase). Generates outputs with randomized UUIDs and a sealed
treatment-ID mapping. Resumable; cost-bounded; operator-paid (Grok or Gemini).

Default behavior is dry-run (no API calls). Pass --authorize-spend to actually run.

Pre-execution checklist per CLAIM_A_PROTOCOL_v1.md section 12 must be approved
by the operator before running with --authorize-spend.

Usage:
    python scripts/claim_a_runner.py \\
        --cases-dir data/claim_a/cases/ \\
        --output-dir data/claim_a/outputs/ \\
        --model-family grok \\
        --model-id grok-4-fast-non-reasoning

Add --authorize-spend to make actual API calls.
Add --resume to skip cases with completed outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Protocol section 4.1: Single-frame divergence (FVS-011 Stakeholder Frame baseline).
SINGLE_FRAME_PROMPT = """You are applying the Stakeholder Frame to a decision case. The Stakeholder Frame asks: who is affected by this decision, who benefits, who bears costs, whose perspective is represented, whose is excluded.

Decision case:
{case_text}

Apply the Stakeholder Frame to this case. Produce a structured analysis covering:
1. Stakeholders identified (named groups or roles affected by the decision)
2. Interests of each stakeholder (what they gain or lose under the decision)
3. Power dynamics (who has agency, who is acted upon)
4. Whose perspective is represented in the current framing, whose is absent
5. What the decision-maker should consider before committing

Be specific. Avoid generic stakeholder language ("our employees, our communities" without analysis). Identify concrete impacts."""


# Protocol section 4.2: Adversarial chain six-step prompts.
CHAIN_PROMPTS: dict[str, str] = {
    "optimist": """Read the following decision case and apply the Optimist frame.

Decision case:
{case_text}

From an optimist frame, name:
- The strongest reasons to proceed with this decision
- The most attractive outcomes if everything goes right
- The opportunities the decision opens up

Be specific. Avoid generic optimism. Anchor in case details.""",
    "realist": """Continue the analysis. The optimist frame produced this output:

[STEP 1 OUTPUT]
{step_1_output}
[END STEP 1 OUTPUT]

Decision case (for reference):
{case_text}

Apply the Realist frame: identify the realistic costs, dependencies, and constraints that the optimist frame underweights. Name what is plausible vs what is aspirational. Anchor in case specifics.""",
    "adversary": """Continue the analysis. Prior steps produced:

[STEP 1 - OPTIMIST]
{step_1_output}

[STEP 2 - REALIST]
{step_2_output}

Decision case (for reference):
{case_text}

Apply the Adversary frame: identify adversarial scenarios. What could a hostile actor exploit? What could go catastrophically wrong? What dependencies could fail under stress? What second-order effects could undermine the decision? Be concrete about failure modes.""",
    "premortem": """Continue the analysis. Prior steps produced:

[STEP 1 - OPTIMIST]
{step_1_output}

[STEP 2 - REALIST]
{step_2_output}

[STEP 3 - ADVERSARY]
{step_3_output}

Decision case (for reference):
{case_text}

Apply the Premortem frame: imagine 24 months from now this decision was a disaster. Name the most likely failure modes. Label them (a), (b), (c), (d) - aim for 3 to 5 specific failure modes that are concrete enough to mitigate against.""",
    "mitigation": """Continue the analysis. Prior steps produced:

[STEPS 1-3]
{steps_1_to_3_outputs}

[STEP 4 - PREMORTEM]
{step_4_output}

Decision case (for reference):
{case_text}

Apply the Mitigation frame: for each failure mode (a) through (d) named in the premortem, propose a pre-mitigation that could be implemented before commitment to reduce probability or impact. Be specific about what pre-mitigation looks like operationally.""",
    "commitment": """Synthesize the prior steps into a structured commitment.

[FULL CHAIN ACCUMULATOR]
{full_accumulator}

Decision case (for reference):
{case_text}

Produce a commitment statement with:
1. The recommended commitment: proceed with conditions, defer, or reject (one of these).
2. If proceeding with conditions: list the specific conditions that must be met before proceeding, anchored to the failure modes the premortem identified and the mitigations Step 5 proposed.
3. If deferring: name what would change the decision (what additional information or conditions would unlock proceeding).
4. Acknowledge: which adversary or premortem concerns are NOT fully mitigated. Do not pretend all risks are addressed.

The commitment is the chain's output to the decision-maker.""",
}

CHAIN_STEPS = ["optimist", "realist", "adversary", "premortem", "mitigation", "commitment"]


# Protocol section 9.1: hard cost ceiling.
COST_CEILING_USD = 1.00

# Approximate pricing per 1K tokens. Adjust if API pricing changes.
PRICING = {
    "grok": {"input_per_1k": 0.0002, "output_per_1k": 0.0010},
    "gemini": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
}

API_BASE_URLS = {
    "grok": "https://api.x.ai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

API_KEY_ENV_VARS = {
    "grok": "GROK_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def estimate_cost(prompt_tokens: int, completion_tokens: int, model_family: str) -> float:
    pricing = PRICING.get(model_family, PRICING["grok"])
    return (
        prompt_tokens * pricing["input_per_1k"] / 1000.0
        + completion_tokens * pricing["output_per_1k"] / 1000.0
    )


def load_cases(cases_dir: Path) -> list[dict[str, str]]:
    """Load case files. Each case is a .txt file in the protocol section 3.2 format."""
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"Cases directory not found: {cases_dir}")
    cases: list[dict[str, str]] = []
    for case_file in sorted(cases_dir.glob("*.txt")):
        case_id = case_file.stem
        case_text = case_file.read_text(encoding="utf-8").strip()
        if not case_text:
            print(f"WARN: skipping empty case file: {case_file}")
            continue
        cases.append({"case_id": case_id, "case_text": case_text})
    return cases


def llm_call(
    client: Any,
    model_id: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    model_family: str,
    retries: int = 3,
) -> tuple[str, int, int, float]:
    """Make one LLM call with exponential-backoff retry per protocol section 4.3."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content or ""
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            cost = estimate_cost(prompt_tokens, completion_tokens, model_family)
            return text, prompt_tokens, completion_tokens, cost
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                break
    assert last_error is not None
    raise last_error


def run_single_frame(
    client: Any,
    case: dict[str, str],
    model_id: str,
    model_family: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Execute single-frame treatment per protocol section 4.1."""
    prompt = SINGLE_FRAME_PROMPT.format(case_text=case["case_text"])
    text, in_tok, out_tok, cost = llm_call(
        client, model_id, prompt, temperature, max_tokens, model_family
    )
    return {
        "treatment": "single_frame",
        "case_id": case["case_id"],
        "output": text,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
        "cost": cost,
        "timestamp": utcnow_iso(),
    }


def run_chain(
    client: Any,
    case: dict[str, str],
    model_id: str,
    model_family: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Execute adversarial chain treatment per protocol section 4.2."""
    accumulator: dict[str, str] = {}
    total_in_tok = 0
    total_out_tok = 0
    total_cost = 0.0

    for step in CHAIN_STEPS:
        format_args: dict[str, str] = {"case_text": case["case_text"]}
        if step == "realist":
            format_args["step_1_output"] = accumulator["optimist"]
        elif step == "adversary":
            format_args["step_1_output"] = accumulator["optimist"]
            format_args["step_2_output"] = accumulator["realist"]
        elif step == "premortem":
            format_args["step_1_output"] = accumulator["optimist"]
            format_args["step_2_output"] = accumulator["realist"]
            format_args["step_3_output"] = accumulator["adversary"]
        elif step == "mitigation":
            steps_1_3 = "\n\n".join(
                f"[STEP {i + 1} - {s.upper()}]\n{accumulator[s]}"
                for i, s in enumerate(["optimist", "realist", "adversary"])
            )
            format_args["steps_1_to_3_outputs"] = steps_1_3
            format_args["step_4_output"] = accumulator["premortem"]
        elif step == "commitment":
            full_accumulator = "\n\n".join(
                f"[STEP {i + 1} - {s.upper()}]\n{accumulator[s]}"
                for i, s in enumerate(CHAIN_STEPS[:-1])
            )
            format_args["full_accumulator"] = full_accumulator

        prompt = CHAIN_PROMPTS[step].format(**format_args)
        text, in_tok, out_tok, cost = llm_call(
            client, model_id, prompt, temperature, max_tokens, model_family
        )
        accumulator[step] = text
        total_in_tok += in_tok
        total_out_tok += out_tok
        total_cost += cost

    return {
        "treatment": "adversarial_chain",
        "case_id": case["case_id"],
        "output": accumulator["commitment"],
        "accumulator": accumulator,
        "prompt_tokens": total_in_tok,
        "completion_tokens": total_out_tok,
        "cost": total_cost,
        "timestamp": utcnow_iso(),
    }


def save_output(
    output_dir: Path,
    case_id: str,
    treatment: str,
    result: dict[str, Any],
    mapping: list[dict[str, Any]],
) -> str:
    """Save output with randomized UUID and append to mapping."""
    output_uuid = str(uuid.uuid4())
    output_file = output_dir / f"output_{output_uuid}.txt"
    output_file.write_text(result["output"], encoding="utf-8")

    if treatment == "adversarial_chain":
        accumulator_dir = output_dir / "accumulator" / output_uuid
        accumulator_dir.mkdir(parents=True, exist_ok=True)
        for i, step in enumerate(CHAIN_STEPS, 1):
            (accumulator_dir / f"step_{i:02d}_{step}.txt").write_text(
                result["accumulator"][step], encoding="utf-8"
            )

    mapping.append(
        {
            "output_uuid": output_uuid,
            "case_id": case_id,
            "treatment": treatment,
            "timestamp": result["timestamp"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "cost": result["cost"],
        }
    )
    return output_uuid


def write_mapping(mapping_file: Path, mapping: list[dict[str, Any]]) -> None:
    """Atomic write of the sealed mapping file."""
    tmp = mapping_file.with_suffix(mapping_file.suffix + ".tmp")
    tmp.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    tmp.replace(mapping_file)


def write_log(log_file: Path, log_entries: list[dict[str, Any]]) -> None:
    log_file.write_text(json.dumps(log_entries, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-family", choices=["grok", "gemini"], required=True)
    parser.add_argument("--model-id", required=True, help="Provider model ID (e.g., grok-4-fast-non-reasoning)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument(
        "--authorize-spend",
        action="store_true",
        help="Required to actually call APIs. Default is dry-run.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip cases with completed outputs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_file = args.output_dir / "run_log.json"
    mapping_file = args.output_dir / "treatment_mapping.SEALED.json"

    cases = load_cases(args.cases_dir)
    print(f"Loaded {len(cases)} cases from {args.cases_dir}")
    if not cases:
        print("No cases found. Aborting.")
        return 1

    if not args.authorize_spend:
        per_case_estimate = (
            0.001 + 0.012
            if args.model_family == "grok"
            else 0.005 + 0.04
        )
        total_estimate = len(cases) * per_case_estimate
        print()
        print("DRY RUN. No API calls made.")
        print(f"Cases: {len(cases)}")
        print(f"Outputs that would be generated: {len(cases) * 2}")
        print(f"Estimated cost: ~${total_estimate:.2f}")
        print(f"Hard cost ceiling: ${COST_CEILING_USD:.2f}")
        print(f"Output directory: {args.output_dir}")
        print()
        print("To actually run: pass --authorize-spend")
        return 0

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package required. Install with: pip install openai", file=sys.stderr)
        return 1

    api_key_env = API_KEY_ENV_VARS[args.model_family]
    api_key = os.environ.get(api_key_env)
    if not api_key:
        print(f"ERROR: {api_key_env} environment variable not set", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key, base_url=API_BASE_URLS[args.model_family])

    mapping: list[dict[str, Any]] = []
    completed_keys: set[tuple[str, str]] = set()
    if args.resume and mapping_file.exists():
        mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
        completed_keys = {(m["case_id"], m["treatment"]) for m in mapping}
        print(f"Resuming with {len(mapping)} existing outputs")

    total_spend = sum(float(m.get("cost", 0.0)) for m in mapping)
    log_entries: list[dict[str, Any]] = []
    halted = False

    for case in cases:
        if halted:
            break
        for treatment in ["single_frame", "adversarial_chain"]:
            if (case["case_id"], treatment) in completed_keys:
                print(f"  SKIP {case['case_id']} {treatment} (already complete)")
                continue
            if total_spend >= COST_CEILING_USD:
                print(f"\nCOST CEILING REACHED (${total_spend:.4f} >= ${COST_CEILING_USD}). Halting.")
                halted = True
                break

            print(f"  RUN  {case['case_id']} {treatment}", flush=True)
            try:
                if treatment == "single_frame":
                    result = run_single_frame(
                        client,
                        case,
                        args.model_id,
                        args.model_family,
                        args.temperature,
                        args.max_tokens,
                    )
                else:
                    result = run_chain(
                        client,
                        case,
                        args.model_id,
                        args.model_family,
                        args.temperature,
                        args.max_tokens,
                    )
                output_uuid = save_output(args.output_dir, case["case_id"], treatment, result, mapping)
                total_spend += float(result["cost"])
                log_entries.append(
                    {
                        "timestamp": utcnow_iso(),
                        "event": "output_saved",
                        "case_id": case["case_id"],
                        "treatment": treatment,
                        "output_uuid": output_uuid,
                        "cost": result["cost"],
                        "cumulative_spend": total_spend,
                    }
                )
                write_mapping(mapping_file, mapping)
            except Exception as exc:
                log_entries.append(
                    {
                        "timestamp": utcnow_iso(),
                        "event": "error",
                        "case_id": case["case_id"],
                        "treatment": treatment,
                        "error": str(exc),
                    }
                )
                print(f"    ERROR: {exc}", file=sys.stderr)

    write_log(log_file, log_entries)

    # Summary of failed cases (per stress-test improvement).
    error_entries = [e for e in log_entries if e.get("event") == "error"]
    if error_entries:
        print(f"\n{len(error_entries)} treatment(s) FAILED:")
        for entry in error_entries:
            print(f"  FAILED: {entry['case_id']} {entry['treatment']} -- {entry['error']}")
        print("\nFailed treatments are excluded from analysis (per CLAIM_A_PROTOCOL_v1.md §4.3).")
        print("Re-run with --resume to retry, or accept exclusions and adjust §7 sample size.")

    print(f"\nDone. Total spend: ${total_spend:.4f}")
    print(f"Outputs recorded: {len(mapping)}")
    print(f"Mapping (SEALED until grading complete): {mapping_file}")
    print(f"Log: {log_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
