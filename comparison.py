"""
AI-to-AI comparison engine.

Generates responses from multiple AI models for the same prompt,
analyzes each structurally, and identifies where they agree, disagree,
and what each uniquely emphasizes.

The insight: different AIs don't just give different answers. They give
different FRAMINGS. Different emphasis, different omissions, different
confidence patterns. Showing this side-by-side is revelatory.

The disagreement signal: when two independent models give different
numbers for the same fact, at least one is unreliable. This is a
zero-cost cross-model verification.
"""

import concurrent.futures
import os
import re

from clarethium_measure import measure
from claim_analysis import analyze_claims
from framing import (
    detect_coverage, temporal_orientation,
    detect_voice, detect_epistemic_basis,
)
from frame_library import suggest_frames
from prompt_safety import (
    PromptInjectionAttempt,
    SAFETY_INSTRUCTION,
    check_user_text_safe,
    wrap_user_text,
)
from source_network import verify_claims_source_network


# ================================================================
# Model generation
# ================================================================

GENERATION_PROMPT = """Write a detailed, factual analysis of the following topic. Include specific statistics, numbers, dates, and data points where relevant. Structure your response with clear sections.

{safety_instruction}

Topic:
{wrapped_topic}

Write 300-500 words with specific, verifiable claims.

Punctuation: use only straight ASCII punctuation. Do not use em-dashes, en-dashes, curly quotes, curly apostrophes, or ellipsis characters. If you would use an em-dash, rewrite the sentence with a comma, colon, period, or parenthesis instead."""


def _render_generation_prompt(topic: str) -> str:
    """Render GENERATION_PROMPT with topic wrapped in V4.2 sentinels.

    Caller MUST have already screened ``topic`` via
    ``check_user_text_safe`` and propagated any
    :class:`PromptInjectionAttempt` to its own caller.
    """
    return GENERATION_PROMPT.format(
        safety_instruction=SAFETY_INSTRUCTION,
        wrapped_topic=wrap_user_text(topic),
    )


# ================================================================
# Model pricing (Phase 1.6a Prereq 1)
# ================================================================
#
# The pricing table and per-call cost computation live in llm_cost
# as of Stream 2. This module re-exports the names under their
# legacy aliases (_compute_token_cost, _empty_usage,
# MODEL_PRICING_PER_1K_TOKENS) so existing importers continue to
# work without change. All future call sites should import directly
# from llm_cost; these aliases exist only to avoid a cross-file
# atomic refactor.
from llm_cost import (
    compute_cost_usd as _compute_token_cost,
    empty_usage as _empty_usage,
)


def generate_gemini(topic):
    """Generate a response from Gemini.

    Phase 1.6a Prereq 1: returns a tuple (text, usage_dict).
    `text` is the response string or None on failure. `usage_dict`
    contains {input_tokens, output_tokens, cost_usd} for the
    calling code. On any failure the function returns
    (None, _empty_usage()) so callers can unpack uniformly.
    """
    try:
        check_user_text_safe(topic)
    except PromptInjectionAttempt:
        return None, _empty_usage()

    try:
        import google.genai as genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_render_generation_prompt(topic),
            config={"temperature": 0.7, "max_output_tokens": 2048},
        )
        text = response.text if response.text else None
        # The python google.genai library exposes token counts
        # via response.usage_metadata. Be defensive: the field
        # name has shifted across library versions, so we
        # attempt several attribute names and fall back to
        # zeros rather than crash.
        meta = getattr(response, "usage_metadata", None)
        input_tokens = 0
        output_tokens = 0
        if meta is not None:
            input_tokens = (
                getattr(meta, "prompt_token_count", None)
                or getattr(meta, "input_token_count", None)
                or 0
            )
            output_tokens = (
                getattr(meta, "candidates_token_count", None)
                or getattr(meta, "output_token_count", None)
                or 0
            )
        usage = {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cost_usd": _compute_token_cost(
                "gemini", "gemini-2.5-flash",
                int(input_tokens or 0), int(output_tokens or 0),
            ),
        }
        return text, usage
    except Exception as e:
        import sys
        print(f"[comparison] Gemini generation error: {e}", file=sys.stderr)
        return None, _empty_usage()


def generate_grok(topic):
    """Generate a response from xAI Grok.

    Phase 1.6a Prereq 1: returns a tuple (text, usage_dict).
    Same shape as generate_gemini. The Grok API is OpenAI
    compatible and exposes usage via response.usage with
    prompt_tokens / completion_tokens.
    """
    try:
        check_user_text_safe(topic)
    except PromptInjectionAttempt:
        return None, _empty_usage()

    try:
        from llm_client import xai_openai_client
        client = xai_openai_client()
        if client is None:
            return None, _empty_usage()
        response = client.chat.completions.create(
            model="grok-4-1-fast",
            messages=[{"role": "user", "content": _render_generation_prompt(topic)}],
            max_completion_tokens=2048,
            temperature=0.7,
        )
        text = None
        if response.choices:
            text = response.choices[0].message.content
        usage_obj = getattr(response, "usage", None)
        input_tokens = 0
        output_tokens = 0
        if usage_obj is not None:
            input_tokens = getattr(usage_obj, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage_obj, "completion_tokens", 0) or 0
        usage = {
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cost_usd": _compute_token_cost(
                "grok", "grok-4-1-fast",
                int(input_tokens or 0), int(output_tokens or 0),
            ),
        }
        return text, usage
    except Exception as e:
        import sys
        print(f"[comparison] Grok generation error: {e}", file=sys.stderr)
        return None, _empty_usage()


def generate_responses(topic):
    """Generate responses from both models in parallel.

    Returns dict of {model_name: response_text}. The token
    usage information from each call is discarded here because
    this function is the legacy compare-page entry point and
    its consumers (the user-facing UI) do not need usage data.
    The calling code (Phase 1.6b) calls generate_gemini
    and generate_grok directly so it can capture the usage
    dict for Tier B telemetry.
    """
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(generate_gemini, topic): "Gemini",
            pool.submit(generate_grok, topic): "Grok",
        }
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                # Phase 1.6a Prereq 1: generate_gemini and
                # generate_grok now return (text, usage_dict).
                # Unpack and ignore usage; this caller is the
                # user-facing path.
                text, _usage = future.result()
                if text:
                    results[model] = text
            except Exception as e:
                # Tolerated by design: per-model generation failures
                # MUST NOT block the rest of the cross-model pool.
                # The user-facing comparison path proceeds with
                # whichever models succeeded; an empty result for
                # this model is treated as "this provider was
                # unavailable for this run." Log to stderr so the
                # operator can investigate without breaking the
                # JSON-RPC channel on stdout.
                import sys
                print(
                    f"[comparison.generate_with_models] "
                    f"{model} failed: {type(e).__name__}: {e}",
                    file=sys.stderr,
                )

    return results


# ================================================================
# Automated Diff Engine (number stability)
# ================================================================

def generate_stability_check(topic, responses) -> tuple[dict, float]:
    """Regenerate responses and diff numbers for stability analysis.

    Numbers that appear in BOTH generations are stable (likely from
    training data). Numbers that differ are unstable (likely generated, not retrieved).

    Returns a tuple (results_dict, total_cost_usd). results_dict is
    {model_name: {stable, changed, stable_count, changed_count, total}}.
    total_cost_usd is the sum of measured costs across both regenerations
    so callers can charge the gates on actual spend instead of a legacy
    estimate.
    """
    model_funcs = {"Gemini": generate_gemini, "Grok": generate_grok}
    results = {}
    total_cost_usd = 0.0

    # Regenerate both models in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {}
        for model_name in responses:
            if model_name in model_funcs:
                futures[pool.submit(model_funcs[model_name], topic)] = model_name

        for future in concurrent.futures.as_completed(futures):
            model_name = futures[future]
            try:
                # Each generator returns (text, usage_dict). Accumulate
                # usage across both regenerations so the caller can
                # charge gates on the measured total; text is the
                # comparison input.
                gen2_text, usage = future.result()
                total_cost_usd += float(usage.get("cost_usd", 0.0) or 0.0)
                if gen2_text:
                    # Extract numbers from generation 2
                    ca2 = analyze_claims(gen2_text)
                    nums2 = _extract_number_set(ca2)

                    # Compare with generation 1
                    ca1 = analyze_claims(responses[model_name])
                    nums1 = _extract_number_set(ca1)

                    stable = nums1 & nums2
                    changed_gen1 = nums1 - nums2  # in gen1 but not gen2
                    all_unique = nums1 | nums2

                    results[model_name] = {
                        "stable": sorted(stable),
                        "changed": sorted(changed_gen1),
                        "stable_count": len(stable),
                        "changed_count": len(changed_gen1),
                        "total": len(nums1),
                    }
            except Exception as e:
                # Tolerated by design: per-model regeneration
                # failures MUST NOT block the rest of the stability
                # pool. results omits this model_name (caller sees
                # which models succeeded); total_cost_usd reflects
                # only the regenerations that completed. Log to
                # stderr for diagnostic logging without breaking the
                # JSON-RPC channel on stdout.
                import sys
                print(
                    f"[comparison.compute_number_stability] "
                    f"{model_name} regeneration failed: "
                    f"{type(e).__name__}: {e}",
                    file=sys.stderr,
                )

    return results, total_cost_usd


# ================================================================
# Stability check
# ================================================================
#
# Stability tracking baked in from day 1. Each run does N
# regenerations of the same prompt to the same model and records
# which numbers were stable across all N runs versus which appeared
# in only some. With N=3 the signal is meaningful.
#
# This is a NEW function. The user-facing compare page consumes the
# existing generate_stability_check above (N=2: original vs one
# regeneration). The N=3 path needs the full schema field set:
#
#   regeneration_count, total_unique_numbers, stable_count,
#   partial_count, unique_to_one_count, stability_rate,
#   stable_value_buckets (per num_type), regeneration_costs_usd
#
# The new function calls generate_gemini or generate_grok N
# times in parallel, runs analyze_claims on each response,
# computes the union of unique normalized numbers across all
# N responses, buckets each unique number by occurrence count
# (stable / partial / unique_to_one), and aggregates the
# stable bucket by num_type. Per-regeneration cost comes from the
# usage_dict that generate_gemini and generate_grok return.

# Map provider name to the corresponding generator function.
# Used by stability_check to dispatch the parallel
# regenerations. Adding a new provider means adding an entry
# here AND a new generate_* function above; the topic
# input references provider names that must match this
# table.
_PROVIDER_GENERATORS = {
    "gemini": generate_gemini,
    "grok": generate_grok,
}


