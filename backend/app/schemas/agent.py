from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    dataset_ids: list[int] | None = None  # None = all datasets


class QueryResult(BaseModel):
    sql: str
    columns: list[str] = []
    rows: list[list[Any]] = []
    truncated: bool = False
    error: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    result: QueryResult | None  # the last successful query, for the table/chart
    queries: list[QueryResult]  # every query the agent tried, including failures
    model: str
