"""Registro de proveedores gratuitos, en orden de prioridad.

El orden importa: es la cadena de failover. Cuando un proveedor agota
su límite por minuto (HTTP 429) o falla, se pasa al siguiente. El
penúltimo escalón es OpenRouter (modelos :free) y el último Ollama
(local, sin límites).
"""

from __future__ import annotations

import os

from core.domain.models import Brain
from core.infrastructure.providers.openai_compat import OpenAICompatProvider


def build_providers() -> list[OpenAICompatProvider]:
    """Construye la cadena de failover con los proveedores configurados."""
    candidates = [
        OpenAICompatProvider(
            "groq", "https://api.groq.com/openai/v1", os.getenv("GROQ_API_KEY")
        ),
        OpenAICompatProvider(
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            os.getenv("GEMINI_API_KEY"),
        ),
        OpenAICompatProvider(
            "cerebras", "https://api.cerebras.ai/v1", os.getenv("CEREBRAS_API_KEY")
        ),
        OpenAICompatProvider(
            "mistral", "https://api.mistral.ai/v1", os.getenv("MISTRAL_API_KEY")
        ),
        OpenAICompatProvider(
            "github", "https://models.github.ai/inference", os.getenv("GITHUB_MODELS_TOKEN")
        ),
        OpenAICompatProvider(
            "openrouter", "https://openrouter.ai/api/v1", os.getenv("OPENROUTER_API_KEY")
        ),
        OpenAICompatProvider(
            "ollama",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1",
            None,
        ),
    ]
    return [p for p in candidates if p.is_configured()]


# Modelo recomendado por (proveedor, cerebro). Todos gratuitos.
DEFAULT_MODELS: dict[str, dict[Brain, str]] = {
    "groq": {
        Brain.CONVERSACIONAL: "llama-3.3-70b-versatile",
        Brain.PROGRAMACION: "llama-3.3-70b-versatile",
        Brain.MATEMATICO: "deepseek-r1-distill-llama-70b",
        Brain.CREATIVO: "llama-3.3-70b-versatile",
    },
    "gemini": {
        Brain.CONVERSACIONAL: "gemini-2.0-flash",
        Brain.PROGRAMACION: "gemini-2.0-flash",
        Brain.MATEMATICO: "gemini-2.0-flash-thinking-exp",
        Brain.CREATIVO: "gemini-2.0-flash",
        Brain.VISUAL: "gemini-2.0-flash",
    },
    "cerebras": {
        Brain.CONVERSACIONAL: "llama-3.3-70b",
        Brain.PROGRAMACION: "llama-3.3-70b",
    },
    "mistral": {
        Brain.CONVERSACIONAL: "mistral-small-latest",
        Brain.PROGRAMACION: "codestral-latest",
        Brain.CREATIVO: "mistral-small-latest",
    },
    "github": {
        Brain.CONVERSACIONAL: "openai/gpt-4o-mini",
        Brain.PROGRAMACION: "openai/gpt-4o",
    },
    "openrouter": {
        Brain.CONVERSACIONAL: "meta-llama/llama-3.3-70b-instruct:free",
        Brain.PROGRAMACION: "deepseek/deepseek-chat-v3-0324:free",
        Brain.MATEMATICO: "deepseek/deepseek-r1:free",
        Brain.CREATIVO: "meta-llama/llama-3.3-70b-instruct:free",
        Brain.VISUAL: "google/gemini-2.0-flash-exp:free",
    },
    "ollama": {
        Brain.CONVERSACIONAL: "llama3.1",
        Brain.PROGRAMACION: "qwen2.5-coder",
    },
}


def model_for(provider_name: str, brain: Brain) -> str | None:
    """Modelo gratuito recomendado para un cerebro en un proveedor dado."""
    models = DEFAULT_MODELS.get(provider_name, {})
    return models.get(brain) or models.get(Brain.CONVERSACIONAL)
