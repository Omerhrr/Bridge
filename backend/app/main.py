from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import items

app = FastAPI(
    title="Bridge API",
    description="FastAPI backend for the Bridge project (Nuxt + Vue frontend).",
    version="0.1.0",
)

# Allow the Nuxt dev server (default http://localhost:3000) to call the API.
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

app.include_router(items.router, prefix="/api/items", tags=["items"])


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    """Simple liveness probe used by the frontend landing page."""
    return {"status": "ok", "service": "bridge-api", "version": "0.1.0"}
