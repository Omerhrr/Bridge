"""Pydantic schemas for workflow definitions and API payloads."""

from pydantic import BaseModel, Field


class NodeDefinition(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    type: str = Field(min_length=1, max_length=40)
    label: str | None = None
    position: dict | None = None  # {"x": ..., "y": ...} — Vue Flow layout
    config: dict = Field(default_factory=dict)


class EdgeDefinition(BaseModel):
    source: str
    target: str
    source_handle: str | None = None  # branch handle: out/true/false/speech/default/<case>


class WorkflowDefinition(BaseModel):
    """Serialisable workflow graph — the contract between Vue Flow and the engine."""

    nodes: list[NodeDefinition] = Field(default_factory=list)
    edges: list[EdgeDefinition] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    enabled: bool = False
    definition: WorkflowDefinition = WorkflowDefinition()


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    definition: WorkflowDefinition | None = None


class WorkflowOut(BaseModel):
    id: int
    name: str
    description: str
    enabled: bool
    current_version: int
    definition: WorkflowDefinition
    created_at: str | None = None
    updated_at: str | None = None


class ValidationIssue(BaseModel):
    node_id: str | None = None
    severity: str  # ok | error | warning
    message: str


class ValidationReport(BaseModel):
    valid: bool
    checks: list[ValidationIssue]
    summary: str
