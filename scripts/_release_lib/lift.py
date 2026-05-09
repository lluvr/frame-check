"""Lift dry-run for `frame-check-mcp`.

Runs the full pre-publish gate sequence locally, in order, and stops
short of `twine upload`. The operator runs this before every actual
TestPyPI / PyPI lift to surface any last-mile metadata, packaging,
or runtime defect that the audit-time tests did not catch.

Sequence:

  1. Clean working state: rm dist/ build/ *.egg-info, drop staged
     framecheck_mcp/ tree (rebuild from scratch).
  2. Build wheel: `python3 -m build --wheel`.
  3. Twine check (strict): metadata, README rendering, classifier
     validity. Fails on any warning.
  4. Install into a clean target: `pip install --target /tmp/...`.
  5. Smoke import: `import mcp_server` resolves; SERVER_VERSION
     reports the expected value.
  6. CLI version mode: `frame-check-mcp --version` runs cleanly.
  7. Conformance driver: all round-trips pass against the installed
     wheel. Round-trip count depends on which optional resources are
     bundled (methodology, spec/frame-divergence/v1 parts).
  8. Final inventory check: file count, no operator-path leaks, no
     internal proxy-leaks, no audit-doc accidents bundled.
  9. URL surface check: every Project-URL in the wheel METADATA
     resolves publicly (HEAD returns < 400). This catches the
     2026-04-27 defect where 0.8.0 published with seven dead
     Project-URLs because the operator's GitHub repo was private
     and the production site was paused. Skip with --skip-urls
     for offline runs or when URLs are knowingly being staged for
     an upcoming change.
 10. Wheel content scan: no embedded references to dev-tree-only
     repositories or paused production sites survive into the
     released wheel's markdown content. The wheel-content audit
     complements the project-URL audit because the latter only
     checks metadata, not embedded link surface in shipped
     markdown. Skip with --skip-content for offline runs or
     staged releases.
 11. Quality harness gate: drive the installed wheel via
     scripts/mcp_quality_driver.py --wheel and verify the
     harness's payload-content invariants (8 layers, 39 checks)
     hold against the actual artifact about to be uploaded. Step
     7's conformance driver covers JSON-RPC envelope shape; this
     step covers payload semantics (FRAME_DIVERGENCE_CONTRACT_v1
     c1.0 invariants, reproducibility, adversarial input
     handling, real-corpus drive, frame_compare quality, render
     enum, contentHash integrity). Allows known gaps named in
     KNOWN_HARNESS_GAPS to fail without blocking lift; any
     unexpected FAIL line surfaces here and stops the operator
     before twine upload. Locks in the 38/39 baseline (D3
     teaching_questions content gap is the named known gap,
     parked for the 0.8.4 operator authoring sprint). Skip with
     --skip-quality for offline runs or staging releases.
 12. Wheel METADATA Project-URLs match pyproject canonical:
     reads the wheel METADATA's Project-URL: lines, reads the
     dev-tree pyproject.toml [project.urls], asserts the two
     {label: url} dicts are byte-for-byte identical. Catches
     the 0.8.10 class where extract.rewrite_pyproject overrode
     the canonical URLs with a stale hardcoded set.
 13. State coherence (wheel content vs PRODUCTION_STATUS):
     reads mcp_compose.py PRODUCTION_STATUS; if "active",
     scans wheel-bundled .md / .txt for the literal
     "(production paused)" outside CHANGELOG.md and fails on
     any match. Catches the 0.8.11 pre-cut class where
     extract.rewrite_content_links injected stale-state prose
     into 82 wheel-bundled files.
 14. CHANGELOG section for cut version is non-empty: locates
     either `## [<version>] - <date>` (post-cut) or
     `## [Unreleased]` (pre-cut) in CHANGELOG.md and asserts the
     section body has at least one non-blank non-heading line.
     Catches the 0.8.11 first-cut class where cut_release.py
     renamed an empty [Unreleased] to [0.8.11] and the resulting
     git tag annotation + GitHub Release body shipped with no
     description of what the version fixes.

 NOTE: a previous gate 14 ("Wheel bundles every setup.py
 _DATA_CARRIERS destination") was retired on 2026-05-08 per
 PUBLIC_CANON_DISCIPLINE.md §3d + FM-PCD-5: a gate of that shape
 mechanically prevents future leak-cleanup (dropping a leak file
 from INCLUDE_FILES would fail the lift while _DATA_CARRIERS
 still names it). The cleanup-in-progress class is handled by
 §3d's verification protocol at agent decision time, not by
 mechanical lift gates that enforce restoration.

If every step passes, prints the exact `twine upload` commands the
operator would run for TestPyPI then PyPI, with explicit "operator
runs this manually" framing. The script never invokes twine upload
itself.

Usage:

    python3 scripts/lift_dry_run.py

    # On success: prints "READY for twine upload" + exact commands.
    # On any failure: prints the failing step, exits non-zero,
    # leaves dist/ and /tmp/fc-target/ in place for inspection.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Library file lives at scripts/_release_lib/lift.py; REPO walks up
# three parents to reach the repo root (file -> _release_lib ->
# scripts -> repo). The thin wrapper at scripts/lift_dry_run.py
# imports this module rather than re-deriving REPO, so this single
# source-of-truth governs both invocation paths.
REPO = Path(__file__).resolve().parent.parent.parent
DIST = REPO / "dist"
BUILD = REPO / "build"
TARGET = Path("/tmp/fc-target")
EXPECTED_PROTOCOL_VERSION = "2024-11-05"
# Conformance driver round-trip count depends on which optional
# resources are bundled (methodology, spec/frame-divergence/v1 parts,
# worked-examples). The lift gate verifies all-pass (passed == total),
# not a fixed total. The driver emits one record per kind sampled in
# step 14 plus the fixed envelope-shape tests (steps 1-13, 15-21).


def _read_pyproject_version() -> str:
    """Reads [project] version from pyproject.toml at runtime.

    Stays correct across version bumps; replaces the hardcoded
    constant the script shipped with originally (which silently
    drifted whenever the operator lifted pyproject without
    updating the script).
    """
    path = REPO / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError(
            f"could not find [project] version in {path}"
        )
    return m.group(1)


EXPECTED_SERVER_VERSION = _read_pyproject_version()

# Internal reference patterns that must NOT appear in wheel
# content. Two layers:
#  - Shape-based artifact path patterns (generic; safe to enumerate
#    publicly): pre-registration artifact IDs and dataset directory
#    shapes that would proxy-leak internal naming conventions if
#    bundled.
#  - Specific filenames (internal; loaded from a config file
#    pointed at by FRAME_CHECK_VAULT_PATTERNS_FILE so the public source
#    does not enumerate them per discipline §5c FM-PCD-4).
_SHAPE_PATTERNS = [
    r"data/falsifications/F-\d{4}-\d{3}",
    r"\bEXP-\d{3}-data/",
]


def _load_extra_patterns() -> list[str]:
    """Load filename patterns from the internal config file.

    Empty list if the env var is unset or the file is missing. The
    public source intentionally does not enumerate which artifact
    filenames are sensitive; only the shape of "this is a maintainer-
    side artifact" reaches the public source.
    """
    import os
    cfg = os.environ.get("FRAME_CHECK_VAULT_PATTERNS_FILE")
    if not cfg:
        return []
    try:
        with open(cfg, "r", encoding="utf-8") as fh:
            return [
                line.strip()
                for line in fh
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except OSError:
        return []


VAULT_DOC_PATTERNS = _SHAPE_PATTERNS + _load_extra_patterns()


_TOTAL_STEPS = 15

# Harness FAIL substrings that are accepted as known gaps and do NOT
# block lift. Each entry should name the operator-decision gating it
# (parked sprint, deferred operator authoring, etc.) so a 3-year-out
# reviewer can see WHY this exception exists. Adding a new entry is
# an operator decision: a regression must either fix the underlying
# defect, or be explicitly accepted as a known gap by adding here
# with the gating reason.
KNOWN_HARNESS_GAPS = (
    # L7: divergence_rendering="teaching_questions" mode requires
    # per-FVS authored `**Teaching question:**` content in the
    # data/frame_library/FVS-*.md bodies; rendering wiring is
    # correct in mcp_server.py, the gap is library content. Parked
    # for a future authoring sprint.
    "teaching_questions mode adds teaching_question per record",
)


def step(num: int, label: str) -> None:
    print(f"\n[{num}/{_TOTAL_STEPS}] {label}")


def fail(msg: str) -> int:
    print(f"\nFAIL: {msg}")
    print("dist/ and /tmp/fc-target/ left in place for inspection.")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run the full lift dry-run sequence.

    `argv` defaults to `sys.argv` so the standalone wrapper at
    `scripts/lift_dry_run.py` keeps the established CLI semantics
    (`--skip-urls`, `--skip-content`, `--skip-quality` toggle the
    corresponding gate). The orchestrator passes its own argv list
    so per-step gating is configurable from `release.py` without
    relying on a process-wide `sys.argv` mutation.
    """
    if argv is None:
        argv = sys.argv

    os.chdir(REPO)

    # 1. Clean
    step(1, "Clean working state")
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
    for p in REPO.glob("*.egg-info"):
        shutil.rmtree(p)
    staged = REPO / "framecheck_mcp"
    for sub in ("data", "calibration", "validation"):
        target = staged / sub
        if target.exists():
            shutil.rmtree(target)
    for md in staged.glob("*.md"):
        md.unlink()
    pv = staged / "pipeline_version.txt"
    if pv.exists():
        pv.unlink()
    print("  OK")

    # 2. Build wheel
    step(2, "Build wheel")
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        capture_output=True, text=True, cwd=REPO,
    )
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        return fail("python -m build --wheel exited non-zero")
    wheels = list(DIST.glob("frame_check_mcp-*.whl"))
    if len(wheels) != 1:
        return fail(f"expected 1 wheel in dist/, got {len(wheels)}")
    wheel = wheels[0]
    print(f"  built: {wheel.name}")

    # 3. Twine check (strict)
    step(3, "Twine check --strict")
    twine = shutil.which("twine") or os.path.expanduser("~/.local/bin/twine")
    if not Path(twine).exists():
        return fail(
            "twine not found. Install with: "
            "pip install --user twine"
        )
    proc = subprocess.run(
        [twine, "check", "--strict", str(wheel)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or "PASSED" not in proc.stdout:
        print(proc.stdout)
        print(proc.stderr)
        return fail("twine check --strict did not pass")
    print(f"  {proc.stdout.strip()}")

    # 4. Install into clean target
    step(4, f"Install into clean {TARGET}")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    proc = subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--quiet",
            "--target", str(TARGET), str(wheel),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        return fail("pip install --target failed")
    print(f"  installed to {TARGET}")

    # 5. Smoke import
    step(5, "Smoke import + SERVER_VERSION")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TARGET)
    env.setdefault("GEMINI_API_KEY", "test-dummy-key")
    proc = subprocess.run(
        [
            sys.executable, "-c",
            ("import mcp_server; "
            "print(mcp_server.SERVER_VERSION); "
            "print(mcp_server.PROTOCOL_VERSION)"),
        ],
        capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        print(proc.stderr)
        return fail("import mcp_server raised")
    lines = proc.stdout.strip().splitlines()
    if len(lines) != 2 or lines[0] != EXPECTED_SERVER_VERSION:
        return fail(
            f"SERVER_VERSION mismatch: expected "
            f"{EXPECTED_SERVER_VERSION!r}, got {lines}"
        )
    if lines[1] != EXPECTED_PROTOCOL_VERSION:
        return fail(
            f"PROTOCOL_VERSION mismatch: expected "
            f"{EXPECTED_PROTOCOL_VERSION!r}, got {lines[1]!r}"
        )
    print(f"  SERVER_VERSION={lines[0]}  PROTOCOL_VERSION={lines[1]}")

    # 6. CLI --version mode
    step(6, "CLI: frame-check-mcp --version")
    cli = TARGET / "bin" / "frame-check-mcp"
    if not cli.exists():
        return fail(f"CLI entry point not at {cli}")
    proc = subprocess.run(
        [str(cli), "--version"],
        capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0 or EXPECTED_SERVER_VERSION not in proc.stdout:
        print(proc.stdout)
        print(proc.stderr)
        return fail(f"CLI --version did not include {EXPECTED_SERVER_VERSION}")
    first_line = proc.stdout.strip().splitlines()[0]
    print(f"  {first_line}")

    # 7. Conformance driver
    step(7, "Conformance driver (all round-trips pass)")
    driver = REPO / "scripts" / "mcp_conformance_driver.py"
    proc = subprocess.run(
        [sys.executable, str(driver)],
        capture_output=True, text=True, env=env,
    )
    summary_match = re.search(
        r"=== summary: (\d+)/(\d+) passed ===", proc.stdout,
    )
    if not summary_match:
        print(proc.stdout[-2000:])
        return fail("conformance driver did not print summary line")
    passed, total = summary_match.group(1), summary_match.group(2)
    if passed != total:
        print(proc.stdout[-2000:])
        return fail(
            f"conformance: {passed}/{total} (expected all-pass)"
        )
    print(f"  {passed}/{total} passed")

    # 8. Inventory: leak check + file count
    step(8, "Wheel inventory: leak check")
    home_leaks: list[str] = []
    vault_leaks: list[str] = []
    audit_leaks: list[str] = []
    audit_doc_names = [
        "LEAKAGE_AUDIT", "REMEDIATION_LOG", "MCP_CLIENT_CONFORMANCE",
        "PUBLISH_READINESS", "SECURITY.md", "CONTRIBUTING.md",
        "GOVERNANCE.md",
    ]
    vault_re = re.compile("|".join(VAULT_DOC_PATTERNS))
    with zipfile.ZipFile(wheel) as z:
        files = z.namelist()
        for f in files:
            if any(d in f for d in audit_doc_names):
                audit_leaks.append(f)
            if not f.endswith((".py", ".md", ".json", ".txt", ".toml")):
                continue
            try:
                content = z.read(f).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if "/home/llucic" in content:  # canon-exempt: leak-detection pattern
                home_leaks.append(f)
            if vault_re.search(content):
                vault_leaks.append(f)
    if home_leaks:
        return fail(f"operator-path leaks: {home_leaks}")
    if vault_leaks:
        return fail(f"internal proxy-leaks: {vault_leaks}")
    if audit_leaks:
        return fail(f"audit/governance docs bundled: {audit_leaks}")
    print(
        f"  {len(files)} files, 0 leaks, 0 internal refs, "
        "0 audit-doc accidents"
    )

    # 9. URL surface: every Project-URL in METADATA resolves publicly.
    skip_urls = "--skip-urls" in argv
    step(9, "URL surface check (Project-URLs resolve publicly)")
    if skip_urls:
        print("  SKIPPED (--skip-urls)")
    else:
        with zipfile.ZipFile(wheel) as z:
            md_name = next(
                n for n in z.namelist() if n.endswith(".dist-info/METADATA")
            )
            md_text = z.read(md_name).decode("utf-8", errors="ignore")
        url_lines = [
            ln for ln in md_text.splitlines()
            if ln.startswith("Project-URL:") or ln.startswith("Home-page:")
        ]
        urls: list[tuple[str, str]] = []
        for ln in url_lines:
            if ln.startswith("Project-URL:"):
                _, _, rest = ln.partition(":")
                label, _, url = rest.strip().partition(",")
                urls.append((label.strip(), url.strip()))
            else:
                _, _, url = ln.partition(":")
                urls.append(("Home-page", url.strip()))
        try:
            from urllib.request import Request, urlopen
            from urllib.error import HTTPError, URLError
        except Exception as exc:
            return fail(f"urllib import failed: {exc}")
        broken: list[tuple[str, str, str]] = []
        for label, url in urls:
            if not url:
                continue
            try:
                req = Request(url, method="HEAD",
                              headers={"User-Agent": "frame-check-lift-dry-run/1.0"})
                resp = urlopen(req, timeout=10)
                code = resp.getcode()
                if code >= 400:
                    broken.append((label, url, f"HTTP {code}"))
            except HTTPError as e:
                # Some servers (Jetty/PyPI/GitHub) reject HEAD; retry GET.
                if e.code in (405, 501):
                    try:
                        req = Request(
                            url, method="GET",
                            headers={"User-Agent": "frame-check-lift-dry-run/1.0"},
                        )
                        resp = urlopen(req, timeout=10)
                        if resp.getcode() >= 400:
                            broken.append((label, url, f"HTTP {resp.getcode()}"))
                    except Exception as exc2:
                        broken.append((label, url, f"GET fallback: {exc2}"))
                else:
                    broken.append((label, url, f"HTTP {e.code}"))
            except URLError as e:
                broken.append((label, url, f"URLError: {e.reason}"))
            except Exception as exc:
                broken.append((label, url, f"{type(exc).__name__}: {exc}"))
        if broken:
            print("  BROKEN URLs in wheel METADATA:")
            for label, url, why in broken:
                print(f"    {label}: {url}  --  {why}")
            return fail(
                f"{len(broken)} of {len(urls)} Project-URLs do not resolve "
                "publicly. Either fix the URLs in pyproject.toml + rebuild, "
                "or pass --skip-urls if this is an intentional staging release."
            )
        print(f"  {len(urls)} URLs all resolve publicly")

    # 10. Wheel content scan: no embedded references to upstream development
    #     or paused production site survive into the released wheel.
    skip_content = "--skip-content" in argv
    step(10, "Wheel content scan (no private/paused refs in shipped markdown)")
    if skip_content:
        print("  SKIPPED (--skip-content)")
    else:
        with zipfile.ZipFile(wheel) as z:
            text_members = [
                n for n in z.namelist()
                if n.endswith(".md") or n.endswith(".txt")
            ]
            text_blobs: dict[str, str] = {}
            for n in text_members:
                try:
                    text_blobs[n] = z.read(n).decode("utf-8", errors="ignore")
                except Exception:
                    continue
        # Patterns mirror the rewriter's exclusion policy in
        # scripts/extract_public_repo.py. Both gate and rewriter use a
        # negative-lookbehind to exclude the same four prefixes:
        #   `@` (email addresses like curator@frame.clarethium.com)
        #   word chars (concatenations like myframe.clarethium.com)
        #   backtick (code-span text mentions like `frame.clarethium.com`)
        #   `/` (already-absolute paths the rewriter visits separately)
        # Without this alignment the gate would flag references the
        # rewriter intentionally preserves (a doc that explains "the
        # previous form was `frame.clarethium.com/...`" is text, not a
        # live hyperlink, and gets a code span around it precisely so
        # that the rewrite pass leaves it alone).
        bad_pats = (
            (
                "upstream development repo (not publicly accessible)",
                re.compile(r"(?<![@\w`/])github\.com/lluvr/frame-check(?!-mcp)"),
            ),
            # frame.clarethium.com production pause was lifted at the
            # T-429 launch (2026-05-05). The tool is live and the
            # launch piece tells readers "Try it: frame.clarethium.com",
            # so worked-examples and FVS docs that link there are
            # accurate, not stale. The pattern stayed here through
            # 0.8.7; removing it as part of 0.8.8 release-pipeline
            # cleanup.
        )
        violations: list[tuple[str, str, int]] = []
        for label, pat in bad_pats:
            for fname, content in text_blobs.items():
                hits = len(pat.findall(content))
                if hits:
                    violations.append((label, fname, hits))
        if violations:
            print("  WHEEL CONTENT contains forbidden references:")
            for label, fname, hits in violations[:10]:
                print(f"    {label}: {fname}  ({hits} hits)")
            if len(violations) > 10:
                print(f"    ... + {len(violations) - 10} more")
            return fail(
                f"{len(violations)} content-reference violations across "
                f"{len(text_members)} wheel-bundled .md/.txt files. "
                "Run scripts/extract_public_repo.py to apply rewrite_content_links "
                "before re-building the wheel; or pass --skip-content if these "
                "references are intentionally being staged for an upcoming change."
            )
        print(f"  {len(text_members)} markdown/text files clean")

    # 11. Quality harness gate: drive the installed wheel via the
    # quality driver and verify payload-content invariants. Catches
    # regressions that step 7's conformance driver does not cover
    # (the conformance driver checks JSON-RPC envelope shape; the
    # quality driver checks the analytical fields the wheel actually
    # returns). Known gaps are accepted via KNOWN_HARNESS_GAPS; any
    # unexpected FAIL line stops the lift.
    skip_quality = "--skip-quality" in argv
    quality_driver = REPO / "scripts" / "mcp_quality_driver.py"
    if not quality_driver.exists():
        skip_quality = True
    step(11, "Quality harness (38/39 baseline; D3 teaching_questions known gap)")
    if skip_quality:
        print("  SKIPPED (--skip-quality or quality driver not in tree)")
    else:
        proc = subprocess.run(
            [sys.executable, str(quality_driver), "--wheel"],
            capture_output=True, text=True, env=env,
        )
        # Parse FAIL lines from harness output. Driver prints one
        # PASS/FAIL line per check with the form:
        #   [Lx] FAIL  <name>  -- <note>
        # The leading bracket-tag plus the FAIL token disambiguate
        # from prose that happens to contain the word "FAIL"; pattern
        # is regex-anchored to "] FAIL  " (close-bracket, space, FAIL,
        # two-spaces) which only the record() formatter produces.
        fail_pat = re.compile(r"\] FAIL  ")
        fail_lines = [
            ln.strip() for ln in proc.stdout.splitlines()
            if fail_pat.search(ln)
        ]
        unexpected = [
            ln for ln in fail_lines
            if not any(gap in ln for gap in KNOWN_HARNESS_GAPS)
        ]
        if unexpected:
            print("  UNEXPECTED harness FAILs (not in known-gaps list):")
            for ln in unexpected:
                print(f"    {ln}")
            print(proc.stdout[-2000:])
            return fail(
                f"{len(unexpected)} unexpected harness FAILs. "
                "Either fix the regression, or add the FAIL substring "
                "to KNOWN_HARNESS_GAPS in lift_dry_run.py with the "
                "operator-decision gating that justifies the exception."
            )
        summary_match = re.search(
            r"=== summary: (\d+)/(\d+) passed ===", proc.stdout,
        )
        if not summary_match:
            print(proc.stdout[-2000:])
            return fail("quality harness did not print summary line")
        passed, total = summary_match.group(1), summary_match.group(2)
        known = len(fail_lines)
        print(
            f"  {passed}/{total} passed "
            f"({known} known gap{'s' if known != 1 else ''})"
        )

    # 12. Wheel METADATA Project-URLs match dev-tree pyproject [project.urls]
    #     byte-for-byte. Catches the 0.8.10 class: extract.rewrite_pyproject
    #     (or any other pre-build mutator) overrides operator-canonical
    #     URLs with a stale fallback that resolves but diverges from
    #     intent. Gate 9 verifies URLs RESOLVE; this gate verifies they
    #     MATCH the operator's source-of-truth in pyproject.toml.
    step(12, "Wheel METADATA Project-URLs match pyproject canonical")
    import tomllib
    with open(REPO / "pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    pyproject_urls = (pyproject_data.get("project") or {}).get("urls") or {}
    if not pyproject_urls:
        return fail(
            "pyproject.toml has no [project.urls] block. Without "
            "operator-canonical URLs to compare against, this gate "
            "has no source of truth."
        )
    with zipfile.ZipFile(wheel) as z:
        md_name = next(
            n for n in z.namelist() if n.endswith(".dist-info/METADATA")
        )
        md_text = z.read(md_name).decode("utf-8", errors="ignore")
    wheel_urls: dict[str, str] = {}
    for ln in md_text.splitlines():
        if ln.startswith("Project-URL:"):
            _, _, rest = ln.partition(":")
            label, _, url = rest.strip().partition(",")
            wheel_urls[label.strip()] = url.strip()
    pyproject_normalized = {k.strip(): v.strip() for k, v in pyproject_urls.items()}
    if wheel_urls != pyproject_normalized:
        only_in_pyproject = set(pyproject_normalized) - set(wheel_urls)
        only_in_wheel = set(wheel_urls) - set(pyproject_normalized)
        differing = {
            k for k in (set(pyproject_normalized) & set(wheel_urls))
            if pyproject_normalized[k] != wheel_urls[k]
        }
        print("  WHEEL METADATA does not match pyproject.toml [project.urls]:")
        for k in sorted(only_in_pyproject):
            print(f"    only in pyproject: {k} = {pyproject_normalized[k]!r}")
        for k in sorted(only_in_wheel):
            print(f"    only in wheel:     {k} = {wheel_urls[k]!r}")
        for k in sorted(differing):
            print(f"    differs:           {k}")
            print(f"      pyproject: {pyproject_normalized[k]!r}")
            print(f"      wheel:     {wheel_urls[k]!r}")
        return fail(
            "Project-URLs in wheel METADATA diverge from pyproject.toml "
            "canonical. The 0.8.10 class. Either fix the mutator that "
            "rewrote them (likely scripts/_release_lib/extract.py), "
            "or update pyproject.toml if the new URLs are intentional."
        )
    print(f"  {len(wheel_urls)} URLs match pyproject canonical")

    # 13. State-coherence: wheel content does not contradict the
    #     mcp_compose.PRODUCTION_STATUS constant. Catches the class
    #     surfaced at the 0.8.11 pre-cut, where extract.rewrite_content_links
    #     was injecting "(production paused)" literal text into 82
    #     wheel-bundled markdown files while PRODUCTION_STATUS was
    #     "active" since 2026-05-07. The MCP server tells consumers
    #     production_status: "active" via the provenance block; the
    #     wheel content must not say otherwise. CHANGELOG.md is
    #     allowlisted because historical entries accurately describe
    #     past pause-window state and editing them would falsify the
    #     record (same precedent as scripts/check_no_em_dashes.py
    #     audit-deliverable allowlist).
    step(13, "State coherence (wheel content vs PRODUCTION_STATUS)")
    mcp_compose_path = REPO / "mcp_compose.py"
    ps_match = re.search(
        r'^PRODUCTION_STATUS\s*=\s*"(active|paused)"',
        mcp_compose_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not ps_match:
        return fail(
            f"could not find PRODUCTION_STATUS = \"active\"|\"paused\" "
            f"in {mcp_compose_path}. The state-coherence gate needs "
            f"this constant to compare against."
        )
    production_status = ps_match.group(1)
    print(f"  PRODUCTION_STATUS = {production_status!r}")
    state_violations: list[tuple[str, int]] = []
    if production_status == "active":
        # Forbidden literal: rewriter-injected stale-state claim.
        forbidden = "(production paused)"
        with zipfile.ZipFile(wheel) as z:
            for n in z.namelist():
                if not (n.endswith(".md") or n.endswith(".txt")):
                    continue
                # CHANGELOG.md historical entries describe past
                # rewriter behavior accurately; preserving them
                # protects the audit trail. Allowlist matches the
                # path basename to be wheel-layout-agnostic
                # (the file lives at framecheck_mcp/CHANGELOG.md
                # in the wheel; matching on basename also covers
                # any future relocation).
                if Path(n).name == "CHANGELOG.md":
                    continue
                try:
                    content = z.read(n).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                hits = content.count(forbidden)
                if hits:
                    state_violations.append((n, hits))
        if state_violations:
            print(
                f"  WHEEL CONTENT contains {forbidden!r} while "
                f"PRODUCTION_STATUS == 'active'. The rewriter (or some"
                f" other path) injected stale-state claims that"
                f" contradict the MCP provenance field."
            )
            for fname, hits in state_violations[:10]:
                print(f"    {fname}  ({hits} hits)")
            if len(state_violations) > 10:
                print(f"    ... + {len(state_violations) - 10} more")
            return fail(
                f"state-coherence violation: {len(state_violations)} "
                f"file(s) contain {forbidden!r} while PRODUCTION_STATUS "
                f"is 'active'. Either flip PRODUCTION_STATUS to 'paused' "
                f"(if production is genuinely paused) or remove the "
                f"injection paths in scripts/_release_lib/extract.py "
                f"(if production is active and the rewriter is stale)."
            )
        print("  no stale-state literals in shipped content")
    else:
        # production_status == "paused": no current check.
        # Future polish could verify N expected rewrites happened.
        print(f"  (no checks defined for PRODUCTION_STATUS = 'paused')")

    # Gate 14 (was: "Wheel bundles every setup.py _DATA_CARRIERS
    # destination") was retired on 2026-05-08. The gate's premise
    # (every file declared in `setup.py:_DATA_CARRIERS` must be present
    # in the wheel) mechanically prevented step 1 of any future leak-
    # cleanup: dropping a leak file from `INCLUDE_FILES` left
    # _DATA_CARRIERS pointing at it, which made the gate fail. Per
    # PUBLIC_CANON_DISCIPLINE.md §3d ("Mechanical guards must not
    # enforce restoration") and FM-PCD-5, this gate's shape is
    # forbidden. The intended catch (a cleanup-in-progress shipping
    # mid-step) is handled instead by §3d's verification protocol +
    # the canon audit, which surfaces what the wheel _should not_
    # contain rather than what it _must_ contain.

    # 14. CHANGELOG section for the cut version is non-empty: catches
    #     the first-attempted-0.8.11-cut class where cut_release.py
    #     renamed `## [Unreleased]` to `## [0.8.11] - 2026-05-08` but
    #     [Unreleased] had no body content authored, so the cut shipped
    #     with empty release notes. Tag annotation extracts the section
    #     verbatim into GitHub Release body; adopters land on a release
    #     page with no description of what shipped. The lift runs both
    #     pre-cut (dev tree, [Unreleased] is the section to author) and
    #     post-cut (orchestrator staging dir, [<version>] - <date> is the
    #     renamed section); gate 14 checks whichever applies.
    step(14, "CHANGELOG section for cut version is non-empty")
    changelog_path = REPO / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    versioned_re = re.compile(
        rf'^## \[{re.escape(EXPECTED_SERVER_VERSION)}\] - \d{{4}}-\d{{2}}-\d{{2}}\s*$',
        re.MULTILINE,
    )
    unreleased_re = re.compile(r'^## \[Unreleased\]\s*$', re.MULTILINE)
    section_match = versioned_re.search(changelog_text)
    section_label = f"[{EXPECTED_SERVER_VERSION}] - YYYY-MM-DD"
    if not section_match:
        section_match = unreleased_re.search(changelog_text)
        section_label = "[Unreleased]"
        if not section_match:
            return fail(
                f"CHANGELOG.md has neither a "
                f"'## [{EXPECTED_SERVER_VERSION}] - YYYY-MM-DD' section "
                f"nor a '## [Unreleased]' section. cut_release.py renames "
                f"[Unreleased] to [<version>] - <date>; one of the two "
                f"must exist with body content describing what the cut "
                f"version ships."
            )
    body_start = section_match.end()
    next_heading = re.search(r'^## ', changelog_text[body_start:], re.MULTILINE)
    body_end = (
        body_start + next_heading.start() if next_heading else len(changelog_text)
    )
    body_text = changelog_text[body_start:body_end]
    body_lines = [
        ln for ln in body_text.splitlines()
        if ln.strip() and not ln.lstrip().startswith('#')
    ]
    if not body_lines:
        return fail(
            f"CHANGELOG.md section '{section_label}' has no body lines "
            f"after the heading. The git tag annotation extracts this "
            f"section verbatim as the GitHub Release body; an empty "
            f"section ships a release with no description of what was "
            f"fixed. Author the release narrative under [Unreleased] "
            f"BEFORE running cut_release.py; the cut will rename it "
            f"to [<version>] - <date>."
        )
    print(
        f"  section '{section_label}' has {len(body_lines)} non-blank "
        f"body line(s)"
    )

    # ── Gate 15: canon audit on wheel content ────────────────────────
    #
    # Defense-in-depth verifier for the bdist_wheel canon-substitution
    # hook in setup.py. The hook runs at build time and applies the
    # ``canon_replacements.txt`` map to text content inside the wheel;
    # this gate extracts the wheel and runs the canonical canon_audit.sh
    # against the result. A failure here means either:
    #
    #   - the bdist_wheel hook silently no-opped (e.g., import error
    #     swallowed somewhere in the build path), or
    #   - a new §3c shape landed in the dev tree that the substitution
    #     map does not yet handle.
    #
    # Either way the lift must halt before twine upload. Replays the
    # 0.8.x leak class (wheel shipped with internal vocabulary
    # in source comments and adopter-facing markdown) exactly because
    # that class lacked any wheel-content canon audit at lift time.
    step(15, "Canon audit on wheel content")
    audit_script = Path.home() / ".claude/clarethium-internal/canon_audit.sh"
    if not audit_script.exists():
        # Internal master is not installed. Soft-warn; the
        # bdist_wheel hook is the primary defense, and the public-extract
        # path's canon audit covers the public mirror surface. The
        # gate is informational without the script.
        print(
            f"  canon_audit.sh not found at {audit_script}; skipping "
            f"wheel-content audit (informational only)"
        )
    else:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="lift-canon-audit-") as tmp:
            with zipfile.ZipFile(wheel) as z:
                z.extractall(tmp)
            audit = subprocess.run(
                ["bash", str(audit_script)],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            if audit.returncode != 0:
                # Surface the audit's findings before failing so the
                # operator sees the leak shapes inline rather than
                # having to reproduce the audit by hand.
                head = "\n".join(audit.stdout.splitlines()[:40])
                return fail(
                    f"Canon audit on wheel content failed (exit "
                    f"{audit.returncode}). Wheel ships §3c violations "
                    f"that the bdist_wheel substitution hook did not "
                    f"clear. Inspect setup.py:_CanonSubstitutedBdistWheel "
                    f"and scripts/_release_lib/canon_replacements.txt; "
                    f"either the hook failed silently or a new pattern "
                    f"shape needs to be added to the replacements file. "
                    f"First findings:\n{head}"
                )
            print("  wheel content canon-clean (zero §3c hits)")

    # All gates green.
    print("\n" + "=" * 60)
    print("READY for twine upload.")
    print("=" * 60)
    print()
    print("Operator runs ONE of these manually (this script does not):")
    print()
    print("  # TestPyPI (always lift here first):")
    print(
        f"  twine upload --repository testpypi {wheel.relative_to(REPO)}"
    )
    print()
    print("  # Verify install from TestPyPI in a clean venv:")
    print(
        "  pip install --index-url https://test.pypi.org/simple/ "
        "--no-deps frame-check-mcp"
    )
    print()
    print("  # PyPI (only after TestPyPI smoke verified clean):")
    print(f"  twine upload {wheel.relative_to(REPO)}")
    print()
    print(
        f"After publish: run `python3 scripts/cut_release.py` to tag "
        f"v{EXPECTED_SERVER_VERSION},"
    )
    print("cut CHANGELOG to release section, and bump pyproject to next dev cycle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
