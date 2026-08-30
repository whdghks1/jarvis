import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    database_url: str
    openai_model: str | None
    auto_create_tables: bool
    conversation_history_limit: int
    owner_id: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "JARVIS API"),
        app_version=os.getenv("APP_VERSION", "0.2.0"),
        environment=os.getenv("ENVIRONMENT", "development"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://jarvis:jarvis@localhost:5432/jarvis",
        ),
        openai_model=os.getenv("OPENAI_MODEL") or None,
        auto_create_tables=_as_bool(os.getenv("AUTO_CREATE_TABLES"), False),
        conversation_history_limit=max(
            2, int(os.getenv("CONVERSATION_HISTORY_LIMIT", "20"))
        ),
        owner_id=os.getenv("OWNER_ID", "owner"),
    )
