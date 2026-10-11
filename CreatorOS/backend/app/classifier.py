"""DM intent classifier.

Buckets an inbound message into exactly one of:
    FAN_LOVE | SPAM | BUSINESS_INQUIRY

Primary path uses Google Gemini with JSON/structured output. If no API key
is configured, or the call fails / output is unparseable, we fall back to a
keyword heuristic. The heuristic is deliberately tuned so that genuine
business keywords always win over fan/spam words, and the ultimate fallback
is FAN_LOVE (safe: never auto-reply spam, never spam a brand).

Routing (used by the orchestrator):
    FAN_LOVE         -> polite auto-reply (optional) or ignore
    SPAM             -> ignore (no reply)
    BUSINESS_INQUIRY -> hand to the Negotiator
"""
import re

from .config import get_settings

# Valid buckets
FAN_LOVE = "FAN_LOVE"
SPAM = "SPAM"
BUSINESS = "BUSINESS_INQUIRY"

_ALL_BUCKETS = {FAN_LOVE, SPAM, BUSINESS}

# Heuristic keyword sets. Business words carry the highest weight.
_BUSINESS_PATTERNS = [
    r"sponsor", r"collab", r"partnership", r"brand deal", r"brand partnership",
    r"\$", r"budget", r"campaign", r"promote", r"promotion", r"advertis",
    r"offer", r"rate", r"pay(?:ing|ment|s)?\b", r"compensat", r"free product",
    r"send you our", r"feature your", r"affiliate", r"influencer", r"reach out",
    r"work with", r"paid", r"contract", r"gifted", r"ambassador", r"creator program",
    r"marketing", r"our product", r"our brand", r"whitelist", r"usage rights",
]

_SPAM_PATTERNS = [
    r"free followers", r"buy followers", r"make money fast",
    r"casino", r"crypto", r"bitcoin", r"lottery", r"winner",
    r"claim your prize", r"click.?link", r"download this app",
    r"get rich", r"loan", r"instant cash", r"verified badge",
    r"dm for promo", r"giveaway", r"pyramid", r"mlm",
]

# High-confidence scam phrases that override even business-like signals
# (e.g. "earn $500 a day" carries a $ but is clearly a work-from-home scam).
_STRONG_SPAM_PATTERNS = [
    r"buy.{0,6}follower", r"get.{0,6}follower", r"free.{0,6}follower",
    r"earn\s*\$?\s*\d+", r"make money", r"working from home", r"sign up today",
    r"get rich", r"instant cash", r"no risk",
]

_FAN_PATTERNS = [
    r"love your", r"you're amazing", r"you are amazing", r"inspir", r"favorite creator",
    r"my favorite", r"keep it up", r"big fan", r"so good", r"love this",
    r"how are you", r"hi!?\b", r"hello", r"hey\b", r"great content",
]


def _heuristic(text: str) -> str:
    low = text.lower()
    biz = sum(1 for p in _BUSINESS_PATTERNS if re.search(p, low))
    spam = sum(1 for p in _SPAM_PATTERNS if re.search(p, low))
    strong_spam = sum(1 for p in _STRONG_SPAM_PATTERNS if re.search(p, low))
    fan = sum(1 for p in _FAN_PATTERNS if re.search(p, low))

    # Strong scam signals always win (protects against "earn $500 a day" scams).
    if strong_spam > 0:
        return SPAM
    # Spam wins over fan if it has any spam signal.
    if spam > 0 and biz == 0:
        return SPAM
    # Any business signal -> business (even if it also looks spammy, we
    # prefer a human/negotiation look than auto-ignoring a real deal).
    if biz > 0:
        return BUSINESS
    if fan > 0:
        return FAN_LOVE
    # No strong signal. If it looks spammy-ish, call it spam; else safe fan.
    return SPAM if spam > 0 else FAN_LOVE


def _parse_bucket(raw: str) -> str:
    """Normalize raw LLM text into a valid bucket or None."""
    if not raw:
        return None
    cleaned = re.sub(r"[^A-Za-z_ ]", " ", raw).strip().upper()
    for token in cleaned.replace("_", " ").split():
        for b in _ALL_BUCKETS:
            if token.replace("_", "") == b.replace("_", ""):
                return b
    for b in _ALL_BUCKETS:
        if b in cleaned:
            return b
    return None


def _classify_gemini(text: str) -> str:
    from .gemini_client import gemini_generate_json

    prompt = {
        "role": "user",
        "parts": [
            (
                "You are a DM classifier for a content creator's Instagram "
                "inbox. Classify the following inbound message into EXACTLY one "
                "bucket: FAN_LOVE, SPAM, or BUSINESS_INQUIRY.\n"
                "- FAN_LOVE: praise, casual chat, admiration, questions about content.\n"
                "- SPAM: scams, buy-followers, crypto/casino, fake giveaways, phishing.\n"
                "- BUSINESS_INQUIRY: real brand/collab/sponsorship/partnership interest, "
                "offers, rates, budgets, paid promotion.\n"
                "Respond with JSON: {\"bucket\": \"ONE_OF_THE_THREE\"} only."
            ),
            f"Message: {text}",
        ],
    }
    try:
        result = gemini_generate_json(prompt, model=get_settings().gemini_model)
        bucket = _parse_bucket((result or {}).get("bucket"))
        if bucket:
            return bucket
    except Exception as exc:  # noqa: BLE001 - fall through to heuristic
        print(f"[classifier] Gemini failed, using heuristic: {exc}")
    return _heuristic(text)


def classify(text: str) -> str:
    """Return one of FAN_LOVE | SPAM | BUSINESS_INQUIRY."""
    if not text or not text.strip():
        return FAN_LOVE
    if get_settings().has_gemini:
        return _classify_gemini(text)
    return _heuristic(text)
