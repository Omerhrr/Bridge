"""Settings/status endpoint: provider configuration status (spec section 32).

Never exposes secrets - only booleans and non-sensitive identifiers.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderStatus(BaseModel):
    telecom: dict
    ai: dict
    environment: str


@router.get("/providers", response_model=ProviderStatus)
async def providers() -> ProviderStatus:
    return ProviderStatus(
        telecom={
            "provider": "africastalking" if settings.at_configured else "stub",
            "configured": settings.at_configured,
            "sandbox": settings.at_sandbox,
            "phone_number": settings.at_phone_number or None,
            "sender_id": settings.at_sender_id or None,
        },
        ai={
            "provider": settings.ai_provider if settings.ai_configured else "stub",
            "configured": settings.ai_configured,
        },
        environment=settings.environment,
    )
