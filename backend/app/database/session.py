from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from app.database.engine import app_engine

SessionLocal = sessionmaker(bind=app_engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
