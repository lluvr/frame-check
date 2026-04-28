"""Bidirectional canon graph consistency tests.

The Frame Library and the decision-readiness methodology
constitute a bidirectional graph:
  - Each library entry's markdown source carries a
    "Decision-readiness implication" section (added by
    scripts/add_readiness_implications.py)
  - The methodology page lists "Related library entries" per
    dimension (in build_corpus_site.py)
  - decision_readiness.py carries DIMENSION_LIBRARY_ENTRIES
    mapping that emits per-dimension library citations into the
    profile JSON

These three sources of truth must agree. If they drift, the
graph develops broken links: a library entry that says it
affects Coverage but isn't listed under Coverage on the
methodology page, OR a methodology page Coverage section that
lists an entry whose markdown doesn't claim to affect Coverage.

This test pins the consistency in BOTH directions so neither
side can silently drift from the other.

The tests run against the source markdown / Python files, not
against the rendered corpus_site, so they catch drift before
the build runs.
"""

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
LIBRARY_DIR = REPO_ROOT / "data" / "frame_library"

# Withdrawn entries do not need to declare implications (they
# carry a withdrawal banner and are not part of the canon graph).
WITHDRAWN = {"FVS-003", "FVS-004", "FVS-018", "FVS-019"}

DIMENSIONS = [
    "coverage", "calibration", "evidence",
    "robustness", "counterfactual",
]


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def _library_implications() -> dict:
    """Returns {fvs_id: set_of_dimensions} parsed from each
    canon library entry's "Decision-readiness implication"
    section. Meta-side entries map to the empty set (they
    declare meta-side status, not affected dimensions)."""
    out = {}
    for path in sorted(LIBRARY_DIR.glob("FVS-*.md")):
        m = re.match(r"^(FVS-\d{3})_", path.name)
        if not m:
            continue
        fvs_id = m.group(1)
        if fvs_id in WITHDRAWN:
            continue
        text = path.read_text(encoding="utf-8")
        if "## Decision-readiness implication" not in text:
            out[fvs_id] = None  # missing; caught downstream
            continue
        # Pull out the section body (until next "## " heading).
        body_match = re.search(
            r"## Decision-readiness implication\s*\n(.+?)(?=\n## |\Z)",
            text, re.DOTALL,
        )
        body = body_match.group(1) if body_match else ""
        # Meta-side detection. Patterns wrap the period inside the
        # bold (e.g. "**Meta-side frame.**") in the canonical
        # implication sections; the regex tolerates either form.
        if re.search(r"\*\*Meta-side frame\.?\*\*", body) or re.search(r"\*\*Meta-meta frame\.?\*\*", body):
            out[fvs_id] = set()
            continue
        # Direct-mapping: extract bold dimension names from the
        # bullet list. Pattern: "- **Coverage**", "- **Counterfactual**", etc.
        # Case-insensitive match against the canonical dimension
        # vocabulary.
        dims = set()
        for dim in DIMENSIONS:
            # Match "**Coverage**" or "**Calibration**" etc as a
            # whole-word marker in the implication body
            pattern = r"\*\*" + dim.capitalize() + r"\*\*"
            if re.search(pattern, body):
                dims.add(dim)
        out[fvs_id] = dims
    return out


def _methodology_page_implications() -> dict:
    """Returns {dimension: set_of_fvs_ids} parsed from the
    methodology page builder's "Related library entries" sections
    in build_corpus_site.py."""
    builder = REPO_ROOT / "build_corpus_site.py"
    src = builder.read_text(encoding="utf-8")

    # Find each dimension's section: anchor on "<h3>N. {Dim}</h3>"
    # and pull library FVS-IDs from the "Related library entries"
    # paragraph that follows.
    out = {dim: set() for dim in DIMENSIONS}
    # Match the section heading allowing any attributes on the <h3>
    # (e.g. id="dim-coverage" used for deep-linking from the library hub).
    dim_to_h3_pattern = {
        "coverage": r"<h3[^>]*>1\. Coverage of perspectives</h3>",
        "calibration": r"<h3[^>]*>2\. Claim calibration</h3>",
        "evidence": r"<h3[^>]*>3\. Evidence backing</h3>",
        "robustness": r"<h3[^>]*>4\. Robustness</h3>",
        "counterfactual": r"<h3[^>]*>5\. Counterfactual thinking</h3>",
    }
    for dim, h3_pattern in dim_to_h3_pattern.items():
        # Find the section between this h3 and the next h3
        m = re.search(h3_pattern, src)
        if not m:
            continue
        h3_idx = m.start()
        next_h3 = src.find("<h3", h3_idx + 1)
        section = src[h3_idx:next_h3 if next_h3 > 0 else len(src)]
        # Extract FVS-XXX references from the Related library
        # entries paragraph specifically.
        related_match = re.search(
            r"<strong>Related library entries:</strong>\s*(.+?)</p>",
            section, re.DOTALL,
        )
        if not related_match:
            continue
        related_text = related_match.group(1)
        for fvs in re.findall(r"FVS-\d{3}", related_text):
            out[dim].add(fvs)
    return out


def _module_dimension_entries() -> dict:
    """Returns {dimension: set_of_fvs_ids} from the
    DIMENSION_LIBRARY_ENTRIES constant in decision_readiness.py."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from decision_readiness import DIMENSION_LIBRARY_ENTRIES
    finally:
        sys.path.pop(0)
    return {dim: set(entries) for dim, entries in DIMENSION_LIBRARY_ENTRIES.items()}


def test_every_canon_entry_declares_implication():
    """Every non-withdrawn library entry must carry the
    'Decision-readiness implication' section. Either as a
    direct mapping (bullet list naming dimensions) OR as a
    meta-side declaration. This is the load-bearing curatorial
    contract."""
    print("=== canon graph: every entry declares implication ===")
    implications = _library_implications()
    missing = [fvs for fvs, dims in implications.items() if dims is None]
    _check(
        not missing,
        f"library entries missing 'Decision-readiness implication' "
        f"section: {missing}",
    )
    print(f"  PASS  ({len(implications)} canon entries verified)\n")


def test_library_to_methodology_consistency():
    """For every library entry that declares it affects a
    dimension, the methodology page's 'Related library entries'
    for that dimension must include the entry. Catches the case
    where a library entry is updated to claim it affects X but
    the methodology page wasn't updated to reference it back."""
    print("=== canon graph: library -> methodology consistency ===")
    library = _library_implications()
    methodology = _methodology_page_implications()
    drifts = []
    for fvs_id, dims in library.items():
        if dims is None or not dims:
            continue
        for dim in dims:
            if fvs_id not in methodology.get(dim, set()):
                drifts.append(
                    f"{fvs_id} declares it affects {dim} but "
                    f"methodology page's {dim} section does not "
                    f"list it"
                )
    _check(
        not drifts,
        "library->methodology drift:\n  " + "\n  ".join(drifts),
    )
    print(f"  PASS\n")


def test_methodology_to_library_consistency():
    """For every methodology dimension that lists a library
    entry as related, the library entry must declare it affects
    that dimension. Catches the case where the methodology page
    is updated to reference an entry that doesn't claim to be
    related."""
    print("=== canon graph: methodology -> library consistency ===")
    library = _library_implications()
    methodology = _methodology_page_implications()
    drifts = []
    for dim, fvs_ids in methodology.items():
        for fvs_id in fvs_ids:
            entry_dims = library.get(fvs_id)
            if entry_dims is None:
                drifts.append(
                    f"methodology page's {dim} section lists "
                    f"{fvs_id} but the library entry doesn't "
                    f"declare any 'Decision-readiness implication' "
                    f"section"
                )
                continue
            if dim not in entry_dims:
                drifts.append(
                    f"methodology page's {dim} section lists "
                    f"{fvs_id} but the library entry declares "
                    f"affected dimensions {sorted(entry_dims)} "
                    f"(does not include {dim})"
                )
    _check(
        not drifts,
        "methodology->library drift:\n  " + "\n  ".join(drifts),
    )
    print(f"  PASS\n")


def test_module_constant_matches_methodology():
    """decision_readiness.DIMENSION_LIBRARY_ENTRIES must agree
    with the methodology page's per-dimension list. The module
    constant is what gets emitted into the profile JSON; if it
    drifts from the methodology page, JSON consumers see
    different citations than human readers see on the rendered
    methodology page."""
    print("=== canon graph: module constant -> methodology consistency ===")
    module = _module_dimension_entries()
    methodology = _methodology_page_implications()
    drifts = []
    for dim in DIMENSIONS:
        mod_set = module.get(dim, set())
        meth_set = methodology.get(dim, set())
        only_module = mod_set - meth_set
        only_methodology = meth_set - mod_set
        if only_module:
            drifts.append(
                f"{dim}: module lists {sorted(only_module)} but "
                f"methodology page does not"
            )
        if only_methodology:
            drifts.append(
                f"{dim}: methodology page lists "
                f"{sorted(only_methodology)} but module does not"
            )
    _check(
        not drifts,
        "module/methodology drift:\n  " + "\n  ".join(drifts),
    )
    print(f"  PASS\n")


