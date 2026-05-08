"""Public-extract inventory discipline tests.

Pins the contract that every test file in
`scripts/_release_lib/extract.py:INCLUDE_FILES` is structurally
shippable to the public mirror -- i.e., every module it imports at
the top level is resolvable inside the wheel-bundled subset
(`pyproject.toml [tool.setuptools] py-modules`) or under an
`INCLUDE_DIRS` directory. A drift here is the bug class that put
`Clarethium/frame-check` on a red-CI badge for ~3 days post-v0.8.3:
15 test files were shipping publicly while their target modules
were operator-only, every one of those tests ImportError'd on the
public mirror's `python3 run_tests.py` (commit 112ffbd closes the
backlog; this test prevents the same bug class from recurring).

The discipline pin: a test ships publicly iff every module it
imports resolves on the public mirror's installed surface. The
inverse (drop the test from `INCLUDE_FILES`) is the structural
fix; the test below is the regression bar that catches the
drift at PR time.

Two test functions:

  - `test_every_shipped_test_imports_resolve_on_public_mirror`
    enumerates every `test_*.py` in `INCLUDE_FILES`, parses its
    top-level imports, and asserts each local import names a
    module that ships publicly. Failures name the test file +
    missing module + the three resolution options (add the
    module to py-modules, drop the test from INCLUDE_FILES,
    or gate the import with `pytest.importorskip` for a class /
    function that exercises both surfaces).

  - `test_every_py_module_in_pyproject_has_a_source_file`
    asserts every name in `pyproject.toml [tool.setuptools]
    py-modules` resolves to a `<name>.py` at the repo root.
    Catches the inverse drift class: a name in py-modules whose
    source file was renamed or removed, which would crash
    `import mcp_server` on the wheel surface in a clean
    environment.

Both tests run in <100ms (pure source-grep / AST-walk; no
subprocess). Run on every PR via `run_tests.py PYTEST_SUITES`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# `scripts/_release_lib/extract.py` is upstream-only by design (it
# lives in `EXCLUDE_PATHS` in itself; the public mirror does not ship
# the extract logic for the same reason it does not ship
# `release.py`: both reference credentials and target-repo
# configuration that have no use to adopters). The two tests in this
# file that read INCLUDE_FILES / INCLUDE_DIRS gate on the file's
# presence so the test ships and skips cleanly on the public mirror,
# runs upstream where it can do its inventory check.
_EXTRACT_PY = REPO_ROOT / "scripts" / "_release_lib" / "extract.py"
_UPSTREAM_TREE = _EXTRACT_PY.exists()
_UPSTREAM_SKIP_REASON = (
    "scripts/_release_lib/extract.py not present; "
    "this is a public-mirror tree (the file is upstream-only by "
    "design via its own EXCLUDE_PATHS entry). The inventory "
    "discipline pins are upstream-side checks."
)


# ── Helpers ──────────────────────────────────────────────────────────


def _read_pyproject_py_modules() -> set[str]:
    """Return the set of names listed under [tool.setuptools] py-modules.

    Hand-parsed because pyproject.toml is small and adding a TOML
    dep just for this test is heavier than the test itself. Match
    the same pattern test_version_coherence.py uses (regex on the
    list literal); fail loudly if the file shape changes.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"py-modules\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if m is None:
        raise AssertionError(
            "pyproject.toml shape change: could not find "
            "`py-modules = [...]` block. Update _read_pyproject_py_modules "
            "or restore the historical shape."
        )
    body = m.group(1)
    names = re.findall(r'"([a-z_][a-z0-9_]*)"', body)
    return set(names)


def _read_include_files_and_dirs() -> tuple[list[str], list[str]]:
    """Return (INCLUDE_FILES, INCLUDE_DIRS) lists from extract.py.

    Source-grep rather than import to avoid pulling in the extract
    module's heavy dependencies (subprocess / shutil / setup.py
    coupling) just to read two list literals.
    """
    text = (REPO_ROOT / "scripts" / "_release_lib" / "extract.py").read_text(encoding="utf-8")

    files_match = re.search(
        r"^INCLUDE_FILES\s*=\s*\[(.*?)\n\]", text, re.MULTILINE | re.DOTALL,
    )
    dirs_match = re.search(
        r"^INCLUDE_DIRS\s*=\s*\[(.*?)\n\]", text, re.MULTILINE | re.DOTALL,
    )
    if files_match is None or dirs_match is None:
        raise AssertionError(
            "extract.py shape change: could not find INCLUDE_FILES "
            "or INCLUDE_DIRS list literal. Update "
            "_read_include_files_and_dirs or restore the historical "
            "shape."
        )
    files = re.findall(r'"([^"]+)"', files_match.group(1))
    dirs = re.findall(r'"([^"]+)"', dirs_match.group(1))
    return files, dirs


