"""Arbiter (decision and conflict resolution) and Explainer (reply + output validation)."""
from __future__ import annotations

import numpy as np

from .blackboard import AgentMessage, Blackboard

# The link agent is deliberately NOT a stacker input: in the synthetic training data almost every
# legitimate message has no link, so a learned weight would mean "any link = scam". Link and
# sender intelligence acts through the explicit policy rules R1-R4 below instead.
SPECIALISTS = ("content", "tactics", "campaign")
SCAM_AT, SAFE_AT = 0.70, 0.30


def feature_vector(board: Blackboard) -> list[float]:
    """Stacker input. A skipped or failed agent contributes a neutral 0.5 plus a missing flag."""
    row = []
    for name in SPECIALISTS:
        message = board.ok(name)
        present = message is not None and message.risk is not None
        row += [message.risk if present else 0.5, 0.0 if present else 1.0]
    drift = board.ok("drift")
    row.append(drift.data["oov_ratio"] if drift else 0.5)
    return row


class ArbiterAgent:
    """Combines the specialists. A learned stacker gives a first score; an explicit policy then
    resolves conflicts and enforces the safety rule: never LIKELY_SAFE when unsure."""
    name = "arbiter"

    def __init__(self, stacker):
        self.stacker = stacker

    def run(self, board: Blackboard) -> AgentMessage:
        p = float(self.stacker.predict_proba([feature_vector(board)])[0][1])
        rules = []
        get = board.ok
        tactics = get("tactics").data["tactics"] if get("tactics") else []
        link_ev = get("link_sender").evidence if get("link_sender") else []
        content = get("content")

        # R1 credential or payment request + a way to act on it (link or number) = scam pattern
        if {"credential_request", "payment_request"} & set(tactics) and (
                any(e.startswith(("shortener", "lookalike", "brand_in", "risky_tld", "unknown_domain", "ip_",
                                  "blocklisted", "asks_to_call")) for e in link_ev)):
            p = max(p, 0.9)
            rules.append("R1_action_request_with_link_or_number")
        # R2 look-alike or blocklisted domain / sender is decisive whatever the wording says
        if any(e.startswith(("lookalike", "blocklisted", "brand_in_unofficial")) for e in link_ev):
            p = max(p, 0.85)
            rules.append("R2_impersonating_link_or_sender")
        # R3 official link and real-institution safety advice with no action request
        if any(e.startswith("official_domain") for e in link_ev) and not link_ev[1:] and \
                not ({"credential_request", "payment_request"} & set(tactics)):
            p = min(p, 0.5)
            rules.append("R3_official_domain_only")
        verdict = "SCAM" if p >= SCAM_AT else "LIKELY_SAFE" if p <= SAFE_AT else "UNCERTAIN"

        # R4 strong disagreement between specialists -> a human should look
        risks = [m.risk for n in ("content", "tactics", "link_sender") if (m := get(n)) and m.risk is not None]
        if verdict == "LIKELY_SAFE" and risks and max(risks) >= 0.7:
            verdict = "UNCERTAIN"
            rules.append("R4_specialists_disagree")
        # R5 unfamiliar wording -> the content score cannot be trusted to clear the message
        drift = get("drift")
        if verdict == "LIKELY_SAFE" and drift and drift.data["novel"]:
            verdict = "UNCERTAIN"
            rules.append("R5_novel_wording")
        # R6 a critical specialist failed -> no clearance without it
        if verdict == "LIKELY_SAFE" and content is None:
            verdict = "UNCERTAIN"
            rules.append("R6_content_agent_unavailable")
        # R8 degraded mode: a learned specialist failed and no hard rule fired -> a human decides,
        # in both directions (no clearance and no accusation on partial evidence)
        missing = [n for n in ("content", "tactics", "campaign") if get(n) is None]
        if missing and verdict == "SCAM" and not {"R1_action_request_with_link_or_number",
                                                  "R2_impersonating_link_or_sender"} & set(rules):
            verdict = "UNCERTAIN"
            rules.append("R8_degraded_mode:" + "+".join(missing))
        # R7 part of an emerging wave of similar unlabelled messages
        campaign = get("campaign")
        if verdict == "LIKELY_SAFE" and campaign and campaign.data.get("wave_size", 0) >= 2:
            verdict = "UNCERTAIN"
            rules.append("R7_emerging_wave")

        evidence = [e for n in ("link_sender", "tactics", "content", "campaign", "drift")
                    if (m := get(n)) for e in m.evidence]
        return AgentMessage(self.name, risk=p, confidence=abs(p - 0.5) * 2, evidence=rules,
                            data={"verdict": verdict, "score": round(p, 4), "rules": rules,
                                  "evidence": evidence, "human_review": verdict == "UNCERTAIN"})


