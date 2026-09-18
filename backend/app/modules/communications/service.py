"""Communication service — the telecom facade used by workflow nodes."""

from functools import lru_cache

from app.core.config import get_settings
from app.modules.communications.africastalking import AfricaTalkingProvider
from app.modules.communications.mock import MockSMSProvider, MockVoiceProvider


class CommunicationService:
    def __init__(self, voice_provider, sms_provider):
        self.voice = voice_provider
        self.sms_provider = sms_provider

    def make_call(self, to: str, from_number: str | None = None) -> dict:
        return self.voice.make_call(to, from_number=from_number)

    def collect_speech(self, prompt: str, timeout: int = 10) -> dict:
        return self.voice.collect_speech(prompt, timeout=timeout)

    def send_sms(self, to: str, message: str, conversation_id: int | None = None) -> dict:
        from app.core.logging import log_event

        result = self.sms_provider.send_sms(to, message)
        log_event(
            "sms.sent",
            conversation_id=conversation_id,
            detail=f"to={to} status={result.get('status')}",
        )
        return result


@lru_cache
def get_communication_service() -> CommunicationService:
    settings = get_settings()
    if settings.comms_provider == "africastalking" and settings.at_api_key:
        provider = AfricaTalkingProvider()
        return CommunicationService(voice_provider=provider, sms_provider=provider)
    return CommunicationService(voice_provider=MockVoiceProvider(), sms_provider=MockSMSProvider())
