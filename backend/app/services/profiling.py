from __future__ import annotations

import pandas as pd


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
        looks_like_id = column_name.lower().endswith("_id") or column_name.lower() == "id"
        if looks_like_id and unique_ratio > 0.95:
            return "id"
        return "numeric"

    # Anything else (legacy "object" dtype, or pandas' newer "str" dtype) is
    # string-like. Try parsing it as a date before falling back to text/categorical.
    parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
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
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
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
