"""WhatsApp provider: Meta's WhatsApp Cloud API (https://developers.facebook.com/docs/whatsapp).

A separate channel from Africa's Talking: a business connects its own
WhatsApp Business number in Meta's developer console (a phone number id and
a permanent access token) and enters them on Bridge's Settings page (stored
encrypted in the database, see ``whatsapp_config.py``) rather than as
backend environment variables, so the owner can (re)configure it themselves
without a redeploy. Bridge never routes WhatsApp traffic through Africa's
Talking.
"""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.comms.whatsapp")

WA_API_VERSION = "v21.0"


@dataclass
class WhatsAppSendResult:
    message_id: str
    status: str = "sent"
    simulated: bool = False
    provider: str = "stub"


class WhatsAppProvider:
    """Interface: send a WhatsApp message through a provider."""

    provider: str = "stub"

    async def send_text(self, to: str, text: str) -> WhatsAppSendResult:
        raise NotImplementedError


class StubWhatsAppProvider(WhatsAppProvider):
    """Development provider: simulates delivery so workflows can be built and
    tested before a real WhatsApp Business number is connected."""

    async def send_text(self, to: str, text: str) -> WhatsAppSendResult:
        message_id = f"stub-wa-{abs(hash((to, text))) % 10_000_000}"
        log_event(logger, "whatsapp.sent", provider="stub", to=to, simulated=True)
        return WhatsAppSendResult(message_id=message_id, status="simulated", simulated=True)


class MetaWhatsAppProvider(WhatsAppProvider):
    """Meta WhatsApp Cloud API integration, bound to one business's own
    phone number id and access token (loaded from the database, not env
    vars, so each Bridge deployment can serve a different WhatsApp number
    without a redeploy)."""

    provider = "whatsapp"

    def __init__(self, phone_number_id: str, access_token: str):
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    async def send_text(self, to: str, text: str) -> WhatsAppSendResult:
        if not (self.phone_number_id and self.access_token):
            raise RuntimeError("WhatsApp (Meta Cloud API) credentials are not configured")
        url = f"https://graph.facebook.com/{WA_API_VERSION}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data: dict = {}
            try:
                data = resp.json()
            except ValueError:
                pass
            if resp.status_code >= 400:
                reason = (data.get("error") or {}).get("message") or resp.text or f"HTTP {resp.status_code}"
                raise RuntimeError(f"WhatsApp rejected the message: {reason}")
        message_id = ((data.get("messages") or [{}])[0]).get("id", "")
        log_event(logger, "whatsapp.sent", provider="whatsapp", to=to, messageId=message_id)
        return WhatsAppSendResult(message_id=message_id, status="sent", provider="whatsapp")


def get_whatsapp_provider(phone_number_id: str = "", access_token: str = "") -> WhatsAppProvider:
    """Build the right provider for the credentials on hand. Falls back to
    `Settings.wa_*` (env vars) only when the database has nothing configured,
    so an existing env-var based deployment keeps working during the switch
    to database-backed settings."""
    phone_number_id = phone_number_id or settings.wa_phone_number_id
    access_token = access_token or settings.wa_access_token
    if phone_number_id and access_token:
        return MetaWhatsAppProvider(phone_number_id, access_token)
    return StubWhatsAppProvider()
