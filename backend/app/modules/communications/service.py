"""Communication service facade (spec section 24).

Workflow nodes never talk to a telecom provider directly:

    Workflow Node -> Communication Service -> Provider Adapter -> Africa's Talking
"""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.communications.airtime import AirtimeProvider, get_airtime_provider
from app.modules.communications.sms import SMSProvider, get_sms_provider
from app.modules.communications.voice import VoiceProvider, get_voice_provider
from app.modules.communications.whatsapp import WhatsAppProvider, get_whatsapp_provider


@dataclass
class CommunicationService:
    voice: VoiceProvider
    sms: SMSProvider
    airtime: AirtimeProvider
    whatsapp: WhatsAppProvider

    @property
    def provider_name(self) -> str:
        return getattr(self.voice, "provider", "stub")


async def get_communication_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommunicationService:
    """WhatsApp credentials live in the database (Settings page), entered by
    the business owner rather than set as backend environment variables, so
    building the WhatsApp provider needs a session; the other providers stay
    environment-configured for now."""
    from app.modules.communications.whatsapp_config import get_whatsapp_credentials

    phone_number_id, access_token, _verify_token = await get_whatsapp_credentials(db)
    return CommunicationService(
        voice=get_voice_provider(),
        sms=get_sms_provider(),
        airtime=get_airtime_provider(),
        whatsapp=get_whatsapp_provider(phone_number_id, access_token),
    )
