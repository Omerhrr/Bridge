"""Shared API dependencies."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Optional bearer-token auth for mutating dashboard operations (spec §32).

    When BRIDGE_API_TOKEN is unset the API is open (local development);
    when set, mutating /api/workflows calls must present it.
    """
    token = get_settings().api_token
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API token")


def db_session(session: Session = Depends(get_db)) -> Session:
    return session
