"""Telecom provider abstractions (spec §24).

    Workflow Node -> Communication Service -> Provider Adapter -> Africa's Talking

The engine never contains Africa's Talking specifics; adapters implement
these interfaces, keeping the platform provider-independent.
"""

from typing import Protocol


class VoiceProvider(Protocol):
    def make_call(self, to: str, from_number: str | None = None) -> dict: ...

    def collect_speech(self, prompt: str, timeout: int = 10) -> dict: ...


class SMSProvider(Protocol):
    def send_sms(self, to: str, message: str, from_number: str | None = None) -> dict: ...