def test_dimension_pills_helper_emits_links_for_direct_mapping_entries():
    """For an entry that affects one or more dimensions, the hub
    pill helper must emit one anchor tag per dimension with href
    targeting the methodology page anchor (#dim-<dimension>). Pins
    that the pills are LINKS, not just text; the canon graph
    becomes navigable, not merely visible. Coverage and Counterfactual
    are spot-checked because they cover both the multi-dimension case
    (FVS-001 affects both) and the most-cited dimensions."""
    print("=== canon graph: pills emit dimension links ===")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import (
            _dimension_pills_html, _entry_dimensions_map, _meta_side_entry_ids,
        )
    finally:
        sys.path.pop(0)
    dim_map = _entry_dimensions_map()
    meta_set = _meta_side_entry_ids()
    # FVS-001 (Frame Amplification) affects both Coverage and Counterfactual
    pills = _dimension_pills_html("FVS-001", dim_map, meta_set)
    _check(
        'href="/corpus/decision-readiness/#dim-coverage"' in pills,
        f"FVS-001 pills missing Coverage anchor link: {pills}",
    )
    _check(
        'href="/corpus/decision-readiness/#dim-counterfactual"' in pills,
        f"FVS-001 pills missing Counterfactual anchor link: {pills}",
    )
    _check(
        ">Coverage</a>" in pills and ">Counterfactual</a>" in pills,
        f"FVS-001 pills missing display labels: {pills}",
    )
    # FVS-016 (Authority by Citation) affects Evidence and Robustness
    pills_16 = _dimension_pills_html("FVS-016", dim_map, meta_set)
    _check(
        'href="/corpus/decision-readiness/#dim-evidence"' in pills_16
        and 'href="/corpus/decision-readiness/#dim-robustness"' in pills_16,
        f"FVS-016 pills missing Evidence/Robustness anchors: {pills_16}",
    )
    print(f"  PASS\n")


def test_dimension_pills_helper_emits_meta_tag_for_meta_side_entries():
    """Meta-side and meta-meta entries must NOT carry dimension
    pills (they don't affect a specific dimension); they get a
    quiet 'meta' tag instead. Pins that the helper distinguishes
    the two classes so the hub honestly reflects the implication
    section's classification."""
    print("=== canon graph: pills emit meta tag for meta-side ===")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import (
            _dimension_pills_html, _entry_dimensions_map, _meta_side_entry_ids,
        )
    finally:
        sys.path.pop(0)
    dim_map = _entry_dimensions_map()
    meta_set = _meta_side_entry_ids()
    # FVS-002 (Fluency-Quality Illusion) is meta-side
    pills = _dimension_pills_html("FVS-002", dim_map, meta_set)
    _check(
        'class="dim-pill dim-pill-meta"' in pills,
        f"FVS-002 should render the meta tag: {pills}",
    )
    _check(
        '#dim-coverage' not in pills and '#dim-calibration' not in pills,
        f"FVS-002 (meta-side) must not carry dimension links: {pills}",
    )
    # FVS-020 (Invisible Frame) is meta-meta; same UI treatment
    pills_20 = _dimension_pills_html("FVS-020", dim_map, meta_set)
    _check(
        'class="dim-pill dim-pill-meta"' in pills_20,
        f"FVS-020 should render the meta tag: {pills_20}",
    )
    print(f"  PASS\n")


def test_every_published_entry_renders_a_pill_or_meta_tag():
    """Every non-withdrawn entry on the library hub MUST render
    either dimension pills or a meta tag. A blank entry would
    silently signal 'no decision-readiness affiliation', which
    is wrong for canon entries: every non-withdrawn entry is
    either direct-mapping (has dimensions) or meta-side. This
    test fails loudly if a new entry is added to the library
    without being wired into either DIMENSION_LIBRARY_ENTRIES or
    declaring meta-side classification."""
    print("=== canon graph: every published entry has a pill or meta ===")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import (
            _dimension_pills_html, _entry_dimensions_map, _meta_side_entry_ids,
        )
    finally:
        sys.path.pop(0)
    dim_map = _entry_dimensions_map()
    meta_set = _meta_side_entry_ids()
    blanks = []
    for path in sorted(LIBRARY_DIR.glob("FVS-*.md")):
        m = re.match(r"^(FVS-\d{3})_", path.name)
        if not m:
            continue
        fvs_id = m.group(1)
        if fvs_id in WITHDRAWN:
            continue
        rendered = _dimension_pills_html(fvs_id, dim_map, meta_set)
        if not rendered.strip():
            blanks.append(fvs_id)
    _check(
        not blanks,
        f"library entries with neither dimension pills nor meta tag: {blanks}",
    )
    print(f"  PASS\n")


def test_methodology_page_has_dimension_anchor_ids():
    """The library hub's dimension pills link to anchors on the
    methodology page (/corpus/decision-readiness/#dim-coverage etc).
    If those IDs disappear from the methodology page builder, every
    pill on the hub silently 404s WITHIN the page (the destination
    page exists but the anchor target doesn't, so the browser scrolls
    to top instead of the section). Pin the IDs in the source so a
    future edit that strips them fails at test time."""
    print("=== canon graph: methodology page carries dimension anchor IDs ===")
    builder = REPO_ROOT / "build_corpus_site.py"
    src = builder.read_text(encoding="utf-8")
    missing = []
    for dim in DIMENSIONS:
        anchor = f'id="dim-{dim}"'
        if anchor not in src:
            missing.append(anchor)
    _check(
        not missing,
        f"methodology page builder missing anchor IDs: {missing}. "
        f"Library hub pills link to these and rely on them existing.",
    )
    print(f"  PASS\n")


def test_methodology_page_has_meta_side_section():
    """The hub's meta pill links to the methodology page's
    "Meta-side frames in the library" section (#meta-side-frames).
    If that section disappears or its ID changes, the meta pill
    becomes a dead link. Also verify the section names every
    meta-side library entry so the canon graph's 6th node (meta)
    actually lists what it represents."""
    print("=== canon graph: methodology page has meta-side section ===")
    builder = REPO_ROOT / "build_corpus_site.py"
    src = builder.read_text(encoding="utf-8")
    _check(
        'id="meta-side-frames"' in src,
        "methodology page builder missing #meta-side-frames anchor. "
        "The hub's meta pill links to this section.",
    )
    # Every meta-side entry must be listed in the meta-side section
    # (not necessarily linked, but mentioned by FVS-ID). Detect the
    # meta-side section block first, then check IDs are present.
    section_match = re.search(
        r'id="meta-side-frames"(.+?)(?=<h2 |\Z)',
        src, re.DOTALL,
    )
    _check(
        section_match is not None,
        "could not locate the meta-side section body",
    )
    section_body = section_match.group(1)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import _meta_side_entry_ids
    finally:
        sys.path.pop(0)
    meta_set = _meta_side_entry_ids()
    missing_in_section = sorted(fid for fid in meta_set if fid not in section_body)
    _check(
        not missing_in_section,
        f"meta-side library entries missing from the meta-side "
        f"methodology section: {missing_in_section}",
    )
    print(f"  PASS  ({len(meta_set)} meta-side entries listed)\n")


def test_entry_page_pill_injection_marker_exists():
    """The entry-page render loop injects pills after the first
    </h1> in each library entry's body. The injection is a regex
    sub on `(</h1>)`. If that sub is removed, entry pages render
    without the at-a-glance dimension affiliation and the canon
    graph loses one of its three surfaces. Pin the call site in
    the source so a future refactor that drops it fails loudly."""
    print("=== canon graph: entry-page pill injection wired ===")
    builder = REPO_ROOT / "build_corpus_site.py"
    src = builder.read_text(encoding="utf-8")
    # Look for both the injection regex AND the helper call inside
    # the entry-page rendering loop. Either being missing would
    # break entry-page pills silently.
    _check(
        '_dimension_pills_html(fvs_id, entry_dim_map, meta_set)' in src,
        "entry-page render loop no longer calls _dimension_pills_html.",
    )
    _check(
        re.search(r'r"\(</h1>\)"', src) is not None,
        "entry-page render loop no longer carries the </h1> "
        "injection regex; pills will not appear under entry titles.",
    )
    print(f"  PASS\n")


def test_worked_example_backlinks_helper_inverts_frames_detected():
    """The _build_worked_example_backlinks helper inverts each
    worked example's frames_detected frontmatter into a reverse
    map {fvs_id: [(slug, title), ...]}. Pin specific corpus state:
    FVS-008 (Growth Frame) is in frames_detected of two worked
    examples (four-llms-bitcoin and grok-nvidia per the seeded
    corpus). FVS-016 (Authority by Citation) is in zero (no worked
    example currently declares it as a primary frame), so its
    backlink list is missing or empty."""
    print("=== worked-example backlinks: helper inverts frames_detected ===")
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import _build_worked_example_backlinks
    finally:
        sys.path.pop(0)
    backlinks = _build_worked_example_backlinks()
    fvs008_slugs = {slug for slug, _t in backlinks.get("FVS-008", [])}
    _check(
        "four-llms-on-bitcoin-retirement-2026" in fvs008_slugs
        and "grok-on-nvidia-earnings-2026" in fvs008_slugs,
        f"FVS-008 backlinks should include both four-llms-bitcoin "
        f"and grok-nvidia worked examples; got {sorted(fvs008_slugs)}",
    )
    # FVS-016: no worked example currently declares it. The
    # helper omits the key entirely (or returns empty list); both
    # mean "no backlinks." Defensive check.
    _check(
        not backlinks.get("FVS-016"),
        f"FVS-016 should have no backlinks (no worked example "
        f"declares it in frames_detected); got "
        f"{backlinks.get('FVS-016')!r}",
    )
    # Lists are sorted by slug for deterministic output
    for fvs_id, lst in backlinks.items():
        slugs = [s for s, _t in lst]
        _check(
            slugs == sorted(slugs),
            f"backlinks for {fvs_id} not sorted by slug "
            f"(deterministic output broken): {slugs}",
        )
    print(f"  PASS  ({len(backlinks)} entries have backlinks)\n")


