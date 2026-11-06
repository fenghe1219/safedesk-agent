"""Tickets, ticket notes and case ticket links for M2.

Revision ID: 0003_tickets
Revises: 0002_knowledge_messages
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_tickets"
down_revision: str | None = "0002_knowledge_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("ticket_id", sa.String(length=40), nullable=True))
    op.create_index("ix_cases_ticket_id", "cases", ["ticket_id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("case_id", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=4), nullable=False),
        sa.Column("priority_reason", sa.String(length=300), nullable=False),
        sa.Column("affected_system", sa.String(length=120), nullable=True),
        sa.Column("environment", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("urgency_reason", sa.String(length=300), nullable=True),
        sa.Column("suggested_assignee_id", sa.String(length=40), nullable=True),
        sa.Column("suggested_assignee_reason", sa.String(length=300), nullable=True),
        sa.Column("assignee_id", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "missing_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(["suggested_assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_case_id", "tickets", ["case_id"], unique=True)
    op.create_index("ix_tickets_category", "tickets", ["category"])
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"])
    op.create_index("ix_tickets_suggested_assignee_id", "tickets", ["suggested_assignee_id"])
    op.create_index("ix_tickets_updated_at", "tickets", ["updated_at"])

    op.create_table(
        "ticket_notes",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("ticket_id", sa.String(length=40), nullable=False),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_notes_ticket_id", "ticket_notes", ["ticket_id"])
    op.create_index("ix_ticket_notes_author_id", "ticket_notes", ["author_id"])


def downgrade() -> None:
    op.drop_table("ticket_notes")
    op.drop_table("tickets")
    op.drop_index("ix_cases_ticket_id", table_name="cases")
    op.drop_column("cases", "ticket_id")
