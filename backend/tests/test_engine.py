"""Engine tests: node execution, branching, pausing, translation flow (spec §13)."""

from app.modules.workflows import service as workflow_service
from app.modules.workflows.engine import get_engine
from app.modules.workflows.models import WorkflowEvent, WorkflowRun
from app.modules.workflows.schemas import WorkflowDefinition
from app.modules.workflows.service import validate_definition


def test_sms_translation_flow_end_to_end(db, sms_workflow):
    """Incoming SMS -> detect -> translate -> send_sms -> end (spec §7)."""
    engine = get_engine(db)
    run = engine.start_run(sms_workflow, variables={"caller": "+234801", "message": "Where are you?"})
    run = engine.resume(run)

    assert run.status == "completed"
    assert run.variables["translation"] == "ina kake"  # mock en->ha dictionary
    assert run.variables["source_language"] == "en"
    assert run.variables["target_language"] == "ha"
    assert run.variables["sms_sent_to"] == "+234801"
    assert run.duration_ms is not None

    node_types = [e.node_type for e in run.events]
    assert node_types[0] == "incoming_sms"
    assert node_types[-1] == "end"
    assert "send_sms" in node_types


def test_condition_branching(db):
    """Failure path: an empty translation routes down the false branch (spec §34)."""
    definition = WorkflowDefinition.model_validate({
        "nodes": [
            {"id": "1", "type": "start", "config": {}},
            {"id": "2", "type": "set_variable", "config": {"name": "translation", "value": ""}},
            {"id": "3", "type": "condition", "config": {"variable": "translation", "operator": "not_empty"}},
            {"id": "4", "type": "send_sms", "config": {"to": "+1", "message": "ok"}},
            {"id": "5", "type": "send_sms", "config": {"to": "+1", "message": "fallback"}},
            {"id": "6", "type": "end", "config": {}},
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"},
            {"source": "3", "target": "4", "source_handle": "true"},
            {"source": "3", "target": "5", "source_handle": "false"},
            {"source": "4", "target": "6"},
            {"source": "5", "target": "6"},
        ],
    })
    workflow = workflow_service.create_workflow(
        db, workflow_service.WorkflowCreate(name="Branch Test", definition=definition)
    )
    engine = get_engine(db)
    run = engine.start_run(workflow)
    run = engine.resume(run)

    assert run.status == "completed"
    messages = [e.detail for e in run.events if e.node_type == "send_sms"]
    assert len(messages) == 1
    assert messages[0]["message"] == "fallback"


def test_voice_run_pauses_at_collect_speech_and_resumes(db, voice_workflow):
    """Two-phase voice call: pause for speech, then resume with a recording (spec §6)."""
    engine = get_engine(db)
    run = engine.start_run(voice_workflow, variables={"caller": "+234802", "_session_id": "sess_1"})
    run = engine.resume(run)

    assert run.status == "waiting_input"
    assert run.current_node == "2"  # collect_speech

    # Resume with the recording from the second webhook event.
    run = engine.resume(run, {"recording_url": "https://recordings.at/abc.mp3"})
    assert run.status == "completed"
    assert run.variables["transcript"]
    assert run.variables["translation"]
    assert run.variables["audio_url"]

    node_types = [e.node_type for e in run.events]
    assert node_types == ["incoming_call", "collect_speech", "speech_to_text", "translate",
                          "text_to_speech", "play_audio", "end"]


def test_validation_detects_broken_definitions(db):
    """Missing trigger, disconnected node, missing required config (spec §23)."""
    report = validate_definition(WorkflowDefinition.model_validate({
        "nodes": [
            {"id": "1", "type": "translate", "config": {}},   # no trigger + missing target
            {"id": "2", "type": "send_sms", "config": {}},    # disconnected
        ],
        "edges": [],
    }))
    assert report.valid is False
    messages = " | ".join(c.message for c in report.checks)
    assert "no trigger" in messages.lower()
    assert "not connected" in messages.lower()
    assert "required" in messages.lower()


def test_failed_node_marks_run_failed(db):
    definition = WorkflowDefinition.model_validate({
        "nodes": [
            {"id": "1", "type": "incoming_sms", "config": {}},
            {"id": "2", "type": "speech_to_text", "config": {}},  # no recording -> node fails
            {"id": "3", "type": "end", "config": {}},
        ],
        "edges": [{"source": "1", "target": "2"}, {"source": "2", "target": "3"}],
    })
    workflow = workflow_service.create_workflow(
        db, workflow_service.WorkflowCreate(name="Fails", definition=definition)
    )
    engine = get_engine(db)
    run = engine.start_run(workflow, variables={"caller": "+1", "message": "hi"})
    run = engine.resume(run)

    assert run.status == "failed"
    assert run.error and "no recording" in run.error
    failed_event = db.query(WorkflowEvent).filter(WorkflowEvent.run_id == run.id, WorkflowEvent.status == "failed").first()
    assert failed_event is not None
