# Validation studies

Pre-registered studies that test Frame Check's load-bearing claims empirically. Each study lives in its own subdirectory with PROTOCOL + harness + rubric + (when run) results.

| Study | Tests | Status | Protocol | Harness |
|---|---|---|---|---|
| `wedge_behavior/` | Load-bearing shift in agent responses when `frame_check` is invoked vs. not | Pre-registered; pilot pending operator authorization | [`PROTOCOL_v1.md`](wedge_behavior/PROTOCOL_v1.md) | [`run_pilot.py`](wedge_behavior/run_pilot.py) |
| `baseline_comparison/` | Information advantage over a frontier LLM prompted for framing analysis | Pre-registered; pilot pending operator authorization | [`PROTOCOL_v1.md`](baseline_comparison/PROTOCOL_v1.md) | [`run_baseline.py`](baseline_comparison/run_baseline.py) |
| `decision_readiness/` | Pre-existing decision-readiness corpus + results | Reference artifacts (bundled in the wheel as `framecheck_mcp/validation/decision_readiness/`) | — | — |

Both pre-registered studies are blocked on operator-handed execution (sample document selection + LLM invocation under authenticated key + rater pool). The protocols + harnesses + rubrics are ready; the operator's hands close the loop.

`ROADMAP.md` names "validation pre-registration first execution" as the only v1.0 contract item still deferred from v1.0.x.
