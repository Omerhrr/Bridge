"""Conversation records: every communication session (spec sections 27-28)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.workflows.models import utcnow


class Channel(str):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), index=True)  # voice | sms | ussd
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|completed|failed
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id"), nullable=True, index=True
    )
    a_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    b_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", order_by="ConversationMessage.id"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # caller | system | callee
    channel: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    translated_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
