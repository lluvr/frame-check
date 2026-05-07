"""Operator review surface for Frame Mirror's accumulated data.

Mirror captures three streams users opt into: structural session
summaries, decision-outcome pairs, and falsification flags on frame
verdicts. This script aggregates the latter two so the operator can
read what the data is saying without writing SQL by hand or trusting
a downstream tool that has not been versioned alongside the schema.

Why this is here
----------------

The compounding loop the Mirror surface tries to build:

  /check log -> /saved attach outcome -> /mirror reflect
  per-frame disagree -> aggregate flag -> rule refinement

Both arrows on the right require a read path. Without one, the data
sits in SQLite and the loop never closes. Operators do not earn the
right to claim the loop works until they can show specific instances
of the loop closing (a frame whose detection rule was refined because
of accumulated flags; a decision whose outcome shifted methodology).
This script is the read path.

Design discipline
-----------------

The script aggregates and counts. It does NOT:

  - Attribute flags or decisions to specific users (cookie-anonymous
    is a structural commitment, not a paper one).
  - Render free-form prose by default (decision_text, outcome_text,
    falsification why_text are user-supplied; opt-in via --show-text
    so the operator's eye does not slide across them in passing).
  - Modify the database in any way (no backfills, no deletions, no
    schema migrations from this surface).

It DOES:

  - Total falsification flags by FVS and by flag_type.
  - Decision/outcome rate over a window (default 30 days).
  - Unresolved decisions older than the validation cutoff (default
    7 days, matching the /check return-visit nudge gate).
  - Per-FVS top reasons when --show-text is set (with cookie-anon
    user IDs truncated to an 8-char prefix so cross-row patterns
    from a single user are visible without exposing the full
    identifier; 8 chars on a UUID4 keeps collisions negligible at
    realistic adoption scales).

Privacy posture
---------------

This script reads the same SQLite the live service writes to. It
does not write a file by default; output is stdout, redirect to a
local file if a snapshot is wanted. Snapshots are operator-local
artifacts, not corpus exports; do not commit them. The MIRROR_DB_PATH
env var (consumed by mirror.py) selects which DB this reads.

Usage
-----

  python scripts/mirror_review.py
  python scripts/mirror_review.py --days 30 --top 10
  python scripts/mirror_review.py --show-text --json > snapshot.json
"""

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import mirror  # noqa: E402


def _summarize_falsifications(
    rows: list[dict],
    top: int,
) -> dict:
    by_type: Counter[str] = Counter()
    by_fvs: Counter[str] = Counter()
    by_fvs_type: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        flag_type = r.get("flag_type") or "unknown"
        fvs_id = r.get("fvs_id") or "UNKNOWN"
        by_type[flag_type] += 1
        by_fvs[fvs_id] += 1
        by_fvs_type[fvs_id][flag_type] += 1
    # Top-N lists shaped as object-arrays
    # ([{"fvs_id": "FVS-007", "count": 2}, ...]) rather than
    # tuple-arrays so the JSON output is self-documenting for
    # downstream tooling. Tuples serialize as positional arrays
    # which require a separate convention to interpret; named
    # fields hold their meaning.
    def _top(counter: Counter[str], n: int) -> list[dict]:
        return [{"fvs_id": k, "count": v} for k, v in counter.most_common(n)]
    return {
        "total_flags": len(rows),
        "by_flag_type": dict(by_type),
        "top_fvs_overall": _top(by_fvs, top),
        "top_fvs_by_type": {
            ft: _top(
                Counter({
                    fvs: by_fvs_type[fvs][ft]
                    for fvs in by_fvs_type
                    if by_fvs_type[fvs][ft] > 0
                }),
                top,
            )
            for ft in ("detection", "reasoning", "frame_choice")
        },
    }


