"""Workflow domain models: definition, versioning, runs and events (spec sections 30-31)."""
import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def mutable_json() -> MutableDict:
    """JSON column that tracks in-place dict mutations (needed for run variables)."""
    return MutableDict.as_mutable(JSON)


class WorkflowStatus(str, enum.Enum):
    inactive = "inactive"
    active = "active"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    waiting = "waiting"  # paused mid-run, e.g. a USSD menu waiting for user input
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.inactive
    )
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_versions.id", use_alter=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    versions: Mapped[list["WorkflowVersion"]] = relationship(
        back_populates="workflow", foreign_keys="WorkflowVersion.workflow_id"
    )
    current_version: Mapped["WorkflowVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workflow")


class WorkflowVersion(Base):
    """Immutable workflow definition snapshot (spec section 31)."""

    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    definition: Mapped[dict] = mapped_column(JSON, default=dict)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workflow: Mapped[Workflow] = relationship(
        back_populates="versions", foreign_keys=[workflow_id]
    )
    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="version")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), index=True)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_versions.id"))
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    current_node: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_payload: Mapped[dict] = mapped_column(mutable_json(), default=dict)
    variables: Mapped[dict] = mapped_column(mutable_json(), default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped[Workflow] = relationship(back_populates="runs", foreign_keys=[workflow_id])
    version: Mapped[WorkflowVersion | None] = relationship(
        back_populates="runs", foreign_keys=[version_id]
    )
    events: Mapped[list["WorkflowEvent"]] = relationship(back_populates="run")


class WorkflowEvent(Base):
    """Execution history for one node step (spec sections 13/29)."""

    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    node_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[WorkflowRun] = relationship(back_populates="events")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
