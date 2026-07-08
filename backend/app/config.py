"""Application configuration from environment variables.

Priority: env vars > .env file > defaults
Supports both PostgreSQL (production) and SQLite (local dev).
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — PostgreSQL for prod, SQLite for local dev
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./try1000.db"  # SQLite fallback
    )

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # LLM (optional — if not set, engine uses Level 1 rule-based)
    llm_provider: str = ""  # "anthropic" | "openai"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    # Ably (for engine communication)
    ably_api_key: str = ""

    # Simulation
    max_matches_per_job: int = 1000

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    model_config = {"env_prefix": "TRY1000_", "env_file": ".env"}


settings = Settings()
