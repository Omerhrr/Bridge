"""Airtime provider interface and implementations (hackathon track: Airtime API).

Used for customer incentives: loyalty rewards, referrals, promotions and
engagement campaigns. Workflow nodes reach airtime through the
CommunicationService facade, never directly.
"""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("bridge.comms.airtime")


@dataclass
class AirtimeSendResult:
    transaction_id: str
    status: str = "sent"
    simulated: bool = False
    provider: str = "stub"


class AirtimeProvider:
    """Interface: send airtime to a phone number."""

    async def send_airtime(self, to: str, amount: str, currency_code: str) -> AirtimeSendResult:
        raise NotImplementedError


class StubAirtimeProvider(AirtimeProvider):
    """Development provider: simulates airtime top-ups so reward workflows
    can be tested end to end without telecom credentials."""

    async def send_airtime(self, to: str, amount: str, currency_code: str) -> AirtimeSendResult:
        transaction_id = f"stub-airtime-{abs(hash((to, amount, currency_code))) % 10_000_000}"
        log_event(
            logger, "airtime.sent", provider="stub", to=to,
            amount=f"{currency_code} {amount}", simulated=True,
        )
        return AirtimeSendResult(transaction_id=transaction_id, status="simulated", simulated=True)


class AfricaTalkingAirtimeProvider(AirtimeProvider):
    """Africa's Talking Airtime API integration.

    POST /version1/airtime with a JSON body:
        {"username": "...", "recipients": [{"phoneNumber": "...",
         "currencyCode": "KES", "amount": "10"}]}
    """

    async def send_airtime(self, to: str, amount: str, currency_code: str) -> AirtimeSendResult:
        if not settings.at_configured:
            raise RuntimeError("Africa's Talking credentials are not configured")
        host = (
            "https://api.sandbox.africastalking.com"
            if settings.at_sandbox
            else "https://api.africastalking.com"
        )
        payload = {
            "username": settings.at_username,
            "recipients": [
                {"phoneNumber": to, "currencyCode": currency_code, "amount": str(amount)}
            ],
        }
        headers = {
            "apiKey": settings.at_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{host}/version1/airtime", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if not data.get("numSent"):
            raise RuntimeError(f"Airtime request rejected: {data.get('errorMessage') or data}")
        entry = (data.get("responses") or [{}])[0]
        transaction_id = str(
            entry.get("transactionId")
            or data.get("requestId")
            or f"at-{abs(hash((to, amount))) % 10_000_000}"
        )
        log_event(
            logger, "airtime.sent", provider="africastalking", to=to,
            amount=f"{currency_code} {amount}", transaction_id=transaction_id,
        )
        return AirtimeSendResult(
            transaction_id=transaction_id,
            status=str(entry.get("status", "sent")).lower(),
            provider="africastalking",
        )


def get_airtime_provider() -> AirtimeProvider:
    if settings.at_configured:
        return AfricaTalkingAirtimeProvider()
    return StubAirtimeProvider()
