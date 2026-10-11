"""Orchestrator — the core flow that turns an inbound DM into the right action.

Flow (mirrors Phase D/E/F of the execution plan):
  inbound DM
    -> resolve creator
    -> find/create conversation
    -> store brand message (idempotent)
    -> if automation paused (human takeover) -> ignore
    -> classify (FAN_LOVE | SPAM | BUSINESS_INQUIRY)
         FAN_LOVE -> polite reply (or ignore)
         SPAM     -> ignore
         BUSINESS -> negotiate
            -> load creator context, generate reply, send, store
            -> if qualified -> insert lead + WhatsApp alert + pause automation
"""
from datetime import datetime, timezone

from . import db, instagram, negotiator, whatsapp
from .classifier import classify
from .config import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestratorError(Exception):
    pass


def handle_inbound(ig_user_id: str, text: str, message_meta_id: str = None) -> dict:
    """Process one inbound DM from an external IG user. Returns a trace dict."""
    settings = get_settings()
    creator = _resolve_creator()
    if not creator:
        raise OrchestratorError("No creator configured. Run `python seed.py`.")

    conv = db.get_open_conversation(creator["id"], ig_user_id)
    if not conv:
        conv = db.create_conversation(creator["id"], ig_user_id)
    conv_id = conv["id"]

    # Store the brand message (deduped by message_meta_id for idempotency).
    stored = db.append_message(
        conv_id, "brand", text, message_meta_id=message_meta_id
    )
    if stored is None:
        # Duplicate webhook delivery — already processed. Return idempotent trace.
        return _trace(conv_id, "duplicate", "ignored", reply_sent=False)

    history = db.list_messages(conv_id)

    # Human takeover: automation paused -> never auto-respond.
    if not conv["automation_on"]:
        return _trace(conv_id, "handed_off", "ignored", reply_sent=False)

    # Rate-limit replies to the same conversation.
    if _rate_limited(conv):
        return _trace(conv_id, "rate_limited", "ignored", reply_sent=False)

    bucket = classify(text)

    if bucket == "SPAM":
        return _trace(conv_id, "spam", "ignored", reply_sent=False)

    if bucket == "FAN_LOVE":
        reply = "Thank you so much! That genuinely means a lot 💛"
        _reply_and_store(conv_id, ig_user_id, reply)
        return _trace(conv_id, "fan_love", "replied", reply=reply, reply_sent=True)

    if bucket == "BUSINESS_INQUIRY":
        return _handle_business(conv, ig_user_id, history)

    # Unknown bucket (safety) -> safe fan behavior.
    return _trace(conv_id, "fallback", "ignored", reply_sent=False)


def _handle_business(conv: dict, ig_user_id: str, history: list[dict]) -> dict:
    creator = db.get_creator(conv["creator_id"])
    conv_id = conv["id"]

    db.update_conversation(conv_id, status="negotiating")

    # Update brand name on first business contact.
    brand = negotiator.extract_brand_name(history)
    if not conv["brand_name"]:
        db.update_conversation(conv_id, brand_name=brand)

    reply = negotiator.generate_reply(creator, history)
    _reply_and_store(conv_id, ig_user_id, reply)

    # Re-load history including our reply, then check qualification.
    history = db.list_messages(conv_id)
    qualified = negotiator.is_qualified(history, creator)

    if qualified:
        lead = db.insert_lead(
            conv_id, brand or conv["brand_name"],
            qualified.get("offer") or "Qualified brand deal",
            qualified.get("amount"),
        )
        # Pause automation = human takeover.
        db.update_conversation(conv_id, status="qualified", automation_on=0)
        whatsapp.send_handoff_alert(
            lead["brand_name"], lead["offer"], lead["amount"], creator.get("phone")
        )
        return _trace(
            conv_id, "negotiating", "qualified", reply=reply,
            reply_sent=True, lead_id=lead["id"],
        )

    return _trace(
        conv_id, "negotiating", "negotiating", reply=reply, reply_sent=True
    )


def _reply_and_store(conv_id: str, ig_user_id: str, reply: str) -> None:
    instagram.send_dm(ig_user_id, reply)
    db.append_message(conv_id, "creator", reply)
    db.update_conversation(conv_id, last_reply_at=_now())


def _resolve_creator():
    settings = get_settings()
    return db.get_creator_by_instagram(settings.creator_instagram_id) or (
        db.list_creators() or [None]
    )[0]


def _rate_limited(conv: dict) -> bool:
    """True if we replied too recently (rate limit guardrail)."""
    settings = get_settings()
    last = conv.get("last_reply_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return False
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
    return elapsed < settings.reply_rate_limit_seconds


def _trace(conv_id, stage, action, reply=None, reply_sent=False, lead_id=None):
    return {
        "conversation_id": conv_id,
        "stage": stage,
        "action": action,
        "reply": reply,
        "reply_sent": reply_sent,
        "lead_id": lead_id,
    }
