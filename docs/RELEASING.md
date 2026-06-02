# Releasing Frame Check

This document is the maintainer's reference for cutting a Frame Check
MCP release. Releases ship through CI from this repository on
annotated tag push; no laptop publish path exists in the
current architecture.

## Release pipeline (overview)

A tag matching `v*` (annotated) triggers `.github/workflows/publish.yml`,
which runs five jobs in sequence:

1. **`preflight`**: verifies the destination repository state. Fails
   if the repo is archived, disabled, or its default branch has
   changed between when the tag was authored and when CI begins,
   closing the class of incident where a release proceeds against a
   destination whose state the contributor cannot have known.
2. **`build`**: checkouts at full depth, bakes the git SHA into
   `pipeline_version.txt`, runs the version-sync gate (pyproject vs
   `mcp_server.SERVER_VERSION`) and the tag-vs-pyproject gate, builds
   the wheel via `python -m build --wheel`, validates wheel contents
   (FVS-001 + FRAME_DIVERGENCE_CONTRACT_v1.md must be present), runs
   the smoke test against the installed wheel in a clean venv, and
   produces a sigstore build-provenance attestation for the wheel.
3. **`publish-to-testpypi`**: runs only for pre-release tags
   (`vX.Y.Zrc1`, `vX.Y.Z.dev0`, `vX.Y.ZaN`, `vX.Y.ZbN`). Uploads to
   TestPyPI via Trusted Publishing (OIDC).
4. **`publish-to-pypi`**: runs only for final tags (no rc / dev / a
   / b suffix). Uploads to PyPI via Trusted Publishing.
5. **`github-release`**: creates a GitHub release with the wheel
   attached. The release body is the annotated tag message, which by
   convention carries the matching `CHANGELOG.md` section so
   `git show vX.Y.Z` and the GitHub release page show identical
   release notes.

Every job past `preflight` runs only if the preflight reported
`destination_writable=true`. There is no path to publish past an
archived destination.

## Cutting a release (step by step)

Replace `1.0.13` with the version being cut.

```bash
# 1. Confirm working tree is on master and up to date.
git checkout master
git pull --ff-only origin master

# 2. Verify all CI gates pass on master.
bash scripts/canon_audit.sh   # rc=0
gitleaks detect --no-banner   # no leaks
python3 -m pytest -q          # all green

# 3. Bump version in two places.
#    - pyproject.toml [project] version
#    - mcp_server.py SERVER_VERSION
# These must match exactly; the CI version-sync gate enforces this.

# 4. Update CHANGELOG.md.
#    Move the [Unreleased] block to [1.0.13] - YYYY-MM-DD with a
#    short narrative describing what shipped. Keep the Unreleased
#    header above for the next cycle.

# 5. Commit the cut.
git add pyproject.toml mcp_server.py CHANGELOG.md
git commit -m "Cut v1.0.13 release"

# 6. Tag with the CHANGELOG section as the annotation.
#    `awk` extracts the [1.0.13] block; `git tag -a -m` sets the
#    annotated tag message. The GitHub release body is auto-derived
#    from this annotation.
git tag -a v1.0.13 -m "$(awk '/^## \[1.0.13\]/{flag=1; next} /^## \[/{flag=0} flag' CHANGELOG.md)"

# 7. Push the commit and the tag. Order matters: the tag push is
#    what triggers the publish workflow, and the workflow's
#    tag-vs-pyproject gate fetches the tag's commit which must be
#    on master.
git push origin master
git push origin v1.0.13

# 8. Watch the workflow.
gh run watch -R lluvr/frame-check
```

## Version-string discipline

`mcp_server.SERVER_VERSION` is exposed in the MCP `initialize`
handshake; clients see the version on connect. It must match the
PyPI wheel's `pyproject.toml` version. The CI version-sync gate
enforces this at every tag push.

The convention is **strict semver** (`M.m.p`, no suffixes) at the
tag boundary. Pre-release work uses `M.m.p.devN`, `M.m.p{rc,a,b}N`
in pyproject during the dev-build window and the suffix is dropped
at cut time.

