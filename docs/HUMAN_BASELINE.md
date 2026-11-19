# Human baseline: protocol

Rule 04 of the challenge asks us to compare the multi-agent system, a single agent and **humans** on the same
documented task. This is how we collect and score the human part. No human results are reported until real
raters have taken part.

## Task

Each rater sees the same **40 messages**, one at a time, and chooses **Scam**, **Not sure** or **Safe**. If the
message is in a language they cannot read, they choose **I can't read this language**. The page records each answer
and the seconds taken. The two systems give the same three verdicts on the same 40 messages, so the
comparison is like for like.

- **Sample:** 5 scam + 5 legitimate messages from each benchmark dataset (held-out templates, new tactics,
  independent Sinhala/Tanglish, link and sender stress set). The sample is fixed by seed 11 (`human.build_sheet`).
- **Blind:** the page contains no labels. Raters never see correct answers, before or after.
- **Order:** shuffled per rater (seeded by initials + age group) to spread order and fatigue effects.

## Raters

- **Target: at least 4 raters,** including at least one aged 50+ and ideally one aged 65+ (the group scams hurt most),
  and at least one who reads Tamil.
- Raters are team members' family and friends (a convenience sample). The team members themselves must **not** rate,
  because they wrote the messages and the agents.
- Consent: the page asks for consent and records only initials, age group, answers and timings.

## Running it

1. Generate the page (already in the repo): `python project/main.py human-sheet` →
   `project/reports/human_baseline/rate.html` (paper fallback: `sheet.csv`).
2. Share the rating page: https://claude.ai/artifact/RbskfqH4u3itNjybroGJ2A (private until the owner turns on
   sharing from claude.ai), or send the `rate.html` file itself, which works offline in any phone browser.
3. Ask each rater to do it alone, on their phone, without searching or asking anyone. It takes about 10 minutes.
4. Each rater sends back the result code (`RKH1|…`). Save each one as a text file, for example
   `project/reports/human_baseline/raters/NF.txt`.
5. Score: `python project/main.py human-score project/reports/human_baseline/raters/*.txt` →
   `project/reports/human_baseline/results.{json,md}`.
6. Commit the result files and the rater codes, and update the README and proposal numbers from `results.md`.

## Metrics

The same metrics as the benchmark (`benchmark.score`): scam caught, unsafe miss (scam called safe), false alarm,
review load (unsure), plus seconds per message for people and milliseconds for the systems. "Can't read"
answers are excluded for that rater and reported as skipped.

## Limitations to state with the results

Small number of raters; not a random sample; synthetic or hand-written messages; raters judge text only (no
real sender context), as the systems do; people may be more careful in a study than when a message arrives.
