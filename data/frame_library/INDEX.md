# Frame Library Index

Canonical reference for the Frame Vocabulary Standard (FVS): which
frames exist, their detection state, and how to cite them.

**Library version:** 0.2.0 (see `VERSION`)

## Status

Each entry carries a stability status. As of v0.2.0, all 20 entries
are `draft` (single-curator entries; reviewers wanted). No entry is
`canon` yet; promotion criteria require external review.

| Status | Meaning |
|--------|---------|
| `canon` | Promoted via review process. Citable in published work. |
| `draft` | Single-curator entry, internal use, "reviewers wanted". |
| `aspirational` | Frame named in the index but no entry exists yet. |
| `retired` | Was canon, then withdrawn. ID preserved for citation continuity. |

## Class

Frames divide into two classes based on whether automated detection
from text is feasible:

| Class | Meaning |
|-------|---------|
| `text-side` | Frame manifests as patterns in document text. Detection rule expected. |
| `meta-side` | Frame describes a reader/system mechanism, not a text property. Documentation only. |

## Detection state

The Detection column records the state of the frame's detection
rule, not the frame concept:

| Detection | Meaning |
|-----------|---------|
| `yes` | Detection rule fires on the frame's patterns. |
| `gap` | Text-side frame; rule planned but not yet implemented. |
| `retired` | Rule existed but was retired after evidence showed it failed its design intent. The frame concept stands; the rule does not. |
| `n/a` | Meta-side frame; detection not applicable. |

## The Frames

| ID | Name | Class | Detection | Status | Curated |
|----|------|-------|-----------|--------|---------|
| FVS-001 | Frame Amplification | text-side | retired | draft | 2026-04-18 |
| FVS-002 | Fluency-Quality Illusion | text-side | yes | draft | 2026-04-12 |
| FVS-003 | Prompt Attribution Error | meta-side | n/a | draft | 2026-04-12 |
| FVS-004 | Default Geometry | meta-side | n/a | draft | 2026-04-12 |
| FVS-005 | System Attribution Error | meta-side | n/a | draft | 2026-04-12 |
| FVS-006 | Identity Framing Asymmetry | meta-side | n/a | draft | 2026-04-12 |
| FVS-007 | Failure Framing | text-side | yes | draft | 2026-04-12 |
| FVS-008 | Growth Frame | text-side | retired | draft | 2026-04-18 |
| FVS-009 | Risk Frame | text-side | yes | draft | 2026-04-12 |
| FVS-010 | Completeness Illusion | text-side | yes | draft | 2026-04-12 |
| FVS-011 | Stakeholder Frame | text-side | yes | draft | 2026-04-17 |
| FVS-012 | Uncertainty Frame | text-side | yes | draft | 2026-04-17 |
| FVS-013 | Oracle Frame | meta-side | n/a | draft | 2026-04-13 |
| FVS-014 | Temporal Anchoring | text-side | yes | draft | 2026-04-13 |
| FVS-015 | Efficiency Frame | text-side | retired | draft | 2026-04-18 |
| FVS-016 | Authority by Citation | text-side | yes | draft | 2026-04-13 |
| FVS-017 | False Balance | meta-side | n/a | draft | 2026-04-18 |
| FVS-018 | Scope Narrowing | meta-side | n/a | draft | 2026-04-18 |
| FVS-019 | Narrative Coherence | meta-side | n/a | draft | 2026-04-18 |
| FVS-020 | The Invisible Frame | meta-side | n/a | draft | 2026-04-13 |

## Citing a frame

Cite by ID and library version:

> Framecheck FVS-008 Growth Frame (library v0.2.0).

The ID is permanent across library versions. Names and identification
text may evolve while a frame is `draft`; only `canon` entries
guarantee identification stability.
