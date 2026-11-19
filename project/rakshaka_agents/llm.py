"""Optional LLM backend for the Explainer (rephrasing only). Off unless a key is set.

The LLM never decides the verdict: it only rewords the template reply, and the Explainer's
validator rejects any reply that changes the verdict, drops the safety footer or cites reasons
no agent found. Reported benchmarks in docs/ were run WITHOUT an LLM.

Environment: ANTHROPIC_API_KEY (and optionally RAKSHAKA_LLM_MODEL). Keys are read from the
environment only and never written to logs or traces.
"""
from __future__ import annotations

import os

import requests

PROMPT = (
    "Rewrite this message so an elderly reader understands it easily. Keep the same language "
    "({lang}). Keep the first line and the last line exactly as they are. Do not add new reasons, "
    "links or phone numbers. Reply with the rewritten message only.\n\n{text}"
)


class AnthropicRephraser:
    def __init__(self, api_key: str, model: str, timeout: float = 1.5):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def rephrase(self, text: str, lang: str) -> str:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": self.model, "max_tokens": 400,
                  "messages": [{"role": "user", "content": PROMPT.format(lang=lang, text=text)}]},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return "".join(part.get("text", "") for part in response.json()["content"]).strip()


def from_env():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return AnthropicRephraser(key, os.environ.get("RAKSHAKA_LLM_MODEL", "claude-haiku-5-5"))
