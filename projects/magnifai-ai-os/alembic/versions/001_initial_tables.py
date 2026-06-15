"""initial tables

Revision ID: 001
Revises:
Create Date: 2026-06-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # clients
    op.create_table(
        "clients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contract_start", sa.Date(), nullable=True),
        sa.Column("monthly_budget_usd", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # templates
    op.create_table(
        "templates",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema", postgresql.JSONB(), nullable=False),
        sa.Column("n8n_workflow", postgresql.JSONB(), nullable=False),
        sa.Column("required_connectors", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("estimated_setup_hours", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "client_id",
            sa.String(36),
            sa.ForeignKey("clients.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), server_default="setup"),
        sa.Column("n8n_instance_url", sa.String(500), nullable=True),
        sa.Column("docker_stack_name", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # deployments
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.String(100),
            sa.ForeignKey("templates.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="configured"),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_status", sa.String(20), server_default="unknown"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # execution_logs
    op.create_table(
        "execution_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "deployment_id",
            sa.String(36),
            sa.ForeignKey("deployments.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # prompt_templates
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("temperature", sa.Float(), server_default="0.7"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("prompt_templates")
    op.drop_table("execution_logs")
    op.drop_table("deployments")
    op.drop_table("projects")
    op.drop_table("templates")
    op.drop_table("clients")
