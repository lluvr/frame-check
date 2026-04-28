# Track B Informal Reader-Aid Study v1

Minimum-viable protocol for extracting external signal on the Frame Check sovereignty claim: **does divergence output help thinkers see frames they were otherwise missing?** Sized for 4-8 hours of operator time, 5 participants, $0 cash. Designed to validate or falsify the load-bearing assumption in FRAME_DIVERGENCE_v1.md §3 before more internal polish compounds conviction-risk.

**Status:** v1, 2026-04-23 late evening. Executable artifact, not a pre-registration. Formal Track B per VALIDATION_PROGRAM.md remains the full-scope paid study on grant or BDFL override; this informal protocol produces the cheapest signal the operator can act on.
**Author:** Lovro Lucic.
**Context:** stress-test-surfaced highest-leverage next move. See SESSION_STATE.md 2026-04-23 late evening entry and the pattern break outlined in the frame-break stress test.

---

## 1. Research question

Does structural divergence output (catalog-anchored absent-frame suggestions with faithfulness disclosures) change how a thinker reads a specific document?

Secondary: does the effect differ across domain (finance, founder-decision, general)?

Tertiary: what specific frames do users find useful, confusing, or irrelevant in the divergence output?

## 2. Participants

### Selection criteria

5 participants, selected opportunistically from the operator's network. No formal recruitment; no honorarium (per STRATEGY §12 budget envelope). Participants must meet:

- **Substantive domain contact.** At least three must be active in one of the three STRATEGY §13 domains (finance/trading, founder-decisions, investment research). The remaining two can be general-interest readers.
- **Willingness to reflect aloud.** Participant agrees to verbalize reasoning during the session (think-aloud protocol). Quiet readers produce no signal.
- **Independent of Frame Check.** Participant has not co-authored, reviewed, or collaborated on Frame Check. They can be aware of the operator; they must not be entangled in the project.
- **No prior exposure to the divergence output.** First-time readers of Frame Check output.

### Sample size rationale

n=5 is not statistically powered. It is a qualitative-signal sample: five participants producing think-aloud reactions to the same stimulus produces strong pattern signal (repeating confusions, repeating insights, repeating rejections) well before sample-size arguments matter. If the signal is ambiguous at n=5, the outcome IS ambiguous signal, which is itself a finding.

Jakob Nielsen's classic usability finding (n=5 catches 85% of problems) applies to reactive measures; we are using it as a sufficiency heuristic, not a precision claim.

## 3. Stimulus

### Document selection

Use three documents from the existing corpus, one per participant (rotate):

1. **Finance/trading:** the four-LLM Bitcoin retirement example (`data/worked_examples/four-llms-on-bitcoin-retirement-2026.md`). Framing-rich, domain-relevant. Stimulus composed 2026-04-23 per commit `d2de4dd`; artifacts at `data/track_b_informal/stimulus_1_bitcoin/` (gitignored; operator reviews locally).
2. **Founder-decision:** operator selects from the four-LLM startup corpus. Rerun the stimulus composer with `--stimulus-path` and `--domain-hint=founder_decision`.
3. **General analytical:** operator selects a non-financial worked example with rich framing density (e.g., NVIDIA earnings framing analysis, a policy document, or a tech-science analytical piece). Rerun the composer with `--domain-hint=general` or the closest matching enumerated value.

### Divergence output

Stimulus composition lands via the CLI reference harness shipped commit `d2de4dd` (`fvs_eval/v4/track_b_stimulus_composer.py` or equivalent path). Per Contract §7.2 web-surface mode, the composer:

1. Runs one V4.2 `detect_framing_v4_2()` call on the stimulus document. V4.2 emits one-sentence reasoning for each frame including `exhibits=false` cases; that reasoning is the semantic `absence_basis` per Contract §4.2.
2. Runs one Grok call to select the top-K most domain-relevant absent frames and compose `domain_relevance_rationale` per selection.
3. Assembles a Contract-compliant `divergence` block (JSON) plus a participant-facing markdown handout plus a provenance README.

Non-prescription discipline per Contract §5.1 guarantee 5 is enforced three ways in the composer: selection prompt forbids "should / must / ought / recommend / needs to"; string lint catches violations post-response; handout language reinforces that absence is observation, not advice.

