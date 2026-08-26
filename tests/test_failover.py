import pytest

from core.application.failover import FailoverChain
from core.domain.contracts import ProviderError, RateLimitedError
from core.domain.models import Brain, CompletionRequest, CompletionResponse, Message, Role
from core.infrastructure.providers import registry


class FakeProvider:
    def __init__(self, name: str, fail_with: Exception | None = None) -> None:
        self.name = name
        self.fail_with = fail_with
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    async def complete(self, request: CompletionRequest, model_id: str) -> CompletionResponse:
        self.calls += 1
        if self.fail_with:
            raise self.fail_with
        return CompletionResponse(content="ok", model=model_id, provider=self.name)


def _request() -> CompletionRequest:
    return CompletionRequest(
        messages=[Message(role=Role.USER, content="hola")], brain=Brain.CONVERSACIONAL
    )


@pytest.fixture(autouse=True)
def fake_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "DEFAULT_MODELS", {})
    from core.application import failover

    monkeypatch.setattr(failover, "model_for", lambda name, brain: "modelo-fake")


async def test_failover_a_siguiente_proveedor() -> None:
    limitado = FakeProvider("groq", RateLimitedError("groq", retry_after=60))
    respaldo = FakeProvider("openrouter")
    chain = FailoverChain([limitado, respaldo])  # type: ignore[list-item]

    response = await chain.complete(_request())
    assert response.provider == "openrouter"

    # groq queda en cooldown: la siguiente llamada va directa al respaldo.
    await chain.complete(_request())
    assert limitado.calls == 1
    assert respaldo.calls == 2


async def test_todos_agotados() -> None:
    chain = FailoverChain([FakeProvider("groq", RateLimitedError("groq"))])  # type: ignore[list-item]
    with pytest.raises(ProviderError):
        await chain.complete(_request())
