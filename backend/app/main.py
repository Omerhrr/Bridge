"""Bridge — FastAPI application entrypoint (modular monolith, spec §14)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import conversations, health, runs, stats, webhooks, workflows
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import get_logger, log_event

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log_event("bridge.started")
    yield


settings = get_settings()

app = FastAPI(
    title="Bridge API",
    description=(
        "Telecom Communication Bridge — a visual communication automation platform "
        "that uses telecommunications and AI to connect people across language and "
        "connectivity barriers without requiring an app or internet connection."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# The Nuxt dashboard is the only browser client (spec §4.1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(conversations.router)
app.include_router(stats.router)
app.include_router(webhooks.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": "bridge-api", "docs": "/docs", "health": "/api/health"}
