"""Version coherence tests.

Pin the contract that `mcp_server.py:SERVER_VERSION` matches
`pyproject.toml [project] version` (with the `.dev0` suffix stripped
when present). The orchestrator's `lift_dry_run` gate at
`scripts/_release_lib/lift.py:271` catches mismatches AT RELEASE
TIME by smoke-testing the built wheel against `_read_pyproject_
version()`. That is too late: a drift introduced between releases
stays invisible until the next cut, and an operator running the
upstream tree directly (e.g., `python3 mcp_server.py --version`)
sees a stale version with no test surface flagging it.

Why this test exists:

  - SERVER_VERSION lives at `mcp_server.py:121` and is the wheel-
    metadata-coupled string reported on the MCP `initialize`
    handshake (`serverInfo.version`). Decoupled from the
    methodology brand version (`version.py:FRAME_CHECK_VERSION`)
    per the two-axes discipline in `version.py`.
  - pyproject.toml `[project] version` is the packaging artifact
    version. The two strings answer different questions but MUST
    match per the discipline named in `version.py` ("on each wheel
    release SERVER_VERSION should bump").
  - Between releases the upstream `mcp_server.py:121` stays
    drifted at the previous-release value; the orchestrator
    rewrites it in the EXTRACTED public tree before building the
    wheel (`scripts/_release_lib/extract.py:rewrite_server_version`),
    so SHIPPED artifacts are always coherent. But the upstream
    drift between releases is still a maintenance trap: an
    operator who runs the upstream clone directly sees the wrong
    version, and any test that imports `mcp_server` and reads
    `SERVER_VERSION` against the upstream pyproject would fail
    silently.
  - This test catches the drift at PR time so it stays explicit
    rather than waiting for the release-time gate. If the
    operator wants to accept the drift between releases as a
    known pattern, this test surfaces a deliberate decision
    rather than letting silence do the work.

Discipline reference: the published-state-must-be-true rule named
in feedback notes -- the wheel METADATA version and the runtime
serverInfo.version handshake string MUST report the same value
to programmatic consumers. The orchestrator path holds this for
shipped wheels via the extract-time rewrite; this test holds it
for the upstream tree.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def _read_pyproject_version() -> str:
    """Read [project] version from pyproject.toml.

    Mirrors `scripts/_release_lib/lift.py:_read_pyproject_version`
    intentionally: same regex, same error message shape, so a
    future refactor that changes one parser also has to change
    this one and the orchestrator's lift_dry_run gate together.
    """
    path = REPO_ROOT / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError(
            f"could not find [project] version in {path}"
        )
    return m.group(1)


def _read_server_version() -> str:
    """Read SERVER_VERSION from mcp_server.py.

    Reads the literal string from the source rather than importing
    the module: importing mcp_server pulls in the full MCP server
    surface (resource cache, tool definitions, prompt templates,
    etc.) which is heavy for a single-string read AND would mask a
    syntax error elsewhere in the file as an ImportError that
    confuses the failure mode here.
    """
    path = REPO_ROOT / "mcp_server.py"
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^SERVER_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError(
            f"could not find SERVER_VERSION in {path}"
        )
    return m.group(1)


def _strip_dev_suffix(v: str) -> str:
    """Strip a trailing `.devN` suffix from a version string.

    Pyproject during a dev cycle carries `.dev0` (e.g.,
    "0.8.4.dev0") to mark the upstream tree as not-yet-released.
    The orchestrator's close_out step bumps pyproject from
    "X.Y.Z" -> "X.Y.(Z+1).dev0" after a release lands. SERVER_VERSION
    does not carry the suffix; the comparison strips it from
    pyproject side.
    """
    return re.sub(r'\.dev\d+$', '', v)


def test_server_version_matches_pyproject():
    """`mcp_server.py:SERVER_VERSION` must equal the pyproject
    `[project] version` (with `.dev0` suffix stripped).

    Failure mode pinned: a drift where SERVER_VERSION lags
    pyproject (the current 2026-04-30 state where pyproject says
    "0.8.4.dev0" but SERVER_VERSION says "0.8.3"). The orchestrator
    rewrites SERVER_VERSION on the EXTRACTED public tree before
    building the wheel (`scripts/_release_lib/extract.py:
    rewrite_server_version`), so SHIPPED wheels are always
    coherent. This test holds the upstream tree to the same
    contract so:

      (a) a developer running `python3 mcp_server.py --version`
          from the upstream clone sees the version that will ship
          on the next release, not the stale one
      (b) any future test that imports mcp_server and reads
          SERVER_VERSION against the upstream pyproject sees a
          coherent value (no silent fail)
      (c) the bump becomes a pre-release operator step (manual or
          automated) that is enforced rather than implicit

    If the operator wants to accept upstream drift between
    releases as a known pattern (i.e., not bump until release.py
    rewrites the public tree), this test will fail and the
    operator can either bump manually or update the discipline by
    deleting / weakening this test with an explicit comment. The
    failure mode being EXPLICIT is the discipline; silence is the
    failure mode the test prevents.
    """
    pyproject_version = _strip_dev_suffix(_read_pyproject_version())
    server_version = _read_server_version()

    assert pyproject_version == server_version, (
        f"SERVER_VERSION drift: pyproject [project] version is "
        f"{pyproject_version!r} (after .dev0 strip) but "
        f"mcp_server.py:121 SERVER_VERSION is {server_version!r}.\n"
        f"\n"
        f"Resolve by ONE of:\n"
        f"  (a) Bump mcp_server.py:121 SERVER_VERSION to match\n"
        f"      pyproject [project] version (the common case when\n"
        f"      pyproject was lifted but SERVER_VERSION was not).\n"
        f"  (b) Bump pyproject [project] version to match\n"
        f"      SERVER_VERSION (rare; would mean SERVER_VERSION\n"
        f"      was lifted independently of pyproject, which is\n"
        f"      against the version.py discipline).\n"
        f"  (c) If accepting upstream drift between releases is a\n"
        f"      deliberate pattern, weaken or remove this test\n"
        f"      with an explicit comment naming the decision.\n"
        f"\n"
        f"The orchestrator's release.py path always rewrites\n"
        f"SERVER_VERSION on the extracted public tree before the\n"
        f"wheel build (per scripts/_release_lib/extract.py:\n"
        f"rewrite_server_version), so SHIPPED wheels are\n"
        f"coherent regardless of upstream drift; this test holds\n"
        f"the upstream tree to the same contract."
    )


def test_pyproject_version_format():
    """pyproject [project] version must follow the
    `<major>.<minor>.<patch>[.dev<n>]` shape per PEP 440 and the
    project's release-arc convention. A future refactor that
    introduces a non-conforming version (e.g., "0.8.4-rc1" or
    "0.8.4+local") would break the orchestrator's lift_dry_run
    SERVER_VERSION rewriter (which expects PEP 440) and the
    Zenodo metadata builder. Pin the format here so a malformed
    version fails at PR time rather than during release.
    """
    v = _read_pyproject_version()
    pattern = r'^\d+\.\d+\.\d+(?:\.dev\d+)?$'
    assert re.match(pattern, v), (
        f"pyproject [project] version {v!r} does not match the "
        f"expected `<major>.<minor>.<patch>[.dev<n>]` shape per "
        f"PEP 440 + the project's release-arc convention. The "
        f"orchestrator's rewrite_server_version, the close_out "
        f"version-bump logic, and the Zenodo metadata builder "
        f"all assume this shape; a non-conforming version will "
        f"fail downstream in non-obvious ways."
    )


def test_server_version_format():
    """mcp_server.py SERVER_VERSION must follow the
    `<major>.<minor>.<patch>` shape (no `.dev` suffix; SERVER_VERSION
    is always the released-or-being-released version, never the
    next-dev placeholder). A drift to "0.8.4.dev0" or
    "0.8.4-something" indicates the file was edited by a tool that
    didn't strip the dev suffix correctly.
    """
    v = _read_server_version()
    pattern = r'^\d+\.\d+\.\d+$'
    assert re.match(pattern, v), (
        f"mcp_server.py SERVER_VERSION {v!r} does not match the "
        f"expected `<major>.<minor>.<patch>` shape. SERVER_VERSION "
        f"is always the released-or-being-released wheel version; "
        f"the `.dev<n>` suffix lives on pyproject's [project] "
        f"version only and is stripped before SERVER_VERSION is "
        f"set."
    )


# ──────────────────────────────────────────────────────────────────
# CITATION.cff coherence (multi-axis)
# ──────────────────────────────────────────────────────────────────
#
# CITATION.cff carries two version fields on independent axes,
# each tied to a different source-of-truth. Drift on either
# misrepresents the citation surface to academic + programmatic
# consumers (Zenodo metadata, GitHub citation tab, paper
# bibliographies), so each is pinned at PR time.
#
# Axis 1: top-level `version` -> version.py:FRAME_CHECK_VERSION
#   The methodology brand version. Bumps when the
#   FRAME_DIVERGENCE_CONTRACT_v1 spec bumps (c1.1 -> 1.1.0;
#   c2.0 -> 2.0.0). Decoupled from pyproject (the wheel version)
#   per the two-axes discipline in version.py.
#
# Axis 2: references[*].version where title = "Frame Vocabulary
#   Standard" -> data/frame_library/VERSION
#   The FVS catalog version. Bumps when frame library entries
#   are added, removed, or revised. Decoupled from both
#   methodology brand and wheel versions; the library can ship
#   v0.3.0 against methodology v1.0.0 against wheel v0.8.5.
#
# These tests catch the drift class similar to the SERVER_VERSION
# coherence pin above: an editor (or an automated tool) bumps one
# source of truth and forgets the citation surface. CITATION.cff
# is human-edited today; future automation that re-derives it
# from the source-of-truth files would obsolete these tests, but
# until then they are the load-bearing pins.


def _read_citation_cff() -> dict:
    """Parse CITATION.cff once. Returns the full YAML doc as
    nested dicts/lists. The CFF v1.2 schema guarantees the top-
    level keys (cff-version, version, references, etc.) so
    callers can index without defensive .get() chains.
    """
    import yaml
    path = REPO_ROOT / "CITATION.cff"
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text)


def _read_frame_check_version_constant() -> str:
    """Read FRAME_CHECK_VERSION from version.py without importing
    the module. Same parse-the-source discipline as
    _read_server_version: avoids pulling in module-level imports
    that might not be available in CI's minimal install (version.py
    is a constants file but a syntax error elsewhere could still
    mask as ImportError).
    """
    path = REPO_ROOT / "version.py"
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^FRAME_CHECK_VERSION\s*=\s*"([^"]+)"',
                  text, re.MULTILINE)
    if not m:
        raise RuntimeError(
            f"could not find FRAME_CHECK_VERSION in {path}"
        )
    return m.group(1)


def _read_frame_library_version() -> str:
    """Read the FVS catalog version from data/frame_library/VERSION.
    Single-line file; strip whitespace.
    """
    path = REPO_ROOT / "data" / "frame_library" / "VERSION"
    return path.read_text(encoding="utf-8").strip()


def test_citation_cff_top_level_version_matches_brand():
    """CITATION.cff top-level `version` must equal
    version.py:FRAME_CHECK_VERSION. Brand-version axis: tied to
    the methodology contract spec (c1.0 -> 1.0.0; c1.1 -> 1.1.0).

    Failure mode pinned: a developer bumps version.py for a
    methodology-spec revision but forgets CITATION.cff, so the
    Zenodo metadata + GitHub citation tab + paper bibliographies
    all keep advertising the previous brand version. Subsequent
    citations resolve to a snapshot that no longer matches what
    the author intended.

    Resolve drift by ONE of:
      - Bump CITATION.cff top-level version to match (the common
        case when version.py was lifted but CITATION.cff was not)
      - Bump version.py:FRAME_CHECK_VERSION to match (rare; would
        mean the brand version was lifted in CITATION.cff
        independently, against the version.py-as-source-of-truth
        discipline)
    """
    cff = _read_citation_cff()
    cff_version = cff.get("version")
    brand_version = _read_frame_check_version_constant()

    assert cff_version == brand_version, (
        f"CITATION.cff top-level version drift: "
        f"CITATION.cff says {cff_version!r}, "
        f"version.py:FRAME_CHECK_VERSION says {brand_version!r}.\n"
        f"\n"
        f"The CITATION.cff version is the methodology brand-version "
        f"axis (decoupled from wheel version per version.py "
        f"discipline). It must equal version.py:FRAME_CHECK_VERSION "
        f"so academic and programmatic consumers (Zenodo, GitHub "
        f"citation tab, paper bibliographies) cite the snapshot "
        f"the author intended."
    )


def test_citation_cff_fvs_reference_version_matches_library():
    """CITATION.cff references[*].version (where title = "Frame
    Vocabulary Standard") must equal data/frame_library/VERSION.
    FVS-catalog axis: tied to frame library entries (bumps on
    add / remove / revise per the existing library-versioning
    discipline).

    Failure mode pinned: a developer bumps data/frame_library/VERSION
    for a library revision but forgets the FVS reference block in
    CITATION.cff. Citations to "Frame Vocabulary Standard v0.2.0"
    keep resolving when the actual catalog has moved on.
    """
    cff = _read_citation_cff()
    library_version = _read_frame_library_version()

    fvs_refs = [
        ref for ref in (cff.get("references") or [])
        if (ref.get("title") or "").startswith(
            "Frame Vocabulary Standard"
        )
    ]
    assert fvs_refs, (
        "CITATION.cff has no references[] entry titled "
        "'Frame Vocabulary Standard'. The FVS catalog is the "
        "load-bearing methodology artifact and must appear in the "
        "citation surface as a separately-versioned reference. If "
        "the entry was deliberately removed, weaken or remove "
        "this test with an explicit comment naming the decision."
    )
    # If multiple FVS references exist (hypothetical: per-version
    # archived references), all must point at the current library
    # version. Today there is exactly one FVS reference.
    for ref in fvs_refs:
        ref_version = ref.get("version")
        assert ref_version == library_version, (
            f"CITATION.cff FVS reference version drift: "
            f"references entry {ref.get('title')!r} says "
            f"version={ref_version!r}, but data/frame_library/"
            f"VERSION says {library_version!r}.\n"
            f"\n"
            f"Resolve by ONE of:\n"
            f"  - Bump CITATION.cff references[*].version to "
            f"    match (common case)\n"
            f"  - Bump data/frame_library/VERSION to match (rare; "
            f"    would mean the library bumped in CITATION.cff "
            f"    first, against the file-as-source-of-truth "
            f"    discipline)"
        )


def test_citation_cff_top_level_version_format():
    """CITATION.cff top-level version must be M.m.p shape (no
    pre-release / dev suffixes). The brand version axis stays
    in semver shape; .dev0 lives on pyproject only.
    """
    cff = _read_citation_cff()
    v = cff.get("version") or ""
    pattern = r'^\d+\.\d+\.\d+$'
    assert re.match(pattern, v), (
        f"CITATION.cff top-level version {v!r} does not match the "
        f"expected `<major>.<minor>.<patch>` shape. The brand "
        f"version axis stays in semver; pre-release / dev suffixes "
        f"would confuse citation-resolution downstream."
    )


def test_citation_cff_schema_version_is_supported():
    """CITATION.cff `cff-version` must be a CFF schema version this
    project is known to handle. Pinning the schema version surfaces
    a deliberate decision when CFF spec releases a new major version
    (CFF 1.3+, 2.0+) rather than letting the upgrade slip through
    silently and break tooling that only knows CFF 1.2.

    Why this is here despite low drift frequency: the citation
    surface is academic-archival (Zenodo, paper bibliographies,
    GitHub citation tab); a silent CFF spec bump that breaks one
    of those resolvers would surface as "your citation does not
    parse" weeks or months after the actual change. Pinning the
    schema version makes the upgrade an explicit operator decision
    (read CFF migration notes, update test allowlist, verify
    consumers handle the new schema) rather than an accident.

    Update path on a deliberate CFF version upgrade: extend
    SUPPORTED_CFF_VERSIONS with the new version (and verify the
    downstream consumers named above handle it) before merging
    the CITATION.cff change.
    """
    SUPPORTED_CFF_VERSIONS = {"1.2.0"}

    cff = _read_citation_cff()
    cff_version = cff.get("cff-version")
    assert cff_version in SUPPORTED_CFF_VERSIONS, (
        f"CITATION.cff cff-version {cff_version!r} is not in the "
        f"project's known-supported set {sorted(SUPPORTED_CFF_VERSIONS)}. "
        f"This is the CFF schema version, not the project's brand "
        f"version. If a deliberate spec upgrade landed (CFF 1.3+, "
        f"2.0+), extend SUPPORTED_CFF_VERSIONS in this test after "
        f"verifying the academic-archival consumers (Zenodo, GitHub "
        f"citation tab, paper bibliographies) handle the new schema."
    )