# ---------------------------------------------------------------------------------------------
# Reply templates. Sinhala and Tamil drafts need native-speaker review before a pilot.
T = {
    "english": {
        "SCAM": "SCAM: this message shows the signs of a scam.",
        "UNCERTAIN": "NOT SURE: we could not confirm this message is safe. Treat it as suspicious.",
        "LIKELY_SAFE": "LIKELY SAFE: we found no scam signs, but stay careful.",
        "why": "Why: ",
        "do_SCAM": "What to do: do not click the link, call the number or pay. If you already shared card details or an OTP, call your bank on the number printed on your card now.",
        "do_UNCERTAIN": "What to do: do not click or pay yet. Check with the organisation using its official number. Our team will review this message.",
        "do_LIKELY_SAFE": "What to do: if anything still looks odd, call the organisation on its official number.",
        "footer": "Rakshaka never asks for your OTP, PIN or NIC.",
        "reasons": {
            "credential_request": "it asks for a code, PIN or personal details",
            "payment_request": "it asks you to pay a fee or send money",
            "reward_lure": "it promises a prize, loan or easy money",
            "threat_or_urgency": "it pressures you to act fast or threatens a block",
            "authority_impersonation": "it claims to come from a bank or government body",
            "lookalike": "the link imitates an official website",
            "shortener": "it hides the real website behind a short link",
            "risky_tld": "the website address is of a type often used by scammers",
            "asks_to_call": "it asks you to call or WhatsApp an unknown number",
            "campaign": "it matches a known scam campaign",
            "novel": "its wording is new to us",
            "official": "the only link goes to an official website",
            "safety_advice": "it contains the safety advice real institutions give",
        },
    },
    "sinhala": {
        "SCAM": "වංචාවක්: මෙම පණිවිඩයේ වංචාවක ලකුණු ඇත.",
        "UNCERTAIN": "විශ්වාස කළ නොහැක: මෙය ආරක්ෂිත බව තහවුරු කළ නොහැක. සැක සහිත ලෙස සලකන්න.",
        "LIKELY_SAFE": "බොහෝ විට ආරක්ෂිතයි: වංචා ලකුණු හමු නොවීය, නමුත් ප්‍රවේශම් වන්න.",
        "why": "හේතුව: ",
        "do_SCAM": "කළ යුත්තේ: සබැඳිය ඔබන්න, අංකයට අමතන්න හෝ මුදල් ගෙවන්න එපා. කාඩ්පත් විස්තර හෝ OTP දැනටමත් දුන්නා නම්, කාඩ්පතේ ඇති අංකයෙන් වහාම බැංකුවට අමතන්න.",
        "do_UNCERTAIN": "කළ යුත්තේ: තවම ඔබන්න හෝ ගෙවන්න එපා. ආයතනයේ නිල අංකයෙන් විමසන්න. අපේ කණ්ඩායම මෙය පරීක්ෂා කරයි.",
        "do_LIKELY_SAFE": "කළ යුත්තේ: තවමත් සැකයක් ඇත්නම්, ආයතනයේ නිල අංකයට අමතන්න.",
        "footer": "රක්ෂක කිසිවිටෙක ඔබගේ OTP, PIN හෝ හැඳුනුම්පත් අංකය ඉල්ලන්නේ නැත.",
        "reasons": {
            "credential_request": "එය කේතයක්, PIN අංකයක් හෝ පුද්ගලික විස්තර ඉල්ලයි",
            "payment_request": "එය ගාස්තුවක් ගෙවන්න හෝ මුදල් එවන්න කියයි",
            "reward_lure": "එය ත්‍යාගයක්, ණයක් හෝ පහසු මුදල් පොරොන්දු වෙයි",
            "threat_or_urgency": "එය ඉක්මන් කරන්න බල කරයි හෝ අවහිර කරන බව තර්ජනය කරයි",
            "authority_impersonation": "එය බැංකුවකින් හෝ රජයේ ආයතනයකින් බව කියයි",
            "lookalike": "සබැඳිය නිල වෙබ් අඩවියක් අනුකරණය කරයි",
            "shortener": "කෙටි සබැඳියකින් සැබෑ වෙබ් අඩවිය සඟවයි",
            "risky_tld": "වෙබ් ලිපිනය වංචාකරුවන් බොහෝ විට භාවිත කරන වර්ගයකි",
            "asks_to_call": "නොදන්නා අංකයකට අමතන්න හෝ WhatsApp කරන්න කියයි",
            "campaign": "එය දන්නා වංචා රැල්ලකට ගැළපේ",
            "novel": "එහි වචන අපට අලුත්",
            "official": "එකම සබැඳිය නිල වෙබ් අඩවියකට යයි",
            "safety_advice": "සැබෑ ආයතන දෙන ආරක්ෂක උපදෙස් එහි ඇත",
        },
    },
    "tamil": {
        "SCAM": "மோசடி: இந்தச் செய்தியில் மோசடியின் அறிகுறிகள் உள்ளன.",
        "UNCERTAIN": "உறுதியில்லை: இது பாதுகாப்பானது என உறுதிப்படுத்த முடியவில்லை. சந்தேகத்துடன் அணுகவும்.",
        "LIKELY_SAFE": "பெரும்பாலும் பாதுகாப்பானது: மோசடி அறிகுறிகள் இல்லை, ஆனால் கவனமாக இருங்கள்.",
        "why": "காரணம்: ",
        "do_SCAM": "செய்ய வேண்டியது: இணைப்பைத் திறக்கவோ, எண்ணை அழைக்கவோ, பணம் செலுத்தவோ வேண்டாம். அட்டை விவரங்கள் அல்லது OTP கொடுத்திருந்தால், அட்டையில் உள்ள எண்ணில் உடனே வங்கியை அழைக்கவும்.",
        "do_UNCERTAIN": "செய்ய வேண்டியது: இப்போது திறக்கவோ செலுத்தவோ வேண்டாம். நிறுவனத்தின் அதிகாரப்பூர்வ எண்ணில் சரிபார்க்கவும். எங்கள் குழு இதை ஆய்வு செய்யும்.",
        "do_LIKELY_SAFE": "செய்ய வேண்டியது: சந்தேகம் இருந்தால், நிறுவனத்தின் அதிகாரப்பூர்வ எண்ணை அழைக்கவும்.",
        "footer": "ரக்ஷக ஒருபோதும் உங்கள் OTP, PIN அல்லது NIC எண்ணைக் கேட்காது.",
        "reasons": {
            "credential_request": "இது குறியீடு, PIN அல்லது தனிப்பட்ட விவரங்களைக் கேட்கிறது",
            "payment_request": "இது கட்டணம் செலுத்த அல்லது பணம் அனுப்பச் சொல்கிறது",
            "reward_lure": "இது பரிசு, கடன் அல்லது எளிதான பணத்தை வாக்களிக்கிறது",
            "threat_or_urgency": "இது அவசரப்படுத்துகிறது அல்லது முடக்குவதாக மிரட்டுகிறது",
            "authority_impersonation": "இது வங்கி அல்லது அரசு நிறுவனத்திடமிருந்து வந்ததாகக் கூறுகிறது",
            "lookalike": "இணைப்பு அதிகாரப்பூர்வ இணையதளத்தைப் போலியாக்குகிறது",
            "shortener": "குறுகிய இணைப்பு உண்மையான இணையதளத்தை மறைக்கிறது",
            "risky_tld": "இணைய முகவரி மோசடியாளர்கள் அடிக்கடி பயன்படுத்தும் வகை",
            "asks_to_call": "தெரியாத எண்ணை அழைக்க அல்லது WhatsApp செய்யச் சொல்கிறது",
            "campaign": "இது அறியப்பட்ட மோசடி அலையுடன் பொருந்துகிறது",
            "novel": "இதன் சொற்கள் எங்களுக்குப் புதியவை",
            "official": "ஒரே இணைப்பு அதிகாரப்பூர்வ இணையதளத்துக்குச் செல்கிறது",
            "safety_advice": "உண்மையான நிறுவனங்கள் தரும் பாதுகாப்பு அறிவுரை இதில் உள்ளது",
        },
    },
}

