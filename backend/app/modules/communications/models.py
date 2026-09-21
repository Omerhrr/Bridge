"""Communication records: calls and SMS messages (spec section 30)."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.workflows.models import utcnow


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_call_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), default="inbound")
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="received")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), default="inbound")  # inbound|outbound
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="received")
    meta: Mapped[dict | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
