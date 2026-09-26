"""Authentication routes (spec section 32).

    GET  /auth/setup     does the dashboard still need its first (owner) account?
    POST /auth/register  create the owner account (first run) or, when
                         ALLOW_REGISTRATION=true, additional accounts
    POST /auth/login     OAuth2 password flow -> bearer token
    GET  /auth/me        the signed-in user
"""
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DbSession, require_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.workflows.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool

    model_config = {"from_attributes": True}


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""
    setup_code: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SetupStatus(BaseModel):
    needs_setup: bool
    setup_code_required: bool
    registration_open: bool
    auth_enabled: bool


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    return result.scalar_one_or_none()


async def _active_users(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User).where(User.is_active.is_(True)))).scalar_one()


def _setup_code_required() -> bool:
    return bool(settings.setup_code) or settings.environment == "production"


@router.get("/setup", response_model=SetupStatus)
async def setup_status(db: DbSession) -> SetupStatus:
    needs_setup = await _active_users(db) == 0
    return SetupStatus(
        needs_setup=needs_setup,
        setup_code_required=needs_setup and _setup_code_required(),
        registration_open=needs_setup or settings.allow_registration,
        auth_enabled=settings.auth_enabled,
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: DbSession) -> TokenOut:
    first_account = await _active_users(db) == 0
    if not first_account and not settings.allow_registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed. Ask the owner for an account.")
    if first_account and _setup_code_required():
        if not settings.setup_code:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Set the SETUP_CODE environment variable on the backend to create the owner account.")
        if not hmac.compare_digest((data.setup_code or "").strip(), settings.setup_code):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "The setup code is not correct.")
    if await _get_user_by_email(db, data.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    return TokenOut(access_token=create_access_token(user.email), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> TokenOut:
    user = await _get_user_by_email(db, form.username)
    if not user or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.email), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User | None, Depends(require_user)]) -> UserOut:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return UserOut.model_validate(user)
