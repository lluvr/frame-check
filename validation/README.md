# Validation studies

Pre-registered studies that test Frame Check's load-bearing claims empirically. Each study lives in its own subdirectory with PROTOCOL + harness + rubric + (when run) results.

| Study | Tests | Status | Protocol | Harness |
|---|---|---|---|---|
| `wedge_behavior/` | Load-bearing shift in agent responses when `frame_check` is invoked vs. not | Pipeline smoke test executed 2026-05-12 (operator-internal); main study under PROTOCOL_v2 pending external-source documents + independent raters | [`PROTOCOL_v1.md`](wedge_behavior/PROTOCOL_v1.md), [`STATUS.md`](wedge_behavior/STATUS.md) | [`run_pilot.py`](wedge_behavior/run_pilot.py) + [`run_arms.py`](wedge_behavior/run_arms.py) |
| `baseline_comparison/` | Information advantage over a frontier LLM prompted for framing analysis (H1, H2, H3) | H3 (reproducibility) measurement complete on N=1, [results published](baseline_comparison/results_h3/REPORT.md); H1, H2 pending external-source documents + independent raters | [`PROTOCOL_v1.md`](baseline_comparison/PROTOCOL_v1.md), [`STATUS.md`](baseline_comparison/STATUS.md) | [`run_baseline.py`](baseline_comparison/run_baseline.py) + [`analyze_h3.py`](baseline_comparison/analyze_h3.py) |
| `decision_readiness/` | Pre-existing decision-readiness corpus + results | Reference artifacts (bundled in the wheel as `framecheck_mcp/validation/decision_readiness/`) | — | — |
| (helpers) | External-document sourcing for the main study | Operator-runnable; standardizes URL + retrieval timestamp + SHA capture and validates inclusion criteria | — | [`external_doc_sourcer.py`](external_doc_sourcer.py) |

`wedge_behavior` shipped the pre-registered protocol + harness end-to-end; the 2026-05-12 pipeline smoke test verified the pipeline works and produced three rubric calibration findings for PROTOCOL_v2. See [`wedge_behavior/STATUS.md`](wedge_behavior/STATUS.md) for the calibration findings + the path to validation evidence (externally-sourced documents + independent raters).

`baseline_comparison` published H3 (reproducibility) at N=1: Frame Check Jaccard distance = 0.0; LLM baseline (Sonnet 4.6 @ T=0.7) Jaccard distance = 0.66. Pre-registered direction confirmed. Mechanical measurement; no rater confound. H1 + H2 await external sourcing + raters per `STATUS.md`.

`external_doc_sourcer.py` is the operator-runnable helper for sourcing main-study documents from outside the operator's authoring reach. Takes URL + text, validates against PROTOCOL inclusion criteria, emits structured corpus entry with provenance metadata (URL, SHA, retrieval timestamp, word count). Removes the operator-authoring confound at sourcing time.

`ROADMAP.md` names "validation pre-registration first execution" — the harness-end-to-end smoke test verified the pipeline; H3 published; the load-bearing H1+H2 main study under PROTOCOL_v2 is the next gate.
