"""Multi-agent vs single-agent benchmark. Every number in reports/ is produced by this file.

Datasets (all labelled scam / legitimate):
  test         synthetic, template-held-out (wording never seen in training)        data/test.csv
  shifted      synthetic NEW tactics: SL-UDI digital ID, QR, crypto, family-impersonation data/shifted.csv
  independent  hand-written Sinhala / Tanglish set, never used for training or tuning  data/extra_test.csv
  stress       link/sender stress set written alongside the agents (NOT an unbiased     project/data/adversarial.csv
               estimate: it was written while the link rules were being designed)

Metrics per system: scam caught (SCAM verdict), unsafe miss (scam called LIKELY_SAFE: the
dangerous error), false alarm (legitimate called SCAM), review load (UNCERTAIN share), balanced
accuracy on decided messages, latency, throughput, and robustness under injected agent failures.
"""
from __future__ import annotations

import csv
import json
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .baseline import SingleAgent
from .orchestrator import Orchestrator
from .training import DATA, PROJECT, build_team, load_content_model, load_rows

REPORTS = PROJECT / "reports"
DATASETS = {
    "test": DATA / "test.csv",
    "shifted": DATA / "shifted.csv",
    "independent": DATA / "extra_test.csv",
    "stress": PROJECT / "data" / "adversarial.csv",
}
SERVER_USD_PER_MONTH = 24.0   # 2 vCPU / 4 GB droplet, as in the Geveo proposal


def score(rows, results) -> dict:
    scams = [res for r, res in zip(rows, results) if r["label"] == "scam"]
    legit = [res for r, res in zip(rows, results) if r["label"] == "legitimate"]
    share = lambda items, v: round(sum(x["verdict"] == v for x in items) / len(items), 4) if items else None
    decided = [(r["label"], res["verdict"]) for r, res in zip(rows, results) if res["verdict"] in ("SCAM", "LIKELY_SAFE")]
    rec = lambda lab, v: (sum(1 for a, b in decided if a == lab and b == v) /
                          max(1, sum(1 for a, _ in decided if a == lab)))
    lat = [res["latency_ms"] for res in results]
    return {
        "n": len(rows), "n_scam": len(scams), "n_legit": len(legit),
        "scam_caught": share(scams, "SCAM"),
        "unsafe_miss": share(scams, "LIKELY_SAFE"),
        "scam_to_review": share(scams, "UNCERTAIN"),
        "false_alarm": share(legit, "SCAM"),
        "legit_cleared": share(legit, "LIKELY_SAFE"),
        "review_load": round(sum(x["verdict"] == "UNCERTAIN" for x in results) / len(results), 4),
        "no_answer": round(sum(x["verdict"] == "ERROR" for x in results) / len(results), 4),
        "decided_balanced_accuracy": round((rec("scam", "SCAM") + rec("legitimate", "LIKELY_SAFE")) / 2, 4),
        "latency_p50_ms": round(statistics.median(lat), 2),
        "latency_p95_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 2),
    }


def run_system(system, rows):
    return [system.check(r["text"], sender=r.get("sender") or None) for r in rows]


def throughput(system, rows, workers: int) -> float:
    texts = [(r["text"], r.get("sender") or None) for r in rows]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda t: system.check(t[0], sender=t[1]), texts))
    return round(len(texts) / (time.perf_counter() - started), 1)


