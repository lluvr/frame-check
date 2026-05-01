"""Falsification registry status: aggregate summary of `data/falsifications/`.

Reads every `data/falsifications/F-*.md` entry, parses YAML frontmatter
per the registry schema (`data/falsifications/README.md` "Entry schema"),
and produces:

  - `data/falsifications/STATUS.md`: human-readable summary with
    aggregate counts by outcome and by type, plus per-outcome tables.
  - `data/falsifications/STATUS.json`: machine-readable equivalent
    (re-derivable; not the canonical record but stable for analytics).

Why this is here
----------------

The methodology paper §6c claims the project's falsification discipline
("Published falsification discipline. AGI produces infinite plausible
theories. Kill records are the scarce good in an economy of infinite
generation." per THE_BETS §AGI-era robustness principle 5). Reviewers
will reasonably ask "how many predictions has the project committed to,
how many have resolved, how many in each direction." A re-derivable
aggregate makes that answer auditable: the registry is the canonical
record, this script is the aggregation, both are reproducible.

Design discipline
-----------------

This script aggregates and counts. It does NOT:

  - Author entry content (operator owns prediction text + outcome
    interpretation).
  - Edit existing entries (the registry README forbids deletion;
    revisions are new entries with `superseded_by`).
  - Judge whether an outcome is correct (the entry's `evidence` field
    points at the load-bearing report).

It DOES:

  - Sum by outcome.
  - Sum by type.
  - List pending entries sorted by `registered_at` so the operator can
    see what is in flight.
  - List failed entries (the load-bearing kill records) so the paper
    can cite them by ID.

Usage
-----

    python3 scripts/falsification_status.py

    # Override output location:
    python3 scripts/falsification_status.py --out /tmp/falsif_status

The output writes are atomic (write tmp, rename) so a partial run does
not leave a half-written summary.

Falsification registry path is gitignored at the per-entry filename
pattern (`data/falsifications/F-NNNN-NNN`) for wheel-content leak
discipline; the top-level directory and STATUS.md are not affected.
This script does not bundle into the wheel.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FATAL: PyYAML required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent
FALSIFICATIONS = REPO / "data" / "falsifications"


def _parse_entry(path: Path) -> dict | None:
    """Parse YAML frontmatter from F-NNNN-NNN.md. Return None on shape error."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    fm["_path"] = str(path.relative_to(REPO))
    return fm


def _parse_evidence_paths(evidence_field: str) -> list[str]:
    """Extract per-path tokens from an entry's `evidence:` field.

    Three formats observed in the registry:
      1. Single path:     `fvs_eval/validation_study/REPORT.md`
      2. Path + section:  `fvs_eval/AUDIT_v1.md §2.1` or `... §changelog`
      3. Multi-path CSV:  `path_a.md, path_b.json, path_c.py`

    The section anchor (everything after `§`) is stripped because the
    section is a within-file address; existence is per-file. The CSV
    form is split on `, ` (comma + space) which is the canonical
    separator the registry uses.

    Returns a list of repo-relative path strings (no leading slash; no
    section anchor; whitespace trimmed). Empty list if `evidence:` is
    empty or whitespace-only.
    """
    if not evidence_field or not evidence_field.strip():
        return []
    paths: list[str] = []
    for chunk in evidence_field.split(","):
        token = chunk.strip()
        if not token:
            continue
        # Strip section anchor (`§` and everything after).
        if "§" in token:
            token = token.split("§", 1)[0].strip()
        if token:
            paths.append(token)
    return paths


