"""Bridge FastAPI application entrypoint (spec section 14)."""
from contextlib import asynccontextmanager

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger, log_event, setup_logging
from app.api.routes import (
    auth,
    communications,
    conversations,
    dashboard,
    runs,
    settings_meta,
    webhooks,
    workflows,
)

setup_logging()
_http_logger = get_logger("bridge.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import init_db
    from app.seed import seed_demo_data

    await init_db()
    await seed_demo_data()
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    description="Communication transformation platform: telecom events in, transformations applied, telecom responses out.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"


@app.middleware("http")
async def log_webhook_timing(request: Request, call_next):
    """Log status and latency of telecom webhooks (visible in Render logs) —
    USSD gateways time out after a few seconds, so this is the first thing
    to check when a session shows the provider's generic error screen."""
    if "/webhooks/" not in request.url.path:
        return await call_next(request)
    started = time.perf_counter()
    response = await call_next(request)
    log_event(
        _http_logger, "webhook.responded", path=request.url.path,
        status=response.status_code, ms=round((time.perf_counter() - started) * 1000),
    )
    return response

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(workflows.router, prefix=API_PREFIX)
app.include_router(runs.router, prefix=API_PREFIX)
app.include_router(conversations.router, prefix=API_PREFIX)
app.include_router(communications.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(settings_meta.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "telecom_provider": "africastalking" if settings.at_configured else "stub",
        "ai_provider": settings.ai_provider if settings.ai_configured else "stub",
    }


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"app": settings.app_name, "docs": "/docs", "api": API_PREFIX}
