# Frame Check Governance

**Status:** single author. Frame Check is a personal project; the repository
is private and the Clarethium brand it was published under is wound down.

Frame Check is written and maintained by Lovro Lucic. There is no external
governance process: no reviewer pipeline, no canon-promotion vote, no
council. Earlier drafts of this document specified that machinery (external
reviewers, promotion criteria, dissent rules, succession, multi-curator
models) as an aspiration for a public project. None of it was ever
exercised, and it does not describe the project as it stands.

## What this means in practice

- The author decides which frame-vocabulary entries are added, refined, or
  withdrawn, which detection rules ship, and what lands in a release.
- No frame-vocabulary entry has been promoted to "canon". Every published
  entry carries the `[DRAFT]` marker; the stability guarantee is ID-only.
- The author does not decide what a reader concludes from a Frame Check
  analysis or worked example. The tool produces analytical scaffolding; the
  reader does the interpretive work.

## Where decisions are recorded

| Decision | Source |
|----------|--------|
| Frame-vocabulary state | per-card prose under `data/frame_library/` and `INDEX.md` |
| Contribution and code conventions | `CONTRIBUTING.md` |
| License | `LICENSE` (corpus CC-BY-4.0; code Apache-2.0) |
| Release notes | `CHANGELOG.md` |
| Divergence-block contract | `docs/FRAME_DIVERGENCE_CONTRACT_v1.md` |

Anything not in these sources is not a decision.
