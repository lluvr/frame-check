"""Cookbook claims verified against the running API.

Each test maps to a recipe's "Load-bearing fields" section in
``docs/COOKBOOK.md``. If a field name changes or disappears, the
matching test here fails and the cookbook entry needs updating.
The existence of this file is what makes the cookbook a falsifiable
contract rather than aspirational documentation.

Run via pytest:

    pytest tests/test_cookbook_recipes.py

The tests are deterministic (no LLM call, no network) and run in
under a second. They use small synthetic documents because the
shape of the response is what's being tested, not the analytical
content.
"""
from __future__ import annotations

import os
import sys

# Add repo root to path so direct pytest invocation resolves
# mcp_server alongside the wheel's flat layout convention.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server import build_compare_payload, build_epistemic_payload  # noqa: E402


_TEST_DOC = (
    "## Bitcoin retirement question\n\n"
    "Bitcoin gained adoption among institutional investors through "
    "the 2020s. Trends compound through 2030, with regulatory "
    "uncertainty as a structural risk. Stakeholders include retail "
    "holders, institutions, and miners.\n"
)


def test_recipe1_frame_check_response_shape():
    """Recipe 1: Frame-check before an AI agent commits.

    Cookbook claims these load-bearing fields exist on the response:
      - ``analysis.coverage``
      - ``analysis.frame_library_matches`` (list)
      - ``divergence.absent_frames`` (list)
      - ``agent_guidance.suggested_next_actions`` (list)
      - ``provenance.analysis_cost_usd`` (float, always 0.0)
      - ``divergence.envelope.catalog_version``
      - ``divergence.envelope.v4_2_engine_status``
    """
    p = build_epistemic_payload(
        _TEST_DOC,
        include_divergence=True,
        domain_hint="founder_decision",
    )
    assert p["analysis"].get("coverage") is not None, (
        "Cookbook recipe 1 claims analysis.coverage exists; "
        "response shape has changed"
    )
    assert isinstance(p["analysis"].get("frame_library_matches"), list), (
        "Cookbook recipe 1 claims frame_library_matches is a list"
    )
    assert isinstance(
        p.get("divergence", {}).get("absent_frames"), list
    ), "Cookbook recipe 1 claims divergence.absent_frames is a list"
    assert isinstance(
        p["agent_guidance"].get("suggested_next_actions"), list
    ), "Cookbook recipe 1 claims suggested_next_actions is a list"
    assert p["provenance"]["analysis_cost_usd"] == 0.0, (
        "Cookbook recipe 1 claims analysis_cost_usd is always 0.0; "
        "if this fails an LLM call leaked into the analysis layer"
    )
    envelope = p.get("divergence", {}).get("envelope", {})
    assert envelope.get("catalog_version"), (
        "Cookbook recipe 2 claims divergence.envelope.catalog_version"
    )
    assert envelope.get("v4_2_engine_status"), (
        "Cookbook recipe 2 claims divergence.envelope.v4_2_engine_status"
    )


def test_recipe2_divergence_renderings():
    """Recipe 2: Frame divergence at decision points.

    Cookbook claims ``divergence_rendering`` accepts the four values:
      - ``list`` (default)
      - ``completeness_check``
      - ``teaching_questions``
      - ``narrative``

    Each call returns a payload with ``divergence`` set; the
    rendering selection drives the surface a downstream client
    presents to the user.
    """
    for rendering in (
        "list",
        "completeness_check",
        "teaching_questions",
        "narrative",
    ):
        p = build_epistemic_payload(
            _TEST_DOC,
            include_divergence=True,
            divergence_rendering=rendering,
        )
        assert p.get("divergence"), (
            f"Cookbook recipe 2 claims divergence_rendering={rendering!r} "
            f"is accepted; the call returned no divergence block"
        )


