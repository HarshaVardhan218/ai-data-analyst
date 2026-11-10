from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.services.loader import load_dataframe
from app.services.metadata import save_dataset_metadata
from app.services.profiling import profile_dataframe
from app.services.table_builder import create_user_table


class IngestionError(Exception):
    """Raised for problems with the uploaded file that the user can fix."""


def parse_csv(content: bytes) -> pd.DataFrame:
    if not content.strip():
        raise IngestionError("The uploaded file is empty.")
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise IngestionError(f"Could not parse the file as CSV: {e}") from e
    if df.empty or len(df.columns) == 0:
        raise IngestionError("The CSV has no data rows or no columns.")
    return df


def ingest_csv(
    filename: str,
    content: bytes,
    engine: Engine,
    session: Session,
) -> Dataset:
    df = parse_csv(content)
    profile = profile_dataframe(df)
    base_name = Path(filename).stem

    table_name, name_map = create_user_table(base_name, profile, engine, session)
    try:
        load_dataframe(df, table_name, name_map, profile, engine)
        return save_dataset_metadata(session, base_name, table_name, filename, profile)
    except Exception:
        # Don't leave an orphan table behind if loading or saving failed.
        session.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS user_data."{table_name}"'))
        raise
