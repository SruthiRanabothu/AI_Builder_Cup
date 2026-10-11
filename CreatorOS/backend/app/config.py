"""Application configuration loaded from environment / .env file.

Uses pydantic-settings. All secrets come from the environment; the
.env loader is provided by python-dotenv.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- AI provider ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- Creator profile (used by seed) ---
    creator_name: str = "Maya Chen"
    creator_min_rate: int = 500
    creator_niche: str = "Tech & Lifestyle"
    creator_tone: str = "friendly, professional, concise"
    creator_exclusions: str = "no gambling, no crypto"
    creator_instagram_id: str = "ig_creator_maya"
    creator_phone: str = "whatsapp:+15551234567"

    # --- Integration toggles ---
    mock_integrations: bool = True

    # --- Meta / Instagram ---
    ig_graph_token: str = ""
    ig_graph_api: str = "https://graph.facebook.com/v19.0"

    # --- Twilio ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""

    # --- Webhook ---
    webhook_verify_token: str = "creatoros-verify-123"

    # --- Runtime ---
    database_path: str = "./data/creatoros.db"
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Guardrails ---
    # Seconds between auto-replies to the same conversation (anti-spam).
    # Default is short for the hackathon demo; raise for production.
    reply_rate_limit_seconds: int = 5
    max_reply_chars: int = 400
    max_history_messages: int = 24

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
