"""Release state machine.

Persists release progress to `.release/state.json` so a partial release can
resume without duplicating completed work and without forgetting where it
stopped. The contract:

  - `state.json` is single-writer (the lockfile guarantees one orchestrator
    process at a time; two concurrent writers would corrupt the file).
  - State is per-machine (`.release/` is gitignored). A release initiated on
    one machine does not resume on another. This is intentional: cross-machine
    resume would need the same /tmp staging directory and credentials, which
    is more coordination surface than the safety gain warrants.
  - State is mutable forward-only. The completed_steps list grows; current_step
    advances. A reset() clears state for a fresh attempt; there is no
    "uncomplete" operation.
  - Mismatched-version load is a hard error. If state.json says v0.8.2 and the
    maintainer invokes release.py 0.8.3, the orchestrator refuses rather than
    silently overwriting. The maintainer must `release.py status` and decide
    explicitly whether to `release.py unlock` and start fresh or resume the
    in-progress version.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReleaseStateError(Exception):
    """Raised on state-file inconsistencies that need maintainer intervention."""


class ReleaseState:
    """Reads/writes `.release/state.json` for one release attempt."""

    def __init__(self, release_dir: Path, version: str) -> None:
        self.release_dir = release_dir
        self.version = version
        self.state_path = release_dir / "state.json"
        self.completed_steps: list[str] = []
        self.current_step: str | None = None
        self.artifacts: dict[str, Any] = {}
        self.started_at: str | None = None
        self.agent_id: str | None = None

    def load(self) -> bool:
        """Load existing state. Returns True if state existed and was loaded.

        Raises ReleaseStateError if the loaded state is for a different
        version (maintainer must resolve before continuing).
        """
        if not self.state_path.exists():
            return False
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ReleaseStateError(
                f"`{self.state_path}` is not valid JSON ({e}). "
                f"Inspect manually and either repair, or run "
                f"`python3 scripts/release.py unlock --reason '<why>' "
                f"--also-state` to clear both lock and state."
            ) from e

        loaded_version = data.get("version")
        if loaded_version != self.version:
            raise ReleaseStateError(
                f"State file is for version {loaded_version!r}; "
                f"current invocation is for {self.version!r}. "
                f"Run `python3 scripts/release.py status` to inspect, then "
                f"either resume {loaded_version} (re-run the release for "
                f"that version with --resume), or run `release.py unlock "
                f"--reason '<why>' --also-state` to clear and start fresh."
            )

        self.completed_steps = list(data.get("completed_steps", []))
        self.current_step = data.get("current_step")
        self.artifacts = dict(data.get("artifacts", {}))
        self.started_at = data.get("started_at")
        self.agent_id = data.get("agent_id")
        return True

    def save(self) -> None:
        """Persist current state atomically (write to tmp, then rename)."""
        self.release_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._snapshot(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.state_path)

    def initialize(self, agent_id: str) -> None:
        """Mark a fresh release attempt; persists start timestamp + agent ID."""
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.agent_id = agent_id
        self.save()

    def begin_step(self, step: str) -> None:
        self.current_step = step
        self.save()

    def complete_step(self, step: str) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.current_step = None
        self.save()

    def is_complete(self, step: str) -> bool:
        return step in self.completed_steps

    def set_artifact(self, key: str, value: Any) -> None:
        self.artifacts[key] = value
        self.save()

    def reset(self) -> None:
        """Delete state file. The lockfile is independent and survives reset()."""
        if self.state_path.exists():
            self.state_path.unlink()
        self.completed_steps = []
        self.current_step = None
        self.artifacts = {}
        self.started_at = None
        self.agent_id = None

    def _snapshot(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "started_at": self.started_at,
            "agent_id": self.agent_id,
            "completed_steps": list(self.completed_steps),
            "current_step": self.current_step,
            "artifacts": dict(self.artifacts),
        }
