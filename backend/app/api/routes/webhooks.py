"""Telecom webhooks (spec sections 25/32/45).

    POST /api/v1/webhooks/africastalking/voice
    POST /api/v1/webhooks/africastalking/sms

Events are mapped into workflow triggers. Duplicate deliveries are ignored
via the provider event id (idempotency, spec section 45). Webhook payloads
are form-encoded for Africa's Talking.
"""
from typing import Annotated, Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger, log_event, new_correlation_id
from app.modules.ai.service import get_ai_service
from app.modules.communications.models import Call
from app.modules.communications.service import get_communication_service
from app.modules.workflows.engine import WorkflowEngine
from app.modules.workflows.service import WorkflowService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("bridge.webhooks")


async def _get_service(db: AsyncSession) -> WorkflowService:
    engine = WorkflowEngine(db, get_ai_service(), get_communication_service())
    return WorkflowService(db, engine)


@router.post("/africastalking/sms")
async def africastalking_sms(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_: Annotated[str, Form(alias="from")] = "",
    to: str = Form(""),
    text: str = Form(""),
    id: str = Form(""),
    date: str = Form(""),
) -> dict:
    """Incoming SMS delivery callback."""
    correlation = new_correlation_id()
    log_event(logger, "sms.received", correlation_id=correlation, sender=from_, to=to, provider="africastalking")

    service = await _get_service(db)
    payload = {"from": from_, "called": to, "text": text, "event_id": id}
    run = await service.dispatch_telecom_event(
        trigger_type="incoming_sms",
        payload=payload,
        channel="sms",
        a_number=from_,
        b_number=to,
        idempotency_key=id or None,
    )
    if run is None:
        # Distinguish "we already processed this delivery" (idempotency,
        # spec section 45) from "nothing matched" for observability.
        duplicate = bool(id) and await service.sms_event_seen(id)
        status = "duplicate_ignored" if duplicate else "no_matching_workflow"
        return {"status": status, "run_id": None}
    return {"status": run.status.value, "run_id": run.id}


@router.post("/africastalking/voice")
async def africastalking_voice(
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    sessionId: str = Form(""),
    isActive: str = Form("1"),
    callerNumber: str = Form(""),
    destinationNumber: str = Form(""),
    direction: str = Form("inbound"),
    dtmfDigits: str = Form(""),
    recordingUrl: str = Form(""),
) -> Response:
    """Voice callback.

    Returns XML actions for the live voice loop; non-active (session end)
    callbacks only record the event. The full interactive STT/TTS loop is
    delivered in Phase 2 with a live Africa's Talking number.
    """
    correlation = new_correlation_id()
    log_event(
        logger, "call.received", correlation_id=correlation,
        session=sessionId, caller=callerNumber, is_active=isActive,
        recording_url=recordingUrl,
    )

    # Record the raw call for the calls history.
    call = Call(
        provider_call_id=sessionId or None,
        direction=direction or "inbound",
        from_number=callerNumber or None,
        to_number=destinationNumber or None,
        status="active" if isActive == "1" else "completed",
        meta=None,
    )
    db.add(call)
    await db.flush()

    if isActive != "1":
        # End-of-call notification: AT ignores the body, just acknowledge.
        return Response(status_code=200)

    service = await _get_service(db)
    payload = {
        "from": callerNumber,
        "called": destinationNumber,
        "session_id": sessionId,
        "recording_url": recordingUrl,
        "text": f"[voice session {sessionId}]" if recordingUrl else "",
    }
    run = await service.dispatch_telecom_event(
        trigger_type="incoming_call",
        payload=payload,
        channel="voice",
        a_number=callerNumber,
        b_number=destinationNumber,
    )
    # Africa's Talking reads the raw response body as Voice XML, so it must be
    # returned as XML — not wrapped in a JSON object.
    if run is None:
        return _voice_xml("No workflow is active. Goodbye.")

    translation = str(run.variables.get("translation", "") or "")
    return _voice_xml(translation or "Thank you for calling Bridge.")


def _voice_xml(say: str) -> Response:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><Response>'
        f"<Say>{xml_escape(say)}</Say>"
        "</Response>"
    )
    return Response(content=body, media_type="application/xml")


@router.post("/africastalking/ussd")
async def africastalking_ussd(
    db: Annotated[AsyncSession, Depends(get_db)],
    sessionId: str = Form(""),
    serviceCode: str = Form(""),
    phoneNumber: str = Form(""),
    text: str = Form(""),
) -> Response:
    """Africa's Talking USSD callback (hackathon track: USSD API).

    The reply body must start with `CON ` (keep the session open) or `END `
    (close the session). The workflow builds its screens with ussd_menu /
    ussd_end nodes, which set the `ussd_response` / `ussd_close` variables.
    """
    correlation = new_correlation_id()
    log_event(
        logger, "ussd.received", correlation_id=correlation,
        session=sessionId, phone=phoneNumber, service_code=serviceCode,
        text=text,
    )

    service = await _get_service(db)
    payload = {
        "session_id": sessionId,
        "service_code": serviceCode,
        "phone_number": phoneNumber,
        "text": text,
    }
    run = await service.dispatch_telecom_event(
        trigger_type="ussd_request",
        payload=payload,
        channel="ussd",
        a_number=phoneNumber,
        b_number=serviceCode,
    )
    if run is None:
        return Response(
            "END No service is available right now. Please try again later.",
            media_type="text/plain",
        )

    screen = str(run.variables.get("ussd_response") or "Thank you for using Bridge.")
    status_value = run.status.value
    if status_value == "waiting":
        # A menu screen was displayed; keep the session open.
        prefix = "CON"
    elif status_value == "completed":
        # A run that finished without an explicit ussd_end node has nothing
        # waiting to consume the next callback — always close the session so
        # Africa's Talking does not hold it open until timeout.
        prefix = "END"
    else:
        # Failed or otherwise unfinished runs always close the session.
        screen = "An error occurred while processing your request."
        prefix = "END"
    return Response(f"{prefix} {screen}", media_type="text/plain")
