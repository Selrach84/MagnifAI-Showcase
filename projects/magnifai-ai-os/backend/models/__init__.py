"""SQLAlchemy models for MagnifAI AI OS."""

from backend.models.base import Base  # noqa: F401

from backend.models.client import Client  # noqa: E402
from backend.models.connector import Connector  # noqa: E402
from backend.models.deployment import Deployment  # noqa: E402
from backend.models.execution_log import ExecutionLog  # noqa: E402
from backend.models.project import Project  # noqa: E402
from backend.models.prompt_template import PromptTemplate  # noqa: E402
from backend.models.template import Template  # noqa: E402

__all__ = [
    "Base",
    "Client",
    "Connector",
    "Project",
    "Template",
    "Deployment",
    "ExecutionLog",
    "PromptTemplate",
]
