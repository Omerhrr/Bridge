"""Conversation endpoints: list, detail and timeline (spec sections 27-28)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import DbSession
from app.modules.conversations.schemas import ConversationOut, TimelineEvent
from app.modules.conversations.service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def get_service(db: DbSession) -> ConversationService:
    return ConversationService(db)


ServiceDep = Annotated[ConversationService, Depends(get_service)]


@router.get("", response_model=list[ConversationOut])
async def list_conversations(service: ServiceDep) -> list[ConversationOut]:
    conversations = await service.list_conversations()
    return [ConversationOut.model_validate(c, from_attributes=True) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: int, service: ServiceDep) -> ConversationOut:
    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return ConversationOut.model_validate(conversation, from_attributes=True)


@router.get("/{conversation_id}/timeline", response_model=list[TimelineEvent])
async def get_timeline(conversation_id: int, service: ServiceDep) -> list[TimelineEvent]:
    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return await service.build_timeline(conversation)