def test_worked_example_backlinks_render_in_library_entry_pages():
    """The library entry page builder must render the backlinks
    section when an entry has cited-by worked examples, and omit
    the section entirely when there are none. Pin both branches.

    Reads the rendered HTML at corpus_site/library/. Assumes
    build_corpus_site has been run (site exists). The pre-flight
    skip protects clean checkouts where the site hasn't been
    built yet; the test then runs as informational rather than
    failing on a missing site."""
    print("=== worked-example backlinks: render in entry pages ===")
    site_dir = REPO_ROOT / "corpus_site" / "library"
    if not site_dir.is_dir():
        print(
            "  SKIP  (corpus_site not built; run build_corpus_site.py "
            "to enable this test)\n"
        )
        return
    # FVS-008 has backlinks
    fvs008 = site_dir / "FVS-008.html"
    _check(fvs008.is_file(), "FVS-008.html missing")
    fvs008_html = fvs008.read_text(encoding="utf-8")
    _check(
        "Cited in worked examples" in fvs008_html,
        "FVS-008 page missing 'Cited in worked examples' section "
        "despite having backlinks",
    )
    # The rendered links should point at worked-examples slugs
    _check(
        "/corpus/worked-examples/four-llms-on-bitcoin-retirement-2026/"
        in fvs008_html
        and "/corpus/worked-examples/grok-on-nvidia-earnings-2026/"
        in fvs008_html,
        "FVS-008 page missing backlink anchors for the two "
        "worked examples that cite it",
    )
    # FVS-010 has no backlinks (no worked example declares it)
    fvs010 = site_dir / "FVS-010.html"
    _check(fvs010.is_file(), "FVS-010.html missing")
    fvs010_html = fvs010.read_text(encoding="utf-8")
    _check(
        "Cited in worked examples" not in fvs010_html,
        "FVS-010 page should NOT have 'Cited in worked examples' "
        "section (no worked example declares it in frames_detected); "
        "an empty section would be visual noise",
    )
    # Withdrawn entry: even if frames_detected coincidentally listed
    # it (which it doesn't), withdrawn entries opt out of backlinks
    # because their canon-graph status is "removed."
    fvs003 = site_dir / "FVS-003.html"
    if fvs003.is_file():
        fvs003_html = fvs003.read_text(encoding="utf-8")
        _check(
            "Cited in worked examples" not in fvs003_html,
            "withdrawn FVS-003 should not carry backlinks section",
        )
    print("  PASS\n")


