"""Base connector interface."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class ConnectorConfig(BaseModel):
    """Configuration for a platform connector."""

    name: str
    type: str  # "n8n", "gohighlevel", "webhook"
    credentials: dict = {}
    base_url: str = ""
    enabled: bool = True


class ConnectorResponse(BaseModel):
    """Standard response from a connector operation."""

    success: bool
    data: dict = {}
    error: str = ""
    latency_ms: float = 0.0


class BaseConnector(ABC):
    """Abstract base class for all platform connectors."""

    connector_type: str

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test that the connector can reach the external platform."""
        ...

    @abstractmethod
    async def send_data(self, data: dict) -> ConnectorResponse:
        """Send data to the external platform."""
        ...

    @abstractmethod
    async def receive_data(self) -> dict:
        """Receive data from the external platform."""
        ...
