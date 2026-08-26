"""Contratos (puertos) del núcleo de JARVIS.

Todo lo concreto (Groq, Gemini, OpenRouter, Redis, Qdrant...) implementa
estas interfaces. El núcleo solo conoce estos contratos.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from core.domain.models import CompletionRequest, CompletionResponse, Event


class RateLimitedError(Exception):
    """El proveedor devolvió 429 (límite alcanzado)."""

    def __init__(self, provider: str, retry_after: float = 60.0) -> None:
        super().__init__(f"Rate limit en {provider}, reintento en {retry_after}s")
        self.provider = provider
        self.retry_after = retry_after


class ProviderError(Exception):
    """Fallo genérico de un proveedor (red, 5xx, auth...)."""


class LLMProvider(Protocol):
    """Contrato estable de proveedor de modelos de lenguaje."""

    name: str

    def is_configured(self) -> bool: ...

    async def complete(self, request: CompletionRequest, model_id: str) -> CompletionResponse: ...

    async def stream(self, request: CompletionRequest, model_id: str) -> AsyncIterator[str]: ...


class EventBus(Protocol):
    async def publish(self, event: Event) -> None: ...

    async def subscribe(self, pattern: str) -> AsyncIterator[Event]: ...
