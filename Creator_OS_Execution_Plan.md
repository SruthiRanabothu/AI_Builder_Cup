# Creator OS — Full Execution Plan & Roadmap to Success

> **Project:** Creator OS — An Autonomous AI Executive Assistant for Content Creators
> **MVP Focus:** Automated Brand Deal & Collab Manager that lives inside Instagram DMs
> **Goal:** Convert an idea into a working, demoable, fundable product at the hackathon — and a foundation for post-hackathon growth.

---

## 0. Success Criteria (Define "Done" First)

Before writing any code, we must agree on what "success" looks like. Everything below serves these targets.

| # | Success Metric | Target | How We Verify |
|---|----------------|--------|---------------|
| S1 | Live end-to-end DM flow | A DM from "Brand" → classified → negotiated → qualified lead hits WhatsApp + dashboard | Live demo with 2 test accounts |
| S2 | Working intent classifier | Correctly buckets FAN / SPAM / BUSINESS ≥ 90% on test set | Run 20 curated test messages |
| S3 | Autonomous negotiation | Bot asks for budget, rejects < min rate, closes at acceptable deal | Scripted demo conversation |
| S4 | Human handoff | Automation pauses; WhatsApp alert fires; creator takes over | Watch live notification + takeover |
| S5 | Judge-ready demo | 3-min pitch + working dashboard + live demo, no Meta review dependency | Dress rehearsal |
| S6 | Credible pitch | Clear hook, demo, business model, roadmap | Rehearsed script + slides |

---

## 1. Pre-Flight: Team & Scope Decisions (Day 0 · 30–60 min)

Before building, lock in roles and boundaries so the team runs parallel without conflict.

1. **Assign roles** (map to strengths):
   - **Backend/API lead** — webhooks, orchestration, AI integration.
   - **Frontend lead** — Next.js dashboard.
   - **AI/LLM lead** — prompts, RAG, classifier accuracy.
   - **Integrations/Infra lead** — Meta/Instagram setup, Twilio, Supabase, deploy.
   - *(If solo, you own all — budget time accordingly.)*
2. **Decide the AI provider** — pick **ONE**: OpenAI (GPT-4o) *or* Anthropic (Claude). Do not build against both in the MVP.
3. **Decide the backend language** — pick **ONE**: Node/Express *or* Python/FastAPI. Match it to the team's strongest skill.
4. **Decide the database** — **Supabase (PostgreSQL)** is recommended (free tier, realtime, auth, storage for media kit). Firebase only if the team knows it better.
5. **Decide the messaging channel for handoff** — **Twilio WhatsApp API** is the simplest path (sandbox is fine for the demo).
6. **Create the shared repo** and a `.env` convention doc (never commit secrets).

---

## 2. Phase A — Foundations & Environment (Hours 0–2)

Get every machine ready so no time is lost later.

1. **Scaffold the monorepo** with two folders:
   - `backend/` (API + webhook handler + AI orchestration)
   - `dashboard/` (Next.js app)
2. **Backend setup:** init Node/FastAPI project, add config loader for env vars, basic `/health` route.
3. **Dashboard setup:** `create-next-app`, Tailwind installed, a blank home page renders.
4. **Database schema draft** in Supabase — create tables now (details in Phase C):
   - `creators` (id, name, min_rate, tone, niche, exclusions, media_kit)
   - `conversations` (id, ig_user_id, status, created_at)
   - `messages` (id, conversation_id, role, content, created_at)
   - `leads` (id, conversation_id, brand_name, offer, status)
5. **Set up `ngrok`** and confirm the local backend is reachable via a public HTTPS URL (Meta requires HTTPS webhooks).
6. **Add a `.gitignore`** covering `.env`, `node_modules`, build outputs.

**✅ Gate to move on:** `/health` returns 200 through the ngrok URL; dashboard loads; Supabase tables exist.

---

## 3. Phase B — Instagram/Meta Integration (Hours 2–6)

This is the highest-risk external dependency. Do it early and de-risk fully.

1. **Create a Meta developer account** at developers.facebook.com.
2. **Create a Meta App** with the "Instagram" product enabled.
3. **Set up test accounts:**
   - One **Instagram Professional (Creator/Business)** test account = the "Creator."
   - One **personal** test account = the "Brand."
   - Link the Creator's IG to a Facebook Page (required by the IG Graph API).
4. **Generate long-lived tokens** for the Creator account.
5. **Subscribe to webhooks** for the `messages` field on the Creator's IG.
6. **Configure the webhook endpoint** pointing at the ngrok URL; verify the "verify token" handshake succeeds.
7. **Send a test DM** from the Brand account → confirm the backend logs the JSON payload (sender id, message text, timestamp).
8. **Implement the DM send path:** call the Graph API `messages` endpoint with `{ recipient, message }` to reply from the Creator account.
9. **Document the payload shape** in a `WEBHOOK_PAYLOAD.md` so the AI team codes against reality, not assumptions.