def stability_n3_check(topic, provider, n=3):
    """Run N independent regenerations of the same prompt and
    return a schema-shaped dict matching the
    stability_n3_check event.

    Phase 1.6a Prereq 6.

    Args:
        topic: the prompt text to regenerate.
        provider: "gemini" or "grok". Dispatch via
            _PROVIDER_GENERATORS.
        n: regeneration count. Default 3 per Section 8.7
            recommendation. Lower values weaken the signal;
            higher values cost proportionally more.

    Returns:
        A dict with the eight Section 5 fields plus a
        per-regeneration response_text_signature list that the
        calling code uses to deduplicate accidental
        double-recording. The dict is JSON-serializable.

    On failure (provider unknown, all generations crash, etc),
    returns a dict with regeneration_count=0 and the other
    counts at zero. The calling code treats this as a
    null stability check for the cycle and continues with the
    next topic; it does NOT raise.

    The calling code does NOT call this function directly because
    it needs to share the N generations between the per-model
    representative analysis (analyze_model) and the stability
    computation. Instead, the caller invokes the generator with
    retry logic,
    then passes the pre-generated texts into
    stability_from_regenerations() below. This function
    remains for ad hoc testing and any future caller that
    wants a generate-and-compute one-shot.
    """
    generator = _PROVIDER_GENERATORS.get(provider)
    if generator is None:
        return _empty_stability_result(provider, n)

    # Parallel regeneration. Each future returns the new
    # (text, usage_dict) tuple from generate_gemini /
    # generate_grok (Phase 1.6a Prereq 1).
    regenerations = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(n, 4)) as pool:
        futures = [pool.submit(generator, topic) for _ in range(n)]
        for future in concurrent.futures.as_completed(futures):
            try:
                text, usage = future.result()
                if text is not None:
                    regenerations.append({
                        "text": text,
                        "usage": usage or _empty_usage(),
                    })
            except Exception:
                # Individual regeneration failures are tolerated;
                # the loop continues. The caller cycle's
                # cost reflects only the regenerations that
                # actually completed.
                pass

    if not regenerations:
        return _empty_stability_result(provider, n)

    return stability_from_regenerations(regenerations)


def stability_from_regenerations(regenerations):
    """Compute the stability_n3_check schema dict from
    pre-generated regenerations.

    Phase 1.6b split this out of stability_n3_check
    so the calling code can share the N generations
    between the representative analyze_model call and the
    stability computation, avoiding 4 LLM calls per
    (topic, model) cycle (1 for analyze_model plus 3 for
    stability = 4 total, vs 3 total when shared).

    Args:
        regenerations: list of dicts, each with `text` (str)
            and `usage` (dict with input_tokens, output_tokens,
            cost_usd). An empty list returns the empty result.

    Returns:
        The same schema-shaped dict as
        stability_n3_check. The separation is purely
        about who owns the generation step; the aggregation
        logic is identical.
    """
    import hashlib
    if not regenerations:
        return _empty_stability_result("", 0)

    # Per-regeneration claim analysis. analyze_claims emits
    # the per-num-type histogram (claims_by_type) from
    # Phase 1.5 Item 4, which feeds the stable_value_buckets
    # field below.
    per_regen_claims = []
    for r in regenerations:
        try:
            ca = analyze_claims(r["text"])
        except Exception:
            # Tolerated by design: per-regeneration claim-analysis
            # failures fall back to an empty claim set so the
            # stability loop can continue. A regeneration with no
            # claims contributes zero numbers to the stability
            # accounting; the corresponding cell shows up as
            # "no measurable claims" rather than crashing the
            # whole stability computation.
            ca = {"claims": [], "claims_by_type": {}}
        per_regen_claims.append(ca)

    # Build a per-number occurrence map across all regenerations.
    # Key: the normalized numeric string. Value: a dict with
    # `count` (how many regenerations contained the number)
    # and `num_type` (from the first regeneration that saw it,
    # because num_type for the same numeric value is stable
    # by definition).
    occurrences = {}
    for regen_idx, ca in enumerate(per_regen_claims):
        # Walk the per-claim numbers, normalize, and bucket
        # by num_type. We use the same _extract_number_set
        # logic as the user-facing stability check so the two
        # paths produce comparable signals; for type-bucketing
        # we walk the per-claim list once more to capture the
        # type alongside each normalized value.
        seen_in_this_regen = set()
        for claim in ca.get("claims", []):
            # The Phase 1.5 Item 4 path stores per-claim
            # numbers as cleaned display strings; we re-derive
            # the normalized form here. Type bucketing uses
            # the per-claim type if available; if not, fall
            # back to inspecting the value form.
            for num in claim.get("numbers", []):
                if isinstance(num, str):
                    normalized = _normalize_for_stability(num)
                    if normalized is None:
                        continue
                    num_type = _infer_num_type(num)
                    seen_in_this_regen.add((normalized, num_type))
        for normalized, num_type in seen_in_this_regen:
            entry = occurrences.setdefault(normalized, {
                "count": 0,
                "num_type": num_type,
            })
            entry["count"] += 1

    n_completed = len(regenerations)
    total_unique_numbers = len(occurrences)
    stable_count = sum(1 for e in occurrences.values() if e["count"] == n_completed)
    unique_to_one_count = sum(1 for e in occurrences.values() if e["count"] == 1)
    partial_count = total_unique_numbers - stable_count - unique_to_one_count
    if total_unique_numbers > 0:
        stability_rate = round(stable_count / total_unique_numbers, 4)
    else:
        stability_rate = 0.0

    # Bucket the stable numbers by num_type. Schema field
    # `stable_value_buckets` per Section 5 Tier B
    # stability_n3_check.
    stable_value_buckets = {
        "percentage": 0, "dollar": 0, "multiplier": 0,
        "decimal": 0, "integer": 0,
    }
    for entry in occurrences.values():
        if entry["count"] == n_completed and entry["num_type"] in stable_value_buckets:
            stable_value_buckets[entry["num_type"]] += 1

    # Per-regeneration cost from the usage_dict.
    regeneration_costs_usd = [
        round(float(r["usage"].get("cost_usd", 0.0)), 6)
        for r in regenerations
    ]

    # Per-regeneration response signature for the caller
    # worker's dedup-check. First 8 hex chars of sha256 of the
    # normalized response text. Used as a key against accidental
    # double-recording, NOT as a way to reconstruct the
    # response: the full text is NOT stored anywhere by this
    # function (the data-collection contract forbids storing it).
    response_text_signatures = [
        hashlib.sha256(r["text"].encode("utf-8")).hexdigest()[:8]
        for r in regenerations
    ]

    return {
        "regeneration_count": n_completed,
        "total_unique_numbers": total_unique_numbers,
        "stable_count": stable_count,
        "partial_count": partial_count,
        "unique_to_one_count": unique_to_one_count,
        "stability_rate": stability_rate,
        "stable_value_buckets": stable_value_buckets,
        "regeneration_costs_usd": regeneration_costs_usd,
        "response_text_signatures": response_text_signatures,
    }


def _empty_stability_result(provider, n):
    """Schema-shaped null result for failed stability checks.

    Returned when the provider is unknown, all regenerations
    failed, or any other early-exit condition. The shape
    matches the success path so calling code code can
    record an event for the failed cycle without branching.
    """
    return {
        "regeneration_count": 0,
        "total_unique_numbers": 0,
        "stable_count": 0,
        "partial_count": 0,
        "unique_to_one_count": 0,
        "stability_rate": 0.0,
        "stable_value_buckets": {
            "percentage": 0, "dollar": 0, "multiplier": 0,
            "decimal": 0, "integer": 0,
        },
        "regeneration_costs_usd": [],
        "response_text_signatures": [],
    }


_CURRENCY_SYMBOLS = "$€£¥₹"
_CURRENCY_CLASS = "[" + re.escape(_CURRENCY_SYMBOLS) + "]"

# Leading numeric token with optional currency symbol, sign,
# digit body (with commas / decimal), and scale suffix (word
# or single letter). The scale alternation lists multi-letter
# forms BEFORE the single-letter class so "billion" does not
# partial-match as "b".
#
# Phase 1.6e item 3: added the non-USD currency class and
# the optional leading sign. Approximate markers like "~"
# (e.g., "~$300B") are handled implicitly by re.search
# skipping non-matching characters until the currency or
# digit token. Ranges ("$10 to $20M") and comparisons
# ("up from $300B") still extract only the leading number;
# that matches stability semantics because the leading
# number IS the claim the model is making, and the
# stability bucket is per-claim_index not per-range-pair.
_NUMERIC_TOKEN_RE = re.compile(
    # Explicit named groups so the sign can appear either
    # before the currency symbol ("-$100") or after it
    # ("$-100"); both forms surface in real LLM output.
    # Unicode minus (U+2212) is accepted alongside ASCII "-"
    # because some models emit the typographic form.
    #
    # Scale suffix splits into two alternatives:
    #   scale_char: single letter IMMEDIATELY adjacent to
    #                the digits (no whitespace). The
    #                adjacency requirement prevents a
    #                stray "t" in "10 to $20 million"
    #                from misreading as the "trillion"
    #                scale letter (regression surfaced by
    #                Phase 1.6e item 3 range tests).
    #   scale_word: spelled-out scale (billion, million,
    #                ...) preceded by at least one whitespace
    #                character.
    # The handler reads whichever group matched.
    r'(?P<sign_pre>[-−]?)\s*'
    r'(?:' + _CURRENCY_CLASS + r')?\s*'
    r'(?P<sign_post>[-−]?)\s*'
    # Digits: a single unified pattern that handles both plain
    # numbers (299792458) and comma-separated (299,792,458) in
    # one branch. The prior alternation
    # `\d{1,3}(?:[,]\d{3})*|\d+` was buggy: Python regex
    # returns the first matching alternative, so the comma-
    # formatted branch always won, truncating 4+-digit plain
    # numbers to 3 digits (299792458 -> 299). A single greedy
    # `\d[\d,]*` avoids the alternation entirely. Trailing
    # commas from sentence-level punctuation ("100, which...")
    # are absorbed and removed by the .replace(",", "") step.
    r'(?P<digits>\d[\d,]*(?:\.\d+)?)'
    r'(?P<scale_char>[BMKTbmkt])?'
    r'(?:\s+(?P<scale_word>billion|million|thousand|trillion|bn|mn|tr))?'
    r'\s*(?P<pct>%)?',
)


