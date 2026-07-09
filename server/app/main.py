"""FastAPI 엔트리 — uvicorn app.main:app --reload --host 0.0.0.0"""
from __future__ import annotations

from fastapi import FastAPI

from .api.events import router as events_router
from .db import init_db

app = FastAPI(title="Cough-ID API", version="0.1.0")
app.include_router(events_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