Per-stimulus cost: ~$0.009 (stimulus #1 actual). Three stimuli total: ~$0.03.

Each stimulus output carries:
- 3-4 `absent_frames` from the FVS library, domain-relevance filtered.
- Per absent frame: `frame_id`, `frame_title`, `absence_basis`, `domain_relevance_rationale`.
- The `faithfulness_note` from the envelope (verbatim).
- No prescriptive language (enforced by composer).

## 4. Session protocol

15 minutes per participant. 5 participants. Total session time: 75 minutes. Plus setup/analysis: 2-4 hours.

### Minute 0-2: orient

"I'm testing a tool that suggests frames a document might not have used. I'll show you a short document, then a list of suggested absent frames. Read the document first, then look at the suggestions, then tell me what you think out loud. There are no right answers; I want your actual reactions."

Do not explain Frame Check, the FVS library, construct honesty, or the empire context. The participant reads as a naive user.

### Minute 2-6: document read

Participant reads the document. Operator silent. No questions yet.

### Minute 6-7: record first impression

"Before you see the suggestions, in one sentence: what is this document about and how do you feel about it?"

Record verbatim. This anchors the reader's pre-divergence state.

### Minute 7-10: divergence exposure

Show the divergence output. Participant reads at their own pace. Operator silent.

### Minute 10-14: think-aloud + five questions

Ask, in order, allowing follow-ups but not leading:

1. "How, if at all, did your reading shift after seeing the suggestions?" (Neutral form; earlier draft "Does any of this change how you see the document?" was leading because it presupposes change is possible. The neutral form lets "no shift" be a valid answer without demand effect.)
2. "Which of these suggestions, if any, felt relevant to your reading?"
3. "Which felt irrelevant or confusing?"
4. "Did any suggestion feel like it was telling you what to think?"
5. "If you encountered this output on a real document you cared about, would you use it?"

Record verbatim. Probe on strong reactions; do not probe on lukewarm ones.

### Minute 14-15: exit

Thank the participant. Offer to share the results summary when complete. Note domain + first impression + five answers + any spontaneous reactions.

## 5. Analysis framework

After all five sessions, produce a single-page summary. For each question across participants:

- **Convergence:** repeated pattern across 3+ participants.
- **Divergence:** specific disagreement worth noting.
- **Surprise:** reactions the operator did not predict.

Focus specifically on four signals:

- **Signal A (validation):** at least 3 of 5 participants independently say divergence output changed how they see the document in a specific, identifiable way. Bonus if they cite a specific absent frame they found useful.
- **Signal B (null):** 4 of 5 participants say divergence output did not change their reading, or changed it only in a decorative way that they would not use in practice.
- **Signal C (prescription drift):** 2 or more participants describe the output as "telling me what to think" or "making recommendations." If this fires, the non-prescriptive rendering requirement (§4.5 of the Part 2 contract) is not landing with real users and requires redesign.
- **Signal D (domain split):** domain participants respond differently from general participants in a load-bearing way (e.g., finance participants find it useful, general participants do not, or vice versa). **Low-power caveat:** n=3 domain plus n=2 general is underpowered to resolve domain split robustly. If Signal D appears ambiguous at this n, it is under-powered rather than null; operator scales n or pre-commits to direction on judgment rather than reading signal from noise.

### Analysis caveats surfaced by stress-test (acknowledge in write-up, do not silently conflate)

- **Format-vs-content confound.** Rotation of 3 stimuli across 5 participants yields ~1-2 participants per stimulus. Signal A ("3 of 5 independently") tests FORMAT efficacy across participants, not content-per-stimulus. State this explicitly so analysis does not later conflate stimulus-specific signal with format-specific signal.
- **Framing-vocabulary pre-exposure.** Stimulus #1 (the four-LLM Bitcoin retirement worked example) is itself a framing-analysis document. Participants reading it encounter framing vocabulary before the divergence exposure at minute 7. The study tests output SHAPE not detector accuracy per §8, so this is not disqualifying; note the pre-exposure in analysis so that "participant said the suggestions were familiar" is not mis-read as a learning or signal-interference effect. Stimuli #2 and #3 (non-meta domain documents) provide the clean-read comparison.
- **Leading-question scrub.** Q1 was revised mid-protocol (see §4) from a leading form ("Does any of this change how you see the document?") to a neutral form. If any session ran before the revision lands in operator's mental model, flag those sessions in analysis as potentially demand-biased.

## 6. Decision rules

Prewrite the decision rules so analysis does not become post-hoc rationalization:

- **Signal A fires + not C:** the thesis validates. Continue Parts 3-4 of the spec, V4.2 web impl, 0.8.0 release arc. Track B informal becomes pre-work for a formal Track B when grant or override triggers.
- **Signal B fires:** the thesis is weakly supported at best. Pivot. Options: (i) redesign the divergence output to address the specific complaints; (ii) re-examine whether divergence is the right primitive; (iii) pause the MCP 0.8.0 release arc and prioritize redesign-informed validation. Operator decides pivot direction.
- **Signal C fires:** non-prescriptive rendering is not landing. Redesign §4.5 with language that users actually parse as non-prescriptive. Re-test before continuing.
- **Signal D fires:** narrow the domain focus more aggressively than STRATEGY §13 currently does. Finance-only or founder-only may be the right framing.
- **Ambiguous (no clear signal):** n=5 ambiguity IS a finding. Scale to n=10 before continuing or acknowledge that the cheap experiment did not produce a conclusive answer.

## 7. Output artifacts

After analysis (3-4 hours of operator time post-sessions):

- `TRACK_B_INFORMAL_RESULTS_v1.md` at repo root: single-page summary with the four signals, the decision made, and the participant-anonymized quotes that justify it.
- Decision recorded in SESSION_STATE.md as a new entry.
- If Signal A fires cleanly, this document serves as evidence in FRAME_DIVERGENCE Part 1 §7 prediction P2 tracking.

## 8. What this study is NOT

- Not a formal Track B. Formal Track B per VALIDATION_PROGRAM.md requires paid participants, pre-registration on OSF, IRB-lite protocol, larger n, statistical analysis. That is future-scope.
- Not generalizable. n=5 convenience sample.
- Not a validation of V4.2 engine quality. It tests the OUTPUT shape's effect on a reader, not the detector's accuracy.
- Not publishable on its own. It produces internal signal for operator decision-making, not academic evidence.

## 9. Why this is the highest-leverage move right now

Three structural reasons:

**Cost asymmetry.** 4-8 operator hours, ~$0.03 cash (three stimulus compositions via the `d2de4dd` harness at ~$0.009 per stimulus), binary thesis signal. Every other pending move (Parts 3-4 spec, web V4.2 impl for Pillar 2, Tier 2 engine hardening, MCP 0.8.0 PyPI publish) is more expensive in operator time and compounds conviction-risk rather than reducing it.

**Reversibility.** Two-way door. Informal study doesn't commit to anything. One-way-door actions (PyPI publish, arXiv preprint, reviewer outreach, manifesto publish) should follow signal, not precede it.

**Pattern break.** Operator's dominant habit is engineering + authoring. Informal study is a distribution-reflex move: operator talks to real users, extracts signal, updates plan. Establishing this reflex is the single most valuable meta-move available, regardless of what the study itself says.

## 10. When to run

As soon as the three stimulus documents are prepared. Ideally one evening of stimulus prep, one week of participant scheduling, two days of sessions, one evening of analysis. Total calendar time: ~10 days. Total operator time: 4-8 hours.

No dependency on production resume, MCP publish, or any other gated item. Runnable today.

## 11. References

- FRAME_DIVERGENCE_v1.md §3 (the thesis being tested).
- FRAME_DIVERGENCE_CONTRACT_v1.md §4 (the output shape being shown to users).
- FRAME_DIVERGENCE_CONTRACT_v1.md §5 (the faithfulness guarantees being tested for landing).
- VALIDATION_PROGRAM.md (formal Track B scope; this document is informal precursor).
- STRATEGY.md §4 (durable decisions), §12 (budget envelope), §13 (three-domain ladder).
- SESSION_STATE.md §6 (the 1-year test).
- V4_2_GAP_INVENTORY_v1.md §2 gaps #14-18 (the product-layer gaps this study informs).
- Stimulus composer CLI: shipped commit `d2de4dd` per Contract §7.2 web-surface mode. Per-stimulus artifacts under `data/track_b_informal/stimulus_<n>_<slug>/` (gitignored; operator reviews locally).
- MCP divergence integration: shipped commit `d735571` implementing Contract §§3-4 + §7.1 on the `frame_check` MCP surface. Operator may invoke MCP-side divergence with `include_divergence=true` as an alternative to the composer CLI if testing the MCP caller flow directly.
