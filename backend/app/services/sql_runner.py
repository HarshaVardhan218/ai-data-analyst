from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text

from app.database.engine import analyst_engine

MAX_ROWS = 500
_ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class UnsafeQueryError(Exception):
    """Raised when generated SQL is not a single read-only query."""


def check_query(sql: str) -> str:
    """Cheap first line of defence. The real guarantee is the analyst_ro role:
    read-only transactions, SELECT-only grants, a 10s statement timeout.
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeQueryError("The query is empty.")
    if ";" in cleaned:
        raise UnsafeQueryError("Only one statement is allowed per query.")
    if not _ALLOWED_START.match(cleaned):
        raise UnsafeQueryError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    return cleaned


def _to_json_value(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def run_readonly_query(sql: str) -> dict:
    """Run a query as analyst_ro. Returns columns, rows (capped at MAX_ROWS)
    and whether the result was truncated.
    """
    cleaned = check_query(sql)
    with analyst_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        result = conn.execute(text(cleaned))
        columns = list(result.keys())
        fetched = result.fetchmany(MAX_ROWS + 1)
        conn.rollback()

    truncated = len(fetched) > MAX_ROWS
    rows = [[_to_json_value(v) for v in row] for row in fetched[:MAX_ROWS]]
    return {"sql": cleaned, "columns": columns, "rows": rows, "truncated": truncated}
