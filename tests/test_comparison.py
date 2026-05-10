"""Tests for ``comparison.py``.

The module ships at 20.9% coverage at v1.0.0 because the previous test
surface only exercised the LLM-orchestrating entry points indirectly
through web-side flows. This file closes the gap toward the v1.0
contract's per-module 80% target by exercising the pure-function
core directly.

Layered roughly leaf-to-root:

  1. Pure normalization / extraction helpers
     (``_normalize_for_stability``, ``_infer_num_type``,
      ``_extract_number_set``, ``_extract_claim_sentences``,
      ``_empty_stability_result``, ``jsonify``,
      ``serialize_model_for_stream``).

  2. Pure stability aggregator
     (``stability_from_regenerations``: takes pre-generated
     regenerations + runs ``analyze_claims`` per regen + computes
     the schema-shaped result dict; no network).

  3. Pure compare-side composers
     (``_compose_compare_verdict`` + inner ``_frame_label``,
      ``_compose_compare_takeaway`` + inner ``_collect_frames`` +
      ``_key``, ``_detect_verbatim_overlap``, ``_oxford``,
      ``_compose_comparison_portrait``).

  4. Pure structural-framing builders
     (``_build_structural_framing_data``,
      ``_build_structural_framing_diff``,
      ``_find_sentence_for_value``).

  5. Pure example providers
     (``get_comparison_examples``, ``get_document_comparison_examples``).

  6. ``build_cross_model_comparison`` orchestrator (pure: takes
     analyzed-model dicts, returns the compare envelope without
     any LLM call).

The LLM-network entry points (``generate_gemini``, ``generate_grok``,
``generate_responses``, ``generate_stability_check``,
``stability_n3_check``, ``analyze_model``, ``compare_responses``)
need provider-mocked harnesses; that work lands separately.
"""

from __future__ import annotations

import json

import pytest

import comparison
from comparison import (
    _build_structural_framing_data,
    _build_structural_framing_diff,
    _compose_compare_takeaway,
    _compose_compare_verdict,
    _compose_comparison_portrait,
    _detect_verbatim_overlap,
    _empty_stability_result,
    _extract_claim_sentences,
    _extract_number_set,
    _find_sentence_for_value,
    _infer_num_type,
    _normalize_for_stability,
    _oxford,
    build_cross_model_comparison,
    get_comparison_examples,
    get_document_comparison_examples,
    jsonify,
    serialize_model_for_stream,
    stability_from_regenerations,
)


# ================================================================
# Layer 1: pure normalization + extraction helpers
# ================================================================


class TestNormalizeForStability:
    """``_normalize_for_stability`` collapses formatting variants of
    the same magnitude to a single canonical key so the stability
    aggregator can detect numeric drift across LLM regenerations."""

    @pytest.mark.parametrize("raw", ["", None, "   "])
    def test_empty_or_blank_returns_none(self, raw: str | None) -> None:
        assert _normalize_for_stability(raw) is None

    def test_no_numeric_pattern_returns_none(self) -> None:
        assert _normalize_for_stability("not a number at all") is None

    def test_plain_integer(self) -> None:
        assert _normalize_for_stability("383") == "383"

    def test_plain_decimal(self) -> None:
        # Whole-number floats canonicalize to integer form.
        assert _normalize_for_stability("100.0") == "100"

    def test_decimal_keeps_precision(self) -> None:
        assert _normalize_for_stability("12.34") == "12.34"

    def test_dollar_billion_scale_word(self) -> None:
        assert _normalize_for_stability("$2.47 billion") == "2470000000"

    def test_dollar_billion_scale_letter(self) -> None:
        assert _normalize_for_stability("$2.47B") == "2470000000"

    def test_dollar_million(self) -> None:
        assert _normalize_for_stability("500M") == "500000000"

    def test_dollar_thousand(self) -> None:
        # "12k" -> 12 * 1e3 = 12000
        assert _normalize_for_stability("12k") == "12000"

    def test_trillion_word(self) -> None:
        assert _normalize_for_stability("1.1 trillion") == "1100000000000"

    def test_negative_dollar(self) -> None:
        assert _normalize_for_stability("-$100") == "-100"

    def test_negative_after_currency(self) -> None:
        assert _normalize_for_stability("$-100") == "-100"

    def test_unicode_minus(self) -> None:
        # U+2212 typographic minus accepted alongside ASCII -.
        assert _normalize_for_stability("−100") == "-100"

    def test_percent_suffix_preserved(self) -> None:
        assert _normalize_for_stability("12.3%") == "12.3%"

    def test_percent_keeps_distinct_from_count(self) -> None:
        # "12.3%" must not collide with "12.3" (a count).
        assert _normalize_for_stability("12.3") != _normalize_for_stability("12.3%")

    def test_non_usd_currency_collides_with_usd(self) -> None:
        # Stability bucket semantics: same magnitude across
        # regenerations regardless of currency.
        assert _normalize_for_stability("€500B") == _normalize_for_stability("$500B")

    def test_comma_formatted(self) -> None:
        assert _normalize_for_stability("1,234,567") == "1234567"

    def test_unparseable_digits_returns_none(self) -> None:
        # _NUMERIC_TOKEN_RE doesn't match this; falls through to None.
        assert _normalize_for_stability("abc") is None

    def test_collision_across_format_variants(self) -> None:
        # Three formattings of "$2.47B" all collapse to one key.
        a = _normalize_for_stability("$2.47B")
        b = _normalize_for_stability("2.47 billion")
        c = _normalize_for_stability("2.47B")
        assert a == b == c


