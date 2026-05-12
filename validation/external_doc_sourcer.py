#!/usr/bin/env python3
"""External-document sourcing helper for the validation main study.

The methodological credibility of the wedge_behavior + baseline_comparison
main studies depends on documents being sourced OUTSIDE the operator's
authoring reach (the agent-as-author confound has to go away). This
script standardizes that sourcing: the operator picks documents from
external sources (web pages, public corpora, archives), pipes them
through this script, and gets back a structured corpus record with
provenance metadata + inclusion-criteria validation.

The script does NOT auto-fetch documents from the web. Operator's
hands on the URL = operator's judgment on representativeness; that
judgment is the load-bearing input the script cannot proxy.

Usage:
    # Pipe document text in via stdin:
    cat downloaded.txt | python3 validation/external_doc_sourcer.py \\
        --slug op-ed-2026-05-X \\
        --url https://example.com/op-ed \\
        --title "The Op-Ed Title" \\
        --author "Author Name" \\
        --retrieved-utc "2026-05-12T00:00:00Z" \\
        > corpus_entry.json

    # Or read from file:
    python3 validation/external_doc_sourcer.py \\
        --slug op-ed-2026-05-X \\
        --document-file downloaded.txt \\
        --url https://example.com/op-ed \\
        --title "The Op-Ed Title" \\
        --author "Author Name" \\
        --retrieved-utc "2026-05-12T00:00:00Z" \\
        > corpus_entry.json

Output: a JSON object suitable for inclusion in a corpus.json array
that the wedge_behavior or baseline_comparison harness consumes.
Includes inclusion-criteria validation (300-2000 words, English,
analytical-prose) with PASS/FAIL/WARN flags so the operator can
filter their corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _paragraph_count(text: str) -> int:
    return sum(1 for p in re.split(r"\n\s*\n", text) if p.strip())


def _english_ratio(text: str) -> float:
    """Crude English-character ratio. Latin alphabet + common
    punctuation. Sufficient for a screening signal; not a language
    detector. Operator visually confirms English."""
    total = sum(1 for c in text if not c.isspace())
    if not total:
        return 0.0
    latin = sum(
        1 for c in text
        if (c.isalnum() and c.isascii()) or c in ".,;:!?'\"()-—–"
    )
    return latin / total


def _validate_inclusion(
    text: str,
    word_min: int = 300,
    word_max: int = 2000,
) -> dict:
    """Apply PROTOCOL_v1 inclusion criteria + return per-criterion
    pass/fail/warn flags."""
    wc = _word_count(text)
    pc = _paragraph_count(text)
    er = _english_ratio(text)

    return {
        "word_count": wc,
        "word_count_in_range": (
            "PASS" if word_min <= wc <= word_max
            else "FAIL" if wc < word_min
            else "FAIL_TOO_LONG"
        ),
        "paragraph_count": pc,
        "paragraphed_prose": (
            "PASS" if pc >= 2 else "WARN_FEW_PARAGRAPHS"
        ),
        "english_ratio": round(er, 3),
        "likely_english": (
            "PASS" if er >= 0.85
            else "WARN_LOW_LATIN_RATIO"
            if er >= 0.5
            else "FAIL"
        ),
        "engine_confidence_gate_likely_fires": wc < 100,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="Doc slug (kebab-case)")
    ap.add_argument(
        "--document-file",
        type=argparse.FileType("r", encoding="utf-8"),
        default=None,
        help="Path to document file. If not provided, reads from stdin.",
    )
    ap.add_argument("--url", required=True, help="Source URL")
    ap.add_argument(
        "--title", default=None,
        help="Document title (for provenance only)",
    )
    ap.add_argument(
        "--author", default=None,
        help="Document author (for provenance only)",
    )
    ap.add_argument(
        "--retrieved-utc", default=None,
        help="Retrieval timestamp (ISO 8601 UTC). Defaults to now.",
    )
    ap.add_argument(
        "--source-text-file",
        type=argparse.FileType("r", encoding="utf-8"),
        default=None,
        help="Optional source text file for the H2 source-fidelity arm.",
    )
    ap.add_argument(
        "--source-url",
        default=None,
        help="URL the source-text was retrieved from (when --source-text-file).",
    )
    args = ap.parse_args()

    text = (args.document_file.read() if args.document_file else sys.stdin.read())
    if not text.strip():
        print("Document text is empty (no content from stdin or file).",
              file=sys.stderr)
        return 1

    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    inclusion = _validate_inclusion(text)
    retrieved = args.retrieved_utc or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    record = {
        "slug": args.slug,
        "document_text": text,
        "provenance": {
            "url": args.url,
            "title": args.title,
            "author": args.author,
            "retrieved_utc": retrieved,
            "sha256": sha,
            "word_count": inclusion["word_count"],
            "inclusion_validation": inclusion,
        },
    }

    if args.source_text_file:
        source_text = args.source_text_file.read()
        record["source_text"] = source_text
        record["source_provenance"] = {
            "url": args.source_url,
            "retrieved_utc": retrieved,
            "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "word_count": _word_count(source_text),
        }

    print(json.dumps(record, indent=2, ensure_ascii=False))

    # Surface inclusion-criteria warnings on stderr so they reach the
    # operator without breaking JSON output piping.
    fails = [k for k, v in inclusion.items()
             if isinstance(v, str) and v.startswith("FAIL")]
    warns = [k for k, v in inclusion.items()
             if isinstance(v, str) and v.startswith("WARN")]
    if fails:
        print(f"\nWARNING — inclusion FAIL on: {fails}", file=sys.stderr)
        print("This document does NOT meet PROTOCOL_v1 inclusion criteria. "
              "Consider re-selecting.", file=sys.stderr)
        return 2
    if warns:
        print(f"\nNote — inclusion WARN on: {warns}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
