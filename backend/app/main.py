"""Bridge FastAPI application entrypoint (spec section 14)."""
from contextlib import asynccontextmanager

import time

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import require_user
from app.core.config import settings
from app.core.logging import get_logger, log_event, setup_logging
from app.api.routes import (
    api_keys,
    auth,
    communications,
    conversations,
    dashboard,
    knowledge,
    messaging,
    public,
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
    from app.seed import ensure_bridge_messenger, reset_interrupted_syncs, secure_default_accounts, seed_demo_data

    await init_db()
    await seed_demo_data()
    await ensure_bridge_messenger()
    await secure_default_accounts()
    await reset_interrupted_syncs()
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
async def public_assistant_cors(request: Request, call_next):
    """The main CORSMiddleware below is scoped to `settings.cors_origin_list`
    (the Bridge dashboard's own origin(s)). The public assistant endpoint is
    meant to be called from an arbitrary customer website, so it gets its
    own permissive CORS handling here rather than loosening CORS for the
    whole API. Runs before the main CORS middleware since it's added last
    (Starlette applies middleware in reverse-add order)."""
    if not request.url.path.startswith(f"{API_PREFIX}/public/"):
        return await call_next(request)
    origin = request.headers.get("origin", "*")
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Api-Key"
    response.headers["Vary"] = "Origin"
    return response


@app.middleware("http")
async def log_webhook_timing(request: Request, call_next):
    """Log status and latency of telecom webhooks (visible in Render logs):
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

# Public: sign-in, telecom webhooks, the health check, and the API-key
# authenticated assistant endpoint (auth handled inside the route itself).
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)
app.include_router(public.router, prefix=API_PREFIX)

# Everything else requires a signed-in user.
_protected = [Depends(require_user)]
for _router in (workflows.router, runs.router, conversations.router, communications.router,
                messaging.router, knowledge.router, dashboard.router, settings_meta.router,
                api_keys.router):
    app.include_router(_router, prefix=API_PREFIX, dependencies=_protected)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "telecom_provider": "africastalking" if settings.at_configured else "stub",
        "ai_provider": settings.ai_provider_resolved if settings.ai_configured else "stub",
    }


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"app": settings.app_name, "docs": "/docs", "api": API_PREFIX}
