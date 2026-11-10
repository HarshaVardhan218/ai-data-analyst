from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    name: str
    pandas_dtype: str
    inferred_role: str
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: list[str]
    min: float | str | None = None
    max: float | str | None = None
    mean: float | None = None


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    duplicate_row_count: int
    columns: list[ColumnProfile]


class DatasetResponse(BaseModel):
    id: int
    name: str
    table_name: str
    original_filename: str
    row_count: int
    column_count: int
    created_at: datetime
    profile: DatasetProfile

    model_config = {"from_attributes": True}
