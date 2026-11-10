from fastapi import FastAPI
from sqlalchemy import text

from app.database.engine import app_engine, analyst_engine
from app.api.datasets import router as datasets_router

app = FastAPI(title="AI Data Analyst Agent")
app.include_router(datasets_router)

@app.get("/health")
def health_check():
    status = {"api": "ok"}

    try:
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["app_rw_db"] = "ok"
    except Exception as e:
        status["app_rw_db"] = f"error: {e}"

    try:
        with analyst_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["analyst_ro_db"] = "ok"
    except Exception as e:
        status["analyst_ro_db"] = f"error: {e}"

    return status
