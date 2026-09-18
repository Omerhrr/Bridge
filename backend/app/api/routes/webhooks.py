"""Africa's Talking webhooks (spec §25, §45).

    Africa's Talking -> Webhook -> Identify workflow -> Create run -> Execute

Voice is *conversational*: each webhook event advances the run until a node
produces caller-facing actions (Say/Play/GetSpeech) or the flow ends. SMS
runs inline: the incoming message triggers a full workflow execution.

Idempotency (spec §45): every event is keyed and checked against the
processed_events table so provider retries never duplicate work.
"""

import hashlib

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import log_event
from app.modules.conversations import service as conversation_service
from app.modules.workflows import service as workflow_service
from app.modules.workflows.engine import get_engine
from app.modules.workflows.models import ProcessedEvent, Workflow, WorkflowRun

router = APIRouter(prefix="/webhooks/africastalking", tags=["webhooks"])


# --------------------------------------------------------------- idempotency
def _already_processed(db: Session, provider: str, event_key: str) -> bool:
    exists = (
        db.query(ProcessedEvent)
        .filter(ProcessedEvent.provider == provider, ProcessedEvent.event_key == event_key)
        .first()
    )
    if exists:
        return True
    try:
        db.add(ProcessedEvent(provider=provider, event_key=event_key))
        db.commit()
    except Exception:  # pragma: no cover — concurrent duplicate insert
        db.rollback()
        return True
    return False


def _event_key(payload: dict) -> str:
    """Stable key for an incoming telecom event (AT retried requests match)."""
    session_id = payload.get("sessionId") or payload.get("sessionId_") or ""
    message_id = payload.get("id") or payload.get("messageId") or ""
    if message_id:
        return f"sms:{message_id}"
    raw = f"{session_id}|{payload.get('phoneNumber') or payload.get('callerNumber')}|{payload.get('text', '')}|{payload.get('dtmf', '')}|{payload.get('isActive')}|{payload.get('recordingUrl', '')}"
    return f"voice:{hashlib.sha1(raw.encode()).hexdigest()[:24]}"


# ----------------------------------------------------------------- matching
def _find_enabled_workflow(db: Session, trigger_type: str, channel_hint: str | None = None) -> Workflow | None:
    workflows = (
        db.query(Workflow)
        .filter(Workflow.enabled.is_(True))
        .order_by(Workflow.id.asc())
        .all()
    )
    for workflow in workflows:
        if not workflow.versions:
            continue
        nodes = workflow.versions[-1].definition.get("nodes", [])
        if any(n.get("type") == trigger_type for n in nodes):
            return workflow
    return None