def test_aggregate_page_renders_when_aggregate_exists():
    """The corpus_site builder must render an aggregate page at
    /corpus/decision-readiness/aggregate/ when at least one
    validation aggregate run is present. Closes the third
    distribution channel (web) for the canon graph at the
    corpus-aggregate level (alongside MCP frame-check://aggregate/
    latest and the local aggregate.json/aggregate.md files).

    This test is conditional on:
      (a) corpus_site has been built (run build_corpus_site.py)
      (b) at least one aggregate exists under
          validation/decision_readiness/results/

    If either is absent the test marks PASS as informational
    rather than failing on a missing artifact."""
    print("=== aggregate page renders when aggregate exists ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import _find_latest_aggregate_md
    finally:
        sys.path.pop(0)
    if _find_latest_aggregate_md() is None:
        print("  SKIP  (no aggregate exists; harness must run first)\n")
        return
    agg_page = site_dir / "decision-readiness" / "aggregate" / "index.html"
    _check(
        agg_page.is_file(),
        f"aggregate page should be built at {agg_page} when an "
        f"aggregate exists; rebuild corpus_site if this fails",
    )
    html = agg_page.read_text(encoding="utf-8")
    # Page should carry the aggregate's structural sections
    _check(
        "Decision-readiness corpus aggregate" in html,
        "aggregate page missing its title",
    )
    # FVS references should be present (rendered from aggregate.md)
    _check(
        "FVS-" in html,
        "aggregate page should contain FVS references from the "
        "rendered aggregate findings",
    )
    # Provenance line names the source artifact path
    _check(
        "Source artifact" in html,
        "aggregate page should carry provenance line naming the "
        "underlying aggregate.md path",
    )
    # The page is in the methodology section so the lateral nav
    # works correctly
    _check(
        'class="header-section-link"' in html,
        "aggregate page should carry the standard header chrome",
    )
    print("  PASS\n")


def test_methodology_page_links_to_aggregate_when_present():
    """When an aggregate exists, the methodology page must link
    to it so a researcher reading the methodology can navigate to
    'what does the corpus actually show.' Without this link the
    aggregate page is reachable only via direct URL.

    Conditional on aggregate existence; the link is honestly
    omitted on clean checkouts so it cannot 404."""
    print("=== methodology page links to aggregate when present ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import _find_latest_aggregate_md
    finally:
        sys.path.pop(0)
    methodology_page = site_dir / "decision-readiness" / "index.html"
    _check(methodology_page.is_file(), "methodology page missing")
    html = methodology_page.read_text(encoding="utf-8")
    if _find_latest_aggregate_md() is not None:
        _check(
            "/corpus/decision-readiness/aggregate/" in html,
            "methodology page should link to aggregate when one "
            "exists; without the link readers must guess the URL",
        )
        # The link's prose context must mention what the aggregate is
        _check(
            "corpus aggregate findings" in html
            or "aggregate findings" in html,
            "methodology page link to aggregate should carry context "
            "naming what the reader will find",
        )
    else:
        _check(
            "/corpus/decision-readiness/aggregate/" not in html,
            "methodology page should NOT link to aggregate when "
            "none exists (avoids 404)",
        )
    print("  PASS\n")


def test_raters_md_exists_and_carries_required_sections():
    """RATERS.md is the contract for Phase 2 decision-readiness
    raters (parallel to REVIEWERS.md which is for library canon
    review). Without this contract, the recruitment surface on
    /corpus/decision-readiness/validation/ has nothing to point
    at; prospective raters need to see the contract before
    committing.

    Pin sections that must be present for the contract to be
    complete: time commitment, deliverable shape, terms,
    blinding requirement, how to engage."""
    print("=== RATERS.md exists and carries required sections ===")
    raters_path = REPO_ROOT / "RATERS.md"
    _check(raters_path.is_file(), "RATERS.md missing at repo root")
    text = raters_path.read_text(encoding="utf-8")
    # Required structural sections; the contract is incomplete
    # without each of these
    required_sections = [
        "## What this document is",
        "## What a rating is for",
        "## What a rating deliverable looks like",
        "## Terms",
        "## How to engage",
    ]
    for section in required_sections:
        _check(
            section in text,
            f"RATERS.md missing required section: {section!r}",
        )
    # Required content markers
    _check(
        "Blinding" in text or "blind to" in text or "blinding" in text.lower(),
        "RATERS.md must name the blinding requirement (raters cannot "
        "read Frame Check's profile before rating); without this the "
        "contract omits the load-bearing methodology constraint",
    )
    _check(
        "30-60 min" in text or "30-60 minutes" in text,
        "RATERS.md must name the per-document time estimate so a "
        "prospective rater can size the commitment before engaging",
    )
    print("  PASS\n")


def test_validation_invitation_page_renders_when_raters_md_exists():
    """The corpus_site builder produces a public Phase 2 rater
    recruitment page at /corpus/decision-readiness/validation/.
    Conditional on RATERS.md existing on the deploy. Without
    this surface, the methodology page describes Phase 2 but
    offers no clickable participation path; the recruitment
    funnel is broken at the surface where prospective raters
    land."""
    print("=== validation invitation page renders when RATERS.md exists ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    raters_path = REPO_ROOT / "RATERS.md"
    if not raters_path.is_file():
        print("  SKIP  (RATERS.md absent)\n")
        return
    page = site_dir / "decision-readiness" / "validation" / "index.html"
    _check(page.is_file(), f"validation page missing at {page}")
    html = page.read_text(encoding="utf-8")
    _check(
        "Phase 2 validation" in html,
        "validation page missing its title",
    )
    _check(
        "reviewers wanted" in html.lower(),
        "validation page missing the call-to-action language",
    )
    # Must link to the operational documents (rater_guide,
    # RATERS.md, examples) so a researcher can follow through
    _check(
        "RATERS.md" in html,
        "validation page must link to RATERS.md (the contract)",
    )
    _check(
        "rater_guide.md" in html,
        "validation page must link to the rater guide",
    )
    # Time commitment must be visible so a prospective rater can
    # size before engaging
    _check(
        "30-60 min" in html or "30-60 minutes" in html,
        "validation page must name the per-document time estimate",
    )
    # GitHub repo link for actual submission
    _check(
        "github.com/lluvr/frame-check" in html,
        "validation page must link to the GitHub repo for PR submission",
    )
    print("  PASS\n")


def test_methodology_page_carries_phase2_invitation_cta():
    """Methodology page must carry a prominent CTA linking to the
    validation invitation page when RATERS.md exists. The CTA is
    the discovery surface for prospective raters who land on the
    methodology; without it, the validation invitation page is
    reachable only via the hub or direct URL.

    Conditional on RATERS.md existing; the CTA is honestly
    omitted on clean checkouts so it cannot 404."""
    print("=== methodology page carries Phase 2 invitation CTA ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    raters_path = REPO_ROOT / "RATERS.md"
    methodology_page = site_dir / "decision-readiness" / "index.html"
    _check(methodology_page.is_file(), "methodology page missing")
    html = methodology_page.read_text(encoding="utf-8")
    if raters_path.is_file():
        _check(
            "/corpus/decision-readiness/validation/" in html,
            "methodology page should link to validation invitation page "
            "when RATERS.md exists",
        )
        _check(
            'class="dr-invitation-cta"' in html,
            "methodology page should carry the dr-invitation-cta "
            "container when RATERS.md exists; the styled CTA is the "
            "visible discovery surface for prospective raters",
        )
        _check(
            "reviewers wanted" in html.lower(),
            "methodology CTA must use the 'reviewers wanted' language "
            "(the canon recruitment phrasing matching FVS entries' status)",
        )
    else:
        _check(
            "/corpus/decision-readiness/validation/" not in html,
            "methodology page should NOT link to validation when "
            "RATERS.md is absent (avoids 404)",
        )
    print("  PASS\n")


def test_decision_readiness_examples_hub_renders_when_sources_exist():
    """The corpus_site builder produces /corpus/decision-readiness/
    examples/index.html when at least one annotation file exists.
    The hub indexes diff annotations, peer annotations, and the
    rating-quality contrast: three audiences, three sub-collections.

    Conditional on the source tree existing AND the corpus_site
    being built. If either is absent the test marks PASS as
    informational rather than failing on a missing artifact."""
    print("=== examples hub renders when source files exist ===")
    site_dir = REPO_ROOT / "corpus_site"
    examples_src_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "examples"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    if not examples_src_dir.is_dir():
        print("  SKIP  (examples source tree absent)\n")
        return
    hub_path = site_dir / "decision-readiness" / "examples" / "index.html"
    _check(
        hub_path.is_file(),
        f"examples hub missing at {hub_path} despite source tree "
        f"existing; rebuild corpus_site if this fails",
    )
    html = hub_path.read_text(encoding="utf-8")
    _check(
        "Decision-readiness examples" in html,
        "examples hub missing its title",
    )
    # Hub must surface the three audience-distinct sub-collections
    # so a reader landing on it understands the structure
    _check(
        "rating-quality contrast" in html.lower()
        or "rating quality contrast" in html.lower(),
        "examples hub must name the rating-quality sub-collection",
    )
    # Source files must be cited so a researcher can find the
    # underlying validation tree
    _check(
        "validation/decision_readiness/examples" in html,
        "examples hub must cite the source artifact path",
    )
    print("  PASS\n")


def test_decision_readiness_diff_annotation_pages_render():
    """Each markdown file in validation/decision_readiness/examples/
    diff/ (excluding README.md and underscore-prefixed scaffold)
    becomes a page at /corpus/decision-readiness/examples/diff/{slug}/.

    Pin: at least one diff annotation page exists when source
    files exist, and the page renders the source markdown title
    as the page H1 (not double-prefixed)."""
    print("=== diff annotation pages render ===")
    site_dir = REPO_ROOT / "corpus_site"
    diff_src_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "examples" / "diff"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    if not diff_src_dir.is_dir():
        print("  SKIP  (diff source tree absent)\n")
        return
    diff_md_files = [
        f for f in diff_src_dir.glob("*.md")
        if f.name != "README.md" and not f.name.startswith("_")
    ]
    if not diff_md_files:
        print("  SKIP  (no diff annotations to render)\n")
        return
    for md in diff_md_files:
        slug = md.stem
        page = (
            site_dir / "decision-readiness" / "examples" / "diff"
            / slug / "index.html"
        )
        _check(
            page.is_file(),
            f"diff annotation page missing for slug {slug!r}: "
            f"expected {page}",
        )
        html = page.read_text(encoding="utf-8")
        # Title must NOT be double-prefixed (the source H1 already
        # carries "Annotated interpretation:" so prefixing with
        # "Diff annotation:" would chain awkwardly)
        _check(
            "Diff annotation: Annotated" not in html,
            f"diff page {slug!r} has double-prefixed title; the "
            f"page_template title must use the source H1 verbatim",
        )
    print(f"  PASS  ({len(diff_md_files)} diff annotation pages verified)\n")


def test_decision_readiness_peer_annotation_pages_render():
    """Mirror of the diff annotation test for peer/ subdirectory."""
    print("=== peer annotation pages render ===")
    site_dir = REPO_ROOT / "corpus_site"
    peer_src_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "examples" / "peer"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    if not peer_src_dir.is_dir():
        print("  SKIP  (peer source tree absent)\n")
        return
    peer_md_files = [
        f for f in peer_src_dir.glob("*.md")
        if f.name != "README.md" and not f.name.startswith("_")
    ]
    if not peer_md_files:
        print("  SKIP  (no peer annotations to render)\n")
        return
    for md in peer_md_files:
        slug = md.stem
        page = (
            site_dir / "decision-readiness" / "examples" / "peer"
            / slug / "index.html"
        )
        _check(
            page.is_file(),
            f"peer annotation page missing for slug {slug!r}: "
            f"expected {page}",
        )
        html = page.read_text(encoding="utf-8")
        _check(
            "Peer annotation: Annotated" not in html,
            f"peer page {slug!r} has double-prefixed title",
        )
    print(f"  PASS  ({len(peer_md_files)} peer annotation pages verified)\n")


def test_decision_readiness_rating_contrast_page_renders():
    """The rating-quality contrast page renders all three example
    YAMLs verbatim in code blocks. A prospective rater landing on
    the page sees what good/mediocre/insufficient submissions look
    like before committing to their own first rating."""
    print("=== rating-quality contrast page renders ===")
    site_dir = REPO_ROOT / "corpus_site"
    examples_src_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "examples"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    if not examples_src_dir.is_dir():
        print("  SKIP  (examples source tree absent)\n")
        return
    page = (
        site_dir / "decision-readiness" / "examples" / "ratings"
        / "index.html"
    )
    has_any_example = any(
        (examples_src_dir / f"example-{label}.yaml").is_file()
        for label in ("good", "mediocre", "insufficient")
    )
    if not has_any_example:
        print("  SKIP  (no rating examples in source)\n")
        return
    _check(
        page.is_file(),
        f"ratings page missing at {page} despite source examples existing",
    )
    html = page.read_text(encoding="utf-8")
    # The contrast: each example should be in its own labeled section
    for label in ("good", "mediocre", "insufficient"):
        if (examples_src_dir / f"example-{label}.yaml").is_file():
            _check(
                f'id="rating-example-{label}"' in html,
                f"ratings page missing section for {label!r} example",
            )
    # YAML rendering must be in pre/code blocks (verbatim is the teaching)
    _check(
        'class="dr-rating-yaml"' in html,
        "ratings page should use dr-rating-yaml CSS class for "
        "verbatim YAML rendering",
    )
    print("  PASS\n")


def test_methodology_page_links_to_examples_when_sources_exist():
    """The methodology page must link to /corpus/decision-readiness/
    examples/ when at least one example sub-source exists. The link
    is the discovery surface for researchers landing on the
    methodology who want to see how artifacts read in practice.

    Conditional on examples sources existing; link omitted on
    clean checkouts so it cannot 404."""
    print("=== methodology page links to examples when sources exist ===")
    site_dir = REPO_ROOT / "corpus_site"
    examples_src_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "examples"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    methodology_page = site_dir / "decision-readiness" / "index.html"
    _check(methodology_page.is_file(), "methodology page missing")
    html = methodology_page.read_text(encoding="utf-8")
    # Detect whether sources exist (mirrors the builder's logic)
    has_diff = (examples_src_dir / "diff").is_dir() and any(
        f.name != "README.md" and not f.name.startswith("_")
        for f in (examples_src_dir / "diff").glob("*.md")
    ) if (examples_src_dir / "diff").is_dir() else False
    has_peer = (examples_src_dir / "peer").is_dir() and any(
        f.name != "README.md" and not f.name.startswith("_")
        for f in (examples_src_dir / "peer").glob("*.md")
    ) if (examples_src_dir / "peer").is_dir() else False
    has_ratings = any(
        (examples_src_dir / f"example-{label}.yaml").is_file()
        for label in ("good", "mediocre", "insufficient")
    ) if examples_src_dir.is_dir() else False
    if has_diff or has_peer or has_ratings:
        _check(
            "/corpus/decision-readiness/examples/" in html,
            "methodology page should link to examples surface when "
            "at least one example source exists",
        )
    else:
        _check(
            "/corpus/decision-readiness/examples/" not in html,
            "methodology page should NOT link to examples when no "
            "source files exist (avoids 404)",
        )
    print("  PASS\n")


def test_validation_page_links_to_rating_contrast():
    """The Phase 2 validation invitation page must link to the
    rating-quality contrast specifically (not just the examples hub).
    Prospective raters need to see what good submissions look like
    before committing; the contrast IS the calibration material.

    Conditional on rating examples existing."""
    print("=== validation page links to rating-quality contrast ===")
    site_dir = REPO_ROOT / "corpus_site"
    examples_src_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "examples"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    validation_page = (
        site_dir / "decision-readiness" / "validation" / "index.html"
    )
    if not validation_page.is_file():
        print("  SKIP  (validation invitation page not built)\n")
        return
    html = validation_page.read_text(encoding="utf-8")
    has_ratings = any(
        (examples_src_dir / f"example-{label}.yaml").is_file()
        for label in ("good", "mediocre", "insufficient")
    ) if examples_src_dir.is_dir() else False
    if has_ratings:
        _check(
            "/corpus/decision-readiness/examples/ratings/" in html,
            "validation page should link to rating-quality contrast "
            "page when examples exist; prospective raters need this "
            "calibration material before committing",
        )
    print("  PASS\n")


def test_validation_corpus_surface_renders():
    """The corpus_site builder produces a per-entry page for every
    validation corpus entry under
    /corpus/decision-readiness/corpus/{slug}/, plus a hub at
    /corpus/decision-readiness/corpus/index.html. Surfacing the
    corpus on the web channel means aggregate findings become
    verifiable against the actual documents.

    Conditional on corpus directory existing AND corpus_site built."""
    print("=== validation corpus surface renders ===")
    site_dir = REPO_ROOT / "corpus_site"
    corpus_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    if not corpus_src.is_dir():
        print("  SKIP  (validation corpus absent)\n")
        return
    src_entries = [
        d for d in corpus_src.iterdir()
        if d.is_dir() and (d / "document.md").is_file()
    ]
    if not src_entries:
        print("  SKIP  (no corpus entries to render)\n")
        return
    hub = site_dir / "decision-readiness" / "corpus" / "index.html"
    _check(
        hub.is_file(),
        f"validation corpus hub missing at {hub}",
    )
    hub_html = hub.read_text(encoding="utf-8")
    _check(
        "validation corpus" in hub_html.lower(),
        "hub missing 'validation corpus' framing",
    )
    # Hub must carry the convenience-sampling caveat; surfacing
    # the corpus could otherwise let readers treat it as a
    # representative sample
    _check(
        "convenience-sampled" in hub_html.lower()
        or "convenience sample" in hub_html.lower(),
        "hub must surface the convenience-sampling caveat so "
        "readers don't treat findings as population-level claims",
    )
    # Each source entry must produce a per-entry page
    missing_pages = []
    for src_entry in src_entries:
        slug = src_entry.name
        page = (
            site_dir / "decision-readiness" / "corpus" / slug
            / "index.html"
        )
        if not page.is_file():
            missing_pages.append(slug)
    _check(
        not missing_pages,
        f"corpus entry pages missing: {missing_pages}",
    )
    print(f"  PASS  ({len(src_entries)} corpus entry pages verified)\n")


def test_corpus_entry_pages_carry_genre_badge_for_ai_responses():
    """ai_response entries (raw LLM output) must carry a visible
    badge so a reader does not conflate raw model output with
    curated worked-example analyses. The badge is a structural
    construct-honesty mechanism: surfacing the corpus risks
    presenting AI output as endorsed; the badge prevents that."""
    print("=== corpus entry pages: AI badge for ai_response ===")
    site_dir = REPO_ROOT / "corpus_site"
    corpus_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    if not site_dir.is_dir() or not corpus_src.is_dir():
        print("  SKIP  (prerequisites absent)\n")
        return
    # Find at least one ai_response entry to test against
    try:
        import yaml
    except ImportError:
        print("  SKIP  (PyYAML required to verify genre)\n")
        return
    ai_entries = []
    for d in corpus_src.iterdir():
        if not d.is_dir():
            continue
        meta_path = d / "metadata.yaml"
        if not meta_path.is_file():
            continue
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if meta.get("genre") == "ai_response":
            ai_entries.append(d.name)
    if not ai_entries:
        print("  SKIP  (no ai_response entries in corpus)\n")
        return
    for slug in ai_entries:
        page = (
            site_dir / "decision-readiness" / "corpus" / slug
            / "index.html"
        )
        _check(page.is_file(), f"page missing for {slug}")
        html = page.read_text(encoding="utf-8")
        _check(
            'class="dr-corpus-genre-badge dr-corpus-genre-ai"' in html
            or "AI-generated response" in html,
            f"corpus entry {slug!r} (ai_response) missing the visible "
            f"AI-generated badge; readers could misread raw LLM "
            f"output as endorsed content",
        )
    print(f"  PASS  ({len(ai_entries)} ai_response entries verified)\n")


def test_corpus_entry_pages_link_to_diff_peer_artifacts():
    """Each corpus entry's page must link to its diff/peer
    artifacts (JSON files on GitHub) when those artifacts exist.
    Without these links, the corpus entry page is disconnected
    from the validation harness output it contributes to."""
    print("=== corpus entry pages link to diff/peer artifacts ===")
    site_dir = REPO_ROOT / "corpus_site"
    corpus_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    if not site_dir.is_dir() or not corpus_src.is_dir():
        print("  SKIP  (prerequisites absent)\n")
        return
    # Find an entry with both diff and peer partners (e.g.,
    # grok-nvidia-q4-fy24-summary has a diff_with file)
    test_slug = None
    for d in corpus_src.iterdir():
        if not d.is_dir():
            continue
        has_diff = any(d.glob("diff_with_*.json"))
        has_peer = any(d.glob("peer_with_*.json"))
        if has_diff or has_peer:
            test_slug = d.name
            break
    if test_slug is None:
        print("  SKIP  (no corpus entries have diff/peer artifacts)\n")
        return
    page = (
        site_dir / "decision-readiness" / "corpus" / test_slug
        / "index.html"
    )
    _check(page.is_file(), f"page missing for {test_slug}")
    html = page.read_text(encoding="utf-8")
    # Heading changed from "artifacts" to "findings" when diff/peer
    # content was inlined (readers now see per-dimension findings
    # directly, not just links to artifacts on GitHub). Accept both
    # so future rename doesn't falsely break.
    has_diff_section = (
        "Transformation diff findings" in html
        or "Transformation diff artifacts" in html
    )
    has_peer_section = (
        "Peer comparison findings" in html
        or "Peer comparison artifacts" in html
    )
    _check(
        has_diff_section or has_peer_section,
        f"corpus entry {test_slug!r} has diff or peer JSONs but "
        f"the page surfaces neither section",
    )
    # GitHub link to underlying JSON
    _check(
        "github.com/lluvr/frame-check" in html
        and ".json" in html,
        f"corpus entry {test_slug!r} should link to the underlying "
        f"diff/peer JSON files on GitHub",
    )
    print("  PASS\n")


def test_aggregate_page_links_to_validation_corpus():
    """The aggregate page must link to the validation corpus
    when corpus entries exist. Without this link, aggregate
    findings ('claude consistently fires FVS-007 in counterfactual')
    are not verifiable from the page they are stated on; a reader
    has to know the URL pattern to navigate to the source documents."""
    print("=== aggregate page links to validation corpus ===")
    site_dir = REPO_ROOT / "corpus_site"
    corpus_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    aggregate_page = (
        site_dir / "decision-readiness" / "aggregate" / "index.html"
    )
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    if not aggregate_page.is_file():
        print("  SKIP  (aggregate page not built)\n")
        return
    has_corpus = corpus_src.is_dir() and any(
        d.is_dir() and (d / "document.md").is_file()
        for d in corpus_src.iterdir()
    ) if corpus_src.exists() else False
    html = aggregate_page.read_text(encoding="utf-8")
    if has_corpus:
        _check(
            "/corpus/decision-readiness/corpus/" in html,
            "aggregate page should link to validation corpus when "
            "corpus exists; findings need a verification path",
        )
    print("  PASS\n")


def test_methodology_page_links_to_validation_corpus():
    """Methodology page must link to validation corpus when
    corpus exists, so a researcher reading methodology can
    navigate to the documents the methodology measures against."""
    print("=== methodology page links to validation corpus ===")
    site_dir = REPO_ROOT / "corpus_site"
    corpus_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    methodology_page = site_dir / "decision-readiness" / "index.html"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    _check(methodology_page.is_file(), "methodology page missing")
    has_corpus = corpus_src.is_dir() and any(
        d.is_dir() and (d / "document.md").is_file()
        for d in corpus_src.iterdir()
    ) if corpus_src.exists() else False
    html = methodology_page.read_text(encoding="utf-8")
    if has_corpus:
        _check(
            "/corpus/decision-readiness/corpus/" in html,
            "methodology page should link to validation corpus when "
            "corpus exists",
        )
    print("  PASS\n")


def test_corpus_entry_pages_render_profile_inline():
    """Corpus entry pages must render the computed
    decision-readiness profile inline, not just link to GitHub.
    The inline profile surfaces signal_text + fired patterns
    with clickable library links, letting researchers verify
    aggregate findings against the per-entry data without
    leaving corpus_site.

    Gate-convention note: this is the validation-context surface
    (research documentation), NOT the live /profile endpoint.
    The gate test at test_decision_readiness_not_in_result_page_ui
    forbids `class=\"decision-readiness\"` and similar markers on
    result-page output; corpus_site uses dr-corpus-profile-*
    identifiers deliberately distinct from those forbidden
    markers.
    """
    print("=== corpus entry pages render profile inline ===")
    site_dir = REPO_ROOT / "corpus_site"
    corpus_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    if not site_dir.is_dir() or not corpus_src.is_dir():
        print("  SKIP  (prerequisites absent)\n")
        return
    # Pick a specific entry with known profile content
    page = (
        site_dir / "decision-readiness" / "corpus"
        / "four-llms-bitcoin-claude" / "index.html"
    )
    if not page.is_file():
        print("  SKIP  (claude bitcoin entry not built)\n")
        return
    html = page.read_text(encoding="utf-8")
    # Profile section must be rendered with validation-context framing
    _check(
        'class="dr-corpus-profile"' in html,
        "corpus entry page missing inline profile rendering; "
        "readers cannot verify findings without leaving corpus_site",
    )
    # Status must be prominent
    _check(
        "experimental" in html.lower(),
        "corpus entry profile rendering must surface experimental "
        "status so readers do not mistake dimensional signals for "
        "validated verdicts",
    )
    # Per-dimension signal_text should be present (claude bitcoin
    # entry is known to have fired FVS-001 + FVS-008 in coverage
    # per the corpus snapshot)
    _check(
        'id="dr-profile-dim-coverage"' in html,
        "coverage dimension card missing from entry profile",
    )
    _check(
        'id="dr-profile-dim-counterfactual"' in html,
        "counterfactual dimension card missing from entry profile",
    )
    # Fired pattern pills must link to library entries (canon graph)
    _check(
        'class="dr-corpus-profile-pill"' in html,
        "fired pattern pills not rendered; readers cannot chain "
        "from dimension to library entry",
    )
    # Gate-convention carefulness: the corpus-surface rendering
    # must NOT use the live-UI markers that the gate forbids
    # (decision-readiness class/id, "Decision-readiness profile"
    # h2). If this test fails, someone copy-pasted the live UI
    # design and broke the gate's spirit.
    _check(
        'class="decision-readiness"' not in html,
        "corpus entry page uses forbidden live-UI marker "
        "class=\"decision-readiness\"; use dr-corpus-profile-* "
        "identifiers instead to stay clear of the gate convention",
    )
    _check(
        'id="decision-readiness"' not in html,
        "corpus entry page uses forbidden live-UI marker "
        "id=\"decision-readiness\"; use dr-corpus-profile-* "
        "identifiers instead",
    )
    print("  PASS\n")


def test_corpus_entry_pages_render_comparisons_inline():
    """Corpus entry pages render diff/peer comparison findings
    inline as collapsible details blocks (rather than only
    linking to GitHub JSON). Each dimension surfaces the
    comparison_text + differs badge + fired_patterns asymmetry."""
    print("=== corpus entry pages render comparisons inline ===")
    site_dir = REPO_ROOT / "corpus_site"
    page = (
        site_dir / "decision-readiness" / "corpus"
        / "four-llms-bitcoin-claude" / "index.html"
    )
    if not page.is_file():
        print("  SKIP  (corpus entry not built)\n")
        return
    html = page.read_text(encoding="utf-8")
    # Per-partner <details> blocks
    _check(
        'class="dr-corpus-comparison-partner"' in html,
        "corpus entry page missing inline comparison details; "
        "readers cannot see comparison findings without leaving "
        "corpus_site for GitHub",
    )
    # Per-dimension comparison_text
    _check(
        'class="dr-corpus-comparison-text"' in html,
        "inline comparison missing per-dimension text",
    )
    # "differs" badge for dimensions with real signal
    _check(
        'class="dr-corpus-comparison-differs"' in html,
        "inline comparison missing 'differs' badge; readers "
        "cannot quickly see which dimensions diverged",
    )
    # Fired-pattern asymmetry (only_a / only_b for peer)
    _check(
        "Only four-llms-bitcoin-claude:" in html
        or "Only four-llms-bitcoin-" in html,
        "inline peer comparison missing only_a/only_b asymmetry "
        "surfacing; fired-pattern differences between peers are "
        "the key structural finding",
    )
    print("  PASS\n")


def test_validation_invitation_page_links_to_corpus():
    """The Phase 2 validation invitation page must link to the
    validation corpus so prospective raters can preview
    documents before committing. Without this, the invitation
    describes a commitment against an opaque "corpus" the rater
    hasn't seen."""
    print("=== validation invitation page links to corpus ===")
    site_dir = REPO_ROOT / "corpus_site"
    page = (
        site_dir / "decision-readiness" / "validation" / "index.html"
    )
    if not page.is_file():
        print("  SKIP  (validation page not built)\n")
        return
    html = page.read_text(encoding="utf-8")
    _check(
        "/corpus/decision-readiness/corpus/" in html,
        "validation invitation page should link to corpus so "
        "prospective raters can preview what they would rate",
    )
    _check(
        "Preview the corpus" in html or "preview the corpus" in html,
        "validation invitation should carry prose inviting the "
        "rater to preview before committing",
    )
    print("  PASS\n")


def test_aggregate_cross_question_findings_deep_link_to_corpus():
    """Aggregate cross-question findings ("claude is the
    counterfactual outlier in 2 of 2 comparable peer groups")
    must deep-link to the specific corpus entries they reference
    (claude's entries, in this case). Without deep linking a
    reader has to hunt through the corpus hub to find the claimed
    entries.

    Conditional: the aggregate page must exist AND contain at
    least one cross-question finding."""
    print("=== aggregate cross-question findings deep-link to corpus ===")
    site_dir = REPO_ROOT / "corpus_site"
    aggregate_page = (
        site_dir / "decision-readiness" / "aggregate" / "index.html"
    )
    if not aggregate_page.is_file():
        print("  SKIP  (aggregate page not built)\n")
        return
    html = aggregate_page.read_text(encoding="utf-8")
    if "outlier in <strong>all" not in html:
        print("  SKIP  (no cross-question findings in current corpus)\n")
        return
    # Find the LLM name being cited (first cross-question finding)
    m = re.search(
        r"<li><strong>(\w+)</strong> is the \w+ outlier in",
        html,
    )
    if m is None:
        print("  SKIP  (finding pattern didn't match for deep link check)\n")
        return
    llm = m.group(1)
    _check(
        f"See {llm}'s corpus entries:" in html,
        f"cross-question finding for {llm!r} missing deep-link "
        f"to corpus entries; readers cannot navigate from the "
        f"finding to the documents it claims about",
    )
    # The deep link should point at a corpus entry URL containing
    # the LLM name
    _check(
        f"/corpus/decision-readiness/corpus/" in html
        and llm in html,
        "deep-link URLs for cross-question findings should point "
        "at corpus entry pages containing the LLM's slug",
    )
    print(f"  PASS  (deep-linked {llm}'s cross-question finding)\n")


def test_rater_guide_page_renders_when_source_exists():
    """The rater guide markdown becomes a corpus_site page at
    /corpus/decision-readiness/rater-guide/. Closes the Phase 2
    recruitment funnel: a prospective rater can read the full
    operational guide in their browser without leaving corpus_site.

    Conditional on source file + corpus_site built."""
    print("=== rater guide page renders ===")
    site_dir = REPO_ROOT / "corpus_site"
    guide_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "rater_guide.md"
    )
    if not site_dir.is_dir() or not guide_src.is_file():
        print("  SKIP  (prerequisites absent)\n")
        return
    page = (
        site_dir / "decision-readiness" / "rater-guide" / "index.html"
    )
    _check(page.is_file(), f"rater guide page missing at {page}")
    html = page.read_text(encoding="utf-8")
    _check(
        "Rater guide" in html,
        "rater guide page missing its title",
    )
    _check(
        "five dimensions" in html.lower()
        or "5 dimension" in html.lower()
        or "1-5 scale" in html.lower(),
        "rater guide page missing expected rating-mechanics content",
    )
    # Provenance framing links back to methodology + invitation
    # + examples + corpus so the rater guide reads as part of the
    # recruitment funnel, not an isolated doc
    _check(
        "/corpus/decision-readiness/validation/" in html,
        "rater guide should link to Phase 2 invitation page",
    )
    _check(
        "/corpus/decision-readiness/" in html,
        "rater guide should link to methodology page",
    )
    print("  PASS\n")


def test_validation_invitation_links_to_rendered_rater_guide():
    """The Phase 2 validation invitation page should link to the
    rendered rater guide on corpus_site (not force a GitHub
    round-trip). Prospective raters evaluating the commitment
    should be able to read the operational guide in-browser."""
    print("=== validation invitation links to rendered rater guide ===")
    site_dir = REPO_ROOT / "corpus_site"
    guide_src = (
        REPO_ROOT / "validation" / "decision_readiness" / "rater_guide.md"
    )
    page = (
        site_dir / "decision-readiness" / "validation" / "index.html"
    )
    if not page.is_file():
        print("  SKIP  (validation page not built)\n")
        return
    if not guide_src.is_file():
        print("  SKIP  (rater guide source absent)\n")
        return
    html = page.read_text(encoding="utf-8")
    _check(
        "/corpus/decision-readiness/rater-guide/" in html,
        "validation invitation should link to rendered rater guide "
        "at /corpus/decision-readiness/rater-guide/ so raters don't "
        "have to leave corpus_site to read operational procedure",
    )
    print("  PASS\n")


def test_aggregate_cross_question_findings_carry_corpus_entries():
    """Aggregate JSON emits corpus_entries field per cross-question
    finding so MCP agents and web consumers chain to the same
    documents without reimplementing slug-matching heuristics.
    Closes an asymmetry between web and MCP (web was deep-linking
    via post-processing, MCP had no mapping)."""
    print("=== aggregate cross_question_findings carry corpus_entries ===")
    import json as _json
    results_dir = REPO_ROOT / "validation" / "decision_readiness" / "results"
    if not results_dir.is_dir():
        print("  SKIP  (no validation results tree)\n")
        return
    # Find most recent aggregate.json by mtime
    candidates = []
    for d in results_dir.iterdir():
        if d.is_dir():
            agg = d / "aggregate.json"
            if agg.is_file():
                candidates.append((agg.stat().st_mtime, agg))
    if not candidates:
        print("  SKIP  (no aggregate.json in results)\n")
        return
    candidates.sort(key=lambda t: t[0], reverse=True)
    payload = _json.loads(candidates[0][1].read_text(encoding="utf-8"))
    findings = payload.get("cross_question_findings") or []
    if not findings:
        print("  SKIP  (no cross-question findings in current corpus)\n")
        return
    for finding in findings:
        _check(
            "corpus_entries" in finding,
            f"cross_question finding missing corpus_entries field; "
            f"MCP agents cannot chain to documents. got keys: "
            f"{sorted(finding.keys())}",
        )
        entries = finding["corpus_entries"]
        _check(
            isinstance(entries, list),
            f"corpus_entries must be a list; got "
            f"{type(entries).__name__}",
        )
        # Each entry uses the corpus_entry_ref shape (parallel to
        # library_entry_ref for library references): slug + title
        # + corpus_resource_uri (MCP) + public_url (HTTP). Parity
        # with library_entry_ref's namespace-qualified field names
        # means MCP agents can chain from the finding to the entry
        # via corpus_resource_uri without URI reconstruction.
        for e in entries:
            for required in (
                "slug", "title", "corpus_resource_uri", "public_url",
            ):
                _check(
                    required in e,
                    f"corpus_entries item missing {required!r}: {e!r}",
                )
            _check(
                e["corpus_resource_uri"].startswith(
                    "frame-check://corpus/"
                ),
                f"corpus_resource_uri wrong scheme/prefix: {e!r}",
            )
            _check(
                e["public_url"].startswith("https://"),
                f"public_url should be absolute HTTPS URL: {e!r}",
            )
            _check(
                e["slug"] in e["corpus_resource_uri"]
                and e["slug"] in e["public_url"],
                f"slug/URI mismatch: {e!r}",
            )
    print(f"  PASS  ({len(findings)} findings carry corpus_entries)\n")


def test_corpus_entry_comparison_text_uses_human_labels():
    """Corpus entry page comparison text substitutes slug-y entry
    names with human-readable labels ("Claude" instead of
    "four-llms-bitcoin-claude"). Web-only substitution; MCP
    consumers get the original slug-style text.

    Readability win for researchers scanning peer comparisons on
    the corpus entry page."""
    print("=== corpus entry comparison text uses human labels ===")
    site_dir = REPO_ROOT / "corpus_site"
    page = (
        site_dir / "decision-readiness" / "corpus"
        / "four-llms-bitcoin-claude" / "index.html"
    )
    if not page.is_file():
        print("  SKIP  (corpus entry page not built)\n")
        return
    html = page.read_text(encoding="utf-8")
    # After substitution: "only Claude addresses X" instead of
    # "only four-llms-bitcoin-claude addresses X"
    _check(
        "only Claude addresses" in html
        or "only Gemini addresses" in html
        or "only Grok addresses" in html
        or "only OpenAI addresses" in html,
        "corpus entry page comparison text should use human labels "
        "(Claude, Gemini, Grok, OpenAI) instead of slug-style entry "
        "names",
    )
    # Specifically: slug form should NOT appear in comparison text
    # within the rendered comparisons (it can appear elsewhere like
    # URLs and the GitHub link). Check a specific phrase that would
    # only appear in un-substituted form.
    _check(
        "only four-llms-bitcoin-claude addresses" not in html,
        "slug-style entry reference 'only four-llms-bitcoin-claude "
        "addresses' should have been substituted to 'only Claude "
        "addresses' at render time",
    )
    print("  PASS\n")


def test_library_entry_pages_link_to_corpus_entries_that_fired_the_frame():
    """Closes the inverse direction of fired_library_entries:
    corpus entries link TO library entries (via fired pills);
    library entries should link BACK to corpus entries that
    fired the frame.

    Pin: FVS-007 (Failure Framing) fires in claude bitcoin/startup
    corpus profiles per the current corpus snapshot. FVS-007's
    library entry page should carry a 'Detected in validation
    corpus' section listing those entries. FVS-016 doesn't fire
    in the offline corpus (no Source Network), so its page should
    NOT carry the section (avoids empty visual noise)."""
    print("=== library entry pages link to corpus fired-in ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    # FVS-007: should have backlinks
    fvs007 = site_dir / "library" / "FVS-007.html"
    if fvs007.is_file():
        html = fvs007.read_text(encoding="utf-8")
        _check(
            "Detected in validation corpus" in html,
            "FVS-007 should have 'Detected in validation corpus' "
            "section (fires in claude entries per current corpus)",
        )
        _check(
            "/corpus/decision-readiness/corpus/" in html,
            "FVS-007 backlinks should point at corpus entry URLs",
        )
        _check(
            'class="dr-corpus-fired-in-backlinks"' in html,
            "FVS-007 should use the dr-corpus-fired-in-backlinks "
            "CSS class for the section",
        )
    # FVS-016: should NOT have backlinks (no detector fires offline)
    fvs016 = site_dir / "library" / "FVS-016.html"
    if fvs016.is_file():
        html = fvs016.read_text(encoding="utf-8")
        _check(
            "Detected in validation corpus" not in html,
            "FVS-016 should NOT have 'Detected in validation corpus' "
            "section when no corpus entry fires it (avoid empty "
            "visual noise)",
        )
    print("  PASS\n")


def test_corpus_fired_in_backlinks_helper_is_inverse_of_fired_library_entries():
    """Algorithmic invariant: _build_corpus_fired_in_backlinks
    inverts the fired_library_entries field across corpus profiles.
    For any (slug, fvs_id) pair where the corpus profile has fvs_id
    in any dimension's fired_library_entries, the library backlink
    map must contain (fvs_id -> [(slug, ...)]). The two surfaces
    must agree because they describe the same underlying
    detection events."""
    print("=== corpus fired-in backlinks inverts fired_library_entries ===")
    import json as _json
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from build_corpus_site import _build_corpus_fired_in_backlinks
    finally:
        sys.path.pop(0)
    backlinks = _build_corpus_fired_in_backlinks()
    corpus_dir = (
        REPO_ROOT / "validation" / "decision_readiness" / "corpus"
    )
    if not corpus_dir.is_dir():
        print("  SKIP  (validation corpus absent)\n")
        return
    # For each corpus entry, walk its profile and verify every
    # fired fvs_id appears in the backlink map keyed by that fvs_id
    for entry_dir in corpus_dir.iterdir():
        if not entry_dir.is_dir():
            continue
        slug = entry_dir.name
        profile_path = entry_dir / "profile.json"
        if not profile_path.is_file():
            continue
        profile = _json.loads(profile_path.read_text(encoding="utf-8"))
        for dim_name, dim_data in (profile.get("dimensions") or {}).items():
            for ref in (dim_data.get("fired_library_entries") or []):
                fid = ref.get("fvs_id")
                if not fid:
                    continue
                _check(
                    fid in backlinks,
                    f"profile {slug!r} fired {fid} in {dim_name} "
                    f"but backlink map has no entry for {fid!r}",
                )
                slugs_in_backlink = [s for s, _t in backlinks[fid]]
                _check(
                    slug in slugs_in_backlink,
                    f"profile {slug!r} fired {fid} in {dim_name} "
                    f"but {slug!r} not in backlink list for "
                    f"{fid!r}; got {slugs_in_backlink!r}",
                )
    print(f"  PASS  ({len(backlinks)} fvs_ids have corpus backlinks)\n")


def test_worked_example_corpus_crosslinks_render_bidirectionally():
    """Heuristic crosslinks render on BOTH sides:
    worked-example pages link to related corpus entries; corpus
    entry pages link to related worked examples.

    Pin specific known matches: four-llms-on-bitcoin-retirement-2026
    worked example must link to all 4 four-llms-bitcoin-* corpus
    entries (and vice versa), and grok-on-nvidia-earnings-2026 must
    link to grok-nvidia-q4-fy24-summary (and vice versa).

    Conditional on both site trees existing."""
    print("=== worked-example <-> corpus crosslinks render bidirectionally ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    # Worked-example -> corpus direction
    we_page = (
        site_dir / "worked-examples"
        / "four-llms-on-bitcoin-retirement-2026" / "index.html"
    )
    if we_page.is_file():
        html = we_page.read_text(encoding="utf-8")
        _check(
            "Possibly related corpus entries" in html,
            "bitcoin-retirement worked example missing crosslinks",
        )
        for llm_slug in (
            "four-llms-bitcoin-claude",
            "four-llms-bitcoin-grok",
            "four-llms-bitcoin-gemini",
            "four-llms-bitcoin-openai",
        ):
            _check(
                f"/corpus/decision-readiness/corpus/{llm_slug}/" in html,
                f"bitcoin-retirement worked example should link to "
                f"corpus entry {llm_slug!r}",
            )
    # Corpus -> worked-example direction
    corpus_page = (
        site_dir / "decision-readiness" / "corpus"
        / "four-llms-bitcoin-claude" / "index.html"
    )
    if corpus_page.is_file():
        html = corpus_page.read_text(encoding="utf-8")
        _check(
            "Possibly related worked examples" in html,
            "claude-bitcoin corpus entry missing worked-example crosslinks",
        )
        _check(
            "/corpus/worked-examples/four-llms-on-bitcoin-retirement-2026/"
            in html,
            "claude-bitcoin corpus entry should link to bitcoin-"
            "retirement worked example",
        )
    # Negative: FOMC worked example has no corpus match (no FOMC
    # entries in corpus); section should be absent
    fomc_page = (
        site_dir / "worked-examples"
        / "fomc-statement-march-2026" / "index.html"
    )
    if fomc_page.is_file():
        html = fomc_page.read_text(encoding="utf-8")
        _check(
            "Possibly related corpus entries" not in html,
            "fomc-statement worked example should NOT have crosslinks "
            "(no matching corpus entries); empty section is visual noise",
        )
    print("  PASS\n")


def test_crosslinks_use_honest_heuristic_framing():
    """The crosslink rendering uses 'possibly related' framing
    (not 'related to') because the match is heuristic, not
    curator-declared. Honest framing tells the reader the link is
    inferred and may need verification."""
    print("=== crosslinks use honest heuristic framing ===")
    site_dir = REPO_ROOT / "corpus_site"
    we_page = (
        site_dir / "worked-examples"
        / "four-llms-on-bitcoin-retirement-2026" / "index.html"
    )
    corpus_page = (
        site_dir / "decision-readiness" / "corpus"
        / "four-llms-bitcoin-claude" / "index.html"
    )
    if we_page.is_file():
        html = we_page.read_text(encoding="utf-8")
        _check(
            "heuristic match" in html.lower()
            or "not curator-declared" in html.lower(),
            "worked-example crosslinks must frame as heuristic; "
            "without honest framing readers may treat inferred "
            "links as authoritative",
        )
    if corpus_page.is_file():
        html = corpus_page.read_text(encoding="utf-8")
        _check(
            "heuristic match" in html.lower()
            or "not curator-declared" in html.lower(),
            "corpus crosslinks must frame as heuristic",
        )
    print("  PASS\n")


def test_corpus_entry_pages_carry_citation_blocks():
    """Each corpus entry page renders a citation block with
    plain-text + BibTeX form. Researchers citing 'the claude
    bitcoin response from Frame Check's validation corpus' need
    a canonical citation; without it each citer reinvents the
    format. Mirror of the library entry citation block pattern."""
    print("=== corpus entry pages carry citation blocks ===")
    site_dir = REPO_ROOT / "corpus_site"
    if not site_dir.is_dir():
        print("  SKIP  (corpus_site not built)\n")
        return
    page = (
        site_dir / "decision-readiness" / "corpus"
        / "four-llms-bitcoin-claude" / "index.html"
    )
    if not page.is_file():
        print("  SKIP  (corpus entry page absent)\n")
        return
    html = page.read_text(encoding="utf-8")
    _check(
        "How to cite" in html,
        "corpus entry should have 'How to cite' section",
    )
    _check(
        "VALIDATION CORPUS" in html,
        "corpus entry citation should include [VALIDATION CORPUS] "
        "marker so citers signal this is research data, not the "
        "live product",
    )
    _check(
        "@misc" in html and "Lucic" in html,
        "corpus entry should have BibTeX form with author",
    )
    _check(
        "experimental" in html.lower(),
        "corpus citation should note experimental status (Phase 2 "
        "validation pending)",
    )
    # Permanent URL should match the canonical corpus_entry_ref shape
    _check(
        "https://frame.clarethium.com/corpus/decision-readiness/"
        "corpus/four-llms-bitcoin-claude/" in html,
        "corpus entry citation should include canonical permanent URL",
    )
    # CC-BY-4.0 license note
    _check(
        "CC-BY-4.0" in html,
        "corpus entry citation should declare CC-BY-4.0 license",
    )
    print("  PASS\n")


def test_how_to_cite_page_lists_corpus_and_aggregate():
    """The how-to-cite page must list ALL citable Frame Check
    artifacts. After validation corpus + aggregate shipped, the
    page must include sections for them so a researcher visiting
    the central citation page sees the full set, not just the
    pre-validation-corpus subset."""
    print("=== how-to-cite lists validation corpus + aggregate ===")
    site_dir = REPO_ROOT / "corpus_site"
    page = site_dir / "how-to-cite" / "index.html"
    if not page.is_file():
        print("  SKIP  (how-to-cite page absent)\n")
        return
    html = page.read_text(encoding="utf-8")
    # Validation corpus section
    _check(
        'id="corpus-entry"' in html,
        "how-to-cite missing corpus-entry section anchor",
    )
    _check(
        "validation corpus entry" in html.lower(),
        "how-to-cite should have a validation-corpus-entry "
        "citation section",
    )
    _check(
        "VALIDATION CORPUS" in html,
        "how-to-cite corpus section should include the "
        "[VALIDATION CORPUS] citation marker",
    )
    # Aggregate section
    _check(
        'id="aggregate"' in html,
        "how-to-cite missing aggregate section anchor",
    )
    _check(
        "decision-readiness corpus aggregate" in html.lower()
        or "corpus aggregate" in html.lower(),
        "how-to-cite should mention aggregate",
    )
    _check(
        "corpus state hash" in html.lower(),
        "how-to-cite aggregate citation should mention "
        "versioning by corpus state hash so citers can pin the "
        "exact revision",
    )
    print("  PASS\n")


if __name__ == "__main__":
    try:
        test_every_canon_entry_declares_implication()
        test_library_to_methodology_consistency()
        test_methodology_to_library_consistency()
        test_module_constant_matches_methodology()
        test_dimension_pills_helper_emits_links_for_direct_mapping_entries()
        test_dimension_pills_helper_emits_meta_tag_for_meta_side_entries()
        test_every_published_entry_renders_a_pill_or_meta_tag()
        test_methodology_page_has_dimension_anchor_ids()
        test_methodology_page_has_meta_side_section()
        test_entry_page_pill_injection_marker_exists()
        test_worked_example_backlinks_helper_inverts_frames_detected()
        test_worked_example_backlinks_render_in_library_entry_pages()
        test_aggregate_page_renders_when_aggregate_exists()
        test_methodology_page_links_to_aggregate_when_present()
        test_raters_md_exists_and_carries_required_sections()
        test_validation_invitation_page_renders_when_raters_md_exists()
        test_methodology_page_carries_phase2_invitation_cta()
        test_decision_readiness_examples_hub_renders_when_sources_exist()
        test_decision_readiness_diff_annotation_pages_render()
        test_decision_readiness_peer_annotation_pages_render()
        test_decision_readiness_rating_contrast_page_renders()
        test_methodology_page_links_to_examples_when_sources_exist()
        test_validation_page_links_to_rating_contrast()
        test_validation_corpus_surface_renders()
        test_corpus_entry_pages_carry_genre_badge_for_ai_responses()
        test_corpus_entry_pages_link_to_diff_peer_artifacts()
        test_aggregate_page_links_to_validation_corpus()
        test_methodology_page_links_to_validation_corpus()
        test_corpus_entry_pages_render_profile_inline()
        test_corpus_entry_pages_render_comparisons_inline()
        test_validation_invitation_page_links_to_corpus()
        test_aggregate_cross_question_findings_deep_link_to_corpus()
        test_rater_guide_page_renders_when_source_exists()
        test_validation_invitation_links_to_rendered_rater_guide()
        test_aggregate_cross_question_findings_carry_corpus_entries()
        test_corpus_entry_comparison_text_uses_human_labels()
        test_library_entry_pages_link_to_corpus_entries_that_fired_the_frame()
        test_corpus_fired_in_backlinks_helper_is_inverse_of_fired_library_entries()
        test_worked_example_corpus_crosslinks_render_bidirectionally()
        test_crosslinks_use_honest_heuristic_framing()
        test_corpus_entry_pages_carry_citation_blocks()
        test_how_to_cite_page_lists_corpus_and_aggregate()
        print("=== ALL CANON GRAPH CONSISTENCY TESTS PASSED ===")
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
