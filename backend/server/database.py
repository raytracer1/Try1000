"""SQLAlchemy engine and session management.

Supports both PostgreSQL (production) and SQLite (local dev).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from server.config import settings

# SQLite needs check_same_thread=False for FastAPI's threaded access
connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
engine = create_engine(
    settings.database_url,
    pool_size=10 if not settings.is_sqlite else 1,
    max_overflow=20,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Import models first to register them with Base.metadata."""
    import server.models  # noqa: F401 — registers all tables with Base
    Base.metadata.create_all(bind=engine)
