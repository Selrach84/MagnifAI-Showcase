"""n8n workflow automation connector."""

import httpx

from backend.connectors.base import BaseConnector, ConnectorResponse


class N8nConnector(BaseConnector):
    """Connector for n8n workflow automation API."""

    connector_type = "n8n"

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"X-N8N-API-KEY": self.api_key, "Accept": "application/json"}

    async def test_connection(self) -> bool:
        """Test connection by fetching workflows list."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/workflows",
                headers=self._headers(),
                timeout=10.0,
            )
            return resp.status_code == 200

    async def send_data(self, data: dict) -> ConnectorResponse:
        """Execute a workflow by posting to its webhook endpoint."""
        workflow_id = data.pop("workflow_id", None)
        if not workflow_id:
            return ConnectorResponse(success=False, error="workflow_id is required")

        import time

        start = time.monotonic()
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/v1/workflows/{workflow_id}/execute",
                    headers=self._headers(),
                    json=data,
                    timeout=30.0,
                )
                latency = (time.monotonic() - start) * 1000
                if resp.status_code == 200:
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
        """List available webhooks configured in n8n."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/workflows",
                headers=self._headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