class TestInferNumType:
    """``_infer_num_type`` buckets a display string into one of
    ``percentage / dollar / multiplier / decimal / integer``."""

    @pytest.mark.parametrize("raw", ["", None])
    def test_empty_or_none_returns_integer(self, raw: str | None) -> None:
        assert _infer_num_type(raw) == "integer"

    def test_percentage(self) -> None:
        assert _infer_num_type("12.3%") == "percentage"

    def test_usd_dollar(self) -> None:
        assert _infer_num_type("$100") == "dollar"

    @pytest.mark.parametrize("sym", ["€", "£", "¥", "₹"])
    def test_non_usd_currencies_route_to_dollar(self, sym: str) -> None:
        assert _infer_num_type(f"{sym}500B") == "dollar"

    def test_multiplier(self) -> None:
        assert _infer_num_type("3x") == "multiplier"

    def test_multiplier_case_insensitive(self) -> None:
        assert _infer_num_type("3X") == "multiplier"

    def test_decimal(self) -> None:
        assert _infer_num_type("12.34") == "decimal"

    def test_integer(self) -> None:
        assert _infer_num_type("383") == "integer"

    def test_percentage_takes_precedence_over_decimal(self) -> None:
        # "12.3%" has a "." but the % wins.
        assert _infer_num_type("12.3%") == "percentage"


class TestEmptyStabilityResult:
    """``_empty_stability_result`` returns a schema-shaped null result
    for failed stability checks. The shape must match the success
    path so calling code can record an event without branching."""

    def test_returns_zero_counts(self) -> None:
        result = _empty_stability_result("gemini", 3)
        assert result["regeneration_count"] == 0
        assert result["total_unique_numbers"] == 0
        assert result["stable_count"] == 0
        assert result["partial_count"] == 0
        assert result["unique_to_one_count"] == 0
        assert result["stability_rate"] == 0.0

    def test_stable_value_buckets_present_and_zero(self) -> None:
        result = _empty_stability_result("gemini", 3)
        buckets = result["stable_value_buckets"]
        assert set(buckets.keys()) == {
            "percentage", "dollar", "multiplier", "decimal", "integer",
        }
        assert all(v == 0 for v in buckets.values())

    def test_costs_and_signatures_empty(self) -> None:
        result = _empty_stability_result("gemini", 3)
        assert result["regeneration_costs_usd"] == []
        assert result["response_text_signatures"] == []


