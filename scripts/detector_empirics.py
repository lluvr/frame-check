"""Detector empirics: per-FVS firing rates across the calibration corpus.

Runs `frame_check` against every available curated document (adversarial
fixtures + worked examples) and aggregates how often each FVS detector
fires, how often each coverage perspective is addressed, and how the
genre classifier distributes across the corpus. The output is a
descriptive empirical artifact suitable for citation in the methodology
paper §5 ("how the detectors behave on our calibration corpus").

What this measures, exactly
---------------------------

- **Firing rate**: for each FVS-NNN, the percentage of corpus documents
  where the detector fires as PRESENT. Computed from
  `analysis.frame_library_matches` filtered to entries whose
  `name` does NOT carry the `(absent)` suffix.

- **Absence rate**: complement of firing rate. The mirror surface; the
  current methodology emphasizes absence-side reading and these numbers
  let the paper claim "FVS-NNN absent in M of N corpus documents" with
  empirical backing.

- **Coverage-perspective addressed rate**: for each of the 5 perspectives
  (causes, risks, stakeholders, trends, uncertainty), the percentage of
  documents where the detector flags it as addressed.

- **Genre classification distribution**: count of corpus documents
  classified into each genre vs. abstaining. Surfaces the construct-
  honest abstention rate as a citable number.

What this does NOT measure
--------------------------

- **Recall.** Recall requires gold-standard "what FVS *should* fire"
  labels per document. Those are operator-authoring work (substantive
  content, no LLM drafting per discipline). The harness DOES NOT
  estimate recall from its own output. To compute recall, an operator
  populates gold-standard labels using the template at
  `scripts/detector_gold_standard_template.md`; once enough fixtures
  have labels, an extension to this harness can produce a recall
  table.

- **Precision.** Same constraint. Reported firings include both true
  positives and false positives; the harness has no way to distinguish
  without labels.

- **Whether the detectors detect what they claim to detect.** Construct
  validity is a separate question (see `CONSTRUCT_VALIDITY_AUDIT_v1.md`).
  This harness measures the OBSERVED behavior, not whether that
  behavior is correct.

Usage
-----

    python3 scripts/detector_empirics.py
        # Default: runs against data/adversarial_fixtures/*/document.md
        # and data/worked_examples/*.md (top-level .md only; the
        # paired directories carry analyses, not source documents).
        # Writes calibration/results/detector_empirics_<date>/REPORT.md
        # plus per_document.json (raw measurements) and aggregate.json.

    python3 scripts/detector_empirics.py --out /tmp/empirics_smoke
        # Override output directory.

    python3 scripts/detector_empirics.py --bin /home/llucic/.local/bin/frame-check-mcp
        # Override mcp_server invocation. Default: dev-tree
        # `python3 mcp_server.py` so changes-in-progress are measured.

The harness operates over stdio MCP (same protocol Claude Desktop
uses), so what it measures is exactly what an integrating agent
sees. No internal-API shortcuts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADVERSARIAL_DIR = REPO / "data" / "adversarial_fixtures"
WORKED_EXAMPLES_DIR = REPO / "data" / "worked_examples"


def _send(proc: subprocess.Popen, msg: dict) -> None:
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _recv(proc: subprocess.Popen) -> dict:
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("mcp_server closed stdout")
    return json.loads(line)


def _spawn(bin_args: list[str]) -> subprocess.Popen:
    proc = subprocess.Popen(
        bin_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    _send(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "detector-empirics", "version": "1.0"},
            "capabilities": {},
        },
    })
    _recv(proc)
    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    return proc


def _frame_check(proc: subprocess.Popen, doc_text: str) -> dict:
    _send(proc, {
        "jsonrpc": "2.0", "id": 99, "method": "tools/call",
        "params": {
            "name": "frame_check",
            "arguments": {
                "document_text": doc_text,
                "include_divergence": True,
                "compose_budget": "minimal",  # we read structural fields only
            },
        },
    })
    resp = _recv(proc)
    if "error" in resp:
        raise RuntimeError(f"frame_check error: {resp['error']}")
    text_item = next(
        (c for c in resp["result"]["content"] if c.get("type") == "text"),
        {"text": "{}"},
    )
    return json.loads(text_item["text"])


def _enumerate_documents() -> list[tuple[str, Path]]:
    """Return [(corpus_label, doc_path), ...] for all corpus documents."""
    docs: list[tuple[str, Path]] = []
    if ADVERSARIAL_DIR.is_dir():
        for sub in sorted(ADVERSARIAL_DIR.iterdir()):
            if sub.is_dir() and (sub / "document.md").is_file():
                docs.append((f"adversarial/{sub.name}", sub / "document.md"))
    if WORKED_EXAMPLES_DIR.is_dir():
        for f in sorted(WORKED_EXAMPLES_DIR.glob("*.md")):
            # Skip README + template + review docs; only operator-curated
            # source documents are corpus members.
            if f.name.startswith("_") or f.name == "README.md":
                continue
            docs.append((f"worked/{f.stem}", f))
    return docs


def _present_fvs(payload: dict) -> set[str]:
    """FVS IDs whose detectors fired as PRESENT (not absence-marked).

    Read `pattern_kind` enum field per `SCHEMA_SPLIT_PROPOSAL_v1.md`
    Option A (landed at commit 92c0190 2026-04-30). Five enum values
    encode the V1-detector emission convention; only `present_detected`,
    `present_past`, and `present_future` count as PRESENCE; the
    `absence_detected` value is the V1 absence-pattern detector
    (today only FVS-007 fires this shape).

    Backward-compat fallback: if `pattern_kind` is absent (older
    payload from a pre-92c0190 wheel), fall back to the legacy
    suffix-parsing convention (`(absent)` substring in `name`). This
    keeps the harness compatible with older wheel artifacts; today
    the dev tree always emits `pattern_kind` so the fallback never
    fires in practice.
    """
    presence_kinds = {"present_detected", "present_past", "present_future"}
    present: set[str] = set()
    for m in payload.get("analysis", {}).get("frame_library_matches", []):
        fvs = m.get("fvs_id") or m.get("frame_id")
        if not fvs:
            continue
        kind = m.get("pattern_kind")
        if kind:
            if kind in presence_kinds:
                present.add(fvs)
            continue
        # Legacy fallback for payloads emitted by pre-92c0190 wheels.
        # Older shape has no pattern_kind field; the convention was to
        # encode absence via the literal `(absent)` substring in `name`.
        name = m.get("name", "") or ""
        if "(absent)" in name.lower():
            continue
        if "absent" in (m.get("status") or "").lower():
            continue
        present.add(fvs)
    return present


def _absent_pattern_fvs(payload: dict) -> set[str]:
    """FVS IDs whose detectors fired as ABSENCE-pattern.

    Returns FVS IDs where `pattern_kind == "absence_detected"`. Today
    only FVS-007 has an absence-pattern detector in `frame_library.py`;
    the per-corpus aggregate of absence-pattern fires is a separate
    metric from the presence-pattern aggregate this harness reports
    in `per_fvs_fires`. Surfaced here so future operator analysis of
    absence-detector behavior has a structured-data path.

    Backward-compat fallback: parse the `(absent)` suffix in `name`
    when `pattern_kind` is absent.
    """
    absent: set[str] = set()
    for m in payload.get("analysis", {}).get("frame_library_matches", []):
        fvs = m.get("fvs_id") or m.get("frame_id")
        if not fvs:
            continue
        kind = m.get("pattern_kind")
        if kind:
            if kind == "absence_detected":
                absent.add(fvs)
            continue
        name = m.get("name", "") or ""
        if "(absent)" in name.lower():
            absent.add(fvs)
    return absent


def _addressed_perspectives(payload: dict) -> list[str]:
    return list(payload.get("analysis", {}).get("coverage", {}).get("addressed", []))


def _frame_deepening_fires(payload: dict) -> list[str]:
    """Names of frame_deepening sub-detectors that fired on this
    document.

    Per `NEXT_STEPS.md` "Substrate-side composition: web exposure"
    the four MCP-only analyzers are gated on validation before web
    exposure. `frame_deepening` is one of them; its blocker is
    "needs corpus-level firing-rate measurement on each of the
    three detectors (temporal_scope, stakeholder_map,
    falsification_conditions)." This helper produces the per-doc
    fire signal that feeds the aggregate so an expert-grading
    pass has empirical baseline numbers to calibrate against.

    Fire semantic: each detector at `frame_deepening.py` returns
    `Optional[dict]`. None = no signal (e.g., no year references
    found, no role mentions found, no candidate falsification
    phrases found). Any dict = at least one signal found,
    regardless of how rich the dict's content is. The MCP wire
    shape preserves this: `analysis.frame_deepening.<detector>`
    is `null` when the detector returned None and the dict
    otherwise. Mirroring that here so the harness output cleanly
    matches the wire-level fire definition.
    """
    fd = payload.get("analysis", {}).get("frame_deepening", {}) or {}
    fired: list[str] = []
    for detector in (
        "temporal_scope", "stakeholder_map", "falsification_conditions",
    ):
        if fd.get(detector) is not None:
            fired.append(detector)
    return fired


def _genre_classification(payload: dict) -> str | None:
    g = payload.get("analysis", {}).get("genre", {}) or {}
    return g.get("classification")


def _voice_classification(payload: dict) -> str | None:
    v = payload.get("analysis", {}).get("voice", {}) or {}
    return v.get("classification")


def _measure(proc: subprocess.Popen, label: str, path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    payload = _frame_check(proc, text)
    return {
        "label": label,
        "path": str(path.relative_to(REPO)),
        "word_count": payload.get("analysis", {})
                              .get("document", {})
                              .get("word_count_estimate"),
        "present_fvs": sorted(_present_fvs(payload)),
        "absent_pattern_fvs": sorted(_absent_pattern_fvs(payload)),
        "addressed_perspectives": _addressed_perspectives(payload),
        "missing_perspectives": list(
            payload.get("analysis", {}).get("coverage", {}).get("missing", [])
        ),
        "genre_classification": _genre_classification(payload),
        "voice_classification": _voice_classification(payload),
        "absence_cluster_dimensions": [
            c.get("dimension")
            for c in payload.get("divergence", {}).get("absence_clusters", [])
        ],
        "frame_deepening_fires": _frame_deepening_fires(payload),
    }


def _aggregate(per_doc: list[dict]) -> dict:
    n = len(per_doc)
    fvs_fires: Counter = Counter()
    fvs_absent_fires: Counter = Counter()
    coverage_addressed: Counter = Counter()
    genre_classified: Counter = Counter()
    voice_classified: Counter = Counter()
    cluster_dims: Counter = Counter()
    frame_deepening: Counter = Counter()
    for d in per_doc:
        for fvs in d["present_fvs"]:
            fvs_fires[fvs] += 1
        for fvs in d.get("absent_pattern_fvs", []):
            fvs_absent_fires[fvs] += 1
        for p in d["addressed_perspectives"]:
            coverage_addressed[p] += 1
        genre_classified[d["genre_classification"] or "(abstain)"] += 1
        voice_classified[d["voice_classification"] or "(abstain)"] += 1
        for dim in d["absence_cluster_dimensions"]:
            cluster_dims[dim] += 1
        for det in d.get("frame_deepening_fires", []):
            frame_deepening[det] += 1
    # frame_deepening always reports the three sub-detector keys
    # so the operator sees zero-fire detectors explicitly. Without
    # this fill, a detector that never fires on the corpus would
    # be absent from the aggregate dict and the report would not
    # mention it at all (silent zero); presenting it as "0 of N"
    # is the construct-honest reading.
    for det in ("temporal_scope", "stakeholder_map",
                "falsification_conditions"):
        frame_deepening.setdefault(det, 0)
    return {
        "n_documents": n,
        "per_fvs_fires": dict(fvs_fires.most_common()),
        "per_fvs_absent_pattern_fires": dict(fvs_absent_fires.most_common()),
        "coverage_perspective_addressed": dict(coverage_addressed.most_common()),
        "genre_distribution": dict(genre_classified.most_common()),
        "voice_distribution": dict(voice_classified.most_common()),
        "absence_cluster_dimension_fires": dict(cluster_dims.most_common()),
        "frame_deepening_per_detector_fires": dict(
            frame_deepening.most_common()
        ),
    }


def _markdown_report(per_doc: list[dict], agg: dict) -> str:
    n = agg["n_documents"]
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append(f"# Detector empirics: per-FVS firing rates")
    lines.append("")
    lines.append(f"**Generated:** {today}")
    lines.append(f"**Corpus size:** {n} documents")
    lines.append(f"**Source:** `data/adversarial_fixtures/*/document.md` + "
                 f"`data/worked_examples/*.md` (top-level only)")
    lines.append("")
    lines.append("## What this measures")
    lines.append("")
    lines.append(
        "Firing rate per FVS detector and per coverage perspective. "
        "Genre + voice classification distribution. Absence-cluster dimension "
        "incidence. Computed by running `frame_check` over stdio MCP against "
        "each document and aggregating the structural fields. **Recall and "
        "precision are not reported**; those require gold-standard labels per "
        "document, which is operator-authoring work outside this harness."
    )
    lines.append("")
    lines.append("## Per-FVS firing rate (presence detection)")
    lines.append("")
    lines.append("| FVS | Fires in | of N | % |")
    lines.append("|---|---|---|---|")
    fires = agg["per_fvs_fires"]
    if not fires:
        lines.append(f"| (none) | 0 | {n} | 0 |")
    for fvs, k in fires.items():
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {fvs} | {k} | {n} | {pct} |")
    lines.append("")
    lines.append(
        "Read this table as: 'FVS-NNN fires as PRESENT in K of N corpus "
        "documents.' The complement (`N - K`) is the absence count for the "
        "same detector. The methodology paper's claim 'FVS-NNN absent in M "
        "of N documents' is `(N - K)` for this row, MINUS any rows where "
        "the same FVS-NNN fires as ABSENCE-pattern (next table) since those "
        "are not silently-absent but actively-detected-as-absent."
    )
    lines.append("")
    lines.append("## Per-FVS absence-pattern firing rate")
    lines.append("")
    lines.append("| FVS | Fires in | of N | % |")
    lines.append("|---|---|---|---|")
    absent_fires = agg.get("per_fvs_absent_pattern_fires", {})
    if not absent_fires:
        lines.append(f"| (none) | 0 | {n} | 0 |")
    for fvs, k in absent_fires.items():
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {fvs} | {k} | {n} | {pct} |")
    lines.append("")
    lines.append(
        "V1-detector absence-pattern fires (`pattern_kind == \"absence_detected\"` "
        "in the structured emission). Today only FVS-007 Failure Framing has an "
        "absence-pattern detector in `frame_library.py:362-370` (fires when "
        "risks AND uncertainty are both missing AND unhedged-claim density "
        "exceeds 60%). A document where FVS-007 fires absence-pattern is "
        "actively-detected-as-absent on the failure-framing dimension, distinct "
        "from documents where FVS-007 is silently-absent (no fire, no "
        "evidence of absence-detection structural conditions)."
    )
    lines.append("")
    lines.append("## Coverage perspective addressed rate")
    lines.append("")
    lines.append("| Perspective | Addressed in | of N | % |")
    lines.append("|---|---|---|---|")
    for p in ("causes", "risks", "stakeholders", "trends", "uncertainty"):
        k = agg["coverage_perspective_addressed"].get(p, 0)
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {p} | {k} | {n} | {pct} |")
    lines.append("")
    lines.append("## Genre classification distribution")
    lines.append("")
    lines.append("| Classification | Count | % |")
    lines.append("|---|---|---|")
    for g, k in agg["genre_distribution"].items():
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {g} | {k} | {pct} |")
    lines.append("")
    lines.append(
        "`(abstain)` = classifier returned `null` (no feature-marker regex "
        "matched). Per the evidence discipline, abstention is "
        "preferred over mislabeling. A high abstention rate on a corpus is "
        "not a defect; it is a measurement of how often the regex-based "
        "feature surface fires."
    )
    lines.append("")
    lines.append("## Voice classification distribution")
    lines.append("")
    lines.append("| Classification | Count | % |")
    lines.append("|---|---|---|")
    for v, k in agg["voice_distribution"].items():
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {v} | {k} | {pct} |")
    lines.append("")
    lines.append("## Frame deepening per-detector firing rate")
    lines.append("")
    lines.append("| Detector | Fires in | of N | % |")
    lines.append("|---|---|---|---|")
    for det, k in agg["frame_deepening_per_detector_fires"].items():
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {det} | {k} | {n} | {pct} |")
    lines.append("")
    lines.append(
        "Three regex/feature detectors at `frame_deepening.py` "
        "(`detect_temporal_scope`, `detect_stakeholder_map`, "
        "`detect_falsification_conditions`). Each returns "
        "`Optional[dict]`: `None` when no signal is found, a dict "
        "of structural evidence otherwise. The MCP wire shape at "
        "`analysis.frame_deepening.<detector>` preserves this "
        "distinction (`null` vs object). 'Fires' here means the "
        "detector returned a non-`None` dict, regardless of how "
        "rich the dict's content is. Per `NEXT_STEPS.md` "
        "\"Substrate-side composition: web exposure\", web "
        "exposure of `frame_deepening` is gated on per-detector "
        "expert-grading; this aggregate is the empirical baseline "
        "the grading pass calibrates against. A 100% firing rate "
        "across the corpus is itself a finding: it tells the "
        "operator the corpus has CEILING saturation on this "
        "detector and grading needs documents specifically lacking "
        "the signal to measure the false-positive boundary."
    )
    lines.append("")
    lines.append("## Absence-cluster dimension incidence")
    lines.append("")
    lines.append("| Dimension | Fires in | of N | % |")
    lines.append("|---|---|---|---|")
    for dim, k in agg["absence_cluster_dimension_fires"].items():
        pct = round(100.0 * k / n) if n else 0
        lines.append(f"| {dim} | {k} | {n} | {pct} |")
    lines.append("")
    lines.append("## Per-document detail")
    lines.append("")
    lines.append(
        "| Document | Words | Genre | Voice | Present | Absent-pattern | Addressed | Deepening |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    # Single-letter codes for the per-doc Deepening column so the
    # table stays narrow: T = temporal_scope, S = stakeholder_map,
    # F = falsification_conditions. Unfired detectors render as `-`
    # in their slot so a "TS-" row is readable as "temporal +
    # stakeholder fired, falsification did not." Aggregate counts
    # in the section above are the load-bearing analytical surface;
    # this column is for per-doc scanning of which detectors fire
    # together (the corpus-saturation finding the aggregate names
    # would surface here as every row reading "TSF").
    deepening_codes = {
        "temporal_scope": "T",
        "stakeholder_map": "S",
        "falsification_conditions": "F",
    }
    for d in per_doc:
        present_str = ",".join(d["present_fvs"]) or "-"
        absent_str = ",".join(d.get("absent_pattern_fvs", [])) or "-"
        addr_str = ",".join(d["addressed_perspectives"]) or "-"
        g = d["genre_classification"] or "-"
        v = d["voice_classification"] or "-"
        fired = set(d.get("frame_deepening_fires", []))
        deepening_str = "".join(
            deepening_codes[det] if det in fired else "-"
            for det in (
                "temporal_scope", "stakeholder_map",
                "falsification_conditions",
            )
        )
        lines.append(
            f"| `{d['label']}` | {d['word_count'] or '?'} | {g} | {v} | "
            f"{present_str} | {absent_str} | {addr_str} | {deepening_str} |"
        )
    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(
        "Re-run via `python3 scripts/detector_empirics.py`. Determinism: "
        "the substrate is regex-only (no LLM); identical input produces "
        "identical output. Drift between this report and a future run "
        "either means (a) the corpus changed (added/removed/edited "
        "fixtures) or (b) a detector regex changed. The aggregate.json "
        "and per_document.json files in this directory are the "
        "machine-readable artifacts; this report is the human-readable "
        "summary derived from them."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    today = date.today().isoformat()
    default_out = REPO / "calibration" / "results" / f"detector_empirics_{today}"
    ap.add_argument(
        "--out", default=str(default_out),
        help=f"Output directory (default: {default_out})",
    )
    ap.add_argument(
        "--bin", default=None,
        help=("MCP server invocation. Default: `python3 <REPO>/mcp_server.py`. "
              "Pass an absolute path to a frame-check-mcp install to "
              "measure that artifact instead."),
    )
    args = ap.parse_args(argv)

    bin_args: list[str]
    if args.bin:
        bin_args = [args.bin]
    else:
        bin_args = [sys.executable, str(REPO / "mcp_server.py")]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = _enumerate_documents()
    if not docs:
        print("FATAL: no corpus documents found", file=sys.stderr)
        return 1
    print(f"running frame_check against {len(docs)} document(s)")

    proc = _spawn(bin_args)
    per_doc: list[dict] = []
    try:
        for label, path in docs:
            print(f"  {label}", flush=True)
            try:
                m = _measure(proc, label, path)
                per_doc.append(m)
            except Exception as e:
                print(f"    ERROR: {e}", file=sys.stderr)
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    agg = _aggregate(per_doc)
    (out_dir / "per_document.json").write_text(
        json.dumps(per_doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "aggregate.json").write_text(
        json.dumps(agg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(
        _markdown_report(per_doc, agg), encoding="utf-8",
    )

    print()
    print(f"wrote {out_dir}/")
    print(f"  REPORT.md       (human-readable summary)")
    print(f"  aggregate.json  (per-FVS / per-perspective firing rates)")
    print(f"  per_document.json (raw per-document measurements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
