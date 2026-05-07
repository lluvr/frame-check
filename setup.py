"""Setuptools shim for cross-platform wheel build.

Modern packaging metadata lives in pyproject.toml (PEP 621). This file
exists ONLY to register a custom build_py command that copies
repo-root data into framecheck_mcp/ at build time.

Why we need this. The repo carries data files at root (data/,
calibration/, validation/, METHODOLOGY.md, FRAME_DIVERGENCE_v1.md,
FRAME_DIVERGENCE_CONTRACT_v1.md, V4_2_GAP_INVENTORY_v1.md,
pipeline_version.txt). The web app, fvs_eval/ scripts, and
build_corpus_site.py all read those paths directly from the repo
root. The MCP wheel needs them bundled INSIDE the framecheck_mcp/
package so a pip-installed user gets the data alongside the code.

The original approach (Unix symlinks at framecheck_mcp/data ->
../data, etc.) works on Linux and macOS but breaks on Windows
(symlinks require elevated privileges) and on shallow clones that
strip symlink info. This shim replaces the runtime symlink approach
with a build-time copy that works on every platform setuptools
itself supports.

Local dev workflow is unchanged: data continues to live at repo root.
This shim only fires during `python -m build` (or `pip install .`
which invokes the build backend).

Staging-time exclusion. The copy applies a per-directory filter that
mirrors RELEASE_PREP_v1.md Section 3 (must-exclude inventory) plus
the maintainer-internal items identified in LEAKAGE_AUDIT_v1.md
(internal AI-authored audits, dev CLI scripts, scaffolding
templates, leak-bearing cross_check artifacts, promotion dossiers,
research ablation forks). Without this filter the wheel ships
research artifacts and maintainer-internal documents that have no
runtime use to MCP consumers; making the filter the gate at staging
time means the must-exclude inventory is enforced by code rather
than by manual inspection.
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
    # The .md files moved to docs/ at v0.8.6 to clean up the public-mirror
    # root surface (10 substantive docs lifted out of root). The destination
    # paths inside the wheel package stay flat at framecheck_mcp/<NAME>.md
    # so mcp_resources.py runtime path resolution (frame-check://methodology,
    # frame-check://spec/frame-divergence/v1/part-1, etc.) keeps working
    # against the wheel layout it has always seen.
    ("data", "data"),
    ("calibration", "calibration"),
    ("validation", "validation"),
    # METHODOLOGY.md stays at root (the most-cited public document; the
    # v0.8.5 wheel METADATA's `Methodology` Project-URL points at the
    # root path, so moving it would break that link on every adopter's
    # PyPI page until the next cut). Other substantive docs moved to
    # docs/ at v0.8.6 per the public-mirror root cleanup.
    ("METHODOLOGY.md", "METHODOLOGY.md"),
    ("docs/MCP_SERVER.md", "MCP_SERVER.md"),
    ("docs/FRAME_DIVERGENCE_v1.md", "FRAME_DIVERGENCE_v1.md"),
    ("docs/FRAME_DIVERGENCE_CONTRACT_v1.md", "FRAME_DIVERGENCE_CONTRACT_v1.md"),
    # V4_2_GAP_INVENTORY_v1.md was bundled in 0.8.x wheels but is an
    # maintainer-internal construct-honesty audit, not user-facing
    # reference content. Migrated off the public surface; not bundled
    # in subsequent releases. Existing 0.8.x PyPI wheels remain frozen
    # with the bundled copy until a yank-and-republish decision lands.
    ("pipeline_version.txt", "pipeline_version.txt"),
]


def _should_skip(rel_dir: str, name: str) -> bool:
    """Decide whether to exclude `name` from staging when copying the
    directory whose path relative to the repo root is `rel_dir`.

    Returns True to exclude (file or subdirectory). The exclusion list
    is the staging-time enforcement of RELEASE_PREP_v1.md Section 3
    plus the maintainer-internal items named in LEAKAGE_AUDIT_v1.md.

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
    # are not runtime resources. RELEASE_PREP_v1.md Section 3.
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

    # data/frame_library/: maintainer-internal canon-development audits
    # and the reviewer-recruitment dossiers. AI-authored audits
    # (AUDIT_*, ADJACENCY_*, DETECTION_RULE_*) are research-internal;
    # the promotions/ subtree is reviewer-engagement material.
    # See LEAKAGE_AUDIT_v1.md Findings 3, 13, 15.
    if rel_dir == "data/frame_library":
        if name == "promotions":
            return True
        if fnmatch.fnmatch(name, "AUDIT_*.md"):
            return True
        if fnmatch.fnmatch(name, "ADJACENCY_*.md"):
            return True
        if fnmatch.fnmatch(name, "DETECTION_RULE_*.md"):
            return True

    # data/worked_examples/: scaffolding (template + internal review)
    # follows the build_corpus_site.py convention: leading-underscore
    # files are not rendered as entries. See LEAKAGE_AUDIT_v1.md
    # Findings 2 and 7.
    if rel_dir == "data/worked_examples":
        if name.startswith("_") and name.endswith(".md"):
            return True

    # validation/decision_readiness/: operator CLI scripts. Only the
    # data subdirectories (results/, corpus/) are runtime resources for
    # the MCP server. See LEAKAGE_AUDIT_v1.md Finding 16.
    if rel_dir == "validation/decision_readiness":
        if name.endswith(".py"):
            return True

    # validation/decision_readiness/results/{date}-{hash}/: drop the
    # cross_check.{json,md} files. Their `aggregate_source` /
    # "Aggregate file:" fields contain the producer's absolute path
    # (operator dev machine) and the files are not consumed by
    # mcp_server.py. aggregate.{json,md} remain. See
    # LEAKAGE_AUDIT_v1.md Finding 1.
    parts = rel_dir.split("/")
    if (
        len(parts) == 4
        and parts[0] == "validation"
        and parts[1] == "decision_readiness"
        and parts[2] == "results"
    ):
        if name in ("cross_check.json", "cross_check.md"):
            return True

    # calibration/: operator CLI scripts. Only results/ ships.
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
    exclusions enforce RELEASE_PREP_v1.md Section 3 + the LEAKAGE_AUDIT
    findings; see _should_skip.
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
