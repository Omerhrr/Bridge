"""Conversation endpoints — history and timelines (spec §27, §28)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.conversations import service as conversation_service
from app.modules.conversations.schemas import ConversationOut, MessageCreate, MessageOut

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _conversation_out(c) -> ConversationOut:
    return ConversationOut(
        id=c.id,
        channel=c.channel,
        status=c.status,
        from_number=c.from_number,
        to_number=c.to_number,
        language=c.language,
        target_language=c.target_language,
        workflow_id=c.workflow_id,
        started_at=c.started_at.isoformat() if c.started_at else None,
        ended_at=c.ended_at.isoformat() if c.ended_at else None,
        duration_ms=c.duration_ms,
    )


def _message_out(m) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role,
        channel=m.channel,
        content=m.content,
        translated_content=m.translated_content,
        language=m.language,
        created_at=m.created_at.isoformat() if m.created_at else None,
    )


@router.get("", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), limit: int = 50, channel: str | None = None):
    conversations = conversation_service.list_conversations(db, limit=limit)
    if channel:
        conversations = [c for c in conversations if c.channel == channel]
    return [_conversation_out(c) for c in conversations]


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = conversation_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    out = _conversation_out(conversation).model_dump()
    out["messages"] = [_message_out(m) for m in conversation.messages]
    return out


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def add_message(conversation_id: int, payload: MessageCreate, db: Session = Depends(get_db)):
    conversation = conversation_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    message = conversation_service.add_message(
        db,
        conversation,
        role=payload.role,
        channel=payload.channel or conversation.channel,
        content=payload.content,
        translated_content=payload.translated_content,
        language=payload.language,
    )
    return _message_out(message)
