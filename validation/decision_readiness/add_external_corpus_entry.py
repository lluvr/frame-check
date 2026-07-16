"""Add a corpus entry from external text.

Companion to `curate_corpus.py`. Where curate_corpus.py reads from
the existing `data/worked_examples/` shape, this script ingests
arbitrary text from a file path and creates a corpus entry. The
intended use: a curator captures source text from an external
location (FOMC statement, AP wire story, public-domain essay)
and runs this script to add it to the corpus.

The script is the "easy button" the curator needs when external
text capture happens. Without it, every new corpus entry would
require either a curate_corpus.py seed edit or manual file
creation (document.md + metadata.yaml + profile.json). With it,
the curator runs one command.

Usage:
  python3 add_external_corpus_entry.py \\
      --slug fomc-statement-2026-03 \\
      --text-file /tmp/fomc-statement.txt \\
      --genre policy \\
      --title "FOMC Statement (March 18, 2026)" \\
      --source "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260318a.htm"

Optional pairing:
  --paired-with grok-summary-of-fomc \\
  --transformation-kind source_document

Optional peer grouping:
  --peer-group fomc_march_2026

The script:
  1. Reads the text file
  2. Computes the structural Frame Check profile (offline, no
     Source Network, same path as curate_corpus.py)
  3. Writes corpus/{slug}/document.md, metadata.yaml, profile.json
  4. Reports the result

The script REFUSES to overwrite an existing corpus entry without
an explicit --force flag, so an accidental re-run with the same
slug does not silently destroy a hand-edited entry.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
CORPUS_DIR = HERE / "corpus"

sys.path.insert(0, str(REPO_ROOT))


VALID_GENRES = {"financial", "policy", "journalism", "ai_response", "other"}


def _build_display(doc_text: str) -> dict:
    """Run the structural analyzers and assemble a partial display
    dict suitable for compute_decision_readiness. Mirrors
    curate_corpus._build_display so both ingestion paths produce
    the same shape."""
    from framing import (
        detect_coverage,
        detect_voice,
        temporal_orientation,
        detect_epistemic_basis,
    )
    from frame_library import suggest_frames
    from claim_analysis import analyze_claims

    cov = detect_coverage(doc_text)
    voice = detect_voice(doc_text)
    temp = temporal_orientation(doc_text)
    epist = detect_epistemic_basis(doc_text)
    claims = analyze_claims(doc_text)
    suggestions = suggest_frames(cov, voice, temp, epist)

    return {
        "framing": {
            "coverage": cov,
            "voice": voice,
            "temporal": temp,
            "epistemic": epist,
            "frame_suggestions": suggestions,
        },
        "claims": {
            "total_claims": claims.get("total_claims", 0),
            "hedged_count": claims.get("hedged_count", 0),
            "unhedged_count": claims.get("unhedged_count", 0),
            "prediction_count": claims.get("prediction_count", 0),
        },
        "source_network": {
            "checked": 0,
            "verified": 0,
            "contradicted": 0,
            "disputed": 0,
            "verified_providers": [],
            "_note": (
                "Source Network not invoked during corpus curation. "
                "Evidence dimension reflects sentence-attribution % only; "
                "robustness reflects no-checks-run."
            ),
        },
    }


def _yaml_dump(d: dict) -> str:
    """YAML dump using PyYAML when available, else a minimal
    deterministic encoder. Mirrors curate_corpus._yaml_dump."""
    try:
        import yaml
        return yaml.safe_dump(d, sort_keys=False, allow_unicode=True)
    except ImportError:
        lines = []
        for k, v in d.items():
            if isinstance(v, str):
                if any(c in v for c in ":#"):
                    lines.append(f'{k}: "{v}"')
                else:
                    lines.append(f"{k}: {v}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k}: {v}")
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{k}: []")
                else:
                    lines.append(f"{k}:")
                    for item in v:
                        lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add a corpus entry from external text",
    )
    parser.add_argument("--slug", required=True,
                        help="Corpus entry slug (e.g., fomc-statement-2026-03)")
    parser.add_argument("--text-file", required=True,
                        help="Path to a UTF-8 text file containing the document")
    parser.add_argument("--genre", required=True,
                        choices=sorted(VALID_GENRES),
                        help="Genre classification")
    parser.add_argument("--title", required=True,
                        help="Human-readable title")
    parser.add_argument("--source", required=True,
                        help="Source URL or attribution string")
    parser.add_argument("--paired-with", default=None,
                        help="Optional: slug of paired corpus entry")
    parser.add_argument("--transformation-kind", default=None,
                        help="Optional: source_document, llm_summary, "
                             "llm_paraphrase, llm_translation, etc.")
    parser.add_argument("--peer-group", default=None,
                        help="Optional: peer group name")
    parser.add_argument("--license-note", default="",
                        help="Optional: license / attribution note for "
                             "the captured text (e.g., 'public domain', "
                             "'fair use excerpt under research purpose')")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing corpus entry if present")

    args = parser.parse_args()

    text_path = Path(args.text_file)
    if not text_path.is_file():
        print(f"ERROR: --text-file not found: {text_path}", file=sys.stderr)
        return 2

    doc_text = text_path.read_text(encoding="utf-8").strip()
    if len(doc_text) < 30:
        print(
            f"ERROR: text too short ({len(doc_text)} chars). The "
            f"analyzers need at least 30 characters of substantive "
            f"text to produce a meaningful profile.",
            file=sys.stderr,
        )
        return 2

    out_dir = CORPUS_DIR / args.slug
    if out_dir.exists() and not args.force:
        print(
            f"ERROR: corpus entry {args.slug!r} already exists. "
            f"Use --force to overwrite, or pick a different slug.",
            file=sys.stderr,
        )
        return 2

    from decision_readiness import compute_decision_readiness
    display = _build_display(doc_text)
    profile = compute_decision_readiness(display)
    if profile is None:
        print(
            "ERROR: decision_readiness returned None; the text "
            "may not produce a meaningful profile (too short or "
            "missing structural signals).",
            file=sys.stderr,
        )
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "document.md").write_text(
        doc_text + "\n", encoding="utf-8",
    )

    metadata = {
        "title": args.title,
        "genre": args.genre,
        "source": args.source,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "char_count": len(doc_text),
        "word_count_estimate": len(doc_text.split()),
        "curated_at_utc": datetime.now(timezone.utc).isoformat(),
        "curation_note": (
            "Profile computed without Source Network "
            "(structural-only). Evidence and robustness dimensions "
            "are partial; see methodology page."
        ),
    }
    if args.license_note:
        metadata["license_note"] = args.license_note
    if args.paired_with:
        metadata["paired_with"] = args.paired_with
    if args.transformation_kind:
        metadata["transformation_kind"] = args.transformation_kind
    if args.peer_group:
        metadata["peer_group"] = args.peer_group

    (out_dir / "metadata.yaml").write_text(
        _yaml_dump(metadata), encoding="utf-8",
    )
    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2) + "\n", encoding="utf-8",
    )

    print(
        f"Added corpus entry: {args.slug}  ({len(doc_text)} chars, "
        f"genre={args.genre})"
    )
    if args.paired_with:
        print(
            f"  Paired with: {args.paired_with} "
            f"(transformation_kind={args.transformation_kind or 'unspecified'})"
        )
    if args.peer_group:
        print(f"  Peer group: {args.peer_group}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
