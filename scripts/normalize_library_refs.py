"""Normalize artifact references in shipped frame-library catalog files.

Two-class transformation, applied across `data/frame_library/` and
`data/frame_library_v3/` (the trees that ship in the wheel under
`framecheck_mcp/data/`):

  Class A: tracked-on-master backtick references -> URL-form-cite
  Class B: maintainer-side path leaks -> strip path, preserve artifact ID

Closes Finding 17 from the 2026-04-27 publish-readiness audit:
catalog files contained ~180 backtick-form references to artifacts
that were either (a) unresolvable from the wheel-only context (the
pip-install consumer cannot follow `fvs_eval/...` because that tree
is not bundled), or (b) proxy-leaks of operator-private content
under `data/falsifications/` and `EXP-NNN-data/` (gitignored, never
intended for downstream surface).

Idempotent: simple string replacement; second run on already-cited
content is a no-op because the source-side backtick form no longer
appears once it has been converted to link form.

Excluded files (not shipped in wheel, left untouched here so that
operator-authored audit + promotion artifacts retain their internal
breadcrumb form):

  - data/frame_library/AUDIT_2026_04_17.md
  - data/frame_library/ADJACENCY_RECONCILIATION_v1.md
  - data/frame_library/DETECTION_RULE_AUDIT_v1.md
  - data/frame_library/INVITATION_TEMPLATE.md
  - data/frame_library/promotions/**

Usage:

    python3 scripts/normalize_library_refs.py [--dry-run] [--verbose]

    # --dry-run reports what would change but writes nothing.
    # --verbose lists per-file replacement counts.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGETS = [REPO / "data" / "frame_library", REPO / "data" / "frame_library_v3"]
GH_BASE = "https://github.com/lluvr/frame-check/blob/master/"
GH_TREE = "https://github.com/lluvr/frame-check/tree/master/"

# Files at the root of a target tree that are operator-authored
# audit / promotion artifacts. They are filtered out of the wheel
# by the staged-build pipeline; we leave them unmodified so the
# repo's audit-document layer keeps its original breadcrumb prose.
EXCLUDED_NAMES = frozenset({
    "AUDIT_2026_04_17.md",
    "ADJACENCY_RECONCILIATION_v1.md",
    "DETECTION_RULE_AUDIT_v1.md",
    "INVITATION_TEMPLATE.md",
})

# Class A: tracked-on-master files. Each entry is the canonical
# repo-rooted path. Replacements are generated for every relative
# prefix that appears in the catalog source: bare ("") and
# `../../` (depth-2 traversal from `data/frame_library/` reaches
# repo root). `../../../` only appears in `promotions/` files,
# which we excluded above, so we do not generate that form.
CLASS_A_FILES = [
    # Root-level docs
    "FRAME_DIVERGENCE_v2.md",
    "METHODOLOGY.md",
    "GOVERNANCE.md",
    "CONTRIBUTING.md",
    # fvs_eval/ tracked artifacts (study reports, design notes,
    # measurement scripts, raw-data JSON the catalog points to)
    "fvs_eval/v4/RELIABILITY_STUDY.md",
    "fvs_eval/v4/DESIGN.md",
    "fvs_eval/v4/MODEL_PANEL.md",
    "fvs_eval/v4/library_v4_reliability.json",
    "fvs_eval/v4/library_v4_per_corpus_reliability.json",
    "fvs_eval/v4/grok_intra_rater_ac1.json",
    "fvs_eval/v4/compute_per_corpus_reliability.py",
    "fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md",
    "fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md",
    "fvs_eval/v4_2/CONSTRUCT_VALIDITY_AUDIT_v1.md",
    "fvs_eval/v4_2/RELIABILITY_ARTIFACT_REPRODUCIBILITY_AUDIT_v1.md",
    "fvs_eval/v4_2/FVS_001_CROSS_FAMILY_v1.md",
    "fvs_eval/v4_2/FVS_007_ABLATION_RESULTS_v1.md",
    "fvs_eval/v4_2/fvs_001_cross_family_target_scope_raw.json",
    "fvs_eval/v4_2/fvs_001_cross_family_target_scope_library_current_raw.json",
    "fvs_eval/v4_2/measure_ablation.py",
    "fvs_eval/v4_2/measure_ablation_cur_v4_cand.py",
    "fvs_eval/validation_study/RULE_AUDIT.md",
    "fvs_eval/validation_study/REPORT.md",
    "fvs_eval/FVS_COACTIVATION_REPORT.md",
    "fvs_eval/analyze_fvs_coactivation.py",
    # Test files
    "test_v4_2_discipline_boundary.py",
    "scripts/reframe_smoke_test.py",
    # Audit / promotion docs that live in data/frame_library/ but
    # are excluded from the wheel by the staged-build pipeline.
    # Shipped catalog files (e.g. INDEX.md) cross-reference them;
    # citing to GitHub gives the wheel reader a working follow-up.
    "data/frame_library/AUDIT_2026_04_17.md",
    "data/frame_library/ADJACENCY_RECONCILIATION_v1.md",
    "data/frame_library/DETECTION_RULE_AUDIT_v1.md",
]

# Bare-basename overrides: when a catalog ref uses just the file
# name without any path (`LIBRARY_CROSS_FAMILY_BASELINE_v1.md`),
# resolve to the canonical Class A entry. Only listed for
# basenames that are unambiguous in the repo (single canonical
# location). Per-directory siblings (INDEX.md, FVS-NNN_*.md) are
# handled by _per_directory_pass instead.
CLASS_A_BARE_OVERRIDES = {
    "LIBRARY_CROSS_FAMILY_BASELINE_v1.md":
        "fvs_eval/v4_2/LIBRARY_CROSS_FAMILY_BASELINE_v1.md",
    "LIBRARY_V3_TO_V4_RATIFICATION_v1.md":
        "fvs_eval/v4_2/LIBRARY_V3_TO_V4_RATIFICATION_v1.md",
    "FVS_COACTIVATION_REPORT.md":
        "fvs_eval/FVS_COACTIVATION_REPORT.md",
    "RULE_AUDIT.md":
        "fvs_eval/validation_study/RULE_AUDIT.md",
    "ADJACENCY_RECONCILIATION_v1.md":
        "data/frame_library/ADJACENCY_RECONCILIATION_v1.md",
    "AUDIT_2026_04_17.md":
        "data/frame_library/AUDIT_2026_04_17.md",
    "DETECTION_RULE_AUDIT_v1.md":
        "data/frame_library/DETECTION_RULE_AUDIT_v1.md",
}

# Class A trees: link to GitHub tree URL not blob URL.
CLASS_A_TREES = [
    "fvs_eval/mixed_genre_v1",
    "fvs_eval/validation_study",
    "fvs_eval/validation_study/corpus",
]

# Section-anchored Class A references: pattern is `path §X.Y` or
# `path §"text"`. These are produced by the catalog when pointing
# at a specific section of a tracked artifact. Convert the whole
# `path §X.Y` token to `[path §X.Y](URL_for_path)`. GitHub does
# not auto-generate fragment IDs for `§N.N` literally, but the
# link still resolves to the document root and the human reader
# can locate the section.
SECTION_RE = re.compile(
    r"`([A-Za-z0-9_./-]+\.md)\s+(§[^`]+?)`"
)


def _build_replacement_table() -> list[tuple[str, str]]:
    """Returns a list of (source, target) pairs, applied in order.

    Order matters only for Class B / Class A overlap: vault path
    strips are listed FIRST so a `data/falsifications/F-NNN.md`
    is collapsed before any later rule could touch the surrounding
    backtick context.
    """
    pairs: list[tuple[str, str]] = []

    # Class B: maintainer-side path strips. F-2026-NNN appears in
    # three forms: bare `F-2026-NNN.md`, with `data/falsifications/`
    # prefix, and with relative `../../data/falsifications/`. Strip
    # all path/extension content; leave the bare artifact ID so the
    # catalog still tells the reader which internal pre-registration
    # this rule's empirical claim came from.
    for n in range(1, 100):
        nstr = f"F-2026-{n:03d}"
        for prefix in ("", "data/falsifications/", "../../data/falsifications/"):
            pairs.append((f"`{prefix}{nstr}.md`", nstr))

    # EXP-NNN-data ghost paths: the maintainer-internal scoring
    # artifact tree is not bundled and not on GitHub. Replace
    # with prose that names the experiment but not a path.
    pairs.append((
        "`EXP-096-data/scorecards_pass1.md`",
        "internal scoring artifact (EXP-096)",
    ))

    # STRATEGY.md is the maintainer-side notebook strategy doc. The
    # references appear only in EXCLUDED files (promotions/,
    # AUDIT_2026_04_17.md), so the wheel-leak surface is already
    # zero. We do not modify the EXCLUDED files. No replacement
    # generated for STRATEGY.md.

    # Class A: tracked files. Generate (bare, ../, ../../) prefix
    # forms; ../../../ is promotions/-only and excluded above.
    for path in CLASS_A_FILES:
        for prefix in ("", "../", "../../"):
            ref = f"`{prefix}{path}`"
            link = f"[{path}]({GH_BASE}{path})"
            pairs.append((ref, link))

    # Class A trees: handle both with and without trailing slash
    for tree in CLASS_A_TREES:
        for prefix in ("", "../", "../../"):
            for suffix in ("", "/"):
                ref = f"`{prefix}{tree}{suffix}`"
                link = f"[{tree}]({GH_TREE}{tree})"
                pairs.append((ref, link))

    # Class A bare-basename overrides
    for bare, canonical in CLASS_A_BARE_OVERRIDES.items():
        pairs.append((
            f"`{bare}`",
            f"[{bare}]({GH_BASE}{canonical})",
        ))

    return pairs


def _section_pass(content: str) -> tuple[str, int]:
    """Convert backtick `path §X.Y` into [path §X.Y](URL) for tracked paths.

    Returns (new_content, n_replacements).
    """
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        path = m.group(1)
        anchor = m.group(2).rstrip()
        # Resolve the path token to a Class A canonical entry.
        # Match by suffix: the catalog often uses bare names
        # (e.g. `METHODOLOGY.md §2.4.1`) where the canonical entry
        # is the full repo-rooted path.
        canonical: str | None = None
        for cf in CLASS_A_FILES:
            if cf == path or cf.endswith("/" + path):
                canonical = cf
                break
        if canonical is None:
            return m.group(0)  # leave unchanged for unknown paths
        n += 1
        return f"[{path} {anchor}]({GH_BASE}{canonical})"

    return SECTION_RE.sub(repl, content), n


def _per_directory_pass(content: str, parent_dir: Path) -> tuple[str, int]:
    """Resolve bare `INDEX.md` and sibling `FVS-NNN_*.md` refs.

    The catalog uses bare names for siblings. Bare INDEX.md inside
    `data/frame_library/FVS-X.md` resolves to
    `data/frame_library/INDEX.md`; inside frame_library_v3/FVS-X.md
    it resolves to `data/frame_library_v3/INDEX.md`.

    Returns (new_content, n_replacements).
    """
    n = 0
    rel_parent = parent_dir.relative_to(REPO).as_posix()  # e.g. "data/frame_library"

    # INDEX.md (bare)
    index_canonical = f"{rel_parent}/INDEX.md"
    index_url = f"{GH_BASE}{index_canonical}"
    src = "`INDEX.md`"
    tgt = f"[INDEX.md]({index_url})"
    n_index = content.count(src)
    if n_index:
        content = content.replace(src, tgt)
        n += n_index

    # Sibling FVS-NNN_*.md files: enumerate what's actually on disk
    # in this parent directory and generate per-name replacements.
    for sibling in parent_dir.glob("FVS-*.md"):
        if sibling.name in EXCLUDED_NAMES:
            continue
        src = f"`{sibling.name}`"
        tgt_path = f"{rel_parent}/{sibling.name}"
        tgt = f"[{sibling.name}]({GH_BASE}{tgt_path})"
        c = content.count(src)
        if c:
            content = content.replace(src, tgt)
            n += c

    return content, n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Report changes without writing files.")
    parser.add_argument("--verbose", action="store_true",
                        help="Print per-file replacement counts.")
    args = parser.parse_args()

    table = _build_replacement_table()

    md_files: list[Path] = []
    for tree in TARGETS:
        for f in tree.rglob("*.md"):
            if "promotions" in f.parts:
                continue
            if f.name in EXCLUDED_NAMES:
                continue
            md_files.append(f)
    md_files.sort()

    total_files_changed = 0
    total_replacements = 0

    for f in md_files:
        content = f.read_text(encoding="utf-8")
        original = content

        n_table = 0
        for src, tgt in table:
            c = content.count(src)
            if c:
                content = content.replace(src, tgt)
                n_table += c

        content, n_section = _section_pass(content)
        content, n_perdir = _per_directory_pass(content, f.parent)
        n_total = n_table + n_section + n_perdir

        if content != original:
            total_files_changed += 1
            total_replacements += n_total
            rel = f.relative_to(REPO).as_posix()
            if args.verbose:
                print(
                    f"  {rel}: {n_table} table + "
                    f"{n_section} section + {n_perdir} per-dir "
                    f"= {n_total}"
                )
            else:
                print(f"  {rel}: {n_total} replacements")
            if not args.dry_run:
                f.write_text(content, encoding="utf-8")

    mode = "(dry-run, no writes)" if args.dry_run else ""
    print(
        f"\n{total_files_changed} files changed, "
        f"{total_replacements} total replacements {mode}".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
