"""Run this once (and again any time a new model is added) to create
the meta schema's tables. Safe to re-run: create_all only creates
tables that don't already exist.
"""
from app.database.base import Base
from app.database.engine import app_engine
from app.models.dataset import Dataset  # noqa: F401  (import registers it with Base)


def init_meta_tables():
    Base.metadata.create_all(app_engine)
    print("Meta tables created (if they didn't already exist).")


if __name__ == "__main__":
    init_meta_tables()
