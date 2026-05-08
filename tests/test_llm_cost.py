"""Tests for llm_cost.py: pricing table, extraction, measurement.

The contract these tests lock in:
  - Pricing math is deterministic given token counts + (provider, model).
  - Usage extraction works on the two response shapes we care about
    (google.genai usage_metadata + OpenAI-compatible usage).
  - Fallback semantics: missing usage means fallback cost; unknown
    model means fallback cost; extraction exceptions mean fallback
    cost. The gate charge never vanishes because measurement failed.
"""

import llm_cost


# ================================================================
# compute_cost_usd
# ================================================================

class TestComputeCostUsd:

    def test_known_model_gemini_flash_2_5(self):
        # 1000 input tokens: 1 * 0.000150 = 0.000150
        # 500 output tokens: 0.5 * 0.000600 = 0.000300
        # Total: 0.000450
        cost = llm_cost.compute_cost_usd("gemini", "gemini-2.5-flash", 1000, 500)
        assert cost == round(0.000150 + 0.000300, 6)

    def test_known_model_grok_4_1_fast(self):
        cost = llm_cost.compute_cost_usd("grok", "grok-4-1-fast", 2000, 300)
        # 2 * 0.000200 + 0.3 * 0.000800 = 0.000400 + 0.000240 = 0.000640
        assert cost == round(0.000640, 6)

    def test_unknown_model_returns_zero(self):
        cost = llm_cost.compute_cost_usd("gemini", "gemini-17-ultra", 1000, 1000)
        assert cost == 0.0

    def test_unknown_provider_returns_zero(self):
        cost = llm_cost.compute_cost_usd("openai", "gpt-5", 1000, 1000)
        assert cost == 0.0

    def test_zero_tokens_zero_cost(self):
        cost = llm_cost.compute_cost_usd("grok", "grok-4-1-fast", 0, 0)
        assert cost == 0.0

    def test_rounding_to_six_decimals(self):
        # 1 input token = 0.000000200 which rounds to 0.0
        # 1 output token = 0.000000800 which rounds to 0.000001
        cost = llm_cost.compute_cost_usd("grok", "grok-4-1-fast", 1, 1)
        # 0.0000002 + 0.0000008 = 0.000001 at 6 decimals
        assert cost == 0.000001


# ================================================================
# Usage extraction: Gemini
# ================================================================

class _GeminiUsageMetadata:
    """Shape 1: current library with prompt_token_count naming."""
    def __init__(self, prompt, candidates):
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates


class _GeminiUsageMetadataAlt:
    """Shape 2: older library with input/output_token_count naming."""
    def __init__(self, input_t, output_t):
        self.input_token_count = input_t
        self.output_token_count = output_t


class _FakeGeminiResponse:
    def __init__(self, usage_metadata):
        self.usage_metadata = usage_metadata


class TestExtractGeminiUsage:

    def test_current_naming(self):
        resp = _FakeGeminiResponse(_GeminiUsageMetadata(prompt=1500, candidates=400))
        assert llm_cost.extract_gemini_usage(resp) == (1500, 400)

    def test_alt_naming(self):
        resp = _FakeGeminiResponse(_GeminiUsageMetadataAlt(input_t=1500, output_t=400))
        assert llm_cost.extract_gemini_usage(resp) == (1500, 400)

    def test_no_usage_metadata_returns_zeros(self):
        class _Bare:
            pass
        assert llm_cost.extract_gemini_usage(_Bare()) == (0, 0)

    def test_usage_metadata_is_none_returns_zeros(self):
        resp = _FakeGeminiResponse(None)
        assert llm_cost.extract_gemini_usage(resp) == (0, 0)


# ================================================================
# Usage extraction: Grok (OpenAI-compatible)
# ================================================================

class _GrokUsage:
    def __init__(self, prompt, completion):
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class _FakeGrokResponse:
    def __init__(self, usage):
        self.usage = usage


class TestExtractGrokUsage:

    def test_normal(self):
        resp = _FakeGrokResponse(_GrokUsage(prompt=800, completion=150))
        assert llm_cost.extract_grok_usage(resp) == (800, 150)

    def test_no_usage(self):
        class _Bare:
            pass
        assert llm_cost.extract_grok_usage(_Bare()) == (0, 0)

    def test_none_usage(self):
        resp = _FakeGrokResponse(None)
        assert llm_cost.extract_grok_usage(resp) == (0, 0)


# ================================================================
# measure (end-to-end, with fallback semantics)
# ================================================================

class TestMeasure:

    def test_gemini_success(self):
        resp = _FakeGeminiResponse(_GeminiUsageMetadata(prompt=1000, candidates=500))
        result = llm_cost.measure("gemini", "gemini-2.5-flash", resp, fallback_cost_usd=0.014)
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        # 0.000150 + 0.000300 = 0.000450
        assert result["cost_usd"] == round(0.000450, 6)

    def test_grok_success(self):
        resp = _FakeGrokResponse(_GrokUsage(prompt=2000, completion=300))
        result = llm_cost.measure("grok", "grok-4-1-fast", resp, fallback_cost_usd=0.015)
        assert result["input_tokens"] == 2000
        assert result["output_tokens"] == 300
        assert result["cost_usd"] == round(0.000640, 6)

    def test_missing_usage_falls_back(self):
        class _Bare:
            pass
        result = llm_cost.measure("gemini", "gemini-2.5-flash", _Bare(), fallback_cost_usd=0.014)
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["cost_usd"] == 0.014

    def test_unknown_model_uses_fallback(self):
        resp = _FakeGeminiResponse(_GeminiUsageMetadata(prompt=1000, candidates=500))
        result = llm_cost.measure("gemini", "gemini-99-ultra", resp, fallback_cost_usd=0.020)
        # Tokens real, cost fallback because pricing unknown.
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["cost_usd"] == 0.020

    def test_unknown_provider_uses_fallback(self):
        class _Bare:
            pass
        result = llm_cost.measure("openai", "gpt-5", _Bare(), fallback_cost_usd=0.030)
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["cost_usd"] == 0.030

    def test_extraction_exception_uses_fallback(self):
        class _Raises:
            @property
            def usage_metadata(self):
                raise RuntimeError("simulated library fault")
        result = llm_cost.measure("gemini", "gemini-2.5-flash", _Raises(),
                                  fallback_cost_usd=0.014)
        assert result == {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.014}

    def test_default_fallback_is_zero(self):
        class _Bare:
            pass
        result = llm_cost.measure("gemini", "gemini-2.5-flash", _Bare())
        assert result["cost_usd"] == 0.0


# ================================================================
# empty_usage
# ================================================================

class TestEmptyUsage:

    def test_shape(self):
        u = llm_cost.empty_usage()
        assert set(u.keys()) == {"input_tokens", "output_tokens", "cost_usd"}
        assert u["input_tokens"] == 0
        assert u["output_tokens"] == 0
        assert u["cost_usd"] == 0.0
