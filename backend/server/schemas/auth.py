"""Auth schemas."""

from pydantic import BaseModel


class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token from frontend


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    llm_provider: str | None = None
    llm_model: str | None = None
    has_llm_key: bool = False  # never expose the actual key


class LLMSettingsRequest(BaseModel):
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5"
