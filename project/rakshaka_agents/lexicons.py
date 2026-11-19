"""Multilingual cue lists for the Tactics and Link & Sender agents.

Sinhala and Tamil entries were drafted with an AI assistant and must be checked by native
speakers before any pilot (see docs/PROJECT_DETAILS.md). Matching is case-insensitive on
NFKC-normalised text.
"""

# Social-engineering tactics, per cue type. Latin entries cover English, Singlish and Tanglish.
TACTICS = {
    "credential_request": [
        "otp", "pin", "password", "cvv", "card number", "card details", "account number",
        "nic photo", "nic number", "verify your identity", "confirm your identity", "login details",
        "share the code", "send the code", "tell us the", "reply with your",
        "otp eka", "pin eka", "card eke", "number eka ewanna",
        "මුරපදය", "රහස් අංකය", "කාඩ්පත් අංකය", "හැඳුනුම්පත් අංකය", "ගිණුම් අංකය",
        "கடவுச்சொல்", "அட்டை எண்", "கணக்கு எண்",
    ],
    "payment_request": [
        "processing fee", "clearance fee", "service fee", "insurance fee", "registration fee",
        "pay rs", "pay now", "deposit", "send money", "send rs", "ez cash", "ezcash", "transfer",
        "fee eka", "gewala", "gewanna", "dala denna", "salli ewanna",
        "ගාස්තුව", "ගෙවන්න", "ගෙවා", "මුදල් එවන්න",
        "கட்டணம்", "செலுத்து", "பணம் அனுப்ப",
    ],
    "reward_lure": [
        "congratulations", "you won", "you have won", "winner", "lottery", "lucky draw", "prize",
        "free data", "guaranteed", "double", "passive income", "daily return", "earn rs", "per day",
        "refund", "cashback", "bonus", "loan is approved", "pre-approved",
        "dinala", "dinuwa", "nomile", "lottery ekak",
        "ත්‍යාග", "දිනා ඇත", "නොමිලේ", "ණය මුදලක් අනුමත",
        "பரிசு", "வென்றுள்ளீர்கள்", "இலவச", "கடன் அங்கீகரிக்கப்பட்டது",
    ],
    "threat_or_urgency": [
        "urgent", "immediately", "within 24 hours", "24 hours", "today only", "within today",
        "tonight", "blocked", "suspended", "deactivated", "disconnected", "will be closed",
        "cancelled", "cancel wenawa", "last chance", "final notice", "legal action", "arrest",
        "block wela", "ikmanata", "dan ma", "nathnam",
        "වහාම", "අත්හිටුවා", "අවහිර", "විසන්ධි", "අද රාත්‍රියේ",
        "உடனே", "முடக்கப்பட்ட", "நிறுத்தப்படும்", "துண்டிக்கப்படும்",
    ],
    "authority_impersonation": [
        "security team", "customs", "police", "cid", "court", "tax refund", "inland revenue",
        "pension", "pensioner", "aswesuma", "sl-udi", "digital id", "government", "govt",
        "central bank", "slkpost", "sri lanka post", "telecom", "kyc",
        "රේගුව", "පොලිසිය", "විශ්‍රාම වැටුප", "අස්වැසුම", "ඩිජිටල් හැඳුනුම්පත",
        "சுங்க", "காவல்", "ஓய்வூதிய", "டிஜிட்டல் அடையாள",
    ],
}

# Phrases that real institutions use to warn customers or point them to official channels. They
# reduce credential-request risk. v0 had English entries only; the Sinhala/Tamil equivalents of
# "official app / office / branch" were added after the first benchmark showed all Sinhala false
# alarms came from one water-bill template ("pay via the official app").
SAFETY_ADVICE = [
    "do not share", "don't share", "never share", "never ask", "will never ask", "not share this",
    "visit your branch", "official app", "official outlet", "call the number on your card",
    "kisiwekuta denna epa", "share karanna epa",
    "කිසිවෙකුට ලබා නොදෙන්න", "බෙදා නොගන්න", "නිල යෙදුම", "නිල කාර්යාල", "ශාඛාවට",
    "யாருடனும் பகிர வேண்டாம்", "அதிகாரப்பூர்வ செயலி", "அதிகாரப்பூர்வ அலுவலக", "கிளைக்கு",
]

# Official domains of Sri Lankan institutions often impersonated (not exhaustive).
OFFICIAL_DOMAINS = {
    "boc.lk": "boc", "combank.lk": "combank", "peoplesbank.lk": "peoplesbank",
    "sampath.lk": "sampath", "hnb.lk": "hnb", "nsb.lk": "nsb", "seylan.lk": "seylan",
    "ndbbank.com": "ndb", "dfcc.lk": "dfcc", "cbsl.gov.lk": "cbsl", "gov.lk": "gov",
    "slpost.gov.lk": "slpost", "police.lk": "police", "ird.gov.lk": "ird",
    "dialog.lk": "dialog", "mobitel.lk": "mobitel", "slt.lk": "slt", "hutch.lk": "hutch",
    "airtel.lk": "airtel", "ceb.lk": "ceb", "leco.lk": "leco", "waterboard.lk": "waterboard",
    "pensions.gov.lk": "pensions", "wbb.gov.lk": "wbb", "drp.gov.lk": "drp",
    "ezcash.lk": "ezcash", "frimi.lk": "frimi", "daraz.lk": "daraz", "pickme.lk": "pickme",
}

# Brand words scammers put inside look-alike domains (e.g. boc-lk-verify.top).
BRAND_WORDS = sorted({v for v in OFFICIAL_DOMAINS.values() if len(v) >= 3} |
                     {"slpost", "lkpost", "post", "customs", "aswesuma", "pension", "udi", "bank",
                      "verify", "refund", "secure"})

URL_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy",
                  "shorturl.at", "tiny.cc", "ow.ly", "s.id"}

RISKY_TLDS = {"top", "xyz", "icu", "click", "live", "online", "site", "buzz", "rest", "cfd",
              "sbs", "shop", "vip", "win", "loan", "work", "info", "cc", "tk", "ml", "ga", "cf"}

# Official SMS sender IDs and the look-alikes seen in the wild.
OFFICIAL_SENDERS = {"SLPOST", "BOC", "COMBANK", "PEOPLESBANK", "SAMPATH", "HNB", "DIALOG",
                    "MOBITEL", "SLT", "CEB", "CBSL"}
