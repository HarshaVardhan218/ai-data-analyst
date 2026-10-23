from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = {"schema": "meta"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
