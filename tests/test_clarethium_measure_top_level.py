"""Tests for ``clarethium_measure.py`` top-level entry points.

The detector layer functions (``structural_profile``,
``mechanism_ratio``, ``claim_density``, etc.) are exercised
indirectly through the wider integration suites. This file targets
the lower-coverage entry points:

  - ``measure()``: top-level orchestrator that runs the 11-layer
    pipeline. Source-conditional layers (4, 5, 6, 8, 11) and
    comparison-conditional layer 3 are exercised with explicit
    arguments.
  - ``temporal_consistency``, ``source_matching``,
    ``entity_provenance``, ``vocabulary_proximity``,
    ``epistemic_calibration``, ``information_novelty``,
    ``quality_profile``, ``grounding_decomposition``: pure
    layer-functions exercised directly.
  - ``extract_entities`` + ``_entity_in_source`` + ``_add_commas``
    + ``_number_in_source``: helper functions.
  - ``print_profile``: pretty-printer over the profile dict.
  - ``main()``: CLI entry point.
  - ``_range_label``: reference-distribution labeller.
"""

from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import patch

import pytest

import clarethium_measure
from clarethium_measure import (
    _add_commas,
    _entity_in_source,
    _number_in_source,
    _range_label,
    entity_provenance,
    epistemic_calibration,
    extract_entities,
    grounding_decomposition,
    information_novelty,
    measure,
    print_profile,
    quality_profile,
    source_matching,
    temporal_consistency,
    vocabulary_proximity,
)


# ================================================================
# Sample markdown docs (markdown headings required to avoid the
# "no markdown headings" UserWarning)
# ================================================================


_DOC = (
    "## Q3 Update\n\n"
    "Apple reported revenue of $89.5 billion in Q3 FY2024, up 1% "
    "year over year. Services revenue grew to $24.2 billion. "
    "iPhone revenue was $39.7 billion. According to the earnings "
    "release, gross margin was 45.2%. The company returned $25 "
    "billion to shareholders through buybacks and dividends.\n\n"
    "## Outlook\n\n"
    "Forward demand visibility has never been stronger. Hyperscaler "
    "and enterprise customers continue to drive growth across every "
    "product line. Apple Intelligence is expected to accelerate "
    "iPhone upgrades through fiscal year 2025.\n"
)

_SOURCE = (
    "## Apple Q3 FY2024 Press Release\n\n"
    "Revenue was $89.5 billion, up 1% year over year. iPhone revenue "
    "of $39.7 billion. Services revenue of $24.2 billion. Gross "
    "margin of 45.2%. The company returned $25 billion to "
    "shareholders during the quarter.\n"
)

_DOC_COMPARISON = (
    "## Q3 Update\n\n"
    "Apple reported revenue of $89.5 billion in Q3 FY2024, up 2% "
    "year over year. Services revenue grew to $24.2 billion. "
    "iPhone revenue was $40.1 billion. Gross margin was 45.0%.\n"
)


# ================================================================
# measure() top-level orchestrator
# ================================================================


