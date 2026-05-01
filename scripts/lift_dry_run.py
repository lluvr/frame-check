"""Backward-compatible wrapper. Real implementation in scripts/_release_lib/lift.py.

The library module carries the operator-facing docstring and the full
gate sequence. Invoking `python3 scripts/lift_dry_run.py [...flags]`
defers to `lift.main()` which defaults `argv` to `sys.argv`, preserving
the established `--skip-urls` / `--skip-content` / `--skip-quality`
semantics. The orchestrator at `scripts/release.py` calls
`lift.main(argv=...)` directly so step gating is configurable from the
release sequence without process-wide `sys.argv` mutation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _release_lib import lift  # noqa: E402


if __name__ == "__main__":
    sys.exit(lift.main())
