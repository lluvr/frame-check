"""Analysis manifest builder.

Provenance record attached to every Frame Check analysis (single-doc
/check, document comparison /compare, live SSE flow, persisted saved
view, and MCP JSON-RPC response). The manifest answers the question
"what actually ran and against what calibration?" in a single
structured block, so a reader, a researcher, or a hostile reviewer
can trace any number on the page back to the substrate version that
produced it.

Design constraints:

  - Plain dict output. Survives JSON round-trip without custom
    encoders, persists into saved_analyses / saved_compare files
    unchanged, ships through SSE and JSON-RPC without dataclass
    serialization issues.

  - No synthesis. Every field is sourced from a primitive that
    already exists in the pipeline. The manifest exposes the
    primitives; it never invents a number.

  - Layers that did not run are emitted EXPLICITLY with a reason,
    not omitted. Silent omission is the failure mode this module
    exists to prevent.

  - Calibration backing is named for every provider F1 score
    surfaced anywhere on the result page. "F1 0.85" without a
    pointer to the corpus that measured it is half a claim.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from version import (
    FRAME_CHECK_VERSION,
    PIPELINE_VERSION,
    SCHEMA_VERSION,
)


# Methodology + calibration link targets. Surfaced in the manifest so
# every layer reference resolves to a documented description rather
# than a bare label. Centralised here so a future docs reorg is a
# one-place edit.
_METHODOLOGY_URL = "/corpus/methodology/"
_CALIBRATION_URL = "/corpus/calibration/"
_LIBRARY_URL = "/corpus/library/"


def _utc_iso_now() -> str:
    """ISO-8601 timestamp in UTC for the analysis_run_at field.

    Manifest timestamps are wall-clock attribution ("when did this
    analysis run?"), not duration measurements; ordinary time-of-day
    accuracy is sufficient. UTC is required so a saved analysis
    shared across timezones renders consistently.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _frame_library_version() -> str:
    """Read the frame library VERSION marker.

    Mirrors app._library_version() but lives here so the manifest
    builder is callable from contexts that have not imported app
    (tests, the MCP wire-up). Falls back to "0.0.0" if the marker is
    missing rather than raising; an absent marker should surface as
    visible "0.0.0" in the manifest, not a 500 on /check.
    """
    try:
        p = Path(__file__).resolve().parent / "data" / "frame_library" / "VERSION"
        return p.read_text(encoding="utf-8").strip() if p.is_file() else "0.0.0"
    except OSError:
        return "0.0.0"


# Calibration corpus reference for the manifest's sn_corpus block.
# Loaded from calibration/source_network_corpus.yaml at module import
# (the file is a versioned reference artifact that changes only on
# explicit calibration sweeps, so once-at-startup parsing is fine
# and avoids per-request YAML latency). Values flow from the YAML
# itself: version comes from the top-level `version:` key, seeded_at
# from `seeded_at:`, size from a count of claim entries across
# provider sections.
#
# Pre-fix the dict was hardcoded with version="0.1" / size=33 /
# seeded_at="2026-04-16". When the operator expanded the corpus to
# v1.0, the manifest would have kept claiming v0.1 unless someone
# remembered to update the constant. The manifest is the construct-
# honesty receipt; it must not be capable of lying about its own
# substrate. Sourcing from the YAML closes that drift class.
#
# Falls back to a sentinel "unknown" reference if the file is
# missing or unparseable so the manifest stays well-formed under
# stripped deploys (lift packages, MCP-only installs that ship
# without the calibration directory). Surface "unknown" reads as
# explicit absence rather than a stale claim.

def _load_calibration_corpus_meta() -> dict:
    """Read corpus identity from calibration/source_network_corpus.yaml.

    Returns a manifest-shaped dict with the same keys hardcoded
    pre-fix. On any read or parse failure, returns the fallback
    sentinel so the manifest builders never raise. Module-level
    side-effect-only function: cached in _CALIBRATION_CORPUS at
    import time.
    """
    fallback = {
        "name": "Frame Check Source Network Calibration Corpus",
        "version": "unknown",
        "size": 0,
        "seeded_at": "unknown",
        "url": _CALIBRATION_URL,
    }
    try:
        p = (
            Path(__file__).resolve().parent
            / "calibration"
            / "source_network_corpus.yaml"
        )
        if not p.is_file():
            return fallback
        text = p.read_text(encoding="utf-8")
    except OSError:
        return fallback

    # Top-level scalar parse without a yaml dependency: scan for
    # `version:` and `seeded_at:` lines BEFORE the first provider
    # section header. Keeps the import surface minimal (manifest is
    # imported by both web and MCP flows; we do not want a yaml
    # import at request-handler init time).
    import re as _re
    version = "unknown"
    seeded_at = "unknown"
    for line in text.splitlines():
        # Stop at the first nested key (provider section). The
        # top-level scalars `version:` and `seeded_at:` sit before
        # any provider block in v0.1.
        if _re.match(r"^[A-Za-z_]+:\s*$", line) and not line.startswith(
            ("version:", "seeded_at:", "seed_author:")
        ):
            break
        m = _re.match(r"^version:\s*\"?([^\"\n]+)\"?\s*$", line)
        if m:
            version = m.group(1).strip()
        m = _re.match(r"^seeded_at:\s*\"?([^\"\n]+)\"?\s*$", line)
        if m:
            seeded_at = m.group(1).strip()

    # Count claim entries across all provider sections. The YAML
    # uses `- id: ...` for each claim under `claims:`. Counting
    # `- id:` line-prefix occurrences is exact for the v0.1 schema
    # and survives ordering changes within a claim block.
    size = sum(
        1 for line in text.splitlines()
        if _re.match(r"^\s*-\s+id:", line)
    )

    return {
        "name": "Frame Check Source Network Calibration Corpus",
        "version": version,
        "size": size,
        "seeded_at": seeded_at,
        "url": _CALIBRATION_URL,
    }


_CALIBRATION_CORPUS = _load_calibration_corpus_meta()


def _build_sn_provider_block(
    sn_results: list,
    reliability_tiers: dict,
    source_name_to_provider_key: dict,
) -> list[dict]:
    """Per-provider provenance block, sourced from the SN result list.

    For every provider that returned at least one verified or close
    match in this analysis, emit one entry naming the provider, its
    calibrated F1 + tier + claims_tested + run_date from the
    reliability_tiers table loaded at app startup, and the count of
    claims this analysis verified through it.

    Mirrors _aggregate_verified_providers' contract but adds the
    calibration-row fields (claims_tested, run_date) so the manifest
    is self-describing: a reader who has never opened the calibration
    page sees inline "F1 0.87 measured on 5 claims, 2026-04-17" and
    knows what backs the number.

    Providers with no reliability_tiers row contribute an entry with
    f1=None, tier="uncalibrated", and claims_tested/run_date=None so
    the absence of calibration is visible rather than implied as
    "strong default".
    """
    by_name: dict[str, dict] = {}
    for r in sn_results or []:
        if isinstance(r, dict):
            verdict = r.get("verdict", "")
            best_source = r.get("best_source", "")
        else:
            verdict = getattr(r, "verdict", "")
            best_source = getattr(r, "best_source", "")
        if verdict not in ("verified", "close") or not best_source:
            continue
        prov_key = source_name_to_provider_key.get(best_source, "")
        tier_row = reliability_tiers.get(prov_key, {}) or {}
        if best_source not in by_name:
            by_name[best_source] = {
                "name": best_source,
                "provider_key": prov_key or None,
                "verified_count": 0,
                "tier": tier_row.get("tier", "uncalibrated"),
                "f1": tier_row.get("f1"),
                "precision": tier_row.get("precision"),
                "recall": tier_row.get("recall"),
                "calibration_claims_tested": tier_row.get("claims_tested"),
                "calibration_run_date": tier_row.get("run_date"),
            }
        by_name[best_source]["verified_count"] += 1
    # Sort: most-relied-upon provider first, then alphabetical so the
    # display order in the manifest is stable across runs with the
    # same input.
    return sorted(
        by_name.values(),
        key=lambda p: (-p["verified_count"], p["name"]),
    )


def _structural_substrate_layer() -> dict:
    """The always-on structural substrate layer.

    Frame Check's substrate (regex coverage detector, voice classifier,
    epistemic basis detector, claim extractor, temporal-orientation
    detector, frame_library suggester) runs on every analysis and is
    the deterministic ground floor of every result. It is named
    here as a single layer so the manifest does not enumerate the
    six sub-detectors as if each were independently optional; they
    are not.

    The "ran" flag is True by construction: a manifest is built only
    after the substrate has produced output. The detail string names
    the components so a reviewer can map the layer onto methodology
    sections without inferring.
    """
    return {
        "name": "structural_substrate",
        "label": "Structural substrate (regex + heuristic)",
        "ran": True,
        "detail": (
            "Coverage detector (5 perspectives), voice classifier, "
            "epistemic basis detector, claim extractor, temporal "
            "orientation, frame library suggester. Deterministic, "
            "no LLM."
        ),
        "see": _METHODOLOGY_URL,
    }


def _llm_call_entry(
    stage: str,
    provider: str,
    model: str,
    prompt_template: str,
    *,
    ran: bool,
    reason_skipped: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
) -> dict:
    """Standard shape for every LLM-call manifest entry.

    `stage` names the analysis stage ("ai_interpret", "compare_framing",
    "reframe", "topic_generation"). `provider` is the canonical
    enum-style key ("grok", "gemini"). `model` is the exact API model
    string the call used. `prompt_template` is a stable name+revision
    string ("ai-interpret/v1", "compare-framing/v3") that a reviewer
    can resolve to the prompt body in source.

    When ran is False, reason_skipped MUST be populated (the manifest
    contract: skipped layers are explicit). Token counts and cost are
    None when the call did not run; preserved as None in JSON so the
    distinction "ran with $0 cost" vs "did not run" remains
    legible.
    """
    return {
        "stage": stage,
        "provider": provider,
        "model": model,
        "prompt_template": prompt_template,
        "ran": ran,
        "reason_skipped": reason_skipped if not ran else None,
        "input_tokens": input_tokens if ran else None,
        "output_tokens": output_tokens if ran else None,
        "cost_usd": round(cost_usd, 6) if (ran and cost_usd is not None) else None,
    }


def build_check_manifest(
    *,
    sn_results: list,
    sn_status: str,
    sn_status_reason: str,
    reliability_tiers: dict,
    source_name_to_provider_key: dict,
    ai_interpret: Optional[dict] = None,
    v4_2_result: Optional[dict] = None,
    consistency_ran: bool = False,
) -> dict:
    """Build the manifest for a single-document /check analysis.

    Parameters are passed in rather than imported so the builder is
    callable from tests, MCP wire-up, and saved-view replay without
    pulling app.py at import time.

    `ai_interpret` is the post-call dict the /api/ai-interpret handler
    constructs (with provider, model, cost_usd, input_tokens,
    output_tokens, interpretation_unavailable). None means the AI
    pass was not run on this analysis (no session created, key not
    configured, or daily cap hit before submission).

    `v4_2_result` is the V4.2 LLM-judge output (None when V4.2 is
    not configured or the daily cap fired). When present, the
    manifest emits a v4_2_judge llm_call entry; when None, an entry
    with ran=False and a clear reason.

    `consistency_ran` is True when source_text was provided (the
    mathematical-consistency check needs source material to operate
    on; with no source, the check is silently no-op today).
    """
    layers_run: list[dict] = [_structural_substrate_layer()]
    layers_skipped: list[dict] = []
    llm_calls: list[dict] = []

    # Source Network layer.
    sn_layer = {
        "name": "source_network",
        "label": "Source Network verification",
        "ran": sn_status not in ("skipped", "unavailable"),
        "detail": (
            f"Status: {sn_status}. {sn_status_reason}"
            if sn_status_reason else f"Status: {sn_status}."
        ),
        "see": _CALIBRATION_URL,
    }
    if sn_layer["ran"]:
        layers_run.append(sn_layer)
    else:
        layers_skipped.append({
            "name": "source_network",
            "label": "Source Network verification",
            "reason": sn_status_reason or f"sn_status={sn_status}",
            "see": _CALIBRATION_URL,
        })

    # Mathematical consistency layer.
    if consistency_ran:
        layers_run.append({
            "name": "mathematical_consistency",
            "label": "Mathematical consistency check",
            "ran": True,
            "detail": "Cross-checked numerical claims against pasted source material.",
            "see": _METHODOLOGY_URL,
        })
    else:
        layers_skipped.append({
            "name": "mathematical_consistency",
            "label": "Mathematical consistency check",
            "reason": "No source material provided. The check requires a source text to compare claims against.",
            "see": _METHODOLOGY_URL,
        })

    # AI-assisted interpretation (Grok).
    if ai_interpret:
        if ai_interpret.get("interpretation_unavailable"):
            llm_calls.append(_llm_call_entry(
                stage="ai_interpret",
                provider=ai_interpret.get("provider") or "grok",
                model=ai_interpret.get("model") or "grok-4-1-fast",
                prompt_template="ai-interpret/v1",
                ran=False,
                reason_skipped="LLM call attempted but failed or returned empty; structural fallback used in its place.",
            ))
        else:
            llm_calls.append(_llm_call_entry(
                stage="ai_interpret",
                provider=ai_interpret.get("provider") or "grok",
                model=ai_interpret.get("model") or "grok-4-1-fast",
                prompt_template="ai-interpret/v1",
                ran=True,
                input_tokens=ai_interpret.get("input_tokens"),
                output_tokens=ai_interpret.get("output_tokens"),
                cost_usd=ai_interpret.get("cost_usd"),
            ))
    else:
        llm_calls.append(_llm_call_entry(
            stage="ai_interpret",
            provider="grok",
            model="grok-4-1-fast",
            prompt_template="ai-interpret/v1",
            ran=False,
            reason_skipped="Not invoked on this analysis (no AI session created, provider not configured, or daily cap hit before request).",
        ))

    # V4.2 LLM-judge frame analysis.
    if v4_2_result and isinstance(v4_2_result, dict) and v4_2_result.get("meta", {}).get("framing_engine") == "v4_2":
        meta = v4_2_result.get("meta", {})
        llm_calls.append(_llm_call_entry(
            stage="v4_2_judge",
            provider="grok",
            model=meta.get("model") or "grok-4-1-fast",
            prompt_template=f"v4_2-judge/{meta.get('contract_version', 'v1')}",
            ran=True,
            input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"),
            cost_usd=meta.get("cost_usd"),
        ))
    else:
        llm_calls.append(_llm_call_entry(
            stage="v4_2_judge",
            provider="grok",
            model="grok-4-1-fast",
            prompt_template="v4_2-judge/v1",
            ran=False,
            reason_skipped="V4.2 judge not run on this analysis (provider not configured, or daily cap hit, or analysis surface excludes V4.2).",
        ))

    sn_providers = _build_sn_provider_block(
        sn_results, reliability_tiers, source_name_to_provider_key,
    )

    return {
        "manifest_version": 1,
        "surface": "check",
        "framecheck_version": FRAME_CHECK_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "frame_library_version": _frame_library_version(),
        "analysis_run_at": _utc_iso_now(),
        "layers_run": layers_run,
        "layers_skipped": layers_skipped,
        "llm_calls": llm_calls,
        "sn_providers": sn_providers,
        "sn_corpus": _CALIBRATION_CORPUS,
        "links": {
            "methodology": _METHODOLOGY_URL,
            "calibration": _CALIBRATION_URL,
            "frame_library": _LIBRARY_URL,
        },
    }


def build_compare_manifest(
    *,
    mode: str,
    analyzed_models: dict,
    reliability_tiers: dict,
    source_name_to_provider_key: dict,
    framing_comparison_call: Optional[dict] = None,
    stability_call: Optional[dict] = None,
    topic_generation_calls: Optional[list[dict]] = None,
) -> dict:
    """Build the manifest for a /compare analysis.

    `analyzed_models` is the {name: analyze_model output} dict the
    SSE handler accumulates. The aggregated SN provider block reads
    each model's sn_results, merges, and sorts.

    `framing_comparison_call`, `stability_call`, and
    `topic_generation_calls` carry the per-call metadata the SSE
    handler captures from each Grok / Gemini invocation. None means
    the corresponding stage did not run on this comparison (mode
    branch, missing provider, daily cap, or operator-disabled topic
    mode).
    """
    layers_run: list[dict] = [_structural_substrate_layer()]
    layers_skipped: list[dict] = []
    llm_calls: list[dict] = []

    # Cross-model structural framing comparison is always run when
    # both models analyzed cleanly. Surface as its own layer so the
    # zero-LLM determinism is legible.
    layers_run.append({
        "name": "structural_framing_diff",
        "label": "Cross-document structural framing comparison",
        "ran": True,
        "detail": (
            "Per-dimension coverage / voice / temporal / claim-density "
            "diff between the two documents. Deterministic, no LLM."
        ),
        "see": _METHODOLOGY_URL,
    })

    # Source Network is run per-model (analyze_model verifies each
    # document independently). Aggregate provider data across both
    # models.
    aggregate_sn_results: list = []
    for _name, data in (analyzed_models or {}).items():
        if isinstance(data, dict):
            aggregate_sn_results.extend(data.get("sn_results") or [])
    if aggregate_sn_results:
        layers_run.append({
            "name": "source_network",
            "label": "Source Network verification (per-document)",
            "ran": True,
            "detail": "Up to 15 numerical claims per document checked against the calibrated provider set.",
            "see": _CALIBRATION_URL,
        })
    else:
        layers_skipped.append({
            "name": "source_network",
            "label": "Source Network verification",
            "reason": "No claims were forwarded to the Source Network on this comparison (zero-claim documents or provider unavailable).",
            "see": _CALIBRATION_URL,
        })

    # V4.2 judge is intentionally not run on the compare flow today.
    # Surface this as a labelled skipped layer so the absence is
    # explicit, matching the in-template disclaimer
    # (compare.html / compare_saved.html).
    layers_skipped.append({
        "name": "v4_2_judge",
        "label": "V4.2 LLM-judge frame analysis",
        "reason": "Per-document V4.2 verdicts are not run on the compare flow (cost trade-off). Run /check on a single document for V4.2 output.",
        "see": _METHODOLOGY_URL,
    })

    # Topic-mode generation calls (Gemini + Grok).
    #
    # Topic mode: emit one ran=True entry per generator with measured
    # tokens / cost. Reader sees both providers and the cost split.
    #
    # Documents mode: skip the LLM-call entries entirely; the absence
    # is named once at the layer level (layers_skipped below) rather
    # than as two always-skipped LLM rows. Pre-fix the manifest emitted
    # both gemini and grok topic_generation rows on every documents-
    # mode comparison, even though no generation runs in that mode;
    # readers consistently flagged this as visual noise on a surface
    # that's supposed to name what ran, not list every primitive that
    # could have run on a different code path.
    if mode == "topic" and topic_generation_calls:
        for entry in topic_generation_calls:
            llm_calls.append(_llm_call_entry(
                stage="topic_generation",
                provider=entry.get("provider", "unknown"),
                model=entry.get("model", "unknown"),
                prompt_template="topic-generation/v1",
                ran=True,
                input_tokens=entry.get("input_tokens"),
                output_tokens=entry.get("output_tokens"),
                cost_usd=entry.get("cost_usd"),
            ))
    elif mode == "documents":
        layers_skipped.append({
            "name": "topic_generation",
            "label": "Topic-mode response generation (Gemini + Grok)",
            "reason": "Documents mode: both inputs were user-pasted; no LLM generation runs on this path.",
            "see": _METHODOLOGY_URL,
        })

    # Cross-document framing comparison (Grok narrative + Question to
    # ask). Same single call, two labelled output sections.
    if framing_comparison_call and framing_comparison_call.get("ran"):
        llm_calls.append(_llm_call_entry(
            stage="compare_framing",
            provider=framing_comparison_call.get("provider", "grok"),
            model=framing_comparison_call.get("model", "grok-4-1-fast"),
            prompt_template="compare-framing/v3",
            ran=True,
            input_tokens=framing_comparison_call.get("input_tokens"),
            output_tokens=framing_comparison_call.get("output_tokens"),
            cost_usd=framing_comparison_call.get("cost_usd"),
        ))
    else:
        llm_calls.append(_llm_call_entry(
            stage="compare_framing",
            provider="grok",
            model="grok-4-1-fast",
            prompt_template="compare-framing/v3",
            ran=False,
            reason_skipped=(
                framing_comparison_call.get("reason_skipped")
                if framing_comparison_call
                else "Not invoked (provider not configured, daily cap, or call timed out)."
            ),
        ))

    # Stability check (topic mode only; regenerates each model's
    # response to diff numbers).
    if stability_call and stability_call.get("ran"):
        llm_calls.append(_llm_call_entry(
            stage="stability_check",
            provider=stability_call.get("provider", "grok"),
            model=stability_call.get("model", "grok-4-1-fast"),
            prompt_template="stability-check/v1",
            ran=True,
            input_tokens=stability_call.get("input_tokens"),
            output_tokens=stability_call.get("output_tokens"),
            cost_usd=stability_call.get("cost_usd"),
        ))
    elif mode == "documents":
        llm_calls.append(_llm_call_entry(
            stage="stability_check",
            provider="grok",
            model="grok-4-1-fast",
            prompt_template="stability-check/v1",
            ran=False,
            reason_skipped="Stability check is topic-mode only (regenerates the AI response to diff numbers; user-pasted documents have no regeneration target).",
        ))

    sn_providers = _build_sn_provider_block(
        aggregate_sn_results, reliability_tiers, source_name_to_provider_key,
    )

    return {
        "manifest_version": 1,
        "surface": "compare",
        "compare_mode": mode,
        "framecheck_version": FRAME_CHECK_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "frame_library_version": _frame_library_version(),
        "analysis_run_at": _utc_iso_now(),
        "layers_run": layers_run,
        "layers_skipped": layers_skipped,
        "llm_calls": llm_calls,
        "sn_providers": sn_providers,
        "sn_corpus": _CALIBRATION_CORPUS,
        "links": {
            "methodology": _METHODOLOGY_URL,
            "calibration": _CALIBRATION_URL,
            "frame_library": _LIBRARY_URL,
        },
    }
