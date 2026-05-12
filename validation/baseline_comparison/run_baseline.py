"""Baseline-comparison harness for the pre-registered protocol.

Reads a corpus of documents (operator-curated, NOT from the bundled
worked examples — see PROTOCOL_v1.md sample-selection criteria),
runs each through Frame Check + the pre-registered LLM baseline, and
captures structured outputs for downstream rater scoring.

Status of execution chain:
- Frame Check side: ready to run from this harness (deterministic, no
  external services).
- LLM baseline side: requires an API key for the pre-registered model.
  Default candidate: Claude Sonnet 4.6 (ANTHROPIC_API_KEY supplied
  by the operator through their secrets infrastructure). Operator
  selects at run time.
- Rater scoring: human-handed; harness only produces inputs for raters
  + a render of the Frame Check payload as readable markdown.

Invocation:
    python3 validation/baseline_comparison/run_baseline.py \\
        --corpus validation/baseline_comparison/corpus_v1.json \\
        --results-dir validation/baseline_comparison/results/pilot \\
        --llm-model claude-sonnet-4-6 \\
        --runs-per-side 5  # H3 reproducibility test

The harness does NOT execute the LLM call by default; the operator
passes a --call-llm flag only when running with credentials available
and authorization to bill against them. Without --call-llm, the
harness produces the Frame Check side + a placeholder llm_baseline
file the operator fills in manually or via a separate authenticated
invocation.

Pre-registered design constraints (do not modify without versioning
the protocol):
  - Same prompt template across all documents.
  - Same model + temperature across all documents.
  - 5 runs per side for H3 reproducibility measurement.
  - LLM output captured as raw JSON for rater consumption; not
    post-processed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import mcp_server  # type: ignore  # noqa: E402


# Pre-registered prompt template (locked at protocol v1).
LLM_PROMPT_TEMPLATE = """You are analyzing a document's framing. Produce a structured analysis with:
- voice classification (one of: directive / promotional / descriptive / analytical)
- five analytical perspectives addressed (causes, risks, stakeholders, trends, uncertainty);
  for each, mark present or absent
- named framing patterns you detect (use the Frame Vocabulary Standard if you know it,
  otherwise describe in your own terms)
- structurally absent framing patterns the document does not address but
  comparable documents would
- numerical claims you can identify in the document; mark each as present in source or
  not present in source (if no source provided, mark "no source provided")

Document:
{document_text}

Source (for numerical claims):
{source_text}

Output as structured JSON. Do not include any commentary outside the JSON."""


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def run_frame_check(
    document_text: str,
    source_text: str | None,
    runs: int = 1,
) -> list[dict[str, Any]]:
    """Frame Check side of the comparison. Deterministic; expected
    to return byte-identical payloads across runs.

    Strips agent_guidance from each captured payload before return:
    the H3 analyzer only reads analysis.* fields, and the verbose
    composition_discipline / per-level claim treatment text under
    agent_guidance is wheel-emitted internal vocabulary that should
    not appear inline in committed data files. Stripping here keeps
    the captured data.json adopter-readable without touching the
    wheel's wire format."""
    out = []
    for _ in range(runs):
        p = mcp_server.build_epistemic_payload(
            document_text,
            source_text=source_text,
            include_divergence=True,
            domain_hint="finance",  # Pre-registered default; rationale: most
                                     # observed AI-summary use cases in the
                                     # bundled corpus are financial.
        )
        # Drop agent_guidance: not needed for the H3 measurement;
        # keeping it would commit verbose internal wire vocabulary
        # to the captured data file.
        p.pop("agent_guidance", None)
        out.append(p)
    return out


def run_llm_baseline_placeholder(
    document_text: str,
    source_text: str | None,
    model: str,
    runs: int = 1,
) -> list[dict[str, Any]]:
    """Placeholder when --call-llm is not passed. Produces a structured
    record naming what the operator needs to fill in. Keeps the
    harness usable without API keys for the Frame Check side."""
    prompt = LLM_PROMPT_TEMPLATE.format(
        document_text=document_text,
        source_text=source_text or "(no source provided)",
    )
    return [
        {
            "status": "PLACEHOLDER",
            "model": model,
            "prompt": prompt,
            "raw_response_text": None,
            "captured_at_utc": None,
            "run_index": i,
            "note": (
                "Harness invoked without --call-llm. Operator authorization "
                "required to bill API. Fill in raw_response_text from the "
                "operator-authenticated LLM call against this exact prompt "
                "+ model + temperature 0.7."
            ),
        }
        for i in range(runs)
    ]