def _normalize_for_stability(raw_value):
    """Normalize a per-claim display string into a stable key.

    Extracts the leading numeric pattern (with optional scale
    suffix) from the input and returns a canonical string
    form. The normalization is intentionally lossy: "$2.47B",
    "2.47 billion", and "2.47B" all collapse to the same key
    so a stability check can detect that the same underlying
    number appeared across regenerations even when the model
    formatted it differently.

    Strips trailing context words like "employees", "people",
    "shares" so that "164,000 employees" and "164000 shares"
    both normalize to the same numeric key. The trade-off is
    that two different metrics with the same value collide;
    that is acceptable for stability detection because the
    caller's claim_index tracks which metric a number
    belongs to, and the stability bucket is per-cycle not
    per-metric.

    Handles non-USD currency symbols (€, £, ¥, ₹) so claims
    from international topics (tsmc_revenue_recent in TWD,
    asml_revenue_recent in EUR) stay in the same bucket as
    their USD equivalents for the purposes of stability
    checking. The currency symbol is stripped during
    normalization, so "€500B" and "$500B" collide; the
    stability-bucket semantics are "same magnitude across
    regenerations" and the bucket key does not need to
    preserve the currency.

    Returns None when no numeric pattern is found.
    """
    if not raw_value:
        return None
    text = str(raw_value).strip()
    match = _NUMERIC_TOKEN_RE.search(text)
    if not match:
        return None
    digits = match.group("digits").replace(",", "")
    # Either the adjacent letter (scale_char) or the spaced
    # multi-letter word (scale_word) may be present, not both.
    scale_token = match.group("scale_word") or match.group("scale_char") or ""
    scale_token = scale_token.lower()
    is_percent = bool(match.group("pct"))
    # Phase 1.6e item 3: negative values ("-$100", "$-100",
    # "-5%") are preserved in the canonical form because the
    # sign is part of the claim (a loss of $100 is not the
    # same claim as a gain of $100 and should not collide in
    # the stability bucket). The sign can appear either
    # before or after the currency symbol; the regex exposes
    # both positions via named groups.
    is_negative = bool(match.group("sign_pre") or match.group("sign_post"))
    try:
        value = float(digits)
    except ValueError:
        return None
    # Apply the scale suffix.
    scale_map = {
        "billion": 1e9, "bn": 1e9, "b": 1e9,
        "million": 1e6, "mn": 1e6, "m": 1e6,
        "thousand": 1e3, "k": 1e3,
        "trillion": 1e12, "tr": 1e12, "t": 1e12,
    }
    if scale_token and scale_token in scale_map:
        value = value * scale_map[scale_token]
    if is_negative:
        value = -value
    # Canonical form: integer if whole, else trimmed float.
    # Append "%" suffix when the source had one so percentages
    # do not collide with the same numeric value as a count
    # ("12.3%" stays distinct from "12.3 employees").
    # The .15g precision matches float64 (15-17 significant
    # digits) so values like 1234567.89 stay as "1234567.89"
    # instead of the default :g's "1.23457e+06". The prior
    # default :g (6 significant digits) silently produced
    # exponential notation for any non-integer value with
    # more than 6 significant digits, which would cause two
    # formattings of the same approximate value (e.g.,
    # "$1,234,567.89" vs "$1.23M") to produce different
    # canonical keys and be miscounted as "unique" in the
    # stability analysis.
    if value == int(value):
        canonical = str(int(value))
    else:
        canonical = f"{value:.15g}"
    if is_percent:
        canonical += "%"
    return canonical


def _infer_num_type(raw_value):
    """Best-effort num_type inference from the display string.

    Mirrors the bucketing in claim_analysis.py. The
    caller cycle calls analyze_claims on each
    regeneration; the per-claim numbers list there contains
    cleaned display strings, not the original dicts, so we
    re-derive the type from the string form. The fallback to
    "integer" is conservative: it lands in the integer bucket
    only when no more specific marker is present.

    Phase 1.6e item 3: non-USD currency symbols (€, £, ¥, ₹)
    also route to the dollar bucket. The schema's num_type
    enum does not distinguish currencies (and adding one
    would break the Appendix C backward-compat guarantee),
    so "dollar" is the de-facto monetary bucket. Topic
    queries that need currency-aware analysis can read the
    raw_value off the source_queried events; the num_type
    is only a coarse histogram key.
    """
    if not raw_value:
        return "integer"
    raw = str(raw_value)
    if "%" in raw:
        return "percentage"
    # Currency detection: USD and all non-USD symbols route to
    # the monetary bucket.
    if any(sym in raw for sym in _CURRENCY_SYMBOLS):
        return "dollar"
    if re.search(r'\d+x\b', raw, re.IGNORECASE):
        return "multiplier"
    if "." in raw:
        return "decimal"
    return "integer"


# ================================================================
# Comparison analysis
# ================================================================

def _extract_number_set(claims):
    """Extract a set of (value_normalized, type) from claims for comparison."""
    numbers = set()
    for claim in claims.get("claims", []):
        for num in claim.get("numbers", []):
            # Normalize: strip $, %, commas, whitespace
            val = num.strip()
            val = re.sub(r'^[$~]', '', val)
            val = re.sub(r'[%xXBMK]$', '', val)
            val = val.replace(",", "").strip()
            try:
                float(val)
                numbers.add(val)
            except ValueError:
                pass
    return numbers


def _extract_claim_sentences(claims):
    """Extract claim sentences for topic comparison."""
    return [
        c.get("sentence", "")[:150]
        for c in claims.get("claims", [])
        if c.get("sentence") and len(c.get("sentence", "")) > 20
    ]


def analyze_model(model_name, text, sn_max_claims=15):
    """Analyze a single model's response.

    `sn_max_claims` caps how many claims are forwarded to the
    Source Network verifier. Default 15 matches the
    user-facing /compare flow where cost and latency per
    request are tight. The calling code passes
    `sn_max_claims=25` (Phase 1.6e item 2) because its per-
    cycle budget absorbs the extra queries and Section 8.4
    estimates 10 to 20 claims per cycle, so the old 15 cap
    was silently truncating the upper end of the distribution.
    The un-capped extracted count is available to any caller
    via the `claim_count` field on the returned dict.

    Public, reusable per-model analysis: structural measure, claim
    extraction, coverage and temporal framing, voice and epistemic
    basis detection, Source Network verification. Used both by
    compare_responses (synchronous batch) and by the SSE
    compare-stream endpoint (per-model events).

    The voice / epistemic detection is zero-LLM regex work that
    runs in microseconds; it was added in Phase 1.5 so the
    Frame Check Corpus Tier A events for compare modes populate
    the same framing fingerprint as single-mode events. The
    existing compare UI does not read the new fields, so this
    addition is invisible to users.
    """
    profile = measure(text)
    ca = analyze_claims(text)
    cov = detect_coverage(text)
    temp = temporal_orientation(text)
    voice = detect_voice(text)
    epist = detect_epistemic_basis(text)
    # V1 detector firings on this document. Same call site shape as
    # /api/profile and as MCP build_epistemic_payload (frame_check)
    # so the cross-surface signal stays uniform: programmatic
    # consumers reading /api/compare-stream's model_analyzed event
    # for either model see the same frame_library_matches[] shape
    # they would see on /api/profile for a single document. Without
    # this call, the per-model SSE payload had no FVS structural
    # match field at all -- same bug class as the four-month
    # /api/profile gap that commit e13284e closed; the gap on the
    # compare-path was discovered by the 2026-04-30 alignment audit.
    frame_suggestions = suggest_frames(cov, voice, temp, epist, text=text)

    # Source Network with always-render contract parity to /api/profile
    # (commit b01b163). Per-model sn_status surfaces partial-coverage and
    # unavailable states to the SSE consumer so the compare UI can show
    # the same honest banner the single-doc result page renders, instead
    # of silently presenting a partial verification subset as if it were
    # complete. sn_status enum values match /api/profile:
    #   "complete"    - every claim was processed
    #   "partial"     - SN budget exhausted; some claims budget-marked
    #   "unavailable" - SN raised; sn=[] returned
    #   "skipped"     - no claims to verify
    sn = []
    sn_status = "skipped"
    sn_status_reason = None
    if ca.get("claims"):
        try:
            sn = verify_claims_source_network(
                ca["claims"], doc_text=text, max_claims=sn_max_claims,
            )
            n_budget = sum(
                1 for r in sn
                if r.verdict == "unverifiable"
                and "budget" in (r.detail or "").lower()
            )
            if n_budget > 0:
                sn_status = "partial"
                processed = len(sn) - n_budget
                sn_status_reason = (
                    f"Source verification budget reached after "
                    f"{processed} of {len(sn)} claims for {model_name}. "
                    f"The most common cause is provider rate-limiting "
                    f"(CoinGecko free-tier 429s on crypto-heavy docs). "
                    f"The structural analysis is unaffected."
                )
            else:
                sn_status = "complete"
        except Exception as e:
            # Tolerated by design: source-network verification is
            # best-effort enrichment. A network failure, provider
            # quota exhaustion, or transient-API error must NOT
            # break the structural analysis path; sn stays empty
            # and the caller surfaces the structural measurements
            # without verification annotations. Log to stderr so
            # the operator can investigate without breaking the
            # JSON-RPC channel on stdout.
            import sys
            print(
                f"[comparison.analyze_model] "
                f"source-network verification failed for "
                f"{model_name}: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            sn_status = "unavailable"
            sn_status_reason = (
                f"Source verification failed for {model_name}: "
                f"{type(e).__name__}. The structural analysis is "
                f"complete and unaffected."
            )

    # Annotated rendering of the document with claim highlights.
    # Mirrors the /check (single-doc) flow at app.py:1670 where every
    # analysis pipes through annotate_document. The compare flow had
    # never wired this in: model cards showed metric pills with the
    # original text hidden inside <details><summary>View full
    # response</summary>, so the actual document the user pasted was
    # not the centerpiece evidence on the comparison surface. Empty
    # string fallback when no claims were extracted (very short docs)
    # so the template can branch on truthiness without surfacing a
    # raw text dump as a claimless block.
    try:
        from annotator import annotate_document as _annotate  # canon-exempt: optional web-only enrichment
        annotated_html = (
            _annotate(text, ca["claims"]) if ca.get("claims") else ""
        )
    except Exception as _exc:
        import sys
        print(
            f"[comparison.analyze_model] annotate_document failed for "
            f"{model_name}: {type(_exc).__name__}: {_exc}",
            file=sys.stderr,
        )
        annotated_html = ""

    return {
        "text": text,
        "annotated_doc": annotated_html,
        "word_count": profile["claim_density"]["word_count"],
        "claims": ca,
        "claim_count": ca.get("total_claims", 0),
        "unhedged_count": ca.get("unhedged_count", 0),
        "hedged_count": ca.get("hedged_count", 0),
        "prediction_count": ca.get("prediction_count", 0),
        "confidence_uniformity": ca.get("confidence_uniformity"),
        "numbers": _extract_number_set(ca),
        "sentences": _extract_claim_sentences(ca),
        "coverage": cov,
        "temporal": temp,
        "voice": voice,
        "epistemic": epist,
        "source_verified": sum(1 for r in sn if r.verdict in ("verified", "close")),
        "source_contradicted": sum(1 for r in sn if r.verdict == "contradicted"),
        "source_total": len(sn),
        # Per-model SN status for the always-render contract on the
        # compare surface. Mirrors the /api/profile sn_status field
        # documented in docs/MCP_SERVER.md so a programmatic consumer
        # of /api/compare-stream's model_analyzed event branches on
        # the same vocabulary it would on /api/profile. Internal
        # substrate signal; not surfaced as user-facing copy.
        "sn_status": sn_status,
        "sn_status_reason": sn_status_reason,
        # Per-contradiction surface so the compare UI can name what
        # contradicted what. Pre-fix the response carried only the
        # count ("1 contradicted out of 2") with no provider attribution
        # and an empty verified_providers list, leaving the reader
        # asking the obvious follow-up "contradicted by whom?". Each
        # entry names the document value and the source value plus
        # the source provider so the reader can verify the disagreement
        # rather than take the count on faith.
        "contradicted_details": [
            {
                "document_value": r.decomposition.raw_value if r.decomposition else None,
                "claim_subject": r.decomposition.subject if r.decomposition else None,
                # source_name fallback: r.best_source is set by the
                # SN orchestrator only when at least one source
                # returned 'exact' or 'close', i.e. when the claim
                # was VERIFIED. For purely-contradicted claims the
                # field is empty. Round-3 follow-up audit found
                # contradicted_details[].source_name was always ""
                # in practice. The fallback walks the per-claim
                # source_results to find the contradicting source
                # by name, which is the field a reader actually
                # wants ("contradicted by SEC EDGAR"). Empty string
                # only when no contradicted source carries a name,
                # which should be unreachable but matches pre-fix
                # behavior on edge cases.
                "source_name": r.best_source or next(
                    (sr.source_name for sr in (r.source_results or [])
                     if sr.match_type == "contradicted"),
                    "",
                ),
                "source_value": next(
                    (sr.source_value for sr in (r.source_results or [])
                     if sr.match_type == "contradicted"),
                    None,
                ),
            }
            for r in sn if r.verdict == "contradicted"
        ],
        # FVS structural matches per the V1 detector substrate.
        # Per-match shape mirrors /api/profile.framing.frame_library_matches[]
        # (8 fields: fvs_id / name / signal / question / definition /
        # url / v4_2_verdict / pattern_kind) so a programmatic
        # consumer reading either web JSON surface uses one
        # vocabulary. v4_2_verdict is always None on the compare
        # path because V4.2 LLM-judge cross-reference does not
        # run on /api/compare-stream by design (compare is
        # structural-only, no LLM in the framing layer); the field
        # is emitted as None for shape parity with /api/profile so
        # consumers branching on the field have a documented null
        # state instead of a missing key. pattern_kind defaults to
        # "present_detected" defensively for the same reason as
        # /api/profile and frame_check (frame_library.py:310 sets
        # it on every emitted suggestion today, but the
        # canned-suggestion shape used by some test callers omits
        # it; the get-with-default keeps those callers compatible).
        "frame_library_matches": [
            {
                "fvs_id": s.get("fvs_id"),
                "name": s.get("name"),
                "signal": s.get("signal"),
                "question": s.get("question"),
                "definition": s.get("definition"),
                "url": s.get("url"),
                "v4_2_verdict": None,
                "pattern_kind": s.get("pattern_kind", "present_detected"),
            }
            for s in (frame_suggestions or [])
        ],
        # Raw verifier-result list for downstream telemetry builders.
        # The compare-stream serializer omits this field via
        # serialize_model_for_stream's truncation logic; it lives in
        # the analyzed dict only for compare-mode builders to read.
        "sn_results": sn,
    }


def jsonify(obj):
    """Recursively convert sets to sorted lists for JSON encoding.

    The analyze_model result and build_cross_model_comparison output
    contain Python sets in fields like 'numbers' that the json module
    cannot encode. This walks the structure and converts in place.

    Also drops the `sn_results` key from any dict it encounters.
    analyze_model attaches the raw verifier-result list to its return
    value so downstream telemetry can derive source name lists for
    compare-mode events; that dataclass is not JSON-serializable and
    the field should never flow into a JSON sink. Stripping here
    keeps front-end serializers in sync with the return shape
    without each having to repeat the strip.
    """
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items() if k != "sn_results"}
    if isinstance(obj, (list, tuple)):
        return [jsonify(v) for v in obj]
    return obj


