"""API keys for the public Ask Assistant endpoint.

A key lets a website chatbot, or any other external integration, ask
questions against the business's knowledge base without a dashboard login.
Only a SHA-256 hash of the key is ever stored (it's a high-entropy random
token, not a user password, so a slow KDF isn't needed); the plaintext is
returned once, at creation, exactly like a typical third-party API key.
"""
import hashlib
import secrets
import time
from collections import deque
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import ApiKey

KEY_PREFIX = "brdg_"
# Requests allowed per key in the trailing window, so one runaway page (or a
# bad actor who finds the key in a site's page source) can't exhaust the AI
# provider's quota or the database. In-process only: fine for the single
# backend instance this hackathon deploys, resets on restart/across dynos.
RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 60

_usage: dict[int, deque] = {}


def generate_key() -> tuple[str, str, str]:
    """Return (plaintext_key, prefix_for_display, sha256_hash)."""
    raw = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    display_prefix = raw[: len(KEY_PREFIX) + 6]
    return raw, display_prefix, hash_key(raw)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def authenticate(session: AsyncSession, raw_key: str | None) -> ApiKey | None:
    """Resolve an active, non-revoked key; None for anything invalid."""
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return None
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(raw_key)))
    key = result.scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        return None
    return key


def check_rate_limit(key_id: int) -> bool:
    """True when the key is still under its per-minute request budget."""
    now = time.monotonic()
    window = _usage.setdefault(key_id, deque())
    while window and now - window[0] > RATE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        return False
    window.append(now)
    return True


async def touch(session: AsyncSession, key: ApiKey) -> None:
    key.last_used_at = datetime.now(timezone.utc)
    key.request_count += 1
    await session.flush()
