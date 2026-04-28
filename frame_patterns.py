"""Named structural patterns over present-frame + absent-frame
combinations, with corpus prevalence as empirical anchoring.

Item 4 of the substrate-side composition roadmap, built on Items 2
(genre classifier), 3 (per-genre absence ranking), and 5/6/7
(corpus context). Where the divergence block previously surfaced
absences and clusters separately, named patterns surface
recognized structural shapes that combine present and absent
frames into a single named composition with curated prose and
empirical anchoring from the corpus.

Substrate stays deterministic: pattern matching is set membership;
no LLM is invoked. Corpus prevalence is a count over per-document
frame fire sets, computed by corpus_intelligence's aggregator.

Pattern definitions are curated. Each pattern carries:
  - id: stable kebab-case identifier
  - name: human-readable name
  - trigger: which frames must be present/absent and (optionally)
    which genre the document must classify into
  - reading: curated reading-form prose composing the pattern
  - load_bearing_dimensions: canon-graph dimensions this pattern
    speaks to

Adding a new pattern requires a curation review (the pattern is
the substrate's claim about a recognizable structural shape) and
an entry in this module's _PATTERNS list.
"""

from __future__ import annotations

from typing import Optional


# Pattern definitions. Each is a dict with the fields documented
# above. Order in _PATTERNS is stable for deterministic output;
# matching patterns are emitted in the order defined here.
_PATTERNS = [
    {
        "id": "recommendation-without-falsification",
        "name": "Recommendation without falsification",
        "trigger": {
            # Detector semantics: FVS-007 fires (matched) when the
            # "failure framing absence" detector triggers, which means
            # the document LACKS falsification conditions per
            # coverage signal. Pairing with absent risk-frame-active
            # (FVS-009) or temporal anchoring (FVS-014) names two
            # structural surfaces that would let the pick be
            # stress-tested.
            #
            # falsification_max_count = 0 is the additional
            # discriminator: the document must ALSO lack explicit
            # "would be wrong if" statements per
            # frame_deepening.falsification_conditions. Without this,
            # FVS-007 fires too easily on coverage signals alone, and
            # the pattern surfaces as a label rather than a pattern.
            "genre": "recommendation",
            "frames_present_all": ["FVS-007"],
            "frames_absent_any": ["FVS-009", "FVS-014"],
            "falsification_max_count": 0,
        },
        "reading": (
            "Document recommends a pick while Frame Check's failure-"
            "framing absence detector fires (FVS-007), and either "
            "FVS-009 Risk Frame or FVS-014 Temporal Anchoring is not "
            "actively detected. Recommendations without falsification "
            "conditions cannot be stress-tested; the pick stands or "
            "falls without the structure that would let a reader see "
            "when it stops being right."
        ),
        "load_bearing_dimensions": ["counterfactual"],
    },
    {
        "id": "growth-without-risk",
        "name": "Growth without risk",
        "trigger": {
            "frames_present_all": ["FVS-008"],
            "frames_absent_all": ["FVS-009"],
        },
        "reading": (
            "FVS-008 Growth Frame fires with FVS-009 Risk Frame "
            "absent. The document foregrounds upside while leaving "
            "downside structurally invisible. The growth narrative "
            "is the structure; the risk surface that would balance "
            "it is not."
        ),
        "load_bearing_dimensions": ["coverage", "counterfactual"],
    },
    {
        "id": "analysis-without-grounding",
        "name": "Analysis without grounding",
        "trigger": {
            # FVS-016 absence means the Authority by Citation
            # detector did not fire (sourced_pct < 50%). The
            # additional sourced_pct_max=20 discriminator
            # tightens this: the analysis must have very low
            # source attribution (< 20%), not merely below the
            # 50% citation-density firing threshold. Without this
            # tightening, any analysis doc without abundant
            # citations triggers the pattern, which means it fires
            # on most analyses and stops being discriminating.
            "genre": "analysis",
            "frames_absent_all": ["FVS-016"],
            "frames_absent_any": ["FVS-012", "FVS-017"],
            "sourced_pct_max": 20,
        },
        "reading": (
            "Analysis without FVS-016 Authority by Citation, paired "
            "with absent FVS-012 Uncertainty Frame or FVS-017 False "
            "Balance. The analysis reads more decisive than its "
            "evidence supports; the structure that would let a "
            "reader verify or hedge is not present."
        ),
        "load_bearing_dimensions": ["evidence", "calibration"],
    },
    {
        "id": "narrative-without-stakeholders",
        "name": "Narrative without stakeholders",
        "trigger": {
            # Narrative documents without any stakeholder roles
            # mentioned (regulators, investors, customers,
            # employees, competitors, communities, suppliers,
            # management, policymakers, public, industry_actors,
            # affected_populations). Story without people; events
            # without perspective. The trigger uses both _min and
            # _max=0: _min requires the signal to be present (so
            # the pattern abstains on short docs where
            # frame_deepening detector returns None), and _max
            # constrains it to zero. Together: stakeholder_role_
            # count must be exactly 0 AND signal must be present.
            "genre": "narrative",
            "stakeholder_role_count_min": 0,
            "stakeholder_role_count_max": 0,
        },
        "reading": (
            "Narrative without stakeholders is structurally "
            "abstract: the document tells a story or sequence of "
            "events but does not name whose perspective the story "
            "carries or whose interests it serves. The reader sees "
            "events but not the people they affect. Stakeholder "
            "absence in narrative is the structural gap that "
            "leaves the story untestable against affected parties."
        ),
        "load_bearing_dimensions": ["coverage"],
    },
    {
        "id": "instruction-without-failure-modes",
        "name": "Instruction without failure modes",
        "trigger": {
            # Procedural instruction that does not name what can
            # go wrong. FVS-009 (Risk Frame) absent + zero explicit
            # falsification statements = the document presents
            # steps as if they cannot fail. Common in setup guides,
            # how-tos, and operational documentation where
            # troubleshooting is the missing surface.
            "genre": "instruction",
            "frames_absent_all": ["FVS-009"],
            "falsification_max_count": 0,
        },
        "reading": (
            "Instruction without failure modes presents the "
            "procedure as if it cannot go wrong. The document "
            "lists steps without warning of common failure "
            "conditions, edge cases, or troubleshooting guidance. "
            "The reader follows the steps but lacks the structural "
            "scaffold to recognize when the procedure is failing "
            "or what to do when a step's preconditions are not met."
        ),
        "load_bearing_dimensions": ["counterfactual"],
    },
    {
        "id": "forward-projection-without-anchoring",
        "name": "Forward projection without anchoring",
        "trigger": {
            # Document makes substantial forward-looking claims
            # (projection_phrase_count >= 2: phrases like "by
            # 2030", "next decade", "in five years") and carries
            # zero explicit falsification statements. The pattern
            # surfaces when projections are made without naming
            # validity windows or conditions under which they
            # would be revised. Genre-agnostic. The FVS-014
            # detector fires when temporal orientation is dominant
            # (e.g., future_pct >= 60%); that is the case this
            # pattern targets, so FVS-014 absent is NOT a trigger
            # condition here.
            "projection_phrase_count_min": 2,
            "falsification_max_count": 0,
        },
        "reading": (
            "Forward-projection without anchoring: the document "
            "carries forward-looking claims (projection phrases "
            "like 'by 2030', 'next decade', or 'in five years') "
            "but does not anchor those projections to validity "
            "windows. The reader has predictions but not their "
            "half-life: when do these projections expire? What "
            "would have to be true for them to hold or fail?"
        ),
        "load_bearing_dimensions": ["counterfactual", "calibration"],
    },
    {
        "id": "cited-but-promotional",
        "name": "Cited but promotional",
        "trigger": {
            # Authority by Citation fires (sourced_pct >= 50%)
            # while voice classifies as promotional. Citations
            # carried in promotional register: the structural
            # shape suggests cherry-picking (citations selected
            # to support a sales-shaped argument rather than to
            # enable verification). Distinct from
            # analysis-without-grounding (which fires when
            # citations are absent); this pattern fires when
            # citations are PRESENT but the voice undermines them.
            "frames_present_all": ["FVS-016"],
            "voice_match": "promotional",
        },
        "reading": (
            "Cited but promotional: the document carries "
            "substantive citation density (FVS-016 Authority by "
            "Citation fires) yet the voice classifies as "
            "promotional. Citations in a sales-shaped voice can "
            "mask cherry-picking: the structural mix of evidence-"
            "claim and persuasive register lets the document "
            "appear authoritative while selecting only sources "
            "that support its position. The reader can ask "
            "whether the citations were selected for verification "
            "or for persuasion."
        ),
        "load_bearing_dimensions": ["evidence"],
    },
    {
        "id": "advocacy-without-counter-perspective",
        "name": "Advocacy without counter-perspective",
        "trigger": {
            # FVS-017 (False Balance) is in the DEFERRED rule set
            # in frame_library.py and never fires positively, so
            # FVS-017 absent is trivially true on every document.
            # The pattern's real discriminator is the stakeholder
            # role count: advocacy with very few stakeholders named
            # (<= 1) is structurally one-sided. Without this
            # discriminator, the pattern fires on every advocacy
            # document.
            "genre": "advocacy",
            "frames_absent_all": ["FVS-017"],
            "frames_absent_any": ["FVS-009", "FVS-011"],
            "stakeholder_role_count_max": 1,
        },
        "reading": (
            "Advocacy without FVS-017 False Balance and either "
            "FVS-009 Risk Frame or FVS-011 Stakeholder Frame "
            "absent. The argument is structurally one-sided: the "
            "alternative-perspectives surface and either the risk "
            "surface or the stakeholder map are not present. The "
            "reader is asked to take a position without the "
            "structure that would let them see what would oppose "
            "it."
        ),
        "load_bearing_dimensions": ["coverage"],
    },
]


