"""Daemon de Sistema de JARVIS.

Proceso independiente con los privilegios del SO. El core le habla
por HTTP; en multi-dispositivo, cada máquina ejecuta su propio daemon.

Arranque:
    uvicorn system_daemon.api:app --port 7801
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from system_daemon import actions

app = FastAPI(title="JARVIS System Daemon", version="0.1.0")


class OpenIn(BaseModel):
    app: str


class CloseIn(BaseModel):
    app: str


class ClipboardIn(BaseModel):
    text: str


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict:
    return actions.metrics()


@app.get("/processes")
async def processes(limit: int = 15) -> list[dict]:
    return actions.list_processes(limit)


@app.post("/apps/open")
async def apps_open(body: OpenIn) -> dict:
    try:
        return actions.open_app(body.app)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/apps/close")
async def apps_close(body: CloseIn) -> dict:
    return actions.close_app(body.app)


@app.get("/clipboard")
async def clipboard_get() -> dict:
    return actions.clipboard_get()


@app.post("/clipboard")
async def clipboard_set(body: ClipboardIn) -> dict:
    return actions.clipboard_set(body.text)
