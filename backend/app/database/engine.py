from sqlalchemy import create_engine

from app.config import settings

# Used by ingestion: can create tables, load data, write metadata.
app_engine = create_engine(settings.app_rw_url, pool_pre_ping=True)

# Used by the SQL agent: read-only at the database level, no matter what SQL it's given.
analyst_engine = create_engine(settings.analyst_ro_url, pool_pre_ping=True)
