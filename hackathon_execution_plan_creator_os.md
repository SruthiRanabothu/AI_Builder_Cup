# Hackathon Project Plan: Creator OS (AI Executive Assistant)

## 1. Executive Summary
**Creator OS** is an autonomous AI Executive Assistant designed specifically for digital content creators. It solves the biggest operational bottleneck in the creator economy: lost revenue due to unmanaged DMs and administrative burnout. The MVP focuses on an **Automated Brand Deal & Collab Manager** that lives inside Instagram, negotiates on behalf of the creator, and hands off qualified leads via WhatsApp.

## 2. Core Hackathon MVP Features
1. **The DM Listener:** Hooks into the Instagram Messenger API to listen for incoming DMs.
2. **Intent Classifier:** AI determines if a message is a fan interaction, spam, or a business/collab inquiry.
3. **Autonomous Negotiator:** If it's a business inquiry, the AI acts as a talent manager, asking for budgets, deliverables, and referencing the creator's base rates (RAG).
4. **The Creator Handoff:** Once a deal is qualified (e.g., budget is confirmed), the AI pauses the automation and pings the creator on WhatsApp to take over.

---

## 3. Technical Architecture Stack

*   **Frontend (Creator Dashboard):** Next.js (React) + Tailwind CSS 
    *   *Purpose:* A simple dashboard for the creator to upload their media kit, set their minimum rates, and view qualified leads.
*   **Backend (API & Logic):** Node.js / Express OR Python (FastAPI)
    *   *Purpose:* Handles Meta Webhooks, rate limits, and orchestrates the AI logic.
*   **Database:** Supabase (PostgreSQL) or Firebase
    *   *Purpose:* Stores creator profiles, media kit data, and chat history.
*   **AI Engine:** OpenAI API (GPT-4o) or Anthropic (Claude 3.5 Sonnet)
    *   *Purpose:* Intent classification and generating conversational replies.
*   **Integration APIs:** 
    *   Instagram Graph API (for reading/sending DMs).
    *   Twilio API or WhatsApp Business API (for notifying the creator).

---

## 4. Step-by-Step Implementation Guide

### Phase 1: Platform Setup & API Webhooks (Hours 1-4)
1. **Create a Meta Developer Account:** Go to developers.facebook.com and create an app.
2. **Connect a Test Account:** Link a test Instagram Professional (Creator/Business) account to a Facebook Page.
3. **Configure Webhooks:** Set up a webhook endpoint in your backend (e.g., using Ngrok for local testing) to listen to `messages` events from the Instagram Graph API.
4. **Test the Connection:** Send a DM to your test account from a personal account and verify your backend receives the JSON payload.

### Phase 2: AI Intent Classification (Hours 4-8)
1. **Extract the Message:** Parse the text from the incoming webhook payload.
2. **The Classifier Prompt:** Send the message to your LLM with a system prompt like: 
   * *"You are a DM classifier. Categorize the following message into one of three buckets: [FAN_LOVE, SPAM, BUSINESS_INQUIRY]. Output only the category name."*
3. **Routing Logic:** 
   * If `FAN_LOVE` -> Ignore (or send a polite auto-like/reply if desired).
   * If `SPAM` -> Ignore.
   * If `BUSINESS_INQUIRY` -> Trigger the Negotiation Agent.

### Phase 3: The Negotiation Agent (Hours 8-12)
1. **Context Loading (RAG):** When a business inquiry is detected, pull the creator's preferences from your database (e.g., Minimum rate: $500, Niche: Tech/Lifestyle, Exclusions: No gambling apps).
2. **The Negotiator Prompt:** Inject this context into a new LLM call:
   * *"You are [Creator's Name]'s AI talent manager. A brand has reached out. Reply professionally, thank them, and ask for their budget and timeline. Do not agree to any terms under $500. Keep it concise, friendly, and human."*
3. **Send the Reply:** Take the LLM's output and send it back to the brand using the Instagram Graph API `messages` endpoint.

### Phase 4: The Handoff & Notification (Hours 12-16)
1. **State Tracking:** Maintain a conversation state in your database (e.g., `status: negotiating`).
2. **Qualification Trigger:** If the LLM detects that the brand has agreed to a budget or provided sufficient details, update the state to `status: qualified`.
3. **WhatsApp Alert:** Trigger an API call via Twilio to send a WhatsApp message to the creator's phone:
   * *"🚨 New Qualified Lead! [Brand Name] is offering $600 for a Reel. Go to your IG requests folder to accept and finalize!"*
4. **Pause Automation:** Ensure your backend logic ignores further messages from this user so the human creator can take over seamlessly.

### Phase 5: Dashboard & Polish (Hours 16-24)
1. Build a very simple 1-page frontend where a judge can see:
   * An input form for "Creator Minimum Rate" and "Tone of Voice."
   * A "Live Leads" table showing the bots successful negotiations.
2. **Prepare the Demo:** Do not rely on live Meta review for the hackathon. Use your pre-approved test accounts to do a live, side-by-side demo: Phone A (Brand) messaging Phone B (Creator app), with the dashboard updating in real-time.

---

## 5. Hackathon Pitch Structure (3 Minutes)
*   **The Hook (0:00-0:30):** "Creators are losing thousands of dollars a month because high-paying sponsorships get lost in a sea of spam and fan DMs."
*   **The Solution (0:30-1:00):** "Meet Creator OS: The first AI Executive Assistant that lives directly in a creator's DMs. It autonomously negotiates brand deals while they sleep."
*   **The Live Demo (1:00-2:15):** Show a live DM conversation where the AI successfully asks for a budget, verifies it against the creator's minimum rate, and sends the WhatsApp alert.
*   **The Business Model / Future (2:15-3:00):** "We charge a $29/mo SaaS fee. In the future, this expands beyond DMs to automated invoicing, calendar management, and cross-platform analytics."