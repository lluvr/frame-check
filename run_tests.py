#!/usr/bin/env python3
"""Run the public test suite via pytest discovery on tests/."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
TESTS = REPO / "tests"


def main() -> int:
    args = [sys.executable, "-m", "pytest", "-q", str(TESTS)] + sys.argv[1:]
    return subprocess.call(args, cwd=str(REPO))


if __name__ == "__main__":
    sys.exit(main())
