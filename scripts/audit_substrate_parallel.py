"""Substrate parallel audit: run the deterministic regex/structural FVS
detection (construct #7 per CONSTRUCT_VALIDITY_AUDIT_v1.md) against the
same mg_v1 + mg_v2 corpora used for the V4.2 LLM-judge audit, and
compute per-frame agreement with the 4-family panel consensus.

Closes the "shipped-vs-evaluated" symmetry gap surfaced in
TP_RATIONALE_PATTERN_AUDIT_v1.md v1.1 §7 #1: the V4.2 LLM-judge audit
covers the evaluation surface (`fvs_eval/v4/v4_2_engine.py`); this
audit covers the actually-shipping surface (`framing.py` analyzers
plus `frame_library.py::suggest_frames` rules), which is what the
0.8.1 PyPI wheel runs.

Method (zero API calls, byte-deterministic):
1. For each doc in fvs_eval/mixed_genre_{v1,v2}/corpus/*.txt: run
   detect_coverage, temporal_orientation, detect_voice,
   detect_epistemic_basis from framing.py; pass to
   suggest_frames(coverage, voice, temporal, epistemic, text=text).
2. Map suggest_frames output (a list of dicts each with fvs_id) to a
   per-doc per-frame True/False fire matrix.
3. Compare to panel consensus (3-of-4 include-self) using the same
   panel labels the V4.2 LLM-judge audit consumed.
4. Compute per-frame TP/FP/FN/TN, precision, recall, f1, macro-F1.
5. Produce per-frame fire-pattern dump for hand-classification of
   substrate behavior parallel to the LLM-judge audit's
   LEXICAL_CAPTURE / PROCESS_NARRATIVE_MISAPPLY / CONSTRUCT_CORRECT
   surface (substrate uses different mechanisms; classification
   surface adapted at synthesis time).

Output: fvs_eval/v4/substrate_parallel_audit.md +
fvs_eval/v4/substrate_parallel_audit.json (deterministic).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from framing import (  # noqa: E402
    detect_coverage,
    detect_epistemic_basis,
    detect_voice,
    temporal_orientation,
)
from frame_library import suggest_frames  # noqa: E402

OUT_MD = REPO / "fvs_eval" / "v4" / "substrate_parallel_audit.md"
OUT_JSON = REPO / "fvs_eval" / "v4" / "substrate_parallel_audit.json"

PANEL = ["claude_haiku_4_5", "gemini_3_1_flash_lite",
         "grok_4_1_fast", "gpt_5_4_mini"]

# 9 default-mode frames matching the V4.2 LLM-judge audit scope.
# FVS-001 is RETIRED in the substrate (per frame_library.py L339-L349):
# the rule was removed 2026-04-18 because v1 signal substrate could not
# distinguish FVS-001 target cases from similarly-shaped non-cases.
# This audit reports FVS-001 substrate behavior as "RETIRED" rather
# than running a non-existent rule; keeps the comparison panel-aligned.
DEFAULT_MODE = ["FVS-001", "FVS-002", "FVS-007", "FVS-008", "FVS-009",
                "FVS-011", "FVS-012", "FVS-014", "FVS-015"]

CORPUS_CFG = {
    "mg_v1": {
        "corpus_dir": REPO / "fvs_eval" / "mixed_genre_v1" / "corpus",
        "labels_dir": REPO / "fvs_eval" / "mixed_genre_v1" / "labels",
        "label_suffix": "new_library_v3",
    },
    "mg_v2": {
        "corpus_dir": REPO / "fvs_eval" / "mixed_genre_v2" / "corpus",
        "labels_dir": REPO / "fvs_eval" / "mixed_genre_v2" / "labels",
        "label_suffix": "new_library_v4",
    },
}


def load_panel_labels(cfg):
    out = {}
    for fam in PANEL:
        p = cfg["labels_dir"] / f"{fam}_{cfg['label_suffix']}.json"
        out[fam] = json.loads(p.read_text())
    return out


def panel_consensus_positive(panel_labels, doc, fid, k=3):
    """Return (votes_dict, consensus_count, consensus_bool) for a
    given doc + frame. consensus is True iff at least k of 4 panel
    families voted exhibits=True. Returns (None, None, None) if any
    family lacks the cell (skip)."""
    votes = {}
    for fam in PANEL:
        cell = panel_labels[fam]["labels"].get(doc, {}).get(fid)
        if cell is None:
            return None, None, None
        if isinstance(cell, bool):
            votes[fam] = cell
        elif isinstance(cell, dict):
            votes[fam] = bool(cell.get("exhibits", False))
        else:
            return None, None, None
    consensus_count = sum(1 for v in votes.values() if v)
    return votes, consensus_count, consensus_count >= k


def run_substrate_on_doc(text):
    """Run the full substrate analyzer chain on one document; return a
    dict mapping fvs_id -> True for every frame the substrate fired
    on. Frames not in the dict are implicit False."""
    coverage = detect_coverage(text)
    voice = detect_voice(text)
    temporal = temporal_orientation(text)
    epistemic = detect_epistemic_basis(text)
    suggestions = suggest_frames(
        coverage=coverage,
        voice=voice,
        temporal=temporal,
        epistemic=epistemic,
        text=text,
    )
    return {s["fvs_id"]: True for s in suggestions}


def compute_per_frame(corpus_id, cfg):
    panel_labels = load_panel_labels(cfg)
    docs = sorted(p.stem for p in cfg["corpus_dir"].glob("*.txt"))

    # Run substrate on every doc, collect per-doc per-frame fire.
    substrate_per_doc = {}
    for doc in docs:
        text = (cfg["corpus_dir"] / f"{doc}.txt").read_text()
        substrate_per_doc[doc] = run_substrate_on_doc(text)

    # For each frame, compute TP/FP/FN/TN against panel consensus.
    per_frame = {}
    for fid in DEFAULT_MODE:
        if fid == "FVS-001":
            per_frame[fid] = {"status": "RETIRED_IN_SUBSTRATE",
                              "tp": 0, "fp": 0, "fn": 0, "tn": 0,
                              "precision": None, "recall": None,
                              "f1": None,
                              "consensus_positives": 0,
                              "substrate_positives": 0,
                              "tp_docs": [], "fp_docs": [],
                              "fn_docs": [], "tn_docs": []}
            for doc in docs:
                _, _, consensus = panel_consensus_positive(
                    panel_labels, doc, fid)
                if consensus:
                    per_frame[fid]["consensus_positives"] += 1
                    per_frame[fid]["fn_docs"].append({"doc": doc})
                    per_frame[fid]["fn"] += 1
                else:
                    per_frame[fid]["tn"] += 1
            continue

        tp = fp = fn = tn = 0
        cp = sp = 0
        tp_docs = []
        fp_docs = []
        fn_docs = []
        tn_docs = []
        for doc in docs:
            votes, cnt, consensus = panel_consensus_positive(
                panel_labels, doc, fid)
            if votes is None:
                continue
            substrate_pos = substrate_per_doc[doc].get(fid, False)
            if consensus:
                cp += 1
            if substrate_pos:
                sp += 1
            entry = {"doc": doc, "panel_count": cnt,
                     "panel_votes": {k: bool(v) for k, v in votes.items()},
                     "substrate_pos": bool(substrate_pos)}
            if substrate_pos and consensus:
                tp += 1
                tp_docs.append(entry)
            elif substrate_pos and not consensus:
                fp += 1
                fp_docs.append(entry)
            elif not substrate_pos and consensus:
                fn += 1
                fn_docs.append(entry)
            else:
                tn += 1
                tn_docs.append(entry)

        # Degenerate cases:
        # - Both sides empty (no panel positives, no substrate positives):
        #   frame is truly absent from the corpus; precision/recall/f1
        #   are mathematically undefined; report None.
        # - Substrate empty but panel positives exist: precision is
        #   undefined (no substrate positives to score), recall = 0,
        #   f1 = 0 (substrate completely missed the frame).
        # - Panel empty but substrate fires: recall is undefined,
        #   precision = 0 (all substrate fires are FPs), f1 = 0
        #   (substrate completely fired into nothing the panel saw).
        # - Both non-empty but tp=0: precision=0, recall=0, f1=0
        #   (complete miss, not unmeasurable).
        if (tp + fp) == 0 and (tp + fn) == 0:
            precision = None
            recall = None
            f1 = None
        elif (tp + fp) == 0:
            precision = None
            recall = 0.0
            f1 = 0.0
        elif (tp + fn) == 0:
            precision = 0.0
            recall = None
            f1 = 0.0
        else:
            precision = tp / (tp + fp)
            recall = tp / (tp + fn)
            if (precision + recall) > 0:
                f1 = 2 * precision * recall / (precision + recall)
            else:
                f1 = 0.0

        per_frame[fid] = {
            "status": "active",
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 4) if precision is not None
                else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "consensus_positives": cp,
            "substrate_positives": sp,
            "tp_docs": tp_docs, "fp_docs": fp_docs,
            "fn_docs": fn_docs, "tn_docs": tn_docs,
        }
    return per_frame, docs


def macro_f1(per_frame, exclude=None):
    exclude = exclude or set()
    f1s = []
    for fid, d in per_frame.items():
        if fid in exclude:
            continue
        if d.get("status") == "RETIRED_IN_SUBSTRATE":
            continue
        if d["f1"] is not None:
            f1s.append(d["f1"])
        else:
            # Convention: F1=0 when both p and r are 0/undefined and a
            # frame had panel positives the substrate missed; F1=undefined
            # when there were no panel positives AND no substrate positives
            # (frame is empty-class; skip from macro).
            if d["consensus_positives"] == 0 and d["substrate_positives"] == 0:
                continue
            f1s.append(0.0)
    return sum(f1s) / len(f1s) if f1s else None


def render(per_corpus_data):
    lines = []
    lines.append("# Substrate parallel audit (regex/structural FVS detection)\n")
    lines.append(
        "Auto-generated by `scripts/audit_substrate_parallel.py`. Sources: "
        "corpus docs at `fvs_eval/mixed_genre_{v1,v2}/corpus/*.txt`, "
        "panel labels at "
        "`fvs_eval/mixed_genre_{v1,v2}/labels/*_new_library_v{3,4}.json`. "
        "Substrate detection: `framing.py` analyzers + "
        "`frame_library.py::suggest_frames` rules (the actually-shipping "
        "detection layer in the 0.8.1 PyPI wheel; construct #7 per "
        "`CONSTRUCT_VALIDITY_AUDIT_v1.md`). Consensus rule: 3-of-4 "
        "majority (include-self) on the 4-family fast-tier panel "
        "(Haiku 4.5 / Gemini 3.1 flash lite / Grok 4.1 fast / GPT-5.4 "
        "mini) using the same labels as the V4.2 LLM-judge audit.\n")
    lines.append(
        "FVS-001 is RETIRED in the substrate per `frame_library.py` "
        "L339-L349 (2026-04-18 retirement; v1 signal substrate could "
        "not distinguish target cases from similarly-shaped non-cases). "
        "Reported as RETIRED_IN_SUBSTRATE rather than running a "
        "non-existent rule; consensus_positives counted but treated as "
        "FNs structurally.\n")

    # Cross-frame summary table per corpus
    for corpus_id, (per_frame, docs) in per_corpus_data.items():
        lines.append(f"\n## {corpus_id} (n={len(docs)})\n")
        lines.append("\n### Per-frame summary\n")
        lines.append(
            "| frame | status | TP | FP | FN | TN | precision | "
            "recall | f1 | consensus_pos | substrate_pos |")
        lines.append(
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for fid in DEFAULT_MODE:
            d = per_frame[fid]
            p = d["precision"]
            r = d["recall"]
            f = d["f1"]
            lines.append(
                f"| {fid} | {d['status']} | {d['tp']} | {d['fp']} | "
                f"{d['fn']} | {d['tn']} | "
                f"{p if p is not None else 'n/a'} | "
                f"{r if r is not None else 'n/a'} | "
                f"{f if f is not None else 'n/a'} | "
                f"{d['consensus_positives']} | "
                f"{d['substrate_positives']} |")

        m_full = macro_f1(per_frame)
        m_no_001 = macro_f1(per_frame, exclude={"FVS-001"})
        lines.append("")
        lines.append(
            f"**Macro-F1 (full, 9 frames; FVS-001 retired counts as "
            f"F1=0 under panel-positive presence):** "
            f"{m_full:.4f}" if m_full is not None else "**Macro-F1: n/a**")
        lines.append("")
        lines.append(
            f"**Macro-F1 (excluding retired FVS-001, 8 active frames):** "
            f"{m_no_001:.4f}" if m_no_001 is not None else
            "**Macro-F1 excl FVS-001: n/a**")
        lines.append("")

        # Per-frame fire-pattern detail
        for fid in DEFAULT_MODE:
            d = per_frame[fid]
            if d["status"] == "RETIRED_IN_SUBSTRATE":
                lines.append(
                    f"\n### {corpus_id} {fid} (RETIRED_IN_SUBSTRATE)\n")
                lines.append(
                    f"Substrate has no rule for this frame "
                    f"(retired 2026-04-18). Panel consensus_positives = "
                    f"{d['consensus_positives']}; all are structural FNs. "
                    f"FN docs: " +
                    ", ".join(e["doc"] for e in d["fn_docs"]))
                continue

            lines.append(f"\n### {corpus_id} {fid}\n")
            for bucket_name, label in (
                ("tp_docs", "TPs (substrate-fire + panel-consensus)"),
                ("fp_docs", "FPs (substrate-fire, panel-no-consensus)"),
                ("fn_docs", "FNs (panel-consensus, substrate-no-fire)"),
            ):
                docs_list = d[bucket_name]
                if not docs_list:
                    continue
                lines.append(f"\n#### {label} (n={len(docs_list)})\n")
                lines.append("| doc | panel_count | panel_votes |")
                lines.append("|---|---:|---|")
                for e in docs_list:
                    votes_str = ", ".join(
                        f"{k.split('_')[0]}={'T' if v else 'F'}"
                        for k, v in e["panel_votes"].items())
                    lines.append(
                        f"| {e['doc']} | {e['panel_count']} | "
                        f"{votes_str} |")

    return "\n".join(lines)


def main():
    per_corpus_data = {}
    for corpus_id, cfg in CORPUS_CFG.items():
        per_frame, docs = compute_per_frame(corpus_id, cfg)
        per_corpus_data[corpus_id] = (per_frame, docs)

    out_md = render(per_corpus_data)
    OUT_MD.write_text(out_md)

    out_json = {
        "schema": "substrate_parallel_audit_v1",
        "panel": PANEL,
        "default_mode_frames": DEFAULT_MODE,
        "by_corpus": {},
    }
    for corpus_id, (per_frame, docs) in per_corpus_data.items():
        out_json["by_corpus"][corpus_id] = {
            "n_docs": len(docs),
            "doc_ids": docs,
            "per_frame": per_frame,
            "macro_f1_full": macro_f1(per_frame),
            "macro_f1_excl_fvs001": macro_f1(per_frame,
                                              exclude={"FVS-001"}),
        }
    OUT_JSON.write_text(json.dumps(out_json, indent=2, sort_keys=True))

    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print()
    for corpus_id, (per_frame, docs) in per_corpus_data.items():
        m_full = macro_f1(per_frame)
        m_no_001 = macro_f1(per_frame, exclude={"FVS-001"})
        print(f"{corpus_id} (n={len(docs)}):")
        print(f"  macro-F1 (full)             = {m_full}")
        print(f"  macro-F1 (excl retired 001) = {m_no_001}")
        for fid in DEFAULT_MODE:
            d = per_frame[fid]
            p = d["precision"]
            r = d["recall"]
            f = d["f1"]
            print(
                f"  {fid}: status={d['status']} tp={d['tp']} fp={d['fp']} "
                f"fn={d['fn']} cp={d['consensus_positives']} "
                f"sp={d['substrate_positives']} "
                f"p={p} r={r} f1={f}")


if __name__ == "__main__":
    main()