def test_recipe3_source_grounded_verification_shape():
    """Recipe 3: Source-grounded verification of an LLM summary.

    Cookbook claims that passing ``source_text`` unlocks the
    ``analysis.verification`` block with two sub-fields:
      - ``analysis.verification.source_fidelity`` (digit-level)
      - ``analysis.verification.grounding_decomposition`` (sentence-level)
    """
    document = (
        "## NVIDIA Q4 summary\n\n"
        "Revenue was $22.1 billion in the quarter. The company "
        "reported sustained growth.\n"
    )
    source = (
        "## Source filing\n\n"
        "NVIDIA reported quarterly revenue of $22.1 billion. "
        "Operating margin held steady.\n"
    )
    p = build_epistemic_payload(
        document, source_text=source, include_divergence=False,
    )
    verification = p["analysis"].get("verification")
    assert isinstance(verification, dict), (
        "Cookbook recipe 3 claims analysis.verification exists when "
        "source_text is passed; got type "
        f"{type(verification).__name__}"
    )
    assert isinstance(verification.get("source_fidelity"), dict), (
        "Cookbook recipe 3 claims analysis.verification.source_fidelity"
    )
    assert isinstance(
        verification.get("grounding_decomposition"), dict
    ), "Cookbook recipe 3 claims analysis.verification.grounding_decomposition"


def test_recipe4_frame_compare_response_shape():
    """Recipe 4: Compare two LLMs on the same prompt.

    Cookbook claims the ``frame_compare`` response carries
    ``analysis.comparison`` with five sub-blocks:
      - ``coverage`` (shared_blind_spots / only_a_misses /
        only_b_misses / addressed_count_delta)
      - ``voice`` / ``temporal`` / ``epistemic``
      - ``framing_differences`` (cards + unique_omissions + summary)

    And ``analysis.documents`` keyed by label
    (``"Document A"`` / ``"Document B"`` by default).
    """
    document_a = (
        "## Bitcoin recommendation A\n\n"
        "Bitcoin will moon in 2030. Massive upside. Strong buy.\n"
    )
    document_b = (
        "## Bitcoin recommendation B\n\n"
        "Bitcoin carries regulatory risk. The trajectory is "
        "uncertain. Wait for clarity.\n"
    )
    c = build_compare_payload(
        document_a, document_b,
        a_name="Recommendation A",
        b_name="Recommendation B",
    )
    comparison = c["analysis"].get("comparison")
    assert isinstance(comparison, dict), (
        "Cookbook recipe 4 claims analysis.comparison is a dict"
    )
    for sub in ("coverage", "voice", "temporal", "epistemic",
                "framing_differences"):
        assert isinstance(comparison.get(sub), dict), (
            f"Cookbook recipe 4 claims analysis.comparison.{sub} "
            f"is a dict; got {type(comparison.get(sub)).__name__}"
        )
    coverage_block = comparison["coverage"]
    for key in ("shared_blind_spots", "only_a_misses",
                "only_b_misses", "addressed_count_delta"):
        assert key in coverage_block, (
            f"Cookbook recipe 4 claims coverage.{key} is "
            f"surfaced; key missing from response"
        )
    documents = c["analysis"].get("documents")
    assert isinstance(documents, dict), (
        "Cookbook recipe 4 claims analysis.documents is a "
        "dict keyed by label"
    )
    assert "Recommendation A" in documents, (
        "Cookbook recipe 4 claims documents are keyed by "
        "the passed labels"
    )
    assert "Recommendation B" in documents


def test_quickstart_zero_cost_invariant():
    """README "Approach" claim: $0.00 per query at the analysis layer.

    Spelled out as an invariant: ``provenance.analysis_cost_usd`` is
    exactly 0.0 on every ``frame_check`` and ``frame_compare`` call.
    This is the load-bearing claim for the "zero per-query cost"
    positioning section in README and cookbook recipe 1.
    """
    payloads = [
        build_epistemic_payload(_TEST_DOC, include_divergence=True),
        build_epistemic_payload(_TEST_DOC, include_divergence=False),
        build_compare_payload(_TEST_DOC, _TEST_DOC),
    ]
    for p in payloads:
        cost = p["provenance"]["analysis_cost_usd"]
        assert cost == 0.0, (
            f"README claim violated: analysis_cost_usd was {cost}, "
            f"not 0.0. The MCP server made an LLM call at the "
            f"analysis layer."
        )


def test_determinism_invariant():
    """README "Approach" claim: deterministic measurement.

    Two calls with the same input produce the same analysis layer.
    This is the load-bearing claim for "Determinism" in the README
    positioning section. The provenance block carries timestamps
    and latency that vary; everything under ``analysis`` is the
    deterministic surface.
    """
    p1 = build_epistemic_payload(_TEST_DOC, include_divergence=True)
    p2 = build_epistemic_payload(_TEST_DOC, include_divergence=True)
    assert p1["analysis"] == p2["analysis"], (
        "README determinism claim violated: same input produced "
        "different analysis output across two calls. The "
        "deterministic floor has regressed."
    )
