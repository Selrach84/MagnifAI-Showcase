import enum

from sqlalchemy import Column, DateTime, Float, JSON, String
from sqlalchemy.sql import func

from backend.models.base import Base


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, default=AgentStatus.ACTIVE)
    config = Column(JSON, default={})
    system_prompt = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False)
    task = Column(JSON, default={})
    status = Column(String, default="pending")
    output = Column(JSON, default={})
    error = Column(String, nullable=True)
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
