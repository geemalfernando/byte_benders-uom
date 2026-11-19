"""Rakshaka AI: multi-agent scam-message checker. Main entry point.

    python project/main.py train                       # (re)train every learned agent
    python project/main.py check "message text" [--sender SLKPOST] [--json]
    python project/main.py demo                        # samples/input/*.txt -> samples/output/*.json
    python project/main.py benchmark                   # multi-agent vs single-agent -> reports/
    python project/main.py human-sheet                 # blind sheet for the human baseline
    python project/main.py human-score FILE            # score a filled human sheet
    python project/main.py serve [--port 8080]         # JSON API: POST /check, GET /health
    python project/main.py review                      # UNCERTAIN messages waiting for a human
    python project/main.py label ID scam|legitimate    # reviewer decision (+ blocklist for scam links)
    python project/main.py retrain                     # gated retraining with reviewed labels
    python project/main.py rollback                    # restore the previous model version

Models train automatically on first use. Traces of every agent decision go to project/traces/,
UNCERTAIN messages (redacted) go to project/runtime/review_queue.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

from rakshaka_agents import benchmark, learning, llm  # noqa: E402
from rakshaka_agents.orchestrator import Orchestrator  # noqa: E402
from rakshaka_agents.training import build_team, train  # noqa: E402

TRACES = PROJECT / "traces" / "traces.jsonl"
REVIEW = PROJECT / "runtime" / "review_queue.jsonl"


def make_orchestrator() -> Orchestrator:
    return Orchestrator(build_team(llm=llm.from_env()), trace_path=TRACES, review_path=REVIEW)


def show(result: dict) -> None:
    print(f"\nVerdict : {result['verdict']}  (score {result['score']}, language {result['language']})")
    print(f"Rules   : {', '.join(result['rules_fired']) or '-'}")
    print("Agents  :")
    for name, a in result["agents"].items():
        risk = "" if a["risk"] is None else f" risk={a['risk']}"
        print(f"  - {name:<12} {a['status']:<8}{risk:<12} {', '.join(a['evidence'][:4])}")
    print(f"\nReply ({result['reply_language']}):\n{result['reply']}")
    print(f"\n{result['latency_ms']} ms | trace id {result['message_id']} in {TRACES.relative_to(PROJECT.parent)}")


def cmd_demo() -> None:
    orch = make_orchestrator()
    out_dir = PROJECT / "samples" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted((PROJECT / "samples" / "input").glob("*.txt")):
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        sender = lines[0][len("SENDER:"):].strip() if lines and lines[0].startswith("SENDER:") else None
        text = "\n".join(lines[1:] if sender else lines)
        result = orch.check(text, sender=sender, channel="demo")
        (out_dir / f"{path.stem}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{path.name:<32} {result['verdict']:<12} {', '.join(result['rules_fired'])}")


CHECKS_PER_MINUTE = int(os.environ.get("CHECKS_PER_MINUTE", "60"))


class RateLimiter:
    """Sliding one-minute window per client address, so one caller cannot flood the agents."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self.lock:
            window = self.hits[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return False
            window.append(now)
            return True


class Handler(BaseHTTPRequestHandler):
    orchestrator: Orchestrator = None
    limiter = RateLimiter(CHECKS_PER_MINUTE)

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        self._send(200, {"status": "ok"}) if self.path == "/health" else self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/check":
            return self._send(404, {"error": "not found"})
        if not self.limiter.allow(self.client_address[0]):
            return self._send(429, {"error": f"rate limit: {CHECKS_PER_MINUTE} checks per minute"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 8192:
                raise ValueError("body must be 1-8192 bytes")
            payload = json.loads(self.rfile.read(length))
            result = self.orchestrator.check(str(payload["text"]), sender=payload.get("sender"), channel="api")
            self._send(200, result)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self._send(400, {"error": str(error)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Rakshaka AI multi-agent scam checker")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train")
    c = sub.add_parser("check")
    c.add_argument("text")
    c.add_argument("--sender")
    c.add_argument("--json", action="store_true")
    sub.add_parser("demo")
    sub.add_parser("benchmark")
    sub.add_parser("human-sheet")
    h = sub.add_parser("human-score")
    h.add_argument("file", type=Path)
    sub.add_parser("review")
    lb = sub.add_parser("label")
    lb.add_argument("message_id")
    lb.add_argument("label", choices=["scam", "legitimate"])
    sub.add_parser("retrain")
    sub.add_parser("rollback")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if args.cmd == "train":
        print(json.dumps(train(), indent=2))
    elif args.cmd == "check":
        result = make_orchestrator().check(args.text, sender=args.sender)
        print(json.dumps(result, ensure_ascii=False, indent=2)) if args.json else show(result)
    elif args.cmd == "demo":
        cmd_demo()
    elif args.cmd == "benchmark":
        report = benchmark.main()
        print((PROJECT / "reports" / "benchmark.md").read_text(encoding="utf-8"))
    elif args.cmd == "human-sheet":
        path = benchmark.write_human_sheet(PROJECT / "reports" / "human_baseline" / "sheet.csv")
        print(f"Blind sheet: {path}\nAnswer key (keep away from raters): {path.with_name('sheet_key.csv')}")
    elif args.cmd == "human-score":
        print(json.dumps(benchmark.score_human(args.file), indent=2))
    elif args.cmd == "review":
        items = learning.pending()
        print(f"{len(items)} message(s) waiting for review")
        for item in items:
            print(f"\n[{item['message_id']}] score={item['score']} rules={','.join(item['rules']) or '-'}")
            print(f"  {item['redacted_text']}")
            print(f"  evidence: {', '.join(item['evidence'][:6]) or '-'}")
    elif args.cmd == "label":
        print(json.dumps(learning.label(args.message_id, args.label), ensure_ascii=False, indent=2))
    elif args.cmd == "retrain":
        print(json.dumps(learning.retrain(), indent=2))
    elif args.cmd == "rollback":
        print(json.dumps(learning.rollback(), indent=2))
    elif args.cmd == "serve":
        Handler.orchestrator = make_orchestrator()
        print(f"Rakshaka API on http://127.0.0.1:{args.port}  (POST /check, GET /health)")
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
