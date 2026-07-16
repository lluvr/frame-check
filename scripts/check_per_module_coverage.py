#!/usr/bin/env python3
"""Enforce per-module coverage floors for the seven-module wheel surface.

The v1.0 ROADMAP commits each wheel-surface module to 80% production-
code coverage. ``pytest-cov`` has only a single global ``--cov-fail-
under`` threshold, so this script runs as a follow-up step after
``pytest --cov`` produces the .coverage data file: it loads the file
via the coverage.py Python API, computes per-module percentage, and
exits non-zero if any module falls below its declared floor.

Run from repo root after a coverage-instrumented test suite. The
.coverage file produced by pytest sits in CWD by default.

Usage:

  python3 -m pytest --cov=. --cov-report=term tests/
  python3 scripts/check_per_module_coverage.py

Exit codes:

  0  every module at or above its floor.
  1  one or more modules below their floor (details printed to stderr).
  2  invocation error (no .coverage file, missing module file).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Per-module floors for the seven-module wheel surface. The v1.0
# contract is 80% on each; raising a floor in the future is a
# one-line edit here. Modules outside this list are not gated by
# this script; the global ``--cov-fail-under=65`` in pytest covers
# everything else.
FLOORS: dict[str, int] = {
    "mcp_server.py": 80,
    "mcp_compose.py": 80,
    "mcp_resources.py": 80,
    "mcp_schema.py": 80,
    "framing.py": 80,
    "comparison.py": 80,
    "clarethium_measure.py": 80,
}


def main() -> int:
    try:
        from coverage import Coverage
    except ImportError:
        print(
            "error: coverage package not installed. Install with "
            "`pip install coverage` or `pip install pytest-cov`.",
            file=sys.stderr,
        )
        return 2

    cov = Coverage()
    try:
        cov.load()
    except Exception as exc:
        print(
            f"error: failed to load coverage data: {exc}\n"
            f"hint: run `pytest --cov=.` first to produce .coverage.",
            file=sys.stderr,
        )
        return 2

    failures: list[tuple[str, float, int]] = []
    print(f"{'Module':<30} {'Coverage':>10} {'Floor':>8} {'Status':>8}")
    print("-" * 60)

    for module, floor in FLOORS.items():
        # Resolve to the actual file path on disk so coverage.py
        # can analyze it. We assume the script runs from repo root
        # where src/ holds the seven modules.
        path = Path("src") / module
        if not path.exists():
            print(
                f"{module:<30} ERROR: file not found under src/",
                file=sys.stderr,
            )
            failures.append((module, 0.0, floor))
            continue

        try:
            analysis = cov.analysis2(str(path))
        except Exception as exc:
            print(
                f"{module:<30} ERROR: coverage.analysis2 failed: {exc}",
                file=sys.stderr,
            )
            failures.append((module, 0.0, floor))
            continue

        # analysis2 returns (filename, executable_lines, excluded_lines,
        #                    missing_lines, missing_formatted)
        executable = analysis[1]
        missing = analysis[3]
        if not executable:
            pct = 100.0
        else:
            covered_count = len(executable) - len(missing)
            pct = 100.0 * covered_count / len(executable)

        status = "PASS" if pct >= floor else "FAIL"
        print(f"{module:<30} {pct:>9.1f}% {floor:>7}% {status:>8}")
        if pct < floor:
            failures.append((module, pct, floor))

    print()
    if failures:
        print(
            f"FAIL: {len(failures)} module(s) below per-module v1.0 "
            f"contract floor:",
            file=sys.stderr,
        )
        for module, pct, floor in failures:
            print(
                f"  {module}: {pct:.1f}% < {floor}% (need "
                f"+{floor - pct:.1f} pp)",
                file=sys.stderr,
            )
        print(
            "\nThe v1.0 ROADMAP commits to 80% per-module on the "
            "seven-module wheel surface. A new uncovered code path "
            "needs tests before this PR can merge.",
            file=sys.stderr,
        )
        return 1

    print(
        f"PASS: all {len(FLOORS)} wheel-surface modules at or above "
        f"the 80% v1.0 contract floor."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
