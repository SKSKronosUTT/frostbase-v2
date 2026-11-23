"""Asistente IA (A1): contrato HTTP, lock, cuota, roles y contexto."""

import json
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, text

import app.services.ai_agent as ai_agent_pkg
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.ai import AiAudit, AiConversation, AiUsage
from app.models.alert import Alert
from app.models.reading import Reading
from app.services.ai_agent.chat import chat as chat_function
from app.services.ai_agent.client import WebImClient
from app.services.ai_agent.context import build_context
from app.services.ai_agent.status import get_status as get_status_function
from app.services.ai_agent.status import reset_status_cache
from app.utils.time import utcnow

GATE_LOCK_KEY = 7712028


class FakeAgent:
    """Servidor HTTP falso con el contrato confirmado de WebIM."""

    def __init__(self, reply: str = "Hola desde el agente", respond: bool = True):
        self.reply = reply
        self.respond = respond
        self.sessions: dict[str, list[dict]] = {}
        self.status_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/status":
            self.status_calls += 1
            return httpx.Response(
                200, json={"boot_id": "boot-1", "wifi_connected": True}
            )
        if path == "/api/webim/sessions" and request.method == "POST":
            session = uuid.uuid4().hex
            self.sessions[session] = []
            return httpx.Response(201, json={"session": session})
        if path.endswith("/messages") and "/api/webim/sessions/" in path:
            session = path.split("/")[4]
            return httpx.Response(
                200, json={"messages": self.sessions.get(session, [])}
            )
        if path == "/api/webim/send" and request.method == "POST":
            payload = json.loads(request.content)
            session = payload["session"]
            messages = self.sessions[session]
            messages.append(
                {"seq": len(messages) + 1, "role": "user", "text": payload["text"]}
            )
            if self.respond:
                messages.append(
                    {
                        "seq": len(messages) + 1,
                        "role": "assistant",
                        "text": self.reply,
                    }
                )
            return httpx.Response(202, json={"run_id": 1, "state": "queued"})
        if request.method == "DELETE":
            session = path.rsplit("/", 1)[-1]
            self.sessions.pop(session, None)
            return httpx.Response(200)
        return httpx.Response(404)


def install_agent(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def factory() -> WebImClient:
        return WebImClient("http://127.0.0.1", transport=transport)

    monkeypatch.setitem(chat_function.__globals__, "build_client", factory)
    monkeypatch.setitem(get_status_function.__globals__, "build_client", factory)
    monkeypatch.setattr(ai_agent_pkg, "build_client", factory)


@pytest.fixture
def ai_settings(monkeypatch):
    monkeypatch.setattr(settings, "ai_agent_enabled", True)
    monkeypatch.setattr(settings, "ai_agent_url", "http://127.0.0.1")
    monkeypatch.setattr(settings, "ai_agent_timeout_seconds", 3)
    monkeypatch.setattr(settings, "ai_agent_poll_interval_seconds", 0.02)
    monkeypatch.setattr(settings, "ai_agent_daily_limit", 100)
    monkeypatch.setattr(settings, "ai_agent_max_message_chars", 500)
    reset_status_cache()
    yield
    reset_status_cache()


def test_chat_creates_conversation_and_replies(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    agent = FakeAgent()
    install_agent(monkeypatch, agent.handler)
    assert login().status_code == 200

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hola"},
        headers=csrf_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hola desde el agente"
    assert body["source"] == "agent"
    conversation_id = body["conversation_id"]

    with SessionLocal() as db:
        conversation = db.get(AiConversation, uuid.UUID(conversation_id))
        assert conversation is not None
        assert conversation.agent_session
        assert conversation.last_seq == 2
        usage = db.scalar(select(AiUsage))
        assert usage is not None and usage.count == 1

    # Segundo mensaje en la misma conversación
    second = client.post(
        "/api/v1/ai/chat",
        json={"message": "Otra", "conversation_id": conversation_id},
        headers=csrf_headers(),
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id

    with SessionLocal() as db:
        assert db.scalar(select(AiUsage)).count == 2
        assert db.scalar(select(AiConversation)).last_seq == 4


def test_chat_requires_csrf(client, login, ai_settings, monkeypatch):
    install_agent(monkeypatch, FakeAgent().handler)
    assert login().status_code == 200
    response = client.post("/api/v1/ai/chat", json={"message": "Hola"})
    assert response.status_code == 403


def test_chat_requires_admin(
    client, create_driver, ai_settings, monkeypatch, csrf_headers
):
    install_agent(monkeypatch, FakeAgent().handler)
    _, email, password = create_driver(email="ia.driver@frostbase.local")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": password},
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hola"},
        headers=csrf_headers(),
    )
    assert response.status_code == 403


def test_chat_disabled_returns_404(client, login, csrf_headers, monkeypatch):
    monkeypatch.setattr(settings, "ai_agent_enabled", False)
    assert login().status_code == 200
    response = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    assert response.status_code == 404


def test_quota_is_enforced(client, login, csrf_headers, ai_settings, monkeypatch):
    monkeypatch.setattr(settings, "ai_agent_daily_limit", 1)
    install_agent(monkeypatch, FakeAgent().handler)
    assert login().status_code == 200

    first = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/ai/chat", json={"message": "Otra"}, headers=csrf_headers()
    )
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "3600"

    with SessionLocal() as db:
        assert db.scalar(select(AiUsage)).count == 1


def test_gate_rejects_concurrent_request(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    install_agent(monkeypatch, FakeAgent().handler)
    assert login().status_code == 200

    connection = engine.connect()
    try:
        connection.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": GATE_LOCK_KEY}
        )
        response = client.post(
            "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
        )
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "3"
    finally:
        connection.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": GATE_LOCK_KEY}
        )
        connection.close()


