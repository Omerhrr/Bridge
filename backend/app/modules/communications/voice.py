"""Voice provider interface and implementations (spec sections 24-25)."""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.comms.voice")


@dataclass
class CallResult:
    call_id: str
    status: str = "started"
    simulated: bool = False
    provider: str = "stub"


class VoiceProvider:
    """Interface: voice call control through a telecom provider."""

    provider: str = "stub"

    async def make_call(self, to: str, from_number: str | None = None) -> CallResult:
        raise NotImplementedError


class StubVoiceProvider(VoiceProvider):
    """Development provider: simulates call placement."""

    async def make_call(self, to: str, from_number: str | None = None) -> CallResult:
        call_id = f"stub-call-{abs(hash((to, from_number))) % 10_000_000}"
        log_event(logger, "call.started", provider="stub", to=to, simulated=True)
        return CallResult(call_id=call_id, status="simulated", simulated=True)


class AfricaTalkingVoiceProvider(VoiceProvider):
    """Africa's Talking Voice integration."""

    provider = "africastalking"

    async def make_call(self, to: str, from_number: str | None = None) -> CallResult:
        if not settings.at_configured:
            raise RuntimeError("Africa's Talking credentials are not configured")
        username = settings.at_username
        host = (
            "https://api.sandbox.africastalking.com"
            if settings.at_sandbox
            else "https://api.africastalking.com"
        )
        payload = {
            "username": username,
            "to": to,
            "from": from_number or settings.at_phone_number,
            "callerId": from_number or settings.at_phone_number,
        }
        headers = {
            "apiKey": settings.at_api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{host}/version1/call", data=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        entries = data.get("entries") or [{}]
        log_event(logger, "call.started", provider="africastalking", to=to)
        return CallResult(call_id=str(entries[0].get("sessionId", "")), provider="africastalking")


def get_voice_provider() -> VoiceProvider:
    if settings.at_configured:
        return AfricaTalkingVoiceProvider()
    return StubVoiceProvider()
