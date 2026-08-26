"""API HTTP y WebSocket de JARVIS (esqueleto del MVP).

Arranque:
    uvicorn core.interfaces.api:app --reload
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.application.failover import FailoverChain
from core.application.router import route
from core.domain.contracts import ProviderError
from core.domain.models import Brain, CompletionRequest, Message, Role
from core.infrastructure.providers.registry import build_providers

load_dotenv()
logging.basicConfig(level=os.getenv("JARVIS_LOG_LEVEL", "INFO"))

app = FastAPI(title="JARVIS Core", version="0.1.0")

SYSTEM_PROMPT = (
    "Eres JARVIS, el asistente personal de Aitor, inspirado en el de Iron Man. "
    "Respondes SIEMPRE en español, con un tono profesional, cercano y ligeramente "
    "británico. Eres conciso y directo."
)

_chain: FailoverChain | None = None


def get_chain() -> FailoverChain:
    global _chain
    if _chain is None:
        _chain = FailoverChain(build_providers())
    return _chain


class ChatIn(BaseModel):
    message: str
    brain: Brain | None = None  # si no se indica, decide el router


class ChatOut(BaseModel):
    reply: str
    brain: Brain
    model: str
    provider: str
    latency_ms: int


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "proveedores": get_chain().status()}


@app.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn) -> ChatOut:
    brain = body.brain or route(body.message)
    request = CompletionRequest(
        messages=[
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=body.message),
        ],
        brain=brain,
    )
    response = await get_chain().complete(request)
    return ChatOut(
        reply=response.content,
        brain=brain,
        model=response.model,
        provider=response.provider,
        latency_ms=response.latency_ms,
    )


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Chat en streaming: envía texto, recibe deltas y un evento final."""
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            brain = route(text)
            await websocket.send_json({"type": "router.decision", "brain": brain.value})
            request = CompletionRequest(
                messages=[
                    Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
                    Message(role=Role.USER, content=text),
                ],
                brain=brain,
                stream=True,
            )
            try:
                async for delta in get_chain().stream(request):
                    await websocket.send_json({"type": "delta", "content": delta})
                await websocket.send_json({"type": "done"})
            except ProviderError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
