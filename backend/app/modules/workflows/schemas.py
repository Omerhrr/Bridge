"""Pydantic schemas for the workflow API."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeDefinition(BaseModel):
    id: str
    type: str
    position: dict[str, float] | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None


class EdgeDefinition(BaseModel):
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None


class WorkflowDefinition(BaseModel):
    nodes: list[NodeDefinition] = Field(default_factory=list)
    edges: list[EdgeDefinition] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    definition: WorkflowDefinition | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: Literal["active", "inactive"] | None = None


class VersionCreate(BaseModel):
    definition: WorkflowDefinition
    comment: str = ""


class WorkflowVersionOut(BaseModel):
    id: int
    version_number: int
    definition: dict[str, Any]
    comment: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowOut(BaseModel):
    id: int
    name: str
    description: str
    status: str
    version_count: int = 0
    current_version: WorkflowVersionOut | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ValidationIssue(BaseModel):
    level: Literal["error", "warning"]
    node_id: str | None = None
    message: str


class ValidationReport(BaseModel):
    valid: bool
    checks_passed: int
    issues: list[ValidationIssue] = Field(default_factory=list)


class WorkflowEventOut(BaseModel):
    id: int
    node_id: str | None
    node_type: str | None
    event: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunOut(BaseModel):
    id: str
    workflow_id: int
    status: str
    current_node: str | None
    variables: dict[str, Any]
    error: str | None
    started_at: datetime
    finished_at: datetime | None
    events: list[WorkflowEventOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TestRunRequest(BaseModel):
    """Simulated trigger payload for the Test button (spec section 20)."""

    payload: dict[str, Any] = Field(default_factory=dict)