class TestMeasure:
    """``measure()`` runs the 11-layer profile. Layers 4/5/6/8/11
    fire only when source is provided; layer 3 only when
    comparisons are provided."""

    def test_doc_only_runs_baseline_layers(self) -> None:
        profile = measure(_DOC)
        layers = profile["metadata"]["layers_run"]
        # Always-on layers.
        assert "structural" in layers
        assert "claim_density" in layers
        assert "presentation" in layers
        assert "information_novelty" in layers
        assert "quality_profile" in layers
        # Source-conditional layers absent.
        assert "source_fidelity" not in layers
        assert "epistemic_calibration" not in layers
        assert "grounding_decomposition" not in layers
        # Comparison-conditional layer absent.
        assert "temporal_instability" not in layers

    def test_with_source_runs_layers_4_5_6_8_11(self) -> None:
        profile = measure(_DOC, source=_SOURCE)
        layers = profile["metadata"]["layers_run"]
        assert "source_fidelity" in layers          # Layer 4
        assert "entity_provenance" in layers        # Layer 5
        assert "vocabulary_proximity" in layers     # Layer 6
        assert "epistemic_calibration" in layers    # Layer 8
        assert "grounding_decomposition" in layers  # Layer 11

    def test_with_comparisons_runs_temporal_layer(self) -> None:
        profile = measure(_DOC, comparisons=[_DOC_COMPARISON])
        assert "temporal_instability" in profile["metadata"]["layers_run"]
        assert "instability_rate" in profile["temporal_instability"]

    def test_full_pipeline_returns_metadata_block(self) -> None:
        profile = measure(_DOC, source=_SOURCE, comparisons=[_DOC_COMPARISON])
        meta = profile["metadata"]
        assert meta["version"] == "1.4"
        assert meta["has_markdown_structure"] is True
        assert isinstance(meta["cannot_detect"], list)
        # Eight named honest-limits items per the docstring claim.
        assert len(meta["cannot_detect"]) >= 5

    def test_unstructured_input_emits_warning(self) -> None:
        with pytest.warns(UserWarning, match="markdown"):
            measure("Plain text with no markdown headings at all.")


# ================================================================
# Layer-function leaves
# ================================================================


class TestSourceMatching:
    """Layer 4: programmatic number-to-source matching."""

    def test_all_numbers_in_source(self) -> None:
        result = source_matching(_DOC, _SOURCE)
        assert "unsourced_rate" in result
        assert "in_source" in result
        assert "not_in_source" in result
        assert "total_numbers" in result
        # Most numbers in _DOC appear verbatim in _SOURCE.
        assert result["unsourced_rate"] < 1.0

    def test_no_source_overlap(self) -> None:
        result = source_matching(_DOC, "## Source\n\nUnrelated text.")
        # No number overlap -> high unsourced_rate.
        assert result["unsourced_rate"] > 0.5

    def test_unsourced_details_carry_value_and_context(self) -> None:
        result = source_matching(_DOC, "## Source\n\nUnrelated.")
        for entry in result["unsourced_details"][:3]:
            assert "value" in entry
            assert "type" in entry


class TestEntityProvenance:
    """Layer 5: entity detection + source matching."""

    def test_entities_extracted(self) -> None:
        text = (
            "## Update\n\n"
            "Apple Inc. reported revenue. According to John Smith, "
            "the figures are accurate. (Smith, 2024) cited the data."
        )
        entities = extract_entities(text)
        assert isinstance(entities, list)
        # Multiple distinct entity-shapes should fire.
        types = {e["type"] for e in entities}
        # At least one type fires (ORG / PERSON / ATTRIBUTED / CITATION).
        assert types

    def test_entity_in_source_substring_match(self) -> None:
        entity = {"value": "Apple", "type": "ORG"}
        assert _entity_in_source(entity, "Apple reported revenue.") is True

    def test_entity_not_in_source(self) -> None:
        entity = {"value": "Microsoft", "type": "ORG"}
        assert _entity_in_source(entity, "Apple reported revenue.") is False

    def test_entity_provenance_returns_summary(self) -> None:
        result = entity_provenance(_DOC, _SOURCE)
        assert "unsourced_rate" in result
        assert "total_entities" in result


class TestVocabularyProximity:
    """Layer 6: content-word overlap between doc and source."""

    def test_high_overlap(self) -> None:
        # Same text on both sides -> proximity ~ 1.0.
        result = vocabulary_proximity(_DOC, _DOC)
        assert result["mean_proximity"] > 0.5

    def test_low_overlap(self) -> None:
        unrelated = "## Other\n\nClimate change affects polar regions."
        result = vocabulary_proximity(_DOC, unrelated)
        assert result["mean_proximity"] < 0.5

    def test_empty_doc_returns_zero(self) -> None:
        result = vocabulary_proximity("", _SOURCE)
        # No sentences -> mean_proximity defaults to 0.
        assert result["mean_proximity"] == 0


