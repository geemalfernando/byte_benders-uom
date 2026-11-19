"""Tests for the multi-agent layer (project/rakshaka_agents). Run: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))

from rakshaka_agents.agents import IntakeAgent, LinkSenderAgent, TacticsAgent  # noqa: E402
from rakshaka_agents.blackboard import Blackboard  # noqa: E402
from rakshaka_agents.decision import ExplainerAgent  # noqa: E402
from rakshaka_agents.orchestrator import Orchestrator  # noqa: E402
from rakshaka_agents.training import build_team  # noqa: E402


class IntakeTests(unittest.TestCase):
    def test_redacts_nic_and_card_before_other_agents(self):
        board = Blackboard("My NIC 200012345678 and card 4111 1111 1111 1111, call 0771234567")
        message = IntakeAgent().run(board)
        self.assertNotIn("200012345678", board.text)
        self.assertNotIn("4111", board.text)
        self.assertIn("[NIC]", board.text)
        self.assertEqual(len(message.data["phones"]), 1)


class LinkTests(unittest.TestCase):
    def test_official_domain_is_low_risk_and_lookalike_high(self):
        agent = LinkSenderAgent()
        self.assertEqual(agent.check_host("www.boc.lk")[0], 0.0)
        self.assertGreaterEqual(agent.check_host("b0c-secure.com")[0], 0.7)
        self.assertGreaterEqual(agent.check_host("slpost-lk.top")[0], 0.8)


class TacticsTests(unittest.TestCase):
    def run_text(self, text):
        board = Blackboard(text)
        IntakeAgent().run(board)
        return TacticsAgent().run(board)

    def test_safety_advice_cancels_credential_cue(self):
        self.assertNotIn("credential_request", self.run_text("Your OTP is 123456. Never share this OTP.").data["tactics"])
        self.assertIn("credential_request", self.run_text("Send the OTP you received to 0771234567").data["tactics"])


class ExplainerTests(unittest.TestCase):
    def test_validator_rejects_reply_that_contradicts_verdict(self):
        explainer = ExplainerAgent()
        good = explainer.template_reply("SCAM", ["lookalike"], "english")
        self.assertEqual(explainer.validate(good, "SCAM", ["lookalike"], "english"), [])
        bad = good.replace("SCAM: this message shows the signs of a scam.", "LIKELY SAFE: we found no scam signs, but stay careful.")
        self.assertIn("verdict_line_mismatch", explainer.validate(bad, "SCAM", ["lookalike"], "english"))
        self.assertIn("cites_unfound_evidence", explainer.validate(good, "SCAM", [], "english"))


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.team = build_team()

    def test_lookalike_link_is_scam_and_traced(self):
        result = Orchestrator(self.team).check("BOC Alert: card locked. Unlock at b0c-secure.com now", sender="BOCALERT")
        self.assertEqual(result["verdict"], "SCAM")
        self.assertIn("R2_impersonating_link_or_sender", result["rules_fired"])

    def test_link_agent_skipped_when_nothing_to_check(self):
        result = Orchestrator(self.team).check("Amma mama 7ta gedara ennam")
        self.assertEqual(result["agents"]["link_sender"]["status"], "skipped")

    def test_failures_never_clear_a_message(self):
        orch = Orchestrator(self.team, fail={"content": 1.0, "tactics": 1.0, "campaign": 1.0})
        result = orch.check("Hi, are we still meeting at 5 today?")
        self.assertNotEqual(result["verdict"], "LIKELY_SAFE")
        self.assertEqual(result["agents"]["content"]["status"], "error")


class RateLimitTests(unittest.TestCase):
    def test_limiter_blocks_after_quota(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))
        from main import RateLimiter
        limiter = RateLimiter(2)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))


if __name__ == "__main__":
    unittest.main()
