#!/usr/bin/env python3
"""Pilot runner for the wedge behavior-change protocol.

Reads a document file, runs frame_check against it locally (via
mcp_server.handle_tools_call, no network round-trip), and prints
the two prompt templates the operator can paste into Claude:

  - WITHOUT-TOOL ARM: the agent sees only the document and the user
    prompt. No frame_check output. This is the baseline response
    for the comparison.
  - WITH-TOOL ARM: the agent sees the document, the user prompt,
    AND the frame_check output (which the runner inlines). This is
    the "agent has tool access" response.

Operator workflow:

  1. python3 validation/wedge_behavior/run_pilot.py <doc.md> --user-prompt "..."
  2. Copy the WITHOUT-TOOL ARM block into a fresh Claude session.
     Capture the response. Save to results_v1/<doc-slug>/without.md.
  3. Open a fresh Claude session (no carryover from step 2). Copy
     the WITH-TOOL ARM block. Capture the response. Save to
     results_v1/<doc-slug>/with.md.
  4. Score both responses against the rubric in PROTOCOL_v1.md
     using rubric_template.md as the form.
  5. Repeat for N=2 documents. The pilot calibrates the rubric;
     N=10 main study comes after.

This runner does NOT make LLM API calls. The operator runs the
prompts in their Claude session (memory: "I do have the test of
Claude. We're gonna design the tests to produce the results we
want."). Keeping the LLM calls operator-driven respects the
budget envelope and lets the operator verify the prompts before
sending.

Usage:
  python3 validation/wedge_behavior/run_pilot.py path/to/doc.md \\
    --user-prompt "Help me think about this document" \\
    --doc-slug my-doc-slug

Outputs are written to validation/wedge_behavior/results_v1/<slug>/:
  - frame_check_output.json     full frame_check payload
  - without_tool_prompt.txt     the prompt for the without-tool arm
  - with_tool_prompt.txt        the prompt for the with-tool arm
  - rubric_form.md              copy of rubric_template.md (rater form)

Operator pastes responses into without.md and with.md alongside.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import mcp_server  # noqa: E402

_PILOT_DIR = Path(__file__).resolve().parent
_RUBRIC_TEMPLATE = _PILOT_DIR / "rubric_template.md"


def _without_tool_prompt(document_text: str, user_prompt: str) -> str:
    """The baseline arm: agent sees only the document and the prompt."""
    return (
        f"User prompt: {user_prompt}\n\n"
        f"Document:\n---\n{document_text}\n---\n\n"
        f"Respond to the user's prompt about this document. "
        f"You have NO tool access; reason from the document text "
        f"alone."
    )


def _with_tool_prompt(
    document_text: str,
    user_prompt: str,
    frame_check_output: str,
) -> str:
    """The treatment arm: agent sees document, prompt, AND frame_check
    output. The frame_check_output is inlined as if the agent had
    just called the MCP tool. This is how a real agent loop would
    consume the output: the tool result is in the agent's context
    when the agent composes its response.
    """
    return (
        f"User prompt: {user_prompt}\n\n"
        f"Document:\n---\n{document_text}\n---\n\n"
        f"You called frame_check on this document. The tool returned:\n"
        f"---\n{frame_check_output}\n---\n\n"
        f"Respond to the user's prompt. Use the frame_check output "
        f"to compose your response per the agent_guidance discipline "
        f"the tool returned. Cite measurements as Framecheck's; "
        f"the reading is yours; reading-form, never verdict-form."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "document",
        type=Path,
        help="Path to the document file (markdown, plain text, etc.)",
    )
    parser.add_argument(
        "--user-prompt",
        default="Help me think about this document",
        help="The user prompt the agent responds to in both arms. "
             "Same prompt across arms; only the tool-access variable "
             "is manipulated.",
    )
    parser.add_argument(
        "--doc-slug",
        default=None,
        help="Slug for the output directory. Defaults to the "
             "document filename stem.",
    )
    parser.add_argument(
        "--compose-budget",
        choices=("full", "standard", "minimal"),
        default="full",
        help="Which agent_guidance budget to use in the with-tool "
             "arm. Default 'full' is the protocol-pre-registered "
             "treatment; 'minimal' is the follow-up to test whether "
             "the compressed agent_guidance preserves discipline.",
    )
    args = parser.parse_args()

    if not args.document.exists():
        print(f"Document not found: {args.document}", file=sys.stderr)
        return 1

    document_text = args.document.read_text(encoding="utf-8")
    slug = args.doc_slug or args.document.stem

    out_dir = _PILOT_DIR / "results_v1" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running frame_check on {args.document} ...", file=sys.stderr)
    response = mcp_server.handle_tools_call({
        "name": "frame_check",
        "arguments": {
            "document_text": document_text,
            "compose_budget": args.compose_budget,
        },
    })
    fc_text = response["content"][0]["text"]
    fc_parsed = json.loads(fc_text)

    (out_dir / "frame_check_output.json").write_text(
        json.dumps(fc_parsed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    without_prompt = _without_tool_prompt(document_text, args.user_prompt)
    with_prompt = _with_tool_prompt(document_text, args.user_prompt, fc_text)
    (out_dir / "without_tool_prompt.txt").write_text(
        without_prompt, encoding="utf-8",
    )
    (out_dir / "with_tool_prompt.txt").write_text(
        with_prompt, encoding="utf-8",
    )

    if _RUBRIC_TEMPLATE.exists():
        shutil.copy(_RUBRIC_TEMPLATE, out_dir / "rubric_form.md")

    # Stub files for the operator to paste responses into.
    without_md = out_dir / "without.md"
    with_md = out_dir / "with.md"
    if not without_md.exists():
        without_md.write_text(
            "# Without-tool arm response\n\n"
            "_Paste the Claude response from a fresh session that "
            "received the prompt in `without_tool_prompt.txt`._\n",
            encoding="utf-8",
        )
    if not with_md.exists():
        with_md.write_text(
            "# With-tool arm response\n\n"
            "_Paste the Claude response from a fresh session that "
            "received the prompt in `with_tool_prompt.txt`._\n",
            encoding="utf-8",
        )

    print(f"\nReady. Output dir: {out_dir}", file=sys.stderr)
    print("\nNext steps:", file=sys.stderr)
    print("  1. Open a fresh Claude session (NO carryover).", file=sys.stderr)
    print(f"  2. Paste {out_dir}/without_tool_prompt.txt", file=sys.stderr)
    print(f"  3. Save the response to {out_dir}/without.md", file=sys.stderr)
    print("  4. Open ANOTHER fresh Claude session.", file=sys.stderr)
    print(f"  5. Paste {out_dir}/with_tool_prompt.txt", file=sys.stderr)
    print(f"  6. Save the response to {out_dir}/with.md", file=sys.stderr)
    print(f"  7. Score both against {out_dir}/rubric_form.md", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