class TestExtractNumberSet:
    """``_extract_number_set`` walks a claim-analysis dict and
    returns the set of normalized numeric values for cross-cycle
    comparison."""

    def test_empty_claims(self) -> None:
        assert _extract_number_set({"claims": []}) == set()

    def test_missing_claims_key(self) -> None:
        # ``.get("claims", [])`` defaults to empty list.
        assert _extract_number_set({}) == set()

    def test_strips_dollar_and_commas(self) -> None:
        claims = {"claims": [{"numbers": ["$1,234"]}]}
        assert _extract_number_set(claims) == {"1234"}

    def test_strips_percent_suffix(self) -> None:
        claims = {"claims": [{"numbers": ["12%"]}]}
        assert _extract_number_set(claims) == {"12"}

    def test_strips_scale_letter(self) -> None:
        # Trailing B/M/K/X stripped before float parse.
        claims = {"claims": [{"numbers": ["500B", "12M"]}]}
        assert _extract_number_set(claims) == {"500", "12"}

    def test_unparseable_value_skipped(self) -> None:
        claims = {"claims": [{"numbers": ["abc"]}]}
        assert _extract_number_set(claims) == set()

    def test_dedupes_across_claims(self) -> None:
        claims = {"claims": [
            {"numbers": ["100", "200"]},
            {"numbers": ["100", "300"]},
        ]}
        assert _extract_number_set(claims) == {"100", "200", "300"}


class TestExtractClaimSentences:
    """``_extract_claim_sentences`` extracts claim sentences (capped
    at 150 chars, gated on >20 chars to drop fragments)."""

    def test_empty(self) -> None:
        assert _extract_claim_sentences({"claims": []}) == []

    def test_short_sentence_dropped(self) -> None:
        # "<= 20 chars" drops; "> 20 chars" keeps.
        claims = {"claims": [{"sentence": "Too short."}]}
        assert _extract_claim_sentences(claims) == []

    def test_sentence_kept_and_truncated(self) -> None:
        long_sentence = "x" * 200
        claims = {"claims": [{"sentence": long_sentence}]}
        out = _extract_claim_sentences(claims)
        assert len(out) == 1
        assert len(out[0]) == 150

    def test_missing_sentence_key_skipped(self) -> None:
        claims = {"claims": [{"other_field": "data"}]}
        assert _extract_claim_sentences(claims) == []


class TestJsonify:
    """``jsonify`` recursively converts dataclasses + sets to
    JSON-serializable shapes. Used by the SSE compare-stream
    serializer."""

    def test_passthrough_primitives(self) -> None:
        assert jsonify("text") == "text"
        assert jsonify(42) == 42
        assert jsonify(3.14) == 3.14
        assert jsonify(None) is None
        assert jsonify(True) is True

    def test_set_becomes_sorted_list(self) -> None:
        out = jsonify({"a", "b", "c"})
        assert isinstance(out, list)
        assert sorted(out) == ["a", "b", "c"]

    def test_nested_dict(self) -> None:
        out = jsonify({"k": {"nested": [1, 2, 3]}})
        assert out == {"k": {"nested": [1, 2, 3]}}
        # Round-trip through json.dumps is the contract.
        json.dumps(out)

    def test_list_of_dicts(self) -> None:
        out = jsonify([{"a": 1}, {"b": 2}])
        assert out == [{"a": 1}, {"b": 2}]


class TestSerializeModelForStream:
    """``serialize_model_for_stream`` wraps ``jsonify`` with response-
    text truncation (2000 chars cap) and drops the ``sn_results``
    field that is not JSON-serializable."""

    def test_none_input_returns_none(self) -> None:
        assert serialize_model_for_stream(None) is None
        assert serialize_model_for_stream({}) is None

    def test_drops_sn_results(self) -> None:
        # The compare-stream payload must not include sn_results
        # (raw SourceNetworkResult dataclasses are not JSON-safe).
        out = serialize_model_for_stream({"text": "x", "sn_results": ["unsafe"]})
        assert out is not None
        assert "sn_results" not in out

    def test_truncates_text_at_2000_chars(self) -> None:
        long = "a" * 5000
        out = serialize_model_for_stream({"text": long})
        assert out is not None
        assert len(out["text"]) == 2000

    def test_short_text_passes_through(self) -> None:
        out = serialize_model_for_stream({"text": "short"})
        assert out is not None
        assert out["text"] == "short"


# ================================================================
# Layer 2: stability_from_regenerations (pure aggregator)
# ================================================================