**⚠️ Pitfall to avoid:** Do **not** rely on Meta's live-app review. Keep everything on test accounts and sandbox mode for the demo.

**✅ Gate to move on:** incoming DM triggers a logged event; outbound reply delivers; round-trip proven.

---

## 4. Phase C — Database & Data Model (Hours 4–7, parallel with B)

1. **Finalize and create the Supabase schema** (tables from Phase A step 4) with foreign keys and sensible defaults.
2. **Add Row Level Security (RLS)** so each creator only sees their own data.
3. **Build a small seed script** that inserts a demo creator (min rate $500, niche Tech/Lifestyle, exclusions "no gambling").
4. **Write the DB helper layer** in the backend: `getCreator`, `createConversation`, `appendMessage`, `updateConversationStatus`, `insertLead`.
5. **Add realtime subscriptions** (optional, Phase F) so the dashboard can live-update without polling.

**✅ Gate to move on:** helper functions insert/read test rows correctly.

---

## 5. Phase D — AI Intent Classifier (Hours 6–9)

1. **Build the classifier module** that takes a message string → category.
2. **Write the classification prompt** (system message):
   > *"You are a DM classifier for a content creator. Classify the message into exactly one bucket: FAN_LOVE, SPAM, or BUSINESS_INQUIRY. Output only the bucket name."*
3. **Use structured output / JSON mode** if the provider supports it, for reliable parsing.
4. **Build a 20-message test set** (mix of fans, spam, real brand inquiries) and iterate until ≥ 90% correct.
5. **Implement routing logic:**
   - `FAN_LOVE` → (optional) polite auto-reply, or ignore.
   - `SPAM` → ignore (no reply).
   - `BUSINESS_INQUIRY` → hand to the Negotiator.
6. **Add a fallback:** if the LLM call fails or output is unparseable, default to `FAN_LOVE` (safe: never spam a brand).

**✅ Gate to move on:** classifier passes the ≥90% accuracy bar on the test set.

---

## 6. Phase E — The Negotiation Agent (Hours 8–13)

1. **Build the RAG/context loader:** on `BUSINESS_INQUIRY`, pull the creator's min rate, niche, tone, and exclusions from Supabase.
2. **Write the negotiator system prompt** (inject context):
   > *"You are [Creator]'s AI talent manager. A brand has reached out. Reply professionally, thank them, ask for their budget and timeline. Never agree to terms below $[MIN_RATE]. Respect these exclusions: [EXCLUSIONS]. Keep replies concise, friendly, and human. Do not reveal that you are an AI."*
3. **Implement the conversational loop:**
   - Append the user's message to the conversation history.
   - Load the creator's context.
   - Call the LLM for a reply.
   - Send the reply via the Instagram `messages` endpoint.
   - Store both sides in `messages` and keep `conversation.status = negotiating`.
4. **Add guardrails:**
   - Cap reply length (avoid wall-of-text).
   - Rate-limit replies to the same user (e.g., 1 per 60s).
   - Never auto-commit a deal above min rate without human sign-off — only *flag* it as qualified.
5. **Add a "qualified" detector:** after each exchange, run a lightweight check (LLM boolean or keyword/heuristic) for "budget confirmed & ≥ min rate" → set `status = qualified` and store the offer.

**✅ Gate to move on:** a scripted 4–6 message brand conversation ends with the bot asking budget, rejecting a lowball, and flagging a qualifying offer.

---

## 7. Phase F — Handoff, WhatsApp Alert & Dashboard (Hours 12–17)

1. **Trigger the handoff:** when `status` flips to `qualified`, call **Twilio WhatsApp API**:
   > *"🚨 New Qualified Lead! [Brand] is offering $[OFFER]. Reply in the app or open your IG requests folder to finalize."*
2. **Pause automation:** set a flag on the conversation so the bot ignores further DMs from that user (human takeover).
3. **Build the dashboard (1-page):**
   - Form: creator minimum rate + tone of voice.
   - "Live Leads" table: brand, offer, status, timestamp (powered by Supabase realtime so it updates live).
   - Simple "conversation log" viewer for the current demo conversation.
4. **Wire dashboard ↔ backend ↔ DB:** updates from negotiations reflect on screen in real time.

**✅ Gate to move on:** qualifying a deal fires a WhatsApp message, pauses the bot, and updates the dashboard live.

---

## 8. Phase G — End-to-End Test & Hardening (Hours 17–20)

