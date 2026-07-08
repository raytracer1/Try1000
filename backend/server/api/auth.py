"""Auth endpoints — Google OAuth + HttpOnly cookie JWT."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from server.database import get_db
from server.models.user import User
from server.schemas.auth import GoogleAuthRequest, UserResponse
from server.auth.jwt_handler import create_access_token, get_current_user, COOKIE_NAME
from server.config import settings

router = APIRouter()


@router.post("/google")
def google_auth(req: GoogleAuthRequest, response: Response,
                db: Session = Depends(get_db)):
    """Verify Google ID token, create user if new, set JWT cookie."""
    try:
        info = id_token.verify_oauth2_token(
            req.credential, google_requests.Request(), settings.google_client_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = info["email"]
    name = info.get("name", email.split("@")[0])
    google_id = info["sub"]

    user = db.query(User).filter(
        (User.google_id == google_id) | (User.email == email)).first()

    if user:
        if not user.google_id:
            user.google_id = google_id
        user.username = user.username or name
    else:
        user = User(email=email, username=name, google_id=google_id)
        db.add(user)

    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    response.set_cookie(
        key=COOKIE_NAME, value=token,
        httponly=True, secure=True, samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
def me(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404)
    return UserResponse(id=user.id, email=user.email, username=user.username or "")