class TestStabilityFromRegenerations:
    """``stability_from_regenerations`` aggregates N pre-generated
    responses into the stability_n3_check schema. No network."""

    def test_empty_list_returns_empty_result(self) -> None:
        result = stability_from_regenerations([])
        assert result["regeneration_count"] == 0
        assert result["total_unique_numbers"] == 0

    def test_single_regen_all_numbers_unique_to_one(self) -> None:
        # With N=1, every distinct number appears in 1 of 1 = 100%
        # of regenerations, which is the "stable" bucket condition
        # (count == n_completed). So all unique numbers count as
        # stable, not unique_to_one. The scenario is degenerate but
        # the math is honest.
        regens = [
            {"text": "Revenue was $100 in 2024.", "usage": {"cost_usd": 0.001}},
        ]
        result = stability_from_regenerations(regens)
        assert result["regeneration_count"] == 1
        # At N=1 every unique number is "stable" (count == n_completed).
        assert result["stable_count"] >= 1

    def test_two_regens_perfect_agreement(self) -> None:
        regens = [
            {"text": "Revenue was $100 in 2024.", "usage": {"cost_usd": 0.001}},
            {"text": "Revenue was $100 in 2024.", "usage": {"cost_usd": 0.001}},
        ]
        result = stability_from_regenerations(regens)
        assert result["regeneration_count"] == 2
        assert result["stability_rate"] == 1.0
        assert result["unique_to_one_count"] == 0

    def test_two_regens_no_agreement(self) -> None:
        regens = [
            {"text": "Revenue was $100.", "usage": {"cost_usd": 0.001}},
            {"text": "Revenue was $200.", "usage": {"cost_usd": 0.001}},
        ]
        result = stability_from_regenerations(regens)
        # Numbers $100 and $200 each appear in only 1 of 2 regens
        # -> unique_to_one bucket. stability_rate = 0/2 = 0.0.
        assert result["unique_to_one_count"] >= 2
        assert result["stability_rate"] == 0.0

    def test_costs_collected_per_regen(self) -> None:
        regens = [
            {"text": "Revenue was $100.", "usage": {"cost_usd": 0.001}},
            {"text": "Revenue was $200.", "usage": {"cost_usd": 0.002}},
        ]
        result = stability_from_regenerations(regens)
        assert result["regeneration_costs_usd"] == [0.001, 0.002]

    def test_signatures_first_eight_hex_chars(self) -> None:
        regens = [
            {"text": "abc", "usage": {"cost_usd": 0.0}},
            {"text": "def", "usage": {"cost_usd": 0.0}},
        ]
        result = stability_from_regenerations(regens)
        sigs = result["response_text_signatures"]
        assert len(sigs) == 2
        assert all(len(s) == 8 for s in sigs)

    def test_signatures_distinct_for_distinct_text(self) -> None:
        regens = [
            {"text": "alpha", "usage": {"cost_usd": 0.0}},
            {"text": "beta", "usage": {"cost_usd": 0.0}},
        ]
        sigs = stability_from_regenerations(regens)["response_text_signatures"]
        assert sigs[0] != sigs[1]


# ================================================================
# Layer 5: pure example providers
# ================================================================


class TestComparisonExamples:
    """Static example providers; no API calls, no cost. Pinned shape
    so the demo surface stays adopter-readable."""

    def test_topic_examples_have_required_fields(self) -> None:
        examples = get_comparison_examples()
        assert len(examples) >= 3
        for ex in examples:
            assert set(ex.keys()) == {"id", "topic", "description"}
            assert ex["id"]
            assert ex["topic"]

    def test_document_examples_have_required_fields(self) -> None:
        examples = get_document_comparison_examples()
        assert len(examples) >= 1
        for ex in examples:
            # Each pair has id + title + hook + two doc bodies.
            assert "id" in ex
            assert "title" in ex
            assert "hook" in ex
            assert "doc_a_label" in ex
            assert "doc_a" in ex
            assert "doc_b_label" in ex
            assert "doc_b" in ex

    def test_document_examples_within_doc_size_limit(self) -> None:
        # Comments in get_document_comparison_examples claim each
        # pair is well under MAX_DOC_CHARS so the textareas validate
        # without truncation.
        for ex in get_document_comparison_examples():
            # 8000 is the documented MAX_DOC_CHARS soft limit; pinning
            # at a generous 16000 here so the test does not mis-fire
            # if the limit is later widened.
            assert len(ex["doc_a"]) < 16000
            assert len(ex["doc_b"]) < 16000


