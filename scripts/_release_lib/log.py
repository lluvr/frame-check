"""Append-only release log.

Each release writes a per-version log file at `.release/v{N}.log`. Format is
one event per line, ISO-8601 UTC timestamp + agent ID + event type + free
text. Append-only; the orchestrator never rewrites prior lines. The log is
the audit trail when something goes wrong.

Log line format (whitespace-separated columns, free text after column 4):

  ISO8601_UTC  AGENT_ID  EVENT  STEP  ...detail...

Events:

  START          orchestration started for this version
  STEP_BEGIN     step about to execute
  STEP_OK        step completed successfully (with optional duration)
  STEP_FAIL      step failed (detail = exception class + message)
  STEP_SKIP      step skipped (already completed in prior run)
  GATE_PASS      operator approved the public-actions gate
  GATE_DENY      operator declined the public-actions gate
  FORCE_CLEAR    operator force-cleared a lock or state (detail = reason)
  START_AT       release launched with --start-at; names target step + the
                 list of pre-skipped step IDs (one event per release, not
                 one per pre-skipped step, to keep the log readable)
  END_OK         orchestration completed successfully
  END_FAIL       orchestration ended in failure (detail = step that failed)

The log lives in `.release/` which is gitignored; logs do not propagate
across machines. Operator may copy logs out for incident review.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path


class ReleaseLog:
    """Append-only log writer for a single release version."""

    def __init__(self, release_dir: Path, version: str, agent_id: str) -> None:
        self.release_dir = release_dir
        self.version = version
        self.agent_id = agent_id
        self.log_path = release_dir / f"v{version}.log"

    def _write(self, event: str, step: str, detail: str = "") -> None:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # Multi-line detail (e.g. a PreflightError carrying a list of
        # uncommitted files) would break the "one event per line"
        # contract that `tail()` and external log-aggregation tools
        # rely on. Collapse internal newlines to ` | ` and CRs to a
        # space; the original message is reconstructible by anyone
        # reading the log line.
        flat_detail = detail.replace("\r\n", "\n").replace("\r", " ")
        flat_detail = flat_detail.replace("\n", " | ")
        line = f"{ts}  {self.agent_id}  {event}  {step}"
        if flat_detail:
            line += f"  {flat_detail}"
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def start(self) -> None:
        self._write("START", "-", f"pid={os.getpid()}")

    def step_begin(self, step: str) -> None:
        self._write("STEP_BEGIN", step)

    def step_ok(self, step: str, duration_s: float | None = None) -> None:
        detail = f"duration={duration_s:.2f}s" if duration_s is not None else ""
        self._write("STEP_OK", step, detail)

    def step_fail(self, step: str, exc: BaseException) -> None:
        self._write("STEP_FAIL", step, f"{type(exc).__name__}: {exc}")

    def step_skip(self, step: str, reason: str = "already complete in prior run") -> None:
        """Record that a step was skipped.

        The default reason ("already complete in prior run") is used when a
        resume invocation finds the step already in `state.completed_steps`.
        Pass an explicit reason for conditional steps that did not run because
        a flag was not set (e.g. `"--testpypi not set"`); the audit trail then
        explains what happened to a 3-year-out reader who sees the gap.
        """
        self._write("STEP_SKIP", step, reason)

    def gate_pass(self, step: str) -> None:
        self._write("GATE_PASS", step)

    def gate_deny(self, step: str) -> None:
        self._write("GATE_DENY", step)

    def force_clear(self, what: str, reason: str) -> None:
        self._write("FORCE_CLEAR", what, f"reason: {reason}")

    def start_at(self, target_step: str, pre_skipped: list[str]) -> None:
        """Record that the release was launched with --start-at, naming the
        target step and the steps that were pre-marked complete.

        Single log entry covers all pre-skipped steps so the log does not
        get N redundant lines per release; the audit trail still answers
        "which steps were ever genuinely run vs which were synthesized as
        complete" because the pre_skipped list is comma-separated in detail.
        """
        skipped_repr = ",".join(pre_skipped) if pre_skipped else "(none)"
        self._write("START_AT", target_step, f"pre-skipped: {skipped_repr}")

    def end_ok(self) -> None:
        self._write("END_OK", "-")

    def end_fail(self, failed_step: str) -> None:
        self._write("END_FAIL", failed_step)

    def tail(self, n: int = 20) -> list[str]:
        """Return the last n lines of the log (for status command)."""
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        return lines[-n:]


class StepTimer:
    """Context manager for timing a step. Use:

        with StepTimer() as t:
            do_work()
        log.step_ok(step, t.elapsed)
    """

    def __init__(self) -> None:
        self.elapsed: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> StepTimer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.elapsed = time.monotonic() - self._start
