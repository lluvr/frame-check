"""LLM cost accounting: pricing table and token-usage extraction.

Single source of truth for per-model pricing, shared by every caller
that invokes a Gemini or Grok API in Frame Check. Two concerns live
here and nowhere else:

  1. MODEL_PRICING_PER_1K_TOKENS: the rate table. Updated when a
     provider changes pricing. The Phase 1.10 reconciliation
     compares estimates to measured numbers. If they differ,
     update this table first and the documentation second.

  2. Token-usage extraction + cost computation: pure functions that
     callers use to derive cost_usd from an API response. The
     shapes differ by provider (google.genai exposes
     response.usage_metadata with prompt_token_count; openai-
     compatible providers like Grok expose response.usage with
     prompt_tokens). Extractors are defensive against library
     version drift.

The module is deliberately side-effect free. Callers take the
computed cost and do whatever they need with it (charge gates,
record telemetry, surface in corpus). Keeping pure cost math
separate from stateful rate-limiting is the boundary that lets
either side change without breaking the other.

Token counts are the primary signal in the corpus (raw, replayable).
Cost is the derived convenience. A researcher with a new pricing
table can re-derive cost from token counts in the published NDJSON.
This is the trade that lets the corpus stay useful when prices
change.
"""

import sys


# ================================================================
# Pricing table (single source of truth)
# ================================================================
# USD per 1,000 tokens. Keyed by (provider, model).
# Source: public pricing pages of each provider as of 2026-04.
# Update here first when a provider changes pricing; the
# caller's Phase 1.10 reconciliation validates this table
# against measured costs in the corpus.

MODEL_PRICING_PER_1K_TOKENS = {
    ("gemini", "gemini-2.5-flash"): {
        "input_per_1k_usd":  0.000150,
        "output_per_1k_usd": 0.000600,
    },
    ("gemini", "gemini-2.0-flash"): {
        "input_per_1k_usd":  0.000100,
        "output_per_1k_usd": 0.000400,
    },
    ("grok", "grok-4-1-fast"): {
        "input_per_1k_usd":  0.000200,
        "output_per_1k_usd": 0.000800,
    },
}

# Flat per-request cost for Gemini grounded responses (google_search
# tool enabled). The grounding fee is the dominant cost for single-
# claim verification calls; adding token cost to this number
# double-counts. Callers using the grounded-search path charge this
# rate directly rather than going through compute_cost_usd.
GEMINI_GROUNDING_COST_USD = 0.014


# ================================================================
# Pure computation
# ================================================================

def compute_cost_usd(provider, model, input_tokens, output_tokens):
    """Token counts -> USD cost. Returns 0.0 for unknown (provider, model).

    The 0.0 return for unknown models is intentional: it is the
    honest "we do not know" value, better than raising because
    callers in production paths should degrade gracefully rather
    than crash. Unknown models that return 0.0 cost are visible
    in the corpus as cost_usd=0 alongside non-zero token counts,
    which is itself a signal for the pricing table to be updated.
    """
    rates = MODEL_PRICING_PER_1K_TOKENS.get((provider, model))
    if not rates:
        return 0.0
    return round(
        (input_tokens / 1000.0) * rates["input_per_1k_usd"]
        + (output_tokens / 1000.0) * rates["output_per_1k_usd"],
        6,
    )


def empty_usage():
    """Uniform shape for failed or no-op calls.

    Callers prefer a stable dict over None so downstream code can
    always do `usage['cost_usd']` without a None check.
    """
    return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


# ================================================================
# Provider-specific extraction
# ================================================================

def extract_gemini_usage(response):
    """Pull (input_tokens, output_tokens) from a google.genai response.

    The google.genai library has had two field naming conventions
    across versions (prompt_token_count vs input_token_count on
    usage_metadata). Both are tried. Missing metadata or unusable
    values return (0, 0).
    """
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0
    input_t = (
        getattr(meta, "prompt_token_count", None)
        or getattr(meta, "input_token_count", None)
        or 0
    )
    output_t = (
        getattr(meta, "candidates_token_count", None)
        or getattr(meta, "output_token_count", None)
        or 0
    )
    return int(input_t or 0), int(output_t or 0)