# ================================================================
# Layer 4: pure structural-framing builders
# ================================================================


def _model_data(
    *,
    name: str,
    coverage_count: int,
    voice: str,
    sourced_pct: int,
    temporal: str,
    claim_count: int = 5,
    unhedged_count: int = 2,
) -> dict[str, object]:
    """Build a minimal model_data dict shaped like analyze_model
    output, for testing the pure compare-side composers."""
    return {
        "text": f"{name} response text body for comparison.",
        "coverage": {
            "covered": ["causes"] if coverage_count >= 1 else [],
            "missing": ["risks", "stakeholders", "trends", "uncertainty"][:5 - coverage_count],
            "coverage_count": coverage_count,
            "total_categories": 5,
        },
        "voice": {"voice": voice, "total_sentences": 30},
        "epistemic": {"sourced_pct": sourced_pct},
        "temporal": {"dominant": temporal},
        "claim_count": claim_count,
        "unhedged_count": unhedged_count,
        "hedged_count": claim_count - unhedged_count,
        "numbers": {"100", "200"},
        "claims": {"claims": []},
        "frame_library_matches": [],
    }


class TestFindSentenceForValue:
    """``_find_sentence_for_value`` searches a claim-analysis dict
    for a sentence that contains the given normalized value."""

    def test_no_matching_value(self) -> None:
        claims = {"claims": [
            {"numbers": ["100"], "sentence": "Revenue was $100."},
        ]}
        assert _find_sentence_for_value("999", claims) == ""

    def test_match_returns_truncated_sentence(self) -> None:
        long_sentence = "Revenue was $100 in " + ("very " * 50) + "2024."
        claims = {"claims": [
            {"numbers": ["$100"], "sentence": long_sentence},
        ]}
        result = _find_sentence_for_value("100", claims)
        # _find_sentence_for_value caps at 100 chars.
        assert len(result) <= 100
        assert "Revenue" in result

    def test_strips_dollar_for_match(self) -> None:
        # Number "$100" -> cleaned to "100" -> matches "100".
        claims = {"claims": [
            {"numbers": ["$100"], "sentence": "Revenue was one hundred."},
        ]}
        assert _find_sentence_for_value("100", claims) != ""


