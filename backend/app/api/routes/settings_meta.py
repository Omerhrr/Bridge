"""Settings/status endpoint: provider configuration status (spec section 32).

Never exposes secrets - only booleans and non-sensitive identifiers.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.dependencies import DbSession
from app.core.config import settings
from app.modules.communications.whatsapp_config import get_whatsapp_credentials, save_whatsapp_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderStatus(BaseModel):
    telecom: dict
    whatsapp: dict
    ai: dict
    environment: str


@router.get("/providers", response_model=ProviderStatus)
async def providers(db: DbSession) -> ProviderStatus:
    phone_number_id, access_token, _verify_token = await get_whatsapp_credentials(db)
    wa_configured = bool(phone_number_id and access_token)
    return ProviderStatus(
        telecom={
            "provider": "africastalking" if settings.at_configured else "stub",
            "configured": settings.at_configured,
            "sandbox": settings.at_sandbox,
            "phone_number": settings.at_phone_number or None,
            "sender_id": settings.at_sender_id or None,
            "shortcode": settings.at_shortcode or None,
        },
        whatsapp={
            "provider": "whatsapp" if wa_configured else "stub",
            "configured": wa_configured,
            "phone_number_id": phone_number_id or None,
        },
        ai={
            "provider": settings.ai_provider_resolved if settings.ai_configured else "stub",
            "configured": settings.ai_configured,
            "model": settings.ai_chat_model if settings.ai_configured else None,
        },
        environment=settings.environment,
    )


# ------------------------------------------------------------- WhatsApp config
class WhatsAppConfigIn(BaseModel):
    phone_number_id: str = Field("", max_length=64)
    verify_token: str = Field("", max_length=128)
    # Blank/omitted keeps whatever token is already saved, so the form can be
    # resaved (e.g. just to change the phone number id) without re-pasting it.
    access_token: str | None = Field(None, max_length=4000)


class WhatsAppConfigOut(BaseModel):
    phone_number_id: str
    verify_token: str
    has_access_token: bool
    configured: bool


@router.get("/whatsapp", response_model=WhatsAppConfigOut)
async def get_whatsapp_config(db: DbSession) -> WhatsAppConfigOut:
    phone_number_id, access_token, verify_token = await get_whatsapp_credentials(db)
    return WhatsAppConfigOut(
        phone_number_id=phone_number_id, verify_token=verify_token,
        has_access_token=bool(access_token), configured=bool(phone_number_id and access_token),
    )


@router.put("/whatsapp", response_model=WhatsAppConfigOut)
async def update_whatsapp_config(data: WhatsAppConfigIn, db: DbSession) -> WhatsAppConfigOut:
    await save_whatsapp_settings(
        db, phone_number_id=data.phone_number_id, access_token=data.access_token,
        verify_token=data.verify_token,
    )
    await db.commit()
    return await get_whatsapp_config(db)
