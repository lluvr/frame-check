"""Per-frame ship-readiness diagnostic for FVS-007 (over-fire) and FVS-001
(low-recall) across mg_v1 and mg_v2, both runs, both consensus modes.

For each (corpus, frame, run, consensus) cell, enumerates the doc IDs in
each error class (false positive for FVS-007; false negative for FVS-001),
records the panel vote pattern (which families voted exhibits=True), and
emits a deterministic JSON report.

Reproducible: zero API calls. Reads engine outputs from
fvs_eval/v4/grok_intra_rater_runs.json and panel labels from
fvs_eval/mixed_genre_{v1,v2}/labels/{family}_new_library_v{3,4}.json.

Output: fvs_eval/v4/per_frame_007_001_diagnostic.json
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "fvs_eval" / "v4" / "grok_intra_rater_runs.json"
OUT = REPO / "fvs_eval" / "v4" / "per_frame_007_001_diagnostic.json"

PANEL = ["claude_haiku_4_5", "gemini_3_1_flash_lite", "grok_4_1_fast", "gpt_5_4_mini"]
DETECTOR_FAMILY = "grok_4_1_fast"
TARGET_FRAMES = ["FVS-001", "FVS-007"]

CORPUS_CFG = {
    "mg_v1": {
        "labels_dir": REPO / "fvs_eval" / "mixed_genre_v1" / "labels",
        "label_suffix": "new_library_v3",
        "engine_prefix": "mixed_genre_v1/",
    },
    "mg_v2": {
        "labels_dir": REPO / "fvs_eval" / "mixed_genre_v2" / "labels",
        "label_suffix": "new_library_v4",
        "engine_prefix": "mixed_genre_v2/",
    },
}


def fam_get(fam_labels, fam, doc, fid):
    cell = fam_labels[fam]["labels"][doc].get(fid)
    if cell is None:
        return None
    if isinstance(cell, bool):
        return cell
    if isinstance(cell, dict):
        return bool(cell.get("exhibits", False))
    return None


def diagnose_one_corpus(corpus_id, cfg, engine_runs):
    keys = sorted(k for k in engine_runs if k.startswith(cfg["engine_prefix"]))
    if not keys:
        raise RuntimeError(f"No {cfg['engine_prefix']} keys in engine runs")

    engine = {"run_a": {}, "run_b": {}}
    for k in keys:
        doc_id = k.split("/", 1)[1]
        for run_name in ("run_a", "run_b"):
            entries = engine_runs[k][run_name]["entries"]
            engine[run_name][doc_id] = {e["fvs_id"]: bool(e["exhibits"]) for e in entries}

    fam_labels = {}
    for fam in PANEL:
        p = cfg["labels_dir"] / f"{fam}_{cfg['label_suffix']}.json"
        fam_labels[fam] = json.loads(p.read_text())

    doc_ids = sorted(engine["run_a"].keys())
    loo_panel = [f for f in PANEL if f != DETECTOR_FAMILY]

    cells = {}
    for run_name in ("run_a", "run_b"):
        for cons_label, ref_panel, k_required in (
            ("include_self_3of4", PANEL, 3),
            ("leave_one_out_2of3", loo_panel, 2),
        ):
            cell = {"reference_panel": ref_panel, "consensus_k": k_required, "frames": {}}
            for fid in TARGET_FRAMES:
                fps = []
                fns = []
                tps = []
                tns = []
                for doc in doc_ids:
                    votes = {fam: fam_get(fam_labels, fam, doc, fid) for fam in ref_panel}
                    if any(v is None for v in votes.values()):
                        continue
                    consensus = sum(votes.values()) >= k_required
                    det = engine[run_name][doc].get(fid)
                    if det is None:
                        continue
                    rec = {
                        "doc": doc,
                        "panel_votes": {fam: bool(v) for fam, v in votes.items()},
                        "consensus_count": sum(votes.values()),
                    }
                    if det and consensus:
                        tps.append(rec)
                    elif det and not consensus:
                        fps.append(rec)
                    elif not det and consensus:
                        fns.append(rec)
                    else:
                        tns.append(rec)
                cell["frames"][fid] = {
                    "n_tp": len(tps), "n_fp": len(fps),
                    "n_fn": len(fns), "n_tn": len(tns),
                    "false_positives": fps,
                    "false_negatives": fns,
                    "true_positives": tps,
                }
            cells[f"{run_name}__{cons_label}"] = cell

    fp_doc_union = {}
    fn_doc_union = {}
    for fid in TARGET_FRAMES:
        fp_set = {}
        fn_set = {}
        for cell_key, cell in cells.items():
            for rec in cell["frames"][fid]["false_positives"]:
                fp_set.setdefault(rec["doc"], []).append(cell_key)
            for rec in cell["frames"][fid]["false_negatives"]:
                fn_set.setdefault(rec["doc"], []).append(cell_key)
        fp_doc_union[fid] = {d: sorted(v) for d, v in sorted(fp_set.items())}
        fn_doc_union[fid] = {d: sorted(v) for d, v in sorted(fn_set.items())}

    return {
        "n_docs": len(doc_ids),
        "doc_ids": doc_ids,
        "cells": cells,
        "fp_doc_union": fp_doc_union,
        "fn_doc_union": fn_doc_union,
    }


def main():
    engine_runs = json.loads(RUNS.read_text())
    report = {
        "schema": "per_frame_007_001_diagnostic_v1",
        "panel": PANEL,
        "detector_family": DETECTOR_FAMILY,
        "target_frames": TARGET_FRAMES,
        "by_corpus": {
            cid: diagnose_one_corpus(cid, cfg, engine_runs)
            for cid, cfg in CORPUS_CFG.items()
        },
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"Wrote {OUT}")
    for cid, data in report["by_corpus"].items():
        print(f"\n=== {cid} (n_docs={data['n_docs']}) ===")
        for fid in TARGET_FRAMES:
            fps = data["fp_doc_union"][fid]
            fns = data["fn_doc_union"][fid]
            print(f"  {fid}: fp_docs={len(fps)}, fn_docs={len(fns)}")
            if fps:
                print(f"    FP docs (any cell): {list(fps.keys())}")
            if fns:
                print(f"    FN docs (any cell): {list(fns.keys())}")


if __name__ == "__main__":
    main()
