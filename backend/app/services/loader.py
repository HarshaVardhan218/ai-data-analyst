from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine


def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    name_map: dict[str, str],
    profile: dict,
    engine: Engine,
) -> int:
    """Insert df's rows into user_data.<table_name>.
    Returns the number of rows loaded.
    """
    data = df.rename(columns=name_map).copy()

    # Convert datetime-role columns so they match the TIMESTAMP column type.
    for col in profile["columns"]:
        if col["inferred_role"] == "datetime":
            sql_name = name_map[col["name"]]
            data[sql_name] = pd.to_datetime(
                data[sql_name], errors="coerce", format="mixed"
            )

    data.to_sql(
        name=table_name,
        con=engine,
        schema="user_data",
        if_exists="append",
        index=False,
        chunksize=5000,
        method="multi",
    )
    return len(data)
