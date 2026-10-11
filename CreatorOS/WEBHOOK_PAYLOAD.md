# WEBHOOK_PAYLOAD — Instagram / Meta DM payload shape

This documents the exact payload the backend ingests so the AI and frontend
teams code against reality (Phase B, step 9). The backend parses this in
`app/instagram.py::parse_webhook` into a normalized event list.

## Meta Graph API `messages` webhook (Instagram Professional DMs)

Meta POSTs JSON to your webhook URL. The relevant structure is `entry[].messaging[]`:

```json
{
  "object": "instagram",
  "entry": [
    {
      "id": "ig_messenger_entry_id",
      "time": 1680000000000,
      "messaging": [
        {
          "sender": { "id": "IG_USER_ID_OF_BRAND" },
          "recipient": { "id": "IG_USER_ID_OF_CREATOR" },
          "timestamp": 1680000000000,
          "message": {
            "mid": "UNIQUE_MESSAGE_ID",
            "text": "Hi! We'd love to sponsor a post. Budget $1200."
          }
        }
      ]
    }
  ]
}
```

## Verification handshake (GET)

When you first subscribe, Meta sends a GET with `hub.*` query params. The
backend responds with the challenge echo if the token matches.

```
GET /webhook/instagram?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>
```

## Normalized event (what the backend actually consumes)

```python
{
    "ig_user_id": "IG_USER_ID_OF_BRAND",   # sender id
    "text": "Hi! We'd love to sponsor a post. Budget $1200.",
    "message_meta_id": "UNIQUE_MESSAGE_ID",  # used for idempotency (dedupe)
    "timestamp": 1680000000000,
}
```

## Key fields used downstream

| Field | Where it's used |
|-------|-----------------|
| `sender.id` | `ig_user_id` — key that opens/continues a `conversations` row |
| `message.text` | sent to the classifier → negotiator |
| `message.mid` | `message_meta_id` — dedupes Meta retries (idempotency) |
| `timestamp` | ordering + rate-limit guardrail |

## Outbound reply

Reply is sent back via the Graph API `messages` endpoint:
`POST {graph_api}/{ig_graph_token}/messages` with body
`{"recipient": {"id": <sender.id>}, "message": {"text": <reply>}}`.

## Demo / mock mode

With `MOCK_INTEGRATIONS=true` (default) the backend does **not** call Meta.
Instead you can POST the exact payload above to `/webhook/instagram`, or use
`POST /api/simulate` `{"ig_user_id": "...", "text": "..."}` — both go through
the identical orchestrator pipeline.
