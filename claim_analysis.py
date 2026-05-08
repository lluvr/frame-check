"""
Per-claim analysis layer.

Extracts individual numerical claims from the document and analyzes
each one for hedging language, confidence framing, and risk indicators.
Works WITHOUT source material. Zero LLM cost.

The core insight this surfaces: AI presents unsourced and verified
claims with identical confidence. This layer makes that visible
by tagging each claim as hedged or unhedged, then computing
confidence uniformity across the document.
"""

import re
from clarethium_measure import (
    extract_numerical_claims,
    extract_numbers_for_matching,
    _filter_numbers,
)


# Hedging patterns: language that QUALIFIES a claim (admits imprecision)
# NOT lower bounds ("exceeded", "over") which are definitive directional claims
HEDGE_RE = re.compile(
    r'\b('
    r'approximately|roughly|about|around|nearly|estimated|'
    r'may\b|might|could|possibly|potentially|likely|unlikely|'
    r'suggest(?:s|ed|ing)?|appear(?:s|ed)?|seem(?:s|ed)?|indicat(?:es?|ed|ing)|'
    r'tends?\s+to|on\s+average|typically|generally|often|sometimes|'
    r'up\s+to|as\s+(?:many|much)\s+as'
    r')\b', re.IGNORECASE
)

# Strong assertion patterns: language that states definitively
ASSERT_RE = re.compile(
    r'\b('
    r'clearly|definitely|certainly|undoubtedly|obviously|'
    r'demonstrat(?:es?|ed)|proves?|confirms?|establish(?:es|ed)|ensures?|'
    r'significant(?:ly)?|dramatic(?:ally)?|substantial(?:ly)?|overwhelmingly|'
    r'dominat(?:es?|ed|ing)|maintain(?:s|ed)|accounted?\s+for|reached|'
    r'represented|comprised|exceeded|surpassed'
    r')\b', re.IGNORECASE
)

# Prediction markers: claims about the future
PREDICTION_RE = re.compile(
    r'\b('
    r'projected|forecast|expected|anticipated|estimated|predicted|'
    r'projects|forecasts|expects|anticipates|estimates|predicts|'
    r'will\s+(?:reach|grow|decline|increase|exceed)|'
    r'(?:is|are)\s+(?:projected|expected|forecast|anticipated)\s+to|'
    r'management\s+(?:projects|expects|forecasts|anticipates|guides)|'
    r'guidance\s+(?:of|for|is|at)|'
    r'by\s+20[2-9]\d'
    r')\b', re.IGNORECASE
)


# Candidate-hedge patterns: softer or more academic qualifying language
# that the primary HEDGE_RE does not recognize. Same construct-honest
# treatment as framing.py::CANDIDATE_PATTERNS (coverage under-detection)
# and framing.py::EPISTEMIC_CANDIDATE_ATTRIBUTION (sourcing under-detection).
# Fires only for claims classified as stated_as_fact or prediction by the
# primary; each candidate match surfaces a hedging style the reader may
# recognize that the primary regex missed.
#
# Conservative by design: false positives are acceptable because each
# candidate is surfaced with explicit caveat, not as a reclassification.
# The claim's primary framing ("stated_as_fact"/"prediction"/"hedged")
# remains the authoritative signal; candidate_hedge_marker is a reader-
# inspectable hint, not a re-categorization.
CANDIDATE_HEDGE_RE = re.compile(
    r'\b('
    # Academic/theoretical hedges
    r'in\s+principle|in\s+theory|conceivably|perhaps\b|'
    r'tentative(?:ly)?|preliminary|inconclusive|'
    # Conditional hedges
    r'subject\s+to|conditional\s+(?:on|upon)|depending\s+on|'
    r'provided\s+that|under\s+certain\s+conditions|'
    r'assuming\s+that|if\s+(?:correct|accurate|right)|'
    # Scholarly-soft hedges
    r'arguably|one\s+might\s+(?:argue|say|suggest|note)|'
    r'one\s+could\s+(?:say|argue|suggest)|'
    r'broadly\s+speaking|loosely\s+speaking|'
    r'in\s+a\s+sense|it\s+is\s+fair\s+to\s+say|'
    # Range/interval hedges (admit imprecision without using the primary words)
    r'somewhere\s+between|ranges?\s+from\s+|on\s+the\s+order\s+of|'
    r'give\s+or\s+take|rough\s+estimate|ballpark|'
    # Caveat language
    r'with\s+(?:the\s+)?caveat(?:s)?|caveats?\s+aside|'
    r'that\s+said|notwithstanding|all\s+things\s+considered'
    r')\b', re.IGNORECASE
)