def serialize_model_for_stream(model_data):
    """Convert an analyze_model result to a JSON-serializable dict.

    Wraps jsonify with response-text truncation so the SSE event
    payload stays reasonable. Used by the compare-stream endpoint.

    Strips the `sn_results` key (added for downstream telemetry)
    because SourceNetworkResult is a Python dataclass that
    json.dumps cannot serialize directly, and because the browser
    does not need the per-source detail in the SSE payload anyway.
    """
    if not model_data:
        return None
    # Shallow-copy and drop the corpus-only field before jsonify.
    # The drop is structural: even if sn_results were
    # serializable, the SSE payload should not include the raw
    # SourceResult URLs and source_text fields that live inside
    # each SourceNetworkResult.
    stream_data = {k: v for k, v in model_data.items() if k != "sn_results"}
    out = jsonify(stream_data)
    text = out.get("text", "")
    if len(text) > 2000:
        out["text"] = text[:2000]
    return out


def _compose_compare_verdict(
    *,
    verbatim_overlap=None,
    frames_shared=None,
    frames_per_model=None,
    agreed_count=0,
    disagreement_count=0,
    subject="Both responses",
):
    """Compose the at-a-glance verdict sentence for the compare page.

    The verdict leads with FRAMES, not counts. The frame each response
    operates in is the load-bearing finding for a comparison: same
    frame means same lens (agreement is plausibly tautological);
    different frames means different measurement (responses reach
    different conclusions because they answer different questions).
    Counts and dimension lists become evidence in sections below;
    the verdict surfaces the structural finding the reader needs to
    interpret everything else.

    Mirrors /check's verdict-headline pattern (frame as headline,
    consequence implicit) adapted for two responses. Zero LLM cost.

    Branches in priority order:

      1. Verbatim alignment. When the structural detector flagged the
         responses as substantially identical text, "Both operate in
         X" is misleading because there is only ONE text being read
         twice. Verdict subsumes what a separate verbatim callout
         used to say.

      2. Shared top frame. Both responses' top detected frame is the
         same; the verdict states what frame they share.

      3. Divergent top frames. Each response has a different top
         detected frame; the verdict names the difference.

      4. One-sided frame. Only one response has a detected frame;
         the verdict names the asymmetry.

      5. No frames detected on either side. The verdict falls back to
         a structural count summary so the page does not lead with
         silence on a comparison that produced data.

      6. All-empty. Rare; the verdict says the responses are analyzed
         below without inventing content.

    Args:
        verbatim_overlap: dict {ratio, level} from
            _detect_verbatim_overlap, or None when responses have
            meaningful text-level differences.
        frames_shared: list of frame dicts from _compose_compare_
            takeaway when both responses use identical frames in the
            same order; None or empty otherwise.
        frames_per_model: list of {model_name, frames} dicts from
            _compose_compare_takeaway. Each "frames" list is the
            top-3 detected frames for that model; the verdict uses
            only the top one.
        agreed_count: int, number of values both responses cite.
        disagreement_count: int, number of near_matches.
        subject: noun phrase for the count fallback ("These responses",
            "These documents", or "Both responses").
    """

    def _frame_label(f):
        # Format a frame for verdict prose. Frame NAME only; the
        # FVS-NNN identifier is library jargon and surfaces on the
        # FVS chip (clickable badge linking to the library entry)
        # rather than in the user-facing verdict sentence. Operator
        # flagged the prior "Frame Name (FVS-NNN)" form as noise:
        # readers don't know what FVS is, and the badge already
        # carries the identifier where it earns its space. The fvs
        # fallback applies only when a frame fired without a name
        # (rare; defensive against partial library data).
        name = (f or {}).get("name") or ""
        fvs = (f or {}).get("fvs_id") or ""
        return name or fvs or "an unnamed frame"

    # 1. Verbatim alignment takes precedence. There is no comparison
    # to make when the responses are the same text.
    if verbatim_overlap and verbatim_overlap.get("level") == "verbatim":
        return f"{subject} are the same text. There is no comparison to make."

    fpm = frames_per_model or []
    a_block = fpm[0] if len(fpm) >= 1 else {}
    b_block = fpm[1] if len(fpm) >= 2 else {}
    a_frames = (a_block.get("frames") or []) if isinstance(a_block, dict) else []
    b_frames = (b_block.get("frames") or []) if isinstance(b_block, dict) else []
    a_top = a_frames[0] if a_frames else None
    b_top = b_frames[0] if b_frames else None
    a_name = (a_block.get("model_name") if isinstance(a_block, dict) else None) or "Document A"
    b_name = (b_block.get("model_name") if isinstance(b_block, dict) else None) or "Document B"

    # 2. Shared top frame. The composer (_compose_compare_takeaway)
    # populates frames_shared only when the top-level frame shape
    # matches across both sides; surface the top shared frame.
    if frames_shared:
        shared_top = frames_shared[0] if isinstance(frames_shared, list) and frames_shared else None
        if shared_top:
            return f"Both responses operate in {_frame_label(shared_top)}."

    # 3. Divergent top frames. Both sides have a frame and they
    # differ. (frames_shared would have caught the matching case
    # above.)
    if a_top and b_top:
        return (
            f"{a_name} operates in {_frame_label(a_top)}; "
            f"{b_name} in {_frame_label(b_top)}. "
            f"They measure different things."
        )

    # 4. One-sided frame.
    if a_top and not b_top:
        return (
            f"{a_name} operates in {_frame_label(a_top)}; "
            f"{b_name} has no detected frame."
        )
    if b_top and not a_top:
        return (
            f"{b_name} operates in {_frame_label(b_top)}; "
            f"{a_name} has no detected frame."
        )

    # 5. No frames on either side. Fall back to structural counts so
    # the page does not lead with silence.
    if agreed_count > 0 or disagreement_count > 0:
        parts = []
        if agreed_count > 0:
            parts.append(
                f"{agreed_count} numerical value"
                f"{'' if agreed_count == 1 else 's'} agree"
            )
        if disagreement_count > 0:
            parts.append(
                f"{disagreement_count} disagreement"
                f"{'' if disagreement_count == 1 else 's'}"
            )
        return f"{subject}: {'; '.join(parts)}."

    # 6. All-empty: no frames, no verbatim, no counts. Returns the
    # empty string so the verdict-hero hides entirely. /check uses
    # the same pattern (frame-check-portrait / frame-check-headline
    # are conditional on substantive content; nothing renders when
    # both are empty). Hollow placeholder prose lowers authority;
    # honest absence beats "<subject> analysed structurally below."
    return ""


