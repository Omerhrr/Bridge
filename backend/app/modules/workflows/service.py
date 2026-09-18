"""Workflow service: persistence, versioning, validation and seeding."""

import uuid

from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.modules.workflows.models import Workflow, WorkflowVersion
from app.modules.workflows.registry import REGISTRY, get_spec
from app.modules.workflows.schemas import (
    ValidationIssue,
    ValidationReport,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowUpdate,
)


# --------------------------------------------------------------------- CRUD
def list_workflows(db: Session) -> list[Workflow]:
    return db.query(Workflow).order_by(Workflow.created_at.desc()).all()


def get_workflow(db: Session, workflow_id: int) -> Workflow | None:
    return db.get(Workflow, workflow_id)


def get_workflow_by_name(db: Session, name: str) -> Workflow | None:
    return db.query(Workflow).filter(Workflow.name == name).first()


def _store_version(db: Session, workflow: Workflow, definition: WorkflowDefinition) -> WorkflowVersion:
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=workflow.current_version,
        definition=definition.model_dump(),
    )
    db.add(version)
    return version


def create_workflow(db: Session, payload: WorkflowCreate) -> Workflow:
    workflow = Workflow(
        name=payload.name,
        description=payload.description,
        enabled=payload.enabled,
        current_version=1,
    )
    db.add(workflow)
    db.flush()
    _store_version(db, workflow, payload.definition)
    db.commit()
    log_event("workflow.created", detail=workflow.name)
    return workflow


def update_workflow(db: Session, workflow: Workflow, payload: WorkflowUpdate) -> Workflow:
    """Definition changes bump the version — history stays intact (spec §31)."""
    definition_changed = payload.definition is not None and payload.definition.model_dump() != workflow.versions[-1].definition
    if payload.name is not None:
        workflow.name = payload.name
    if payload.description is not None:
        workflow.description = payload.description
    if payload.enabled is not None:
        workflow.enabled = payload.enabled
    if definition_changed:
        workflow.current_version += 1
        _store_version(db, workflow, payload.definition)
    db.commit()
    db.refresh(workflow)
    return workflow


def delete_workflow(db: Session, workflow: Workflow) -> None:
    db.delete(workflow)
    db.commit()


def latest_definition(workflow: Workflow) -> dict:
    return workflow.versions[-1].definition if workflow.versions else {"nodes": [], "edges": []}


# --------------------------------------------------------------- validation
def validate_definition(definition: WorkflowDefinition) -> ValidationReport:
    """Static validation before deployment (spec §23)."""
    checks: list[ValidationIssue] = []

    nodes = definition.nodes
    edges = definition.edges
    node_ids = {n.id for n in nodes}

    # Unknown node types
    unknown = [n for n in nodes if n.type not in REGISTRY]
    for node in unknown:
        checks.append(ValidationIssue(node_id=node.id, severity="error", message=f"Unknown node type '{node.type}'"))
    if not unknown:
        checks.append(ValidationIssue(severity="ok", message="All node types recognised"))

    # At least one trigger / entry node
    trigger_types = {"incoming_call", "incoming_sms", "ussd_request", "start"}
    triggers = [n for n in nodes if n.type in trigger_types]
    if not triggers:
        checks.append(ValidationIssue(severity="error", message="Workflow has no trigger or Start node"))
    elif len(triggers) > 1:
        checks.append(ValidationIssue(
            node_id=triggers[-1].id, severity="warning",
            message="Multiple triggers — only the first is used as the entry point",
        ))
    else:
        checks.append(ValidationIssue(node_id=triggers[0].id, severity="ok", message="Trigger node configured"))

    # Edge integrity
    broken = [e for e in edges if e.source not in node_ids or e.target not in node_ids]
    for edge in broken:
        checks.append(ValidationIssue(severity="error", message=f"Edge {edge.source} -> {edge.target} references a missing node"))
    if not broken:
        checks.append(ValidationIssue(severity="ok", message="All connections reference existing nodes"))

    # Disconnected nodes (except end)
    connected = {e.source for e in edges} | {e.target for e in edges}
    disconnected = [n for n in nodes if n.id not in connected and n.type not in (*trigger_types, "end")]
    for node in disconnected:
        checks.append(ValidationIssue(node_id=node.id, severity="error", message="Node is not connected to the flow"))
    if not disconnected:
        checks.append(ValidationIssue(severity="ok", message="No disconnected nodes"))

    # End reachable
    has_end = any(n.type == "end" for n in nodes)
    if nodes and not has_end:
        checks.append(ValidationIssue(severity="warning", message="No End node — the run stops at the last connected node"))
    else:
        checks.append(ValidationIssue(severity="ok", message="End node configured"))

    # Required configuration per node
    for node in nodes:
        if node.type not in REGISTRY:
            continue
        spec = get_spec(node.type)
        for field in spec.config_fields:
            if field.required and not (node.config or {}).get(field.name):
                checks.append(ValidationIssue(
                    node_id=node.id, severity="error",
                    message=f"{spec.label}: '{field.label}' is required",
                ))
    required_total = sum(
        len(get_spec(n.type).config_fields) for n in nodes if n.type in REGISTRY
    )
    if required_total:
        passed_required = required_total - sum(1 for c in checks if c.severity == "error" and "'" in c.message and "required" in c.message)
        checks.append(ValidationIssue(severity="ok", message=f"Required node configuration present ({passed_required}/{required_total})"))

    errors = [c for c in checks if c.severity == "error"]
    warnings = [c for c in checks if c.severity == "warning"]
    summary = (
        f"{len(checks) - len(errors) - len(warnings)} checks passed, "
        f"{len(errors)} issue{'s' if len(errors) != 1 else ''} found"
        + (f", {len(warnings)} warning{'s' if len(warnings) != 1 else ''}" if warnings else "")
    )
    return ValidationReport(valid=not errors, checks=checks, summary=summary)


