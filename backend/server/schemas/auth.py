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