Do **not** pre-bump `SERVER_VERSION` past the cut version (e.g.,
do not set `SERVER_VERSION = "1.0.14"` immediately after cutting
`1.0.13`). The version-sync gate hard-fails on drift.

## Pre-release flow

For any release whose CHANGELOG narrative needs adopter-side review
before the final cut, tag a pre-release first:

```bash
# Pre-release tag.
git tag -a v1.0.13rc1 -m "$(awk '/^## \[1.0.13/{flag=1; next} /^## \[/{flag=0} flag' CHANGELOG.md)"
git push origin v1.0.13rc1
```

The publish workflow routes pre-release tags to TestPyPI (not PyPI).
Verify the artifact installs cleanly:

```bash
python -m venv /tmp/fc-rc1
/tmp/fc-rc1/bin/pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  frame-check-mcp==1.0.13rc1
/tmp/fc-rc1/bin/frame-check-mcp --version
```

If the rc looks good, drop the rc suffix and cut the final tag.

## Yanking a release

A yank removes a release from PyPI's default-resolution surface
without deleting the artifact. Use yank when a published release
has a defect serious enough that no adopter should pin to it but
adopters who already pinned should not have their installs break.

```bash
twine yank frame-check-mcp 1.0.13 --reason "<short reason>"
```

Document the yank in the next release's CHANGELOG narrative under a
"Note on prior versions" section.

## Recovery from a botched release

If the wrong artifact reaches PyPI (wrong version, missing file,
unintended content), the recovery sequence is:

1. **Yank** the bad version (above) so new installs don't pick it
   up. The artifact stays available for adopters with explicit pins.
2. **Cut a fix version** (`1.0.13` becomes `1.0.14`, not retried with
   the same number). PyPI never reuses version numbers; the bad one
   is burned.
3. **Document** in CHANGELOG: what shipped, why it was bad, what
   the fix is, what adopters should do. Place this under the new
   version's narrative; do not silently replace the bad version's
   entry.

## Trusted Publishing setup (one-time, manual)

The publish workflow uses PyPI's Trusted Publishing (OIDC) so the
GitHub-issued workflow identity authenticates against PyPI without
an API token. Configure once at:

- https://pypi.org/manage/project/frame-check-mcp/settings/publishing/

Settings:

- **Owner**: `Clarethium`
- **Repository name**: `frame-check`
- **Workflow filename**: `publish.yml`
- **Environment name**: `pypi` (for final releases)

Repeat for TestPyPI:

- https://test.pypi.org/manage/project/frame-check-mcp/settings/publishing/
- Same settings, environment name `testpypi`.

Add corresponding GitHub environments at
`https://github.com/lluvr/frame-check/settings/environments`
and protect them with branch-restriction (only `master` can deploy
to `pypi`).

Until this manual setup lands, the `publish-to-pypi` and
`publish-to-testpypi` jobs will fail at the OIDC exchange step. The
build / validation / GitHub-release stages still run and validate
the artifact.

## Release notes format

Each release's CHANGELOG section is the source of truth for both
the annotated tag message and the GitHub release page. Keep the
narrative consistent with [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):

- Use `## [X.Y.Z] - YYYY-MM-DD` as the version heading.
- Group changes under categorized subheadings (`### Fixed`, `###
  Changed`, `### Added`, `### Removed`).
- Keep the prose adopter-facing: explain what changed and why an
  adopter should care, not internal mechanics.
- For yanks of prior versions, add a "Note on prior versions"
  subsection at the end.

## Reproducibility

The wheel is built from the tag commit alone; no developer-machine
state contributes. To reproduce a release locally:

```bash
git checkout v1.0.13
python -m pip install --upgrade build
python -m build --wheel
# dist/frame_check_mcp-1.0.13-py3-none-any.whl
```

Wheel content (file list, hashes) should match the artifact on PyPI
modulo build timestamp. Sigstore attestations from the CI build are
attached to the GitHub release for cryptographic provenance.
