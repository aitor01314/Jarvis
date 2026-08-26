"""Modelos de dominio puros de JARVIS.

Esta capa no depende de ningún framework ni proveedor concreto.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    role: Role
    content: str


class Brain(StrEnum):
    CONVERSACIONAL = "conversacional"
    PROGRAMACION = "programacion"
    MATEMATICO = "matematico"
    CREATIVO = "creativo"
    VISUAL = "visual"
    VOZ = "voz"
    AUTONOMO = "autonomo"


class CompletionRequest(BaseModel):
    messages: list[Message]
    brain: Brain = Brain.CONVERSACIONAL
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False


class CompletionResponse(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class ModelSpec(BaseModel):
    """Un modelo concreto ofrecido por un proveedor."""

    provider: str
    model_id: str
    supports_vision: bool = False
    supports_tools: bool = False
    context_window: int = 8192


class ProviderStatus(BaseModel):
    name: str
    available: bool
    rate_limited_until: float = 0.0  # epoch; 0 = sin límite activo
    consecutive_errors: int = 0


class Event(BaseModel):
    """Evento del bus interno de JARVIS."""

    type: str
    schema_version: int = 1
    payload: dict = Field(default_factory=dict)
