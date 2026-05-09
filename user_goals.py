"""User goal awareness for divergence ranking.

The user (or agent on behalf of the user) signals a goal: decide,
brainstorm, persuade, learn, audit. The divergence ranking shifts
accordingly: deciding emphasizes falsification, brainstorming
emphasizes perspective diversity, persuading emphasizes counter-
perspectives, learning emphasizes full taxonomy, auditing applies
the catalog/coverage/genre logic without goal override.

The substrate stays deterministic: per-goal maps are curated text
and the relevance lookup is exact-match against canon FVS IDs. No
LLM is invoked. The sort respects all prior ranking dimensions
(signal_strength tier first, then goal_relevance, then
genre_relevance, then frame_id) so goal awareness composes with
the existing layers rather than overriding them.

The "audit" goal is the default-equivalent: no goal-specific
re-ranking is applied. It is named explicitly so the agent can
surface "auditing this document" as a distinct posture from
"deciding from this document."
"""

from __future__ import annotations

from typing import Optional


# Bounded goal set. Adding a new goal requires updating this map
# (paired with any agent_guidance teaching).
_GOALS = (
    "decide",
    "brainstorm",
    "persuade",
    "learn",
    "audit",
)


# Per-goal load-bearing absence maps. Each goal lists FVS IDs in
# priority order with curated reasons explaining why the absent
# frame is load-bearing for that goal. Reading-form prose; not
# verdict-form. The "audit" goal carries an empty list because the
# existing catalog/coverage/genre logic already serves the
# sovereignty-audit case.
_GOAL_LOAD_BEARING_FRAMES = {
    "decide": [
        (
            "FVS-007",
            ("When the goal is to decide, failure-framing absence is "
            "the load-bearing structural gap: a document without "
            "falsification conditions cannot be stress-tested at "
            "decision time, and the decision rests on the document's "
            "framing rather than on tested grounds.")
        ),
        (
            "FVS-009",
            ("When deciding, risk-frame absence leaves downside "
            "structurally invisible; the reader cannot weigh the "
            "decision against the failures the document does not "
            "name.")
        ),
        (
            "FVS-014",
            ("When deciding from forward-looking content, temporal-"
            "anchoring absence means the projections lack a "
            "validity window; the figures may already be expired or "
            "may shift before the decision matures.")
        ),
        (
            "FVS-012",
            ("Uncertainty-frame absence at decision time leaves the "
            "reader without explicit confidence calibration; "
            "decisions are made against the document's level of "
            "decisiveness rather than the evidence's level of "
            "support.")
        ),
    ],
    "brainstorm": [
        (
            "FVS-011",
            ("When brainstorming, stakeholder-frame absence names "
            "the missing options most directly: whose perspective "
            "the framing leaves out is exactly the brainstorm "
            "expansion the document does not yet carry.")
        ),
        (
            "FVS-001",
            ("Frame-amplification awareness is load-bearing for "
            "brainstorming: surfacing which framing the document "
            "amplifies lets the brainstorm name and challenge the "
            "default reading explicitly.")
        ),
        (
            "FVS-009",
            ("Risk-frame absence in brainstorming surfaces the "
            "downside-lens option that complements an upside-only "
            "exploration.")
        ),
        (
            "FVS-008",
            ("Growth-frame absence in brainstorming surfaces the "
            "upside-lens option that complements a downside-only "
            "exploration.")
        ),
    ],
    "persuade": [
        (
            "FVS-017",
            ("When persuading, false-balance absence (no detected "
            "alternative perspective) means the persuasive content "
            "has no opposition surface; an audience that probes "
            "will find structural one-sidedness.")
        ),
        (
            "FVS-011",
            ("Stakeholder-frame absence in persuasive content leaves "
            "the question unanswered: whose interests does this "
            "argument serve? The audience asks; the framing does "
            "not answer.")
        ),
        (
            "FVS-007",
            ("Persuasion without falsification conditions is "
            "structurally absolute; a persuasion that survives "
            "scrutiny names what would change the position, and "
            "absence of that structure invites the audience to "
            "supply the falsification themselves.")
        ),
        (
            "FVS-009",
            ("Risk-frame absence in persuasion leaves the audience "
            "to imagine the downside; the persuasion stronger when "
            "it names the risks it argues are worth bearing.")
        ),
    ],
    "learn": [
        (
            "FVS-001",
            ("Learning a topic requires seeing the framing the "
            "content amplifies; without that awareness, the reader "
            "absorbs a particular reading as if it were the topic "
            "itself.")
        ),
        (
            "FVS-014",
            ("Learning a topic requires temporal context: when did "
            "this hold? When does it expire? Absence of anchoring "
            "leaves the topic position-less in time.")
        ),
        (
            "FVS-011",
            ("Learning a topic requires the stakeholder map: who "
            "this affects, whose perspective is included, whose is "
            "missing. Absence leaves the topic abstract from the "
            "people it serves.")
        ),
        (
            "FVS-016",
            ("Learning requires citable authority: claims that "
            "cannot be traced cannot be verified; absence of "
            "FVS-016 leaves the reader with content but not with "
            "the means to extend or audit it.")
        ),
    ],
    "audit": [],
}


def get_user_goals() -> tuple:
    """Return the canonical goal set for tool inputSchema enumeration."""
    return _GOALS


def get_goal_load_bearing_frames(goal: str) -> list[tuple[str, str]]:
    """Return the ordered list of (fvs_id, reason) tuples for a
    user goal's load-bearing absences. Returns an empty list when
    the goal is None, unknown, or is 'audit' (the default-
    equivalent posture)."""
    if not goal:
        return []
    return list(_GOAL_LOAD_BEARING_FRAMES.get(goal, []))


def get_goal_relevance(fvs_id: str, goal: str) -> Optional[dict]:
    """Return per-frame goal relevance for an FVS ID under the
    chosen user goal. None when:
      - goal is None, unknown, or 'audit'
      - fvs_id is not in the goal's load-bearing list

    Output:
      {
        "relevant_for_goal": True,
        "priority": int (1 = most load-bearing for the goal),
        "reason": str,
      }
    """
    if not fvs_id or not goal:
        return None
    bearings = _GOAL_LOAD_BEARING_FRAMES.get(goal)
    if not bearings:
        return None
    for idx, (canon_id, reason) in enumerate(bearings, start=1):
        if canon_id == fvs_id:
            return {
                "relevant_for_goal": True,
                "priority": idx,
                "reason": reason,
            }
    return None