def _trigger_matches(
    trigger: dict,
    matched_ids: set,
    absent_ids: set,
    genre: Optional[str],
    doc_signals: Optional[dict] = None,
) -> bool:
    """Return True when the trigger conditions hold against the
    given document signal.

    Trigger fields (all optional; absent fields are unconstrained):
      genre: must equal the document's classified genre exactly
      frames_present_all: every listed frame must be in matched_ids
      frames_absent_all: every listed frame must be in absent_ids
      frames_present_any: at least one listed frame must be present
      frames_absent_any: at least one listed frame must be absent
      falsification_max_count: doc_signals.falsification_count <= this
      sourced_pct_max: doc_signals.sourced_pct <= this
      stakeholder_role_count_max: doc_signals.stakeholder_role_count <= this
      stakeholder_role_count_min: doc_signals.stakeholder_role_count >= this
      projection_phrase_count_min: doc_signals.projection_phrase_count >= this
      voice_match: doc_signals.voice_label must equal this string
      hedge_ratio_max: doc_signals.hedge_ratio <= this

    The frame_deepening discriminators (falsification_max_count,
    sourced_pct_max, stakeholder_role_count_max) are how a pattern
    distinguishes itself from a label. Without them, a pattern that
    only constrains genre + FVS membership fires on most documents
    in its target genre. With them, the pattern fires only when
    document content evidence confirms the structural shape.
    """
    if "genre" in trigger and trigger["genre"] != genre:
        return False
    if "frames_present_all" in trigger:
        for fid in trigger["frames_present_all"]:
            if fid not in matched_ids:
                return False
    if "frames_absent_all" in trigger:
        for fid in trigger["frames_absent_all"]:
            if fid not in absent_ids:
                return False
    if "frames_present_any" in trigger:
        if not any(
            fid in matched_ids for fid in trigger["frames_present_any"]
        ):
            return False
    if "frames_absent_any" in trigger:
        if not any(
            fid in absent_ids for fid in trigger["frames_absent_any"]
        ):
            return False
    # Frame-deepening discriminators. None of these fire when
    # doc_signals is None; the trigger then degrades to the
    # FVS-only logic above. When doc_signals is provided, each
    # constraint is checked against the corresponding signal.
    signals = doc_signals or {}
    if "falsification_max_count" in trigger:
        fc = signals.get("falsification_count")
        if fc is not None and fc > trigger["falsification_max_count"]:
            return False
    if "sourced_pct_max" in trigger:
        sp = signals.get("sourced_pct")
        if sp is not None and sp > trigger["sourced_pct_max"]:
            return False
    if "stakeholder_role_count_max" in trigger:
        sc = signals.get("stakeholder_role_count")
        if (
            sc is not None
            and sc > trigger["stakeholder_role_count_max"]
        ):
            return False
    if "stakeholder_role_count_min" in trigger:
        sc = signals.get("stakeholder_role_count")
        # Min constraints fail when signal is unavailable; the
        # pattern requires the signal be present and meet the
        # threshold. Without this, "min" patterns would degrade
        # to FVS-only on short docs and fire too often.
        if sc is None or sc < trigger["stakeholder_role_count_min"]:
            return False
    if "projection_phrase_count_min" in trigger:
        pc = signals.get("projection_phrase_count")
        if pc is None or pc < trigger["projection_phrase_count_min"]:
            return False
    if "voice_match" in trigger:
        vl = signals.get("voice_label")
        if vl is None or vl != trigger["voice_match"]:
            return False
    if "hedge_ratio_max" in trigger:
        hr = signals.get("hedge_ratio")
        if hr is not None and hr > trigger["hedge_ratio_max"]:
            return False
    return True


