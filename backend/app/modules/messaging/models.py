"""Messaging records: the unified message log and relay profiles.

New tables only (no ALTERs on existing ones) so `create_all` upgrades an
existing database — including the one already running on Render — safely.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.workflows.models import utcnow


class MessageLog(Base):
    """Every SMS Bridge received or sent, with its translation."""

    __tablename__ = "bridge_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[str] = mapped_column(String(8), index=True)  # inbound | outbound
    # inbound | relay | broadcast | reply | system | workflow
    kind: Mapped[str] = mapped_column(String(16), default="workflow")
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    to_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    source_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="sent")
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class BridgeProfile(Base):
    """Per-phone relay state: who they are chatting with, and whether their
    language was set explicitly (LANG command / dashboard) or auto-detected."""

    __tablename__ = "bridge_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    partner_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