def extract_grok_usage(response):
    """Pull (input_tokens, output_tokens) from an OpenAI-compatible response.

    Grok uses the OpenAI-compatible chat completions API which
    exposes usage via response.usage.prompt_tokens and
    response.usage.completion_tokens.
    """
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None:
        return 0, 0
    input_t = getattr(usage_obj, "prompt_tokens", 0) or 0
    output_t = getattr(usage_obj, "completion_tokens", 0) or 0
    return int(input_t or 0), int(output_t or 0)


def extract_proxy_cost_usd(response):
    """Read cost_in_usd_ticks from a LiteLLM-proxy response, if present.

    LiteLLM proxies set `cost_in_usd_ticks` on the OpenAI-compatible
    response.usage object as an integer count of nano-dollars
    (1 tick = 1e-9 USD). The proxy's value is the actual billing
    amount the proxy will charge the master provider key, which is
    more accurate than frame-check's local pricing table because it
    captures price changes the table has not picked up.

    Returns the cost in USD when the field is present, or None when
    the response is from a direct provider (no proxy in front), the
    response has no usage object, or the field is absent. Callers
    treat None as "fall back to local pricing table".

    Lives in llm_cost so the conversion logic stays co-located with
    the rest of the cost-extraction primitives.
    """
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None:
        return None
    # LiteLLM may attach the field directly on usage or under a
    # provider-specific subfield; check both shapes.
    ticks = getattr(usage_obj, "cost_in_usd_ticks", None)
    if ticks is None:
        # Some shapes pack it as a dict the SDK exposes via __dict__
        # but not as direct attributes; tolerate both.
        try:
            ticks = (usage_obj.__dict__ or {}).get("cost_in_usd_ticks")
        except Exception:
            ticks = None
    if ticks is None:
        return None
    try:
        return float(ticks) / 1e9
    except (TypeError, ValueError):
        return None


# ================================================================
# High-level: measure from a response, with fallback
# ================================================================

def measure(provider, model, response, fallback_cost_usd=0.0):
    """Extract usage and compute cost for an LLM response.

    Returns a dict {input_tokens, output_tokens, cost_usd}. The
    contract with callers:

      - Normal success: dict carries actual token counts and
        actual cost from the pricing table.
      - Missing usage metadata (API returned no counts):
        {0, 0, fallback_cost_usd}. The fallback is the caller's
        pre-measurement estimate; using it preserves the gate
        charge even when measurement fails.
      - Unknown model: token counts are real, cost is the fallback
        (rather than 0) because the call DID cost something even
        when the pricing table does not know the model.
      - Any extraction exception: logged to stderr, returns the
        fallback shape. Never raises.

    `provider` must be 'gemini' or 'grok'. Other values return the
    fallback shape; callers with non-LLM providers should not use
    this function.
    """
    try:
        if provider == "gemini":
            input_t, output_t = extract_gemini_usage(response)
        elif provider == "grok":
            input_t, output_t = extract_grok_usage(response)
        else:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": float(fallback_cost_usd),
            }

        if input_t == 0 and output_t == 0:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": float(fallback_cost_usd),
            }

        # Prefer the proxy-reported cost when it is present. A proxy
        # in front of frame-check (when configured) returns
        # cost_in_usd_ticks on usage; that value reflects the actual
        # billing the proxy will pass to the master provider key,
        # which is more accurate than frame-check's local pricing
        # table whenever provider pricing has changed since the
        # table was last calibrated.
        proxy_cost = extract_proxy_cost_usd(response)
        if proxy_cost is not None and proxy_cost > 0:
            return {
                "input_tokens": input_t,
                "output_tokens": output_t,
                "cost_usd": proxy_cost,
            }

        cost = compute_cost_usd(provider, model, input_t, output_t)
        if cost == 0.0:
            cost = float(fallback_cost_usd)

        return {
            "input_tokens": input_t,
            "output_tokens": output_t,
            "cost_usd": cost,
        }
    except Exception as exc:
        print(
            f"[llm_cost] measure failed for ({provider}, {model}): "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": float(fallback_cost_usd),
        }
