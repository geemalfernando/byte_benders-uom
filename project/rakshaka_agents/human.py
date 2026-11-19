"""Human baseline: the same messages, rated by people, compared with both systems.

    python project/main.py human-sheet            # balanced 40-message sheet + rating page (rate.html)
    python project/main.py human-score FILE...    # score rater result codes / CSVs against both systems

Protocol: docs/HUMAN_BASELINE.md. The rating page holds no labels, so raters cannot see the answers.
Each rater ends with a one-line result code (sent by WhatsApp or email); save each as a .txt file.
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .baseline import SingleAgent
from .benchmark import DATASETS, score
from .orchestrator import Orchestrator
from .training import PROJECT, build_team, load_content_model, load_rows

OUT = PROJECT / "reports" / "human_baseline"
SEED = 11
PER_CELL = 5   # 4 datasets x 2 labels x 5 = 40 messages
VERDICTS = {"S": "SCAM", "U": "UNCERTAIN", "F": "LIKELY_SAFE", "X": "SKIPPED"}


def build_sheet() -> list[dict]:
    """Balanced, reproducible sample: 5 scam + 5 legitimate from each of the 4 benchmark datasets."""
    rng = random.Random(SEED)
    sample = []
    for name, path in DATASETS.items():
        rows = load_rows(path)
        for label in ("scam", "legitimate"):
            pool = sorted((r for r in rows if r["label"] == label), key=lambda r: r["text"])
            seen, picked = set(), []
            for r in rng.sample(pool, len(pool)):
                key = r.get("group_id") if name in ("test", "shifted") else r["text"]
                if key in seen:          # one message per template, so 5 different wordings
                    continue
                seen.add(key)
                picked.append(dict(r, dataset=name))
                if len(picked) == PER_CELL:
                    break
            sample += picked
    rng.shuffle(sample)
    for i, r in enumerate(sample):
        r["id"] = i
    return sample


def write_sheet() -> dict:
    sheet = build_sheet()
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "sheet.csv", "w", newline="", encoding="utf-8") as handle:   # paper fallback, no labels
        w = csv.writer(handle)
        w.writerow(["id", "text", "sender", "your_verdict (SCAM/UNSURE/SAFE/CANT_READ)", "seconds_taken"])
        for r in sheet:
            w.writerow([r["id"], r["text"], r.get("sender") or "", "", ""])
    template = (Path(__file__).parent / "rate_template.html").read_text(encoding="utf-8")
    items = [{"id": r["id"], "text": r["text"], "sender": r.get("sender") or ""} for r in sheet]
    page = template.replace("/*ITEMS*/[]", json.dumps(items, ensure_ascii=False))
    (OUT / "rate.html").write_text(page, encoding="utf-8")
    return {"messages": len(sheet), "sheet": str(OUT / "sheet.csv"), "page": str(OUT / "rate.html")}


def parse_result(path: Path) -> dict:
    """Accept the page's result code (RKH1|rater|age|id:V:secs;...) or a filled sheet.csv."""
    text = path.read_text(encoding="utf-8").strip()
    if "RKH1|" in text:
        code = text[text.index("RKH1|"):].split()[0]
        _, rater, age, body = code.split("|", 3)
        answers = {}
        for part in filter(None, body.split(";")):
            i, v, secs = part.split(":")
            answers[int(i)] = (VERDICTS[v], float(secs))
        return {"rater": rater, "age_group": age, "answers": answers, "source": path.name}
    answers = {}
    for r in csv.DictReader(text.splitlines()):
        raw = (r.get("your_verdict (SCAM/UNSURE/SAFE/CANT_READ)") or "").strip().upper()
        v = {"SCAM": "SCAM", "UNSURE": "UNCERTAIN", "SAFE": "LIKELY_SAFE", "CANT_READ": "SKIPPED"}.get(raw)
        if v:
            answers[int(r["id"])] = (v, float(r.get("seconds_taken") or 0))
    return {"rater": path.stem, "age_group": "unknown", "answers": answers, "source": path.name}


def score_humans(paths: list[Path]) -> dict:
    sheet = build_sheet()
    by_id = {r["id"]: r for r in sheet}
    raters = [parse_result(p) for p in paths]
    if not raters:
        raise ValueError("give at least one rater result file")

    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "n_messages": len(sheet), "n_raters": len(raters), "raters": [], "systems": {}}
    pooled_rows, pooled_res = [], []
    for rater in raters:
        rows, res = [], []
        for i, (verdict, secs) in sorted(rater["answers"].items()):
            if verdict == "SKIPPED" or i not in by_id:
                continue
            rows.append(by_id[i])
            res.append({"verdict": verdict, "latency_ms": secs * 1000})
        m = score(rows, res) if rows else {}
        m.update(rater=rater["rater"], age_group=rater["age_group"], answered=len(rows),
                 skipped=sum(v == "SKIPPED" for v, _ in rater["answers"].values()),
                 seconds_per_message=round(statistics.mean(r["latency_ms"] for r in res) / 1000, 1) if res else None)
        report["raters"].append(m)
        pooled_rows += rows
        pooled_res += res
    human = score(pooled_rows, pooled_res)
    human["seconds_per_message"] = round(statistics.mean(r["latency_ms"] for r in pooled_res) / 1000, 1)
    report["systems"]["humans_pooled"] = human

    multi, single = Orchestrator(build_team()), SingleAgent(load_content_model())
    for name, system in (("multi_agent", multi), ("single_agent", single)):
        res = [system.check(r["text"], sender=r.get("sender") or None) for r in sheet]
        report["systems"][name] = score(sheet, res)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "results.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def to_markdown(r: dict) -> str:
    out = ["# Human baseline vs single agent vs multi-agent", "",
           f"Generated {r['generated_at']} by `python project/main.py human-score`. Same {r['n_messages']} messages "
           "(5 scam + 5 legitimate from each benchmark dataset), shown to raters without labels. "
           f"Raters: {r['n_raters']}. Messages a rater could not read are excluded for that rater.", "",
           "| System | Scam caught | Unsafe miss | False alarm | Review load (unsure) | Time per message |",
           "|---|---|---|---|---|---|"]
    for name, m in r["systems"].items():
        t = f"{m['seconds_per_message']} s" if "seconds_per_message" in m else f"{m['latency_p50_ms']} ms"
        out.append(f"| {name} | {pct(m['scam_caught'])} | {pct(m['unsafe_miss'])} | {pct(m['false_alarm'])} | "
                   f"{pct(m['review_load'])} | {t} |")
    out += ["", "## Per rater", "", "| Rater | Age group | Answered | Skipped | Scam caught | Unsafe miss | False alarm | s/msg |",
            "|---|---|---|---|---|---|---|---|"]
    for m in r["raters"]:
        out.append(f"| {m['rater']} | {m['age_group']} | {m['answered']} | {m['skipped']} | {pct(m.get('scam_caught'))} | "
                   f"{pct(m.get('unsafe_miss'))} | {pct(m.get('false_alarm'))} | {m['seconds_per_message']} |")
    out += ["", "Limitations: small number of raters; raters are team members' family and friends, not a random "
                "sample; messages are synthetic or hand-written; raters judged text only, as the systems do."]
    return "\n".join(out) + "\n"