def _compose_compare_takeaway(models, model_names, shared_blind):
    """Compose structural takeaway questions for the comparison.

    Mirrors the per-document takeaway-questions panel on /check
    (frame_library.compose_takeaway_questions). Surfaces:
      - frames_per_model: each model's detected frames, capped at
        three per side, with name + FVS id + library link + the
        operator-curated per-frame question. Lets a reader see at
        a glance which structural frames each response is doing
        work through; the per-frame question is the operator-
        curated probe to take to an LLM.
      - absent_dimensions: shared blind-spot dimensions (those
        BOTH responses fail to engage) with the canonical
        COVERAGE_QUESTIONS phrasing. Each dimension gets a
        ready-to-ask question rather than a bare label.

    Zero LLM cost; pure composition from existing per-model
    `frame_library_matches` data + the cross-model `shared_blind`
    list.

    Returned dict shape mirrors compose_takeaway_questions's
    relevant subset so a future template-extraction pass could
    share a partial between /check and /compare for the
    frames-list rendering. The numerical_disputes section that
    /check's takeaway panel does not have is omitted here too:
    the compare page already has a dedicated Numerical
    disagreements section with full per-claim cards, so duplicating
    in the takeaway panel would crowd the page.
    """
    # Avoid a hard import dependency at module load time; this
    # composition path is only exercised when callers actually need
    # the takeaway data, so import inline keeps comparison.py
    # importable without frame_library installed (e.g., for save-
    # side validation paths that read the compare JSON without
    # building it).
    try:
        from frame_library import COVERAGE_QUESTIONS
    except ImportError:
        COVERAGE_QUESTIONS = {}

    def _collect_frames(model_data):
        # frame_library_matches is the analyzed-model output's
        # canonical name (set in comparison.analyze_model). Older
        # callers that pass models without this field get an empty
        # list rather than a KeyError.
        matches = (model_data or {}).get("frame_library_matches") or []
        out = []
        for m in matches[:3]:
            if not isinstance(m, dict):
                continue
            fvs_id = m.get("fvs_id")
            out.append({
                "name": m.get("name") or "",
                "fvs_id": fvs_id or "",
                "library_url": (
                    f"/corpus/library/{fvs_id}.html" if fvs_id else ""
                ),
                "signal": m.get("signal") or "",
                "question": m.get("question") or "",
                # Carry the frame's library-paragraph definition so the
                # compare takeaway panel can render at the same depth as
                # /check's suggestion-card surface (name + signal +
                # definition + question), not just a thinner three-field
                # subset. Pre-2026-05-06 the compare path stripped this
                # field on the way through; the operator flagged the
                # missing context as the highest-leverage gap on the
                # compare top-section.
                "definition": m.get("definition") or "",
            })
        return out

    frames_per_model = []
    for name in model_names:
        if name not in models:
            continue
        frames_per_model.append({
            "model_name": name,
            "frames": _collect_frames(models[name]),
        })

    # Detect "both responses use the exact same frames in the same
    # order." When true, the takeaway panel collapses the per-model
    # block into one shared "Both documents" block instead of
    # rendering the same frame chip + signal + question twice. The
    # operator flagged the per-side duplicate as visual noise on
    # comparisons of near-identical documents (verbatim sample).
    #
    # Comparison key: (fvs_id, name, signal, question) tuple per
    # frame. fvs_id alone would be enough for shape-equality but
    # carrying name + signal + question prevents a future case
    # where two slightly different signal extractions for the same
    # FVS-ID get collapsed when they shouldn't be. List length must
    # match too; if A has [X, Y] and B has [X], they're not the
    # same shape even if X matches.
    frames_shared = None
    if len(frames_per_model) == 2:
        a_frames = frames_per_model[0].get("frames") or []
        b_frames = frames_per_model[1].get("frames") or []
        if a_frames and len(a_frames) == len(b_frames):
            def _key(f):
                return (
                    f.get("fvs_id") or "",
                    f.get("name") or "",
                    f.get("signal") or "",
                    f.get("question") or "",
                )
            if [_key(f) for f in a_frames] == [_key(f) for f in b_frames]:
                # Both sides identical: surface the shared list.
                # Templates branch on this and skip per-model render.
                frames_shared = list(a_frames)

    absent_dimensions = [
        {"name": dim, "question": COVERAGE_QUESTIONS.get(dim, "")}
        for dim in (shared_blind or [])
    ]

    return {
        "frames_per_model": frames_per_model,
        "frames_shared": frames_shared,
        "absent_dimensions": absent_dimensions,
    }


def _detect_verbatim_overlap(models, model_names, threshold=0.95):
    """Detect whether two compared responses share substantially
    identical text.

    Why this matters: when two responses are byte-identical or
    near-identical, the structural agreements surfaced elsewhere on
    /compare (numerical agreement, shared blind spots, shared frames)
    reflect the SAME TEXT being analyzed twice, not two independent
    reads converging. Failure modes that produce near-identical text:
    cached response served from two providers, the same response
    pasted twice by accident, two RAG calls hitting the same source,
    training-data echo across providers, deterministic models with
    temperature 0 on the same prompt. Without this signal a reader
    of /compare draws "both responses agree" conclusions when the
    correct read is "the responses are the same text."

    Algorithm: difflib.SequenceMatcher.ratio() in [0, 1]. Inputs are
    capped at 20K chars per side to bound the O(N*M) worst case;
    longer responses sample the first 20K which preserves verbatim-
    alignment detection (verbatim duplicates trigger >= threshold on
    any substantial prefix). The cheap real_quick_ratio() and
    quick_ratio() upper bounds short-circuit the full ratio() when
    they cannot possibly cross threshold, so the typical "very
    different responses" path stays O(N+M).

    Args:
        models: {name: analyze_model_result} dict. Each model_result
            carries a "text" field with the original response.
        model_names: ordered list of names to compare. Only the
            first two are read; if fewer than two are available,
            returns None.
        threshold: ratio cutoff. Default 0.95 corresponds to "byte-
            identical or trivially different (whitespace, encoding)."
            Below 0.95 the responses have meaningful text-level
            differences even if they share substantial prose, so the
            agreement signal is still informative; above 0.95 the
            responses are effectively the same text and the agreement
            signal is misleading.

    Returns:
        {"ratio": float, "level": "verbatim"} when ratio >= threshold;
        None otherwise. Future expansion can add more levels at
        lower thresholds; the current scope only surfaces the
        strongest signal so the page does not flag every comparison
        with shared topic-driven prose.
    """
    import difflib

    if not model_names or len(model_names) < 2:
        return None
    name_a = model_names[0]
    name_b = model_names[1]
    if name_a not in models or name_b not in models:
        return None
    text_a = (models[name_a] or {}).get("text") or ""
    text_b = (models[name_b] or {}).get("text") or ""
    if not text_a or not text_b:
        return None

    cap = 20000
    a = text_a[:cap]
    b = text_b[:cap]

    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < threshold:
        return None
    if sm.quick_ratio() < threshold:
        return None
    ratio = sm.ratio()
    if ratio < threshold:
        return None

    return {
        "ratio": round(ratio, 3),
        "level": "verbatim",
    }


def _oxford(items, conj="and"):
    """Join a list with commas + a conjunction for the last item.

    Returns "" for empty, "X" for one, "X <conj> Y" for two,
    "X, Y, <conj> Z" for three or more (Oxford comma). Conjunction
    defaults to "and"; pass conj="or" for negative-list lists where
    "neither addresses A, B, or C" reads more naturally than "and".
    """
    items = [str(x) for x in items if x]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return ", ".join(items[:-1]) + f", {conj} {items[-1]}"


def _compose_comparison_portrait(models, model_names, agreed_count, mode=None):
    """Deterministic 2-3 sentence prose portrait of the comparison.

    Sits at the top of /compare's takeaway panel, mirroring the role
    /check's framing_portrait_natural plays: a one-glance read of the
    structural picture before any LLM lands. Zero LLM cost, anchored
    on measured signals (voice, temporal, coverage overlap, claim
    counts, numerical agreement).

    Three sentences, each conditional:
      1. voice + temporal across both responses
      2. shared coverage / shared blind spots (intersection language)
      3. claim counts + numerical agreement note (if agreed > 0)

    Returns the composed paragraph as a string, or None when
    insufficient input (less than two models, missing voice data).
    """
    if not model_names or len(model_names) < 2:
        return None
    name_a = model_names[0]
    name_b = model_names[1]
    if name_a not in models or name_b not in models:
        return None
    a = models[name_a] or {}
    b = models[name_b] or {}

    a_voice = (a.get("voice") or {}).get("voice", "") or ""
    b_voice = (b.get("voice") or {}).get("voice", "") or ""
    a_temp = (a.get("temporal") or {}).get("dominant", "") or ""
    b_temp = (b.get("temporal") or {}).get("dominant", "") or ""

    # Subject vocabulary. Documents-mode reads as "responses" still,
    # because the user is comparing two pasted texts side-by-side and
    # "documents" + "neither addresses" + claim counts feels stilted
    # in the same sentence. Mirrors the verdict_subject default.
    subject_plural = (
        "These documents" if mode == "documents" else "Both responses"
    )

    sentences = []

    # ── 1. voice + temporal ──
    voice_phrase = None
    if a_voice and b_voice:
        if a_voice == b_voice:
            voice_phrase = f"{subject_plural} read as {a_voice}"
        else:
            voice_phrase = (
                f"{name_a} reads as {a_voice} while "
                f"{name_b} reads as {b_voice}"
            )

    temporal_phrase = None
    if a_temp and b_temp:
        if a_temp == b_temp:
            temporal_phrase = f"both {a_temp}-oriented"
        else:
            temporal_phrase = (
                f"{name_a} leans {a_temp}-oriented while "
                f"{name_b} leans {b_temp}-oriented"
            )

    if voice_phrase and temporal_phrase:
        sentences.append(f"{voice_phrase}, {temporal_phrase}.")
    elif voice_phrase:
        sentences.append(f"{voice_phrase}.")
    elif temporal_phrase:
        # Capitalize the first letter when temporal is the lead.
        s = temporal_phrase[0].upper() + temporal_phrase[1:]
        sentences.append(f"{s}.")

    # ── 2. shared coverage + shared blind spots ──
    a_cov = a.get("coverage") or {}
    b_cov = b.get("coverage") or {}
    a_covered = set(a_cov.get("covered") or [])
    b_covered = set(b_cov.get("covered") or [])
    a_missing = set(a_cov.get("missing") or [])
    b_missing = set(b_cov.get("missing") or [])

    shared_covered = sorted(a_covered & b_covered)
    shared_missing = sorted(a_missing & b_missing)

    if shared_covered and shared_missing:
        sentences.append(
            f"Both engage {_oxford(shared_covered)}; "
            f"neither addresses {_oxford(shared_missing, conj='or')}."
        )
    elif shared_covered:
        sentences.append(f"Both engage {_oxford(shared_covered)}.")
    elif shared_missing:
        sentences.append(
            f"Neither addresses {_oxford(shared_missing, conj='or')}."
        )

    # ── 3. claim counts + numerical agreement ──
    a_claims = a.get("claim_count") or 0
    b_claims = b.get("claim_count") or 0
    a_unhedged = a.get("unhedged_count") or 0
    b_unhedged = b.get("unhedged_count") or 0

    if a_claims > 0 and b_claims > 0:
        a_part = (
            f"{name_a} carries {a_claims} "
            f"{'claim' if a_claims == 1 else 'claims'}"
        )
        if a_unhedged > 0:
            a_part += f" ({a_unhedged} as fact)"
        b_part = (
            f"{name_b} carries {b_claims}"
        )
        if b_unhedged > 0:
            b_part += f" ({b_unhedged} as fact)"
        tail = ""
        if agreed_count > 0:
            tail = (
                f", with {agreed_count} numerical "
                f"{'value' if agreed_count == 1 else 'values'} "
                f"cited identically"
            )
        sentences.append(f"{a_part}; {b_part}{tail}.")

    if not sentences:
        return None
    return " ".join(sentences)


