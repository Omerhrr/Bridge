"""Unit tests for workflow validation (spec section 44)."""
import os

os.environ.setdefault("SEED_DEMO_DATA", "false")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

import pytest  # noqa: E402

from app.modules.workflows.schemas import WorkflowDefinition  # noqa: E402
from app.modules.workflows.validator import validate_workflow  # noqa: E402


def _voice_translation_definition() -> dict:
    return {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "speech_to_text"},
            {"id": "3", "type": "translate", "config": {"target_language": "ha"}},
            {"id": "4", "type": "text_to_speech"},
            {"id": "5", "type": "play_voice"},
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"},
            {"source": "3", "target": "4"},
            {"source": "4", "target": "5"},
        ],
    }


def test_valid_workflow_passes():
    report = validate_workflow(WorkflowDefinition.model_validate(_voice_translation_definition()))
    assert report.valid, [i.message for i in report.issues]
    assert report.checks_passed >= 6


def test_missing_trigger_fails():
    definition = {
        "nodes": [{"id": "2", "type": "translate", "config": {"target_language": "ha"}}],
        "edges": [],
    }
    report = validate_workflow(WorkflowDefinition.model_validate(definition))
    assert not report.valid
    assert any("trigger" in i.message.lower() for i in report.issues)


def test_missing_required_config_detected():
    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "translate"},  # missing target_language
        ],
        "edges": [{"source": "1", "target": "2"}],
    }
    report = validate_workflow(WorkflowDefinition.model_validate(definition))
    assert not report.valid
    assert any("target_language" in i.message for i in report.issues)


def test_disconnected_node_detected():
    definition = _voice_translation_definition()
    definition["nodes"].append({"id": "9", "type": "send_sms"})
    report = validate_workflow(WorkflowDefinition.model_validate(definition))
    assert not report.valid
    assert any("not connected" in i.message.lower() for i in report.issues)


def test_unknown_node_type_detected():
    definition = _voice_translation_definition()
    definition["nodes"].append({"id": "6", "type": "not_a_node"})
    definition["edges"].append({"source": "5", "target": "6"})
    report = validate_workflow(WorkflowDefinition.model_validate(definition))
    assert not report.valid
    assert any("unknown node type" in i.message.lower() for i in report.issues)
