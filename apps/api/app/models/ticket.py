from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("cases.id", ondelete="CASCADE"), unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    priority: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    priority_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    affected_system: Mapped[str | None] = mapped_column(String(120), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    suggested_assignee_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    suggested_assignee_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="DRAFT")
    fields: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict
    )
    missing_fields: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    case: Mapped[Case] = relationship(lazy="selectin")
    suggested_assignee: Mapped[User | None] = relationship(
        foreign_keys=[suggested_assignee_id], lazy="selectin"
    )
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="selectin")
    notes: Mapped[list[TicketNote]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketNote.created_at"
    )


class TicketNote(Base):
    __tablename__ = "ticket_notes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    author_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    ticket: Mapped[Ticket] = relationship(back_populates="notes")
    author: Mapped[User] = relationship(lazy="selectin")
