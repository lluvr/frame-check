# Reviewer Outreach Templates

**Status:** pre-curator-draft v0.1, 2026-04-21. Not live. Agent-produced template pack for the curator to personalize and send when inviting external reviewers for Frame Vocabulary Standard canon promotions. Each template is a STARTING POINT; curator replaces bracketed tokens and tone-calibrates to the recipient.

**Companion to REVIEWERS.md.** REVIEWERS.md is the open invitation / terms document reviewers read on arrival. These templates are the curator-side outreach that prompts them to read REVIEWERS.md in the first place. Two separate artifacts.

**Use.** Curator identifies a candidate reviewer (see `REVIEWERS.md §Candidate profile`), picks the template closest to that reviewer's persona below, replaces `[BRACKETED]` tokens with the specific details, tone-calibrates to the curator's voice, sends.

**Principle:** honest-limits preserved even in outreach. A reviewer invited with inflated claims reads REVIEWERS.md five minutes later, sees the `[DRAFT]` markers and the falsified detector F1, and concludes the outreach was dishonest. Worse than no outreach. Templates below keep the evidence discipline in the invitation itself.

---

## Template 1: Media framing / communication research scholar

**Target audience:** tenured or post-PhD researcher in framing analysis, media studies, communication, computational social science. Familiar with Entman, Iyengar, Media Frames Corpus, FrameAxis. CHI/CSCW/JASIST publication track.

**Subject line:** Inviting your review on a computational framing artifact (Frame Check FVS-001)

**Body:**

Dear [PROF. NAME],

I'm reaching out because your work on [SPECIFIC PAPER / TOPIC, e.g., "the role of amplification in news framing"] is directly relevant to a research artifact I'm building toward canon publication and would benefit from your review.

Frame Check is a deterministic structural-framing analysis tool with a 20-entry Frame Vocabulary Standard (FVS) library. The first entry approaching canon promotion, FVS-001 Frame Amplification, names a pattern where a framing choice made early in a document compounds through subsequent paragraphs. You can read the candidate entry at:

https://github.com/lluvr/frame-check/blob/master/data/frame_library/promotions/FVS-001_v1.md

Honest state: the library is single-curator-authored. Zero entries have been promoted to canon. The detector associated with FVS-001 scored F1 = 0.36 against expert labelers in a pre-registered validation, below the useful threshold of 0.4; this negative result is published in full at `fvs_eval/validation_study/REPORT_V3_TRACK_A.md`. The canon promotion is not about detector accuracy (which is below useful); it's about whether the named framing pattern is a worthwhile vocabulary contribution at all. Your review would test exactly that.

The ask: a 1,500-3,000 word adversarial review against the five promotion criteria in `data/frame_library/INDEX.md`. Per-engagement terms are specified at:

https://github.com/lluvr/frame-check/blob/master/REVIEWERS.md

Compensation defaults to co-curator aspiration plus named attribution; a situational honorarium ($500-$1,000) applies where your context requires it (unpaid academic year, visiting position). This is not a bug-bounty transaction; it's a research-contribution invitation.

Timeline: 3-6 months realistic, written at whatever cadence fits your workload.

What you get: named authorship on the first canon promotion decision record; early access to subsequent FVS entries at aspirational status; a genuine research contribution that will be cited as the artifact gains external adoption.

I've tried to make the self-enumerated limits legible before you open anything: `ANTICIPATED_CRITIQUES.md` at the repo root collects 20 anticipated adversarial readings with the project's current defenses and open gaps. If you want to spot-check whether the project is honest about what it does not know before investing time, that document is the fastest route.

If you're interested, reply and I'll send a scoped reading package. If not, a pointer to colleagues you think would be a better fit is also welcome.

Lovro Lucic
[CONTACT]

---

## Template 2: LLM safety / AI evaluation researcher

**Target audience:** researcher at Anthropic RSP / OpenAI Preparedness / DeepMind Frontier Safety / UK AISI / METR / Apollo. Familiar with model-card evaluations, systemic safety, capability elicitation. May not have framing-analysis background but evaluates LLM output structurally for a living.