def build_cross_model_comparison(models, mode=None):
    """Build the cross-model insights from per-model analyses.

    Takes a dict of {model_name: analyze_model(...) result} and
    returns the agreed numbers, disagreements, blind spots, etc.
    Used both by compare_responses and by the SSE stream endpoint.

    The optional `mode` arg ("topic" or "documents") drives the
    subject phrasing in the at-a-glance verdict text. Defaults to
    None so existing callers (compare_examples.py, sync
    compare_responses) keep working without modification; the
    verdict uses the generic "Both responses" subject in that
    case, which reads cleanly for both topic-mode (LLM models
    answering the same question) and documents-mode (pasted
    documents on the same subject).
    """
    if len(models) < 2:
        return None

    model_names = list(models.keys())
    a_name, b_name = model_names[0], model_names[1]
    a, b = models[a_name], models[b_name]

    a_nums = a["numbers"]
    b_nums = b["numbers"]

    agreed_numbers = a_nums & b_nums
    only_a = a_nums - b_nums
    only_b = b_nums - a_nums

    near_matches = []
    for va in only_a:
        try:
            fa = float(va)
        except ValueError:
            continue
        for vb in only_b:
            try:
                fb = float(vb)
            except ValueError:
                continue
            if fa == 0 or fb == 0:
                continue
            rel_diff = abs(fa - fb) / max(abs(fa), abs(fb))
            if 0.01 < rel_diff < 0.30:
                near_matches.append({
                    "value_a": va,
                    "value_b": vb,
                    "difference": f"{rel_diff:.0%}",
                    "model_a": a_name,
                    "model_b": b_name,
                    "context_a": _find_sentence_for_value(va, a["claims"]),
                    "context_b": _find_sentence_for_value(vb, b["claims"]),
                })

    missing_a = set(a["coverage"]["missing"])
    missing_b = set(b["coverage"]["missing"])
    shared_blind = sorted(missing_a & missing_b)

    # Build the deterministic structural framing comparison. This
    # is the zero-LLM counterpart to the AI "How they frame this
    # topic" section. It compares voice, coverage, epistemic,
    # and temporal orientation between the two models and
    # produces a structural narrative that works without any
    # API key. The AI comparison enhances this when available;
    # this provides the baseline that every user gets.
    #
    # Two forms are emitted:
    #   - structural_framing_diff: the legacy single-paragraph
    #     prose string. Older saved-comparison JSON files and the
    #     existing test corpus rely on this exact form; keeping it
    #     means a save written on an earlier build still renders,
    #     and the test for prose content keeps passing.
    #   - structural_framing_cards: the structured data (headline
    #     + per-dimension cards + shared-blind note). New templates
    #     render this as a visual comparison layout rather than a
    #     dense prose paragraph. When a saved JSON file does not
    #     carry this key (older save), the template falls back to
    #     the prose string transparently.
    framing_data = _build_structural_framing_data(
        a_name, a, b_name, b, shared_blind,
        missing_a - missing_b, missing_b - missing_a,
    )
    structural_diff = framing_data["prose"] if framing_data else None
    structural_cards = None
    if framing_data:
        structural_cards = {
            "headline": framing_data["headline"],
            "cards": framing_data["cards"],
            "unique_omissions": framing_data["unique_omissions"],
            "shared_blind_note": framing_data["shared_blind_note"],
        }

    # Agreed numbers with per-model context. Operator's call
    # 2026-05-05: bare-number tags ("383", "200", "31.5") tell the
    # reader nothing about what those numbers mean or where they
    # came from. The richer shape attaches model A's sentence and
    # model B's sentence for each agreed value (using the same
    # _find_sentence_for_value helper that near_matches uses), so
    # the rendered output can show "Both models cite $383B in:
    # 'Apple reported total revenue of $383 billion' / 'Apple's
    # FY2024 revenue was $383 billion'" instead of just "$383".
    # Older saved-comparison JSON files carry agreed_numbers as a
    # plain list of strings; the saved-view template tolerates
    # both shapes (list-of-strings -> bare tags fallback;
    # list-of-dicts -> context cards) so existing saves keep
    # rendering without server backfill.
    agreed_numbers_sorted = sorted(
        agreed_numbers,
        key=lambda x: float(x) if x.replace(".", "").isdigit() else 0,
    )
    agreed_numbers_with_context = [
        {
            "value": v,
            "context_a": _find_sentence_for_value(v, a["claims"]),
            "context_b": _find_sentence_for_value(v, b["claims"]),
        }
        for v in agreed_numbers_sorted
    ]

    # Compute the takeaway and verbatim-overlap signals BEFORE the
    # verdict so the verdict can lead with frames (which the takeaway
    # composer detects) and short-circuit on verbatim alignment. The
    # verdict is the load-bearing top-of-page string; pulling its
    # input dependencies up here means the verdict has full
    # structural context, not just count fallbacks.
    takeaway_questions = _compose_compare_takeaway(
        models=models,
        model_names=model_names,
        shared_blind=shared_blind,
    )
    # Mode-aware verbatim gating. The detector's documented failure
    # modes (cached response served from two providers, training-data
    # echo, deterministic models with temperature 0 on the same prompt,
    # the same response pasted twice by accident) are topic-mode
    # pathologies primarily, but documents-mode users also paste
    # near-identical text often enough that a quietly-disabled detector
    # leaves the verdict reading "Both responses operate in <Frame>"
    # on a comparison that is actually two copies of the same document.
    # The original gate disabled documents-mode entirely after a 0.98-
    # ratio false-positive on docs sharing exec-summary + conclusion
    # boilerplate; raising the documents-mode threshold to 0.99 keeps
    # the detector live for byte-identical paste-twice cases while
    # still excluding shared-template comparisons. Topic-mode keeps
    # the original 0.95 threshold (where shared training-data echo
    # is the dominant pathology); the legacy mode=None caller keeps
    # 0.95 for backward compat with programmatic consumers that have
    # not opted into the mode contract.
    if mode == "documents":
        verbatim_overlap = _detect_verbatim_overlap(
            models, model_names, threshold=0.99,
        )
    else:
        verbatim_overlap = _detect_verbatim_overlap(models, model_names)

    verdict_subject = (
        "These responses" if mode == "topic"
        else "These documents" if mode == "documents"
        else "Both responses"
    )
    verdict_text = _compose_compare_verdict(
        verbatim_overlap=verbatim_overlap,
        frames_shared=takeaway_questions.get("frames_shared"),
        frames_per_model=takeaway_questions.get("frames_per_model"),
        agreed_count=len(agreed_numbers_sorted),
        disagreement_count=len(near_matches),
        subject=verdict_subject,
    )

    # Comparison portrait: deterministic 2-3 sentence prose summary
    # of the structural picture across both responses (voice +
    # temporal, shared coverage + blind spots, claim counts +
    # numerical agreement). Mirrors /check's framing_portrait_natural
    # role on the compare side: gives the reader a one-glance read of
    # the structural depth before any LLM narrative lands. Zero LLM
    # cost; rendered immediately in the takeaway panel hero. Operator
    # flagged 2026-05-06 that the compare top-section was missing the
    # complexity and value /check's first section surfaces.
    comparison_portrait = _compose_comparison_portrait(
        models=models,
        model_names=model_names,
        agreed_count=len(agreed_numbers_sorted),
        mode=mode,
    )

    return {
        "models": models,
        "model_names": model_names,
        "framing_comparison": None,
        "structural_framing_diff": structural_diff,
        "structural_framing_cards": structural_cards,
        # framing_differences: canonical name matching MCP
        # frame_compare's analysis.comparison.framing_differences
        # field. Carries the full _build_structural_framing_data
        # return dict (headline + cards + unique_omissions +
        # shared_blind_note + prose) so a programmatic consumer
        # reading either web JSON (SSE comparison event payload
        # OR saved comparison JSON loaded from
        # /saved-compare/<hash>) and MCP frame_compare uses one
        # vocabulary. The structural_framing_diff and
        # structural_framing_cards siblings remain for backward-
        # compat with already-deployed clients (HTML template at
        # templates/compare.html reads structural_framing_cards;
        # already-saved JSON files written before 2026-04-30 do
        # not carry framing_differences at all and the load path
        # tolerates the missing key via dict.get). Discovered as
        # a saved-JSON alias gap in the post-audit polish pass:
        # the SSE-payload alias landed first; this propagates
        # the same alias to the saved-JSON storage layer so the
        # canonical name is reachable from every export surface,
        # not just the live SSE stream.
        "framing_differences": framing_data,
        # Verdict text: a single-sentence at-a-glance read composed
        # frame-first. The verdict leads with what frame each response
        # operates in, falling back to a structural count summary when
        # no frames detected, and short-circuits to "These responses
        # are the same text" when verbatim alignment fires. Zero LLM
        # cost; computed above from takeaway_questions + verbatim_
        # overlap + agreed/disagreed counts. Mirrors /check's
        # verdict-headline shape (frame as headline) adapted for two
        # responses.
        "verdict_text": verdict_text,
        # Comparative takeaway questions: structurally composed
        # from per-model frame_library_matches + cross-model
        # shared_blind. Mirrors /check's takeaway-questions panel
        # but on the compare side. Zero LLM cost. The compare
        # template renders this as a panel right after the verdict
        # hero; the compare-takeaway block driven by Grok
        # (honest_headline + question_to_ask) stays separately
        # inside the framing-comparison section so the two action
        # surfaces complement rather than overlap.
        "takeaway_questions": takeaway_questions,
        # Deterministic structural prose portrait of the comparison.
        # Sits at the top of the takeaway panel as a one-glance read of
        # the structural picture before any LLM lands. Mirrors the role
        # framing_portrait_natural plays on /check. May be None when
        # input is too thin (single model, missing voice data).
        "comparison_portrait": comparison_portrait,
        "agreed_numbers": agreed_numbers_with_context,
        "only_a": sorted(only_a),
        "only_b": sorted(only_b),
        "near_matches": near_matches,
        "blind_spots": shared_blind,
        "only_a_missing": sorted(missing_a - missing_b),
        "only_b_missing": sorted(missing_b - missing_a),
        "summary": {
            "total_agreed": len(agreed_numbers),
            "total_only_a": len(only_a),
            "total_only_b": len(only_b),
            "disagreements": len(near_matches),
        },
        # Verbatim overlap finding: populated when both responses
        # share substantially identical text (>= 0.95 SequenceMatcher
        # ratio). The verdict_text above absorbs this into its
        # leading sentence ("These responses are the same text...");
        # the field is also persisted on the SSE payload and saved
        # JSON for programmatic consumers (MCP, etc.) that may want
        # the raw signal independent of the verdict prose.
        "verbatim_overlap": verbatim_overlap,
    }


