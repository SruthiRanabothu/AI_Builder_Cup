"""Instagram / Meta integration layer.

In MOCK mode (default) this logs DMs locally and simulates the Graph API —
no Meta account or review needed, so the demo is fully self-contained.
In REAL mode it calls the Meta Graph API to send replies.

The webhook parser accepts the real Meta `messages` payload shape so the
code is identical when wired to real Instagram (see WEBHOOK_PAYLOAD.md).
"""
import logging

from .config import get_settings

logger = logging.getLogger("creatoros.instagram")


# ----------------------------------------------------------------- webhook

def parse_webhook(payload: dict) -> list[dict]:
    """Parse a Meta Messenger/IG webhook payload into normalized events.

    Returns a list of dicts:
        {ig_user_id, text, message_meta_id, timestamp}
    """
    events = []
    entries = payload.get("entry", []) or []
    for entry in entries:
        for messaging in entry.get("messaging", []) or []:
            sender = (messaging.get("sender") or {}).get("id")
            message = messaging.get("message") or {}
            text = message.get("text", "").strip()
            mid = message.get("mid") or messaging.get("message_id")
            ts = messaging.get("timestamp")
            if not sender or not text:
                continue
            events.append(
                {
                    "ig_user_id": str(sender),
                    "text": text,
                    "message_meta_id": str(mid) if mid else None,
                    "timestamp": ts,
                }
            )
    return events


def verify_webhook(hub: dict) -> bool:
    """Return True if the Meta verification handshake passes."""
    mode = hub.get("hub.mode")
    token = hub.get("hub.verify_token")
    challenge = hub.get("hub.challenge")
    if mode == "subscribe" and token == get_settings().webhook_verify_token:
        return challenge
    return False


# ----------------------------------------------------------------- sending

def send_dm(ig_user_id: str, text: str) -> dict:
    """Send an outbound DM to a user as the creator. Returns a status dict."""
    settings = get_settings()
    if settings.mock_integrations:
        return {"ok": True, "mode": "mock", "to": ig_user_id, "text": text}

    # Real Meta Graph API path (requires IG_GRAPH_TOKEN + approved app).
    if not settings.ig_graph_token:
        logger.warning("No IG_GRAPH_TOKEN and mock disabled; dropping DM")
        return {"ok": False, "mode": "real", "error": "no_token"}

    import requests

    url = f"{settings.ig_graph_api}/{settings.ig_graph_token}/messages"
    resp = requests.post(
        url,
        json={"recipient": {"id": ig_user_id}, "message": {"text": text}},
        timeout=15,
    )
    ok = resp.status_code == 200
    logger.info("IG send -> %s ok=%s", ig_user_id, ok)
    return {"ok": ok, "mode": "real", "status_code": resp.status_code}
