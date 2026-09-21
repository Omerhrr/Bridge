"""Conversation API schemas (spec sections 27-28)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConversationMessageOut(BaseModel):
    id: int
    role: str
    channel: str
    content: str
    translated_content: str | None
    source_language: str | None
    target_language: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    channel: str
    status: str
    a_number: str | None
    b_number: str | None
    source_language: str | None
    target_language: str | None
    workflow_run_id: str | None
    started_at: datetime
    ended_at: datetime | None
    messages: list[ConversationMessageOut] = []

    model_config = {"from_attributes": True}


class TimelineEvent(BaseModel):
    """A single timeline entry combining run events and messages (spec section 28)."""

    timestamp: datetime
    kind: str
    label: str
    detail: dict[str, Any] = {}
