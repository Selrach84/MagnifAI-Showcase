"""Tests for the connectors layer."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.connectors.base import BaseConnector, ConnectorConfig, ConnectorResponse
from backend.connectors.gohighlevel import GoHighLevelConnector
from backend.connectors.n8n import N8nConnector
from backend.connectors.webhook import send_webhook, verify_signature
from backend.database import get_db
from backend.main import app
from backend.models.connector import Connector

# ── BaseConnector interface ──────────────────────────────────────────────────


def test_base_connector_cannot_be_instantiated():
    """BaseConnector is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseConnector()


def test_base_connector_requires_methods():
    """A subclass missing abstract methods cannot be instantiated."""

    class Incomplete(BaseConnector):
        connector_type = "test"

    with pytest.raises(TypeError):
        Incomplete()


# ── ConnectorConfig ──────────────────────────────────────────────────────────


def test_connector_config_defaults():
    """ConnectorConfig applies sensible defaults."""
    cfg = ConnectorConfig(name="test", type="webhook")
    assert cfg.enabled is True
    assert cfg.credentials == {}
    assert cfg.base_url == ""


def test_connector_config_validation():
    """ConnectorConfig rejects missing required fields."""
    with pytest.raises(Exception, match="Field required"):
        ConnectorConfig(type="webhook")  # missing name


# ── ConnectorResponse ────────────────────────────────────────────────────────


def test_connector_response_defaults():
    """ConnectorResponse defaults to empty values."""
    resp = ConnectorResponse(success=True)
    assert resp.error == ""
    assert resp.latency_ms == 0.0
    assert resp.data == {}


