"""GoHighLevel CRM connector."""

import httpx

from backend.connectors.base import BaseConnector, ConnectorResponse

GHL_BASE = "https://services.leadconnectorhq.com"


class GoHighLevelConnector(BaseConnector):
    """Connector for GoHighLevel (GHL) CRM API."""

    connector_type = "gohighlevel"

    def __init__(self, api_key: str, location_id: str):
        self.api_key = api_key
        self.location_id = location_id

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Version": "2021-07-28",
            "Accept": "application/json",
        }

    async def test_connection(self) -> bool:
        """Test connection by listing contacts."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GHL_BASE}/contacts/",
                headers=self._headers(),
                params={"locationId": self.location_id, "limit": 1},
                timeout=10.0,
            )
            return resp.status_code == 200

    async def send_data(self, data: dict) -> ConnectorResponse:
        """Create or update a contact in GoHighLevel."""
        import time

        start = time.monotonic()
        async with httpx.AsyncClient() as client:
            try:
                payload = {**data, "locationId": self.location_id}
                resp = await client.post(
                    f"{GHL_BASE}/contacts/",
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                latency = (time.monotonic() - start) * 1000
                if resp.status_code in (200, 201):
                    return ConnectorResponse(
                        success=True, data=resp.json(), latency_ms=latency
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

    async def receive_data(self) -> dict:
        """List contacts from GoHighLevel."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GHL_BASE}/contacts/",
                headers=self._headers(),
                params={"locationId": self.location_id},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