def _build_structural_framing_data(
    a_name, a, b_name, b,
    shared_blind, only_a_blind, only_b_blind,
):
    """Build a deterministic structural framing comparison as
    structured data. Zero LLM.

    Returns a dict with:
      - headline: optional opening characterization (str or None)
      - cards: list of per-dimension comparison cards, each with:
          dimension, label, a_value, b_value, note (implication)
      - unique_omissions: {"a_omits": [...], "b_omits": [...]}
      - shared_blind_note: {"dimensions": [...], "consequence": str}
        or None
      - prose: the joined single-paragraph prose form, derived from
        the structured content, for surfaces that cannot render
        structured layouts (the legacy structural_framing_diff
        string used by older saved-comparison JSON and by tests).

    This is the Frame Check core value for compare mode: a
    computational structural diff that reveals how two responses
    frame the same topic differently. It works without any API
    key and produces the same output every time for the same
    inputs. The prose form and the structured cards are produced
    together so the prose rendering stays word-identical to the
    pre-refactor output for the test corpus and for already-saved
    comparisons.
    """
    prose_parts = []
    cards = []
    headline = None
    shared_blind_note = None

    a_cov = a.get("coverage", {})
    b_cov = b.get("coverage", {})
    a_count = a_cov.get("coverage_count", 0)
    b_count = b_cov.get("coverage_count", 0)
    a_voice = (a.get("voice") or {}).get("voice", "")
    b_voice = (b.get("voice") or {}).get("voice", "")
    a_sourced = (a.get("epistemic") or {}).get("sourced_pct", 0) or 0
    b_sourced = (b.get("epistemic") or {}).get("sourced_pct", 0) or 0
    a_temp = (a.get("temporal") or {}).get("dominant", "")
    b_temp = (b.get("temporal") or {}).get("dominant", "")

    # Count divergent dimensions for opening characterization
    divergences = 0
    if a_count != b_count:
        divergences += 1
    if a_voice and b_voice and a_voice != b_voice:
        divergences += 1
    if abs(a_sourced - b_sourced) >= 10:
        divergences += 1
    if a_temp and b_temp and a_temp != b_temp:
        divergences += 1

    # ── Opening: characterize the relationship ──
    if divergences == 0:
        if shared_blind:
            headline = (
                "Both documents take a structurally similar approach. "
                "The shared framing means shared blind spots."
            )
        else:
            headline = (
                "Both documents take a structurally similar approach, "
                "with comparable analytical coverage, voice, and sourcing."
            )
    elif divergences >= 3:
        headline = (
            "These documents position the reader differently "
            "across multiple structural dimensions."
        )
    if headline:
        prose_parts.append(headline)

    # ── Coverage ──
    if a_count != b_count:
        wider = a_name if a_count > b_count else b_name
        narrower = b_name if a_count > b_count else a_name
        wider_n = max(a_count, b_count)
        narrower_n = min(a_count, b_count)
        if narrower_n == 0:
            cov_prose = (
                f"{wider} has markers for {wider_n} of 5 analytical "
                f"perspectives. {narrower} has none."
            )
            cov_note = None
        else:
            cov_prose = (
                f"{wider} has markers for {wider_n} of 5 analytical "
                f"perspectives while {narrower} has {narrower_n}. The "
                f"narrower document produces conclusions from less "
                f"context."
            )
            cov_note = (
                "The narrower document produces conclusions from less context."
            )
        cards.append({
            "dimension": "coverage",
            "label": "Analytical coverage",
            "a_value": f"{a_count} of 5 perspectives",
            "b_value": f"{b_count} of 5 perspectives",
            "note": cov_note,
        })
        prose_parts.append(cov_prose)
    elif a_count == b_count and a_count < 5:
        cards.append({
            "dimension": "coverage",
            "label": "Analytical coverage",
            "a_value": f"{a_count} of 5 perspectives",
            "b_value": f"{b_count} of 5 perspectives",
            "note": "Shared coverage footprint across both documents.",
        })
        prose_parts.append(
            f"Both cover {a_count} of 5 analytical perspectives."
        )

    if only_a_blind:
        prose_parts.append(
            f"Only {a_name} has no detected markers for: "
            f"{', '.join(sorted(only_a_blind))}."
        )
    if only_b_blind:
        prose_parts.append(
            f"Only {b_name} has no detected markers for: "
            f"{', '.join(sorted(only_b_blind))}."
        )

    # ── Voice ──
    if a_voice and b_voice and a_voice != b_voice:
        # "analytical" is the residual cascade classification (no
        # prescriptive/promotional/descriptive/advisory markers fired).
        # Report as evidence-absence rather than existential
        # "presents third-person examination."
        voice_implications = {
            "promotional": "positions the reader as a buyer",
            "prescriptive": "tells the reader what to do",
            "analytical": "has no directive/promotional/descriptive voice markers detected",
            "descriptive": "catalogs facts without interpretation",
            "advisory": "offers guidance with some direction",
        }
        a_imp = voice_implications.get(a_voice, f"uses {a_voice} voice")
        b_imp = voice_implications.get(b_voice, f"uses {b_voice} voice")
        cards.append({
            "dimension": "voice",
            "label": "Voice",
            "a_value": a_voice,
            "b_value": b_voice,
            "note": (
                f"{a_name} {a_imp}; {b_name} {b_imp}. "
                f"The same data serves different purposes depending on "
                f"which document a reader encounters first."
            ),
        })
        prose_parts.append(
            f"{a_name} {a_imp}; {b_name} {b_imp}. "
            f"The same data serves different purposes depending on "
            f"which document a reader encounters first."
        )

    # ── Epistemic ──
    if abs(a_sourced - b_sourced) >= 10:
        better = a_name if a_sourced > b_sourced else b_name
        better_pct = max(a_sourced, b_sourced)
        worse = b_name if a_sourced > b_sourced else a_name
        worse_pct = min(a_sourced, b_sourced)
        cards.append({
            "dimension": "sourcing",
            "label": "Sourcing",
            "a_value": f"{a_sourced}% attributed",
            "b_value": f"{b_sourced}% attributed",
            "note": (
                f"Conclusions from {worse} are harder to independently verify."
            ),
        })
        prose_parts.append(
            f"{better} attributes {better_pct}% of claims to sources; "
            f"{worse} attributes {worse_pct}%. "
            f"Conclusions from {worse} are harder to independently verify."
        )

    # ── Hedging strategy / certainty ──
    a_claims = a.get("claim_count", 0)
    b_claims = b.get("claim_count", 0)
    a_unhedged = a.get("unhedged_count", 0)
    b_unhedged = b.get("unhedged_count", 0)

    if a_claims >= 3 and b_claims >= 3:
        a_unhedged_pct = round(a_unhedged / a_claims * 100)
        b_unhedged_pct = round(b_unhedged / b_claims * 100)
        if abs(a_unhedged_pct - b_unhedged_pct) >= 20:
            assertive = a_name if a_unhedged_pct > b_unhedged_pct else b_name
            cautious = b_name if a_unhedged_pct > b_unhedged_pct else a_name
            assertive_pct = max(a_unhedged_pct, b_unhedged_pct)
            cautious_pct = min(a_unhedged_pct, b_unhedged_pct)
            cards.append({
                "dimension": "certainty",
                "label": "Certainty",
                "a_value": f"{a_unhedged_pct}% as fact",
                "b_value": f"{b_unhedged_pct}% as fact",
                "note": (
                    f"A reader of {assertive} receives more confidence "
                    f"than the evidence warrants compared to {cautious}."
                ),
            })
            prose_parts.append(
                f"{assertive} states {assertive_pct}% of claims as "
                f"definitive fact; {cautious} states {cautious_pct}%. "
                f"The certainty gap means a reader of {assertive} receives "
                f"more confidence than the evidence warrants compared "
                f"to {cautious}."
            )

    # ── Temporal ──
    if a_temp and b_temp and a_temp != b_temp:
        temp_implications = {
            "past": "grounds conclusions in historical data",
            "present": "describes current state",
            "future": "projects forward based on assumptions",
        }
        a_imp = temp_implications.get(a_temp, f"is {a_temp}-oriented")
        b_imp = temp_implications.get(b_temp, f"is {b_temp}-oriented")
        cards.append({
            "dimension": "temporal",
            "label": "Time horizon",
            "a_value": a_temp,
            "b_value": b_temp,
            "note": f"{a_name} {a_imp}; {b_name} {b_imp}.",
        })
        prose_parts.append(f"{a_name} {a_imp}; {b_name} {b_imp}.")

    # ── Closing: combined blind spot ──
    if shared_blind:
        perspective_desc = {
            "causes": "why things happen",
            "risks": "what could go wrong",
            "stakeholders": "who is affected",
            "trends": "what is changing",
            "uncertainty": "what is unknown",
        }
        blind_expanded = [perspective_desc.get(b, b) for b in shared_blind]
        shared_blind_note = {
            "dimensions": list(shared_blind),
            "consequence": (
                f"A reader of both would still not know: "
                f"{'; '.join(blind_expanded)}."
            ),
        }
        prose_parts.append(
            f"Neither document has detected markers for "
            f"{', '.join(shared_blind)}. A reader of both would still "
            f"not know: {'; '.join(blind_expanded)}."
        )

    prose = " ".join(prose_parts) if prose_parts else None
    if not (headline or cards or only_a_blind or only_b_blind
            or shared_blind_note):
        return None

    return {
        "headline": headline,
        "cards": cards,
        "unique_omissions": {
            "a_omits": sorted(only_a_blind) if only_a_blind else [],
            "b_omits": sorted(only_b_blind) if only_b_blind else [],
            "a_name": a_name,
            "b_name": b_name,
        },
        "shared_blind_note": shared_blind_note,
        "prose": prose,
    }


