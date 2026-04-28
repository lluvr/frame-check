"""
Regression tests for documented Frame Check detection boundaries.

Frame Check STRATEGY.md §8 names three failure modes of the regex-based
detection approach:

  1. Dismissive mention (partial mitigation shipped). Sentence-bounded
     dismissal is caught. Dismissal spread across clauses, euphemistic
     dismissal without explicit modifiers, and structural dismissal are
     not.
  2. Promotional intent in analytical language (fundamental boundary).
     A document can sell using benchmark results and competitive
     comparisons without promotional markers. Regex cannot see intent.
  3. Stale data in present tense (fundamental boundary). Historical
     data presented in present tense evades the temporal detector.

These tests PIN the current behavior so any future detection change
is a deliberate update to a citable boundary test, not an accident.

Each test asserts what Frame Check CURRENTLY does and names what it
does NOT do in the docstring. If a detection improvement lands, the
test must update consciously. That is the point.
"""

import re

from framing import (
    detect_coverage,
    detect_voice,
    temporal_orientation,
)


# ── Failure mode 1: dismissive mention (partial mitigation) ──────────

class TestBoundaryDismissiveMention:
    """STRATEGY §8.1: sentence-bounded dismissal is caught by the
    diminisher filter (minimal, negligible, manageable, overblown).
    Dismissal spread across multiple clauses or expressed without an
    explicit modifier is NOT caught. Pinned: 2026-04-17."""

    def test_sentence_bounded_dismissal_is_caught(self):
        """Catch case: 'risks are minimal', diminisher in same sentence
        as the risk marker should suppress the risk coverage signal."""
        doc = "## Analysis\n\n" + (
            "The company has seen strong quarterly growth and expanding "
            "margins. Risks are minimal given the diversified portfolio. "
            "Operating results should continue to improve.\n"
        )
        cov = detect_coverage(doc)
        # "risks" occurrence is dismissed in the same sentence; the
        # detector suppresses it. If the count drops to 0 after
        # diminisher filtering, risks are not marked covered.
        assert cov["categories"]["risks"]["count"] == 0, (
            "Sentence-bounded dismissal ('risks are minimal') should "
            "cause the risks count to be suppressed by the diminisher."
        )

    def test_multi_clause_dismissal_is_not_caught(self):
        """Boundary case: dismissal spread across independent clauses.
        The diminisher filter is sentence-bounded; when the dismissal
        and the risk token live in different sentences, the risk token
        is counted as coverage even though the document is dismissing
        the dimension.

        This is a known boundary. If a future release widens the filter
        beyond sentence scope, this test must update accordingly. See
        STRATEGY §8.1."""
        doc = "## Analysis\n\n" + (
            "The strategy carries real risks. In practice, however, "
            "every concern on the list has been dealt with by the team "
            "and can be set aside. Execution has been textbook. "
            "Structural concerns exist. None of them are load-bearing. "
            "Leadership is confident and the plan is well-funded.\n"
        )
        cov = detect_coverage(doc)
        # Boundary: risks are "covered" here even though the doc dismisses them.
        # The diminisher filter cannot reach across sentence boundaries.
        assert cov["categories"]["risks"]["count"] >= 1, (
            "Boundary: multi-clause dismissal leaves risk tokens counted. "
            "Updating this test requires a corresponding detection change."
        )


# ── Failure mode 2: promotional intent in analytical language ────────

class TestBoundaryPromotionalInAnalytical:
    """STRATEGY §8.2: a document can sell using competitive comparisons
    and benchmark results without using promotional markers. The voice
    detector classifies on surface markers and cannot infer intent.
    This is a fundamental boundary of regex detection. Pinned: 2026-04-17."""

    def test_benchmark_heavy_doc_evades_promotional_voice(self):
        """Boundary case: a thesis that sells via numeric comparisons
        and no promotional language ('leading', 'best-in-class', etc.)
        classifies as analytical/neutral, not promotional.

        This is fundamental to regex. If addressed, it will be through
        a different mechanism (semantic narration, structural heuristic),
        not by extending the regex. See STRATEGY §8.2."""
        doc = "## Q4 Results\n\n" + (
            "Revenue grew 34% year-over-year to $2.1 billion. Gross "
            "margin was 78%, compared to peer averages of 61-64%. "
            "Operating margin reached 29% versus the sector median of "
            "18%. Customer retention was 97%, while the next-closest "
            "public comparable reported 89%. Free cash flow conversion "
            "stood at 94%, well ahead of the 70% typical in the group."
        )
        voice = detect_voice(doc)
        # detect_voice returns {'voice': 'analytical' | 'promotional' |
        # 'advisory' | ...}. The boundary assertion needs the real key.
        # Earlier draft of this test used .get('label') which returned
        # None and made the assertion trivially pass: a silent hole.
        voice_label = str(voice.get("voice", "")).lower()
        assert voice_label and "promotional" not in voice_label, (
            f"Boundary: analytical-language selling classified as "
            f"voice={voice_label!r}. Regex cannot see intent."
        )


# ── Failure mode 3: stale data in present tense ──────────────────────

class TestBoundaryStalePresentTense:
    """STRATEGY §8.3: when old data is presented in present tense
    ('the market IS worth $196B' for 2023 data), the temporal detector
    sees present-tense prose and does not flag staleness. Temporal
    orientation counts tense markers; it does not resolve claim
    timestamps against reality. Pinned: 2026-04-17."""

    def test_stale_present_tense_not_flagged_as_past(self):
        """Boundary case: a document stating historical numbers in
        present tense reads as present-oriented to the detector."""
        doc = "## Market View\n\n" + (
            "The global EV market is worth $196 billion. Tesla holds "
            "18% share. Rivian is a rising entrant. Legacy automakers "
            "are struggling to catch up. Growth is decelerating. "
            "Battery costs are declining."
        )
        temp = temporal_orientation(doc)
        # Boundary: no temporal signal identifies the data as stale.
        # The orientation will be dominated by present tense.
        dominant = temp.get("dominant") or temp.get("primary") or ""
        assert "past" not in str(dominant).lower(), (
            f"Boundary: stale data in present tense reads as "
            f"dominant={dominant!r}, not 'past'. Frame Check cannot "
            f"resolve claim timestamps."
        )
