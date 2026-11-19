# Project details

## Objectives

1. Give anyone in Sri Lanka a verdict, the reason and a next step for a suspicious SMS or WhatsApp message in seconds,
   in Sinhala, Tamil or English.
2. Never give a false "safe". When the system is unsure, it says so and routes the message to a human.
3. Show, with a fair and reproducible benchmark, where a team of specialist agents does better than one agent, and
   where it costs more.
4. Keep personal data out of every component except the one that has to read it.

## Features

| Feature | Status |
|---|---|
| Seven specialist agents + arbiter + explainer on a shared blackboard | Built |
| Adaptive routing (Link & Sender agent only when there is something to check) | Built |
| Parallel specialists with 2 s timeout, retry, failure fallbacks, degraded mode | Built |
| Redaction of NIC, card numbers and emails before analysis; hash-only identity | Built |
| Replies in English, Sinhala and Tamil; validator for every reply | Built (Sinhala/Tamil drafts need native review) |
| Optional LLM rewording of replies, validated | Code written, **not yet executed against the live API** (no key in the build environment); not used in benchmarks. The template path is what runs. |
| JSONL traces of every agent post and decision | Built |
| Human review queue (redacted), labels, audit log | Built (`review`, `label`); review UI in progress |
| Single-agent baseline and benchmark harness, failure injection, throughput | Built |
| Human baseline: balanced 40-message timed rating page, scorer vs both systems | Built; ratings not yet collected (protocol in `docs/HUMAN_BASELINE.md`) |
| Gated retraining, blocklist growth from labels, rollback | Built (`retrain`, `rollback`; gate from the pre-existing code) |
| WhatsApp bot channel | Planned (Meta Cloud API webhook calling `POST /check`) |

## Agents

| Agent | Responsibility | Technique | Reads | Posts |
|---|---|---|---|---|
| Intake & Privacy | Only agent that sees raw text; redacts and parses | Regex redaction, URL/phone extraction, SHA-256 | raw text, sender | redacted text, links, phones, sender |
| Language | Language form and reply language | Unicode script rules; char 1–4-gram TF-IDF + logistic regression for Latin script | redacted text | language, reply language |
| Content | What the words say | char 2–5 + word 1–2-gram TF-IDF + logistic regression (pre-existing model, retrained) | redacted text | risk, top words |
| Tactics | How the message manipulates | Multilingual cue lists: credential, payment, reward, threat/urgency, authority; safety-advice cancellation | redacted text | risk, tactics |
| Link & Sender | Where the message sends you | Official-domain allowlist, look-alike edit distance, brand words in unofficial domains, shorteners, risky TLDs, IP links, call/WhatsApp asks, sender look-alikes, blocklist | links, phones, sender | risk, evidence |
| Campaign | Is this part of a known or new wave | Cosine similarity to scam and legitimate template centroids; memory of recent UNCERTAIN messages | redacted text | risk, campaign, wave size |
| Drift sentinel | Is the wording new to the content model | Share of unseen char n-grams vs 90th percentile on validation | redacted text | novelty flag |
| Arbiter | Final decision and conflict resolution | Logistic-regression stacker on out-of-fold agent outputs + rules R1–R8 | all posts | verdict, score, rules |
| Explainer | Reply in the user's language | Evidence-to-reason templates; optional LLM rewrite; validator | verdict, evidence, language | reply |

## Technical details

- **Language and runtime:** Python 3.12+, CPU only. Standard-library thread pools for parallel agents and a
  standard-library HTTP server for the API.
- **Shared state:** `Blackboard` (thread-safe dict of `AgentMessage` posts). Agents never call each other; the
  orchestrator controls the order.
- **Data:** synthetic multilingual messages from `src/make_data.py` (seed 42, split by template so that test wording is
  unseen), 189 hand-written training rows, 65 hand-written independent test rows, and a 64-row link and sender
  stress set. No real personal data. Phishing domains in the stress set are invented.
- **Model sizes:** all models together are a few MB. One message takes about 9–14 ms on one CPU core.
- **Security:** no secrets in the repository. The optional LLM key is read from the environment. Traces and the
  review queue hold redacted text only. The API limits body size to 8 KB.

## Known limitations (stated openly)

- All training data is synthetic or hand-written. Real, consented reports from a pilot partner are needed before
  any confidence claim about real traffic.
- The Language agent mislabels some unusual Singlish spellings as Tanglish, so the reply comes in the wrong
  language. Example: the real loan scam "Obe vaetupata pera mudal avasyada…".
- One Tanglish gift-card scam was cleared as LIKELY SAFE on the independent set (unsafe miss 3.3%). The Tactics
  agent has no "gift card" cue.
- The Sinhala/Tamil equivalents of "official app / office / branch" were added to the safety-advice list **after** the
  first benchmark run showed that all Sinhala false alarms came from one water-bill template. The run before the fix
  is kept in `project/reports/benchmark_v0_before_safety_fix.json` (held-out test false alarms 20.3% → 0% after the fix).
- A Singlish family-impersonation money request ("Mama oyage nangi … danna puluwanda 07…") was cleared as LIKELY SAFE in manual testing: the Tactics agent has no cue for "danna" (put money). Found 19 Nov; fix planned with native-speaker cue review.
- Throughput falls with more threads (Python GIL). Process-pool workers are planned.
- The human baseline is not collected yet.

## Pre-existing work and reuse (disclosure)

| Component | Origin | How it is used |
|---|---|---|
| `rakshaka/modeling.py` (`make_classifier`, `preprocess_text`, `char_ngram_oov_ratio`, `retrain_gate`) | Rakshaka AI, our earlier prototype (Oct 2026, github.com/geemalfernando/Rakshaka_AI), our team | Content agent model, Drift sentinel signal, planned retraining gate |
| `src/make_data.py`, `data/extra_*.csv`, `rakshaka/data.py` | same | Training and test data |
| `src/api.py`, `app/dashboard.py`, `scripts/` | same | Single-model prototype; not part of the multi-agent pipeline; the review desk will be adapted |
| Everything in `project/` and `tests/test_agents.py` | New, built for AI Catalyst from 16 Nov 2026 | The multi-agent system, baseline and benchmark |

## Third-party components

| Component | Licence | Use |
|---|---|---|
| scikit-learn | BSD-3-Clause | TF-IDF, logistic regression, GroupKFold |
| NumPy, SciPy | BSD-3-Clause | numerics |
| joblib | BSD-3-Clause | model files |
| requests | Apache-2.0 | optional LLM call |
| FastAPI, Streamlit, uvicorn, pandas (pre-existing prototype only) | MIT / Apache-2.0 / BSD | legacy UI and API |

## AI models, services and tools used (declaration)

| Tool | Where | Purpose |
|---|---|---|
| Claude (Anthropic), as an AI coding and writing assistant | Development | Helped write the multi-agent code, tests, documentation, the stress-test set, the first drafts of the Sinhala/Tamil reply templates and cue lists, and the proposal draft. The team reviewed and edited everything. |
| Anthropic Messages API (optional, off by default) | Runtime, Explainer | Rewording of replies only, validated. Not used in any reported result. |
| AI-assisted translation (pre-existing project) | `data/extra_*.csv`, see `data/PROMPTS.md` | Some multilingual rows were drafted with AI help and checked by the team |

No other AI models or services are used. The classifiers are trained locally from the data in this repository.
