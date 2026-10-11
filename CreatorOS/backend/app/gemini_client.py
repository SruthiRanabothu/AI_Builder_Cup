"""Thin wrapper around the Google Gemini API.

Kept separate so the classifier / negotiator / qualified-detector share one
client and a single error-handling path. Falls back gracefully on any error
(callers implement their own heuristic fallbacks).
"""
import google.generativeai as genai

from .config import get_settings

_client = None


def _get_client():
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.has_gemini:
            raise RuntimeError("GEMINI_API_KEY not configured")
        genai.configure(api_key=settings.gemini_api_key)
        _client = genai
    return _client


def gemini_generate_text(prompt, model: str = None) -> str:
    """Return plain text from Gemini. Raises on any failure."""
    settings = get_settings()
    client = _get_client()
    genai_model = client.GenerativeModel(model or settings.gemini_model)
    # `prompt` may be a list of parts (dicts) for multi-turn-ish context.
    content = prompt if isinstance(prompt, str) else prompt
    resp = genai_model.generate_content(content)
    return resp.text.strip()


def gemini_generate_json(prompt, model: str = None) -> dict:
    """Ask Gemini for JSON and parse it. Raises on failure/unparseable."""
    settings = get_settings()
    client = _get_client()
    genai_model = client.GenerativeModel(
        model or settings.gemini_model,
        generation_config={"response_mime_type": "application/json"},
    )
    content = prompt if isinstance(prompt, str) else prompt
    resp = genai_model.generate_content(content)
    return _safe_json(resp.text)


def _safe_json(text: str) -> dict:
    import json
    import re

    if not text:
        return {}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