1. **Run the full loop 5×:** Brand DMs → classify → negotiate → qualify → WhatsApp + dashboard update.
2. **Test edge cases:**
   - Spam/fan messages ignored.
   - Lowball offers rejected gracefully.
   - LLM failure/timeout → safe fallback.
   - Duplicate webhook deliveries (Meta can retry) → idempotency via message dedupe.
3. **Add basic logging** and a simple error-alert (console/log) for the demo operator.
4. **Load the demo data** (a few pre-qualified leads) so the dashboard never looks empty.
5. **Freeze the scope** — no new features past this point; only fixes.

**✅ Gate to move on:** full loop runs reliably 5/5 times with no manual intervention.

---

## 9. Phase H — Demo & Pitch Preparation (Hours 20–24)

1. **Build the live demo flow (side-by-side, no Meta review):**
   - Phone/Device A = the Brand (personal test account).
   - Phone/Device B = the Creator (pro IG account).
   - Projector shows the dashboard updating in real time.
   - Pre-script the exact messages the Brand will send.
2. **Write the 3-minute pitch script** (from the original doc):
   - **Hook (0:00–0:30):** "Creators lose thousands a month because high-paying sponsorships drown in spam and fan DMs."
   - **Solution (0:30–1:00):** "Meet Creator OS — the AI executive assistant that lives in a creator's DMs and negotiates brand deals while they sleep."
   - **Live Demo (1:00–2:15):** show classify → negotiate → qualify → WhatsApp alert.
   - **Business model (2:15–3:00):** "$29/mo SaaS; future = invoicing, calendar, cross-platform analytics."
3. **Build 3–5 slides** (hook, problem, solution, demo, business model, roadmap).
4. **Dress rehearsal:** run the entire pitch + demo end-to-end at least twice; time it.
5. **Prepare answers to likely judge questions:**
   - How is this different from an auto-reply bot? *(RAG + rate enforcement + human handoff.)*
   - What about IG API limits / Meta review? *(Test-account demo; production uses approved app + token tiers.)*
   - What's the moat? *(Creator-specific data, negotiation history, trust.)*

**✅ Gate to move on:** full rehearsal passes within time; no live demo blocker remains.

---

## 10. Phase I — Submission & Post-Hackathon (After Demo)

1. **Package the submission:** repo link, 1-page README (pitch + how to run), short demo video.
2. **Record a backup demo video** in case the live demo fails at the last second.
3. **Collect feedback** from judges/mentors — note every objection.
4. **Define the next 30-day roadmap** (pick 1–2, not all):
   - Production Meta app approval for real accounts.
   - Automated invoicing.
   - Calendar/booking management.
   - Cross-platform (YouTube/TikTok) DM ingestion.
5. **Set up a waitlist landing page** to capture creator emails from the demo.

---

## 11. Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Meta review blocks real IG use | High | High | Demo on pre-approved test accounts only |
| Webhook payload shape differs from docs | Medium | High | Capture real payload in Phase B, code against it |
| LLM cost / rate limits during demo | Medium | Medium | Cache replies, cap tokens, use cheap model for classification |
| LLM outputs unparseable / hallucinated | Medium | Medium | Structured output + safe fallback to FAN_LOVE |
| Duplicate webhook deliveries | Medium | Medium | Idempotent message dedupe |
| Live demo network failure | Medium | High | Backup recorded video + pre-cached dashboard data |
| Time overrun in integration | High | High | Freeze scope at Phase G; fix-only after |
| Team conflict / unclear ownership | Medium | Medium | Roles locked in Pre-Flight |

---

## 12. Time Budget Summary

| Phase | Hours | Status |
|-------|-------|--------|
| 0–1. Pre-flight & scope | 0–1 | ☐ |
| 2. Foundations | 1–2 | ☐ |
| 3. Meta/Instagram integration | 2–6 | ☐ |
| 4. Database | 4–7 (parallel) | ☐ |
| 5. Intent classifier | 6–9 | ☐ |
| 6. Negotiation agent | 8–13 | ☐ |
| 7. Handoff + dashboard | 12–17 | ☐ |
| 8. E2E test & hardening | 17–20 | ☐ |
| 9. Demo & pitch | 20–24 | ☐ |
| 10. Submission & next steps | post-demo | ☐ |

---

## 13. Definition of Done (Final Checklist)

- [ ] A DM from the Brand account is received by the backend.
- [ ] The classifier labels it BUSINESS_INQUIRY (not spam/fan).
- [ ] The negotiator replies with context (rate, tone, exclusions) enforced.
- [ ] A qualifying offer flips status to `qualified`.
- [ ] A WhatsApp notification reaches the creator's phone.
- [ ] Automation pauses for that conversation.
- [ ] The dashboard shows the live lead in real time.
- [ ] The 3-minute pitch + live demo pass the full dress rehearsal.

> **When all boxes above are checked, the project is a success by our own definition.**
