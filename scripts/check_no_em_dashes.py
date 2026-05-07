#!/usr/bin/env python3
"""Pre-commit hook: reject prose em-dashes and en-dashes.

Per `feedback_em_dashes.md` and the operator's writing-rule discipline
(`~/.claude/CLAUDE.md` "WRITING RULES" section), em-dashes (U+2014) and
en-dashes (U+2013) are not allowed in code comments, docstrings, test
messages, or markdown prose. They are allowed only where the character
is functional (regex character classes that match em/en-dash characters
in user text, and the em-dash-scanning grep pattern in CONTRIBUTING.md
itself).

This hook scans files staged for commit and fails if any em-dash or
en-dash is found outside the allowlist below.

Allowlist entries are file-path-suffix-matched plus a substring match
against the offending line. Both must match for the line to be allowed.
"""
import re
import sys

# (file_suffix, line_substring): if BOTH match the offending line is
# allowed. Add new allowlist entries here when adding new load-bearing
# em-dash uses; explain why in a comment.
_ALLOWLIST = [
    # CONTRIBUTING.md documents the em-dash-scanning grep pattern that
    # contributors are expected to run before committing. The pattern
    # itself contains the characters it matches; removing them defeats
    # the discipline.
    ("CONTRIBUTING.md", "Grep with"),
    # clarethium_measure.py: four regex character classes that match
    # the characters in user text. Functional, not stylistic. Allowlist
    # is anchored to the named-tuple labels and structural fragments
    # that surround each regex so a future prose em-dash addition to
    # this file is still caught.
    ("clarethium_measure.py", "pct_range"),
    ("clarethium_measure.py", "dollar_range"),
    ("clarethium_measure.py", "[-–]?\\s*(?:\\d"),
    ("clarethium_measure.py", "(?:—\\s*)"),
    # time_context.py: en-dash in year-range regex (e.g., 2020 to 2023
    # written with an en-dash). Anchored to the year-range pattern.
    ("time_context.py", "(?:-|–|to)"),
    # This script (the em-dash detector itself) MUST contain the
    # characters it scans for. Whitelist all em/en-dash occurrences in
    # its own source.
    ("scripts/check_no_em_dashes.py", ""),
    # Pre-discipline historical audit deliverables. The audits were
    # written before the em-dash writing rule was adopted; they are
    # frozen historical records of what the operator said at audit
    # time. Editing the body would falsify the record. The em-dashes
    # ship in the public mirror under docs/internal/ where adopters
    # can read the audit posture as written. Future audit reports use
    # the post-discipline writing rules.
    ("docs/internal/LEAKAGE_AUDIT_v1.md", ""),
    ("docs/internal/REMEDIATION_LOG_v1.md", ""),
    ("docs/internal/LEAKAGE_AUDIT_v1_appendix_a_2026_04_29.md", ""),
]

_EM_DASH = "—"
_EN_DASH = "–"


def _is_allowed(path: str, line: str) -> bool:
    for suffix, substring in _ALLOWLIST:
        if path.endswith(suffix) and substring in line:
            return True
    return False


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0
    failures: list[str] = []
    for path in files:
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            # Binary or unreadable file. Skip.
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if _EM_DASH not in line and _EN_DASH not in line:
                continue
            if _is_allowed(path, line):
                continue
            snippet = line.strip()
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            failures.append(f"{path}:{lineno}: {snippet}")
    if failures:
        sys.stderr.write(
            "Em-dash discipline violation (per feedback_em_dashes.md). "
            "Replace — / – with appropriate punctuation, "
            "or rewrite the sentence:\n"
        )
        for fail in failures:
            sys.stderr.write(f"  {fail}\n")
        sys.stderr.write(
            "\nIf the em-dash or en-dash is functional (regex character "
            "class, scanning grep pattern, etc.), add an allowlist entry "
            "to scripts/check_no_em_dashes.py.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
