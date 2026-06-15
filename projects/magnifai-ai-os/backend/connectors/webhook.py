"""Webhook sender and receiver utilities."""

import hashlib
import hmac
import time
from typing import Any

import httpx
from fastapi import APIRouter, Request

from backend.connectors.base import BaseConnector, ConnectorResponse

webhook_router = APIRouter(tags=["webhooks"])

# In-memory registry of dynamically registered webhook routes.
_dynamic_routes: dict[str, dict[str, Any]] = {}


class WebhookConnector(BaseConnector):
    """Connector for sending and receiving webhook payloads."""

    connector_type = "webhook"

    def __init__(self, base_url: str = "", secret: str = ""):
        self.base_url = base_url
        self.secret = secret

    async def test_connection(self) -> bool:
        """Test connectivity by sending a GET to the base URL."""
        if not self.base_url:
            return False
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(self.base_url, timeout=10.0)
                return resp.status_code < 400
            except httpx.HTTPError:
                return False

    async def send_data(self, data: dict) -> ConnectorResponse:
        """Send data to the configured webhook URL."""
        if not self.base_url:
            return ConnectorResponse(success=False, error="No base_url configured")
        return await send_webhook(self.base_url, data)

    async def receive_data(self) -> dict:
        """Return the most recent received webhook payload."""
        if not _dynamic_routes:
            return {}
        latest = max(_dynamic_routes.values(), key=lambda r: r["timestamp"])
        return latest


async def send_webhook(
    url: str, data: dict, method: str = "POST", headers: dict | None = None
) -> ConnectorResponse:
    """Send data to a webhook URL."""
    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        try:
            req_method = getattr(client, method.lower())
            resp = await req_method(
                url,
                json=data,
                headers=headers or {"Content-Type": "application/json"},
                timeout=30.0,
            )
            latency = (time.monotonic() - start) * 1000
            if 200 <= resp.status_code < 300:
                return ConnectorResponse(
                    success=True, data=resp.json() if resp.text else {}, latency_ms=latency
                )
            return ConnectorResponse(
                success=False,
                error=f"HTTP {resp.status_code}: {resp.text}",
                latency_ms=latency,
            )
        except httpx.HTTPError as e:
            return ConnectorResponse(
                success=False, error=str(e), latency_ms=(time.monotonic() - start) * 1000
            )


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_receive_endpoint(path: str) -> APIRouter:
    """Register a FastAPI route that captures incoming webhook payloads.

    Returns a dedicated router that can be included in the main app.
    """
    router = APIRouter(tags=["webhooks"])

    async def _handler(request: Request) -> dict:
        body = await request.body()
        _dynamic_routes[path] = {
            "body": body,
            "headers": dict(request.headers),
            "timestamp": time.time(),
        }
        return {"received": True, "path": path}

    router.add_api_route(path, _handler, methods=["POST"])
    return router
