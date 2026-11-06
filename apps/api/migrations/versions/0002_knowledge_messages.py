"""Knowledge chunks, citations and case messages for M1.

Revision ID: 0002_knowledge_messages
Revises: 0001_initial
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_knowledge_messages"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False, server_default="v1"),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("file_uri", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("acl", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="READY"),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_content", sa.Text(), nullable=False, server_default=""),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_owner_id", "knowledge_documents", ["owner_id"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_documents_title", "knowledge_documents", ["title"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("doc_id", sa.String(length=40), nullable=False),
        sa.Column("doc_version", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("section", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("offset_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offset_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("acl_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("embedding", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column(
            "chunk_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["doc_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_doc_id", "knowledge_chunks", ["doc_id"])
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_content_trgm ON knowledge_chunks "
        "USING gin (content gin_trgm_ops)"
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("case_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="COMPLETE"),
        sa.Column("citations", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("model_version", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("client_message_id", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_case_id", "messages", ["case_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_client_message_id", "messages", ["client_message_id"])

    op.create_table(
        "citations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("chunk_id", sa.String(length=40), nullable=False),
        sa.Column("doc_id", sa.String(length=40), nullable=False),
        sa.Column("doc_version", sa.String(length=30), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("locator", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("section", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("offset_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offset_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citations_message_id", "citations", ["message_id"])
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"])
    op.create_index("ix_citations_doc_id", "citations", ["doc_id"])


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("messages")
    op.drop_index("ix_knowledge_chunks_content_trgm", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
