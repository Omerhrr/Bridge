"""Health and registry endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.modules.workflows.registry import registry_dump

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "bridge-api",
        "version": "0.1.0",
        "environment": settings.environment,
        "comms_provider": settings.comms_provider if settings.at_api_key else "mock",
        "ai_provider": settings.ai_provider,
    }


@router.get("/api/node-types")
def node_types() -> list[dict]:
    """The node catalogue powering the Vue Flow palette and inspector."""
    return registry_dump()
