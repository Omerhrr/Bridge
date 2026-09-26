"""Public, API-key-authenticated endpoints for external integrations (a
website chatbot widget, another backend, a mobile app) that want to ask
Bridge's knowledge assistant a question without a dashboard login.

    POST /api/v1/public/assistant/ask

Authenticated with an `X-Api-Key` header (see app/modules/knowledge/apikeys.py),
never a dashboard JWT. This router is intentionally NOT added to the
`_protected` group in app/main.py, and its responses get permissive CORS
headers (any origin) since the caller is an arbitrary customer website,
unlike the rest of the API which is restricted to `settings.cors_origin_list`.
"""
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import AiServiceDep, DbSession
from app.modules.knowledge import apikeys
from app.modules.knowledge.assistant import KnowledgeAssistant
from app.modules.knowledge.service import log_query

router = APIRouter(prefix="/public", tags=["public"])


class PublicAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    language: str | None = None
    # Optional caller-supplied identifier (e.g. a website visitor id) so the
    # business can tell conversations apart in the query log. Never trusted
    # for anything security-sensitive.
    user_ref: str | None = Field(None, max_length=64)


class PublicAskOut(BaseModel):
    answered: bool
    answer: str
    language: str | None


@router.post("/assistant/ask", response_model=PublicAskOut)
async def public_ask(
    data: PublicAskIn,
    db: DbSession,
    ai: AiServiceDep,
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
) -> PublicAskOut:
    key = await apikeys.authenticate(db, x_api_key)
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
    if not apikeys.check_rate_limit(key.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded, try again shortly")

    result = await KnowledgeAssistant(db, ai).answer(data.question, language=data.language)
    await log_query(db, data.question, result, phone=data.user_ref, channel="api")
    await apikeys.touch(db, key)
    await db.commit()
    return PublicAskOut(answered=result.answered, answer=result.text, language=result.language)