def match_patterns(
    matched_frame_ids: list[str] | set[str],
    absent_frame_ids: list[str] | set[str],
    genre: Optional[str],
    doc_signals: Optional[dict] = None,
) -> list[dict]:
    """Return the list of triggered patterns for the given
    document signal. Each entry is a copy of the pattern definition
    with `supporting_evidence` attached, naming which frames in
    matched_ids and absent_ids contributed to the trigger.

    `doc_signals` (optional dict) carries frame_deepening,
    epistemic, and voice/claims discriminators that patterns may
    require for tightening beyond FVS membership. Recognized keys:
      falsification_count: int (from
        analysis.frame_deepening.falsification_conditions
        .primary_match_count)
      stakeholder_role_count: int (from
        analysis.frame_deepening.stakeholder_map.role_count)
      projection_phrase_count: int (from
        analysis.frame_deepening.temporal_scope
        .projection_phrase_count)
      sourced_pct: float (from analysis.epistemic.sourced_pct)
      voice_label: str (from analysis.voice.classification:
        promotional / prescriptive / analytical / descriptive /
        advisory)
      hedge_ratio: float (hedged_count / total_claims, computed
        from analysis.claims_extracted)

    Without doc_signals, patterns degrade to FVS-only triggers.

    Substrate is deterministic. Same inputs produce the same output
    in the same order.
    """
    matched = set(matched_frame_ids)
    absent = set(absent_frame_ids)
    results: list[dict] = []
    for pattern in _PATTERNS:
        trigger = pattern["trigger"]
        if not _trigger_matches(
            trigger, matched, absent, genre, doc_signals,
        ):
            continue
        # Supporting evidence: which frames in the trigger lists
        # actually fired or absented in this document.
        evidence = {}
        if "frames_present_all" in trigger:
            evidence["frames_present"] = sorted(
                fid for fid in trigger["frames_present_all"]
                if fid in matched
            )
        if "frames_absent_all" in trigger:
            evidence["frames_absent_required"] = sorted(
                fid for fid in trigger["frames_absent_all"]
                if fid in absent
            )
        if "frames_present_any" in trigger:
            evidence.setdefault("frames_present", []).extend(
                fid for fid in trigger["frames_present_any"]
                if fid in matched
            )
            evidence["frames_present"] = sorted(
                set(evidence.get("frames_present", []))
            )
        if "frames_absent_any" in trigger:
            evidence["frames_absent_optional_match"] = sorted(
                fid for fid in trigger["frames_absent_any"]
                if fid in absent
            )
        result = {
            "id": pattern["id"],
            "name": pattern["name"],
            "reading": pattern["reading"],
            "load_bearing_dimensions": list(
                pattern["load_bearing_dimensions"]
            ),
            "trigger_genre": trigger.get("genre"),
            "supporting_evidence": evidence,
        }
        results.append(result)
    return results


def all_patterns() -> list[dict]:
    """Return a copy of all pattern definitions (for tests / docs)."""
    return [dict(p) for p in _PATTERNS]
