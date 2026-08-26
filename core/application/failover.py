"""Cadena de failover entre proveedores gratuitos.

Recorre los proveedores en orden de prioridad. Si uno devuelve 429
(límite por minuto agotado) se marca en cooldown hasta que su ventana
se recupere y se prueba el siguiente automáticamente — así JARVIS
nunca deja de responder aunque todo sea gratis.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

from core.domain.contracts import ProviderError, RateLimitedError
from core.domain.models import CompletionRequest, CompletionResponse
from core.infrastructure.providers.openai_compat import OpenAICompatProvider
from core.infrastructure.providers.registry import model_for

logger = logging.getLogger("jarvis.failover")

MAX_CONSECUTIVE_ERRORS = 3
ERROR_COOLDOWN_SECONDS = 120.0


class FailoverChain:
    def __init__(self, providers: list[OpenAICompatProvider]) -> None:
        if not providers:
            raise RuntimeError(
                "Ningún proveedor configurado. Copia .env.example a .env y "
                "añade al menos una clave (GROQ_API_KEY, GEMINI_API_KEY...) "
                "o arranca Ollama en local."
            )
        self._providers = providers
        self._cooldown_until: dict[str, float] = {}
        self._errors: dict[str, int] = {}

    def _usable(self) -> list[OpenAICompatProvider]:
        now = time.monotonic()
        return [p for p in self._providers if self._cooldown_until.get(p.name, 0.0) <= now]

    def _penalize(self, name: str, seconds: float) -> None:
        self._cooldown_until[name] = time.monotonic() + seconds

    def status(self) -> list[dict]:
        now = time.monotonic()
        return [
            {
                "proveedor": p.name,
                "disponible": self._cooldown_until.get(p.name, 0.0) <= now,
                "cooldown_restante_s": max(0.0, self._cooldown_until.get(p.name, 0.0) - now),
            }
            for p in self._providers
        ]

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        last_error: Exception | None = None
        for provider in self._usable():
            model_id = model_for(provider.name, request.brain)
            if not model_id:
                continue
            try:
                response = await provider.complete(request, model_id)
                self._errors[provider.name] = 0
                return response
            except RateLimitedError as exc:
                logger.warning("Límite agotado en %s; failover al siguiente", provider.name)
                self._penalize(provider.name, exc.retry_after)
                last_error = exc
            except ProviderError as exc:
                logger.warning("Error en %s: %s", provider.name, exc)
                self._errors[provider.name] = self._errors.get(provider.name, 0) + 1
                if self._errors[provider.name] >= MAX_CONSECUTIVE_ERRORS:
                    self._penalize(provider.name, ERROR_COOLDOWN_SECONDS)
                last_error = exc
        raise ProviderError(f"Todos los proveedores agotados o en error: {last_error}")

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        last_error: Exception | None = None
        for provider in self._usable():
            model_id = model_for(provider.name, request.brain)
            if not model_id:
                continue
            started = False
            try:
                async for delta in provider.stream(request, model_id):
                    started = True
                    yield delta
                self._errors[provider.name] = 0
                return
            except RateLimitedError as exc:
                self._penalize(provider.name, exc.retry_after)
                last_error = exc
            except ProviderError as exc:
                self._errors[provider.name] = self._errors.get(provider.name, 0) + 1
                if self._errors[provider.name] >= MAX_CONSECUTIVE_ERRORS:
                    self._penalize(provider.name, ERROR_COOLDOWN_SECONDS)
                last_error = exc
                if started:
                    # No se puede reintentar a mitad de un stream ya emitido.
                    raise
        raise ProviderError(f"Todos los proveedores agotados o en error: {last_error}")
