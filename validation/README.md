# Validation studies

Pre-registered studies that test Frame Check's load-bearing claims empirically. Each study lives in its own subdirectory with PROTOCOL + harness + rubric + (when run) results.

| Study | Tests | Status | Protocol | Harness |
|---|---|---|---|---|
| `wedge_behavior/` | Load-bearing shift in agent responses when `frame_check` is invoked vs. not | Pipeline smoke test executed 2026-05-12 (operator-internal); main study under PROTOCOL_v2 pending external-source documents + independent raters | [`PROTOCOL_v1.md`](wedge_behavior/PROTOCOL_v1.md), [`STATUS.md`](wedge_behavior/STATUS.md) | [`run_pilot.py`](wedge_behavior/run_pilot.py) + [`run_arms.py`](wedge_behavior/run_arms.py) |
| `baseline_comparison/` | Information advantage over a frontier LLM prompted for framing analysis | Pre-registered; pilot pending operator authorization (see `wedge_behavior/STATUS.md` for the methodological constraints that apply equally here) | [`PROTOCOL_v1.md`](baseline_comparison/PROTOCOL_v1.md) | [`run_baseline.py`](baseline_comparison/run_baseline.py) |
| `decision_readiness/` | Pre-existing decision-readiness corpus + results | Reference artifacts (bundled in the wheel as `framecheck_mcp/validation/decision_readiness/`) | — | — |

`wedge_behavior` shipped the pre-registered protocol + harness end-to-end; the 2026-05-12 pipeline smoke test verified the pipeline works and produced three rubric calibration findings for PROTOCOL_v2. See [`wedge_behavior/STATUS.md`](wedge_behavior/STATUS.md) for the calibration findings + the path to validation evidence (externally-sourced documents + independent raters).

`baseline_comparison` is on the same path: protocol + harness ready; methodologically credible execution awaits the same external sourcing + independent-rater conditions.

`ROADMAP.md` names "validation pre-registration first execution" — the harness-end-to-end smoke test verified the pipeline; the load-bearing main study under PROTOCOL_v2 is the next gate.