def _public_resolvable_modules(
    py_modules: set[str], include_dirs: list[str],
) -> set[str]:
    """Return module names resolvable on the public mirror.

    Public-resolvable = either listed in `py-modules` (wheel-bundled
    root-level module) or available as a top-level submodule under
    one of `INCLUDE_DIRS` (e.g., `framecheck_mcp.something`,
    `scripts.detector_empirics`). The set is the upper bound on
    "what a test running on the public mirror can `import` and
    have it resolve."

    Builtin / third-party modules are tracked separately via the
    `_is_stdlib_or_thirdparty` heuristic; this helper ONLY returns
    LOCAL names.
    """
    resolvable = set(py_modules)
    for rel_dir in include_dirs:
        dir_path = REPO_ROOT / rel_dir
        if not dir_path.is_dir():
            continue
        for entry in dir_path.iterdir():
            if entry.is_file() and entry.suffix == ".py":
                resolvable.add(entry.stem)
            elif entry.is_dir() and (entry / "__init__.py").exists():
                resolvable.add(entry.name)
    return resolvable


def _stdlib_module_set() -> set[str]:
    """Return the set of stdlib top-level module names.

    Uses sys.stdlib_module_names (Python 3.10+) which is the
    authoritative built-in. The test suite requires Python 3.10+
    per pyproject.toml `requires-python`.
    """
    return set(sys.stdlib_module_names)


# Third-party modules that ship as wheel dependencies. The list is
# small and explicit so a future addition is a deliberate edit
# rather than implicit import-magic. Keep in sync with
# `pyproject.toml [project] dependencies` plus the test extras.
_KNOWN_THIRD_PARTY = {
    "yaml",          # PyYAML, declared in dependencies
    "pytest",        # test extras
    "openai",        # optional, gated
    "anthropic",     # optional, gated (web-side; not in py-modules)
    "google",        # google.genai, optional
    "fastapi",       # web-side; tests using it gate on app presence
    "starlette",     # web-side
    "uvicorn",       # web-side
    "requests",      # transitive
}


def _local_imports_in(test_file: Path) -> set[str]:
    """Return the set of local module names imported by `test_file`.

    Walks the AST so we catch top-level `import x` and `from x import y`
    forms. Function-local imports (the `pytest.importorskip(...)` and
    `pytest.mark.skipif(... find_spec ...)` patterns the polish work
    used) live INSIDE function bodies and are correctly excluded -- a
    function-local import is not a structural ship-time dependency
    because the test class is gated to skip when the module is absent.

    Local = "not stdlib, not known third-party." False positives here
    show up as test failures naming a module the user can either add
    to `py-modules` / `INCLUDE_DIRS`, allowlist via
    `_KNOWN_THIRD_PARTY`, or gate the import.
    """
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except SyntaxError as e:
        raise AssertionError(
            f"{test_file.name} failed to parse: {e}. Fix the "
            f"syntax error before this test can run."
        )
    imports: set[str] = set()
    stdlib = _stdlib_module_set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in stdlib or top in _KNOWN_THIRD_PARTY:
                    continue
                imports.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:  # relative import
                continue
            if node.module is None:
                continue
            top = node.module.split(".")[0]
            if top in stdlib or top in _KNOWN_THIRD_PARTY:
                continue
            imports.add(top)
    return imports


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _UPSTREAM_TREE, reason=_UPSTREAM_SKIP_REASON)
def test_every_shipped_test_imports_resolve_on_public_mirror():
    """Every `test_*.py` listed in `INCLUDE_FILES` must have all
    its top-level local imports resolvable on the public mirror.

    The discipline closed by 112ffbd: a test ships publicly iff
    every module it imports is in `pyproject.toml` py-modules or
    under `INCLUDE_DIRS`. Future-drift catcher: if a contributor
    adds `test_new_feature.py` to `INCLUDE_FILES` that imports
    `feature_x` (operator-only), this test fails at PR time
    naming the offending pair plus the three resolution options.

    Function-local imports (the `pytest.importorskip(...)` pattern)
    are EXCLUDED from the check by design: a class or function
    that gates its import via `pytest.importorskip` ships
    cleanly because the gate skips the test when the module is
    absent. Only top-level (module-load-time) imports are
    counted because those are the ones that ImportError-fail
    the whole file at collection if the module is absent.
    """
    files, dirs = _read_include_files_and_dirs()
    py_modules = _read_pyproject_py_modules()
    resolvable = _public_resolvable_modules(py_modules, dirs)

    # Tests in INCLUDE_FILES can live at root ("test_X.py") or under
    # `tests/` ("tests/test_X.py") per the 0.8.5 organization. Both
    # shapes are supported; the existence check uses the path
    # verbatim against REPO_ROOT.
    test_files = [
        REPO_ROOT / f for f in files
        if f.endswith(".py") and (
            f.startswith("test_") or f.startswith("tests/test_")
        )
    ]

    failures: list[str] = []
    for test_file in test_files:
        if not test_file.exists():
            failures.append(
                f"{test_file.name}: listed in INCLUDE_FILES but does "
                f"not exist at {test_file}; remove from INCLUDE_FILES "
                f"or restore the file"
            )
            continue
        local_imports = _local_imports_in(test_file)
        for mod in sorted(local_imports):
            if mod not in resolvable and mod != test_file.stem:
                failures.append(
                    f"{test_file.name} imports `{mod}` at module "
                    f"top-level, but `{mod}` is not in pyproject "
                    f"py-modules and not under INCLUDE_DIRS. "
                    f"This will ImportError on the public mirror's "
                    f"`python3 run_tests.py`. Resolution options: "
                    f"(a) add `{mod}` to py-modules + INCLUDE_FILES "
                    f"if it is wheel-bundle-relevant; "
                    f"(b) drop {test_file.name} from INCLUDE_FILES "
                    f"if the test is upstream-only; "
                    f"(c) move the `import {mod}` inside a function "
                    f"body and gate the test with "
                    f"`pytest.importorskip('{mod}')` if the test "
                    f"covers both wheel-bundled AND upstream-only "
                    f"surfaces."
                )

    assert not failures, (
        f"{len(failures)} INCLUDE_FILES inventory drift(s) detected. "
        f"Each will fail the public mirror's CI on the next sync. "
        f"Details:\n  - " + "\n  - ".join(failures)
    )


