"""Cut a Frame Check MCP release: CHANGELOG rename + dev-bump + local tag.

The maintainer runs this BEFORE the orchestrator (`scripts/release.py`).
The script does the five mechanical pre-publish steps in one invocation:

  1. CHANGELOG.md: rename `## [Unreleased]` to `## [<version>] - <YYYY-MM-DD>`
     and insert a new empty `## [Unreleased]` section above it.
  2. pyproject.toml: bump `[project] version` to the next dev cycle
     (`X.Y.(Z+1).dev0`).
  3. mcp_server.py: bump `SERVER_VERSION` to the same next-cycle
     version (`X.Y.(Z+1)` -- without the .dev suffix; SERVER_VERSION
     never carries one per test_version_coherence::test_server_version_
     format). Paired with step 2 so the upstream tree post-cut has
     both axes coherent (pinned by test_version_coherence::test_
     server_version_matches_pyproject).
  4. Create release commit (CHANGELOG + pyproject + mcp_server.py).
  5. Create annotated git tag with release notes extracted from the
     just-renamed CHANGELOG section.

Order in the canonical flow:

  cut_release.py        (this script: CHANGELOG + bump + commit + local tag)
    -> release.py release <version>
       (orchestrator: build wheel + lift gates, maintainer gate, twine upload,
        public-repo sync, tag push, gh release create, Zenodo poll,
        CITATION back-fill, push origin master + tag)

The script does NOT push to origin. The orchestrator pushes during
its `close_out` step (step 17 of 18). Pushing the cut commit + tag
manually before the orchestrator runs twine recreates the 2026-04-29
v0.8.3 24-hour gap (origin advertises a tag for an artifact PyPI
does not yet have).

The script does NOT call twine; the orchestrator does. The wheel-exists
precondition (refuse if `dist/frame_check_mcp-<version>-*.whl` is
missing) remains because the lift step that precedes cut produces the
wheel; it is the only requirement on prior dist/ state.

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

# Library file lives at scripts/_release_lib/close_out.py; REPO walks
# up three parents to reach the repo root (file -> _release_lib ->
# scripts -> repo). The thin wrapper at scripts/cut_release.py imports
# this module rather than re-deriving REPO, so this single source-of-
# truth governs both invocation paths.
REPO = Path(__file__).resolve().parent.parent.parent
PYPROJECT = REPO / "pyproject.toml"
CHANGELOG = REPO / "CHANGELOG.md"
MCP_SERVER = REPO / "mcp_server.py"


def _strip_dev_suffix(version: str) -> str:
    """Strip a trailing `.devN` suffix from a version string.

    SERVER_VERSION discipline pins the literal `M.m.p` shape (no
    `.dev` suffix; pinned by test_version_coherence::test_server_
    version_format). pyproject during a dev cycle carries `.dev0`
    (e.g., "0.8.5.dev0") to mark the upstream tree as not-yet-
    released. The two-axes coherence rule
    (test_version_coherence::test_server_version_matches_pyproject)
    requires that SERVER_VERSION equals strip(pyproject_version) at
    all points in the release arc; close_out's bump_server_version
    uses this helper to compute the new SERVER_VERSION value from
    the .dev0-suffixed next-cycle pyproject value.
    """
    return re.sub(r'\.dev\d+$', '', version)


def _read_server_version() -> str:
    """Read SERVER_VERSION literal from mcp_server.py.

    Mirrors read_pyproject_version's shape (parse the source file
    for the literal, do not import the module). Importing
    mcp_server pulls in the full MCP server surface (resource
    cache, tool definitions, prompt templates) which is heavy for
    a single-string read AND would mask a syntax error elsewhere
    in the file as an ImportError that confuses the failure mode
    here.
    """
    text = MCP_SERVER.read_text(encoding="utf-8")
    m = re.search(r'^SERVER_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(
            f"could not find SERVER_VERSION in {MCP_SERVER}"
        )
    return m.group(1)


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
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
        # Ignore untracked maintainer-in-progress files
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
            "FATAL: pyproject.toml [project] version line did not change. "
            "Current line may not match expected pattern."
        )
    return new_text


def bump_server_version(current: str, next_version: str) -> str:
    """Return the new mcp_server.py text with SERVER_VERSION
    rewritten from `current` to strip(next_version).

    `current` is the pre-bump SERVER_VERSION literal the file
    currently carries (e.g., "0.8.4"). `next_version` is the
    next-dev-cycle pyproject version (e.g., "0.8.5.dev0"); this
    function strips the `.dev0` suffix because SERVER_VERSION
    never carries it (test_version_coherence::test_server_version_
    format pin). Result: SERVER_VERSION moves from "0.8.4" to
    "0.8.5" alongside pyproject moving from "0.8.4" to
    "0.8.5.dev0".

    Mirrors bump_pyproject's contract: refuse with SystemExit when
    the literal `SERVER_VERSION = "<current>"` line is missing
    (file was edited by something other than this function or the
    extractor's rewrite_server_version, and the bump can no longer
    be done blindly). Same count=1 discipline so a stray
    `SERVER_VERSION = "..."` elsewhere in the file (a comment, a
    docstring example) is not touched.

    Why bump SERVER_VERSION here, alongside bump_pyproject:
    test_version_coherence pins that mcp_server.py:SERVER_VERSION
    matches strip(pyproject [project] version) at all points in
    the release arc. Without this bump, close_out would leave the
    upstream tree in a state where pyproject is the next-cycle
    version (X.Y.(Z+1).dev0) but SERVER_VERSION is the just-
    released version (X.Y.Z), and the coherence test would
    false-positive on the post-cut state every dev cycle. The
    SERVER_VERSION rewrite at extract time
    (scripts/_release_lib/extract.py:rewrite_server_version)
    handles the SHIPPED wheel; this bump_server_version handles
    the upstream tree so both paths converge on the discipline.
    """
    text = MCP_SERVER.read_text(encoding="utf-8")
    new_server_version = _strip_dev_suffix(next_version)
    new_text = re.sub(
        r'^(SERVER_VERSION\s*=\s*)"' + re.escape(current) + r'"',
        rf'\1"{new_server_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if new_text == text:
        raise SystemExit(
            f"FATAL: mcp_server.py SERVER_VERSION line did not change. "
            f"Expected current value {current!r}; the file may have "
            f"been edited externally or the line may not match the "
            f"expected pattern."
        )
    return new_text


def main(argv: list[str] | None = None) -> int:
    """Run the close-out sequence.

    `argv` defaults to `sys.argv[1:]` (argparse's standard contract)
    so the standalone wrapper at `scripts/cut_release.py` keeps the
    established CLI semantics. The orchestrator passes its own argv
    list so the close_out step is configurable from `release.py`
    without process-wide `sys.argv` mutation.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--next", dest="next_version", default=None,
                    help="Override next-cycle version (default: bump patch + .dev0)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print operations and exit without modifying anything")
    ap.add_argument("--date", dest="release_date", default=None,
                    help="Override release date (YYYY-MM-DD); default = today UTC")
    args = ap.parse_args(argv)

    version = read_pyproject_version()
    next_version = args.next_version or compute_next_version(version)
    today = args.release_date or date.today().isoformat()

    print(f"Cutting release: {version} (released {today}) -> next dev cycle {next_version}")
    print()

    check_clean_state(version)

    new_changelog_text, version_section = cut_changelog(version, today)
    new_pyproject_text = bump_pyproject(version, next_version)
    # SERVER_VERSION coherence per the test_version_coherence
    # discipline: pyproject and SERVER_VERSION must agree (after
    # .dev0 strip) at all points in the release arc. Without this
    # bump, close_out would leave pyproject at the next-cycle
    # version while SERVER_VERSION stayed at the just-released
    # value, and the upstream tree would fail the coherence
    # test on every post-cut state.
    current_server_version = _read_server_version()
    new_mcp_server_text = bump_server_version(
        current_server_version, next_version,
    )
    new_server_version = _strip_dev_suffix(next_version)

    tag_message = f"frame-check-mcp v{version}\n\n" + version_section.strip() + "\n"

    if args.dry_run:
        print("DRY RUN. Operations that would be performed:")
        print(f"  1. Rewrite CHANGELOG.md (renames [Unreleased] -> [{version}] - {today})")
        print(f"  2. Rewrite pyproject.toml [project] version: {version} -> {next_version}")
        print(f"  3. Rewrite mcp_server.py SERVER_VERSION: "
              f"{current_server_version} -> {new_server_version}")
        print("  4. Stage CHANGELOG.md + pyproject.toml + mcp_server.py")
        print(f"  5. Create commit: 'Cut v{version} release'")
        print(f"  6. Create annotated tag v{version} with first lines:")
        for line in tag_message.splitlines()[:10]:
            print(f"       {line}")
        print()
        print("Next step (drives twine + public-repo sync + tag push + Zenodo):")
        print(f"  python3 scripts/release.py release {version}")
        return 0

    print("[1/5] Rewriting CHANGELOG.md")
    CHANGELOG.write_text(new_changelog_text, encoding="utf-8")

    print("[2/5] Rewriting pyproject.toml")
    PYPROJECT.write_text(new_pyproject_text, encoding="utf-8")

    print(f"[3/5] Rewriting mcp_server.py SERVER_VERSION "
          f"{current_server_version} -> {new_server_version}")
    MCP_SERVER.write_text(new_mcp_server_text, encoding="utf-8")

    print("[4/5] Creating release commit")
    run(["git", "add", "CHANGELOG.md", "pyproject.toml", "mcp_server.py"])
    commit_message = (
        f"Cut v{version} release: CHANGELOG [Unreleased] -> [{version}] - {today}; "
        f"pyproject version {version} -> {next_version}; "
        f"mcp_server.py SERVER_VERSION {current_server_version} -> {new_server_version} "
        f"for next dev cycle. "
        f"Tag v{version} carries the released CHANGELOG section as the annotated tag "
        f"message so the GitHub release notes are derivable from `git show v{version}`. "
        f"This commit is the PRE-publish prerequisite: it creates the local cut "
        f"commit + tag that the orchestrator's preflight (`python3 scripts/release.py "
        f"release {version}`) requires. The actual publish (twine upload, public-repo "
        f"sync, GitHub release, Zenodo mint, master + tag push to origin) is driven "
        f"by the orchestrator after this commit lands. Manually pushing the cut "
        f"commit + tag before twine has run recreates the 2026-04-29 v0.8.3 24-hour "
        f"gap (origin advertises a tag for an artifact PyPI does not yet have)."
    )
    run(["git", "commit", "-m", commit_message])

    print(f"[5/5] Creating annotated tag v{version}")
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
    print(f"Release v{version} cut locally (commit + tag created).")
    print(f"  Next dev version: {next_version}")
    print()
    print("Next step: drive the publish through the orchestrator:")
    print(f"  python3 scripts/release.py release {version}")
    print()
    print("DO NOT push the cut commit or tag manually before twine.")
    print("The orchestrator runs twine + public-repo sync + tag push + gh")
    print("release create + Zenodo poll + CITATION back-fill + origin master/")
    print("tag push inside its lock + state machine. Manual `git push` /")
    print("`git push --tags` ahead of twine recreates the 2026-04-29 v0.8.3")
    print("24-hour gap (origin advertises a tag for an artifact PyPI does")
    print("not yet have).")
    return 0


def _release_page_url(version: str) -> str:
    """Derive the GitHub releases/new URL from `git remote get-url origin`.

    Path A.1 split-repo discipline: the public source repo
    `Clarethium/frame-check` is the user-visible release target; the
    the upstream development tree carries audit-trail-only
    tags. Both are valid call sites for cut_release.py, so the URL
    must reflect whichever repo this script is actually running in
    rather than carrying a hardcoded reference.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True, capture_output=True, text=True
        )
        url = result.stdout.strip()
    except subprocess.CalledProcessError:
        return f"https://github.com/<owner>/<repo>/releases/new?tag=v{version}"

    m = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/]+/[^/.]+)(?:\.git)?$", url)
    if not m:
        return f"{url} (releases/new?tag=v{version})"
    return f"https://github.com/{m.group(1)}/releases/new?tag=v{version}"


if __name__ == "__main__":
    sys.exit(main())
