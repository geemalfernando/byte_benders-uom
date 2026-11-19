"""Shared state and message format used by every agent.

Agents never call each other directly. Each one reads the blackboard (the shared state for one
message), does its job, and posts an AgentMessage. The orchestrator decides who runs when, and
every post is written to a JSONL trace so judges can replay what each agent saw and decided.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AgentMessage:
    agent: str                       # who posted it
    status: str = "ok"               # ok | skipped | timeout | error | fallback
    risk: float | None = None        # 0 = clearly legitimate, 1 = clearly scam, None = no opinion
    confidence: float | None = None  # how sure the agent is of its own risk score
    evidence: list[str] = field(default_factory=list)   # short machine-readable reasons
    data: dict[str, Any] = field(default_factory=dict)  # anything other agents may need
    latency_ms: float = 0.0
    attempts: int = 1


class Blackboard:
    """Per-message shared state. Thread-safe because specialists run in parallel."""

    def __init__(self, text: str, sender: str | None = None, channel: str = "cli"):
        self.message_id = uuid.uuid4().hex[:12]
        self.raw_text = text                # only the Intake agent reads this
        self.sender = sender
        self.channel = channel
        self.text: str | None = None        # redacted text, set by the Intake agent
        self.posts: dict[str, AgentMessage] = {}
        self.events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._t0 = time.perf_counter()

    def post(self, message: AgentMessage) -> None:
        with self._lock:
            self.posts[message.agent] = message
            self.events.append({"t_ms": round((time.perf_counter() - self._t0) * 1000, 2),
                                "type": "post", **asdict(message)})

    def log(self, kind: str, **details: Any) -> None:
        with self._lock:
            self.events.append({"t_ms": round((time.perf_counter() - self._t0) * 1000, 2),
                                "type": kind, **details})

    def get(self, agent: str) -> AgentMessage | None:
        return self.posts.get(agent)

    def ok(self, agent: str) -> AgentMessage | None:
        message = self.posts.get(agent)
        return message if message and message.status in ("ok", "fallback") else None

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000


class TraceWriter:
    """Append-only JSONL trace: one line per message, with every agent post and decision.

    Traces contain the redacted text only, never the raw message (privacy layer)."""

    def __init__(self, path: Path | None):
        self.path = path
        self._lock = threading.Lock()
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, board: Blackboard, result: dict[str, Any]) -> None:
        if not self.path:
            return
        record = {
            "message_id": board.message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "channel": board.channel,
            "redacted_text": board.text,
            "events": board.events,
            "result": result,
        }
        with self._lock, open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
