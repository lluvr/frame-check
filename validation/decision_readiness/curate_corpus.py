"""Corpus curation for the decision-readiness validation harness.

Reads document text from the `data/worked_examples/` directory,
runs the structural Frame Check analyzers (offline; no Source
Network calls), computes the decision-readiness profile, and
writes a corpus entry under `validation/decision_readiness/corpus/{slug}/`.

Why this script exists: Phase 2 validation needs a curated corpus
with computed Frame Check profiles. The worked examples already
hold real document text we have analyzed; this script lifts that
text into the validation corpus structure and computes the profile
from the same code paths the live analyzer uses.

Limitations:
  - Source Network is NOT invoked. The profile's evidence and
    robustness dimensions populate from structural signals only
    (epistemic.sourced_pct for evidence; zeros for robustness).
    The metadata file documents this so raters and the harness
    handle the partial profile honestly.
  - When a worked example yields multiple sub-documents (the
    four-llms-bitcoin example holds responses from four LLMs to
    the same question), each sub-document is a distinct corpus
    entry with its own slug.

Usage:
  python3 curate_corpus.py {worked_example_slug} {genre}
  python3 curate_corpus.py --all-defaults

Genre values: financial, policy, journalism, ai_response, other.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
WORKED_EXAMPLES = REPO_ROOT / "data" / "worked_examples"
CORPUS_DIR = HERE / "corpus"

sys.path.insert(0, str(REPO_ROOT))


# ── Document extraction shapes ──
# Worked examples have evolved over time; their data.json shapes
# vary. Each entry below is one curatable document with the path
# and the JSON pointer to the document text.
#
# The list is the set of seed corpus entries; expand it as the
# corpus grows. For a worked example that holds N sub-documents
# (different LLM responses to the same prompt), enter N rows.

DEFAULT_CORPUS_SEEDS = [
    {
        "slug": "grok-nvidia-q4-fy24-summary",
        "data_path": "grok-on-nvidia-earnings-2026/data.json",
        "text_pointer": ["llm_summary", "text"],
        "genre": "ai_response",
        "title": "Grok 4.1 Fast: 200-word summary of NVIDIA Q4 FY24 earnings press release",
        "source_label": "data/worked_examples/grok-on-nvidia-earnings-2026/data.json",
        # Transformation pair: this entry is what an LLM produced
        # when asked to summarize the source. The diff harness
        # measures per-dimension decision-readiness delta from
        # source to summary, the load-bearing measurement for the
        # AI-response audit lead use case.
        "paired_with": "nvidia-q4-fy24-press-release",
        "transformation_kind": "llm_summary",
    },
    # Originally seeded as 'ai-on-life-decisions-startup' from a
    # separate data file; renamed and re-pointed to the four-llms
    # source (identical text content, verified by SHA-256). The
    # rename unifies the slug with its siblings (Claude / Grok /
    # Gemini variants) so the four-llms-startup family is visible
    # as such and rater notes can compare across the same prompt.
    {
        "slug": "four-llms-startup-openai",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["B_startup", "openai_gpt", "text"],
        "genre": "ai_response",
        "title": "OpenAI GPT on whether to take a startup offer (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "startup_offer_question",
    },
    {
        "slug": "four-llms-bitcoin-claude",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["A_bitcoin", "claude", "text"],
        "genre": "ai_response",
        "title": "Claude on whether to retire on Bitcoin (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "bitcoin_retirement_question",
    },
    {
        "slug": "four-llms-bitcoin-openai",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["A_bitcoin", "openai_gpt", "text"],
        "genre": "ai_response",
        "title": "OpenAI GPT on whether to retire on Bitcoin (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "bitcoin_retirement_question",
    },
    # Financial-genre seed: the NVIDIA press release that the
    # grok-nvidia worked example used as source_text. Pairs with
    # grok-nvidia-q4-fy24-summary so raters can compare how the
    # ORIGINAL document scores vs how the LLM SUMMARY of it scores
    # on the same dimensions. This source-vs-summary pairing is
    # uniquely informative for the validation: it tests whether
    # decision-readiness signals are sensitive to the
    # transformation an LLM applies to a known input.
    {
        "slug": "nvidia-q4-fy24-press-release",
        "data_path": "grok-on-nvidia-earnings-2026/data.json",
        "text_pointer": ["source", "text"],
        "genre": "financial",
        "title": "NVIDIA Q4 FY2024 earnings press release (source document)",
        "source_label": "data/worked_examples/grok-on-nvidia-earnings-2026/data.json (source.text)",
        # Source side of the transformation pair. The Grok summary
        # entry references this slug as its source so the diff
        # harness can compute the per-dimension delta. The pair is
        # bidirectional in metadata; pair-detection in the harness
        # walks both directions.
        "paired_with": "grok-nvidia-q4-fy24-summary",
        "transformation_kind": "source_document",
    },
    # Within-ai_response variance: the four_llms file holds two
    # questions (bitcoin retirement, startup offer) each answered
    # by four LLMs. The first iteration of the seeded corpus
    # captured only Claude and OpenAI on bitcoin; expanding to
    # Grok and Gemini on bitcoin plus Claude / Grok / Gemini on
    # startup gives raters within-genre variance to score against
    # (same prompt, different models; same model, different
    # prompts). Sufficient diversity for ai_response per-dimension
    # correlations even before cross-genre capture lands.
    {
        "slug": "four-llms-bitcoin-grok",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["A_bitcoin", "xai_grok", "text"],
        "genre": "ai_response",
        "title": "Grok on whether to retire on Bitcoin (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "bitcoin_retirement_question",
    },
    {
        "slug": "four-llms-bitcoin-gemini",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["A_bitcoin", "gemini", "text"],
        "genre": "ai_response",
        "title": "Gemini on whether to retire on Bitcoin (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "bitcoin_retirement_question",
    },
    {
        "slug": "four-llms-startup-claude",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["B_startup", "claude", "text"],
        "genre": "ai_response",
        "title": "Claude on whether to take a startup offer (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "startup_offer_question",
    },
    {
        "slug": "four-llms-startup-grok",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["B_startup", "xai_grok", "text"],
        "genre": "ai_response",
        "title": "Grok on whether to take a startup offer (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "startup_offer_question",
    },
    {
        "slug": "four-llms-startup-gemini",
        "data_path": "four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "text_pointer": ["B_startup", "gemini", "text"],
        "genre": "ai_response",
        "title": "Gemini on whether to take a startup offer (life-decision question)",
        "source_label": "data/worked_examples/four-llms-on-bitcoin-retirement-2026/llm_responses.json",
        "peer_group": "startup_offer_question",
    },
]


def _resolve_pointer(d: dict, pointer: list) -> Optional[str]:
    """Walk a JSON pointer list into a nested dict, return string
    leaf or None."""
    cur = d
    for key in pointer:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    if isinstance(cur, str):
        return cur
    return None


def _build_display(doc_text: str) -> dict:
    """Run the structural analyzers and assemble a partial display
    dict suitable for compute_decision_readiness.

    No Source Network: source_network is empty so evidence and
    robustness dimensions surface their structural-only signals
    (epistemic.sourced_pct for evidence; zero contradictions for
    robustness). The decision_readiness module handles the partial
    case correctly.
    """
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

    # claims keys: claims (list), confidence_uniformity, hedged_count,
    # unhedged_count, prediction_count, total_claims, ...
    # The display.claims block uses the count fields directly.
    claims_block = {
        "total_claims": claims.get("total_claims", 0),
        "hedged_count": claims.get("hedged_count", 0),
        "unhedged_count": claims.get("unhedged_count", 0),
        "prediction_count": claims.get("prediction_count", 0),
    }

    return {
        "framing": {
            "coverage": cov,
            "voice": voice,
            "temporal": temp,
            "epistemic": epist,
            "frame_suggestions": suggestions,
        },
        "claims": claims_block,
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
    deterministic encoder for the simple shapes we write here.

    PyYAML is the standard project dep; the manual encoder is a
    defensive fallback that keeps curation usable in a stripped
    environment. Only handles strings, ints, lists of strings, and
    flat dicts."""
    try:
        import yaml
        return yaml.safe_dump(d, sort_keys=False, allow_unicode=True)
    except ImportError:
        lines = []
        for k, v in d.items():
            if isinstance(v, str):
                # Quote if value contains special chars
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


