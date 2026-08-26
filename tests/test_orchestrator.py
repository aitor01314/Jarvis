from core.application.orchestrator import Orchestrator


class FakeDaemon:
    async def open_app(self, app: str) -> dict:
        return {"ok": True, "accion": "abrir", "aplicacion": app}

    async def close_app(self, app: str) -> dict:
        return {"ok": True, "accion": "cerrar", "aplicacion": app, "procesos": 1}

    async def metrics(self) -> dict:
        return {
            "cpu_porcentaje": 12.0,
            "cpu_nucleos": 8,
            "ram_porcentaje": 40.0,
            "ram_usada_gb": 6.4,
            "ram_total_gb": 16.0,
            "disco_porcentaje": 55.0,
            "procesos": 200,
            "gpu": [],
        }

    async def processes(self, limit: int = 15) -> list:
        return [{"pid": 1, "nombre": "chrome.exe", "ram_mb": 500.0}]


def _orchestrator() -> Orchestrator:
    return Orchestrator(chain=None, daemon=FakeDaemon(), system_prompt="test")  # type: ignore[arg-type]


async def test_abrir_app() -> None:
    result = await _orchestrator().try_system_action("Jarvis, abre el bloc de notas")
    assert result is not None
    assert "bloc de notas" in result.reply


async def test_cerrar_app() -> None:
    result = await _orchestrator().try_system_action("cierra la calculadora")
    assert result is not None
    assert "cerrado" in result.reply


async def test_metricas() -> None:
    result = await _orchestrator().try_system_action("¿cuánta RAM estoy usando?")
    assert result is not None
    assert "RAM 6.4/16.0 GB" in result.reply


async def test_conversacion_no_es_accion() -> None:
    result = await _orchestrator().try_system_action("hola, ¿qué tal estás?")
    assert result is None
