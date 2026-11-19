# Benchmark: multi-agent vs single-agent

Generated 2026-11-19T14:00:05+00:00 on Linux x86_64, Python 3.13.18, CPU only. LLM used: False.
Produced by `python project/main.py benchmark`; nothing in this file is edited by hand.

| Dataset | System | n | Scam caught | Unsafe miss | False alarm | Review load | Decided bal. acc. | p50 ms |
|---|---|---|---|---|---|---|---|---|
| test | multi_agent | 264 | 100.0% | 0.0% | 0.0% | 5.7% | 100.0% | 8.71 |
| test | single_agent | 264 | 93.7% | 0.0% | 0.0% | 10.2% | 100.0% | 1.55 |
| shifted | multi_agent | 152 | 95.5% | 0.0% | 0.0% | 7.9% | 100.0% | 9.78 |
| shifted | single_agent | 152 | 87.1% | 0.0% | 0.0% | 12.5% | 100.0% | 1.54 |
| independent | multi_agent | 65 | 80.0% | 3.3% | 0.0% | 41.5% | 98.0% | 11.65 |
| independent | single_agent | 65 | 80.0% | 0.0% | 0.0% | 29.2% | 100.0% | 1.62 |
| stress | multi_agent | 64 | 78.1% | 0.0% | 0.0% | 28.1% | 100.0% | 13.59 |
| stress | single_agent | 64 | 12.5% | 3.1% | 0.0% | 62.5% | 90.0% | 1.62 |

## Per language (test + shifted + independent)

| Language | System | n | Scam caught | Unsafe miss | False alarm | Review load |
|---|---|---|---|---|---|---|
| english | multi_agent | 224 | 100.0% | 0.0% | 0.0% | 1.8% |
| english | single_agent | 224 | 86.3% | 0.0% | 0.0% | 10.3% |
| singlish | multi_agent | 68 | 89.8% | 0.0% | 0.0% | 8.8% |
| singlish | single_agent | 68 | 100.0% | 0.0% | 0.0% | 0.0% |
| sinhala | multi_agent | 97 | 95.4% | 0.0% | 0.0% | 33.0% |
| sinhala | single_agent | 97 | 95.4% | 0.0% | 0.0% | 26.8% |
| tamil | multi_agent | 52 | 100.0% | 0.0% | 0.0% | 0.0% |
| tamil | single_agent | 52 | 85.0% | 0.0% | 0.0% | 11.5% |
| tanglish | multi_agent | 40 | 85.0% | 5.0% | 0.0% | 30.0% |
| tanglish | single_agent | 40 | 85.0% | 0.0% | 0.0% | 25.0% |

## Robustness under injected failures (all datasets)

| Failure rate per attempt | System | Unsafe miss | No answer | Scam caught | False alarm |
|---|---|---|---|---|---|
| 0.3 | multi_agent | 0.5% | 0.0% | 81.5% | 0.0% |
| 0.3 | single_agent | 0.3% | 11.7% | 74.5% | 0.0% |
| 0.6 | multi_agent | 0.8% | 0.0% | 48.2% | 0.0% |
| 0.6 | single_agent | 0.3% | 39.8% | 49.5% | 0.0% |

## Throughput

- workers_1: multi-agent 41.9 msg/s, single-agent 564.0 msg/s
- workers_4: multi-agent 21.0 msg/s, single-agent 484.1 msg/s

## Test conditions and limitations

- Machine: Linux x86_64, Python 3.13.18, CPU only. Same messages, same training data, same content model and thresholds for both systems.
- Sample sizes are the `n` column above. All data is synthetic or hand-written; these results show the design works, not accuracy on real traffic.
- The stress set was written while the link rules were designed, so it is not an unbiased estimate.
- Failure injection: each agent attempt fails with the stated probability; 2 attempts per agent (and per single-agent call).
- Human baseline: not yet collected (see `python project/main.py human-sheet`).
- The LLM rephraser was off for every run (`llm_used: false`).

Compute cost at full load on a USD 24.0/month server: USD 0.000441 per 1,000 messages (compute only; WhatsApp reply fees and reviewer time are separate).
