"""Conversation service — creation, message timeline, completion."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.modules.conversations.models import Conversation, ConversationMessage
from app.modules.workflows.models import Workflow


def get_or_create_conversation(
    db: Session,
    *,
    channel: str,
    from_number: str,
    to_number: str | None = None,
    session_id: str | None = None,
    workflow: Workflow | None = None,
) -> Conversation:
    """Reuse the conversation for an ongoing telecom session (voice) or
    create one per message (SMS)."""
    if channel == "voice" and session_id:
        existing = (
            db.query(Conversation)
            .filter(Conversation.provider_session_id == session_id, Conversation.channel == "voice")
            .first()
        )
        if existing:
            return existing
    conversation = Conversation(
        channel=channel,
        status="active",
        from_number=from_number,
        to_number=to_number,
        workflow_id=workflow.id if workflow else None,
        provider_session_id=session_id,
        target_language=_guess_target(workflow),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    log_event("conversation.created", conversation_id=conversation.id, detail=channel)
    return conversation


def _guess_target(workflow: Workflow | None) -> str | None:
    if not workflow or not workflow.versions:
        return None
    for node in workflow.versions[-1].definition.get("nodes", []):
        if node.get("type") == "translate":
            return (node.get("config") or {}).get("target_language")
    return None


def add_message(
    db: Session,
    conversation: Conversation,
    *,
    role: str,
    channel: str,
    content: str,
    translated_content: str | None = None,
    language: str | None = None,
    meta: dict | None = None,
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation.id,
        role=role,
        channel=channel,
        content=content,
        translated_content=translated_content,
        language=language,
        meta=meta or {},
    )
    db.add(message)
    db.commit()
    return message


def complete_conversation(db: Session, conversation: Conversation, status: str = "completed") -> Conversation:
    conversation.status = status
    conversation.ended_at = datetime.now(UTC).replace(tzinfo=None)
    if conversation.started_at:
        delta = conversation.ended_at - conversation.started_at
        conversation.duration_ms = round(delta.total_seconds() * 1000, 1)
    db.commit()
    log_event("conversation.completed", conversation_id=conversation.id, detail=status)
    return conversation


def list_conversations(db: Session, limit: int = 50) -> list[Conversation]:
    return db.query(Conversation).order_by(Conversation.started_at.desc()).limit(limit).all()


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.get(Conversation, conversation_id)
