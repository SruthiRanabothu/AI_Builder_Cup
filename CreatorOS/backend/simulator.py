"""CLI simulator — drives a full scripted brand-DM conversation against the
orchestrator, printing each step (classify -> negotiate -> qualify -> alert).
This is the Phase E "scripted demo conversation" and Phase G end-to-end run.

Usage:
    python seed.py
    python simulator.py
"""
import os
import sys
import time
from pathlib import Path

# Bypass the anti-spam rate limit so the scripted demo can run back-to-back.
os.environ["REPLY_RATE_LIMIT_SECONDS"] = "0"

sys.path.insert(0, str(Path(__file__).parent))

from app import db, whatsapp  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.orchestrator import handle_inbound  # noqa: E402


def banner(text):
    print("\n" + "=" * 62)
    print("  " + text)
    print("=" * 62)


def main():
    db.init_db()
    settings = get_settings()
    mode = "Gemini" if settings.has_gemini else "heuristic (offline)"
    print(f"Creator OS demo | AI mode: {mode}")
    print(f"Creator min rate: ${settings.creator_min_rate}")

    # --- 1. FAN message ---
    banner("1) FAN message  -> should get a polite reply (or ignore)")
    r = handle_inbound("ig_fan_amy", "I love your content, you're amazing!", "sim-fan-1")
    print(f"   [{r['action']}] stage={r['stage']} reply={r.get('reply')!r}")

    # --- 2. SPAM message ---
    banner("2) SPAM message -> should be ignored, no reply")
    r = handle_inbound("ig_spam_bot", "Buy 10k followers instantly, click link now!", "sim-spam-1")
    print(f"   [{r['action']}] stage={r['stage']} reply_sent={r['reply_sent']}")

    # --- 3. BUSINESS lowball ---
    banner("3) BUSINESS lowball -> negotiator replies, does NOT qualify")
    r = handle_inbound("ig_brand_zenith", "Hi! This is Zenith Tech. We love your videos. Can you do a post for $200?", "sim-biz-1")
    print(f"   [{r['action']}] stage={r['stage']}")
    if r.get("reply"):
        print(f"   reply: {r['reply']}")
    time.sleep(1)

    # --- 4. BUSINESS qualifying offer ---
    banner("4) BUSINESS qualifying offer -> qualifies + WhatsApp handoff + pause")
    r = handle_inbound("ig_brand_zenith", "Got it, we can do $900 for a 3-post bundle, timeline next month. Deal?", "sim-biz-2")
    print(f"   [{r['action']}] stage={r['stage']} lead_id={r.get('lead_id')}")
    if r.get("reply"):
        print(f"   reply: {r['reply']}")

    # --- 5. After handoff, automation paused -> further DMs ignored ---
    banner("5) Post-handoff message -> ignored (human takeover active)")
    r = handle_inbound("ig_brand_zenith", "Actually can we bump it to $1000?", "sim-biz-3")
    print(f"   [{r['action']}] stage={r['stage']} reply_sent={r['reply_sent']}")

    # --- Summary ---
    banner("RESULT: Handoff alerts fired (mock WhatsApp)")
    for a in whatsapp.MOCK_OUTBOX[-3:][::-1]:
        print(f"   🚨 to {a['to']}: {a['body']}")

    banner("RESULT: Qualified leads in DB")
    creator = (db.list_creators() or [None])[0]
    for lead in db.list_leads(creator["id"] if creator else None):
        print(f"   • {lead['brand_name']} — {lead['offer']} (${lead['amount']}) [{lead['status']}]")

    print("\nDone. Start the server with `uvicorn app.main:app --reload` and open")
    print("the dashboard at http://localhost:8000 to see it live.")


if __name__ == "__main__":
    main()
