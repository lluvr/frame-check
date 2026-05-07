"""Pre-commit gate: catch unconditional top-level imports from wheel-
bundled modules to source-tree modules that are NOT in pyproject.toml
[tool.setuptools] py-modules.

The 0.8.6/0.8.7 release leak (mcp_compose.py started importing
`manifest` unconditionally; manifest.py was not added to py-modules;
the wheel shipped without it; frame_check + frame_compare tools failed
at runtime with ModuleNotFoundError) was caught by the conformance
driver, but only because that ran during 0.8.8's release-orchestrator
preflight. A static check at commit time catches the same class of bug
several layers earlier.

Discipline: every wheel-bundled module's import graph must close
within (a) the Python standard library, (b) declared external
dependencies in pyproject.toml `dependencies`, (c) other modules in
py-modules, OR (d) a `try / except ImportError` block (lazy / web-app
side imports of modules that are intentionally not bundled).

This script reports:
  - top-level unconditional imports inside wheel-bundled modules that
    resolve to a source-tree top-level .py file NOT in py-modules.

False positives the script intentionally accepts:
  - imports inside `try: / except ImportError:` blocks (skipped; the
    runtime catches the missing module gracefully).
  - imports inside conditional bodies (skipped for the same reason).

Exit codes:
  0  no violations.
  1  violations found. The caller (pre-commit) blocks the commit; the
     developer must either add the import target to py-modules
     (correct fix, the module is needed) or wrap the import in a
     try / except (the module is web-app-side and absence is
     intentional).

Run standalone:  python3 scripts/check_wheel_imports.py
"""
from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _wheel_modules() -> set[str]:
    """Read the [tool.setuptools] py-modules list from pyproject.toml."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return set(data.get("tool", {}).get("setuptools", {}).get("py-modules", []))


def _source_tree_top_level() -> set[str]:
    """Return the set of every .py module name at the source-tree
    root."""
    return {
        f.stem for f in REPO_ROOT.iterdir()
        if f.is_file() and f.suffix == ".py" and f.stem != "setup"
    }


def _unconditional_imports(path: Path) -> set[str]:
    """Return the names of modules that `path` imports unconditionally
    (at any nesting depth). Imports inside try / except blocks are
    treated as lazy and skipped, since the runtime catches ImportError
    gracefully there. Imports inside function bodies, class bodies,
    or unconditional `if` branches still count as "will fire when
    that code path runs"; if the imported module is missing from the
    wheel, the call site fails at runtime."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return set()
    names: set[str] = set()

    class ImportScanner(ast.NodeVisitor):
        def visit_Try(self, node: ast.Try) -> None:
            # An import inside `try:` is lazy iff at least one except
            # handler catches ImportError (or a bare except). Visit
            # the orelse and finalbody normally; treat the try body
            # as lazy.
            catches_import_error = any(
                _handler_catches_import_error(h) for h in node.handlers
            )
            if not catches_import_error:
                # `try` without ImportError handler: the body's imports
                # still propagate out, so they count as unconditional.
                for stmt in node.body:
                    self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)
            for stmt in node.finalbody:
                self.visit(stmt)
            for handler in node.handlers:
                for stmt in handler.body:
                    self.visit(stmt)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                names.add(alias.name.split(".")[0])

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module:
                names.add(node.module.split(".")[0])

    ImportScanner().visit(tree)
    return names


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True  # bare except catches everything
    # Match `except ImportError`, `except ModuleNotFoundError`,
    # `except Exception`, `except BaseException`, or tuple forms that
    # include any of those. `Exception` and `BaseException` are valid
    # because both transitively catch ImportError.
    targets = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    catching = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
    for t in targets:
        if isinstance(t, ast.Name) and t.id in catching:
            return True
        if isinstance(t, ast.Attribute) and t.attr in catching:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    bundled = _wheel_modules()
    source_top = _source_tree_top_level()
    violations: list[tuple[str, str]] = []
    for mod in sorted(bundled):
        path = REPO_ROOT / f"{mod}.py"
        if not path.is_file():
            # Module declared in py-modules but missing from the source
            # tree. setup_requires would catch this at build time; not
            # in scope for this gate.
            continue
        for imp in _unconditional_imports(path):
            if imp in source_top and imp not in bundled:
                violations.append((mod, imp))
    if violations:
        print(
            "ERROR: wheel-bundled modules import source-tree top-level "
            "modules that are NOT in pyproject.toml py-modules.",
            file=sys.stderr,
        )
        print(
            "These imports are unconditional (module-scope, not in a "
            "try / except ImportError block); the wheel will fail at "
            "runtime with ModuleNotFoundError on a fresh install.",
            file=sys.stderr,
        )
        print(file=sys.stderr)
        for bundled_mod, missing_imp in violations:
            print(
                f"  {bundled_mod}.py imports `{missing_imp}` "
                f"(missing from py-modules)",
                file=sys.stderr,
            )
        print(file=sys.stderr)
        print(
            "Fix options:",
            file=sys.stderr,
        )
        print(
            "  1. Add the imported module to pyproject.toml "
            "[tool.setuptools] py-modules (and the matching "
            "INCLUDE_FILES list in scripts/_release_lib/extract.py "
            "for the public mirror) if the import is intentional and "
            "the module belongs in the wheel.",
            file=sys.stderr,
        )
        print(
            "  2. Wrap the import in try / except ImportError if the "
            "module is web-app-side and the wheel-bundled code path "
            "should silently skip its features when absent.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
