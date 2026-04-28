"""Per-frame panel-rationale audit for all 9 default-mode frames across
mg_v1 + mg_v2.

Closes the "what I have NOT verified #5" caveat in
TP_RATIONALE_PATTERN_AUDIT_v1.md, which incorrectly stated panel labels
store binary `exhibits` fields without rationales. They actually store
{'exhibits': bool, 'reasoning': str} cells; this script consumes those
fields to test whether panel-positive cells use construct-correct
criteria or whether the panel itself is substrate-confused on the same
words the detector is.

For each frame and each panel-positive doc (3-of-4 include-self
consensus): emit a per-family rationale row. Ditto for panel-negative
docs the detector flagged (engine FPs) and panel-positive docs the
detector missed (engine FNs). The output is a hand-classification
surface paralleling tp_rationale_pattern_audit.md but at the panel
level rather than the detector level.

Reproducible: zero API calls. Reads panel labels from
fvs_eval/mixed_genre_{v1,v2}/labels/{family}_new_library_v{3,4}.json.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "fvs_eval" / "v4" / "grok_intra_rater_runs.json"
OUT = REPO / "fvs_eval" / "v4" / "panel_rationale_pattern_audit.md"

# Source file is ASCII-only by hygiene rule. Glyph keys are constructed
# from codepoint integers so the source contains no Unicode dashes,
# smart quotes, or ellipsis. The runtime dict is identical to a literal
# mapping; the indirection only affects how the source bytes look.
GLYPH_CODEPOINTS = [
    (0x2010, '-'),     # hyphen
    (0x2011, '-'),     # non-breaking hyphen
    (0x2012, '-'),     # figure dash
    (0x2013, '-'),     # en dash
    (0x2014, ' -- '),  # em dash
    (0x2015, '-'),     # horizontal bar
    (0x2018, "'"),     # left single quote
    (0x2019, "'"),     # right single quote / apostrophe
    (0x201A, "'"),     # single low-9 quote
    (0x201B, "'"),     # single high-reversed-9 quote
    (0x201C, '"'),     # left double quote
    (0x201D, '"'),     # right double quote
    (0x201E, '"'),     # double low-9 quote
    (0x201F, '"'),     # double high-reversed-9 quote
    (0x2026, '...'),   # ellipsis
]
GLYPH_REPLACEMENTS = [(chr(cp), repl) for cp, repl in GLYPH_CODEPOINTS]


def sanitize_glyphs(text: str) -> str:
    out = text
    for src, dst in GLYPH_REPLACEMENTS:
        out = out.replace(src, dst)
    return out

PANEL = ["claude_haiku_4_5", "gemini_3_1_flash_lite", "grok_4_1_fast", "gpt_5_4_mini"]
DEFAULT_MODE = ["FVS-001", "FVS-002", "FVS-007", "FVS-008", "FVS-009",
                "FVS-011", "FVS-012", "FVS-014", "FVS-015"]

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


def fam_cell(fam_labels, fam, doc, fid):
    cell = fam_labels[fam]["labels"][doc].get(fid)
    if cell is None:
        return None, ""
    if isinstance(cell, bool):
        return cell, ""
    if isinstance(cell, dict):
        return bool(cell.get("exhibits", False)), cell.get("reasoning", "")
    return None, ""


def load_engine(runs):
    out = {}
    for k, payload in runs.items():
        if "/" not in k:
            continue
        out[k] = {}
        for run_name in ("run_a", "run_b"):
            entries = payload.get(run_name, {}).get("entries", [])
            out[k][run_name] = {
                e["fvs_id"]: {
                    "exhibits": bool(e["exhibits"]),
                    "reasoning": e.get("reasoning", ""),
                }
                for e in entries
            }
    return out


def classify(corpus_id, cfg, engine):
    fam_labels = {}
    for fam in PANEL:
        p = cfg["labels_dir"] / f"{fam}_{cfg['label_suffix']}.json"
        fam_labels[fam] = json.loads(p.read_text())

    keys = sorted(k for k in engine if k.startswith(cfg["engine_prefix"]))
    doc_ids = sorted(k.split("/", 1)[1] for k in keys)

    out = {fid: {"panel_pos": [], "engine_fp": [], "engine_fn": []}
           for fid in DEFAULT_MODE}

    for fid in DEFAULT_MODE:
        for doc in doc_ids:
            full_key = f"{cfg['engine_prefix']}{doc}"
            votes = {}
            for fam in PANEL:
                ex, rsn = fam_cell(fam_labels, fam, doc, fid)
                votes[fam] = (ex, rsn)
            if any(v[0] is None for v in votes.values()):
                continue
            consensus_count = sum(1 for v in votes.values() if v[0] is True)
            consensus = consensus_count >= 3

            ra = engine[full_key]["run_a"].get(fid, {})
            rb = engine[full_key]["run_b"].get(fid, {})
            ra_ex = ra.get("exhibits")
            rb_ex = rb.get("exhibits")
            if ra_ex is None or rb_ex is None:
                continue
            engine_any_pos = ra_ex or rb_ex
            engine_all_pos = ra_ex and rb_ex

            entry = {
                "doc": doc,
                "consensus_count": consensus_count,
                "panel_votes": {fam: v[0] for fam, v in votes.items()},
                "panel_rationales": {fam: v[1] for fam, v in votes.items()},
                "engine": {
                    "run_a": {"exhibits": ra_ex,
                              "reasoning": ra.get("reasoning", "")},
                    "run_b": {"exhibits": rb_ex,
                              "reasoning": rb.get("reasoning", "")},
                },
            }

            if consensus:
                out[fid]["panel_pos"].append(entry)
            elif engine_any_pos and not consensus:
                out[fid]["engine_fp"].append(entry)
            elif consensus and not engine_any_pos:
                out[fid]["engine_fn"].append(entry)

    return out


def render_frame_section(fid, per_corpus, lines):
    lines.append(f"\n## {fid}\n")
    for cid, data in per_corpus.items():
        lines.append(f"\n### {fid} {cid} cell-summary\n")
        lines.append(f"- panel-consensus-positive (3-of-4): "
                     f"n={len(data['panel_pos'])}")
        lines.append(f"- engine-positive panel-no-consensus: "
                     f"n={len(data['engine_fp'])}")
        lines.append(f"- panel-consensus-positive engine-negative: "
                     f"n={len(data['engine_fn'])}")
        lines.append("")

        for bucket_name, label in (
            ("panel_pos", "Panel-consensus-positive (TPs at panel level)"),
            ("engine_fp", "Engine-positive panel-no-consensus (engine FPs)"),
            ("engine_fn", "Panel-consensus-positive engine-negative (engine FNs)"),
        ):
            entries = data[bucket_name]
            if not entries:
                continue
            lines.append(f"\n#### {fid} {cid} {label} (n={len(entries)})\n")
            for e in sorted(entries, key=lambda x: x["doc"]):
                lines.append(f"\n**{e['doc']}** "
                             f"(consensus_count={e['consensus_count']})\n")
                lines.append("| family | exh | reasoning |")
                lines.append("|---|---|---|")
                for fam in PANEL:
                    ex = e["panel_votes"][fam]
                    rs = sanitize_glyphs(e["panel_rationales"][fam]).replace(
                        "|", "\\|").replace("\n", " ")[:320]
                    lines.append(f"| {fam} | {ex} | {rs} |")
                ra = e["engine"]["run_a"]
                rb = e["engine"]["run_b"]
                ra_r = sanitize_glyphs(ra["reasoning"]).replace(
                    "|", "\\|").replace("\n", " ")[:320]
                rb_r = sanitize_glyphs(rb["reasoning"]).replace(
                    "|", "\\|").replace("\n", " ")[:320]
                lines.append(f"| ENGINE run_a | {ra['exhibits']} | {ra_r} |")
                lines.append(f"| ENGINE run_b | {rb['exhibits']} | {rb_r} |")


def main():
    runs = json.loads(RUNS.read_text())
    engine = load_engine(runs)

    lines = []
    lines.append("# Per-frame panel-rationale audit "
                 "(all 9 default-mode frames)\n")
    lines.append("Auto-generated by `scripts/audit_panel_rationale_patterns.py`. "
                 "Sources: panel labels at "
                 "`fvs_eval/mixed_genre_{v1,v2}/labels/{family}_new_library_v{3,4}.json` "
                 "(`exhibits` + `reasoning` fields); engine outputs at "
                 "`fvs_eval/v4/grok_intra_rater_runs.json`. Consensus rule: "
                 "3-of-4 majority (include-self).\n")
    lines.append("Closes the 'what I have NOT verified #5' gap in "
                 "`TP_RATIONALE_PATTERN_AUDIT_v1.md` v1 (which mistakenly "
                 "claimed panel rationales were unavailable).\n")
    lines.append("Each frame section dumps panel rationales (4 families) "
                 "side-by-side with engine rationales (run_a, run_b) for "
                 "three buckets per corpus: panel-consensus-positive docs, "
                 "engine-only-positive docs, panel-only-positive docs. "
                 "Hand-classification surface for whether panel families "
                 "co-apply the same substrate-confused criterion as the "
                 "detector or apply distinguishing construct criteria.\n")

    for fid in DEFAULT_MODE:
        per_corpus = {}
        for cid, cfg in CORPUS_CFG.items():
            per_corpus[cid] = classify(cid, cfg, engine)[fid]
        render_frame_section(fid, per_corpus, lines)

    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}")
    print()
    print("Per-frame cell counts (panel-pos / engine-fp / engine-fn):")
    for fid in DEFAULT_MODE:
        per_corpus = {cid: classify(cid, cfg, engine)[fid]
                      for cid, cfg in CORPUS_CFG.items()}
        for cid in CORPUS_CFG:
            d = per_corpus[cid]
            print(f"  {fid} {cid}: panel_pos={len(d['panel_pos'])} "
                  f"engine_fp={len(d['engine_fp'])} "
                  f"engine_fn={len(d['engine_fn'])}")


if __name__ == "__main__":
    main()