def _build_structural_framing_diff(
    a_name, a, b_name, b,
    shared_blind, only_a_blind, only_b_blind,
):
    """Legacy wrapper: return the framing comparison as the single
    prose paragraph string older saved-JSON files and existing
    tests expect. New consumers should call
    _build_structural_framing_data() directly for the structured
    form."""
    data = _build_structural_framing_data(
        a_name, a, b_name, b,
        shared_blind, only_a_blind, only_b_blind,
    )
    return data["prose"] if data else None


def _find_sentence_for_value(val, claims):
    """Find the claim sentence containing this value."""
    for c in claims.get("claims", []):
        for n in c.get("numbers", []):
            cleaned = n.strip().lstrip("$~").rstrip("%xXBMK").replace(",", "").strip()
            if cleaned == val:
                sent = c.get("sentence", "")
                return sent[:100] if sent else ""
    return ""


def compare_responses(responses):
    """Analyze and compare responses from multiple models.

    Synchronous batch entry point. Calls analyze_model for each
    response in parallel, then build_cross_model_comparison.

    Args:
        responses: dict of {model_name: response_text}

    Returns comparison dict with per-model analysis and cross-model insights.
    """
    if len(responses) < 2:
        return None

    # Analyze both models in parallel (Source Network is the bottleneck)
    models = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(analyze_model, name, text): name
            for name, text in responses.items()
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                models[name] = future.result()
            except Exception as e:
                # Tolerated by design: per-model analyze_model
                # failures MUST NOT block the cross-model comparison.
                # The downstream `if len(models) < 2: return None`
                # check enforces the comparison contract: at least
                # two models must analyze successfully or the
                # comparison is skipped at the caller. Log to stderr
                # so the operator can investigate without breaking
                # the JSON-RPC channel on stdout.
                import sys
                print(
                    f"[comparison.compare_responses] "
                    f"analyze_model failed for {name}: "
                    f"{type(e).__name__}: {e}",
                    file=sys.stderr,
                )

    if len(models) < 2:
        return None

    return build_cross_model_comparison(models)


# ================================================================
# Example topics (static, no API calls)
# ================================================================

def get_comparison_examples():
    """Return static example topics. No API calls. No cost."""
    return [
        {
            "id": "semiconductor",
            "topic": "Global semiconductor market size, growth, and key players in 2025",
            "description": "Financial/market topic with specific numbers",
        },
        {
            "id": "climate",
            "topic": "Current state of climate change: temperature rise, CO2 levels, and ice loss statistics",
            "description": "Scientific topic with verifiable data",
        },
        {
            "id": "ai",
            "topic": "State of AI adoption in enterprise: spending, deployment rates, and ROI statistics",
            "description": "Technology topic with industry projections",
        },
    ]


# ================================================================
# Example document pairs (static, no API calls)
# ================================================================
#
# These pairs let users demo documents-mode without pasting anything.
# Each pair is engineered to surface a distinct analytical signal:
#
#   1. Numerical disagreement: same topic, conflicting numbers,
#      to demonstrate the cross-model verification feature
#   2. Voice / framing contrast: same event, opposite tone,
#      to demonstrate how omissions differ between PR and analysis
#   3. Stakeholder coverage gaps: same regulation, opposite sides,
#      to demonstrate the shared blind spots feature
#
# The texts are deliberately fictional (made-up companies, made-up
# numbers) so we are not putting words in real organizations' mouths.
# They are written in the same register as the AI-generated content
# Frame Check is built to analyze.

def get_document_comparison_examples():
    """Return preset document pairs for the documents mode demo.

    Each pair is well under MAX_DOC_CHARS so the textareas validate
    without truncation. Hooks summarize the analytical insight users
    will see after running the comparison.
    """
    return [
        {
            "id": "ev-forecasts",
            "title": "Bullish vs cautious EV market forecast",
            "description": "Same market, two analyst takes, different numbers",
            "hook": (
                "Numerical disagreements jump out: market size, growth "
                "rate, battery prices, and market share all conflict. "
                "Voice and temporal framing diverge."
            ),
            "doc_a_label": "Bullish forecast",
            "doc_a": (
                "## Electric Vehicle Market 2025: Acceleration\n\n"
                "The global electric vehicle market reached $623 billion "
                "in 2024, growing at 28% year over year. Battery prices "
                "declined to $89 per kWh, an 18% drop from 2023. Tesla, "
                "BYD, and Volkswagen together captured 47% of global "
                "sales.\n\n"
                "Charging infrastructure expanded dramatically: public "
                "charging points increased to 4.2 million worldwide, up "
                "from 2.7 million in 2023. Government incentives in 27 "
                "countries directly subsidize EV purchases. Goldman Sachs "
                "projects the market will reach $1.1 trillion by 2028, "
                "implying continued 15% annual growth.\n\n"
                "Adoption is accelerating across every major segment. "
                "Commercial fleets transitioned 23% of new purchases to "
                "electric models. Two-wheeler electrification reached "
                "67% in Asian markets."
            ),
            "doc_b_label": "Cautious forecast",
            "doc_b": (
                "## Electric Vehicle Market 2025: Headwinds\n\n"
                "Electric vehicle sales slowed in late 2024 as growth "
                "fell from prior peaks. The global market reached "
                "approximately $580 billion, growing at 12% year over "
                "year, well below the 28% rate analysts had expected. "
                "Battery prices declined modestly to $103 per kWh, but "
                "the pace of cost reductions has flattened.\n\n"
                "Tesla, BYD, and Volkswagen jointly held 39% of global "
                "sales as Chinese rivals captured share. Charging "
                "infrastructure remains uneven: public charging points "
                "reached 3.6 million globally, but half of new "
                "installations cluster in China and the EU. Several "
                "governments scaled back purchase incentives due to "
                "budget pressures.\n\n"
                "McKinsey estimates the market will reach roughly $850 "
                "billion by 2028, representing slower growth of 8 to 10 "
                "percent annually. Used EV depreciation accelerated 22% "
                "in 2024."
            ),
        },
        {
            "id": "earnings-takes",
            "title": "Press release vs analyst note",
            "description": "Same quarter, opposite framing: what gets left out",
            "hook": (
                "Both texts use the same headline numbers, but the "
                "analyst note adds decelerating growth, a workforce "
                "reduction, and competitive pressure. Voice analysis "
                "catches the PR vs analytical tone."
            ),
            "doc_a_label": "Company release",
            "doc_a": (
                "## NovaTech Q4 2024 Highlights\n\n"
                "NovaTech delivered exceptional Q4 results, with revenue "
                "reaching $4.27 billion, a 31% increase year over year. "
                "Cloud Platform sales grew 42% to $1.83 billion, our "
                "fastest-growing segment ever. Operating margin expanded "
                "to 27.4%, up 220 basis points. Net income reached $812 "
                "million.\n\n"
                "Customer wins this quarter included three Fortune 100 "
                "enterprises across financial services, healthcare, and "
                "retail. Our AI Assistant product crossed 12 million "
                "active users, adding 4.1 million in Q4 alone, an "
                "extraordinary pace.\n\n"
                "Looking ahead, we are guiding full-year 2025 revenue of "
                "$19.5 to $20.2 billion, reflecting strong momentum "
                "across all segments and continued execution on our "
                "long-term strategy."
            ),
            "doc_b_label": "Analyst note",
            "doc_b": (
                "## NovaTech Q4 2024: A Closer Look\n\n"
                "NovaTech reported Q4 revenue of $4.27 billion, hitting "
                "consensus but marking the third straight quarter of "
                "decelerating growth. The 31% year-over-year increase "
                "compares with 38% in Q3 and 47% in Q1. Cloud Platform "
                "growth of 42% remains strong but trails the 51% "
                "reported by larger rival Apex Cloud.\n\n"
                "Operating margin of 27.4% reflects aggressive cost "
                "cuts that included a 6% workforce reduction in October. "
                "AI Assistant active users reached 12 million, but the "
                "company did not disclose paying users or revenue "
                "contribution from this product, which we estimate at "
                "less than 4% of total.\n\n"
                "Full-year 2025 guidance of $19.5 to $20.2 billion "
                "implies 18% growth at the midpoint, below buy-side "
                "expectations of $20.5 billion. Management did not "
                "address competitive pressure from Apex and DataPrime."
            ),
        },
        {
            "id": "privacy-perspectives",
            "title": "Industry vs consumer-advocate perspective",
            "description": "Same regulation, opposite sides, shared blind spots",
            "hook": (
                "Each side cites different statistics for the same "
                "policy. The blind-spots view shows what each text "
                "leaves out: industry omits consumer harms, advocates "
                "omit small-business burden."
            ),
            "doc_a_label": "Industry view",
            "doc_a": (
                "## Impact of New Data Privacy Regulations\n\n"
                "The proposed federal data privacy framework would "
                "impose significant compliance costs on US businesses, "
                "with industry estimates ranging from $14.5 billion to "
                "$23.8 billion annually. Companies would face mandatory "
                "data audits every 12 months, breach notification "
                "within 72 hours, and individual data deletion rights "
                "that average 240 hours of engineering work per "
                "request.\n\n"
                "Small businesses with fewer than 500 employees face "
                "the greatest burden: compliance costs are projected to "
                "consume 4.2% of revenue for affected firms. The "
                "Chamber of Commerce estimates 38% of small tech "
                "companies would be unable to fully comply within the "
                "proposed 18-month timeline, putting up to 220,000 jobs "
                "at risk.\n\n"
                "International coordination remains weak. The framework "
                "diverges from EU GDPR in three significant ways, "
                "creating dual-compliance burden for any business "
                "serving both markets."
            ),
            "doc_b_label": "Consumer view",
            "doc_b": (
                "## Why Americans Need Data Privacy Protection\n\n"
                "US consumers lose an estimated $58 billion annually to "
                "data breaches, identity theft, and unauthorized data "
                "sales. The proposed federal data privacy framework "
                "would establish basic rights that 47 other countries "
                "already provide, including the right to know what data "
                "companies collect, the right to delete it, and the "
                "right to refuse sale of personal information.\n\n"
                "Currently, 78% of Americans report feeling that they "
                "have little control over how companies use their data. "
                "Only 9% say they fully understand what they are "
                "agreeing to in privacy policies. The framework would "
                "require plain-language disclosures and create real "
                "penalties for violations, with fines of up to 4% of "
                "global revenue for systematic abuse.\n\n"
                "The Chamber of Commerce opposes the framework, "
                "arguing compliance costs are excessive. Independent "
                "analysis suggests these estimates are inflated 3 to 5 "
                "times by including normal business operations as "
                "compliance costs."
            ),
        },
    ]