# ── N8nConnector ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_n8n_test_connection_success():
    """N8nConnector.test_connection returns True on 200."""
    connector = N8nConnector(base_url="http://n8n.local", api_key="k1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("backend.connectors.n8n.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        assert await connector.test_connection() is True


@pytest.mark.asyncio
async def test_n8n_test_connection_failure():
    """N8nConnector.test_connection returns False on non-200."""
    connector = N8nConnector(base_url="http://n8n.local", api_key="k1")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("backend.connectors.n8n.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        assert await connector.test_connection() is False


@pytest.mark.asyncio
async def test_n8n_send_data_missing_workflow_id():
    """N8nConnector.send_data fails when workflow_id is missing."""
    connector = N8nConnector(base_url="http://n8n.local", api_key="k1")
    resp = await connector.send_data({"foo": "bar"})
    assert resp.success is False
    assert "workflow_id" in resp.error


@pytest.mark.asyncio
async def test_n8n_send_data_success():
    """N8nConnector.send_data posts to the workflow execute endpoint."""
    connector = N8nConnector(base_url="http://n8n.local", api_key="k1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"executionId": "123"}

    with patch("backend.connectors.n8n.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        resp = await connector.send_data({"workflow_id": "wf-1", "key": "val"})
        assert resp.success is True
        assert resp.data["executionId"] == "123"


@pytest.mark.asyncio
async def test_n8n_send_data_http_error():
    """N8nConnector.send_data returns error on non-200 response."""
    connector = N8nConnector(base_url="http://n8n.local", api_key="k1")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("backend.connectors.n8n.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        resp = await connector.send_data({"workflow_id": "wf-1"})
        assert resp.success is False
        assert "500" in resp.error


# ── GoHighLevelConnector ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ghl_test_connection_success():
    """GoHighLevelConnector.test_connection returns True on 200."""
    connector = GoHighLevelConnector(api_key="ghl_key", location_id="loc1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("backend.connectors.gohighlevel.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        assert await connector.test_connection() is True


@pytest.mark.asyncio
async def test_ghl_send_data_success():
    """GoHighLevelConnector.send_data creates a contact."""
    connector = GoHighLevelConnector(api_key="ghl_key", location_id="loc1")

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"contact": {"id": "c1"}}

    with patch("backend.connectors.gohighlevel.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        resp = await connector.send_data({"email": "test@example.com", "name": "Test"})
        assert resp.success is True
        assert resp.data["contact"]["id"] == "c1"


@pytest.mark.asyncio
async def test_ghl_send_data_failure():
    """GoHighLevelConnector.send_data returns error on non-201 response."""
    connector = GoHighLevelConnector(api_key="ghl_key", location_id="loc1")

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Bad Request"

    with patch("backend.connectors.gohighlevel.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        resp = await connector.send_data({"email": "bad"})
        assert resp.success is False
        assert "400" in resp.error


@pytest.mark.asyncio
async def test_ghl_receive_data():
    """GoHighLevelConnector.receive_data fetches contacts."""
    connector = GoHighLevelConnector(api_key="ghl_key", location_id="loc1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"contacts": [{"id": "c1"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("backend.connectors.gohighlevel.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        data = await connector.receive_data()
        assert data["contacts"][0]["id"] == "c1"


# ── Webhook ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_send_success():
    """send_webhook posts JSON and returns success."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_resp.text = '{"ok": true}'

    with patch("backend.connectors.webhook.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        resp = await send_webhook("https://example.com/hook", {"event": "test"})
        assert resp.success is True
        assert resp.data["ok"] is True


@pytest.mark.asyncio
async def test_webhook_send_failure():
    """send_webhook returns error on non-2xx."""
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"

    with patch("backend.connectors.webhook.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock()
        mock_cls.return_value = instance

        resp = await send_webhook("https://example.com/hook", {"event": "test"})
        assert resp.success is False
        assert "503" in resp.error


def test_webhook_verify_signature_valid():
    """verify_signature returns True for a correct HMAC."""
    secret = "my_secret"
    payload = b'{"event":"test"}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_signature(payload, sig, secret) is True


def test_webhook_verify_signature_invalid():
    """verify_signature returns False for a wrong HMAC."""
    assert verify_signature(b'{"event":"test"}', "deadbeef", "secret") is False


# ── API endpoints ────────────────────────────────────────────────────────────

# Shared in-memory store for mock sessions within a test.
_connector_store: dict[str, Connector] = {}


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _MockSession:
    def __init__(self):
        self._added: list[Connector] = []

    async def execute(self, stmt):
        try:
            where = stmt.whereclause
        except AttributeError:
            where = None

        if where is not None:
            # Try to extract the comparison value from the WHERE clause.
            for attr in ("right", "element"):
                comp = getattr(where, attr, None)
                if comp is not None and hasattr(comp, "value"):
                    val = comp.value
                    row = _connector_store.get(val)
                    return _FakeResult([row] if row else [])
            # Fallback: if the where clause compares Connector.id, search by all.
            if hasattr(where, "left") and hasattr(where.left, "key"):
                key = where.left.key
                if key == "id" and hasattr(where, "right"):
                    val = where.right.value
                    row = _connector_store.get(val)
                    return _FakeResult([row] if row else [])
        return _FakeResult(list(_connector_store.values()))

    def add(self, obj):
        if obj.id is None:
            from uuid import uuid4

            obj.id = str(uuid4())
        self._added.append(obj)

    async def flush(self):
        from uuid import uuid4

        for obj in self._added:
            if obj.id is None:
                obj.id = str(uuid4())
            _connector_store[obj.id] = obj

    async def delete(self, obj):
        _connector_store.pop(obj.id, None)


async def _mock_get_db():
    session = _MockSession()
    try:
        yield session
    except Exception:
        raise


@pytest.fixture(autouse=True)
def _override_db():
    _connector_store.clear()
    app.dependency_overrides[get_db] = _mock_get_db
    yield
    app.dependency_overrides.clear()
    _connector_store.clear()


@pytest.mark.asyncio
async def test_create_connector(client):
    """POST /api/connectors creates a connector."""
    resp = await client.post(
        "/api/connectors",
        json={"name": "My n8n", "type": "n8n", "base_url": "http://n8n.local"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My n8n"
    assert data["type"] == "n8n"
    assert data["enabled"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_connectors(client):
    """GET /api/connectors returns a list."""
    await client.post("/api/connectors", json={"name": "A", "type": "webhook"})
    resp = await client.get("/api/connectors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_connector_not_found(client):
    """GET /api/connectors/{id} returns 404 for unknown id."""
    resp = await client.get("/api/connectors/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_connector(client):
    """DELETE /api/connectors/{id} removes the connector."""
    create_resp = await client.post(
        "/api/connectors", json={"name": "Del", "type": "webhook"}
    )
    cid = create_resp.json()["id"]
    resp = await client.delete(f"/api/connectors/{cid}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_test_connector_not_found(client):
    """POST /api/connectors/{id}/test returns 404 for unknown id."""
    resp = await client.post("/api/connectors/nonexistent/test")
    assert resp.status_code == 404
