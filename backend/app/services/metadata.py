from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dataset import Dataset


def save_dataset_metadata(
    session: Session,
    display_name: str,
    table_name: str,
    original_filename: str,
    profile: dict,
) -> Dataset:
    """Insert a row into meta.datasets describing a freshly loaded dataset.
    Commits and returns the saved Dataset (with its generated id).
    """
    dataset = Dataset(
        name=display_name,
        table_name=table_name,
        original_filename=original_filename,
        row_count=profile["row_count"],
        column_count=profile["column_count"],
        profile=profile,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    return dataset