def test_agent_timeout_returns_504(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    monkeypatch.setattr(settings, "ai_agent_timeout_seconds", 0.3)
    install_agent(monkeypatch, FakeAgent(respond=False).handler)
    assert login().status_code == 200
    response = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    assert response.status_code == 504


def test_agent_unreachable_returns_503(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    install_agent(monkeypatch, handler)
    assert login().status_code == 200
    response = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    assert response.status_code == 503

    status_response = client.get("/api/v1/ai/status")
    assert status_response.status_code == 200
    assert status_response.json()["online"] is False


def test_status_is_cached(client, login, ai_settings, monkeypatch):
    agent = FakeAgent()
    install_agent(monkeypatch, agent.handler)
    assert login().status_code == 200

    first = client.get("/api/v1/ai/status")
    assert first.status_code == 200
    assert first.json()["online"] is True
    assert first.json()["boot_id"] == "boot-1"
    assert agent.status_calls == 1

    second = client.get("/api/v1/ai/status")
    assert second.status_code == 200
    assert agent.status_calls == 1


def test_close_conversation(client, login, csrf_headers, ai_settings, monkeypatch):
    install_agent(monkeypatch, FakeAgent().handler)
    assert login().status_code == 200
    created = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    conversation_id = created.json()["conversation_id"]

    closed = client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=csrf_headers()
    )
    assert closed.status_code == 200
    assert closed.json()["closed"] is True

    again = client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=csrf_headers()
    )
    assert again.status_code == 404


def test_context_contains_operational_data_without_pii(create_truck, create_device):
    truck_id = create_truck(plate="CTX-001")
    device_pk, _, _ = create_device(truck_id, device_id="ESP32-CTX-001")
    with SessionLocal() as db:
        now = utcnow()
        db.add(
            Reading(
                device_id=device_pk,
                truck_id=truck_id,
                temperature=9.0,
                humidity=50.0,
                received_at=now,
                reading_timestamp=now,
            )
        )
        db.add(
            Alert(
                truck_id=truck_id,
                alert_type="temperatura",
                status="activa",
                message="Temperatura alta",
                value=9.0,
            )
        )
        db.commit()
        context = build_context(db)

    assert "CTX-001" in context
    assert "fuera de rango" in context
    assert "1 alertas activas" in context
    assert "America/Tijuana" in context
    assert "@" not in context
    assert "Temperatura alta" not in context


