# Human baseline vs single agent vs multi-agent

Generated 2026-11-19T14:33:30+00:00 by `python project/main.py human-score`. Same 40 messages (5 scam + 5 legitimate from each benchmark dataset), shown to raters without labels. Raters: 1. Messages a rater could not read are excluded for that rater.

| System | Scam caught | Unsafe miss | False alarm | Review load (unsure) | Time per message |
|---|---|---|---|---|---|
| humans_pooled | 58.8% | 11.8% | 0.0% | 17.1% | 4.8 s |
| multi_agent | 90.0% | 0.0% | 0.0% | 27.5% | 7.45 ms |
| single_agent | 65.0% | 0.0% | 0.0% | 32.5% | 1.57 ms |

## Per rater

| Rater | Age group | Answered | Skipped | Scam caught | Unsafe miss | False alarm | s/msg |
|---|---|---|---|---|---|---|---|
| R01 | 18-29 | 35 | 5 | 58.8% | 11.8% | 0.0% | 4.8 |

Limitations: small number of raters; raters are team members' family and friends, not a random sample; messages are synthetic or hand-written; raters judged text only, as the systems do.
