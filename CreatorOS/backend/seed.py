"""Seed the database with a demo creator and a few pre-qualified demo leads
so the dashboard never looks empty (Phase G, step 4). Run: `python seed.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings  # noqa: E402
from app import db  # noqa: E402


def seed() -> dict:
    db.init_db()
    s = get_settings()

    creator = db.upsert_creator(
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
    print(f"✔ Seeded creator: {creator['name']} (min ${creator['min_rate']})")

    # A couple of pre-qualified demo leads so the dashboard has content.
    demo_leads = [
        ("Nordic Fit Apparel", "$800 for a 3-post bundle", 800.0, "ig_brand_nordic"),
        ("Glow Skincare", "$1,200 sponsored reel", 1200.0, "ig_brand_glow"),
    ]
    for brand, offer, amount, ig_user in demo_leads:
        conv = db.get_open_conversation(creator["id"], ig_user)
        if not conv:
            conv = db.create_conversation(creator["id"], ig_user, brand_name=brand)
            db.append_message(conv["id"], "brand",
                              f"Hi {creator['name']}! We'd love to partner. {offer}",
                              message_meta_id=f"seed-{ig_user}")
            db.update_conversation(conv["id"], status="qualified", automation_on=1)
            db.insert_lead(conv["id"], brand, offer, amount)
            print(f"✔ Seeded demo lead: {brand} — {offer}")

    return creator


if __name__ == "__main__":
    seed()
    print("Seed complete.")
