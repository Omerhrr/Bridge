"""Shared FastAPI dependencies."""
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.ai.service import AIService, get_ai_service
from app.modules.communications.service import CommunicationService, get_communication_service
from app.modules.workflows.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User | None:
    """Resolve the user from a bearer token; None when absent/invalid.

    The hackathon MVP keeps dashboard browsing open; write operations can
    tighten this by switching to a required variant.
    """
    if not token:
        return None
    subject = decode_access_token(token)
    if not subject:
        return None
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == subject))
    return result.scalar_one_or_none()


def get_engine_factory(db: DbSession):
    """Build a workflow engine bound to the request session."""
    def factory() -> "tuple[AsyncSession, WorkflowEngine]":
        ai = get_ai_service()
        comms = get_communication_service()
        from app.modules.workflows.engine import WorkflowEngine

        return db, WorkflowEngine(db, ai, comms)
    return factory


AiServiceDep = Annotated[AIService, Depends(get_ai_service)]
CommsServiceDep = Annotated[CommunicationService, Depends(get_communication_service)]
