from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.case import Case


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETE")
    citations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    request_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    client_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

    citations_rel: Mapped[list[Citation]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="Citation.ordinal"
    )
    case: Mapped[Case] = relationship(back_populates="messages")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    doc_id: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    doc_version: Mapped[str] = mapped_column(String(30), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    section: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    offset_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    offset_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    message: Mapped[Message] = relationship(back_populates="citations_rel")
