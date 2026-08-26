"""Adaptador genérico para APIs compatibles con OpenAI.

Groq, Gemini, Cerebras, Mistral, GitHub Models, OpenRouter y Ollama
exponen todos un endpoint /chat/completions compatible con OpenAI,
así que un único adaptador configurable cubre todos los proveedores
gratuitos. Añadir un proveedor nuevo = una entrada en providers.yaml.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from core.domain.contracts import ProviderError, RateLimitedError
from core.domain.models import CompletionRequest, CompletionResponse


class OpenAICompatProvider:
    def __init__(self, name: str, base_url: str, api_key: str | None) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=120.0)

    def is_configured(self) -> bool:
        # Ollama (local) no necesita clave.
        return bool(self.api_key) or self.name == "ollama"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, request: CompletionRequest, model_id: str, stream: bool) -> dict:
        return {
            "model": model_id,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": stream,
        }

    async def complete(self, request: CompletionRequest, model_id: str) -> CompletionResponse:
        start = time.monotonic()
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(request, model_id, stream=False),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: error de red: {exc}") from exc

        if response.status_code == 429:
            retry_after = float(response.headers.get("retry-after", 60))
            raise RateLimitedError(self.name, retry_after)
        if response.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        usage = data.get("usage") or {}
        return CompletionResponse(
            content=data["choices"][0]["message"]["content"] or "",
            model=model_id,
            provider=self.name,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    async def stream(self, request: CompletionRequest, model_id: str) -> AsyncIterator[str]:
        import json

        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(request, model_id, stream=True),
            ) as response:
                if response.status_code == 429:
                    retry_after = float(response.headers.get("retry-after", 60))
                    raise RateLimitedError(self.name, retry_after)
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ProviderError(f"{self.name}: HTTP {response.status_code}: {body[:300]!r}")
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    chunk = json.loads(line[len("data: ") :])
                    delta = chunk["choices"][0].get("delta", {}).get("content")
                    if delta:
                        yield delta
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: error de red: {exc}") from exc
