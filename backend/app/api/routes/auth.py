"""Authentication routes (spec section 32)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DbSession
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
    password: str
    full_name: str = ""


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: DbSession) -> TokenOut:
    if await _get_user_by_email(db, data.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    return TokenOut(access_token=create_access_token(user.email), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> TokenOut:
    user = await _get_user_by_email(db, form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.email), user=UserOut.model_validate(user))
