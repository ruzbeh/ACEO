from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Local dashboard dev (Vite). Used when CORS_ORIGINS is unset or empty in .env (empty overrides the default below).
DEV_CORS_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5174,http://127.0.0.1:5174,"
    "http://localhost:5175,http://127.0.0.1:5175,"
    "http://localhost:5176,http://127.0.0.1:5176,"
    "http://localhost:4173,http://127.0.0.1:4173,"
    "http://localhost:8100,http://127.0.0.1:8100"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database (defaults to local SQLite for easy dev; use PostgreSQL in production)
    database_url: str = "sqlite+aiosqlite:///aeco.db"
    redis_url: str = "redis://localhost:6379/0"

    # ClickUp
    clickup_api_token: str = ""
    clickup_workspace_id: str = ""
    clickup_list_id: str = ""

    # LLM API Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    # LLM request timeout (seconds); prevents workflow hanging forever on slow/missing API
    llm_request_timeout: float = 120.0

    # Chroma (vector store). If set, use HTTP client; else use local persist.
    chroma_host: Optional[str] = None
    chroma_port: int = 8001

    # CORS (comma-separated origins). Use CORS_ORIGINS=__DISABLED__ to turn off middleware.
    cors_origins: str = DEV_CORS_ORIGINS

    # Claude Code CLI
    claude_code_binary: str = ""  # Auto-detected at startup
    claude_code_default_timeout: int = 900

    # Initiative workflow: max seconds per task so one agent can't hang the whole run
    initiative_task_timeout_seconds: int = 900

    # Facebook/Meta Ads API
    facebook_app_id: Optional[str] = None
    facebook_app_secret: Optional[str] = None
    facebook_access_token: Optional[str] = None
    facebook_ad_account_id: str = ""

    # Runway ML — image-to-video generation (Phase 2 video harness)
    runway_api_key: Optional[str] = None

    # ElevenLabs — voiceover TTS (Phase 2 video harness)
    elevenlabs_api_key: Optional[str] = None

    # Stripe API
    stripe_api_key: Optional[str] = None

    # Resend email API
    resend_api_key: Optional[str] = None
    resend_from_email: str = "onboarding@resend.dev"

    # WhatsApp Business API (uses Meta Cloud API)
    whatsapp_token: Optional[str] = None
    whatsapp_phone_number_id: str = ""
    whatsapp_recipient_number: str = ""  # Your phone number in international format (e.g. 14155551234)

    # Postmortem Writer: optional base URL(s) for screenshots (e.g. http://localhost:8000/dashboard/)
    postmortem_dashboard_base_url: str = ""

    # App
    workspace_path: str = "/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio"
    log_level: str = "INFO"
    log_path: Optional[str] = "logs/aeco.log"  # app log file; set empty to disable

    # Company logging (structured workflow/agent/tool logs)
    company_log_path: Optional[str] = "logs/company.log"  # JSON lines; set empty to disable
    company_log_console: bool = True  # also emit to stderr


settings = Settings()


def effective_cors_origins() -> str | None:
    """Origins for CORSMiddleware, or None to skip (same-origin-only deployments)."""
    raw = (settings.cors_origins or "").strip()
    if raw.upper() == "__DISABLED__":
        return None
    if not raw:
        return DEV_CORS_ORIGINS
    return raw
