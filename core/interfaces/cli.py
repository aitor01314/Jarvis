"""Chat con JARVIS desde la terminal (para probar sin UI).

Uso:
    python -m core.interfaces.cli
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from core.application.failover import FailoverChain
from core.application.router import route
from core.domain.contracts import ProviderError
from core.domain.models import CompletionRequest, Message, Role
from core.infrastructure.providers.registry import build_providers
from core.interfaces.api import SYSTEM_PROMPT


async def main() -> None:
    load_dotenv()
    chain = FailoverChain(build_providers())
    history: list[Message] = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]
    print("JARVIS listo. Escribe 'salir' para terminar.\n")
    while True:
        try:
            text = input("Tú > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() in {"salir", "exit"}:
            break
        brain = route(text)
        history.append(Message(role=Role.USER, content=text))
        request = CompletionRequest(messages=history, brain=brain, stream=True)
        print(f"JARVIS ({brain.value}) > ", end="", flush=True)
        chunks: list[str] = []
        try:
            async for delta in chain.stream(request):
                chunks.append(delta)
                print(delta, end="", flush=True)
        except ProviderError as exc:
            print(f"\n[error] {exc}")
            history.pop()
            continue
        print("\n")
        history.append(Message(role=Role.ASSISTANT, content="".join(chunks)))


if __name__ == "__main__":
    asyncio.run(main())
