"""Single-agent baseline: one model reads the message and decides, in one pass.

For a fair comparison it gets the same training data, the same content model (TF-IDF char +
word n-grams, logistic regression), the same three-way verdict thresholds and the same retry
budget. What it lacks is what the multi-agent design adds: language routing, link and sender
checks, tactic detection, campaign memory, a novelty sentinel, a conflict-resolving arbiter and
a validated multilingual reply.
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rakshaka.modeling import preprocess_text  # noqa: E402

from .decision import SAFE_AT, SCAM_AT  # noqa: E402

MAX_ATTEMPTS = 2


class SingleAgent:
    name = "single_agent"

    def __init__(self, model, fail: float = 0.0, seed: int = 0):
        self.model = model
        self.fail = fail
        self.rng = random.Random(seed)

    def check(self, text: str, sender: str | None = None) -> dict:
        started = time.perf_counter()
        for _ in range(MAX_ATTEMPTS):
            try:
                if self.rng.random() < self.fail:
                    raise RuntimeError("injected failure")
                classes = list(self.model.classes_)
                p = float(self.model.predict_proba([preprocess_text(text)])[0][classes.index("scam")])
                verdict = "SCAM" if p >= SCAM_AT else "LIKELY_SAFE" if p <= SAFE_AT else "UNCERTAIN"
                reply = {"SCAM": "SCAM: this looks like a scam. Do not click or pay.",
                         "UNCERTAIN": "NOT SURE: treat this message as suspicious.",
                         "LIKELY_SAFE": "LIKELY SAFE: no scam signs found."}[verdict]
                return {"verdict": verdict, "score": round(p, 4), "reply": reply, "reply_language": "english",
                        "human_review": verdict == "UNCERTAIN",
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
            except Exception:  # noqa: BLE001
                continue
        return {"verdict": "ERROR", "score": None, "reply": "", "reply_language": None, "human_review": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
