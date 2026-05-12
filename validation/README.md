# Validation studies

Pre-registered studies that test Frame Check's load-bearing claims empirically. Each study lives in its own subdirectory with PROTOCOL + harness + rubric + (when run) results.

| Study | Tests | Status | Protocol | Harness | Results |
|---|---|---|---|---|---|
| `wedge_behavior/` | Load-bearing shift in agent responses when `frame_check` is invoked vs. not | Pilot complete (N=2, 2026-05-12); main study (N=10) pending operator decision | [`PROTOCOL_v1.md`](wedge_behavior/PROTOCOL_v1.md) | [`run_pilot.py`](wedge_behavior/run_pilot.py) + [`run_arms.py`](wedge_behavior/run_arms.py) | [`results_v1/RESULTS_v1.md`](wedge_behavior/results_v1/RESULTS_v1.md) |
| `baseline_comparison/` | Information advantage over a frontier LLM prompted for framing analysis | Pre-registered; pilot pending operator authorization | [`PROTOCOL_v1.md`](baseline_comparison/PROTOCOL_v1.md) | [`run_baseline.py`](baseline_comparison/run_baseline.py) | — |
| `decision_readiness/` | Pre-existing decision-readiness corpus + results | Reference artifacts (bundled in the wheel as `framecheck_mcp/validation/decision_readiness/`) | — | — | — |

`wedge_behavior` pilot finding: load-bearing shift = YES on both pilot documents (one recommendation-shaped, one opinion-shaped). Three rubric calibration findings surfaced for v2 before main study. See [`results_v1/RESULTS_v1.md`](wedge_behavior/results_v1/RESULTS_v1.md) for the per-item outcomes table, calibration findings, honest scope, and operator review checklist. Pilot is descriptive only per pre-registered analysis; the N=10 main study is the hypothesis test under PROTOCOL_v1's pre-registered decision rule.

`baseline_comparison` pilot still pending. Same shape: harness ready, protocol locked, awaiting operator authorization for sample selection + execution.

`ROADMAP.md` names "validation pre-registration first execution" — the wedge_behavior pilot above closes that item at the pilot level; main-study execution is the next gate.
