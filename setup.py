"""Setuptools shim for cross-platform wheel build.

Modern packaging metadata lives in pyproject.toml (PEP 621). This file
exists to register two custom build commands:

1. ``build_py`` (``_StagedBuildPy``): copies repo-root data into
   ``framecheck_mcp/`` before setuptools packages it.
2. ``bdist_wheel`` (``_CanonSubstitutedBdistWheel``): applies the canon
   replacement map to text content inside the built wheel before it
   leaves the build directory. Symmetric with the publication-pipeline
   transform that runs against the public extract; both surfaces share
   the same substitution map so the wheel cannot drift from the public
   mirror.

Why we need (1). The repo carries data files at root (data/,
calibration/, validation/, FRAME_DIVERGENCE_CONTRACT_v1.md,
pipeline_version.txt). Various tools read those paths directly from
the repo root in dev mode. The MCP wheel needs them bundled INSIDE
the framecheck_mcp/ package so a pip-installed user gets the data
alongside the code.

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
drops research artifacts, scaffolding templates, leak-bearing
cross_check artifacts, promotion dossiers, and ablation forks that
have no runtime use to MCP consumers; making the filter the gate at
staging time means the must-exclude inventory is enforced by code
rather than by manual inspection.

Why we need (2). The wheel content is the surface adopters see when
they run ``pip install frame-check-mcp``. Without this hook, dev-tree
comments and adopter-facing markdown reach pip-install consumers
even when the public mirror is canon-clean. The canon-substitution
discipline must be symmetric: every public surface gets the same
transform.
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import sys

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
    # MCP_SERVER.md is the adopter-facing API reference (load-bearing
    # for the runtime mcp_resources.py URI registry). Stays.
    # FRAME_DIVERGENCE_CONTRACT_v1.md is the divergence-block interface
    # contract (load-bearing for adopter integration). Stays.
    #
    # The methodology paper, the frame-divergence specification draft,
    # and the v4.2 gap inventory are not bundled in the wheel. They
    # are part of the public methodology canon hosted separately at
    # github.com/Clarethium/lodestone and at
    # frame.clarethium.com/corpus/methodology/. mcp_resources.py
    # registers no URIs for those paths when their files are absent
    # from the wheel layout (the file-presence gate handles it). The
    # conformance driver's expected resource count tracks the
    # currently-bundled subset.
    ("docs/MCP_SERVER.md", "MCP_SERVER.md"),
    ("docs/FRAME_DIVERGENCE_CONTRACT_v1.md", "FRAME_DIVERGENCE_CONTRACT_v1.md"),
    ("pipeline_version.txt", "pipeline_version.txt"),
]


def _should_skip(rel_dir: str, name: str) -> bool:
    """Decide whether to exclude `name` from staging when copying the
    directory whose path relative to the repo root is `rel_dir`.

    Returns True to exclude (file or subdirectory). The exclusion list
    enforces the must-exclude inventory at staging time so the wheel
    cannot ship research artifacts, scaffolding templates, or
    dev-side audit output that has no MCP runtime use.

    `rel_dir` is POSIX-separated (forward-slash) for portability.
    """
    # Universal exclusions (any directory).
    if name == "__pycache__":
        return True
    if name.startswith(".env"):
        return True
    if name.endswith((".sqlite", ".sqlite-shm", ".sqlite-wal")):
        return True
    if name in ("circuit_breaker.json", "frame_check_observatory_state.json"):  # canon-exempt: skip-list literals
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
            "frame_library_v3",
            "frame_library_v4",
        ):
            return True
        if fnmatch.fnmatch(name, "frame_library_*_abl*"):
            return True

    # data/frame_library/: dev-side canon-development audits and the
    # reviewer-recruitment dossiers. AUDIT_*.md / ADJACENCY_*.md /
    # DETECTION_RULE_*.md files are dev-side audit output; the
    # promotions/ subtree is reviewer-engagement material. None of
    # these are part of the adopter-facing frame catalog.
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
    # files are leading-underscore-prefixed; the corpus rendering
    # convention treats them as non-rendered entries.
    if rel_dir == "data/worked_examples":
        if name.startswith("_") and name.endswith(".md"):
            return True

    # validation/decision_readiness/: dev-side CLI scripts. Only the
    # data subdirectories (results/, corpus/) are runtime resources for
    # the MCP server.
    if rel_dir == "validation/decision_readiness":
        if name.endswith(".py"):
            return True

    # validation/decision_readiness/results/{date}-{hash}/: drop the
    # cross_check.{json,md} files. Their `aggregate_source` and
    # "Aggregate file:" fields contain the producer's absolute path
    # (dev machine layout) and the files are not consumed by
    # mcp_server.py. aggregate.{json,md} remain.
    parts = rel_dir.split("/")
    if (
        len(parts) == 4
        and parts[0] == "validation"
        and parts[1] == "decision_readiness"
        and parts[2] == "results"
    ):
        if name in ("cross_check.json", "cross_check.md"):
            return True

    # calibration/: CLI scripts. Only results/ ships.
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
    exclusions are enforced via _should_skip.
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


# bdist_wheel lives at different import paths depending on which
# package version owns the command (setuptools >=70.1 vendored it from
# wheel; older setuptools defers to the wheel package). Try the
# setuptools location first; fall back to wheel.
try:
    from setuptools.command.bdist_wheel import bdist_wheel  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover -- fallback for older setuptools
    from wheel.bdist_wheel import bdist_wheel  # type: ignore[import-not-found]


class _CanonSubstitutedBdistWheel(bdist_wheel):
    """bdist_wheel command that applies canon substitutions post-build.

    Runs the wheel-mode of the canon substitution map immediately after
    the wheel is built and before bdist_wheel returns. The transform is
    in-place on the wheel file (the helper writes a sibling .tmp wheel
    and renames atomically; on failure the original is untouched).

    Without this hook, comments in dev-tree source files (mcp_server.py,
    framing.py, etc.) and adopter-facing markdown shipped under
    framecheck_mcp/ reach pip-install consumers even when the public
    mirror is canon-clean, because setuptools copies the dev-tree
    bytes into the wheel as-is.
    """

    def run(self) -> None:  # type: ignore[override]
        super().run()
        from pathlib import Path
        # Resolve the helper without polluting sys.path globally: insert,
        # import, restore. Path.parent is the repo root because this
        # setup.py lives there.
        #
        # The helper at scripts/_release_lib/extract.py is not part of
        # the public package. ImportError is the legitimate "skip"
        # signal when the helper is absent; the wheel content is already
        # canon-clean in those contexts.
        repo_root = Path(__file__).resolve().parent
        release_lib = str(repo_root / "scripts" / "_release_lib")
        added = False
        if release_lib not in sys.path:
            sys.path.insert(0, release_lib)
            added = True
        try:
            try:
                from extract import apply_canon_substitutions_to_wheel  # type: ignore[import-not-found]
            except ImportError:
                # Public extract / adopter-clone build context. Source
                # is already canon-clean; no substitution needed.
                return
        finally:
            if added:
                sys.path.remove(release_lib)
        # bdist_wheel records the produced wheel in
        # self.distribution.dist_files. Iterate that list rather than
        # globbing dist/ so a stale wheel from a prior build is not
        # touched.
        produced: list[Path] = []
        for cmd, _py_version, path in getattr(
            self.distribution, "dist_files", ()
        ):
            if cmd == "bdist_wheel":
                produced.append(Path(path))
        if not produced:
            # Fallback: dist_files API unchanged in modern setuptools but
            # defensive in case a future version reshapes it. Glob the
            # configured dist_dir for the freshest *.whl.
            dist_dir = Path(getattr(self, "dist_dir", repo_root / "dist"))
            wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime)
            if wheels:
                produced = [wheels[-1]]
        for wheel_path in produced:
            files_changed, total_subs = apply_canon_substitutions_to_wheel(
                wheel_path
            )
            if files_changed:
                print(
                    f"canon substitutions applied to wheel: "
                    f"{files_changed} files, {total_subs} replacements "
                    f"in {wheel_path.name}"
                )


setup(
    cmdclass={
        "build_py": _StagedBuildPy,
        "bdist_wheel": _CanonSubstitutedBdistWheel,
    },
)