def main() -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    traces = PROJECT / "traces" / "benchmark_traces.jsonl"
    traces.unlink(missing_ok=True)
    multi = Orchestrator(build_team(), trace_path=traces)
    single = SingleAgent(load_content_model())
    data = {name: load_rows(path) for name, path in DATASETS.items()}

    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "machine": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}, CPU only",
              "llm_used": False, "datasets": {}, "per_language": {}, "robustness": {}, "scalability": {}}
    for name, rows in data.items():
        report["datasets"][name] = {"multi_agent": score(rows, run_system(multi, rows)),
                                    "single_agent": score(rows, run_system(single, rows))}

    # per-language view on everything except the stress set
    pooled = [r for n in ("test", "shifted", "independent") for r in data[n]]
    m_res, s_res = run_system(multi, pooled), run_system(single, pooled)
    for lang in sorted({r["language"] for r in pooled}):
        idx = [i for i, r in enumerate(pooled) if r["language"] == lang]
        rows = [pooled[i] for i in idx]
        report["per_language"][lang] = {"multi_agent": score(rows, [m_res[i] for i in idx]),
                                        "single_agent": score(rows, [s_res[i] for i in idx])}

    # robustness: inject failures (each attempt fails with this probability; 2 attempts allowed)
    everything = [r for rows in data.values() for r in rows]
    for rate in (0.3, 0.6):
        fail_multi = Orchestrator(build_team(), fail={a: rate for a in ("content", "tactics", "link_sender",
                                                                         "campaign", "drift", "language")}, seed=7)
        fail_single = SingleAgent(load_content_model(), fail=rate, seed=7)
        report["robustness"][f"failure_rate_{rate}"] = {
            "multi_agent": score(everything, run_system(fail_multi, everything)),
            "single_agent": score(everything, run_system(fail_single, everything))}

    # scalability and cost on this machine
    for workers in (1, 4):
        report["scalability"][f"workers_{workers}"] = {"multi_agent_msgs_per_s": throughput(multi, everything, workers),
                                                       "single_agent_msgs_per_s": throughput(single, everything, workers)}
    best = report["scalability"]["workers_4"]["multi_agent_msgs_per_s"]
    seconds_per_month = 30 * 24 * 3600
    report["cost"] = {"server_usd_per_month": SERVER_USD_PER_MONTH,
                      "multi_agent_capacity_msgs_per_month": int(best * seconds_per_month),
                      "multi_agent_usd_per_1000_msgs_at_full_load": round(SERVER_USD_PER_MONTH / (best * seconds_per_month) * 1000, 6),
                      "note": "compute only; WhatsApp reply fees and reviewer time are separate"}
    (REPORTS / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORTS / "benchmark.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def to_markdown(r: dict) -> str:
    out = [f"# Benchmark: multi-agent vs single-agent", "",
           f"Generated {r['generated_at']} on {r['machine']}. LLM used: {r['llm_used']}.",
           "Produced by `python project/main.py benchmark`; nothing in this file is edited by hand.", "",
           "| Dataset | System | n | Scam caught | Unsafe miss | False alarm | Review load | Decided bal. acc. | p50 ms |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name, systems in r["datasets"].items():
        for sys_name, m in systems.items():
            out.append(f"| {name} | {sys_name} | {m['n']} | {pct(m['scam_caught'])} | {pct(m['unsafe_miss'])} | "
                       f"{pct(m['false_alarm'])} | {pct(m['review_load'])} | {pct(m['decided_balanced_accuracy'])} | "
                       f"{m['latency_p50_ms']} |")
    out += ["", "## Per language (test + shifted + independent)", "",
            "| Language | System | n | Scam caught | Unsafe miss | False alarm | Review load |", "|---|---|---|---|---|---|---|"]
    for lang, systems in r["per_language"].items():
        for sys_name, m in systems.items():
            out.append(f"| {lang} | {sys_name} | {m['n']} | {pct(m['scam_caught'])} | {pct(m['unsafe_miss'])} | "
                       f"{pct(m['false_alarm'])} | {pct(m['review_load'])} |")
    out += ["", "## Robustness under injected failures (all datasets)", "",
            "| Failure rate per attempt | System | Unsafe miss | No answer | Scam caught | False alarm |", "|---|---|---|---|---|---|"]
    for rate, systems in r["robustness"].items():
        for sys_name, m in systems.items():
            out.append(f"| {rate.split('_')[-1]} | {sys_name} | {pct(m['unsafe_miss'])} | {pct(m['no_answer'])} | "
                       f"{pct(m['scam_caught'])} | {pct(m['false_alarm'])} |")
    out += ["", "## Throughput", ""]
    for k, v in r["scalability"].items():
        out.append(f"- {k}: multi-agent {v['multi_agent_msgs_per_s']} msg/s, single-agent {v['single_agent_msgs_per_s']} msg/s")
    out += ["", "## Test conditions and limitations", "",
            f"- Machine: {r['machine']}. Same messages, same training data, same content model and thresholds for both systems.",
            "- Sample sizes are the `n` column above. All data is synthetic or hand-written; these results show the design works, "
            "not accuracy on real traffic.",
            "- The stress set was written while the link rules were designed, so it is not an unbiased estimate.",
            "- Failure injection: each agent attempt fails with the stated probability; 2 attempts per agent (and per single-agent call).",
            "- Human baseline: not yet collected (see `python project/main.py human-sheet`).",
            "- The LLM rephraser was off for every run (`llm_used: false`)."]
    c = r["cost"]
    out += ["", f"Compute cost at full load on a USD {c['server_usd_per_month']}/month server: "
                f"USD {c['multi_agent_usd_per_1000_msgs_at_full_load']} per 1,000 messages ({c['note']})."]
    return "\n".join(out) + "\n"
