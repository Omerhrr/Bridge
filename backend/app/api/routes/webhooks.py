"""Telecom webhooks (spec sections 25/32/45).

    POST /api/v1/webhooks/africastalking/voice
    POST /api/v1/webhooks/africastalking/sms

Events are mapped into workflow triggers. Duplicate deliveries are ignored
via the provider event id (idempotency, spec section 45). Webhook payloads
are form-encoded for Africa's Talking.
"""
from typing import Annotated, Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger, log_event, new_correlation_id
from app.modules.ai.service import get_ai_service
from app.modules.communications.models import Call
from app.modules.communications.service import get_communication_service
from app.modules.messaging.service import MessagingService
from app.modules.workflows.engine import WorkflowEngine
from app.modules.workflows.service import WorkflowService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("bridge.webhooks")


async def _get_service(db: AsyncSession) -> WorkflowService:
    engine = WorkflowEngine(db, get_ai_service(), await get_communication_service(db))
    return WorkflowService(db, engine)


@router.post("/africastalking/sms")
async def africastalking_sms(
    db: Annotated[AsyncSession, Depends(get_db)],
    background: BackgroundTasks,
    from_: Annotated[str, Form(alias="from")] = "",
    to: str = Form(""),
    text: str = Form(""),
    id: str = Form(""),
    date: str = Form(""),
) -> dict:
    """Incoming SMS delivery callback.

    The message is logged and acknowledged right away; the workflow (which
    may call the AI provider several times) runs after the response is sent.
    """
    correlation = new_correlation_id()
    log_event(logger, "sms.received", correlation_id=correlation, sender=from_, to=to, provider="africastalking")

    service = await _get_service(db)
    # Idempotency (spec section 45): AT retries deliveries it thinks failed.
    if id and await service.sms_event_seen(id):
        log_event(logger, "webhook.duplicate_ignored", provider_message_id=id)
        return {"status": "duplicate_ignored", "run_id": None}

    # Record the inbound message first so the Messages page shows it before
    # any replies the workflow sends.
    inbound = await MessagingService(db, None, None).log_inbound(
        from_, to, text, provider_message_id=id or None,
    )
    payload = {"from": from_, "called": to, "text": text, "event_id": id}

    if settings.sms_background_processing:
        await db.commit()  # make the inbound record (and its id) visible to retries
        background.add_task(_process_sms_in_background, payload, inbound.id)
        return {"status": "accepted", "run_id": None, "message_id": inbound.id}

    run = await _dispatch_sms(service, payload)
    if run is None:
        return {"status": "no_matching_workflow", "run_id": None}
    inbound.run_id = run.id
    return {"status": run.status.value, "run_id": run.id}


async def _dispatch_sms(service: WorkflowService, payload: dict):
    return await service.dispatch_telecom_event(
        trigger_type="incoming_sms",
        payload=payload,
        channel="sms",
        a_number=payload["from"],
        b_number=payload["called"],
        idempotency_key=payload["event_id"] or None,
    )


async def _process_sms_in_background(payload: dict, inbound_id: int) -> None:
    from app.core.database import async_session_factory
    from app.modules.messaging.models import MessageLog

    async with async_session_factory() as session:
        try:
            run = await _dispatch_sms(await _get_service(session), payload)
            inbound = await session.get(MessageLog, inbound_id)
            if inbound is not None and run is not None:
                inbound.run_id = run.id
            await session.commit()
            log_event(logger, "sms.processed", run_id=run.id if run else None,
                      status=run.status.value if run else "no_matching_workflow")
        except Exception:
            await session.rollback()
            logger.exception("sms.processing_failed")


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
    # returned as XML, not wrapped in a JSON object.
    if run is None:
        return _voice_xml(say="No workflow is active. Goodbye.")

    # A Play Audio (or Text to Speech + Play Voice) node sets audio_url; a
    # Play Text or Translate node sets translation. Either is what the
    # workflow actually wants the caller to hear on this turn.
    audio_url = str(run.variables.get("audio_url", "") or "")
    translation = str(run.variables.get("translation", "") or "")
    if audio_url and not audio_url.startswith("stub://"):
        return _voice_xml(play=audio_url)
    return _voice_xml(say=translation or "Thank you for calling Bridge.")