# ---------------------------------------------------------------------- SMS
@router.post("/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """Incoming SMS -> language detection -> translation -> outgoing SMS."""
    payload = await _parse(request)
    key = _event_key(payload)
    if _already_processed(db, "africastalking", key):
        log_event("webhook.duplicate_ignored", detail=key)
        return {"status": "duplicate_ignored"}

    text = (payload.get("text") or "").strip()
    sender = payload.get("from") or payload.get("phoneNumber") or "unknown"
    log_event("sms.received", detail=f"from={sender}")

    workflow = _find_enabled_workflow(db, "incoming_sms")
    if not workflow:
        return {"status": "no_workflow"}

    conversation = conversation_service.get_or_create_conversation(
        db, channel="sms", from_number=sender, to_number=payload.get("to"),
        session_id=payload.get("id") or payload.get("messageId"), workflow=workflow,
    )
    conversation_service.add_message(db, conversation, role="user", channel="sms", content=text)

    engine = get_engine(db)
    run = engine.start_run(
        workflow,
        variables={"caller": sender, "message": text, "_conversation_id": conversation.id},
        conversation_id=conversation.id,
    )
    run = engine.resume(run)
    _sync_conversation_from_run(db, conversation, run)
    conversation_service.complete_conversation(db, conversation)
    log_event("sms.processed", conversation_id=conversation.id, workflow_run_id=run.id)
    return {"status": run.status, "run_id": run.id, "conversation_id": conversation.id}


# -------------------------------------------------------------------- Voice
@router.post("/voice")
async def voice_webhook(request: Request, db: Session = Depends(get_db)):
    """AT voice callback.

    First event of a session starts the workflow and returns the accumulated
    actions; subsequent events (GetSpeech result with dtmf/recordingUrl)
    resume the paused run.
    """
    payload = await _parse(request)
    key = _event_key(payload)
    if _already_processed(db, "africastalking", key):
        log_event("webhook.duplicate_ignored", detail=key)
        return {"actions": []}

    session_id = payload.get("sessionId") or payload.get("callSessionId") or payload.get("id") or ""
    caller = payload.get("callerNumber") or payload.get("phoneNumber") or "unknown"
    is_active = str(payload.get("isActive", "true")).lower() != "false"
    log_event("call.received", call_id=session_id, detail=f"caller={caller} active={is_active}")

    # Resume the paused run belonging to this call session, if any.
    run = None
    if session_id:
        waiting_runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.status == "waiting_input", WorkflowRun.current_node.isnot(None))
            .order_by(WorkflowRun.started_at.desc())
            .limit(25)
            .all()
        )
        for candidate in waiting_runs:
            if (candidate.variables or {}).get("_session_id") == session_id:
                run = candidate
                break

    if run is not None:
        input_variables = {}
        if payload.get("recordingUrl"):
            input_variables["recording_url"] = payload["recordingUrl"]
        if payload.get("dtmf"):
            input_variables["dtmf"] = payload["dtmf"]
        engine = get_engine(db)
        run = engine.resume(run, input_variables)
        conversation = conversation_service.get_conversation(db, run.conversation_id) if run.conversation_id else None
        if conversation:
            _sync_conversation_from_run(db, conversation, run)
        if run.status == "completed" and conversation:
            conversation_service.complete_conversation(db, conversation)
        return {"actions": _run_actions(run), "run_id": run.id, "status": run.status}

    # ...or start a new call session.
    if not is_active:
        return {"actions": []}

    workflow = _find_enabled_workflow(db, "incoming_call")
    if not workflow:
        return {"actions": [{"action": "Say", "text": "Bridge is not configured for calls yet."}]}

    conversation = conversation_service.get_or_create_conversation(
        db, channel="voice", from_number=caller, to_number=payload.get("destinationNumber"),
        session_id=session_id, workflow=workflow,
    )
    engine = get_engine(db)
    run = engine.start_run(
        workflow,
        variables={"caller": caller, "_conversation_id": conversation.id, "_session_id": session_id},
        conversation_id=conversation.id,
    )
    run = engine.resume(run)
    _sync_conversation_from_run(db, conversation, run)
    if run.status == "completed":
        conversation_service.complete_conversation(db, conversation)
    return {"actions": _run_actions(run), "run_id": run.id, "status": run.status}


# ------------------------------------------------------------------ helpers
async def _parse(request: Request) -> dict:
    """AT sends form-encoded data; accept JSON too for tests/tools."""
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        try:
            return await request.json() or {}
        except Exception:
            return {}
    form = await request.form()
    return {k: v for k, v in form.items()}


def _run_actions(run: WorkflowRun) -> list[dict]:
    """Reconstruct caller-facing actions from the run's execution history."""
    actions: list[dict] = []
    for event in run.events:
        for action in event.detail.get("actions", []):
            actions.append(action)
    return actions


def _sync_conversation_from_run(db: Session, conversation, run: WorkflowRun) -> None:
    """Mirror interesting run variables into the conversation timeline."""
    variables = run.variables or {}
    transcript = variables.get("transcript")
    translation = variables.get("translation")
    if transcript:
        conversation_service.add_message(
            db, conversation, role="user", channel=conversation.channel,
            content=str(transcript), language=variables.get("source_language"),
        )
    if translation:
        conversation_service.add_message(
            db, conversation, role="system", channel=conversation.channel,
            content=str(translation), translated_content=str(translation),
            language=variables.get("target_language"),
        )
    elif variables.get("sms_sent_to") and not transcript:
        conversation_service.add_message(
            db, conversation, role="system", channel="sms",
            content="SMS delivered", meta={"to": variables.get("sms_sent_to")},
        )
