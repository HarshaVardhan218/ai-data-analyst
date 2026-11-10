from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database.engine import app_engine, analyst_engine
from app.api.agent import router as agent_router
from app.api.datasets import router as datasets_router

app = FastAPI(title="AI Data Analyst Agent")
app.include_router(datasets_router)
app.include_router(agent_router)

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


# The dashboard: plain HTML/JS in the repo-root frontend/ folder, served at "/".
# Mounted last so the API routes above (and /docs) take priority.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