# -------------------------------------------------------------------- seed
VOICE_TRANSLATOR: dict = {
    "nodes": [
        {"id": "1", "type": "incoming_call", "position": {"x": 40, "y": 160}, "config": {}},
        {"id": "2", "type": "collect_speech", "position": {"x": 300, "y": 160},
         "config": {"prompt": "Please say your message.", "timeout": 10}},
        {"id": "3", "type": "speech_to_text", "position": {"x": 560, "y": 160}, "config": {"language": "auto"}},
        {"id": "4", "type": "translate", "position": {"x": 820, "y": 160},
         "config": {"source_language": "auto", "target_language": "ha", "from_variable": "transcript", "fallback": True}},
        {"id": "5", "type": "text_to_speech", "position": {"x": 1080, "y": 160},
         "config": {"from_variable": "translation", "language": "ha"}},
        {"id": "6", "type": "play_audio", "position": {"x": 1340, "y": 160}, "config": {"audio_url": "{{audio_url}}"}},
        {"id": "7", "type": "end", "position": {"x": 1600, "y": 160}, "config": {}},
    ],
    "edges": [
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3", "source_handle": "speech"},
        {"source": "3", "target": "4"},
        {"source": "4", "target": "5"},
        {"source": "5", "target": "6"},
        {"source": "6", "target": "7"},
    ],
}

SMS_TRANSLATOR: dict = {
    "nodes": [
        {"id": "1", "type": "incoming_sms", "position": {"x": 40, "y": 160}, "config": {}},
        {"id": "2", "type": "detect_language", "position": {"x": 300, "y": 160}, "config": {"from_variable": "message"}},
        {"id": "3", "type": "translate", "position": {"x": 560, "y": 160},
         "config": {"source_language": "auto", "target_language": "ha", "from_variable": "message", "fallback": True}},
        {"id": "4", "type": "send_sms", "position": {"x": 820, "y": 160},
         "config": {"to": "{{caller}}", "from_variable": "translation"}},
        {"id": "5", "type": "end", "position": {"x": 1080, "y": 160}, "config": {}},
    ],
    "edges": [
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3"},
        {"source": "3", "target": "4"},
        {"source": "4", "target": "5"},
    ],
}

VOICE_TO_SMS: dict = {
    "nodes": [
        {"id": "1", "type": "incoming_call", "position": {"x": 40, "y": 160}, "config": {}},
        {"id": "2", "type": "collect_speech", "position": {"x": 300, "y": 160},
         "config": {"prompt": "Please say the message you would like to send.", "timeout": 12}},
        {"id": "3", "type": "speech_to_text", "position": {"x": 560, "y": 160}, "config": {"language": "auto"}},
        {"id": "4", "type": "translate", "position": {"x": 820, "y": 160},
         "config": {"source_language": "auto", "target_language": "ha", "from_variable": "transcript"}},
        {"id": "5", "type": "send_sms", "position": {"x": 1080, "y": 160},
         "config": {"to": "{{recipient}}", "from_variable": "translation"}},
        {"id": "6", "type": "end", "position": {"x": 1340, "y": 160}, "config": {}},
    ],
    "edges": [
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3", "source_handle": "speech"},
        {"source": "3", "target": "4"},
        {"source": "4", "target": "5"},
        {"source": "5", "target": "6"},
    ],
}

DEFAULT_WORKFLOWS = [
    ("Voice Translator", "Answers a call, transcribes the caller's speech, translates it and plays it back.", VOICE_TRANSLATOR),
    ("SMS Translator", "Detects the language of an incoming SMS, translates it and replies by SMS.", SMS_TRANSLATOR),
    ("Voice to SMS", "Collects a spoken message on a call, translates it and delivers it as an SMS.", VOICE_TO_SMS),
]


def seed_default_workflows(db: Session) -> None:
    """Create the demo workflows once so the platform boots with value."""
    if db.query(Workflow).count() > 0:
        return
    for name, description, definition in DEFAULT_WORKFLOWS:
        workflow = Workflow(name=name, description=description, enabled=True, current_version=1)
        db.add(workflow)
        db.flush()
        _store_version(db, workflow, WorkflowDefinition.model_validate(definition))
    db.commit()
    log_event("seed.default_workflows", detail=f"{len(DEFAULT_WORKFLOWS)} workflows")
