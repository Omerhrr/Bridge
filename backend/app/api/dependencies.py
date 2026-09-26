"""Shared FastAPI dependencies."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    user = result.scalar_one_or_none()
    return user if user and user.is_active else None


async def require_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User | None:
    """Gate for every dashboard/API route (webhooks and health stay public).
    Disabled with AUTH_ENABLED=false (tests, local experiments)."""
    if not settings.auth_enabled:
        return user
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sign in to continue",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User | None, Depends(require_user)]


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
