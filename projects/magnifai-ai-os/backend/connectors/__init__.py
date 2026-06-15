"""Platform connectors for MagnifAI AI OS."""

from backend.connectors.base import BaseConnector, ConnectorConfig, ConnectorResponse
from backend.connectors.gohighlevel import GoHighLevelConnector
from backend.connectors.n8n import N8nConnector
from backend.connectors.webhook import WebhookConnector

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorResponse",
    "GoHighLevelConnector",
    "N8nConnector",
    "WebhookConnector",
]