def test_quick_list_and_deterministic_answers(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    def boom():
        raise AssertionError("Las respuestas rápidas no deben llamar al agente")

    monkeypatch.setattr(ai_agent_pkg, "build_client", boom)
    assert login().status_code == 200

    listed = client.get("/api/v1/ai/quick")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert {
        "fleet-summary",
        "active-alerts",
        "active-trips",
        "critical-containers",
        "today-routes",
    } <= ids

    response = client.post("/api/v1/ai/quick/fleet-summary", headers=csrf_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "system"
    assert "Flota:" in body["text"]
    assert "Datos del sistema" in body["text"]

    unknown = client.post("/api/v1/ai/quick/no-existe", headers=csrf_headers())
    assert unknown.status_code == 404

    with SessionLocal() as db:
        assert db.scalar(select(AiUsage)) is None


def test_quick_requires_admin_and_csrf(client, create_driver, csrf_headers):
    # Sin sesión → 401 (el middleware/dependencia de rol lo rechaza).
    assert client.post("/api/v1/ai/quick/fleet-summary").status_code in (401, 403)

    _, email, password = create_driver(email="quick.driver@frostbase.local")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": password},
        ).status_code
        == 200
    )
    denied = client.post("/api/v1/ai/quick/fleet-summary", headers=csrf_headers())
    assert denied.status_code == 403


def test_quick_requires_csrf(client, login):
    assert login().status_code == 200
    response = client.post("/api/v1/ai/quick/fleet-summary")
    assert response.status_code == 403


def test_chat_writes_audit_without_content(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    install_agent(monkeypatch, FakeAgent().handler)
    assert login().status_code == 200
    response = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        row = db.scalar(select(AiAudit))
        assert row is not None
        assert row.action == "chat"
        assert row.status == "ok"
        assert row.http_status == 200
        assert row.latency_ms and row.latency_ms >= 0
        assert not hasattr(row, "message")


def test_busy_request_is_audited_as_error(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    install_agent(monkeypatch, FakeAgent().handler)
    assert login().status_code == 200

    connection = engine.connect()
    try:
        connection.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": GATE_LOCK_KEY}
        )
        response = client.post(
            "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
        )
        assert response.status_code == 429
    finally:
        connection.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": GATE_LOCK_KEY}
        )
        connection.close()

    with SessionLocal() as db:
        row = db.scalar(select(AiAudit).where(AiAudit.action == "chat"))
        assert row.status == "error"
        assert row.http_status == 429
        assert row.detail == "busy"


def test_quick_and_metrics_are_audited(client, login, csrf_headers, ai_settings):
    assert login().status_code == 200
    assert (
        client.post(
            "/api/v1/ai/quick/fleet-summary", headers=csrf_headers()
        ).status_code
        == 200
    )
    assert (
        client.post("/api/v1/ai/quick/no-existe", headers=csrf_headers()).status_code
        == 404
    )

    response = client.get("/api/v1/ai/metrics", params={"days": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["requests"] == 2
    assert body["errors"] == 1
    assert body["by_action"]["quick"] == 2

    with SessionLocal() as db:
        assert db.query(AiAudit).count() == 2


def test_metrics_requires_admin(client, create_driver, csrf_headers):
    _, email, password = create_driver(email="metrics.driver@frostbase.local")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": password},
        ).status_code
        == 200
    )
    response = client.get("/api/v1/ai/metrics")
    assert response.status_code == 403


def test_session_ttl_rotates_agent_session(
    client, login, csrf_headers, ai_settings, monkeypatch
):
    monkeypatch.setattr(settings, "ai_agent_session_ttl_hours", 1)
    agent = FakeAgent()
    install_agent(monkeypatch, agent.handler)
    assert login().status_code == 200

    first = client.post(
        "/api/v1/ai/chat", json={"message": "Hola"}, headers=csrf_headers()
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    with SessionLocal() as db:
        conversation = db.get(AiConversation, uuid.UUID(conversation_id))
        old_session = conversation.agent_session
        conversation.last_used_at = utcnow() - timedelta(hours=2)
        db.add(conversation)
        db.commit()

    second = client.post(
        "/api/v1/ai/chat",
        json={"message": "Otra", "conversation_id": conversation_id},
        headers=csrf_headers(),
    )
    assert second.status_code == 200

    with SessionLocal() as db:
        conversation = db.get(AiConversation, uuid.UUID(conversation_id))
        assert conversation.agent_session != old_session
        assert conversation.last_seq == 2
    assert old_session not in agent.sessions
    assert len(agent.sessions) == 1