def _detect_patterns(
    falsifications: list[dict],
    decisions_summary: dict,
    cross_user_threshold: int = 2,
    low_outcome_rate: float = 0.3,
    min_decisions_for_rate: int = 5,
) -> list[dict]:
    """Surface patterns worth the operator's attention. Reads the
    raw falsification rows and the decisions summary; emits a list
    of structured findings (each with kind + detail). Empty list
    means no signal in the data; the section renders as 'no
    patterns to surface' rather than going silent so the operator
    knows the script ran.

    Three pattern kinds:

    1. cross_user_agreement: same FVS + flag_type flagged by N
       distinct users. N=2 default because two independent users
       agreeing is much stronger signal than one. The set-of-users
       check (rather than total-flag-count) screens out a single
       user spam-flagging the same frame.

       Known limitation: cookie-anonymous identity means a single
       user clearing browser cookies and re-flagging the same FVS
       appears as two distinct user_ids in this aggregate. In the
       low-data regime this is mostly noise; at scale (and after
       per-class calibration corpora exist) the signal washes out.
       A persistent-identity (account login) future would close
       this gap; out of scope for the current cookie-anonymous
       posture.

    2. low_outcome_rate: outcome_rate below threshold with at least
       min_decisions_for_rate decisions in the window. Below the
       min, the rate is too noisy to act on. Above it, a low rate
       suggests the return-visit nudge is not landing or the
       outcome-capture UX has friction worth diagnosing.

    3. high_unresolved_share: more than half the in-window
       decisions are unresolved >7 days. Same diagnostic as #2
       but for the backlog rather than the rate.

    Thresholds are operator-tunable via CLI flags so the script
    stays useful across different adoption regimes (sub-1% to
    higher). Default thresholds picked for the low-data regime;
    raise once data accumulates.
    """
    findings: list[dict] = []

    # Pattern 1: cross-user agreement on FVS + flag_type
    by_fvs_type_users: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in falsifications:
        fvs = r.get("fvs_id")
        ft = r.get("flag_type")
        uid = r.get("user_id")
        if fvs and ft and uid:
            by_fvs_type_users[(fvs, ft)].add(uid)
    for (fvs, ft), users in by_fvs_type_users.items():
        if len(users) >= cross_user_threshold:
            findings.append({
                "kind": "cross_user_agreement",
                "fvs_id": fvs,
                "flag_type": ft,
                "distinct_users": len(users),
                "detail": (
                    f"{len(users)} distinct users flagged {fvs} as "
                    f"'{ft}'. Independent agreement is a stronger "
                    f"signal than total flag count; consider "
                    f"revisiting the rule."
                ),
            })

    # Pattern 2: low outcome rate above the noise floor.
    total = decisions_summary.get("total_decisions", 0)
    rate = decisions_summary.get("outcome_rate", 0.0)
    if total >= min_decisions_for_rate and rate < low_outcome_rate:
        findings.append({
            "kind": "low_outcome_rate",
            "outcome_rate": rate,
            "total_decisions": total,
            "detail": (
                f"Outcome rate {rate} on {total} decisions is below "
                f"the {low_outcome_rate} threshold. The return-visit "
                f"nudge may not be landing; check whether users are "
                f"finding the log-outcome surface."
            ),
        })

    # Pattern 3: high unresolved share (>50% of in-window decisions).
    unresolved = decisions_summary.get("unresolved_over_7_days", 0)
    if total >= min_decisions_for_rate and total > 0:
        share = unresolved / total
        if share > 0.5:
            findings.append({
                "kind": "high_unresolved_share",
                "unresolved": unresolved,
                "total_decisions": total,
                "share": round(share, 2),
                "detail": (
                    f"{unresolved} of {total} in-window decisions are "
                    f"unresolved >7 days ({round(share, 2)} share). "
                    f"Outcome capture is the bottleneck; review "
                    f"whether the nudge surface is reaching returning "
                    f"users."
                ),
            })

    return findings


