"""Cliente HTTP del agente ESP-Claw (contrato confirmado en A0)."""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, settings


class AgentError(Exception):
    """Error base del agente."""


class AgentDisabledError(AgentError):
    pass


class AgentConfigError(AgentError):
    pass


class AgentUnavailableError(AgentError):
    pass


class AgentTimeoutError(AgentError):
    pass


class AgentSessionNotFoundError(AgentError):
    """La sesión ya no existe en el agente (p. ej. tras reiniciar el ESP32)."""


class AgentProtocolError(AgentError):
    pass


class AgentCircuitOpenError(AgentError):
    """Cortacircuito abierto: no se llama al agente hasta que expire."""

    def __init__(self, message: str, *, retry_after: int = 30) -> None:
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))


class AgentBusyError(AgentError):
    pass


class AgentValidationError(AgentError):
    pass


@dataclass
class AgentStatus:
    online: bool
    latency_ms: float | None = None
    boot_id: str | None = None
    wifi_connected: bool | None = None


def _validate_agent_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise AgentConfigError("AI_AGENT_URL debe usar http o https")
    host = parsed.hostname or ""
    if not host:
        raise AgentConfigError("AI_AGENT_URL no incluye host")
    if host in {"localhost"} or host.endswith(".local"):
        return url.rstrip("/")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise AgentConfigError(
            "AI_AGENT_URL debe usar una IP privada o un nombre .local"
        ) from exc
    if not (address.is_private or address.is_loopback):
        raise AgentConfigError("AI_AGENT_URL apunta a una IP no privada")
    return url.rstrip("/")


class WebImClient:
    """Cliente del contrato «WebIM» de ESP-Claw.

    - ``POST /api/webim/sessions`` crea la conversación.
    - ``POST /api/webim/send`` encola el mensaje.
    - ``GET  /api/webim/sessions/{id}/messages`` devuelve el historial.
    - ``GET  /api/status`` comprueba salud del dispositivo.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        timeout: int = 90,
        connect_timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(
                min(30.0, float(timeout)),
                connect=connect_timeout,
                pool=connect_timeout,
            ),
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WebImClient:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise AgentUnavailableError(
                "No se pudo conectar con el agente; revise la red y la URL"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AgentTimeoutError(
                "El agente no respondió dentro del tiempo esperado"
            ) from exc
        if response.status_code == 404 and (
            "/api/webim/sessions/" in path or path == "/api/webim/send"
        ):
            raise AgentSessionNotFoundError("La conversación ya no existe en el agente")
        if response.status_code >= 400:
            raise AgentProtocolError(f"El agente respondió {response.status_code}")
        return response

    def status(self, timeout: float = 5.0) -> AgentStatus:
        started = time.perf_counter()
        try:
            response = self._client.get("/api/status", timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            return AgentStatus(
                online=bool(payload.get("wifi_connected", True)),
                latency_ms=(time.perf_counter() - started) * 1000,
                boot_id=payload.get("boot_id"),
                wifi_connected=payload.get("wifi_connected"),
            )
        except (httpx.HTTPError, ValueError):
            return AgentStatus(online=False)

    def create_session(self) -> str:
        response = self._request("POST", "/api/webim/sessions")
        payload = response.json()
        session = payload.get("session") or payload.get("id")
        if not session:
            raise AgentProtocolError("El agente no devolvió una sesión válida")
        return str(session)

    def messages(self, session: str) -> list[dict]:
        response = self._request(
            "GET",
            f"/api/webim/sessions/{session}/messages",
            params={"before": 0},
            timeout=10.0,
        )
        payload = response.json()
        items = payload.get("messages") or payload.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    def send_message(self, session: str, text: str, client_message_id: str) -> dict:
        response = self._request(
            "POST",
            "/api/webim/send",
            json={
                "session": session,
                "client_message_id": client_message_id,
                "text": text,
                "files": [],
            },
        )
        return response.json()

    def delete_session(self, session: str) -> None:
        try:
            self._client.delete(f"/api/webim/sessions/{session}", timeout=5.0)
        except httpx.HTTPError:
            # El cierre es best-effort: la conversación local se cierra igual.
            return


def build_client(config: Settings | None = None) -> WebImClient:
    config = config or settings
    if not config.ai_agent_enabled:
        raise AgentDisabledError("El asistente IA está deshabilitado")
    if not config.ai_agent_url.strip():
        raise AgentConfigError("AI_AGENT_URL no está configurada")
    return WebImClient(
        _validate_agent_url(config.ai_agent_url),
        token=config.ai_agent_token,
        timeout=config.ai_agent_timeout_seconds,
        connect_timeout=config.ai_agent_connect_timeout_seconds,
    )
