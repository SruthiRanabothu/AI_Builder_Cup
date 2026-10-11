"""Negotiation agent.

On BUSINESS_INQUIRY it loads the creator's context (min rate, tone, niche,
exclusions) and drives a professional conversation toward qualifying the
deal. Includes guardrails and a "qualified" detector.

Guardrails (from the execution plan):
    - Never agree to terms below min_rate.
    - Respect exclusions.
    - Do not reveal that you are an AI.
    - Cap reply length.
    - Never auto-commit a deal without human sign-off — only flag qualified.
"""
import re

from .config import get_settings
from . import classifier

# ---------------------------------------------------------------- prompt

def build_negotiator_prompt(creator: dict, history: list[dict]) -> list:
    """Build a multi-turn style prompt for Gemini."""
    turns = []
    system = (
        f"You are {creator['name']}'s AI talent manager on Instagram. "
        f"Your client's niche: {creator['niche']}. Tone: {creator['tone']}. "
        f"Minimum acceptable rate: ${creator.get('min_rate', 0)}. "
        f"Exclusions (never accept): {creator['exclusions']}. "
        "Your job: reply professionally to a brand that reached out. Thank "
        "them, ask for their budget and timeline, and steer toward a paid "
        "partnership. Never agree to terms below the minimum rate. Never "
        "accept a prohibited category. Keep replies concise (1-3 sentences), "
        "friendly, and human-sounding. Do NOT reveal that you are an AI or "
        "an automated assistant. Do not confirm a final price on the spot — "
        "you only qualify the lead and let the creator finalize."
    )
    turns.append({"role": "user", "parts": [system]})
    for msg in history[-get_settings().max_history_messages:]:
        role = "user" if msg["role"] == "brand" else "model"
        turns.append({"role": role, "parts": [msg["content"]]})
    turns.append({"role": "user", "parts": ["Reply now:"]})
    return turns


def _template_reply(creator: dict, history: list[dict]) -> str:
    """Offline fallback: a context-aware but simple negotiation response."""
    min_rate = creator.get("min_rate", 0)
    name = creator["name"]
    # If we already asked for budget, and the user gave a number, respond to it.
    last_brand = next(
        (m["content"] for m in reversed(history) if m["role"] == "brand"), ""
    )
    amount = parse_amount(last_brand)
    if amount is not None:
        if amount < min_rate:
            return (
                f"Thanks so much for the offer! I really appreciate the interest. "
                f"Given the scope we'd need, I'd be looking at something in the "
                f"${min_rate}+ range for this kind of partnership. Would you be "
                f"able to adjust the budget? Happy to explore a fit."
            )
        return (
            f"That budget sounds like it could work well for us! Could you share "
            f"a bit more on the timeline and exactly what deliverables you had "
            f"in mind? Then we can line things up."
        )
    # No number yet — ask for budget + timeline.
    return (
        f"Hi! Thanks so much for reaching out — I'd love to hear more about what "
        f"you have in mind. Could you share your budget range and timeline for "
        f"the campaign? Happy to see if we're a good fit."
    )


def generate_reply(creator: dict, history: list[dict]) -> str:
    """Return the next outbound reply (bounded length)."""
    settings = get_settings()
    reply = None
    if settings.has_gemini:
        try:
            from .gemini_client import gemini_generate_text
            reply = gemini_generate_text(
                build_negotiator_prompt(creator, history),
                model=settings.gemini_model,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[negotiator] Gemini failed, using template: {exc}")
    if not reply:
        reply = _template_reply(creator, history)
    return reply[: settings.max_reply_chars].strip()


# ------------------------------------------------------------- amount parse

_AMOUNT_RE = re.compile(r"\$\s*([0-9][0-9,]{0,9}(?:\.[0-9]{1,2})?)|\b([0-9][0-9,]{1,7})\s*(?:usd|dollars|bucks)?")


def parse_amount(text: str) -> float | None:
    """Extract the first dollar amount from a string, or None."""
    if not text:
        return None
    low = text.lower()
    for m in _AMOUNT_RE.finditer(low):
        raw = m.group(1) or m.group(2)
        if raw is None:
            continue
        val = float(raw.replace(",", ""))
        if val <= 0:
            continue
        return val
    return None


# ------------------------------------------------------------- qualified

def is_qualified(history: list[dict], creator: dict) -> dict | None:
    """Return a lead dict if the conversation has qualified, else None.

    Qualification = a concrete budget/offer has been stated that is >= min_rate.
    Uses Gemini boolean check when available; otherwise a heuristic that reads
    the latest brand messages for an amount >= min_rate.
    """
    min_rate = creator.get("min_rate", 0)
    settings = get_settings()

    if settings.has_gemini:
        try:
            from .gemini_client import gemini_generate_json
            transcript = "\n".join(
                f"{m['role']}: {m['content']}" for m in history
            )
            res = gemini_generate_json(
                {
                    "role": "user",
                    "parts": [
                        (
                            "A creator and a brand negotiated via DM. Determine "
                            "whether the brand has (a) stated a concrete budget or "
                            f"offer amount, and (b) that amount is at least ${min_rate}. "
                            "Respond JSON: {\"qualified\": true/false, \"amount\": number_or_null, "
                            "\"offer\": \"short summary\"}"
                        ),
                        transcript,
                    ],
                },
                model=settings.gemini_model,
            )
            if res.get("qualified"):
                return {
                    "amount": res.get("amount"),
                    "offer": res.get("offer") or "Qualified brand deal",
                }
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"[qualified] Gemini failed, using heuristic: {exc}")

    # Heuristic: scan brand messages for an amount >= min_rate.
    for msg in reversed(history):
        if msg["role"] != "brand":
            continue
        amount = parse_amount(msg["content"])
        if amount is not None and amount >= min_rate:
            offer = msg["content"][:140]
            return {"amount": amount, "offer": offer}
    return None


def extract_brand_name(history: list[dict]) -> str:
    """Best-effort brand name from the first inbound business message."""
    for msg in history:
        if msg["role"] != "brand":
            continue
        text = msg["content"].strip()
        if not text:
            continue
        first_line = text.splitlines()[0]
        # e.g. "Hi! This is Glow Skincare ..." -> take a plausible company token
        for keyword in ("we are", "we're", "this is", "i'm", "i am", "from"):
            idx = first_line.lower().find(keyword)
            if idx != -1:
                tail = first_line[idx + len(keyword):].strip(" ,.!:")
                if tail:
                    stop = {"we", "we'd", "we're", "we'll", "our", "i'm", "and", "to", "a", "the"}
                    name_tokens = []
                    for w in tail.split():
                        clean = w.strip(" ,.:;!?")
                        if not clean or clean.lower() in stop or clean.lower().startswith("we'"):
                            break
                        name_tokens.append(clean)
                        if len(name_tokens) == 3:
                            break
                    name = " ".join(name_tokens).strip(" ,.")
                    if name and len(name) > 1:
                        return name[:40]
        break
    return "Unknown Brand"


def classify(text: str) -> str:
    """Re-export for convenience."""
    return classifier.classify(text)