EVIDENCE_TO_REASON = [
    ("lookalike", "lookalike"), ("brand_in_unofficial", "lookalike"), ("blocklisted", "lookalike"),
    ("tactic:credential_request", "credential_request"), ("tactic:payment_request", "payment_request"),
    ("tactic:reward_lure", "reward_lure"), ("tactic:threat_or_urgency", "threat_or_urgency"),
    ("tactic:authority_impersonation", "authority_impersonation"), ("shortener", "shortener"),
    ("risky_tld", "risky_tld"), ("asks_to_call", "asks_to_call"), ("matches_campaign", "campaign"),
    ("emerging_wave", "campaign"), ("novel_wording", "novel"), ("official_domain", "official"),
    ("official_sender", "official"), ("safety_advice", "safety_advice"),
]
RISK_REASONS = {"lookalike", "credential_request", "payment_request", "reward_lure", "threat_or_urgency",
                "authority_impersonation", "shortener", "risky_tld", "asks_to_call", "campaign"}


class ExplainerAgent:
    """Turns the decision into a short reply in the user's language, citing only evidence that
    other agents actually posted. An optional LLM can rephrase it; the validator rejects any
    reply that contradicts the verdict or cites reasons nobody found, and falls back to the
    template."""
    name = "explainer"

    def __init__(self, llm=None):
        self.llm = llm

    def reasons_for(self, verdict: str, evidence: list[str]) -> list[str]:
        keys = []
        for prefix, key in EVIDENCE_TO_REASON:
            if any(e.startswith(prefix) for e in evidence) and key not in keys:
                keys.append(key)
        if verdict == "SCAM":
            keys = [k for k in keys if k in RISK_REASONS] or keys
        elif verdict == "LIKELY_SAFE":
            keys = [k for k in keys if k not in RISK_REASONS]
        return keys[:3]

    def template_reply(self, verdict: str, keys: list[str], lang: str) -> str:
        t = T.get(lang, T["english"])
        lines = [t[verdict]]
        if keys:
            lines.append(t["why"] + "; ".join(t["reasons"][k] for k in keys) + ".")
        lines += [t[f"do_{verdict}"], t["footer"]]
        return "\n".join(lines)

    @staticmethod
    def validate(reply: str, verdict: str, keys: list[str], lang: str) -> list[str]:
        problems = []
        t = T.get(lang, T["english"])
        if not reply.startswith(t[verdict]):
            problems.append("verdict_line_mismatch")
        if verdict != "LIKELY_SAFE" and t["LIKELY_SAFE"] in reply:
            problems.append("says_safe_when_not_safe")
        if t["footer"] not in reply:
            problems.append("missing_safety_footer")
        cited = [k for k, v in t["reasons"].items() if v in reply]
        if any(k not in keys for k in cited):
            problems.append("cites_unfound_evidence")
        if len(reply) > 700:
            problems.append("too_long")
        return problems

    def run(self, board: Blackboard) -> AgentMessage:
        decision = board.get("arbiter").data
        lang_msg = board.ok("language")
        lang = lang_msg.data["reply_language"] if lang_msg else "english"
        verdict = decision["verdict"]
        keys = self.reasons_for(verdict, decision["evidence"])
        reply, source = self.template_reply(verdict, keys, lang), "template"
        problems: list[str] = []
        if self.llm is not None:
            try:
                candidate = self.llm.rephrase(reply, lang)
                problems = self.validate(candidate, verdict, keys, lang)
                if not problems:
                    reply, source = candidate, "llm"
            except Exception as error:   # LLM down or slow -> template
                problems = [f"llm_error:{type(error).__name__}"]
        final_problems = self.validate(reply, verdict, keys, lang)
        return AgentMessage(self.name, status="ok" if not final_problems else "error",
                            evidence=[f"reason:{k}" for k in keys],
                            data={"reply": reply, "reply_language": lang, "source": source,
                                  "rejected_llm_reply": problems, "validation": final_problems or "passed"})
