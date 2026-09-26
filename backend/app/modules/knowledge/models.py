"""Knowledge base: the business profile and the sources Bridge answers from."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.workflows.models import utcnow


class BusinessProfile(Base):
    """Single-row table describing the business the assistant speaks for."""

    __tablename__ = "business_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    # Sent when the knowledge base doesn't contain the answer.
    fallback_message: Mapped[str] = mapped_column(Text, default="")
    assistant_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # website | google_doc | google_sheet | database | text
    kind: Mapped[str] = mapped_column(String(24))
    # Non-secret settings: url, max_pages, query, text …
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # Encrypted secret (database connection string). Never returned by the API.
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|syncing|ready|error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    location: Mapped[str] = mapped_column(String(1000), default="")  # page URL, sheet row …
    content: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ApiKey(Base):
    """A key issued so an external site or app (a chatbot widget, a backend
    integration) can call the public Ask Assistant endpoint without signing
    in to the Bridge dashboard. Only a hash of the key is stored; the
    plaintext is shown once, at creation."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    # First few characters of the key, kept for display ("brdg_a1b2...").
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeQuery(Base):
    """Every question the assistant handled; unanswered ones tell the
    business owner which information to add."""

    __tablename__ = "knowledge_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel: Mapped[str] = mapped_column(String(16), default="sms")  # sms | dashboard | workflow
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    answered: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(24), default="")
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
