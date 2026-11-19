"""Human-in-the-loop learning: review queue -> labels -> blocklist + gated retraining -> rollback.

    review            list UNCERTAIN messages waiting for a human
    label ID LABEL    record a reviewer decision (scam | legitimate)
    retrain           train a candidate with the labels, promote it only if it passes the gate
    rollback          restore the previous model version

The gate is the pre-existing rakshaka.modeling.retrain_gate: the candidate's Content agent may not
lose more than 1 point of balanced accuracy, scam recall or legitimate recall on the held-out
validation + test templates. Scam-labelled messages also add their link domains to the Link &
Sender agent's blocklist, which takes effect immediately, without retraining.
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib

from .agents import URL_RE, LinkSenderAgent
from .training import BLOCKLIST, DATA, MODELS, PROJECT, REVIEWED, load_rows, train

ROOT = PROJECT.parent
sys.path.insert(0, str(ROOT))
from rakshaka.modeling import evaluate_classifier, retrain_gate  # noqa: E402  (pre-existing)

QUEUE = PROJECT / "runtime" / "review_queue.jsonl"
AUDIT = PROJECT / "runtime" / "model_audit.jsonl"
CANDIDATE, PREVIOUS = PROJECT / "models_candidate", PROJECT / "models_previous"


def _queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    return [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _audit(event: str, **details) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "event": event, **details}, ensure_ascii=False) + "\n")


def pending() -> list[dict]:
    return [item for item in _queue() if item.get("label") is None]


def label(message_id: str, value: str) -> dict:
    value = value.strip().lower()
    if value not in ("scam", "legitimate"):
        raise ValueError("label must be 'scam' or 'legitimate'")
    items = _queue()
    match = next((i for i in items if i["message_id"] == message_id and i.get("label") is None), None)
    if match is None:
        raise KeyError(f"no pending review item {message_id}")
    match["label"] = value
    QUEUE.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")

    new_file = not REVIEWED.exists()
    with open(REVIEWED, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(["text", "label", "language"])
        writer.writerow([match["redacted_text"], value, "reviewed"])

    added = []
    if value == "scam":   # the blocklist grows at once: no retraining needed for known scam domains
        current = set(BLOCKLIST.read_text(encoding="utf-8").split()) if BLOCKLIST.exists() else set()
        for m in URL_RE.finditer(match["redacted_text"]):
            domain = LinkSenderAgent.registered_domain(m.group(1).lower())
            score, evidence = LinkSenderAgent().check_host(domain)
            if domain not in current and not any(e.startswith("official_domain") for e in evidence):
                added.append(domain)
        if added:
            BLOCKLIST.parent.mkdir(parents=True, exist_ok=True)
            with open(BLOCKLIST, "a", encoding="utf-8") as handle:
                handle.write("".join(d + "\n" for d in added))
    _audit("LABEL", message_id=message_id, label=value, blocklisted=added)
    return {"message_id": message_id, "label": value, "blocklisted": added}


def _gate_rows() -> list[dict]:
    return load_rows(DATA / "val.csv") + load_rows(DATA / "test.csv")


def retrain() -> dict:
    if not REVIEWED.exists():
        return {"status": "skipped", "reason": "no reviewed labels yet"}
    shutil.rmtree(CANDIDATE, ignore_errors=True)
    meta = train(out_dir=CANDIDATE)
    current = evaluate_classifier(joblib.load(MODELS / "agents.joblib")["content"], _gate_rows())
    candidate = evaluate_classifier(joblib.load(CANDIDATE / "agents.joblib")["content"], _gate_rows())
    accepted, reasons = retrain_gate(current, candidate)
    summary = {"candidate_version": meta["version"], "n_reviewed": meta["n_reviewed"],
               "current_balanced_accuracy": round(current["balanced_accuracy"], 4),
               "candidate_balanced_accuracy": round(candidate["balanced_accuracy"], 4)}
    if accepted:
        shutil.rmtree(PREVIOUS, ignore_errors=True)
        shutil.copytree(MODELS, PREVIOUS)
        for f in CANDIDATE.iterdir():
            shutil.copy2(f, MODELS / f.name)
        shutil.rmtree(CANDIDATE, ignore_errors=True)
        _audit("RETRAIN_DEPLOYED", **summary)
        return {"status": "deployed", **summary}
    _audit("RETRAIN_REJECTED", reasons=reasons, **summary)
    return {"status": "rejected", "reasons": reasons, **summary}


def rollback() -> dict:
    if not (PREVIOUS / "agents.joblib").exists():
        return {"status": "skipped", "reason": "no previous version"}
    swap = PROJECT / "models_swap"
    shutil.rmtree(swap, ignore_errors=True)
    shutil.copytree(MODELS, swap)
    for f in PREVIOUS.iterdir():
        shutil.copy2(f, MODELS / f.name)
    shutil.rmtree(PREVIOUS)
    swap.rename(PREVIOUS)
    version = json.loads((MODELS / "meta.json").read_text(encoding="utf-8")).get("version")
    _audit("ROLLBACK", restored=version)
    return {"status": "rolled_back", "live_version": version}
