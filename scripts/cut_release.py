"""Cut a Frame Check MCP release after twine upload completes.

The operator runs this AFTER both `twine upload --repository testpypi`
and `twine upload` (PyPI) have succeeded. The script does the four
mechanical post-publish steps in one invocation:

  1. CHANGELOG.md: rename `## [Unreleased]` to `## [<version>] - <YYYY-MM-DD>`
     and insert a new empty `## [Unreleased]` section above it.
  2. pyproject.toml: bump `[project] version` to the next dev cycle.
  3. Create release commit.
  4. Create annotated git tag with release notes extracted from the
     just-renamed CHANGELOG section.

The script does NOT push to origin. The operator pushes manually
(`git push && git push --tags`) after reviewing the commit and tag.

It also does NOT call twine. By the time this script runs, both
TestPyPI and PyPI uploads must already have completed; the script
will refuse to run if `dist/frame_check_mcp-<version>-*.whl` is
missing.

Usage:

    # Default: cut version from current pyproject.toml [project] version,
    # bump to <major>.<minor>.<patch+1>.dev0
    python3 scripts/cut_release.py

    # Override the next-version target
    python3 scripts/cut_release.py --next 0.9.0.dev0

    # Dry-run prints all four operations and exits without modifying
    python3 scripts/cut_release.py --dry-run

Refuses to run if:
  - The working tree has uncommitted changes (other than CHANGELOG/pyproject)
  - dist/frame_check_mcp-<version>-py3-none-any.whl is missing
  - CHANGELOG has no `## [Unreleased]` section
  - pyproject already has a tag for v<version>
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
CHANGELOG = REPO / "CHANGELOG.md"


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=REPO, check=check,
        text=True,
        capture_output=capture,
    )


def read_pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(f"could not read [project] version from {PYPROJECT}")
    return m.group(1)


def compute_next_version(current: str) -> str:
    """Default next-version: <major>.<minor>.<patch+1>.dev0"""
    m = re.match(r'^(\d+)\.(\d+)\.(\d+)$', current)
    if not m:
        raise SystemExit(
            f"current version {current!r} is not <major>.<minor>.<patch>; "
            f"pass --next to override"
        )
    major, minor, patch = m.groups()
    return f"{major}.{minor}.{int(patch) + 1}.dev0"


def check_clean_state(version: str) -> None:
    # Refuse if uncommitted changes outside CHANGELOG/pyproject
    res = run(["git", "status", "--porcelain"], capture=True)
    dirty = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:]
        if path in ("CHANGELOG.md", "pyproject.toml"):
            continue
        # Ignore untracked operator-in-progress files
        if line.startswith("??"):
            continue
        dirty.append(line)
    if dirty:
        print("FATAL: working tree has uncommitted modifications:", file=sys.stderr)
        for d in dirty:
            print(f"  {d}", file=sys.stderr)
        print("Commit or stash these before cutting the release.", file=sys.stderr)
        raise SystemExit(1)

    wheel = REPO / "dist" / f"frame_check_mcp-{version}-py3-none-any.whl"
    if not wheel.exists():
        raise SystemExit(
            f"FATAL: {wheel} not found. Run scripts/lift_dry_run.py first to "
            f"build the wheel; cut_release.py does not build wheels."
        )

    res = run(["git", "tag", "--list", f"v{version}"], capture=True)
    if res.stdout.strip():
        raise SystemExit(
            f"FATAL: tag v{version} already exists. The release is already "
            f"cut, or the tag must be deleted before re-cutting."
        )


def cut_changelog(version: str, today: str) -> tuple[str, str]:
    """Rename [Unreleased] to [version] - today, insert new empty [Unreleased].

    Returns (new_full_text, version_section_text).
    """
    text = CHANGELOG.read_text(encoding="utf-8")

    # Find [Unreleased] header
    unreleased_re = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)
    m = unreleased_re.search(text)
    if not m:
        raise SystemExit(
            "FATAL: CHANGELOG.md has no `## [Unreleased]` header. The release "
            "format does not match Keep a Changelog; cut by hand."
        )

    # Find next ## [version] header to bound the Unreleased section
    next_section_re = re.compile(r"^## \[\d", re.MULTILINE)
    after_unreleased = text[m.end():]
    nm = next_section_re.search(after_unreleased)
    if not nm:
        # Unreleased is the last section
        version_section_body = after_unreleased
        version_section_end_offset = len(text)
    else:
        version_section_body = after_unreleased[:nm.start()]
        version_section_end_offset = m.end() + nm.start()

    # Build new top: empty [Unreleased] then renamed [version] header
    new_unreleased = "## [Unreleased]\n\n"
    new_version_header = f"## [{version}] - {today}\n"

    new_text = (
        text[:m.start()]
        + new_unreleased
        + new_version_header
        + version_section_body
        + text[version_section_end_offset:]
    )

    version_section_full = new_version_header + version_section_body
    return new_text, version_section_full


def bump_pyproject(current: str, next_version: str) -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    new_text = re.sub(
        r'^(version\s*=\s*)"' + re.escape(current) + r'"',
        rf'\1"{next_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if new_text == text:
        raise SystemExit(
            f"FATAL: pyproject.toml [project] version line did not change. "
            f"Current line may not match expected pattern."
        )
    return new_text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--next", dest="next_version", default=None,
                    help="Override next-cycle version (default: bump patch + .dev0)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print operations and exit without modifying anything")
    ap.add_argument("--date", dest="release_date", default=None,
                    help="Override release date (YYYY-MM-DD); default = today UTC")
    args = ap.parse_args()

    version = read_pyproject_version()
    next_version = args.next_version or compute_next_version(version)
    today = args.release_date or date.today().isoformat()

    print(f"Cutting release: {version} (released {today}) -> next dev cycle {next_version}")
    print()

    check_clean_state(version)

    new_changelog_text, version_section = cut_changelog(version, today)
    new_pyproject_text = bump_pyproject(version, next_version)

    tag_message = f"frame-check-mcp v{version}\n\n" + version_section.strip() + "\n"

    if args.dry_run:
        print("DRY RUN. Operations that would be performed:")
        print(f"  1. Rewrite CHANGELOG.md (renames [Unreleased] -> [{version}] - {today})")
        print(f"  2. Rewrite pyproject.toml [project] version: {version} -> {next_version}")
        print(f"  3. Stage CHANGELOG.md + pyproject.toml")
        print(f"  4. Create commit: 'Cut v{version} release'")
        print(f"  5. Create annotated tag v{version} with first lines:")
        for line in tag_message.splitlines()[:10]:
            print(f"       {line}")
        print()
        print(f"After completion, operator pushes:")
        print(f"  git push && git push --tags")
        return 0

    print("[1/4] Rewriting CHANGELOG.md")
    CHANGELOG.write_text(new_changelog_text, encoding="utf-8")

    print("[2/4] Rewriting pyproject.toml")
    PYPROJECT.write_text(new_pyproject_text, encoding="utf-8")

    print(f"[3/4] Creating release commit")
    run(["git", "add", "CHANGELOG.md", "pyproject.toml"])
    commit_message = (
        f"Cut v{version} release: CHANGELOG [Unreleased] -> [{version}] - {today}; "
        f"pyproject version {version} -> {next_version} for next dev cycle. "
        f"Tag v{version} carries the released CHANGELOG section as the annotated tag "
        f"message so the GitHub release notes are derivable from `git show v{version}`. "
        f"This commit is the post-twine close-out: by the time it lands, "
        f"frame-check-mcp {version} is on PyPI and the wheel in dist/ matches the "
        f"PyPI artifact byte-for-byte."
    )
    run(["git", "commit", "-m", commit_message])

    print(f"[4/4] Creating annotated tag v{version}")
    # `git tag -m <text>` passes the message via argv; large CHANGELOG
    # sections (the v0.8.0 release notes were 147KB) exceed the kernel
    # MAX_ARG_STRLEN. Use `-F <file>` so the message goes through stdin
    # and is bounded by filesystem, not by argv limits.
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".txt", delete=False
    ) as tf:
        tf.write(tag_message)
        tag_file = tf.name
    try:
        run(["git", "tag", "-a", f"v{version}", "-F", tag_file])
    finally:
        Path(tag_file).unlink(missing_ok=True)

    print()
    print(f"Release v{version} cut.")
    print(f"  Working tree: clean (commit + tag created)")
    print(f"  Next dev version: {next_version}")
    print()
    print("Operator pushes manually:")
    print("  git push && git push --tags")
    print()
    print(f"GitHub release: https://github.com/lluvr/frame-check/releases/new?tag=v{version}")
    print("  Release notes: paste output of `git tag -n99 v{version}` or click")
    print("  'Generate release notes' (the annotated tag body is already the notes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
