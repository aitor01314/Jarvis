from core.application.router import route
from core.domain.models import Brain


def test_programacion() -> None:
    assert route("Jarvis, refactoriza esta función de Python") == Brain.PROGRAMACION


def test_matematico() -> None:
    assert route("calcula la probabilidad de sacar dos seises") == Brain.MATEMATICO


def test_creativo() -> None:
    assert route("escríbeme un guion para TikTok") == Brain.CREATIVO


def test_conversacional_por_defecto() -> None:
    assert route("hola, ¿qué tal?") == Brain.CONVERSACIONAL
