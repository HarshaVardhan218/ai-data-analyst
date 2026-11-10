from __future__ import annotations

import re

import pandas as pd

_SLASH_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}")


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse date strings, working out day/month order for dates like 03/04/2024:
    if any value has a first part over 12 (e.g. 13/03/2024), the column is day-first."""
    dayfirst = False
    for value in series.dropna().astype(str).head(1000):
        m = _SLASH_DATE.match(value)
        if not m:
            continue
        first, second = int(m.group(1)), int(m.group(2))
        if first > 12:
            dayfirst = True
            break
        if second > 12:
            break  # month-first, e.g. 10/16/2019
    return pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=dayfirst)


def infer_column_role(series: pd.Series, column_name: str) -> str:
    """Classify a column into a role we can reason about later:
    'id', 'numeric', 'datetime', 'categorical', or 'text'.
    """
    non_null = series.dropna()

    if non_null.empty:
        return "text"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_numeric_dtype(series):
        unique_ratio = non_null.nunique() / len(non_null)
        # "id", "customer_id", "Order ID"
        looks_like_id = re.search(r"(^|[\s_])id$", column_name.strip().lower()) is not None
        if looks_like_id and unique_ratio > 0.95:
            return "id"
        return "numeric"

    # Anything else (legacy "object" dtype, or pandas' newer "str" dtype) is
    # string-like. Try parsing it as a date before falling back to text/categorical.
    # Digit-only codes (zip "02683", "20240115"-style IDs) are not dates.
    as_text = non_null.astype(str).str.strip()
    if not as_text.str.fullmatch(r"\d+").all():
        parsed = parse_dates(non_null)
        if parsed.notna().mean() > 0.9:
            return "datetime"

    unique_ratio = non_null.nunique() / len(non_null)
    if unique_ratio < 0.5:
        return "categorical"
    return "text"


def profile_column(series: pd.Series, column_name: str) -> dict:
    non_null = series.dropna()
    role = infer_column_role(series, column_name)

    profile = {
        "name": column_name,
        "pandas_dtype": str(series.dtype),
        "inferred_role": role,
        "null_count": int(series.isna().sum()),
        "null_pct": round(float(series.isna().mean()) * 100, 2),
        "unique_count": int(non_null.nunique()),
        "sample_values": non_null.drop_duplicates().head(5).astype(str).tolist(),
    }

    if role in ("numeric", "id") and not non_null.empty:
        profile["min"] = float(non_null.min())
        profile["max"] = float(non_null.max())
        profile["mean"] = round(float(non_null.mean()), 2)

    if role == "datetime" and not non_null.empty:
        parsed = parse_dates(non_null)
        profile["min"] = str(parsed.min())
        profile["max"] = str(parsed.max())

    return profile


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Build a full dataset profile: row/column counts, duplicates, and a
    per-column profile for every column.
    """
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_row_count": int(df.duplicated().sum()),
        "columns": [profile_column(df[col], col) for col in df.columns],
    }