def curate(seed: dict) -> int:
    """Curate one corpus entry from a seed descriptor."""
    slug = seed["slug"]
    data_path = WORKED_EXAMPLES / seed["data_path"]
    if not data_path.is_file():
        print(f"ERROR: source data not found: {data_path}", file=sys.stderr)
        return 1

    we_data = json.loads(data_path.read_text(encoding="utf-8"))
    doc_text = _resolve_pointer(we_data, seed["text_pointer"])
    if not doc_text:
        print(
            f"ERROR: could not extract text via pointer "
            f"{seed['text_pointer']!r} from {data_path}",
            file=sys.stderr,
        )
        return 1

    # Compute profile
    from decision_readiness import compute_decision_readiness
    display = _build_display(doc_text)
    profile = compute_decision_readiness(display)
    if profile is None:
        print(
            f"ERROR: decision_readiness returned None for {slug}; "
            f"document may be too short or analyzers produced no signal",
            file=sys.stderr,
        )
        return 1

    out_dir = CORPUS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "document.md").write_text(
        doc_text.strip() + "\n", encoding="utf-8",
    )

    metadata = {
        "title": seed["title"],
        "genre": seed["genre"],
        "source": seed["source_label"],
        "captured_at_utc": (
            we_data.get("captured_at_utc")
            or we_data.get("run_date_utc")
            or ""
        ),
        "char_count": len(doc_text),
        "word_count_estimate": len(doc_text.split()),
        "curated_at_utc": datetime.now(timezone.utc).isoformat(),
        "curation_note": (
            "Profile computed without Source Network "
            "(structural-only). Evidence and robustness dimensions "
            "are partial; see methodology page."
        ),
    }
    # Optional pairing fields. When this entry is one half of a
    # transformation pair (source-vs-summary, original-vs-rewrite,
    # etc.), record the partner slug + kind so the diff harness
    # can compute per-dimension decision-readiness delta. The kind
    # vocabulary names what the transformation did:
    #   source_document  - the unmodified source
    #   llm_summary      - LLM-produced summary of the source
    #   llm_paraphrase   - LLM paraphrase preserving meaning
    #   llm_translation  - LLM cross-language transformation
    # Extend the vocabulary as new transformation kinds get
    # documented in the corpus.
    if seed.get("paired_with"):
        metadata["paired_with"] = seed["paired_with"]
    if seed.get("transformation_kind"):
        metadata["transformation_kind"] = seed["transformation_kind"]
    # Optional peer group: declares this entry as one of N peer
    # responses to the same prompt. The peer-comparison harness
    # discovers groups by this field and computes pairwise
    # decision-readiness comparisons within each group. Different
    # from `paired_with` (which is a single directional partner)
    # in that a peer group can have any number of members and the
    # comparisons are non-directional.
    if seed.get("peer_group"):
        metadata["peer_group"] = seed["peer_group"]
    (out_dir / "metadata.yaml").write_text(
        _yaml_dump(metadata), encoding="utf-8",
    )

    (out_dir / "profile.json").write_text(
        json.dumps(profile, indent=2) + "\n", encoding="utf-8",
    )

    print(
        f"Curated {slug:40s} {len(doc_text):5d} chars   "
        f"genre={seed['genre']}"
    )
    return 0


def main(argv: list) -> int:
    if "--all-defaults" in argv:
        rc = 0
        for seed in DEFAULT_CORPUS_SEEDS:
            rc = max(rc, curate(seed))
        return rc

    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    slug = argv[0]
    genre = argv[1]
    matched = [s for s in DEFAULT_CORPUS_SEEDS if s["slug"] == slug]
    if not matched:
        print(
            f"ERROR: slug {slug!r} not in DEFAULT_CORPUS_SEEDS. "
            f"Add a seed entry first, or use --all-defaults.",
            file=sys.stderr,
        )
        return 2
    seed = dict(matched[0])
    seed["genre"] = genre  # allow CLI override
    return curate(seed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
