"""Application configuration from environment variables."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — PostgreSQL for prod, SQLite for local dev
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./try1000.db"
    )

    # JWT
    jwt_secret_key: str = os.environ.get("TRY1000_JWT_SECRET_KEY", "change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Google OAuth
    google_client_id: str = os.environ.get("TRY1000_GOOGLE_CLIENT_ID", "")

    # Supabase Storage
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    supabase_service_key: str = os.environ.get("SUPABASE_SERVICE_KEY", "")

    # Ably
    ably_api_key: str = os.environ.get("TRY1000_ABLY_API_KEY", "")

    # LLM (user overrides per account)
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    # Simulation
    max_matches_per_job: int = 1000

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
