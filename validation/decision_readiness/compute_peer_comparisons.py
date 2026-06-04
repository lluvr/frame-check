"""Compute pairwise decision-readiness comparisons across peer
responses to the same prompt.

Walks `corpus/` looking for entries whose `metadata.yaml` carries
a `peer_group` field. Within each group, computes pairwise
decision-readiness comparisons via
`decision_readiness_peer.compute_peer_comparison` and writes the
results to `corpus/{slug}/peer_with_{partner_slug}.json`.

Comparisons are non-directional: the same comparison is written
to both peers' directories so a reader landing on either side
finds the comparison at hand.

Sibling to compute_pair_diffs.py (transformation pair diffs);
both use the same underlying decision-readiness profile data
but answer different questions.

Run:
  python3 validation/decision_readiness/compute_peer_comparisons.py
"""

import itertools
import json
import sys
from collections import defaultdict
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


def _discover_peer_groups() -> dict:
    """Returns {peer_group_name: [slug, slug, ...]} for every
    corpus entry that declares a peer_group."""
    if not CORPUS_DIR.is_dir():
        return {}
    groups = defaultdict(list)
    for d in sorted(CORPUS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "metadata.yaml"
        if not meta_path.is_file():
            continue
        meta = _load_yaml(meta_path)
        if not meta:
            continue
        peer_group = meta.get("peer_group")
        if peer_group:
            groups[peer_group].append(d.name)
    return dict(groups)


def _load_profile(slug: str) -> dict:
    path = CORPUS_DIR / slug / "profile.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    print("Frame Check decision-readiness peer-comparison harness")
    print("=" * 60)

    groups = _discover_peer_groups()
    if not groups:
        print(
            "No peer groups declared. Add `peer_group: <group_name>` "
            "to two or more entries' metadata.yaml to enable pairwise "
            "peer-comparison computation."
        )
        return 0

    from framecheck.decision_readiness_peer import compute_peer_comparison

    total_groups = len(groups)
    total_pairs = 0
    written = 0

    for group_name, slugs in sorted(groups.items()):
        print(f"\nGroup: {group_name}  ({len(slugs)} member{'s' if len(slugs) != 1 else ''})")
        if len(slugs) < 2:
            print(
                f"  SKIP: peer group needs >=2 members for "
                f"comparison; got {len(slugs)}"
            )
            continue

        profiles = {slug: _load_profile(slug) for slug in slugs}
        # Generate all unordered pairs within the group.
        pairs_in_group = list(itertools.combinations(sorted(slugs), 2))
        total_pairs += len(pairs_in_group)

        for slug_a, slug_b in pairs_in_group:
            profile_a = profiles[slug_a]
            profile_b = profiles[slug_b]
            if not profile_a or not profile_b:
                print(f"  SKIP {slug_a} <-> {slug_b}: missing profile.json")
                continue

            comparison = compute_peer_comparison(
                profile_a, profile_b,
                label_a=slug_a,
                label_b=slug_b,
                peer_group=group_name,
            )
            if comparison is None:
                print(
                    f"  SKIP {slug_a} <-> {slug_b}: comparison returned "
                    f"None (methodology version mismatch or empty profile)"
                )
                continue

            # Write to BOTH directories with the partner's slug in the
            # filename. Mirror of the pair-diff convention.
            for owner, partner in ((slug_a, slug_b), (slug_b, slug_a)):
                path = CORPUS_DIR / owner / f"peer_with_{partner}.json"
                path.write_text(
                    json.dumps(comparison, indent=2) + "\n",
                    encoding="utf-8",
                )
            written += 1
            differs = sum(
                1 for d in comparison["dimensions"].values() if d.get("differs")
            )
            print(
                f"  Wrote: {slug_a} <-> {slug_b}  "
                f"(differ on {differs} of 5 dimensions)"
            )

    print()
    print(f"Peer groups discovered: {total_groups}")
    print(f"Pairs evaluated:        {total_pairs}")
    print(f"Comparisons written:    {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