class TestEpistemicCalibration:
    """Layer 8: per-sentence assertion grounding check."""

    def test_returns_calibration_score(self) -> None:
        result = epistemic_calibration(_DOC, _SOURCE)
        assert "calibration_score" in result
        assert "status" in result

    def test_returns_with_no_source(self) -> None:
        # Even with empty source the function returns a dict.
        result = epistemic_calibration(_DOC, "")
        assert "calibration_score" in result


class TestInformationNovelty:
    """Layer 9: per-sentence novelty via cumulative vocabulary."""

    def test_returns_novelty_summary(self) -> None:
        result = information_novelty(_DOC)
        assert "mean_novelty" in result
        assert "repetition_rate" in result
        assert "information_decay" in result
        assert "total_sentences" in result

    def test_empty_doc(self) -> None:
        result = information_novelty("")
        assert result["mean_novelty"] == 0
        assert result["total_sentences"] == 0


class TestQualityProfile:
    """Layer 10: composite substance vs presentation index."""

    def test_full_pipeline_profile_yields_indices(self) -> None:
        profile = measure(_DOC, source=_SOURCE)
        qp = profile["quality_profile"]
        assert "substance_index" in qp
        assert "presentation_index" in qp
        assert "gap" in qp
        assert "gap_direction" in qp

    def test_baseline_doc_only_profile(self) -> None:
        profile = measure(_DOC)
        qp = profile["quality_profile"]
        # Without source, substance_index may be None (no fidelity layers).
        assert "substance_index" in qp


class TestGroundingDecomposition:
    """Layer 11: per-sentence G/F/P classification."""

    def test_returns_grounding_summary(self) -> None:
        result = grounding_decomposition(_DOC, _SOURCE)
        assert "proportions" in result
        # Proportions are G, F, P fractions summing to ~ 1.0.
        props = result["proportions"]
        for key in ("G", "F", "P"):
            assert key in props
        total = props.get("G", 0) + props.get("F", 0) + props.get("P", 0)
        assert 0.95 < total < 1.05


class TestTemporalConsistency:
    """Layer 3: cross-version number stability."""

    def test_returns_instability_summary(self) -> None:
        result = temporal_consistency(_DOC, [_DOC_COMPARISON])
        assert "instability_rate" in result
        assert "stable_count" in result
        assert "unstable_count" in result
        assert "n_versions" in result
        assert result["n_versions"] == 2

    def test_identical_versions_stable(self) -> None:
        result = temporal_consistency(_DOC, [_DOC])
        # Same text on both sides -> 0 instability.
        assert result["instability_rate"] == 0


# ================================================================
# Helper functions
# ================================================================


class TestAddCommas:
    """``_add_commas`` re-inserts thousands separators."""

    def test_short_value_returns_none(self) -> None:
        assert _add_commas("12") is None
        assert _add_commas("999") is None

    def test_decimal_returns_none(self) -> None:
        assert _add_commas("12.5") is None

    def test_thousands_inserted(self) -> None:
        assert _add_commas("2000") == "2,000"
        assert _add_commas("1234567") == "1,234,567"

    def test_unparseable_returns_none(self) -> None:
        assert _add_commas("abcd") is None


class TestNumberInSource:
    """``_number_in_source`` matches a normalized number against
    source text accounting for type-specific formatting."""

    def test_dollar_match(self) -> None:
        num = {"value": "100", "type": "dollar"}
        assert _number_in_source(num, "Revenue was $100 in Q3.") is True

    def test_dollar_not_in_source(self) -> None:
        num = {"value": "999", "type": "dollar"}
        assert _number_in_source(num, "Revenue was $100 in Q3.") is False

    def test_percentage_match(self) -> None:
        num = {"value": "12", "type": "percentage"}
        assert _number_in_source(num, "Margin was 12%.") is True

    def test_dollar_with_commas(self) -> None:
        # _number_in_source falls back to comma-formatted: $45000 -> $45,000.
        num = {"value": "45000", "type": "dollar"}
        assert _number_in_source(num, "Revenue was $45,000 last year.") is True

    def test_multiplier_match(self) -> None:
        num = {"value": "3", "type": "multiplier"}
        assert _number_in_source(num, "Growth of 3x year-over-year.") is True


