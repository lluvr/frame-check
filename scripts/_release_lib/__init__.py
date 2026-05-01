"""Release orchestrator library modules.

Imported by `scripts/release.py`. Each module has a single responsibility:

  state.py     -- read/write `.release/state.json` (resumability)
  lock.py      -- exclusive lock with stale-pid detection (multi-agent guard)
  log.py       -- append-only release log (audit trail)
  extract.py   -- extract public repo subset to staging (was extract_public_repo.py)
  lift.py      -- lift_dry_run gates as a library function (was lift_dry_run.py)
  close_out.py -- cut_release logic: CHANGELOG rename + dev-bump + tag (was cut_release.py)

Library modules deliberately avoid importing each other; the orchestrator
composes them. This keeps the public API small and makes unit-testing each
module independent of the others.

Architectural principle: a library module here exists only when there is
a STANDALONE CLI to preserve via a thin wrapper. The orchestrator's
twine + gh CLI + Zenodo poll + CITATION back-fill steps live directly
in `scripts/release.py` (with small subprocess helpers `_git`, `_gh`,
`_vault_decrypt`) because none of them had a prior standalone script
to refactor. This is the right boundary: introducing pypi.py /
github.py / zenodo.py modules would force generic interfaces that
nothing currently consumes; the simpler shape pays for itself.

Each refactored module preserves the standalone CLI by leaving the
original `scripts/<name>.py` as a thin wrapper that imports from here.
"""
