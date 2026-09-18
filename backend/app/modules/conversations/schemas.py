"""Conversation schemas."""

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    id: int
    channel: str
    status: str
    from_number: str
    to_number: str | None = None
    language: str | None = None
    target_language: str | None = None
    workflow_id: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: float | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    channel: str
    content: str
    translated_content: str | None = None
    language: str | None = None
    created_at: str | None = None


class MessageCreate(BaseModel):
    role: str = Field(default="system")
    channel: str = Field(default="sms")
    content: str = ""
    translated_content: str | None = None
    language: str | None = None