def _voice_xml(say: str | None = None, play: str | None = None) -> Response:
    if play:
        attr = xml_escape(play, {'"': "&quot;"})
        action = f'<Play url="{attr}"/>'
    else:
        action = f"<Say>{xml_escape(say or '')}</Say>"
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response>{action}</Response>'
    return Response(content=body, media_type="application/xml")


@router.get("/whatsapp")
async def whatsapp_verify(db: Annotated[AsyncSession, Depends(get_db)], request: Request) -> Response:
    """Meta's webhook verification handshake: when a webhook URL is entered
    in the Meta App dashboard, Meta sends this GET once and expects the
    `hub.challenge` value echoed back verbatim if the verify token matches
    the one saved on the Settings page."""
    from app.modules.communications.whatsapp_config import get_whatsapp_credentials

    _phone_number_id, _access_token, verify_token = await get_whatsapp_credentials(db)
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and verify_token
        and params.get("hub.verify_token") == verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")


@router.post("/whatsapp")
async def whatsapp_incoming(db: Annotated[AsyncSession, Depends(get_db)], request: Request,
                            background: BackgroundTasks) -> dict:
    """Incoming WhatsApp message (Meta Cloud API webhook).

    Meta also posts status callbacks (sent/delivered/read) and non-text
    message types on this same URL; those are acknowledged and ignored, only
    an actual inbound text message triggers a workflow.
    """
    body: dict = await request.json()
    correlation = new_correlation_id()

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {}) or {}
            phone_number_id = (value.get("metadata") or {}).get("phone_number_id", "")
            for message in value.get("messages", []) or []:
                if message.get("type") != "text":
                    continue  # images/audio/interactive replies: out of scope for the hackathon MVP
                from_ = message.get("from", "")
                text = (message.get("text") or {}).get("body", "")
                message_id = message.get("id", "")
                log_event(logger, "whatsapp.received", correlation_id=correlation, sender=from_,
                          to=phone_number_id, provider="whatsapp")

                service = await _get_service(db)
                if message_id and await service.sms_event_seen(message_id):
                    log_event(logger, "webhook.duplicate_ignored", provider_message_id=message_id)
                    continue

                from app.modules.messaging.service import MessagingService

                inbound = await MessagingService(db, None, None).log_inbound(
                    from_, phone_number_id, text, provider_message_id=message_id or None,
                )
                payload = {"from": from_, "called": phone_number_id, "text": text, "event_id": message_id}
                await db.commit()
                background.add_task(_process_whatsapp_in_background, payload, inbound.id)

    return {"status": "accepted"}


async def _process_whatsapp_in_background(payload: dict, inbound_id: int) -> None:
    from app.core.database import async_session_factory
    from app.modules.messaging.models import MessageLog

    async with async_session_factory() as session:
        try:
            service = await _get_service(session)
            run = await service.dispatch_telecom_event(
                trigger_type="incoming_whatsapp",
                payload=payload,
                channel="whatsapp",
                a_number=payload["from"],
                b_number=payload["called"],
                idempotency_key=payload["event_id"] or None,
            )
            inbound = await session.get(MessageLog, inbound_id)
            if inbound is not None and run is not None:
                inbound.run_id = run.id
            await session.commit()
            log_event(logger, "whatsapp.processed", run_id=run.id if run else None,
                      status=run.status.value if run else "no_matching_workflow")
        except Exception:
            await session.rollback()
            logger.exception("whatsapp.processing_failed")


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
        # waiting to consume the next callback; always close the session so
        # Africa's Talking does not hold it open until timeout.
        prefix = "END"
    else:
        # Failed or otherwise unfinished runs always close the session.
        screen = "An error occurred while processing your request."
        prefix = "END"
    return Response(f"{prefix} {screen}", media_type="text/plain")