def analyze_claims(doc_text):
    """Extract and analyze individual numerical claims.

    Returns a dict with:
        claims: list of per-claim analysis dicts
        confidence_uniformity: fraction of claims that are unhedged (0.0-1.0)
        risk_indicators: structural risk factors detected
        risk_level: "low" | "moderate" | "high"
        risk_explanation: human-readable risk assessment
    """
    raw_claims = extract_numerical_claims(doc_text)

    # Filter extraction artifacts: "000 years" from "110,000 years" where
    # the duration pattern matches the post-comma portion of large numbers
    raw_claims = [
        c for c in raw_claims
        if not all(
            n.get("raw", "").strip().startswith("000")
            for n in c.get("numbers", [])
        )
    ]

    # Also extract individual numbers to catch bullets and short lines
    # that extract_numerical_claims misses (its 30-char sentence filter
    # drops bullet points like "- Revenue: $500 billion")
    all_numbers = _filter_numbers(extract_numbers_for_matching(doc_text), doc_text)

    # Find numbers not covered by any extracted claim sentence.
    # Normalize values: extract_numerical_claims uses float,
    # extract_numbers_for_matching uses string. Compare as stripped strings.
    claimed_values = set()
    for rc in raw_claims:
        for n in rc.get("numbers", []):
            v = n.get("value", "")
            # Normalize: float 30.0 -> "30", string "30" -> "30"
            try:
                v = str(int(float(v))) if float(v) == int(float(v)) else str(float(v))
            except (ValueError, TypeError):
                v = str(v)
            claimed_values.add(v)

    uncovered_numbers = []
    for n in all_numbers:
        v = n["value"]
        try:
            v_norm = str(int(float(v))) if float(v) == int(float(v)) else str(float(v))
        except (ValueError, TypeError):
            v_norm = str(v)
        if v_norm not in claimed_values:
            # Skip range upper bounds: if this number appears right after
            # a dash in the context (e.g., "2.65" in "$2.55-2.65"), it's
            # the upper bound of a range already covered by another number
            ctx = n.get("context", "")
            raw = n.get("raw", n["value"])
            is_range_bound = bool(re.search(
                r'\d+(?:\.\d+)?\s*[-\u2013]\s*' + re.escape(raw),
                ctx
            ))
            if is_range_bound:
                continue
            uncovered_numbers.append(n)
            claimed_values.add(v_norm)  # Prevent duplicates within uncovered

    # Build synthetic claims from uncovered numbers (bullets, short lines).
    # Use the raw text as a tighter context to avoid hedging false positives
    # from neighboring bullets in the 100-char context window.
    for num in uncovered_numbers:
        # Extract just the line containing this number for hedging analysis
        context = num.get("context", num["value"])
        # Trim context to the segment around the number (reduce bleed from neighbors)
        raw_val = num.get("raw", num["value"])
        idx = context.find(raw_val)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(context), idx + len(raw_val) + 30)
            tight_context = context[start:end].strip()
        else:
            tight_context = context

        raw_claims.append({
            "sentence": tight_context,
            "heading": "",
            "numbers": [{"raw": num["raw"], "type": num["type"], "value": num["value"]}],
            "position": -1,
            "from_bullet": True,
        })

    if not raw_claims:
        return {
            "claims": [],
            "confidence_uniformity": None,
            "hedged_count": 0,
            "unhedged_count": 0,
            "prediction_count": 0,
            "high_precision_count": 0,
            "total_claims": 0,
            "risk_indicators": [],
            "risk_level": "info",
            "risk_explanation": "No numerical claims detected.",
        }

    claims = []
    hedged_count = 0
    unhedged_count = 0
    prediction_count = 0
    high_precision_count = 0
    # Per-num-type aggregate for the Frame Check Corpus Tier A
    # `claims.by_type` field. Computed here using the RAW number
    # dicts (which still carry the `type` field) because the
    # per-claim `numbers` list gets string-converted later in this
    # loop and the type information is lost.
    claims_by_type = {
        "percentage": 0, "dollar": 0, "multiplier": 0,
        "decimal": 0, "integer": 0,
    }

    for rc in raw_claims:
        sent = rc["sentence"]
        heading = rc.get("heading", "")
        is_bullet = rc.get("from_bullet", False)

        # Hedging analysis
        # Skip for synthetic bullet claims: the context window bleeds
        # across bullet boundaries, causing false positives
        if is_bullet:
            hedge_matches = []
            assert_matches = []
            prediction_matches = []
        else:
            hedge_matches = HEDGE_RE.findall(sent)
            assert_matches = ASSERT_RE.findall(sent)
            prediction_matches = PREDICTION_RE.findall(sent)

        is_hedged = len(hedge_matches) > 0
        is_prediction = len(prediction_matches) > 0

        if is_hedged:
            hedged_count += 1
            framing = "hedged"
        elif is_prediction:
            prediction_count += 1
            framing = "prediction"
        else:
            unhedged_count += 1
            framing = "stated_as_fact"

        # Candidate-hedge surfacing: if the primary classified this claim
        # as stated_as_fact or prediction (not hedged), check whether a
        # softer/academic hedge form fires. If so, surface it on the
        # claim dict with a caveat. Primary framing is unchanged; the
        # candidate field is reader-inspectable hint for under-detection.
        candidate_hedge = None
        if not is_hedged and not is_bullet:
            cm = CANDIDATE_HEDGE_RE.search(sent)
            if cm is not None:
                candidate_hedge = re.sub(r'\s+', ' ', cm.group(0).strip().lower())

        # Precision analysis: decimal places suggest fabrication risk
        numbers = rc.get("numbers", [])
        has_high_precision = False
        for n in numbers:
            raw = n.get("raw", "")
            # Check for suspicious decimal precision: $384.7, 24.3%, 38.6%
            if re.search(r'\d+\.\d{1,2}[%$BbMm]', raw) or re.search(r'\$\d+\.\d', raw):
                has_high_precision = True
                break
            # Phase 1.5: aggregate the num_type histogram while
            # the dicts are still in their raw form. The cleaned
            # display strings replace the dicts later in this
            # loop, so this is the only place we have access to
            # the type field per claim.
        for n in numbers:
            if isinstance(n, dict):
                t = n.get("type")
                # Map upstream extractor type names that don't
                # match the spec's 5-value enum. The upstream
                # extract_numerical_claims emits "entity_count"
                # for things like "164,000 employees"; the spec
                # bucket for integer-valued counts is "integer".
                if t == "entity_count":
                    t = "integer"
                if t in claims_by_type:
                    claims_by_type[t] += 1

        if has_high_precision:
            high_precision_count += 1

        # Build clean display values
        num_strs = []
        for n in numbers[:3]:
            raw = n.get("raw", str(n.get("value", "")))
            # Clean up truncated suffixes: "$2.47 b" -> "$2.47B"
            raw = re.sub(r'\s+([bBmMkKtT])$', lambda m: m.group(1).upper(), raw)
            # "$2.47 bi" -> "$2.47B"
            raw = re.sub(r'\s+(?:bi|mi|tr)$', lambda m: m.group(0).strip()[0].upper(), raw)
            num_strs.append(raw)

        claim_entry = {
            "sentence": sent,
            "heading": heading,
            "numbers": num_strs,
            "framing": framing,
            "hedge_words": [w.lower() for w in hedge_matches],
            "assert_words": [w.lower() for w in assert_matches],
            "is_prediction": is_prediction,
            "has_high_precision": has_high_precision,
        }
        if candidate_hedge is not None:
            # Surface the candidate-hedge marker on the claim. Primary
            # framing is unchanged; candidate_hedge_marker is a reader-
            # inspectable under-detection hint.
            claim_entry["candidate_hedge_marker"] = candidate_hedge
            claim_entry["candidate_hedge_caveat"] = (
                "Candidate-hedge pattern fired; primary hedge detector "
                "did not. Reader judges whether this claim is "
                "substantively hedged (academic/conditional forms the "
                "primary regex does not recognize)."
            )
        claims.append(claim_entry)

    total = len(claims)

    # Confidence uniformity: fraction of claims that are unhedged
    # Higher = more uniform confidence = higher risk (no distinction between
    # verified and potentially fabricated claims)
    confidence_uniformity = unhedged_count / total if total > 0 else 0.0

    # Risk indicators
    risk_indicators = []
    words = len(re.findall(r'\b\w+\b', doc_text))
    claims_per_kw = total / max(words / 1000, 0.1)

    if claims_per_kw > 30:
        risk_indicators.append(
            f"Very high claim density: {claims_per_kw:.0f} numerical claims "
            f"per 1,000 words"
        )

    if confidence_uniformity > 0.85 and total >= 5:
        risk_indicators.append(
            f"{unhedged_count} of {total} claims stated as definitive fact "
            "with no qualifying language detected"
        )

    if high_precision_count > total * 0.3:
        risk_indicators.append(
            f"{high_precision_count} claims use decimal precision "
            "(e.g., $384.7B, 24.3%) which may be false precision"
        )

    if prediction_count > 0:
        risk_indicators.append(
            f"{prediction_count} claim{'s' if prediction_count != 1 else ''} "
            "about the future (projections, not verifiable facts)"
        )

    # Risk level
    if len(risk_indicators) >= 3:
        risk_level = "high"
    elif len(risk_indicators) >= 1:
        risk_level = "moderate"
    else:
        risk_level = "low"

    # Risk explanation (the insight, not just data)
    if confidence_uniformity > 0.85 and total >= 5:
        risk_explanation = (
            f"This document presents {unhedged_count} of {total} numerical "
            f"claims as definitive fact. Only {hedged_count} use any qualifying "
            f"language. The writing does not distinguish between claims the AI "
            f"retrieved from knowledge and claims it may have generated. "
            f"Without source material, none of these claims can be verified."
        )
    elif total >= 3:
        risk_explanation = (
            f"{total} numerical claims detected. "
            f"{unhedged_count} stated as fact, "
            f"{hedged_count} hedged"
            + (f", {prediction_count} predictions" if prediction_count else "")
            + ". Provide source material to verify which claims are grounded."
        )
    else:
        risk_explanation = (
            f"{total} numerical claim{'s' if total != 1 else ''} detected. "
            "Low claim density."
        )

    return {
        "claims": claims,
        "confidence_uniformity": round(confidence_uniformity, 3),
        "hedged_count": hedged_count,
        "unhedged_count": unhedged_count,
        "prediction_count": prediction_count,
        "high_precision_count": high_precision_count,
        "total_claims": total,
        # Candidate-hedge aggregate: count of claims where primary
        # framing is stated_as_fact or prediction BUT candidate-hedge
        # pattern fires. Reader-inspectable under-detection signal.
        # Operationalizes the under-detection posture for the claims
        # signal, completing the trilogy with coverage (Phase A) and
        # epistemic (Phase A-extended).
        "candidate_hedge_count": sum(
            1 for c in claims if c.get("candidate_hedge_marker") is not None
        ),
        # Per-num-type histogram for the Frame Check Corpus Tier A
        # `claims.by_type` field.
        "claims_by_type": claims_by_type,
        "risk_indicators": risk_indicators,
        "risk_level": risk_level,
        "risk_explanation": risk_explanation,
    }