**Subject line:** Frame Check FVS-Eval: inviting measurement-construct review

**Body:**

Hi [NAME],

I'm writing because Frame Check, a structural-framing analysis instrument I've been building, produces an evaluation artifact (`fvs_eval/SPEC.md`) that I think belongs in front of lab safety teams before the v0.1 corpus ships.

The eval measures what a model PRODUCES structurally (coverage of five analytical dimensions, voice cascade, temporal orientation, epistemic basis) on a prompt corpus designed to elicit framing variation. Scoring is deterministic regex, not LLM-as-judge. The thesis is that framing is a safety-adjacent behavioral axis no existing benchmark targets (TruthfulQA, BBQ, HELM, Sycophancy evals each target something else). The full v0 spec is at:

https://github.com/lluvr/frame-check/blob/master/fvs_eval/SPEC.md

The specific ask: measurement-construct review. The spec makes five load-bearing claims (§19 "Key claims for reviewer stress-test"); your review would evaluate whether those claims hold under safety-team scrutiny. 1,000-2,000 word budget per REVIEWERS.md.

Honest state:
- Detector F1 against expert labelers on a separate validation study (Track A) landed at 0.36, below the pre-registered 0.4 threshold. Published in full. The eval's scoring precision is upper-bounded by detector precision on model outputs specifically, which is unvalidated and named in SPEC.md §8 as the gating check before v1.0.
- The eval has not yet been run against a model panel. The v0 specification is what the review engages.
- A separate reader-aid study (Track B) is pre-registered at `fvs_eval/reader_aid_study/DESIGN_v1.1.md` with an OSF submission. Has not run.

What you get: named contribution to a safety-adjacent eval specification before any lab commits to running it. The spec commits (v0 §18) to publish a no-lab-engagement outcome after 12 months as a finding rather than letting the effort lapse quietly.

I've made the self-enumerated limits legible at `ANTICIPATED_CRITIQUES.md` (20 anticipated attacks, current defenses, open gaps). Specifically §3 "Strategic critiques" covers the MCP-adoption and external-engagement questions a safety team will ask.

Terms per REVIEWERS.md: co-curator aspiration, named attribution, situational honorarium where context requires. Timeline: 3-6 months realistic.

Interested?

Lovro Lucic
[CONTACT]

---

## Template 3: Journalist / practitioner with structural-reading expertise

**Target audience:** investigative or science journalist who engages seriously with how AI-generated documents are structured. Writers / editors with an interest in framing. The audience who would be the first to USE the tool and can review the library from a practitioner perspective.

**Subject line:** Frame Check FVS-001: can you read this as a practitioner?

**Body:**

Hi [NAME],

I'm reaching out because you're one of the small number of people who would actually use a tool like Frame Check in your work, and the first frame entry approaching canon publication would benefit from your eye before it lands.

