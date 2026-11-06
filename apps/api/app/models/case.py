from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False, default="NEW")
    current_node: Mapped[str] = mapped_column(String(40), nullable=False, default="intake")
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    action_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    requester: Mapped[User] = relationship(back_populates="cases")
    messages: Mapped[list[Message]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Message.created_at"
    )