def _validate_evidence_pointers(entries: list[dict]) -> dict:
    """Walk each entry's `evidence:` field; report broken pointers.

    Returns a dict keyed by entry id with the list of broken paths.
    Empty dict means every cited evidence path resolves to a real file
    in the working tree. The methodology paper section 6c falsification-
    discipline claim depends on the evidence pointers being live; this
    surfaces drift between registry entries and the actual filesystem.
    """
    broken: dict[str, list[str]] = {}
    for e in entries:
        ev = e.get("evidence")
        if ev is None:
            continue
        ev_str = str(ev)
        paths = _parse_evidence_paths(ev_str)
        broken_for_entry = []
        for rel in paths:
            full = REPO / rel
            if not full.exists():
                broken_for_entry.append(rel)
        if broken_for_entry:
            broken[e.get("id", e.get("_path", "<unknown>"))] = broken_for_entry
    return broken


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(FALSIFICATIONS),
                    help="Output directory (default: data/falsifications/)")
    args = ap.parse_args(argv)

    if not FALSIFICATIONS.is_dir():
        print(f"FATAL: {FALSIFICATIONS} not found", file=sys.stderr)
        return 1

    entries: list[dict] = []
    skipped: list[str] = []
    for path in sorted(FALSIFICATIONS.glob("F-*.md")):
        e = _parse_entry(path)
        if e is None:
            skipped.append(str(path.relative_to(REPO)))
            continue
        entries.append(e)

    if not entries:
        print(f"FATAL: no parseable entries in {FALSIFICATIONS}",
              file=sys.stderr)
        return 1

    # Aggregate
    by_outcome: Counter = Counter()
    by_type: Counter = Counter()
    by_outcome_and_type: dict = defaultdict(Counter)
    for e in entries:
        outcome = e.get("outcome", "(no outcome field)")
        etype = e.get("type", "(no type field)")
        by_outcome[outcome] += 1
        by_type[etype] += 1
        by_outcome_and_type[outcome][etype] += 1

    pending = [e for e in entries if e.get("outcome") == "pending"]
    failed = [e for e in entries if e.get("outcome") == "failed"]
    passed = [e for e in entries if e.get("outcome") == "passed"]
    revised = [e for e in entries if e.get("outcome") == "revised"]

    # Sort pending by registered_at so the operator sees what is oldest
    pending.sort(key=lambda e: str(e.get("registered_at", "")))
    failed.sort(key=lambda e: str(e.get("outcome_at") or e.get("registered_at", "")))

    # Build STATUS.md
    today = date.today().isoformat()
    md: list[str] = []
    md.append("# Falsification registry status")
    md.append("")
    md.append(f"**Generated:** {today} (re-derivable via `scripts/falsification_status.py`)")
    md.append(f"**Source:** `data/falsifications/F-*.md` ({len(entries)} entries parsed)")
    if skipped:
        md.append(f"**Skipped (unparseable):** {len(skipped)}: " + ", ".join(skipped))
    md.append("")
    md.append("## At a glance")
    md.append("")
    md.append("| Outcome | Count | Share |")
    md.append("|---|---|---|")
    n = len(entries)
    for outcome in ("pending", "passed", "failed", "revised"):
        k = by_outcome.get(outcome, 0)
        pct = round(100.0 * k / n) if n else 0
        md.append(f"| {outcome} | {k} | {pct}% |")
    other = sum(v for k, v in by_outcome.items()
                if k not in ("pending", "passed", "failed", "revised"))
    if other:
        md.append(f"| (other) | {other} | {round(100.0*other/n)}% |")
    md.append(f"| **Total** | **{n}** | 100% |")
    md.append("")
    md.append("## By type")
    md.append("")
    md.append("| Type | Count |")
    md.append("|---|---|")
    for t, k in by_type.most_common():
        md.append(f"| {t} | {k} |")
    md.append("")
    md.append("## Failed predictions (the load-bearing kill records)")
    md.append("")
    md.append(
        "These are the entries that committed to a falsifiable bar and "
        "the evidence came in below it. The methodology paper cites the "
        "count and individual IDs; the per-entry `evidence:` field points "
        "at the load-bearing report behind each."
    )
    md.append("")
    md.append("| ID | Title | Resolved | Observed |")
    md.append("|---|---|---|---|")
    for e in failed:
        title = (e.get("title") or "").strip().strip('"')
        if len(title) > 80:
            title = title[:77] + "..."
        observed = (e.get("observed") or "").strip()
        if len(observed) > 80:
            observed = observed[:77] + "..."
        md.append(
            f"| {e.get('id','?')} | {title} | "
            f"{e.get('outcome_at','-')} | {observed or '-'} |"
        )
    md.append("")
    md.append("## Pending predictions (in flight)")
    md.append("")
    md.append(
        "Sorted by `registered_at` ascending so the longest-pending "
        "entries surface first. Each carries a `criterion:` field naming "
        "the exact measurement that resolves it."
    )
    md.append("")
    md.append("| ID | Title | Registered | Type |")
    md.append("|---|---|---|---|")
    for e in pending:
        title = (e.get("title") or "").strip().strip('"')
        if len(title) > 80:
            title = title[:77] + "..."
        md.append(
            f"| {e.get('id','?')} | {title} | "
            f"{e.get('registered_at','-')} | {e.get('type','-')} |"
        )
    md.append("")
    md.append("## Passed predictions")
    md.append("")
    md.append("| ID | Title | Resolved |")
    md.append("|---|---|---|")
    for e in passed:
        title = (e.get("title") or "").strip().strip('"')
        if len(title) > 80:
            title = title[:77] + "..."
        md.append(
            f"| {e.get('id','?')} | {title} | "
            f"{e.get('outcome_at','-')} |"
        )
    md.append("")
    if revised:
        md.append("## Revised predictions")
        md.append("")
        md.append(
            "Entries whose initial outcome was revised by a later entry. "
            "The `superseded_by` field on each entry below points at the "
            "revising entry."
        )
        md.append("")
        md.append("| ID | Title | Resolved | Superseded by |")
        md.append("|---|---|---|---|")
        for e in revised:
            title = (e.get("title") or "").strip().strip('"')
            if len(title) > 80:
                title = title[:77] + "..."
            md.append(
                f"| {e.get('id','?')} | {title} | "
                f"{e.get('outcome_at','-')} | "
                f"{e.get('superseded_by','-')} |"
            )
        md.append("")
    # Evidence pointer validation. The methodology paper section 6c
    # falsification-discipline claim depends on the evidence pointers
    # being live; if a kill record cites
    # `evidence: fvs_eval/REPORT.md` and that file no longer exists,
    # the audit trail is broken. This walk surfaces such drift.
    broken_evidence = _validate_evidence_pointers(entries)
    md.append("## Evidence pointer validation")
    md.append("")
    n_with_evidence = sum(1 for e in entries if e.get("evidence"))
    n_broken = len(broken_evidence)
    if n_broken == 0:
        md.append(
            f"All {n_with_evidence} of {len(entries)} entries with an "
            f"`evidence:` field point at paths that resolve in the "
            f"working tree. Audit-trail integrity verified."
        )
    else:
        md.append(
            f"{n_broken} of {n_with_evidence} entries with an "
            f"`evidence:` field cite paths that do not resolve in the "
            f"working tree. Each broken pointer is a candidate for "
            f"investigation: file rename, file deletion, or evidence-"
            f"field typo."
        )
        md.append("")
        md.append("| Entry | Broken paths |")
        md.append("|---|---|")
        for entry_id, paths in sorted(broken_evidence.items()):
            md.append(f"| {entry_id} | {', '.join(paths)} |")
    md.append("")
    md.append(
        "**Discipline.** Pointers are validated against the operator-"
        "local working tree. Files that exist in upstream but were "
        "renamed before this aggregation runs surface here as "
        "broken; the registry README's "
        "deletion-is-forbidden discipline does not extend to "
        "evidence files cited from outside `data/falsifications/`. "
        "When a cited evidence file is renamed, update the citing "
        "entry rather than restoring the file under its old name."
    )
    md.append("")

    md.append("## Reproducibility")
    md.append("")
    md.append(
        "Re-derive via `python3 scripts/falsification_status.py`. The "
        "registry README at `data/falsifications/README.md` is the "
        "canonical schema; per-entry F-NNNN-NNN.md files are the "
        "canonical record (deletion is forbidden by the registry "
        "discipline; revisions are new entries with `superseded_by`). "
        "This summary is a re-derivable aggregation of those, not a "
        "replacement for them."
    )
    md.append("")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(out_dir / "STATUS.md", "\n".join(md))
    payload = {
        "generated": today,
        "n_entries": n,
        "by_outcome": dict(by_outcome.most_common()),
        "by_type": dict(by_type.most_common()),
        "by_outcome_and_type": {
            k: dict(v) for k, v in by_outcome_and_type.items()
        },
        "pending_ids": [e.get("id") for e in pending],
        "failed_ids": [e.get("id") for e in failed],
        "passed_ids": [e.get("id") for e in passed],
        "revised_ids": [e.get("id") for e in revised],
        "skipped_paths": skipped,
        "broken_evidence_pointers": broken_evidence,
    }
    _atomic_write(
        out_dir / "STATUS.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )

    print(f"wrote {out_dir}/STATUS.md + STATUS.json")
    print(f"  entries: {n}; outcomes: {dict(by_outcome.most_common())}")
    if skipped:
        print(f"  skipped (unparseable): {len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