def test_every_py_module_in_pyproject_has_a_source_file():
    """Every name in `pyproject.toml [tool.setuptools] py-modules`
    must have a corresponding `<name>.py` at the repo root.

    Catches the inverse drift class to the test above: a module
    name in `py-modules` whose source file was renamed or
    removed without updating pyproject. The wheel build would
    fail in that case, but the failure surfaces at release-time
    via `lift_dry_run` step 2 (build wheel) -- this test surfaces
    it at PR time so the commit that introduced the drift is the
    commit that fails CI.
    """
    py_modules = _read_pyproject_py_modules()
    missing: list[str] = []
    for name in sorted(py_modules):
        if not (REPO_ROOT / f"{name}.py").exists():
            missing.append(
                f"`{name}` listed in pyproject py-modules but no "
                f"`{name}.py` at {REPO_ROOT}. Either restore the "
                f"file or remove the name from py-modules."
            )
    assert not missing, (
        f"{len(missing)} py-modules name(s) without source files:\n"
        f"  - " + "\n  - ".join(missing)
    )


@pytest.mark.skipif(not _UPSTREAM_TREE, reason=_UPSTREAM_SKIP_REASON)
def test_every_test_in_run_tests_py_suites_exists_or_is_documented_skip():
    """Every test_*.py listed in `run_tests.py` SUITES /
    PYTEST_SUITES must either exist at the repo root OR be
    structurally-skipped on the public mirror by design (i.e., the
    file is upstream-only and intentionally absent on the public
    extract). The SKIP path is documented inside `run_tests.py
    _run_and_record` (missing files emit a SKIP line and omit
    from `results`); this test pins the upstream contract that
    every declared suite resolves to a real file.

    Catches typos in SUITES / PYTEST_SUITES and tests that were
    deleted but not removed from the runner.
    """
    text = (REPO_ROOT / "run_tests.py").read_text(encoding="utf-8")
    suites: list[str] = []
    for block_re in (
        r"^SUITES\s*=\s*\[(.*?)\n\]",
        r"^PYTEST_SUITES\s*=\s*\[(.*?)\n\]",
    ):
        m = re.search(block_re, text, re.MULTILINE | re.DOTALL)
        if m is None:
            raise AssertionError(
                "run_tests.py shape change: SUITES or PYTEST_SUITES "
                "list literal not found. Update test or restore shape."
            )
        suites.extend(re.findall(r'"([^"]+\.py)"', m.group(1)))

    missing: list[str] = []
    for suite in suites:
        # Tests can live at REPO_ROOT/<suite> (legacy / public-mirror
        # back-compat) or REPO_ROOT/tests/<suite> (the 0.8.5+ canonical
        # location). Both shapes are accepted; the check is "exists
        # somewhere we'd find it" not "exists at exactly this path".
        if not (REPO_ROOT / suite).exists() and not (REPO_ROOT / "tests" / suite).exists():
            missing.append(suite)
    assert not missing, (
        f"{len(missing)} run_tests.py-declared test file(s) missing "
        f"at repo root:\n  - " + "\n  - ".join(missing) + "\n"
        f"Either restore the files, remove the entries from "
        f"SUITES / PYTEST_SUITES, or (if upstream-only and "
        f"intentionally not in this checkout) document the "
        f"structural-skip path."
    )
