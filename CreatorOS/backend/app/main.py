"""Creator OS — FastAPI application.

Endpoints:
    GET  /                       -> dashboard (served static)
    GET  /health                 -> health check
    GET  /webhook/instagram      -> Meta webhook verification handshake
    POST /webhook/instagram      -> inbound DM webhook (real payloads)
    POST /api/simulate           -> simulate a brand DM (mock mode)
    GET  /api/dashboard          -> aggregated data for the dashboard
    GET  /api/leads              -> list leads
    GET  /api/conversations      -> list conversations
    GET  /api/conversations/{id}/messages
    GET  /api/alerts             -> mock whatsapp outbox
    POST /api/creators           -> upsert creator
    GET  /api/creators           -> list creators
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, instagram, orchestrator, whatsapp

app = FastAPI(title="Creator OS", version="0.1.0")

DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"

# Ensure tables exist on startup (safe to call repeatedly).
db.init_db()


# ---------------------------------------------------------------- schemas

class SimulateRequest(BaseModel):
    ig_user_id: str = "ig_brand_001"
    text: str
    message_meta_id: str = None


class CreatorPayload(BaseModel):
    id: str = None
    name: str
    min_rate: float = 0
    tone: str = "friendly"
    niche: str = ""
    exclusions: str = ""
    media_kit_url: str = None
    instagram_id: str = None
    phone: str = None


# ----------------------------------------------------------------- health

@app.get("/health")
def health():
    return {"status": "ok", "service": "creator-os"}


# ------------------------------------------------------- IG webhook (Meta)

@app.get("/webhook/instagram")
def verify_instagram(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    challenge = instagram.verify_webhook(
        {
            "hub.mode": hub_mode,
            "hub.verify_token": hub_verify_token,
            "hub.challenge": hub_challenge,
        }
    )
    if challenge:
        return Response(challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook/instagram")
async def instagram_webhook(request: Request):
    payload = await request.json()
    events = instagram.parse_webhook(payload)
    results = []
    for ev in events:
        try:
            results.append(
                orchestrator.handle_inbound(
                    ev["ig_user_id"], ev["text"], ev["message_meta_id"]
                )
            )
        except orchestrator.OrchestratorError as exc:
            results.append({"error": str(exc)})
    # Meta expects a 200 (with any body) to ack delivery.
    return JSONResponse({"received": len(events), "results": results})


# ------------------------------------------------------------------ simulate

@app.post("/api/simulate")
def simulate_dm(req: SimulateRequest):
    """Simulate an inbound DM from a 'brand' account (mock demo path)."""
    try:
        return orchestrator.handle_inbound(
            req.ig_user_id, req.text, req.message_meta_id
        )
    except orchestrator.OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------ data API

@app.get("/api/dashboard")
def dashboard():
    creator = (db.list_creators() or [None])[0]
    leads = db.list_leads(creator["id"] if creator else None)
    conversations = db.list_conversations(creator["id"] if creator else None)
    return {
        "creator": creator,
        "leads": leads,
        "conversations": conversations,
        "alerts": whatsapp.MOCK_OUTBOX[-20:][::-1],
    }


@app.get("/api/leads")
def leads():
    creator = (db.list_creators() or [None])[0]
    return {"leads": db.list_leads(creator["id"] if creator else None)}


@app.get("/api/conversations")
def conversations():
    return {"conversations": db.list_conversations()}


@app.get("/api/conversations/{conv_id}/messages")
def conversation_messages(conv_id: str):
    messages = db.list_messages(conv_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": messages}


@app.get("/api/alerts")
def alerts():
    return {"alerts": whatsapp.MOCK_OUTBOX[-20:][::-1]}


@app.post("/api/creators")
def upsert_creator(payload: CreatorPayload):
    return db.upsert_creator(payload.model_dump(exclude_none=True))


@app.get("/api/creators")
def list_creators():
    return {"creators": db.list_creators()}


# ------------------------------------------------------------------- static

# Serve the dashboard as the app root.
if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(DASHBOARD_DIR / "index.html"))
