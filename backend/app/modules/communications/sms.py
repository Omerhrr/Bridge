"""SMS provider interface and implementations (spec sections 24-25)."""
from dataclasses import dataclass

import httpx

from app.core.config import clean_sender_id, settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.comms.sms")


@dataclass
class SmsSendResult:
    message_id: str
    status: str = "sent"
    simulated: bool = False
    provider: str = "stub"


class SMSProvider:
    """Interface: send an SMS through a telecom provider."""

    provider: str = "stub"

    async def send_sms(self, to: str, text: str, sender_id: str | None = None) -> SmsSendResult:
        raise NotImplementedError


class StubSMSProvider(SMSProvider):
    """Development provider: simulates delivery so workflows can be tested
    end to end without telecom credentials."""

    async def send_sms(self, to: str, text: str, sender_id: str | None = None) -> SmsSendResult:
        message_id = f"stub-{abs(hash((to, text))) % 10_000_000}"
        log_event(logger, "sms.sent", provider="stub", to=to, simulated=True)
        return SmsSendResult(message_id=message_id, status="simulated", simulated=True)


class AfricaTalkingSMSProvider(SMSProvider):
    """Africa's Talking SMS integration (https://developers.africastalking.com)."""

    provider = "africastalking"

    async def send_sms(self, to: str, text: str, sender_id: str | None = None) -> SmsSendResult:
        if not settings.at_configured:
            raise RuntimeError("Africa's Talking credentials are not configured")
        host = (
            "https://api.sandbox.africastalking.com"
            if settings.at_sandbox
            else "https://api.africastalking.com"
        )
        # Whatever produced this sender id (workflow config, a saved
        # shortcode, or a webhook's own reported "to" value) might not be a
        # clean token, and Africa's Talking rejects anything else outright.
        sender = clean_sender_id(sender_id) or clean_sender_id(settings.at_sender_id)
        try:
            return await self._post(host, to, text, sender)
        except _InvalidSenderId:
            if not sender:
                raise
            # The id is well-formed but the account itself doesn't have it
            # provisioned as an SMS sender (a common sandbox gap: a shortcode
            # set up for USSD/Voice isn't automatically valid for SMS "from").
            # Retry once without it so the reply still reaches the person,
            # rather than silently failing every message until that's fixed
            # on the Africa's Talking dashboard.
            log_event(
                logger, "sms.sender_id_rejected", provider="africastalking",
                to=to, rejected_sender=sender,
            )
            return await self._post(host, to, text, sender=None)

    async def _post(self, host: str, to: str, text: str, sender: str | None) -> SmsSendResult:
        payload: dict = {"username": settings.at_username, "to": to, "message": text}
        if sender:
            payload["from"] = sender
        headers = {
            "apiKey": settings.at_api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{host}/version1/messaging", data=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        entry = (data.get("SMSMessageData", {}).get("Recipients") or [{}])[0]
        # AT answers 201 even when it rejects the message; the real outcome is
        # the per-recipient statusCode (100 processed, 101 sent, 102 queued).
        if entry.get("statusCode") not in (100, 101, 102):
            reason = entry.get("status") or data.get("SMSMessageData", {}).get("Message") or data
            if "invalidsenderid" in str(reason).replace(" ", "").lower():
                raise _InvalidSenderId(str(reason))
            raise RuntimeError(f"Africa's Talking rejected the SMS: {reason}")
        log_event(logger, "sms.sent", provider="africastalking", to=to, messageId=entry.get("messageId"))
        return SmsSendResult(
            message_id=str(entry.get("messageId", "")),
            status=str(entry.get("status", "sent")).lower(),
            provider="africastalking",
        )


class _InvalidSenderId(RuntimeError):
    """Internal signal: Africa's Talking rejected the sender id/shortcode
    itself, distinct from any other delivery failure."""


def get_sms_provider() -> SMSProvider:
    if settings.at_configured:
        return AfricaTalkingSMSProvider()
    return StubSMSProvider()
