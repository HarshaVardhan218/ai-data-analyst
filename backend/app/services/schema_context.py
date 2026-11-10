from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.dataset import Dataset


def describe_datasets(session: Session, dataset_ids: list[int] | None = None) -> str:
    """Build a plain-text description of the datasets the agent may query:
    table names, real SQL column names and types, and what profiling found.
    """
    query = session.query(Dataset).order_by(Dataset.id)
    if dataset_ids:
        query = query.filter(Dataset.id.in_(dataset_ids))
    datasets = query.all()
    if not datasets:
        return ""

    blocks = []
    for ds in datasets:
        sql_columns = session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'user_data' AND table_name = :t "
                "ORDER BY ordinal_position"
            ),
            {"t": ds.table_name},
        ).all()
        if not sql_columns:
            continue  # metadata row whose table is gone

        # Profile columns were built in the same order as the table's columns.
        profiled = ds.profile.get("columns", [])
        lines = [
            f'Table user_data."{ds.table_name}" '
            f'(dataset {ds.id}, from "{ds.original_filename}", {ds.row_count} rows)'
        ]
        for i, (col_name, data_type) in enumerate(sql_columns):
            info = profiled[i] if i < len(profiled) else {}
            details = [data_type]
            if info.get("inferred_role"):
                details.append(f"role={info['inferred_role']}")
            if info.get("null_pct"):
                details.append(f"{info['null_pct']}% null")
            if info.get("min") is not None:
                details.append(f"range {info['min']} to {info['max']}")
            samples = info.get("sample_values") or []
            if samples:
                details.append("e.g. " + ", ".join(repr(s) for s in samples[:5]))
            original = info.get("name")
            label = f'"{col_name}"' + (f' (CSV header "{original}")' if original and original != col_name else "")
            lines.append(f"  - {label}: " + "; ".join(details))
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
