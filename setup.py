"""Setuptools shim for cross-platform wheel build.

Modern packaging metadata lives in pyproject.toml (PEP 621). This file
exists ONLY to register a custom build_py command that copies
repo-root data into framecheck_mcp/ at build time.

The repo carries data at root (`data/`, `calibration/`,
`validation/`, the divergence-contract spec, `pipeline_version.txt`).
The MCP wheel needs those bundled INSIDE the `framecheck_mcp/`
package so a pip-installed user gets the data alongside the code.

A symlink-based layout works on Linux and macOS but breaks on Windows
(symlinks require elevated privileges) and on shallow clones that
strip symlink info. This shim replaces symlinks with a build-time
copy that works on every platform setuptools supports.

Local dev workflow is unchanged: data continues to live at repo root.
This shim only fires during `python -m build` (or `pip install .`
which invokes the build backend).

Staging-time exclusion. The copy applies a per-directory filter so
the wheel ships only the runtime-loaded subset. Research snapshots,
build/CLI scripts, scaffolding templates, and per-run debug artifacts
that have no runtime use to MCP consumers are filtered out at staging
time so the inclusion contract is enforced by code rather than by
manual inspection.
"""
from __future__ import annotations

import fnmatch
import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


# Files and directories at repo root that need to ship inside the
# framecheck_mcp/ package so mcp_server.py's `_DATA_ROOT` resolution
# finds them in the installed wheel layout.
_DATA_CARRIERS = [
    # (source-path-relative-to-repo-root, destination-path-relative-to-pkg)
    # Destination paths inside the wheel package stay flat at
    # framecheck_mcp/<NAME>.md so mcp_resources.py runtime path
    # resolution (frame-check:// resource URIs) keeps working against
    # the wheel layout.
    ("data", "data"),
    ("calibration", "calibration"),
    ("validation", "validation"),
    ("docs/MCP_SERVER.md", "MCP_SERVER.md"),
    ("docs/FRAME_DIVERGENCE_CONTRACT_v1.md", "FRAME_DIVERGENCE_CONTRACT_v1.md"),
    ("pipeline_version.txt", "pipeline_version.txt"),
]


def _should_skip(rel_dir: str, name: str) -> bool:
    """Decide whether to exclude `name` from staging when copying the
    directory whose path relative to the repo root is `rel_dir`.

    Returns True to exclude (file or subdirectory). The exclusions
    keep research artifacts, build/CLI scripts, and per-run debug
    files out of the wheel; only runtime-loaded resources ship.

    `rel_dir` is POSIX-separated (forward-slash) for portability.
    """
    # Universal exclusions (any directory).
    if name == "__pycache__":
        return True
    if name.startswith(".env"):
        return True
    if name.endswith((".sqlite", ".sqlite-shm", ".sqlite-wal")):
        return True
    if name in ("circuit_breaker.json", "frame_check_observatory_state.json"):
        return True

    # data/: research-snapshot and research-fork subdirectories that
    # are not runtime resources.
    if rel_dir == "data":
        if name in (
            "adversarial_fixtures",
            "anchor_retractions",
            "anchor_working_notes",
            "falsifications",
            "track_b_informal",
            "frame_library_v2",
            "frame_library_v4",
        ):
            return True
        if fnmatch.fnmatch(name, "frame_library_*_abl*"):
            return True

    # data/frame_library/: research-development audits
    # (AUDIT_*, ADJACENCY_*, DETECTION_RULE_*) and the promotions/
    # subtree are not runtime resources for the MCP server.
    if rel_dir == "data/frame_library":
        if name == "promotions":
            return True
        if fnmatch.fnmatch(name, "AUDIT_*.md"):
            return True
        if fnmatch.fnmatch(name, "ADJACENCY_*.md"):
            return True
        if fnmatch.fnmatch(name, "DETECTION_RULE_*.md"):
            return True

    # data/worked_examples/: scaffolding (template + draft review)
    # follows the build_corpus_site.py convention: leading-underscore
    # files are not rendered as entries.
    if rel_dir == "data/worked_examples":
        if name.startswith("_") and name.endswith(".md"):
            return True

    # validation/decision_readiness/: build/CLI scripts. Only the
    # data subdirectories (results/, corpus/) are runtime resources
    # for the MCP server.
    if rel_dir == "validation/decision_readiness":
        if name.endswith(".py"):
            return True

    # validation/decision_readiness/results/{date}-{hash}/: drop the
    # cross_check.{json,md} files. Their `aggregate_source` /
    # "Aggregate file:" fields contain producer-machine absolute paths
    # and the files are not consumed by mcp_server.py.
    # aggregate.{json,md} remain.
    parts = rel_dir.split("/")
    if (
        len(parts) == 4
        and parts[0] == "validation"
        and parts[1] == "decision_readiness"
        and parts[2] == "results"
    ):
        if name in ("cross_check.json", "cross_check.md"):
            return True

    # calibration/: build/CLI scripts. Only results/ ships.
    if rel_dir == "calibration":
        if name.endswith(".py"):
            return True

    return False


def _make_ignore(repo_root: str):
    """Build an `ignore` callback for shutil.copytree that applies the
    staging-time exclusion list relative to `repo_root`.
    """

    def ignore(src_dir: str, names: list[str]) -> set[str]:
        rel = os.path.relpath(src_dir, repo_root).replace(os.sep, "/")
        return {n for n in names if _should_skip(rel, n)}

    return ignore


def _stage_package_data() -> None:
    """Copy repo-root data into framecheck_mcp/ before setuptools
    inspects the package tree. Idempotent: existing destinations are
    replaced. Missing sources are skipped (e.g., pipeline_version.txt
    may not exist locally if it has not been baked yet). Per-directory
    exclusions filter to the runtime-loaded subset; see _should_skip.
    """
    repo_root = os.path.dirname(os.path.abspath(__file__))
    pkg_root = os.path.join(repo_root, "framecheck_mcp")
    if not os.path.isdir(pkg_root):
        os.makedirs(pkg_root)
    ignore_cb = _make_ignore(repo_root)
    for src_rel, dst_rel in _DATA_CARRIERS:
        src = os.path.join(repo_root, src_rel)
        dst = os.path.join(pkg_root, dst_rel)
        if os.path.lexists(dst):
            # Remove existing destination, including symlinks created
            # by an earlier dev workflow. This is the cross-platform
            # replacement for the symlinks the repo used to carry.
            if os.path.islink(dst) or os.path.isfile(dst):
                os.unlink(dst)
            elif os.path.isdir(dst):
                shutil.rmtree(dst)
        if not os.path.exists(src):
            # Source missing (e.g., pipeline_version.txt before the
            # CI bake step). Skip; package_data globs will simply not
            # match this entry.
            continue
        if os.path.isdir(src):
            shutil.copytree(src, dst, symlinks=False, ignore=ignore_cb)
        else:
            shutil.copy2(src, dst)


class _StagedBuildPy(build_py):
    """build_py command that stages package data before running."""

    def run(self) -> None:  # type: ignore[override]
        _stage_package_data()
        super().run()


setup(
    cmdclass={"build_py": _StagedBuildPy},
)
