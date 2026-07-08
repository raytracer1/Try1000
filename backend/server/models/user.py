"""User model — Google OAuth, password optional."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer
from server.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    google_id = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)  # null for Google-only users
    created_at = Column(DateTime, default=datetime.utcnow)
