"""Actions, approvals, tool executions and workflow checkpoints for M3.

Revision ID: 0004_actions_workflow
Revises: 0003_tickets
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_actions_workflow"
down_revision: str | None = "0003_tickets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("action_id", sa.String(length=40), nullable=True))
    op.create_index("ix_cases_action_id", "cases", ["action_id"])

    op.add_column(
        "users",
        sa.Column(
            "approval_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute(
        "UPDATE users SET approval_scopes = "
        "'{\"tools\": [\"*\"], \"departments\": [\"*\"]}'::jsonb "
        "WHERE role = 'approver'"
    )

    op.create_table(
        "action_requests",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("case_id", sa.String(length=40), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("tool_label", sa.String(length=120), nullable=False),
        sa.Column("tool_type", sa.String(length=10), nullable=False, server_default="WRITE"),
        sa.Column("risk_level", sa.String(length=10), nullable=False, server_default="HIGH"),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("args_hash", sa.String(length=80), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("impact", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_plan", sa.Text(), nullable=False, server_default=""),
        sa.Column("rollback_plan", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "evidence_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="AWAITING_APPROVAL"
        ),
        sa.Column("requested_by_id", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_requests_case_id", "action_requests", ["case_id"])
    op.create_index("ix_action_requests_tool_name", "action_requests", ["tool_name"])
    op.create_index("ix_action_requests_status", "action_requests", ["status"])
    op.create_index("ix_action_requests_requested_by_id", "action_requests", ["requested_by_id"])
    op.create_index(
        "ix_action_requests_idempotency_key",
        "action_requests",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("action_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("args_hash", sa.String(length=80), nullable=False),
        sa.Column("approver_id", sa.String(length=40), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["action_id"], ["action_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_action_id", "approvals", ["action_id"], unique=True)
    op.create_index("ix_approvals_status", "approvals", ["status"])
    op.create_index("ix_approvals_approver_id", "approvals", ["approver_id"])
    op.create_index("ix_approvals_expires_at", "approvals", ["expires_at"])

    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("action_id", sa.String(length=40), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RUNNING"),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("args_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "verification",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["action_id"], ["action_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_executions_action_id", "tool_executions", ["action_id"], unique=True)
    op.create_index("ix_tool_executions_tool_name", "tool_executions", ["tool_name"])
    op.create_index("ix_tool_executions_status", "tool_executions", ["status"])
    op.create_index(
        "ix_tool_executions_idempotency_key",
        "tool_executions",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("case_id", sa.String(length=40), nullable=False),
        sa.Column("thread_id", sa.String(length=80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.String(length=40), nullable=True),
        sa.Column("node", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="complete"),
        sa.Column("workflow_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["workflow_checkpoints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id", "sequence", name="uq_workflow_checkpoints_case_sequence"
        ),
    )
    op.create_index("ix_workflow_checkpoints_case_id", "workflow_checkpoints", ["case_id"])
    op.create_index("ix_workflow_checkpoints_thread_id", "workflow_checkpoints", ["thread_id"])
    op.create_index("ix_workflow_checkpoints_node", "workflow_checkpoints", ["node"])

    op.create_table(
        "tool_policies",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mock_mode", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("tool_policies")
    op.drop_table("workflow_checkpoints")
    op.drop_table("tool_executions")
    op.drop_table("approvals")
    op.drop_table("action_requests")
    op.drop_column("users", "approval_scopes")
    op.drop_index("ix_cases_action_id", table_name="cases")
    op.drop_column("cases", "action_id")
