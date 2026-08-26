"""Orquestador v1.

Decide si una entrada es una acción de sistema (la ejecuta vía daemon,
sin gastar tokens) o una conversación (la enruta a un cerebro LLM).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.application.failover import FailoverChain
from core.application.router import route
from core.domain.models import Brain, CompletionRequest, Message, Role
from core.infrastructure.daemon_client import DaemonClient, DaemonNotAvailableError

_OPEN = re.compile(
    r"^\s*(?:jarvis[,]?\s+)?(?:abre|abrir|lanza|ejecuta|inicia)\s+(?:el\s+|la\s+)?(.{2,60}?)\s*$",
    re.IGNORECASE,
)
_CLOSE = re.compile(
    r"^\s*(?:jarvis[,]?\s+)?(?:cierra|cerrar|mata|termina)\s+(?:el\s+|la\s+)?(.{2,60}?)\s*$",
    re.IGNORECASE,
)
_METRICS = re.compile(
    r"\b(cu[aá]nta?\s+(ram|cpu|memoria)|estado del (sistema|pc|ordenador)|m[eé]tricas)\b",
    re.IGNORECASE,
)
_PROCESSES = re.compile(r"\b(procesos (abiertos|activos)|qu[eé] procesos)\b", re.IGNORECASE)


@dataclass
class OrchestratorResult:
    reply: str
    brain: Brain | None = None
    model: str = "sistema"
    provider: str = "daemon"
    latency_ms: int = 0


class Orchestrator:
    def __init__(self, chain: FailoverChain, daemon: DaemonClient, system_prompt: str) -> None:
        self._chain = chain
        self._daemon = daemon
        self._system_prompt = system_prompt

    async def handle(self, text: str, history: list[Message] | None = None) -> OrchestratorResult:
        system = await self.try_system_action(text)
        if system is not None:
            return system

        brain = route(text)
        messages = [Message(role=Role.SYSTEM, content=self._system_prompt)]
        messages += history or []
        messages.append(Message(role=Role.USER, content=text))
        response = await self._chain.complete(CompletionRequest(messages=messages, brain=brain))
        return OrchestratorResult(
            reply=response.content,
            brain=brain,
            model=response.model,
            provider=response.provider,
            latency_ms=response.latency_ms,
        )

    async def try_system_action(self, text: str) -> OrchestratorResult | None:
        try:
            if match := _OPEN.match(text):
                result = await self._daemon.open_app(match.group(1))
                return OrchestratorResult(reply=f"Abriendo {result['aplicacion']}, señor.")
            if match := _CLOSE.match(text):
                result = await self._daemon.close_app(match.group(1))
                app = result["aplicacion"]
                if result["ok"]:
                    return OrchestratorResult(
                        reply=f"He cerrado {app} ({result['procesos']} proceso(s))."
                    )
                return OrchestratorResult(reply=f"No encuentro {app} en ejecución.")
            if _METRICS.search(text):
                m = await self._daemon.metrics()
                gpu = ", ".join(
                    f"{g['nombre']} al {g['uso_porcentaje']}%" for g in m.get("gpu", [])
                ) or "sin GPU dedicada detectada"
                return OrchestratorResult(
                    reply=(
                        f"CPU al {m['cpu_porcentaje']}% ({m['cpu_nucleos']} núcleos) · "
                        f"RAM {m['ram_usada_gb']}/{m['ram_total_gb']} GB "
                        f"({m['ram_porcentaje']}%) · disco al {m['disco_porcentaje']}% · "
                        f"{m['procesos']} procesos · GPU: {gpu}."
                    )
                )
            if _PROCESSES.search(text):
                procs = await self._daemon.processes(limit=10)
                listado = "\n".join(
                    f"- {p['nombre']} (PID {p['pid']}, {p['ram_mb']} MB)" for p in procs
                )
                return OrchestratorResult(reply=f"Los 10 procesos que más RAM consumen:\n{listado}")
        except DaemonNotAvailableError as exc:
            return OrchestratorResult(reply=str(exc))
        return None
