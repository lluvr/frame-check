"""Compute decision-readiness transformation diffs for paired
corpus entries.

Walks `corpus/` looking for entries whose `metadata.yaml` carries
a `paired_with` field. For each unique pair, computes the
per-dimension decision-readiness delta via
`decision_readiness_diff.compute_diff` and writes the result to
`corpus/{slug}/diff_with_{partner_slug}.json`.

Pairs are bidirectional: if entry A names B as its partner,
the harness writes the diff to BOTH A and B's directories so a
reader landing on either side has the diff at hand.

Run:
  python3 validation/decision_readiness/compute_pair_diffs.py

Idempotent: re-running with the same corpus state produces the
same diff files. Re-running after a profile.json regeneration
picks up the new signals automatically.
"""

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
CORPUS_DIR = HERE / "corpus"

sys.path.insert(0, str(REPO_ROOT))


def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        print(
            "ERROR: PyYAML required to read metadata.yaml. "
            "Install: pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _discover_pairs() -> list:
    """Return a list of unique (source_slug, transformed_slug)
    tuples by walking corpus/ metadata.

    The convention: when an entry's transformation_kind is
    'source_document', it is the source side; the entry it pairs
    with is the transformed side. If neither carries that kind,
    the pair is recorded with the alphabetically-first slug as
    the source, arbitrary but deterministic.
    """
    if not CORPUS_DIR.is_dir():
        return []

    entries = {}
    for d in sorted(CORPUS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "metadata.yaml"
        if not meta_path.is_file():
            continue
        meta = _load_yaml(meta_path)
        if not meta:
            continue
        partner = meta.get("paired_with")
        if not partner:
            continue
        entries[d.name] = {
            "slug": d.name,
            "partner": partner,
            "kind": meta.get("transformation_kind", ""),
        }

    pairs_seen = set()
    pairs = []
    for slug, info in entries.items():
        partner = info["partner"]
        if partner not in entries:
            print(
                f"WARN: {slug} pairs with {partner} but {partner} "
                f"not found in corpus; skipping",
                file=sys.stderr,
            )
            continue
        # Establish source vs transformed direction
        partner_info = entries[partner]
        if info["kind"] == "source_document":
            source_slug, xfm_slug = slug, partner
        elif partner_info["kind"] == "source_document":
            source_slug, xfm_slug = partner, slug
        else:
            # Neither side declares itself the source. Use
            # alphabetical ordering as a deterministic fallback.
            source_slug, xfm_slug = sorted([slug, partner])

        key = (source_slug, xfm_slug)
        if key in pairs_seen:
            continue
        pairs_seen.add(key)
        pairs.append({
            "source_slug": source_slug,
            "transformed_slug": xfm_slug,
            "transformation_kind": (
                entries[xfm_slug]["kind"] or "unspecified"
            ),
        })

    return pairs


def _load_profile(slug: str) -> dict:
    path = CORPUS_DIR / slug / "profile.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    print("Frame Check decision-readiness pair-diff harness")
    print("=" * 60)

    pairs = _discover_pairs()
    if not pairs:
        print(
            "No paired corpus entries found. Add `paired_with` and "
            "`transformation_kind` fields to two entries' metadata.yaml "
            "to enable pair-diff computation."
        )
        return 0

    from framecheck.decision_readiness_diff import compute_diff

    written = 0
    for pair in pairs:
        src = pair["source_slug"]
        xfm = pair["transformed_slug"]
        kind = pair["transformation_kind"]

        src_profile = _load_profile(src)
        xfm_profile = _load_profile(xfm)
        if not src_profile or not xfm_profile:
            print(f"  SKIP {src} <-> {xfm}: missing profile.json")
            continue

        diff = compute_diff(
            src_profile, xfm_profile,
            source_label=src,
            transformed_label=xfm,
            transformation_kind=kind,
        )
        if diff is None:
            print(
                f"  SKIP {src} <-> {xfm}: compute_diff returned None "
                f"(methodology version mismatch or empty profile)"
            )
            continue

        # Write to BOTH directories so a reader landing on either
        # side finds the diff at hand.
        src_path = CORPUS_DIR / src / f"diff_with_{xfm}.json"
        xfm_path = CORPUS_DIR / xfm / f"diff_with_{src}.json"
        for path in (src_path, xfm_path):
            path.write_text(
                json.dumps(diff, indent=2) + "\n",
                encoding="utf-8",
            )
        written += 1
        print(
            f"  Wrote diff: {src} -> {xfm}  ({kind})"
        )

    print()
    print(f"Pairs processed: {len(pairs)}")
    print(f"Diffs written:   {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
