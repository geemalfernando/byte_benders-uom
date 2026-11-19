"""Orchestrator: plans which agents run, runs specialists in parallel with timeouts, retries and
fallbacks, then hands the blackboard to the arbiter and the explainer.

Flow:  intake -> language -> plan -> [content | tactics | link_sender | campaign | drift] (parallel)
       -> arbiter -> explainer -> (UNCERTAIN) human review queue -> trace
"""
from __future__ import annotations

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import replace
from pathlib import Path
from typing import Any

from .blackboard import AgentMessage, Blackboard, TraceWriter

AGENT_TIMEOUT_S = 2.0
MAX_ATTEMPTS = 2


class Orchestrator:
    def __init__(self, agents: dict[str, Any], trace_path: Path | None = None,
                 review_path: Path | None = None, fail: dict[str, float] | None = None, seed: int = 0):
        self.agents = agents
        self.trace = TraceWriter(trace_path)
        self.review_path = review_path
        self.fail = fail or {}                       # failure injection for robustness tests
        self.rng = random.Random(seed)
        # two pools: steps wait on agent calls, so they must not share workers (no deadlock)
        self.pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="agent")
        self.step_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="step")

    # ------------------------------------------------------------------ helpers
    def _call(self, name: str, board: Blackboard) -> AgentMessage:
        agent = self.agents[name]
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                if self.rng.random() < self.fail.get(name, 0.0):
                    raise RuntimeError(f"injected failure in {name}")
                future = self.pool.submit(agent.run, board)
                message = future.result(timeout=AGENT_TIMEOUT_S)
                return replace(message, latency_ms=round((time.perf_counter() - started) * 1000, 2),
                               attempts=attempt)
            except FutureTimeout:
                last_error = "timeout"
            except Exception as error:  # noqa: BLE001 - any agent failure is contained here
                last_error = f"{type(error).__name__}: {error}"
            board.log("retry" if attempt < MAX_ATTEMPTS else "agent_failed", agent=name, error=last_error)
        return AgentMessage(name, status="timeout" if last_error == "timeout" else "error",
                            evidence=[f"failed:{last_error}"], attempts=MAX_ATTEMPTS)

    def plan(self, board: Blackboard) -> list[str]:
        """Adaptive routing: the link agent only runs when there is something to check."""
        intake = board.get("intake").data
        steps = ["content", "tactics", "campaign", "drift"]
        if intake["links"] or intake["phones"] or intake["sender"]:
            steps.insert(2, "link_sender")
        else:
            board.post(AgentMessage("link_sender", status="skipped", evidence=["no_links_or_numbers"]))
        board.log("plan", steps=steps)
        return steps

    # ------------------------------------------------------------------ main entry
    def check(self, text: str, sender: str | None = None, channel: str = "cli") -> dict[str, Any]:
        board = Blackboard(text, sender=sender, channel=channel)
        intake = self._call("intake", board)
        board.post(intake)
        if intake.status != "ok":
            return self._finish(board, {"verdict": "ERROR", "error": intake.evidence})

        board.post(self._call("language", board))
        steps = self.plan(board)
        futures = {name: self.step_pool.submit(self._call, name, board) for name in steps}
        for name, future in futures.items():
            board.post(future.result())

        arbiter = self._call("arbiter", board)
        if arbiter.status != "ok":     # fallback: never clear a message without the arbiter
            arbiter = AgentMessage("arbiter", status="fallback", evidence=["arbiter_failed"],
                                   data={"verdict": "UNCERTAIN", "score": None, "rules": ["F1_arbiter_fallback"],
                                         "evidence": [], "human_review": True})
        board.post(arbiter)
        explainer = self._call("explainer", board)
        if explainer.status != "ok":
            explainer = AgentMessage("explainer", status="fallback",
                                     data={"reply": "NOT SURE: please treat this message as suspicious and check "
                                                    "with the organisation on its official number.",
                                           "reply_language": "english", "source": "fallback"})
        board.post(explainer)

        decision = arbiter.data
        campaign = board.ok("campaign")
        if decision["verdict"] == "UNCERTAIN" and campaign and "_vec" in campaign.data:
            self.agents["campaign"].remember(campaign.data["_vec"])
        result = {
            "message_id": board.message_id,
            "verdict": decision["verdict"],
            "score": decision["score"],
            "reply": explainer.data["reply"],
            "reply_language": explainer.data["reply_language"],
            "language": board.ok("language").data["language"] if board.ok("language") else "unknown",
            "rules_fired": decision["rules"],
            "evidence": decision["evidence"],
            "human_review": decision["human_review"],
            "agents": {n: {"status": m.status, "risk": None if m.risk is None else round(m.risk, 3),
                           "evidence": m.evidence, "latency_ms": m.latency_ms, "attempts": m.attempts}
                       for n, m in board.posts.items()},
        }
        if decision["human_review"]:
            self._queue_for_review(board, result)
        return self._finish(board, result)

    def _finish(self, board: Blackboard, result: dict[str, Any]) -> dict[str, Any]:
        result["latency_ms"] = round(board.elapsed_ms(), 2)
        self.trace.write(board, result)
        return result

    def _queue_for_review(self, board: Blackboard, result: dict[str, Any]) -> None:
        if not self.review_path:
            return
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        item = {"message_id": board.message_id, "redacted_text": board.text, "score": result["score"],
                "rules": result["rules_fired"], "evidence": result["evidence"], "label": None}
        with open(self.review_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
