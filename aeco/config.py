from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # CORS (comma-separated origins, e.g. "http://localhost:5173")
    cors_origins: str = ""

    # Claude Code CLI
    claude_code_binary: str = "claude"
    claude_code_default_timeout: int = 300

    # Initiative workflow: max seconds per task so one agent can't hang the whole run
    initiative_task_timeout_seconds: int = 600

    # Facebook/Meta Ads API
    facebook_access_token: Optional[str] = None
    facebook_ad_account_id: str = ""

    # Stripe API
    stripe_api_key: Optional[str] = None

    # WhatsApp Business API (uses Meta Cloud API)
    whatsapp_token: Optional[str] = None
    whatsapp_phone_number_id: str = ""
    whatsapp_recipient_number: str = ""  # Your phone number in international format (e.g. 14155551234)

    # App
    workspace_path: str = "./workspace"
    log_level: str = "INFO"
    log_path: Optional[str] = "logs/aeco.log"  # app log file; set empty to disable

    # Company logging (structured workflow/agent/tool logs)
    company_log_path: Optional[str] = "logs/company.log"  # JSON lines; set empty to disable
    company_log_console: bool = True  # also emit to stderr


settings = Settings()
