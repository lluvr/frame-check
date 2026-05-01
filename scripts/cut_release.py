"""Backward-compatible wrapper. Real implementation in scripts/_release_lib/close_out.py.

The library module carries the operator-facing docstring and CLI;
argparse's `description=__doc__` resolves to the library's `__doc__`,
so `--help` output is unchanged from before the refactor. Invoking
`python3 scripts/cut_release.py [...flags]` defers to
`close_out.main()` which defaults `argv` to `sys.argv[1:]` (argparse
contract). The orchestrator at `scripts/release.py` calls
`close_out.main(argv=...)` directly so the close_out step is
configurable from the release sequence without process-wide
`sys.argv` mutation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _release_lib import close_out  # noqa: E402


if __name__ == "__main__":
    sys.exit(close_out.main())
