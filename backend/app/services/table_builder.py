from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.services.naming import dedupe_identifiers, sanitize_identifier

# Maps our inferred column role to a Postgres column type.
# NUMERIC (not INTEGER) avoids overflow surprises on large sums; TEXT has
# no length cap in Postgres, so we don't need to guess VARCHAR(n) sizes.
ROLE_TO_PG_TYPE = {
    "id": "NUMERIC",
    "numeric": "NUMERIC",
    "datetime": "TIMESTAMP",
    "categorical": "TEXT",
    "text": "TEXT",
}


def resolve_table_name(base_name: str, session: Session) -> str:
    """Sanitize a proposed table name and, if it collides with an existing
    dataset's table_name, suffix it (_2, _3, ...) until it's unique.
    """
    candidate = sanitize_identifier(base_name, fallback="dataset")
    existing = {
        row[0]
        for row in session.query(Dataset.table_name).all()
    }

    if candidate not in existing:
        return candidate

    suffix = 2
    while f"{candidate}_{suffix}" in existing:
        suffix += 1
    return f"{candidate}_{suffix}"


def build_column_definitions(profile: dict) -> tuple[list[str], dict[str, str]]:
    """From a profile's column list, produce sanitized+deduped column names
    and the SQL column definitions to use in CREATE TABLE.

    Returns (column_defs, original_to_sanitized_map).
    """
    original_names = [col["name"] for col in profile["columns"]]
    sanitized = [sanitize_identifier(n) for n in original_names]
    deduped = dedupe_identifiers(sanitized)

    name_map = dict(zip(original_names, deduped))

    column_defs = []
    for col, sql_name in zip(profile["columns"], deduped):
        pg_type = ROLE_TO_PG_TYPE.get(col["inferred_role"], "TEXT")
        column_defs.append(f'"{sql_name}" {pg_type}')

    return column_defs, name_map


def create_user_table(
    base_name: str,
    profile: dict,
    engine: Engine,
    session: Session,
) -> tuple[str, dict[str, str]]:
    """Create a table in user_data for this dataset.
    Returns (final_table_name, {original_column_name: sanitized_column_name}).
    """
    table_name = resolve_table_name(base_name, session)
    column_defs, name_map = build_column_definitions(profile)

    create_sql = (
        f'CREATE TABLE user_data."{table_name}" (\n    '
        + ",\n    ".join(column_defs)
        + "\n)"
    )

    with engine.begin() as conn:
        conn.execute(text(create_sql))

    return table_name, name_map
