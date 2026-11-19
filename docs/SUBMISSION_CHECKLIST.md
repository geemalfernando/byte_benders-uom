# Submission checklist (AI Catalyst 2026, University Track)

Repository: https://github.com/geemalfernando/byte_benders-uom (public)

## Required structure

| Required | Here | Status |
|---|---|---|
| `project/main.py` | yes | ✅ |
| `project/requirements.txt` | yes | ✅ |
| `README.md` | yes | ✅ |
| `docs/Proposal.docx` (≤ 10 pages) | 7 pages | ✅ |
| `docs/Workflow.md` | yes | ✅ |
| `docs/PROJECT_DETAILS.md` (incl. AI tool declaration) | yes | ✅ |
| `project-demo.mp4` (MP4, H.264 + AAC, ≥720p, 5–10 min, ≤100 MB) | — | ⏳ due 29 Nov |

## Deadlines

| When | What | Status |
|---|---|---|
| Fri 20 Nov 2026, 11:59 PM | Proposal in `docs/Proposal.docx`, repo link shared | ⏳ |
| Sun 29 Nov 2026, 11:59 PM | Working MVP, complete project plan (`docs/PROJECT_PLAN.md`), samples, docs, demo video | ⏳ |
| Mon 7 Dec 2026, 8 AM – 8 PM | Grand finale, Hilton Colombo Residences: final-day features, 5 min prep + 15 min demo + 10 min Q&A, max 10 slides | — |

## Organiser steps

- [x] Repo named `team_name-university` (`byte_benders-uom`)
- [x] Invited the Innodata GitHub account **AI-Catalyst-Innodata** as a collaborator (19 Nov; pending their acceptance)
- [ ] Share the repo link with the organisers through the channel given at the 16 Nov introductory session
- [x] Fourth team member (Pamindu Piumaka) added to `docs/Proposal.docx`
- [ ] Keep the repo updated; organisers must keep access at all times

## Before 29 Nov

- [ ] Human baseline: send 4+ raters (not team members; one aged 50+, one Tamil reader) the rating page https://claude.ai/artifact/RbskfqH4u3itNjybroGJ2A or `rate.html`; save each result code in `project/reports/human_baseline/raters/`; run `human-score`; commit results (see `docs/HUMAN_BASELINE.md`)
- [ ] Native-speaker check of Sinhala/Tamil replies (`decision.py`) and cue lists (`lexicons.py`)
- [ ] Final `python project/main.py benchmark`; commit `project/reports/`
- [ ] Record `project-demo.mp4`: problem → architecture → live `check` and `demo` → trace → benchmark → review loop (`review`, `label`, `retrain`)
- [ ] Update README results and docs from the final benchmark
