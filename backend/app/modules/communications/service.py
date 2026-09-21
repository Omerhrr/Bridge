"""Communication service facade (spec section 24).

Workflow nodes never talk to a telecom provider directly:

    Workflow Node -> Communication Service -> Provider Adapter -> Africa's Talking
"""
from dataclasses import dataclass

from app.modules.communications.airtime import AirtimeProvider, get_airtime_provider
from app.modules.communications.sms import SMSProvider, get_sms_provider
from app.modules.communications.voice import VoiceProvider, get_voice_provider


@dataclass
class CommunicationService:
    voice: VoiceProvider
    sms: SMSProvider
    airtime: AirtimeProvider

    @property
    def provider_name(self) -> str:
        return getattr(self.voice, "provider", "stub")


def get_communication_service() -> CommunicationService:
    return CommunicationService(
        voice=get_voice_provider(),
        sms=get_sms_provider(),
        airtime=get_airtime_provider(),
    )