Frame Check is a deterministic structural-framing analysis tool for documents. It surfaces which perspectives a document takes and which it omits, classifies voice (prescriptive / promotional / analytical), names numeric claims that were or were not attributable to sources, and matches the document against a Frame Vocabulary Standard of named patterns. I have a public-facing essay draft in progress about what it does (https://frame.clarethium.com).

The FVS entry approaching canon promotion is FVS-001 Frame Amplification. Candidate entry with worked example at:

https://github.com/lluvr/frame-check/blob/master/data/frame_library/promotions/FVS-001_v1.md

The ask, adapted to a practitioner: read the entry, read the worked example, and tell me whether the named pattern is one you recognize from documents you actually encounter. If yes, is the definition tight enough to be useful? Is the worked example load-bearing or ceremonial? Are there failure cases (documents that exhibit the pattern but the entry misses, or vice versa) you know from your own reading?

Format: whatever works for you. A typed response, a Zoom call with notes, voice memos. 1,500-3,000 words is the typical reviewer budget; a practitioner review might be shorter and more concrete without losing weight.

Honest state: the library is currently all-draft, zero promotions. I'd be inviting you to be one of three reviewers on the first promotion. What I don't have is user-study evidence that the tool helps readers see frames they would otherwise miss; that's a separate pre-registered study, not yet run. What I do have is the computational substrate that makes the named patterns reproducibly detectable.

Terms at https://github.com/lluvr/frame-check/blob/master/REVIEWERS.md (compensation defaults to co-curator aspiration plus named attribution; situational honorarium where applicable; no paid-transaction framing).

Interested? If yes, I'll send the scoped reading package. If no, a pointer to a colleague you trust is welcome.

Lovro Lucic
[CONTACT]

---

## Template 4: Cognitive / measurement-theory scholar

**Target audience:** researcher in cognitive psychology, measurement theory, or reader-comprehension studies. The review here is about whether the tool's construct-honesty posture (under-detection discipline, classification-confidence surfacing) is measurement-theoretically sound.

**Subject line:** Review request: construct-honesty posture in a deterministic framing tool

**Body:**

Dear [PROF. NAME],

Your work on [SPECIFIC PAPER / TOPIC, e.g., "lower-bound claims in measurement," "reader calibration"] is precisely the grounding I'd like to pressure-test a evidence discipline against before it ships in a methodology paper.

Frame Check is a deterministic structural-framing analysis tool. The evidence discipline runs across its five signals: under-detection surfacing for coverage / epistemic / claims (the "no markers detected for X" rather than "fails to address X" rendering); classification-confidence for voice (distinguishing firing-rule decisive calls from residual-fallback classifications); distribution-with-dominant for temporal (surfacing margin alongside dominant tense). The methodology paper in progress makes this discipline the primary contribution claim.

The discipline is documented at `METHODOLOGY.md §1.3` and `§1.3.1`. A recent self-audit is at `fvs_eval/CONSTRUCT_HONESTY_AUDIT_v1.md` (the audit found its own first-pass missed two of five rendering surfaces; subsequent passes closed them; the v1.3 audit documents the iteration as evidence that self-audit is lower-grade than independent).

The ask: 1,500-2,500 word review evaluating whether the construct-honesty posture is measurement-theoretically sound. Specifically:

- Is "no markers detected for X" a legitimate lower-bound claim that a reader can be expected to read as such, or is it an aesthetic reframing of "missing" that doesn't actually shift interpretation?
- Is the firing-rule vs. residual-fallback distinction in the voice cascade a useful consumer-facing distinction, or measurement-theoretic overkill?
- Does the progression of the self-audit (v1 to v1.3, each pass finding more) belong as evidence for the discipline or against it?

What you get: named contribution to the methodology paper's §7 limitations and construct-validity argument. The paper is explicitly co-authored with the first engaged academic reader (per `SESSION_STATE.md §4` ED-1 resolution), so this invitation carries that authorship offer directly.

Terms at REVIEWERS.md; same compensation posture as other reviews.

Interested?

Lovro Lucic
[CONTACT]

---

## Template 5: Omnibus short (first-touch, no persona-specific tailoring)

**Subject line:** Frame Check: inviting review on a canon-promotion candidate

**Body:**

Hi [NAME],

You came up on my shortlist for inviting review on Frame Check's first Frame Vocabulary Standard canon promotion.

Candidate entry: FVS-001 Frame Amplification. Dossier with self-assessment against promotion criteria and named weaknesses for reviewer stress-test at:

https://github.com/lluvr/frame-check/blob/master/data/frame_library/promotions/FVS-001_v1.md

Terms and honest state of what you would be reviewing at:

https://github.com/lluvr/frame-check/blob/master/REVIEWERS.md

The project's self-enumerated limits (20 anticipated critiques with current defenses) at:

https://github.com/lluvr/frame-check/blob/master/ANTICIPATED_CRITIQUES.md

Target: 3 reviewers for the first promotion. 1,500-3,000 words per review, 3-6 month timeline. Compensation: co-curator aspiration, named attribution, situational honorarium.

If you're interested in engaging, reply with questions or a pointer to the entry that matches your background best. If this isn't a fit, a suggestion of someone you'd trust for the role is also welcome.

Lovro Lucic
[CONTACT]

---

## Template 6: Follow-up after two weeks with no response

**Subject line:** Re: [ORIGINAL SUBJECT]

**Body:**

Hi [NAME],

Following up on my note from [DATE]. No pressure if the timing isn't right; reviewer commitment is a genuine time investment and I respect the ask is substantial.

Two updates since I wrote:
- [RECENT PROJECT UPDATE, e.g., "the construct-honesty audit v1.3 shipped L3a fixes across five rendering surfaces"]
- [ANY RELEVANT EXTERNAL SIGNAL]

If you've decided this isn't for you, a one-line reply is all I need. If you're deliberating, I'd rather you take the time than commit prematurely. If you're interested but the candidate entry isn't the right fit, I can steer you toward a different entry or toward the FVS-Eval measurement-construct review path (different workload, different audience).

Lovro Lucic
[CONTACT]

---

## Template 7: Decline gracefully (template for handling inbound polite-no)

When a candidate responds with "not the right fit" or "no capacity":

**Subject line:** Re: [ORIGINAL SUBJECT]

**Body:**

Hi [NAME],

Thanks for the quick and honest reply. No hard feelings on the decline; reviewer capacity is a scarce resource and a measured "no" is more useful than a reluctant "yes."

Two things before I step off:

- If you think of someone who fits better, a pointer is welcome at any time. No urgency.
- The project is open source (Apache-2.0 / CC-BY-4.0 split); if you want to engage at a lower commitment level (a one-line issue on GitHub, a brief conversation), the surface is at https://github.com/lluvr/frame-check.

Thanks for considering.

Lovro Lucic

---

## Curator checklist before sending any of the above

1. **Personalize the opening.** The `[SPECIFIC PAPER / TOPIC]` placeholder is load-bearing; if the curator cannot name specifically why this recipient, the outreach is premature. Ask why this person first.
2. **Tone match.** Read one of the recipient's recent publications or public writings. Adjust the template's register. An overly formal template to a practitioner, or an overly casual one to a senior academic, is worse than no outreach.
3. **Volume throttle.** Per REVIEWERS.md: target 3 reviewers for the first promotion. The curator should not send template 1 to ten people in one week; send 2-4, wait for response, then iterate based on what the first responses surface.
4. **Attach the right version hash.** FVS-001_v1.md evolves as the curator refines. Include the commit hash or version marker in the email so the reviewer reads the version the curator intends.
5. **Honest-limits discipline.** Before hitting send, reread the template to check that every claim is one the curator stands behind. If a claim reads as inflated, soften it to match `ANTICIPATED_CRITIQUES.md` state.
6. **Decline paths.** Have templates 6 (follow-up) and 7 (graceful decline) ready. A reviewer pipeline is a portfolio, not a single outreach.

---

## Honest limits of this template pack

- **Agent-authored in the curator's voice-estimation.** The curator may write substantially differently; templates should be rewritten into the curator's actual voice before sending. Verbatim use is worse than a template-per-target written from scratch.
- **Personas are stereotypes.** Template 1 assumes an academic prof; template 3 assumes a practitioner; template 4 assumes a measurement theorist. Real candidates are mixed. Curator blends.
- **No DPP / DPI reviewer personas.** Data privacy and legal reviewers are not enumerated; those are out-of-scope for REVIEWERS.md's canon-promotion invitation surface (they would engage via security / legal channels per `SECURITY.md`).
- **No direct-message platforms.** Templates assume email. Twitter DMs / LinkedIn / Signal are different surfaces with different register norms. Curator adapts.
- **Does not address rejected-candidate patterns.** Reviewers who decline and cite specific criticisms of the work are valuable signal; their feedback shapes future outreach. This template pack does not yet capture that feedback loop.

---

*v0.1 pre-curator-draft. 2026-04-21. Agent-produced template pack for reviewer outreach. Curator personalizes, tone-calibrates, and sends. Companion to REVIEWERS.md (reviewer-facing terms document).*
