"""Exclusive release lock with stale-pid detection.

The lock guarantees one release orchestrator runs at a time on this machine.
Implementation:

  - `.release/release.lock` is created with O_EXCL so two simultaneous
    acquire() calls cannot both succeed; the loser sees EEXIST.
  - Lock content is JSON with agent_id, pid, version, acquired_at. This
    lets a stale lock be detected: if the recorded pid is no longer alive
    (os.kill(pid, 0) raises), the lock is stale and may be reclaimed.
  - release() unlinks the file. release() is also idempotent; it does not
    error if the lock has already been released.

What the lock does NOT cover:

  - Cross-machine coordination. Two operators on two machines could both
    acquire their local lock and both run twine upload; PyPI's
    file-uniqueness gate would reject the second one but only after the
    first succeeded. The internal discipline is "one machine handles
    releases" not enforced by code.
  - Long-running stale processes that were forgotten. A pid is "alive"
    even if the process is hung; the operator runs `release.py unlock
    --reason ...` to clear, recording why.
"""

from __future__ import annotations

import errno
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LockHeld(Exception):
    """Raised when an acquire() collides with a live lock held by another agent."""


class LockState:
    """Snapshot of lock contents at a point in time."""

    def __init__(
        self,
        path: Path,
        agent_id: str,
        pid: int,
        version: str,
        acquired_at: str,
    ) -> None:
        self.path = path
        self.agent_id = agent_id
        self.pid = pid
        self.version = version
        self.acquired_at = acquired_at

    def is_alive(self) -> bool:
        """Return True if the recorded pid is still running on this machine."""
        try:
            os.kill(self.pid, 0)
            return True
        except OSError as e:
            if e.errno == errno.ESRCH:
                return False
            if e.errno == errno.EPERM:
                # Process exists but is owned by another user. Treat as alive.
                return True
            raise

    def describe(self) -> str:
        return (
            f"agent_id={self.agent_id} pid={self.pid} "
            f"version={self.version} acquired_at={self.acquired_at}"
        )


class ReleaseLock:
    """File-based lock at `.release/release.lock`."""

    def __init__(self, release_dir: Path) -> None:
        self.lock_path = release_dir / "release.lock"

    def acquire(self, version: str, agent_id: str) -> None:
        """Acquire the lock. Raises LockHeld if a live agent already holds it."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(
                str(self.lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            existing = self.read()
            if existing is None:
                # Empty/corrupt lockfile. Reclaim by treating as stale.
                self.lock_path.unlink()
                self.acquire(version, agent_id)
                return
            if existing.is_alive():
                raise LockHeld(
                    f"Release lock held: {existing.describe()}. "
                    f"Wait for that release to complete, or run "
                    f"`python3 scripts/release.py unlock --reason ...` "
                    f"to clear if the lock is genuinely stale."
                )
            self.lock_path.unlink()
            self.acquire(version, agent_id)
            return

        try:
            payload = {
                "agent_id": agent_id,
                "pid": os.getpid(),
                "version": version,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            }
            os.write(fd, (json.dumps(payload) + "\n").encode("utf-8"))
        finally:
            os.close(fd)

    def release(self) -> None:
        """Idempotent unlock."""
        if self.lock_path.exists():
            self.lock_path.unlink()

    def read(self) -> LockState | None:
        """Return current lock contents, or None if absent / unreadable."""
        if not self.lock_path.exists():
            return None
        try:
            data: dict[str, Any] = json.loads(
                self.lock_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            return None
        return LockState(
            path=self.lock_path,
            agent_id=str(data.get("agent_id", "<unknown>")),
            pid=int(data.get("pid", 0)),
            version=str(data.get("version", "<unknown>")),
            acquired_at=str(data.get("acquired_at", "<unknown>")),
        )

    def force_clear(self, reason: str) -> LockState | None:
        """Unlink the lock unconditionally; return what was cleared (if any).

        The caller is responsible for recording `reason` in the release log.
        force_clear() is not the normal release() path; it is the operator's
        manual override for stuck locks.
        """
        existing = self.read()
        if self.lock_path.exists():
            self.lock_path.unlink()
        return existing
