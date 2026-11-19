"""The specialist agents. Each agent reads the blackboard and posts one AgentMessage.

Agent             Kind                         Needs
intake            privacy + parsing            raw text (the only agent that sees it)
language          learned (char n-gram LR)     redacted text
content           learned (TF-IDF LR)          redacted text, language
tactics           multilingual cue model       redacted text
link_sender       URL / sender intelligence    links, phones, sender from intake
campaign          nearest-campaign retrieval   redacted text
drift             novelty sentinel             content agent's vocabulary
arbiter           learned stacker + policy     every specialist post
explainer         reply writer + validator     arbiter decision, evidence, language
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import deque
from urllib.parse import urlparse

import numpy as np

from . import lexicons as lx
from .blackboard import AgentMessage, Blackboard

SINHALA = re.compile(r"[඀-෿]")
TAMIL = re.compile(r"[஀-௿]")
URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}|\d{1,3}(?:\.\d{1,3}){3})"
    r"(?::\d+)?(/[^\s]*)?", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+94|0)\s?\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)|07X-XXXXXXX|011-XXXXXXX")
NIC_RE = re.compile(r"(?<!\d)(?:\d{9}[vVxX]|\d{12})(?!\d)")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
NOT_DOMAINS = {"rs.", "e.g", "i.e"}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()


def has_cue(text_cf: str, cue: str) -> bool:
    if cue.isascii() and len(cue) <= 4:           # short Latin cues must be whole words (pin, otp)
        return re.search(r"(?<![a-z])" + re.escape(cue) + r"(?![a-z])", text_cf) is not None
    return cue in text_cf


# --------------------------------------------------------------------------------------------
class IntakeAgent:
    """Privacy first: redacts NIC, card numbers and emails, hashes the message, extracts links,
    phone numbers and the sender. Downstream agents only ever see the redacted text."""
    name = "intake"

    def run(self, board: Blackboard) -> AgentMessage:
        raw = normalize(board.raw_text)
        if not raw:
            raise ValueError("empty message")
        redactions = {}
        text = raw
        for label, pattern in (("NIC", NIC_RE), ("CARD", CARD_RE), ("EMAIL", EMAIL_RE)):
            text, n = pattern.subn(f"[{label}]", text)
            if n:
                redactions[label] = n
        links = []
        for match in URL_RE.finditer(text):
            host = match.group(1).lower()
            if any(host.startswith(x) for x in NOT_DOMAINS) or host.replace(".", "").isdigit() and "." not in host:
                continue
            if re.fullmatch(r"[\d.]+", host) and host.count(".") != 3:   # "5.30" is a time, not a host
                continue
            links.append({"host": host, "path": match.group(2) or "", "raw": match.group(0)})
        phones = PHONE_RE.findall(text)
        board.text = text
        return AgentMessage(
            self.name,
            evidence=[f"redacted_{k.lower()}" for k in redactions],
            data={"sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "links": links,
                  "phones": phones, "sender": (board.sender or "").strip().upper() or None,
                  "redactions": redactions, "length": len(text)},
        )


# --------------------------------------------------------------------------------------------
class LanguageAgent:
    """Script rules first (Sinhala / Tamil Unicode blocks), then a char n-gram model separates
    English, Singlish and Tanglish written in Latin letters."""
    name = "language"

    def __init__(self, model):
        self.model = model

    def run(self, board: Blackboard) -> AgentMessage:
        text = board.text
        sinhala, tamil = len(SINHALA.findall(text)), len(TAMIL.findall(text))
        if sinhala or tamil:
            language = "sinhala" if sinhala >= tamil else "tamil"
            return AgentMessage(self.name, confidence=1.0, evidence=[f"script:{language}"],
                                data={"language": language, "reply_language": language})
        proba = self.model.predict_proba([text.casefold()])[0]
        best = int(np.argmax(proba))
        language = str(self.model.classes_[best])
        reply = {"singlish": "sinhala", "tanglish": "tamil"}.get(language, "english")
        return AgentMessage(self.name, confidence=float(proba[best]),
                            evidence=[f"model:{language}"],
                            data={"language": language, "reply_language": reply})


# --------------------------------------------------------------------------------------------
class ContentAgent:
    """What the words say. TF-IDF char 2-5 + word 1-2 grams with logistic regression (the
    pre-existing Rakshaka classifier, retrained here). Also reports the words that pushed the
    score up, so the explainer can cite them."""
    name = "content"

    def __init__(self, model, preprocess):
        self.model = model
        self.preprocess = preprocess
        features = model.named_steps["features"]
        self.word_vec = dict(features.transformer_list)["word"]
        self.n_char = len(dict(features.transformer_list)["char"].vocabulary_)
        coef = model.named_steps["classifier"].coef_[0]
        classes = list(model.named_steps["classifier"].classes_)
        self.sign = 1.0 if classes.index("scam") == 1 else -1.0
        self.word_coef = coef[self.n_char:] * self.sign
        self.word_names = self.word_vec.get_feature_names_out()

    def run(self, board: Blackboard) -> AgentMessage:
        text = self.preprocess(board.text)
        proba = self.model.predict_proba([text])[0]
        classes = list(self.model.classes_)
        p_scam = float(proba[classes.index("scam")])
        row = self.word_vec.transform([text])
        contrib = row.multiply(self.word_coef).toarray()[0]
        top = [self.word_names[i] for i in np.argsort(contrib)[::-1][:3]
               if contrib[i] > 0.05 and len(self.word_names[i]) >= 3
               and self.word_names[i] not in ("urltoken", "phonetoken")]
        return AgentMessage(self.name, risk=p_scam, confidence=abs(p_scam - 0.5) * 2,
                            evidence=[f"words:{w}" for w in top], data={"top_words": top})


# --------------------------------------------------------------------------------------------
class TacticsAgent:
    """How the message tries to manipulate: credential requests, payment requests, rewards,
    threats or urgency, and impersonated authorities, in five language forms. Safety advice
    from real institutions ("never share your OTP") cancels a credential cue."""
    name = "tactics"
    WEIGHTS = {"credential_request": 0.45, "payment_request": 0.35, "reward_lure": 0.30,
               "threat_or_urgency": 0.25, "authority_impersonation": 0.15}

    def run(self, board: Blackboard) -> AgentMessage:
        text = board.text.casefold()
        found = {kind: [c for c in cues if has_cue(text, c)] for kind, cues in lx.TACTICS.items()}
        found = {k: v for k, v in found.items() if v}
        safety = [c for c in lx.SAFETY_ADVICE if c in text]
        if safety and "credential_request" in found:
            found.pop("credential_request")
        score = 1 - np.prod([1 - self.WEIGHTS[k] for k in found]) if found else 0.0
        if safety:
            score *= 0.4
        # an action request is what turns pressure into a scam; pressure alone is weak evidence
        action = {"credential_request", "payment_request"} & set(found)
        if not action and "reward_lure" not in found:
            score *= 0.6
        evidence = [f"tactic:{k}" for k in found] + (["safety_advice"] if safety else [])
        return AgentMessage(self.name, risk=float(min(score, 1.0)),
                            confidence=min(1.0, 0.3 + 0.2 * len(found)),
                            evidence=evidence, data={"tactics": sorted(found), "cues": found,
                                                     "safety_advice": bool(safety)})


# --------------------------------------------------------------------------------------------
def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class LinkSenderAgent:
    """Checks the links and the sender, not the wording: shorteners, look-alike domains of
    banks and government bodies, risky TLDs, raw IP links, numbers to call or WhatsApp, and
    sender IDs that imitate official ones. A link to an official domain lowers risk."""
    name = "link_sender"

    def __init__(self, blocklist: set[str] | None = None):
        self.blocklist = blocklist or set()

    @staticmethod
    def registered_domain(host: str) -> str:
        parts = host.split(".")
        if len(parts) >= 3 and parts[-2] in ("gov", "com", "org", "edu", "ac", "net") and parts[-1] == "lk":
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])

    def check_host(self, host: str) -> tuple[float, list[str]]:
        reg = self.registered_domain(host)
        if reg in lx.OFFICIAL_DOMAINS or host in lx.OFFICIAL_DOMAINS or host.endswith(".gov.lk"):
            return 0.0, [f"official_domain:{reg}"]
        signals = []
        if host in self.blocklist or reg in self.blocklist:
            signals.append((0.95, f"blocklisted:{reg}"))
        if host in lx.URL_SHORTENERS or reg in lx.URL_SHORTENERS:
            signals.append((0.55, f"shortener:{reg}"))
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
            signals.append((0.8, "ip_address_link"))
        tld = host.rsplit(".", 1)[-1]
        if tld in lx.RISKY_TLDS:
            signals.append((0.5, f"risky_tld:.{tld}"))
        squashed = host.replace("0", "o").replace("1", "l").replace("3", "e").replace("5", "s")
        label = reg.split(".")[0]
        for official in lx.OFFICIAL_DOMAINS:
            off_label = official.split(".")[0]
            if len(off_label) >= 4 and label != off_label and _levenshtein(label, off_label) <= 1:
                signals.append((0.9, f"lookalike_of:{official}"))
                break
        brands = [b for b in lx.BRAND_WORDS if b in squashed.replace(".", "-").split("-")
                  or (len(b) >= 5 and b in squashed)]
        if brands:
            signals.append((0.85 if len(brands) >= 2 or tld in lx.RISKY_TLDS else 0.7,
                            f"brand_in_unofficial_domain:{'+'.join(brands[:2])}"))
        if host.count("-") >= 2:
            signals.append((0.45, "many_hyphens"))
        if not signals:
            return 0.35, [f"unknown_domain:{reg}"]
        score = 1 - np.prod([1 - s for s, _ in signals])
        return float(min(score, 0.99)), [e for _, e in signals]

    def run(self, board: Blackboard) -> AgentMessage:
        intake = board.get("intake").data
        evidence, scores = [], []
        for link in intake["links"]:
            score, ev = self.check_host(link["host"])
            scores.append(score)
            evidence += ev
        text = board.text.casefold()
        if intake["phones"] and re.search(r"call|whatsapp|contact|ta call|අමතන්න|அழைக்க", text):
            scores.append(0.45)
            evidence.append("asks_to_call_or_whatsapp_number")
        sender = intake.get("sender")
        if sender:
            if sender in lx.OFFICIAL_SENDERS:
                evidence.append(f"official_sender:{sender}")
            elif any(_levenshtein(sender, s) <= 2 for s in lx.OFFICIAL_SENDERS):
                scores.append(0.8)
                evidence.append(f"lookalike_sender:{sender}")
        if not scores:
            return AgentMessage(self.name, status="skipped", evidence=["no_links_or_numbers"])
        risk = max(scores)
        if any(e.startswith("official_domain") for e in evidence) and risk == 0.0:
            risk = 0.05
        return AgentMessage(self.name, risk=float(risk), confidence=0.8 if risk >= 0.7 or risk <= 0.1 else 0.5,
                            evidence=evidence, data={"n_links": len(intake["links"])})


# --------------------------------------------------------------------------------------------
class CampaignAgent:
    """Compares the message with known scam campaigns (centroids of past scam templates) and
    with recent uncertain messages, to spot a new wave before anyone has labelled it."""
    name = "campaign"

    def __init__(self, vectorizer, scam_centroids, scam_names, legit_centroids, window: int = 200):
        self.vectorizer = vectorizer
        self.scam_centroids = scam_centroids
        self.scam_names = scam_names
        self.legit_centroids = legit_centroids
        self.recent = deque(maxlen=window)   # vectors of recent UNCERTAIN messages (in memory)

    def run(self, board: Blackboard) -> AgentMessage:
        vec = self.vectorizer.transform([board.text.casefold()])
        dense = vec.toarray().ravel()
        sim_scam = self.scam_centroids @ dense       # centroids are L2-normalised dense rows
        sim_legit = self.legit_centroids @ dense
        best = int(np.argmax(sim_scam))
        s_scam, s_legit = float(sim_scam[best]), float(sim_legit.max())
        risk = float(1 / (1 + np.exp(-8 * (s_scam - s_legit))))
        evidence = []
        if s_scam >= 0.45 and s_scam > s_legit:
            evidence.append(f"matches_campaign:{self.scam_names[best]}")
        wave = 0
        if self.recent:
            sims = np.asarray([float((vec @ r.T).toarray()[0, 0]) for r in self.recent])
            wave = int((sims >= 0.55).sum())
            if wave >= 2:
                evidence.append(f"emerging_wave:{wave + 1}_similar_recent_messages")
        return AgentMessage(self.name, risk=risk, confidence=min(1.0, abs(s_scam - s_legit) * 3),
                            evidence=evidence, data={"sim_scam": round(s_scam, 3), "sim_legit": round(s_legit, 3),
                                                     "campaign": self.scam_names[best], "wave_size": wave, "_vec": vec})

    def remember(self, vec) -> None:
        self.recent.append(vec)


# --------------------------------------------------------------------------------------------
class DriftAgent:
    """Novelty sentinel: share of character n-grams the content model has never seen. High
    novelty means the content agent's score is not trustworthy, so the arbiter must not say
    LIKELY_SAFE."""
    name = "drift"

    def __init__(self, oov_fn, content_model, threshold: float):
        self.oov_fn = oov_fn
        self.content_model = content_model
        self.threshold = threshold

    def run(self, board: Blackboard) -> AgentMessage:
        oov = float(self.oov_fn(self.content_model, board.text))
        novel = oov >= self.threshold
        return AgentMessage(self.name, confidence=1.0, evidence=["novel_wording"] if novel else [],
                            data={"oov_ratio": round(oov, 3), "threshold": round(self.threshold, 3), "novel": novel})
