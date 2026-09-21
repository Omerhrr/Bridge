"""Call and SMS history endpoints (spec section 30)."""
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.modules.communications.models import Call, SmsMessage

router = APIRouter(tags=["communications"])


class CallOut(BaseModel):
    id: int
    provider_call_id: str | None
    direction: str
    from_number: str | None
    to_number: str | None
    status: str
    duration_seconds: float
    started_at: datetime

    model_config = {"from_attributes": True}


class SmsOut(BaseModel):
    id: int
    provider_message_id: str | None
    direction: str
    from_number: str | None
    to_number: str | None
    text: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/calls", response_model=list[CallOut])
async def list_calls(db: DbSession) -> list[CallOut]:
    result = await db.execute(select(Call).order_by(Call.started_at.desc()).limit(200))
    return [CallOut.model_validate(c, from_attributes=True) for c in result.scalars()]


@router.get("/messages", response_model=list[SmsOut])
async def list_messages(db: DbSession) -> list[SmsOut]:
    result = await db.execute(select(SmsMessage).order_by(SmsMessage.created_at.desc()).limit(200))
    return [SmsOut.model_validate(m, from_attributes=True) for m in result.scalars()]