class TestRangeLabel:
    """``_range_label`` places a score against reference distribution
    ranges (mean +/- sd)."""

    def test_within_one_sd_uses_tilde(self) -> None:
        ref = {"baseline": {"mean": 0.5, "sd": 0.1}}
        # Score 0.55 is within 0.1 of mean 0.5 -> "~baseline".
        assert _range_label(0.55, ref) == "~baseline"

    def test_above_mean_plus_sd_uses_gt(self) -> None:
        ref = {"baseline": {"mean": 0.5, "sd": 0.1}}
        # Score 0.8 > 0.6 (mean+sd) -> ">baseline".
        assert _range_label(0.8, ref) == ">baseline"

    def test_below_mean_minus_sd_returns_outside_range(self) -> None:
        ref = {"baseline": {"mean": 0.5, "sd": 0.1}}
        # Score 0.1 < 0.4 (mean-sd) -> not within sd, not above
        # mean+sd; falls through to "outside reference range".
        assert _range_label(0.1, ref) == "outside reference range"

    def test_multiple_conditions_returns_first_two(self) -> None:
        ref = {
            "alpha": {"mean": 0.5, "sd": 0.1},
            "beta": {"mean": 0.55, "sd": 0.1},
            "gamma": {"mean": 0.6, "sd": 0.1},
        }
        # All three within sd of 0.5; sorted lookup returns alpha,
        # beta first; the [:2] cap drops gamma.
        out = _range_label(0.5, ref)
        assert "alpha" in out
        assert "beta" in out
        assert "gamma" not in out


# ================================================================
# print_profile + main CLI
# ================================================================


class TestPrintProfile:
    """``print_profile`` prints a human-readable summary of the
    measure() output."""

    def test_prints_metadata_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        profile = measure(_DOC)
        print_profile(profile)
        out = capsys.readouterr().out
        assert "CLARETHIUM MEASURE" in out
        # Metadata version line.
        assert "v1.4" in out

    def test_prints_with_full_pipeline(self, capsys: pytest.CaptureFixture[str]) -> None:
        profile = measure(_DOC, source=_SOURCE, comparisons=[_DOC_COMPARISON])
        print_profile(profile)
        out = capsys.readouterr().out
        # Each layer name appears.
        assert "STRUCTURAL" in out
        assert "CLAIM DENSITY" in out


class TestMainCli:
    """``main()`` is the argparse entry. Builds doc/source files
    on disk and dispatches into measure() + print_profile()."""

    def test_main_with_doc_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        with tempfile.TemporaryDirectory() as td:
            doc_path = os.path.join(td, "doc.md")
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(_DOC)
            with patch.object(sys, "argv", ["clarethium_measure.py", "--doc", doc_path]):
                clarethium_measure.main()
        out = capsys.readouterr().out
        assert "CLARETHIUM MEASURE" in out

    def test_main_with_doc_source_compare(self, capsys: pytest.CaptureFixture[str]) -> None:
        with tempfile.TemporaryDirectory() as td:
            doc_path = os.path.join(td, "doc.md")
            src_path = os.path.join(td, "src.md")
            cmp_path = os.path.join(td, "cmp.md")
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(_DOC)
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(_SOURCE)
            with open(cmp_path, "w", encoding="utf-8") as f:
                f.write(_DOC_COMPARISON)
            with patch.object(sys, "argv", [
                "clarethium_measure.py",
                "--doc", doc_path,
                "--source", src_path,
                "--compare", cmp_path,
            ]):
                clarethium_measure.main()
        out = capsys.readouterr().out
        assert "CLARETHIUM MEASURE" in out

    def test_main_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json
        with tempfile.TemporaryDirectory() as td:
            doc_path = os.path.join(td, "doc.md")
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(_DOC)
            with patch.object(sys, "argv", [
                "clarethium_measure.py", "--doc", doc_path, "--json",
            ]):
                clarethium_measure.main()
        out = capsys.readouterr().out
        # JSON output is parseable.
        parsed = json.loads(out)
        assert "metadata" in parsed