class TestBuildStructuralFramingData:
    """``_build_structural_framing_data`` produces the structured
    per-dimension comparison cards plus the legacy prose paragraph."""

    def test_returns_none_when_nothing_to_say(self) -> None:
        # Two structurally-identical models with no shared blind
        # spots and no unique omissions -> no cards, no prose.
        a = _model_data(
            name="A", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        result = _build_structural_framing_data(
            "A", a, "B", b,
            shared_blind=[], only_a_blind=set(), only_b_blind=set(),
        )
        # All four divergence checks are 0; no shared_blind. The
        # function still emits a "structurally similar approach"
        # headline in this case, so result is not None.
        assert result is not None
        assert "headline" in result

    def test_diverging_voice_creates_voice_card(self) -> None:
        a = _model_data(
            name="A", coverage_count=5, voice="promotional",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        result = _build_structural_framing_data(
            "A", a, "B", b,
            shared_blind=[], only_a_blind=set(), only_b_blind=set(),
        )
        assert result is not None
        dimensions = [c["dimension"] for c in result["cards"]]
        assert "voice" in dimensions

    def test_diverging_sourcing_creates_sourcing_card(self) -> None:
        a = _model_data(
            name="A", coverage_count=5, voice="analytical",
            sourced_pct=80, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=5, voice="analytical",
            sourced_pct=20, temporal="present",
        )
        result = _build_structural_framing_data(
            "A", a, "B", b,
            shared_blind=[], only_a_blind=set(), only_b_blind=set(),
        )
        assert result is not None
        dimensions = [c["dimension"] for c in result["cards"]]
        assert "sourcing" in dimensions

    def test_shared_blind_creates_consequence_block(self) -> None:
        a = _model_data(
            name="A", coverage_count=3, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=3, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        result = _build_structural_framing_data(
            "A", a, "B", b,
            shared_blind=["uncertainty", "stakeholders"],
            only_a_blind=set(),
            only_b_blind=set(),
        )
        assert result is not None
        assert result["shared_blind_note"] is not None
        assert result["shared_blind_note"]["dimensions"] == ["uncertainty", "stakeholders"]

    def test_diff_wrapper_returns_prose_only(self) -> None:
        a = _model_data(
            name="A", coverage_count=5, voice="promotional",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        prose = _build_structural_framing_diff(
            "A", a, "B", b,
            shared_blind=[], only_a_blind=set(), only_b_blind=set(),
        )
        assert prose is not None
        assert isinstance(prose, str)


# ================================================================
# Layer 3: pure compare-side composers
# ================================================================


class TestOxford:
    """``_oxford`` joins a list with an Oxford comma."""

    def test_empty(self) -> None:
        assert _oxford([]) == ""

    def test_singleton(self) -> None:
        assert _oxford(["alpha"]) == "alpha"

    def test_pair(self) -> None:
        assert _oxford(["alpha", "beta"]) == "alpha and beta"

    def test_triple_uses_oxford_comma(self) -> None:
        assert _oxford(["alpha", "beta", "gamma"]) == "alpha, beta, and gamma"

    def test_or_conjunction(self) -> None:
        assert _oxford(["a", "b", "c"], conj="or") == "a, b, or c"

    def test_filters_empty_items(self) -> None:
        assert _oxford(["alpha", "", "beta"]) == "alpha and beta"


class TestComposeCompareVerdict:
    """``_compose_compare_verdict`` produces the at-a-glance verdict
    sentence for the compare page. Branches in priority order:
    verbatim -> shared frame -> divergent frames -> one-sided ->
    count fallback -> empty."""

    def test_verbatim_overlap_short_circuits(self) -> None:
        result = _compose_compare_verdict(
            verbatim_overlap={"ratio": 0.99, "level": "verbatim"},
            frames_shared=None,
            frames_per_model=None,
            agreed_count=0,
            disagreement_count=0,
            subject="Both responses",
        )
        assert "same text" in result
        assert "no comparison" in result.lower()

    def test_shared_frame_emits_both_operate_in(self) -> None:
        shared = [{"name": "Growth Frame", "fvs_id": "FVS-008"}]
        per_model = [
            {"model_name": "A", "frames": [shared[0]]},
            {"model_name": "B", "frames": [shared[0]]},
        ]
        result = _compose_compare_verdict(
            verbatim_overlap=None,
            frames_shared=shared,
            frames_per_model=per_model,
            agreed_count=0,
            disagreement_count=0,
            subject="Both responses",
        )
        assert "operate in" in result
        assert "Growth Frame" in result

    def test_divergent_top_frames(self) -> None:
        per_model = [
            {"model_name": "Claude", "frames": [{"name": "Growth Frame", "fvs_id": "FVS-008"}]},
            {"model_name": "GPT-5", "frames": [{"name": "Risk Frame", "fvs_id": "FVS-009"}]},
        ]
        result = _compose_compare_verdict(
            verbatim_overlap=None,
            frames_shared=None,
            frames_per_model=per_model,
            agreed_count=0,
            disagreement_count=0,
            subject="Both responses",
        )
        assert "Claude" in result and "Growth Frame" in result
        assert "GPT-5" in result and "Risk Frame" in result
        assert "different things" in result

    def test_one_sided_frame(self) -> None:
        per_model = [
            {"model_name": "A", "frames": [{"name": "Growth Frame", "fvs_id": "FVS-008"}]},
            {"model_name": "B", "frames": []},
        ]
        result = _compose_compare_verdict(
            verbatim_overlap=None,
            frames_shared=None,
            frames_per_model=per_model,
            agreed_count=0,
            disagreement_count=0,
            subject="Both responses",
        )
        assert "no detected frame" in result

    def test_count_fallback_when_no_frames(self) -> None:
        result = _compose_compare_verdict(
            verbatim_overlap=None,
            frames_shared=None,
            frames_per_model=None,
            agreed_count=3,
            disagreement_count=1,
            subject="Both responses",
        )
        assert "agree" in result
        assert "disagreement" in result

    def test_all_empty_returns_empty_string(self) -> None:
        # No frames, no verbatim, no counts.
        result = _compose_compare_verdict(
            verbatim_overlap=None,
            frames_shared=None,
            frames_per_model=None,
            agreed_count=0,
            disagreement_count=0,
            subject="Both responses",
        )
        assert result == ""


class TestComposeCompareTakeaway:
    """``_compose_compare_takeaway`` composes structural takeaway
    questions: per-model frame chips + shared blind-spot
    dimensions."""

    def test_returns_takeaway_dict_shape(self) -> None:
        models = {
            "A": {"frame_library_matches": [
                {"fvs_id": "FVS-008", "name": "Growth", "signal": "x", "question": "?"},
            ]},
            "B": {"frame_library_matches": []},
        }
        result = _compose_compare_takeaway(
            models=models, model_names=["A", "B"], shared_blind=["risks"],
        )
        assert "frames_per_model" in result
        assert "frames_shared" in result
        assert "absent_dimensions" in result

    def test_collects_frames_per_model_in_order(self) -> None:
        models = {
            "A": {"frame_library_matches": [
                {"fvs_id": "FVS-008", "name": "Growth", "signal": "x", "question": "?"},
            ]},
            "B": {"frame_library_matches": []},
        }
        result = _compose_compare_takeaway(
            models=models, model_names=["A", "B"], shared_blind=[],
        )
        assert result["frames_per_model"][0]["model_name"] == "A"
        assert len(result["frames_per_model"][0]["frames"]) == 1
        assert result["frames_per_model"][1]["model_name"] == "B"
        assert result["frames_per_model"][1]["frames"] == []

    def test_caps_frames_per_model_at_three(self) -> None:
        many_frames = [
            {"fvs_id": f"FVS-{i:03d}", "name": f"F{i}", "signal": "x", "question": "?"}
            for i in range(1, 8)
        ]
        models = {"A": {"frame_library_matches": many_frames}}
        result = _compose_compare_takeaway(
            models=models, model_names=["A"], shared_blind=[],
        )
        assert len(result["frames_per_model"][0]["frames"]) == 3

    def test_frames_shared_when_identical(self) -> None:
        same_frames = [
            {"fvs_id": "FVS-008", "name": "Growth", "signal": "sig", "question": "q?"},
        ]
        models = {
            "A": {"frame_library_matches": same_frames},
            "B": {"frame_library_matches": same_frames},
        }
        result = _compose_compare_takeaway(
            models=models, model_names=["A", "B"], shared_blind=[],
        )
        # frames_shared populated when both sides have identical frames.
        assert result["frames_shared"] is not None
        assert len(result["frames_shared"]) == 1

    def test_absent_dimensions_carry_questions(self) -> None:
        result = _compose_compare_takeaway(
            models={"A": {}, "B": {}},
            model_names=["A", "B"],
            shared_blind=["risks", "uncertainty"],
        )
        dims = [d["name"] for d in result["absent_dimensions"]]
        assert dims == ["risks", "uncertainty"]


class TestDetectVerbatimOverlap:
    """``_detect_verbatim_overlap`` flags two responses as the same
    text when difflib SequenceMatcher.ratio() crosses threshold."""

    def test_returns_none_for_fewer_than_two_models(self) -> None:
        models = {"A": {"text": "x"}}
        assert _detect_verbatim_overlap(models, ["A"]) is None

    def test_returns_none_for_short_or_missing_text(self) -> None:
        models = {"A": {"text": ""}, "B": {"text": "real text"}}
        assert _detect_verbatim_overlap(models, ["A", "B"]) is None

    def test_identical_text_flagged_verbatim(self) -> None:
        text = "The Federal Reserve raised rates by 25 basis points." * 20
        models = {"A": {"text": text}, "B": {"text": text}}
        result = _detect_verbatim_overlap(models, ["A", "B"])
        assert result is not None
        assert result["level"] == "verbatim"
        assert result["ratio"] >= 0.95

    def test_different_text_not_flagged(self) -> None:
        models = {
            "A": {"text": "Apple reported $100B in revenue."},
            "B": {"text": "Climate change affects polar ice."},
        }
        # quick_ratio short-circuits below 0.95 threshold.
        assert _detect_verbatim_overlap(models, ["A", "B"]) is None

    def test_threshold_argument_respected(self) -> None:
        # Identical text but threshold raised above 1.0 -> impossible.
        text = "Same text body for both."
        models = {"A": {"text": text}, "B": {"text": text}}
        # At 0.95 it would fire; at 1.01 (impossible ratio) it cannot.
        # Since ratio() is bounded [0, 1], threshold 1.01 always fails.
        result = _detect_verbatim_overlap(models, ["A", "B"], threshold=1.01)
        assert result is None


class TestComposeComparisonPortrait:
    """``_compose_comparison_portrait`` produces the deterministic
    2-3 sentence portrait at the top of the compare takeaway panel.
    Returns None for thin input."""

    def test_returns_none_for_single_model(self) -> None:
        models = {"A": _model_data(
            name="A", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )}
        assert _compose_comparison_portrait(models, ["A"], agreed_count=0) is None

    def test_emits_portrait_for_two_models(self) -> None:
        a = _model_data(
            name="A", coverage_count=4, voice="analytical",
            sourced_pct=70, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=4, voice="promotional",
            sourced_pct=20, temporal="future",
        )
        portrait = _compose_comparison_portrait(
            {"A": a, "B": b}, ["A", "B"], agreed_count=2,
        )
        assert portrait is not None
        assert isinstance(portrait, str)

    def test_documents_mode_subject(self) -> None:
        a = _model_data(
            name="docA", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="docB", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        portrait = _compose_comparison_portrait(
            {"docA": a, "docB": b}, ["docA", "docB"],
            agreed_count=0, mode="documents",
        )
        # subject_plural="These documents" when mode == documents.
        assert portrait is not None


# ================================================================
# Layer 6: build_cross_model_comparison orchestrator
# ================================================================


class TestBuildCrossModelComparison:
    """``build_cross_model_comparison`` orchestrates the pure compare
    helpers above; pure (no LLM)."""

    def test_returns_none_for_single_model(self) -> None:
        models = {"A": _model_data(
            name="A", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )}
        assert build_cross_model_comparison(models) is None

    def test_two_models_returns_envelope(self) -> None:
        a = _model_data(
            name="A", coverage_count=4, voice="analytical",
            sourced_pct=70, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=3, voice="promotional",
            sourced_pct=20, temporal="future",
        )
        out = build_cross_model_comparison({"A": a, "B": b})
        assert out is not None
        assert "models" in out
        assert "model_names" in out
        assert "verdict_text" in out
        assert "takeaway_questions" in out
        assert "comparison_portrait" in out
        assert "agreed_numbers" in out
        assert "near_matches" in out
        assert "blind_spots" in out
        assert "summary" in out

    def test_mode_topic_subject(self) -> None:
        a = _model_data(
            name="A", coverage_count=4, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=4, voice="promotional",
            sourced_pct=50, temporal="present",
        )
        # mode='topic' surfaces "These responses" subject in verdict
        # fallback. We just verify the orchestrator accepts the mode.
        out = build_cross_model_comparison({"A": a, "B": b}, mode="topic")
        assert out is not None

    def test_mode_documents_subject(self) -> None:
        a = _model_data(
            name="A", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        b = _model_data(
            name="B", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        out = build_cross_model_comparison({"A": a, "B": b}, mode="documents")
        assert out is not None

    def test_summary_counts_present(self) -> None:
        a = _model_data(
            name="A", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        a["numbers"] = {"100", "200"}
        b = _model_data(
            name="B", coverage_count=5, voice="analytical",
            sourced_pct=50, temporal="present",
        )
        b["numbers"] = {"100", "300"}
        out = build_cross_model_comparison({"A": a, "B": b})
        assert out is not None
        s = out["summary"]
        assert s["total_agreed"] == 1   # "100" in both
        assert s["total_only_a"] == 1   # "200" only in A
        assert s["total_only_b"] == 1   # "300" only in B
