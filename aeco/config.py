from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://aeco:aeco@localhost:5432/aeco"
    redis_url: str = "redis://localhost:6379/0"

    # ClickUp
    clickup_api_token: str = ""
    clickup_workspace_id: str = ""
    clickup_list_id: str = ""

    # LLM API Keys
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # App
    workspace_path: str = "./workspace"
    log_level: str = "INFO"


settings = Settings()