def _summarize_decisions(rows: list[dict]) -> dict:
    total = len(rows)
    with_outcome = sum(1 for r in rows if r.get("outcome_at"))
    rate = (with_outcome / total) if total else 0.0
    now = time.time()
    median_gap_seconds: float | None = None
    gaps = [
        r["outcome_at"] - r["decision_at"]
        for r in rows
        if r.get("outcome_at") and r.get("decision_at")
    ]
    if gaps:
        gaps.sort()
        median_gap_seconds = gaps[len(gaps) // 2]
    unresolved_old = sum(
        1
        for r in rows
        if not r.get("outcome_at")
        and r.get("decision_at")
        and (now - r["decision_at"]) >= 7 * 86400
    )
    by_user: Counter[str] = Counter()
    for r in rows:
        uid = r.get("user_id") or ""
        if uid:
            by_user[uid] += 1
    return {
        "total_decisions": total,
        "with_outcome": with_outcome,
        "outcome_rate": round(rate, 4),
        "unresolved_over_7_days": unresolved_old,
        "median_decision_to_outcome_gap_days": (
            round(median_gap_seconds / 86400.0, 1)
            if median_gap_seconds is not None else None
        ),
        "active_users": len(by_user),
        # Top-N users shaped as object-arrays for the same
        # self-documentation reason as the falsification top-N
        # lists. user_prefix is the eight-character truncation
        # described in the privacy page; the full identifier is
        # never emitted by the CLI under any flag.
        "decisions_per_user_top": [
            {"user_prefix": uid[:8], "count": n}
            for uid, n in by_user.most_common(5)
        ],
    }


def _format_text(
    falsifications: list[dict],
    falsifications_summary: dict,
    decisions_summary: dict,
    patterns: list[dict],
    days: int | None,
    show_text: bool,
    db_path: str | None = None,
) -> str:
    out: list[str] = []
    window = (
        f"last {days} days" if days is not None and days > 0 else "all time"
    )
    # ISO timestamp at the top makes piped snapshots
    # (`> review-2026-05-05.txt`) self-describing once the
    # operator opens them later. Local time, since the operator
    # reads and acts in local time; UTC offset preserved by
    # %z so the timestamp is unambiguous.
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime())
    out.append(f"Frame Mirror review (window: {window})")
    out.append(f"Generated: {generated_at}")
    # DB path makes the snapshot self-describing about which
    # database it was read from. The CLI defaults to the
    # production data dir or the repo fallback when MIRROR_DB_PATH
    # is unset; an operator running it without the env var might
    # silently query the wrong file (empty default vs production
    # data). Printing the path resolves the ambiguity at-a-glance.
    if db_path:
        out.append(f"DB: {db_path}")
    out.append("=" * 56)
    out.append("")

    out.append("Falsifications")
    out.append("-" * 56)
    fs = falsifications_summary
    out.append(f"  Total flags:       {fs['total_flags']}")
    if fs["total_flags"] == 0:
        out.append("  (no flags in window)")
    else:
        bft = fs["by_flag_type"]
        out.append("  By flag_type:")
        for ft in ("detection", "reasoning", "frame_choice"):
            out.append(f"    {ft:<13} {bft.get(ft, 0)}")
        out.append("")
        out.append("  Top FVS overall:")
        for entry in fs["top_fvs_overall"]:
            out.append(
                f"    {entry['fvs_id']:<10} {entry['count']} flag(s)"
            )
        for ft in ("detection", "reasoning", "frame_choice"):
            top = fs["top_fvs_by_type"].get(ft, [])
            if top:
                out.append("")
                out.append(f"  Top FVS by '{ft}':")
                for entry in top:
                    out.append(
                        f"    {entry['fvs_id']:<10} {entry['count']}"
                    )
    out.append("")

    out.append("Decisions and outcomes")
    out.append("-" * 56)
    ds = decisions_summary
    out.append(f"  Total decisions:           {ds['total_decisions']} (in window)")
    out.append(f"  With outcome:              {ds['with_outcome']} (in window)")
    out.append(f"  Outcome rate:              {ds['outcome_rate']} (in window)")
    out.append(f"  Unresolved >7 days:        {ds['unresolved_over_7_days']} (in window)")
    gap = ds.get("median_decision_to_outcome_gap_days")
    out.append(f"  Median decision -> outcome gap (days): {gap}")
    out.append(f"  Active users:              {ds['active_users']}")
    if ds["decisions_per_user_top"]:
        out.append("  Top users by decision count (cookie-anon, prefix):")
        for entry in ds["decisions_per_user_top"]:
            prefix = entry["user_prefix"] or "????????"
            out.append(f"    {prefix}... {entry['count']}")
    out.append("")

    out.append("Patterns worth investigating")
    out.append("-" * 56)
    if not patterns:
        out.append("  (no patterns above thresholds; data may be too thin)")
    else:
        for p in patterns:
            out.append(f"  [{p['kind']}] {p['detail']}")
    out.append("")

    if show_text and falsifications:
        out.append("Falsification reasons (most recent first)")
        out.append("-" * 56)
        for r in falsifications[:50]:
            uid = (r.get("user_id") or "")[:8]
            fvs = r.get("fvs_id") or "?"
            ft = r.get("flag_type") or "?"
            why = (r.get("why_text") or "").replace("\n", " ")
            out.append(f"  [{uid}...] {fvs} ({ft}): {why}")
        out.append("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--days", type=int, default=30,
        help="Time window in days (default: 30). 0 means everything.",
    )
    ap.add_argument(
        "--top", type=int, default=10,
        help="Top-N FVS entries to surface (default: 10).",
    )
    ap.add_argument(
        "--show-text", action="store_true",
        help=(
            "Dump the most recent falsification why_text excerpts. "
            "Off by default so prose stays opt-in to read."
        ),
    )
    ap.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    ap.add_argument(
        "--cross-user-threshold", type=int, default=2,
        help=(
            "Distinct-user count for the cross-user-agreement "
            "pattern (default: 2). Two independent users flagging "
            "the same FVS+flag_type is much stronger signal than "
            "one user spam-flagging."
        ),
    )
    ap.add_argument(
        "--low-outcome-rate", type=float, default=0.3,
        help=(
            "Outcome-rate threshold for the low-rate pattern "
            "(default: 0.3). Below this rate, the script flags "
            "the outcome-capture surface as worth diagnosing."
        ),
    )
    ap.add_argument(
        "--min-decisions-for-rate", type=int, default=5,
        help=(
            "Minimum decisions in window before the outcome-rate "
            "pattern fires (default: 5). Below this, the rate is "
            "too noisy to act on."
        ),
    )
    args = ap.parse_args(argv)

    days = args.days if args.days > 0 else None

    # Idempotent. If the DB file exists but the schema is older
    # than mirror_falsifications, init_db creates the missing
    # table; if the DB does not exist yet, init_db creates it
    # empty. Either way, the aggregate queries below run cleanly.
    mirror.init_db()

    # Resolve the DB path now so we can surface it in the output;
    # the operator running without MIRROR_DB_PATH set otherwise
    # has no signal that the script chose a default file.
    db_path = str(mirror._db_path())

    falsifications = mirror.get_falsifications_aggregate(limit=10000)
    if days is not None:
        cutoff = time.time() - (days * 86400.0)
        falsifications = [
            r for r in falsifications if r.get("flagged_at", 0) >= cutoff
        ]
    f_summary = _summarize_falsifications(falsifications, args.top)

    decisions = mirror.get_decisions_aggregate(days=days, limit=10000)
    d_summary = _summarize_decisions(decisions)
    patterns = _detect_patterns(
        falsifications=falsifications,
        decisions_summary=d_summary,
        cross_user_threshold=args.cross_user_threshold,
        low_outcome_rate=args.low_outcome_rate,
        min_decisions_for_rate=args.min_decisions_for_rate,
    )

    if args.json:
        payload = {
            "window_days": days,
            "falsifications": f_summary,
            "decisions": d_summary,
            "patterns_worth_investigating": patterns,
        }
        if args.show_text:
            payload["falsification_excerpts"] = [
                {
                    "user_prefix": (r.get("user_id") or "")[:8],
                    "fvs_id": r.get("fvs_id"),
                    "flag_type": r.get("flag_type"),
                    "why_text": r.get("why_text"),
                    "flagged_at": r.get("flagged_at"),
                }
                for r in falsifications[:50]
            ]
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(_format_text(
        falsifications, f_summary, d_summary, patterns,
        days, args.show_text, db_path=db_path,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
