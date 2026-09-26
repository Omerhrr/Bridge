"""Manage API keys for the public Ask Assistant endpoint (dashboard-only,
requires a signed-in user).

    GET    /api-keys           list keys (never returns the plaintext)
    POST   /api-keys           create a key; the plaintext is returned ONCE
    DELETE /api-keys/{id}      revoke a key
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import DbSession
from app.modules.knowledge import apikeys
from app.modules.knowledge.models import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    revoked_at: datetime | None
    last_used_at: datetime | None
    request_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    # Only present in the response to the create call; never stored or shown again.
    key: str


class ApiKeyIn(BaseModel):
    name: str = Field("", max_length=255)


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(db: DbSession) -> list[ApiKeyOut]:
    from sqlalchemy import select

    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return [ApiKeyOut.model_validate(k) for k in result.scalars()]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(data: ApiKeyIn, db: DbSession) -> ApiKeyCreated:
    raw, prefix, key_hash = apikeys.generate_key()
    key = ApiKey(name=data.name.strip(), prefix=prefix, key_hash=key_hash)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyCreated(
        id=key.id, name=key.name, prefix=key.prefix, revoked_at=key.revoked_at,
        last_used_at=key.last_used_at, request_count=key.request_count,
        created_at=key.created_at, key=raw,
    )


@router.delete("/{key_id}", response_model=ApiKeyOut)
async def revoke_key(key_id: int, db: DbSession) -> ApiKeyOut:
    from datetime import timezone

    key = await db.get(ApiKey, key_id)
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(key)
    return ApiKeyOut.model_validate(key)
