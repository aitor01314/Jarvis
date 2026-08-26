"""Router Inteligente v1.

Etapa 1 (MVP): reglas deterministas por palabras clave para elegir
cerebro. Etapa 2 (Beta): clasificador con un modelo pequeño gratuito
(Groq llama-3.1-8b-instant) por delante de las reglas.
"""

from __future__ import annotations

import re

from core.domain.models import Brain

_RULES: list[tuple[Brain, re.Pattern[str]]] = [
    (
        Brain.PROGRAMACION,
        re.compile(
            r"\b(código|programa|función|bug|error|refactoriza|python|script|"
            r"api|clase|compila|depura|desarrolla)\b",
            re.IGNORECASE,
        ),
    ),
    (
        Brain.MATEMATICO,
        re.compile(
            r"\b(calcula|ecuación|deriva|integra|probabilidad|estadística|"
            r"porcentaje|optimiza|álgebra|matriz)\b",
            re.IGNORECASE,
        ),
    ),
    (
        Brain.CREATIVO,
        re.compile(
            r"\b(historia|guion|guión|poema|marketing|eslogan|idea|copy|"
            r"creativo|relato|título)\b",
            re.IGNORECASE,
        ),
    ),
    (
        Brain.VISUAL,
        re.compile(r"\b(imagen|foto|captura|diagrama|ocr|pantalla|dibuja)\b", re.IGNORECASE),
    ),
]


def route(text: str) -> Brain:
    """Elige el cerebro adecuado para una entrada del usuario."""
    for brain, pattern in _RULES:
        if pattern.search(text):
            return brain
    return Brain.CONVERSACIONAL