def run_llm_baseline_anthropic(
    document_text: str,
    source_text: str | None,
    model: str,
    runs: int = 1,
) -> list[dict[str, Any]]:
    """Drive the LLM-baseline arm via Anthropic API. Pre-registered
    constraints per PROTOCOL_v1.md §"Treatment design": same model +
    temperature 0.7 + locked prompt template across all runs.
    Separate API calls per run = separate sessions (the H3
    reproducibility measurement requires no carryover).
    Requires ANTHROPIC_API_KEY in env."""
    import time as _time

    import anthropic  # type: ignore

    client = anthropic.Anthropic()
    prompt = LLM_PROMPT_TEMPLATE.format(
        document_text=document_text,
        source_text=source_text or "(no source provided)",
    )
    out = []
    for i in range(runs):
        t0 = _time.perf_counter()
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=0.7,
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = _time.perf_counter() - t0
        text = "".join(b.text for b in response.content if b.type == "text")
        out.append({
            "status": "executed",
            "model": response.model,
            "prompt": prompt,
            "raw_response_text": text,
            "captured_at_utc": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "run_index": i,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "elapsed_s": round(elapsed, 2),
            "response_id": response.id,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help=(
            "Path to corpus JSON. Schema: [{slug, document_text, "
            "source_text?, provenance}, ...]"
        ),
    )
    ap.add_argument(
        "--results-dir",
        type=Path,
        required=True,
        help="Directory to write per-document results under.",
    )
    ap.add_argument(
        "--llm-model",
        type=str,
        default="claude-sonnet-4-6",
        help="Pre-registered LLM model. Default: claude-sonnet-4-6.",
    )
    ap.add_argument(
        "--runs-per-side",
        type=int,
        default=1,
        help=(
            "Number of runs per side (H3 reproducibility test). "
            "Set to 5 for the H3 sub-study; default 1 for pilot."
        ),
    )
    ap.add_argument(
        "--call-llm",
        action="store_true",
        help=(
            "Actually invoke the LLM API. Without this flag, the LLM side "
            "produces a placeholder file naming what the operator needs to "
            "fill in. The Frame Check side runs either way."
        ),
    )
    args = ap.parse_args()

    # --call-llm: drive the LLM-baseline arm via Anthropic API.
    # Without --call-llm, the harness produces a placeholder file
    # the operator fills in via their authenticated LLM invocation.
    # Either path satisfies pre-reg as long as the prompt template
    # + model + temperature stay locked.

    corpus = json.loads(args.corpus.read_text())
    if not isinstance(corpus, list):
        raise SystemExit(
            f"corpus file {args.corpus} must contain a list of documents"
        )

    args.results_dir.mkdir(parents=True, exist_ok=True)

    print("Baseline harness v1 (PROTOCOL_v1)")
    print(f"  corpus:        {args.corpus} ({len(corpus)} documents)")
    print(f"  results_dir:   {args.results_dir}")
    print(f"  llm_model:     {args.llm_model}")
    print(f"  runs_per_side: {args.runs_per_side}")
    print()

    for doc in corpus:
        slug = doc["slug"]
        doc_dir = args.results_dir / slug
        doc_dir.mkdir(parents=True, exist_ok=True)
        document_text = doc["document_text"]
        source_text = doc.get("source_text")

        t0 = time.perf_counter()
        fc_runs = run_frame_check(
            document_text, source_text, runs=args.runs_per_side
        )
        fc_dt = (time.perf_counter() - t0) * 1000

        if args.call_llm:
            if "ANTHROPIC_API_KEY" not in os.environ:
                print("ANTHROPIC_API_KEY not set; --call-llm requires it",
                      file=sys.stderr)
                return 1
            llm_runs = run_llm_baseline_anthropic(
                document_text, source_text, args.llm_model,
                runs=args.runs_per_side,
            )
        else:
            llm_runs = run_llm_baseline_placeholder(
                document_text, source_text, args.llm_model,
                runs=args.runs_per_side,
            )

        record = {
            "slug": slug,
            "document_sha256": _sha256(document_text),
            "source_sha256": _sha256(source_text) if source_text else None,
            "provenance": doc.get("provenance", {}),
            "frame_check_runs": fc_runs,
            "frame_check_total_ms": round(fc_dt, 1),
            "llm_baseline_runs": llm_runs,
            "harness_version": "v1",
            "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        out_path = doc_dir / "data.json"
        out_path.write_text(json.dumps(record, indent=2, default=str))
        llm_status = (
            "executed" if args.call_llm else "placeholder"
        )
        print(f"  {slug}: frame_check {len(fc_runs)} runs, "
              f"{fc_dt:.0f}ms; llm {llm_status} x {len(llm_runs)}")

    print()
    print("Done. Next steps:")
    if args.call_llm:
        print("  1. LLM-baseline arm executed via Anthropic API.")
        print("  2. For H3 (reproducibility), run analyze_h3.py on the "
              "results dir.")
        print("  3. For H1 + H2 (require raters), score per "
              "rating_rubric_v1.md.")
    else:
        print("  1. Operator runs the LLM side against each prompt with "
              "ANTHROPIC_API_KEY or equivalent (or re-run with --call-llm).")
        print("  2. For H3, run analyze_h3.py once LLM responses captured.")
        print("  3. Raters score per rating_rubric_v1.md for H1 + H2.")


if __name__ == "__main__":
    main()
