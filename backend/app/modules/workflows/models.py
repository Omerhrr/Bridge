"""Workflow persistence models.

Separation of concerns (spec §30):
- Workflow + WorkflowVersion  -> the *definition* (what to run)
- WorkflowRun + WorkflowEvent -> the *execution* (what happened)
- Communication records live in the conversations/communications modules.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    versions: Mapped[list["WorkflowVersion"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowVersion.version_number"
    )
    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workflow")


class WorkflowVersion(Base):
    """Immutable snapshot of a workflow definition.

    Runs keep the version they started with so modifying a workflow never
    changes the interpretation of a historical execution (spec §31).
    """

    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSON)  # {"nodes": [...], "edges": [...]}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    workflow: Mapped[Workflow] = relationship(back_populates="versions")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version_id: Mapped[int] = mapped_column(ForeignKey("workflow_versions.id", ondelete="CASCADE"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|waiting_input|completed|failed
    current_node: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # MutableDict so in-place updates (engine merging node outputs) are persisted.
    variables: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    workflow: Mapped[Workflow] = relationship(back_populates="runs")
    version: Mapped[WorkflowVersion] = relationship()
    events: Mapped[list["WorkflowEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="WorkflowEvent.id"
    )


class WorkflowEvent(Base):
    """One executed node inside a run — the execution history (spec §13, §29)."""

    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    node_id: Mapped[str] = mapped_column(String(60))
    node_type: Mapped[str] = mapped_column(String(40))
    node_label: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="completed")  # completed|failed|waiting
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    run: Mapped[WorkflowRun] = relationship(back_populates="events")


class ProcessedEvent(Base):
    """Telecom webhooks can retry — this table guarantees one event runs once (spec §45)."""

    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("provider", "event_key", name="uq_provider_event_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    event_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
