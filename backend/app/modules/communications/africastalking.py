"""Africa's Talking provider adapter.

Implements the voice/SMS provider interfaces against the AT REST API
(https://developers.africastalking.com). Activated only when credentials are
configured (``BRIDGE_COMMS_PROVIDER=africastalking`` + username/api key);
otherwise the mock provider keeps the whole platform usable offline.
"""

import httpx

from app.core.config import get_settings
from app.core.logging import log_event


class AfricaTalkingProvider:
    name = "africastalking"

    def __init__(self) -> None:
        settings = get_settings()
        self.username = settings.at_username
        self.api_key = settings.at_api_key
        self.sender_id = settings.at_sender_id
        self.base_url = settings.at_base_url.rstrip("/")

    # ------------------------------------------------------------- internals
    def _headers(self) -> dict:
        return {
            "apiKey": self.api_key or "",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ SMS
    def send_sms(self, to: str, message: str, from_number: str | None = None) -> dict:
        sender = from_number or self.sender_id
        payload = {"username": self.username, "to": to, "message": message}
        if sender:
            payload["from"] = sender
        try:
            response = httpx.post(
                f"{self.base_url}/messaging",
                data=payload,
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
            body = response.json()
            recipients = (
                body.get("SMSMessageData", {}).get("Recipients", [{}])
            )
            return {
                "provider": self.name,
                "message_id": recipients[0].get("messageId") if recipients else None,
                "status": "sent",
                "to": to,
            }
        except httpx.HTTPError as exc:
            log_event("sms.failed", level=40, detail=str(exc))
            return {"provider": self.name, "status": "failed", "error": str(exc), "to": to}

    # ---------------------------------------------------------------- Voice
    def make_call(self, to: str, from_number: str | None = None) -> dict:
        payload = {
            "username": self.username,
            "to": to,
            # The callback URL is served by our own voice webhook route.
            "callBackUrl": "/webhooks/africastalking/voice",
        }
        if from_number:
            payload["from"] = from_number
        try:
            response = httpx.post(
                "https://api.africastalking.com/version1/voice/call",
                data=payload,
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
            return {"provider": self.name, "status": "queued", "to": to}
        except httpx.HTTPError as exc:
            log_event("call.failed", level=40, detail=str(exc))
            return {"provider": self.name, "status": "failed", "error": str(exc), "to": to}

    def collect_speech(self, prompt: str, timeout: int = 10) -> dict:
        # In AT voice flows, speech collection is expressed as a GetSpeech
        # action returned by the webhook — nothing to call proactively.
        return {"provider": self.name, "action": "GetSpeech", "prompt": prompt, "timeout": timeout}
