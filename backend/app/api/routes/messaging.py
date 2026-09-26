"""Messaging, contacts and language endpoints.

    GET    /languages                 languages Bridge offers
    POST   /messages/send             send an SMS to one or many people, translated per recipient
    POST   /messages/translate        preview a translation without sending
    GET    /messages/log              unified inbound/outbound message log
    GET    /contacts                  contacts with their languages
    POST   /contacts                  create or update a contact
    PATCH  /contacts/{id}             edit name / language
    DELETE /contacts/{id}             remove a contact
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, or_, select

from app.api.dependencies import AiServiceDep, CommsServiceDep, DbSession
from app.core.config import settings
from app.modules.ai.languages import language_name, language_options, normalize_language
from app.modules.contacts.models import Contact
from app.modules.messaging.models import BridgeProfile, MessageLog
from app.modules.messaging.service import InvalidPhoneNumber, MessagingService, normalize_phone

router = APIRouter(tags=["messaging"])

MAX_RECIPIENTS = 100


# ---------------------------------------------------------------- languages
class LanguageOut(BaseModel):
    code: str
    name: str


@router.get("/languages", response_model=list[LanguageOut])
async def list_languages() -> list[LanguageOut]:
    return [LanguageOut(**item) for item in language_options()]


# ------------------------------------------------------------------ sending
class SendIn(BaseModel):
    recipients: list[str] = Field(min_length=1, max_length=MAX_RECIPIENTS)
    text: str = Field(min_length=1, max_length=1600)
    # "contact" = each recipient's saved language, "none" = no translation,
    # or a language code / name applied to everyone.
    language: str = "contact"
    sender: str | None = None

    @field_validator("language")
    @classmethod
    def _language(cls, value: str) -> str:
        if value in ("contact", "none", "auto"):
            return value
        code = normalize_language(value)
        if not code:
            raise ValueError(f"Unsupported language '{value}'")
        return code


class DeliveryOut(BaseModel):
    to: str
    status: str
    text: str
    original_text: str
    target_language: str | None = None
    source_language: str | None = None
    message_id: str | None = None
    error: str | None = None


class SendOut(BaseModel):
    sent: int
    failed: int
    results: list[DeliveryOut]


@router.post("/messages/send", response_model=SendOut)
async def send_messages(data: SendIn, db: DbSession, ai: AiServiceDep, comms: CommsServiceDep) -> SendOut:
    service = MessagingService(db, ai, comms)
    # De-duplicate while keeping order.
    recipients = list(dict.fromkeys(r.strip() for r in data.recipients if r.strip()))
    results = await service.broadcast(recipients, data.text, language_mode=data.language,
                                      sender=data.sender or None)
    failed = sum(1 for r in results if r.status == "failed")
    return SendOut(sent=len(results) - failed, failed=failed,
                   results=[DeliveryOut(**r.as_dict()) for r in results])


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=1600)
    language: str


class TranslateOut(BaseModel):
    text: str
    source_language: str | None
    target_language: str
    provider: str


@router.post("/messages/translate", response_model=TranslateOut)
async def preview_translation(data: TranslateIn, ai: AiServiceDep) -> TranslateOut:
    target = normalize_language(data.language)
    if not target:
        raise HTTPException(422, f"Unsupported language '{data.language}'")
    try:
        result = await ai.translation.translate(data.text, source="auto", target=target)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Translation failed: {exc}") from exc
    return TranslateOut(text=result.text, source_language=result.source,
                        target_language=result.target, provider=result.provider)


class MessageLogOut(BaseModel):
    id: int
    direction: str
    kind: str
    from_number: str | None
    to_number: str | None
    original_text: str | None
    text: str
    source_language: str | None
    target_language: str | None
    status: str
    error: str | None
    run_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/messages/log", response_model=list[MessageLogOut])
async def message_log(
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
    phone: str | None = None,
) -> list[MessageLogOut]:
    query = select(MessageLog).order_by(MessageLog.created_at.desc(), MessageLog.id.desc()).limit(limit)
    if phone:
        query = query.where(or_(MessageLog.from_number == phone, MessageLog.to_number == phone))
    result = await db.execute(query)
    return [MessageLogOut.model_validate(m) for m in result.scalars()]


# ----------------------------------------------------------------- contacts
class ContactOut(BaseModel):
    id: int
    phone_number: str
    name: str
    language: str | None
    language_name: str | None
    language_locked: bool
    partner_number: str | None
    message_count: int
    created_at: datetime


class ContactIn(BaseModel):
    phone_number: str
    name: str = ""
    language: str | None = None


class ContactPatch(BaseModel):
    name: str | None = None
    language: str | None = None


def _clean_language(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    code = normalize_language(value)
    if not code:
        raise HTTPException(422, f"Unsupported language '{value}'")
    return code


async def _contact_out(db, contact: Contact) -> ContactOut:
    profile = (await db.execute(
        select(BridgeProfile).where(BridgeProfile.phone_number == contact.phone_number)
    )).scalar_one_or_none()
    count = (await db.execute(
        select(func.count()).select_from(MessageLog).where(
            or_(MessageLog.from_number == contact.phone_number, MessageLog.to_number == contact.phone_number)
        )
    )).scalar_one()
    return ContactOut(
        id=contact.id, phone_number=contact.phone_number, name=contact.name or "",
        language=contact.language,
        language_name=language_name(contact.language) if contact.language else None,
        language_locked=bool(profile and profile.language_locked),
        partner_number=profile.partner_number if profile else None,
        message_count=count, created_at=contact.created_at,
    )


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(db: DbSession) -> list[ContactOut]:
    result = await db.execute(select(Contact).order_by(Contact.created_at.desc()).limit(500))
    return [await _contact_out(db, c) for c in result.scalars()]


@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def upsert_contact(data: ContactIn, db: DbSession) -> ContactOut:
    try:
        phone = normalize_phone(data.phone_number)
    except InvalidPhoneNumber as exc:
        raise HTTPException(422, str(exc)) from exc
    language = _clean_language(data.language)
    service = MessagingService(db, None, None)
    contact = await service.ensure_contact(phone)
    if data.name:
        contact.name = data.name.strip()
    if language:
        await service.set_language(phone, language, locked=True)
    await db.flush()
    return await _contact_out(db, contact)


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(contact_id: int, data: ContactPatch, db: DbSession) -> ContactOut:
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    if data.name is not None:
        contact.name = data.name.strip()
    if data.language is not None:
        language = _clean_language(data.language)
        service = MessagingService(db, None, None)
        profile = await service.get_profile(contact.phone_number)
        contact.language = language
        # Clearing the language hands it back to auto-detection.
        profile.language_locked = language is not None
    await db.flush()
    return await _contact_out(db, contact)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: int, db: DbSession) -> None:
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    await db.execute(delete(BridgeProfile).where(BridgeProfile.phone_number == contact.phone_number))
    await db.delete(contact)


# ------------------------------------------------------------ messaging info
class MessagingInfo(BaseModel):
    default_sender: str | None
    ai_provider: str
    ai_configured: bool
    sandbox: bool


@router.get("/messages/info", response_model=MessagingInfo)
async def messaging_info() -> MessagingInfo:
    return MessagingInfo(
        default_sender=settings.default_sms_sender,
        ai_provider=settings.ai_provider_resolved if settings.ai_configured else "stub",
        ai_configured=settings.ai_configured,
        sandbox=settings.at_sandbox,
    )
