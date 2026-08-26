"""Cliente HTTP hacia el Daemon de Sistema.

El core no toca el SO: delega en el daemon (proceso independiente,
uno por dispositivo). Si el daemon no está en marcha, las acciones
de sistema devuelven un error claro en español.
"""

from __future__ import annotations

import os

import httpx


class DaemonNotAvailableError(Exception):
    pass


class DaemonClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("DAEMON_URL", "http://localhost:7801")).rstrip("/")
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        try:
            response = await self._client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise DaemonNotAvailableError(
                "No puedo hablar con el Daemon de Sistema. Arráncalo con: "
                "uvicorn system_daemon.api:app --port 7801"
            ) from exc

    async def open_app(self, app: str) -> dict:
        return await self._request("POST", "/apps/open", json={"app": app})  # type: ignore[return-value]

    async def close_app(self, app: str) -> dict:
        return await self._request("POST", "/apps/close", json={"app": app})  # type: ignore[return-value]

    async def metrics(self) -> dict:
        return await self._request("GET", "/metrics")  # type: ignore[return-value]

    async def processes(self, limit: int = 15) -> list:
        return await self._request("GET", f"/processes?limit={limit}")  # type: ignore[return-value]
