-- Creator OS — SQLite schema.
-- Mirrors the Supabase (PostgreSQL) design from the execution plan so it can
-- be migrated 1:1 to Supabase later. Uses TEXT ids to match Supabase UUIDs.

PRAGMA foreign_keys = ON;

-- One creator = one account. Holds the negotiation context.
CREATE TABLE IF NOT EXISTS creators (
    id            TEXT PRIMARY KEY,              -- creator id (uuid in supabase)
    name          TEXT NOT NULL,
    min_rate      REAL NOT NULL DEFAULT 0,       -- $ minimum acceptable rate
    tone          TEXT NOT NULL DEFAULT 'friendly',
    niche         TEXT NOT NULL DEFAULT '',
    exclusions    TEXT NOT NULL DEFAULT '',      -- comma-separated "no X, no Y"
    media_kit_url TEXT,
    instagram_id  TEXT UNIQUE,
    phone         TEXT,                          -- whatsapp handoff target
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A DM thread between a creator and an external user (brand/fan).
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY,
    creator_id    TEXT NOT NULL REFERENCES creators(id),
    ig_user_id    TEXT NOT NULL,                 -- external instagram user id
    brand_name    TEXT,                          -- resolved brand name if any
    status        TEXT NOT NULL DEFAULT 'incoming',  -- incoming|negotiating|qualified|handed_off|closed
    automation_on INTEGER NOT NULL DEFAULT 1,    -- 0 = human takeover (paused)
    last_reply_at TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conversations_creator ON conversations(creator_id);
CREATE INDEX IF NOT EXISTS idx_conversations_iguser ON conversations(ig_user_id);

-- Every message in a conversation (both inbound and outbound).
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL,               -- 'brand' (inbound) | 'creator' (outbound)
    content         TEXT NOT NULL,
    message_meta_id TEXT UNIQUE,                 -- idempotency key (ig message id)
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

-- Qualified leads surfaced for human review.
CREATE TABLE IF NOT EXISTS leads (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    brand_name      TEXT,
    offer           TEXT,
    amount          REAL,
    status          TEXT NOT NULL DEFAULT 'qualified',  -- qualified|accepted|declined
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_leads_conv ON leads(conversation_id);
