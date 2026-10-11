# Creator OS — Autonomous AI Executive Assistant for Content Creators

> **MVP:** Automated Brand Deal & Collab Manager that lives inside Instagram DMs.
> The AI classifies DMs, negotiates brand deals on the creator's behalf
> (enforcing a minimum rate and exclusions), and hands qualified leads to the
> creator via a WhatsApp alert + live dashboard — while they sleep.

This repo is a working, **demoable, fundable** MVP built from
`Creator_OS_Execution_Plan.md`. It runs fully offline with mock Instagram &
WhatsApp layers, so the entire flow demos end-to-end **without Meta/Twilio
review or credentials**.

---

## What it does

1. **Classify** every inbound DM into `FAN_LOVE` | `SPAM` | `BUSINESS_INQUIRY`
   (Gemini, with an offline heuristic fallback — 100% on the 20-message test set).
2. **Negotiate** with business inquiries using the creator's context
   (min rate, tone, niche, exclusions). Never accepts below min rate,
   respects exclusions, never reveals it's an AI.
3. **Qualify** a deal when a budget ≥ min rate is confirmed → stores a lead.
4. **Hand off:** fires a WhatsApp alert to the creator and **pauses automation**
   for that conversation (human takeover).
5. **Dashboard** shows the creator profile, live leads, conversations, and the
   conversation log — updating in real time.

---

## Tech stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | **Python / FastAPI** | webhooks + orchestration + AI |
| AI | **Google Gemini** | classifier + negotiator + qualified-detector; offline heuristic fallback |
| DB | **SQLite now → Supabase-ready** | schema mirrors the Supabase (Postgres) design; `db.py` is the only file to swap |
| Integrations | **Mock by default** | real Meta Graph API + Twilio paths included |
| Dashboard | Single-page HTML/JS served by FastAPI | polls `/api/dashboard` |

---

## Quick start

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # optional: add GEMINI_API_KEY for smarter AI
.venv/bin/python seed.py       # create demo creator + pre-qualified leads
.venv/bin/python -m uvicorn app.main:app --reload
```

Then open **http://localhost:8000** for the dashboard.

### Run the scripted demo (no server needed)

```bash
.venv/bin/python seed.py
.venv/bin/python simulator.py
```

This plays a full conversation: fan → spam → lowball → qualifying offer →
WhatsApp handoff → automation pause.

### Run the tests

```bash
.venv/bin/python -m pytest tests -v
```

---

## Demo it live

1. Start the server, open the dashboard.
2. In the **DM Simulator** panel, send a brand message, e.g.
   `"Hi! This is Acme Co. We love your content and want to sponsor a post. Budget $1200."`
3. Watch it get classified, negotiated, and **qualified**.
4. The **Handoff Alert** panel shows the WhatsApp message that "hit the creator's phone";
   the lead appears in **Live Leads**; the conversation is marked **paused**.

You can also POST a real Meta-shaped payload to `/webhook/instagram` (see
`WEBHOOK_PAYLOAD.md`).

---

## Enable Gemini AI (optional)

Put your key in `.env`:

```
GEMINI_API_KEY=your_key
```

With no key, the system uses the built-in keyword classifier and template
negotiator, so everything still works offline.

---

## Project layout

```
CreatorOS/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + routes
│   │   ├── orchestrator.py  # core DM → action pipeline
│   │   ├── classifier.py    # FAN/SPAM/BUSINESS (Gemini + heuristic)
│   │   ├── negotiator.py    # negotiation + qualified detector
│   │   ├── instagram.py     # Meta webhook parse + send (mock/real)
│   │   ├── whatsapp.py      # Twilio handoff alert (mock/real)
│   │   ├── gemini_client.py # Gemini wrapper
│   │   ├── db.py            # persistence (swap for Supabase later)
│   │   └── schema.sql       # Supabase-compatible schema
│   ├── seed.py              # demo creator + leads
│   ├── simulator.py         # scripted CLI demo
│   └── tests/               # classifier (20 msgs) + end-to-end flow
├── dashboard/index.html     # live dashboard
├── WEBHOOK_PAYLOAD.md       # documented IG payload shape
└── README.md
```

---

## Security & guardrails

- Secrets live in `.env` (gitignored). Never commit them.
- Webhook verification token handshake enforced.
- Idempotent message dedupe (handles Meta retries).
- Rate-limited auto-replies; capped reply length.
- Safe fallback: unparseable/LLM-failure → `FAN_LOVE` (never spam a brand).
- Automation pauses on qualification (human takeover).

## Moving to Supabase (post-hackathon)

The schema in `app/schema.sql` is 1:1 with the Supabase Postgres tables.
Replace the helpers in `app/db.py` with Supabase (postgrest) calls — no other
module touches SQL. Then enable Supabase Realtime for the dashboard instead of
polling.

## Business model (pitch)

$29/mo SaaS per creator. Roadmap: automated invoicing, calendar/booking,
cross-platform (YouTube/TikTok) DM ingestion, production Meta app approval.
