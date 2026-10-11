"""WhatsApp handoff alert (Twilio).

In MOCK mode this writes the alert to a local "outbox" and logs it, so the
demo operator can see the notification that would hit the creator's phone.
In REAL mode it calls the Twilio Messages API.
"""
import logging
from typing import Optional

from .config import get_settings

logger = logging.getLogger("creatoros.whatsapp")

# In-memory mock outbox so the dashboard/simulator can surface alerts.
MOCK_OUTBOX: list[dict] = []


def send_handoff_alert(brand: str, offer: str, amount: Optional[float],
                       to_phone: Optional[str] = None) -> dict:
    """Fire the 'New Qualified Lead' WhatsApp alert to the creator."""
    settings = get_settings()
    phone = to_phone or settings.creator_phone
    body = (
        f"🚨 New Qualified Lead! {brand} is offering {offer}"
        f"{f' (${amount:,.0f})' if amount else ''}. "
        "Reply in the app or open your IG requests folder to finalize."
    )

    if settings.mock_integrations:
        record = {
            "to": phone,
            "body": body,
            "mode": "mock",
            "timestamp": _now(),
        }
        MOCK_OUTBOX.append(record)
        logger.info("[mock-whatsapp] -> %s: %s", phone, body)
        return {"ok": True, "mode": "mock", **record}

    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        logger.warning("Twilio creds missing and mock disabled; dropping alert")
        return {"ok": False, "mode": "real", "error": "no_creds"}

    from twilio.rest import Client  # type: ignore

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    msg = client.messages.create(
        from_=settings.twilio_whatsapp_from,
        to=phone,
        body=body,
    )
    logger.info("[twilio] sent sid=%s", msg.sid)
    return {"ok": True, "mode": "real", "sid": msg.sid, "to": phone, "body": body}


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
