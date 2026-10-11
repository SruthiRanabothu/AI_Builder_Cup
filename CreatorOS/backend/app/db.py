"""SQLite persistence layer.

This is the single place that touches the database. When migrating to
Supabase later, only this module needs to change (swap the SQL functions
for Supabase REST / postgrest calls). The rest of the app calls these
helpers and never sees SQL.

Thread-safety: each helper opens a short-lived connection so it works
across FastAPI's threadpool without a shared connection object.
"""
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from .config import get_settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _conn() -> sqlite3.Connection:
    settings = get_settings()
    db_path = settings.database_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------- creators

def get_creator(creator_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM creators WHERE id = ?", (creator_id,)
        ).fetchone()
    return dict(row) if row else None


def get_creator_by_instagram(ig_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM creators WHERE instagram_id = ?", (ig_id,)
        ).fetchone()
    return dict(row) if row else None


def list_creators() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM creators ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def upsert_creator(data: dict) -> dict:
    """Create or update a creator. `data` may carry an existing `id`."""
    data = dict(data)
    if not data.get("id"):
        data["id"] = _uuid()
    # Fill any missing columns with defaults so partial payloads don't break.
    defaults = {
        "name": None, "min_rate": 0, "tone": "friendly", "niche": "",
        "exclusions": "", "media_kit_url": None, "instagram_id": None,
        "phone": None,
    }
    for k, v in defaults.items():
        data.setdefault(k, v)
    if data.get("name") is None:
        raise ValueError("creator `name` is required")
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO creators
                (id, name, min_rate, tone, niche, exclusions, media_kit_url,
                 instagram_id, phone)
            VALUES (:id, :name, :min_rate, :tone, :niche, :exclusions,
                    :media_kit_url, :instagram_id, :phone)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, min_rate=excluded.min_rate,
                tone=excluded.tone, niche=excluded.niche,
                exclusions=excluded.exclusions,
                media_kit_url=excluded.media_kit_url,
                instagram_id=excluded.instagram_id, phone=excluded.phone
            """,
            data,
        )
    return get_creator(data["id"])


# ---------------------------------------------------------- conversations

def get_conversation(conversation_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    return dict(row) if row else None


def get_open_conversation(creator_id: str, ig_user_id: str) -> Optional[dict]:
    """Find an existing non-closed conversation for the same pair."""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM conversations
            WHERE creator_id = ? AND ig_user_id = ? AND status != 'closed'
            ORDER BY created_at DESC LIMIT 1
            """,
            (creator_id, ig_user_id),
        ).fetchone()
    return dict(row) if row else None


def create_conversation(creator_id: str, ig_user_id: str, brand_name: str = None) -> dict:
    conv = {
        "id": _uuid(),
        "creator_id": creator_id,
        "ig_user_id": ig_user_id,
        "brand_name": brand_name,
        "status": "incoming",
        "automation_on": 1,
    }
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO conversations
                (id, creator_id, ig_user_id, brand_name, status, automation_on)
            VALUES (:id, :creator_id, :ig_user_id, :brand_name, :status, :automation_on)
            """,
            conv,
        )
    return get_conversation(conv["id"])


def update_conversation(conversation_id: str, **fields) -> dict:
    allowed = {
        "status", "brand_name", "automation_on", "last_reply_at",
        "ig_user_id",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_conversation(conversation_id)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = conversation_id
    with _conn() as conn:
        conn.execute(
            f"UPDATE conversations SET {sets} WHERE id = :id", updates
        )
    return get_conversation(conversation_id)


def list_conversations(creator_id: str = None) -> list[dict]:
    with _conn() as conn:
        if creator_id:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE creator_id = ? ORDER BY created_at DESC",
                (creator_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM conversations ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------- messages

def append_message(conversation_id: str, role: str, content: str,
                   message_meta_id: str = None) -> Optional[dict]:
    """Insert a message, deduped by message_meta_id (idempotency)."""
    if message_meta_id:
        with _conn() as conn:
            existing = conn.execute(
                "SELECT id FROM messages WHERE message_meta_id = ?",
                (message_meta_id,),
            ).fetchone()
        if existing:
            return None  # duplicate webhook delivery — already stored
    msg = {
        "id": _uuid(),
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "message_meta_id": message_meta_id,
    }
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, message_meta_id)
            VALUES (:id, :conversation_id, :role, :content, :message_meta_id)
            """,
            msg,
        )
    return get_message(msg["id"])


def get_message(message_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return dict(row) if row else None


def list_messages(conversation_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def last_message_time(conversation_id: str) -> Optional[str]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT MAX(created_at) AS t FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
    return row["t"] if row else None


# ------------------------------------------------------------------- leads

def insert_lead(conversation_id: str, brand_name: str, offer: str,
                amount: float = None) -> dict:
    lead = {
        "id": _uuid(),
        "conversation_id": conversation_id,
        "brand_name": brand_name,
        "offer": offer,
        "amount": amount,
        "status": "qualified",
    }
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO leads (id, conversation_id, brand_name, offer, amount, status)
            VALUES (:id, :conversation_id, :brand_name, :offer, :amount, :status)
            """,
            lead,
        )
    with _conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead["id"],)).fetchone()
    return dict(row)


def list_leads(creator_id: str = None) -> list[dict]:
    with _conn() as conn:
        if creator_id:
            rows = conn.execute(
                """
                SELECT l.* FROM leads l
                JOIN conversations c ON c.id = l.conversation_id
                WHERE c.creator_id = ? ORDER BY l.created_at DESC
                """,
                (creator_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
