"""End-to-end flow test: classify -> negotiate -> qualify -> handoff.

Uses a temp DB and the mock integrations so it runs fully offline.
Run:  python -m pytest tests -v
"""
import os
import sys
import tempfile
from pathlib import Path

# Point DB to a temp file and bypass rate limit before importing app.
tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = str(Path(tmpdir) / "test.db")
os.environ["REPLY_RATE_LIMIT_SECONDS"] = "0"

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import db, instagram, whatsapp  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.orchestrator import handle_inbound  # noqa: E402
from app.classifier import classify  # noqa: E402


def setup_module():
    db.init_db()
    s = get_settings()
    db.upsert_creator(
        {
            "name": s.creator_name,
            "min_rate": s.creator_min_rate,
            "tone": s.creator_tone,
            "niche": s.creator_niche,
            "exclusions": s.creator_exclusions,
            "instagram_id": s.creator_instagram_id,
            "phone": s.creator_phone,
        }
    )


def test_webhook_parse():
    payload = {
        "entry": [{"messaging": [{
            "sender": {"id": "u1"},
            "message": {"mid": "m-1", "text": "hello"},
            "timestamp": 1,
        }]}]
    }
    events = instagram.parse_webhook(payload)
    assert len(events) == 1
    assert events[0]["ig_user_id"] == "u1"
    assert events[0]["text"] == "hello"


def test_spam_ignored():
    r = handle_inbound("u_spam", "Buy 10k followers instantly!", "t-spam")
    assert r["action"] == "ignored"
    assert r["stage"] == "spam"
    assert r["reply_sent"] is False


def test_fan_replied():
    r = handle_inbound("u_fan", "You're amazing, love your content!", "t-fan")
    assert r["stage"] == "fan_love"
    assert r["reply_sent"] is True


def test_full_negotiation_to_qualification():
    # lowball -> should NOT qualify
    r1 = handle_inbound("u_brand", "Hi this is Acme Co. We love your work. $200 for a post?", "t-b1")
    assert r1["action"] == "negotiating"
    assert r1["lead_id"] is None

    # qualifying offer -> should qualify + fire handoff + pause automation
    r2 = handle_inbound("u_brand", "Okay we can do $1000 for a 3-post bundle. Deal?", "t-b2")
    assert r2["lead_id"] is not None, "should qualify at $1000"
    assert r2["action"] == "qualified"

    # handoff alert fired
    assert any("Acme" in a["body"] and "1000" in a["body"] for a in whatsapp.MOCK_OUTBOX)

    # automation paused -> further DMs ignored (human takeover)
    conv = db.get_open_conversation(
        get_settings().creator_instagram_id and db.get_creator_by_instagram(
            get_settings().creator_instagram_id)["id"], "u_brand"
    )
    r3 = handle_inbound("u_brand", "Actually let's do $1200!", "t-b3")
    assert r3["stage"] == "handed_off"
    assert r3["reply_sent"] is False


def test_idempotency_duplicate_webhook():
    # Same message_meta_id twice -> only stored once, no double reply.
    handle_inbound("u_dup", "Hi we'd love to collab, budget $900", "dup-1")
    handle_inbound("u_dup", "Hi we'd love to collab, budget $900", "dup-1")
    conv = db.get_open_conversation(
        db.get_creator_by_instagram(get_settings().creator_instagram_id)["id"], "u_dup"
    )
    msgs = db.list_messages(conv["id"])
    brand_msgs = [m for m in msgs if m["role"] == "brand"]
    assert len(brand_msgs) == 1, "duplicate webhook must be deduped"
