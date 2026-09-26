"""Knowledge base endpoints: business profile, sources, test console, question log.

    GET  /knowledge/profile              business profile + knowledge stats
    PUT  /knowledge/profile              update the profile
    GET  /knowledge/sources              configured sources
    POST /knowledge/sources              add a source (imported in the background)
    POST /knowledge/sources/{id}/sync    re-import a source
    GET  /knowledge/sources/{id}/chunks  what Bridge extracted (first 50 passages)
    DELETE /knowledge/sources/{id}       remove a source and its passages
    POST /knowledge/ask                  ask the assistant (test console)
    GET  /knowledge/queries              recent questions, answered or not
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.dependencies import AiServiceDep, DbSession
from app.core.config import settings
from app.modules.knowledge.assistant import KnowledgeAssistant
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeQuery, KnowledgeSource
from app.modules.knowledge.service import (
    SourceConfigError,
    build_source,
    delete_source,
    log_query,
    sync_in_background,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ------------------------------------------------------------------ profile
class ProfileIn(BaseModel):
    name: str = Field("", max_length=255)
    description: str = Field("", max_length=4000)
    contact: str = Field("", max_length=255)
    fallback_message: str = Field("", max_length=480)
    assistant_enabled: bool = True


class ProfileOut(ProfileIn):
    sources: int
    ready_sources: int
    passages: int
    questions: int
    unanswered: int
    ai_configured: bool
    available: bool


@router.get("/profile", response_model=ProfileOut)
async def get_profile(db: DbSession) -> ProfileOut:
    assistant = KnowledgeAssistant(db)
    profile = await assistant.profile()
    count = lambda q: db.execute(q)  # noqa: E731
    sources = (await count(select(func.count()).select_from(KnowledgeSource))).scalar_one()
    ready = (await count(select(func.count()).select_from(KnowledgeSource)
                         .where(KnowledgeSource.status == "ready"))).scalar_one()
    passages = (await count(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
    questions = (await count(select(func.count()).select_from(KnowledgeQuery))).scalar_one()
    unanswered = (await count(select(func.count()).select_from(KnowledgeQuery)
                              .where(KnowledgeQuery.answered.is_(False)))).scalar_one()
    return ProfileOut(
        name=profile.name, description=profile.description, contact=profile.contact,
        fallback_message=profile.fallback_message, assistant_enabled=profile.assistant_enabled,
        sources=sources, ready_sources=ready, passages=passages, questions=questions,
        unanswered=unanswered, ai_configured=settings.ai_configured,
        available=await assistant.is_available() and settings.ai_configured,
    )


@router.put("/profile", response_model=ProfileOut)
async def update_profile(data: ProfileIn, db: DbSession) -> ProfileOut:
    profile = await KnowledgeAssistant(db).profile()
    for key, value in data.model_dump().items():
        setattr(profile, key, value.strip() if isinstance(value, str) else value)
    await db.flush()
    return await get_profile(db)


# ------------------------------------------------------------------ sources
class SourceIn(BaseModel):
    kind: str
    name: str = ""
    config: dict = Field(default_factory=dict)
    # Database connection string. Write-only: stored encrypted, never returned.
    secret: str | None = None


class SourceOut(BaseModel):
    id: int
    name: str
    kind: str
    config: dict
    has_secret: bool
    status: str
    error: str | None
    chunk_count: int
    last_synced_at: datetime | None
    created_at: datetime


def _source_out(source: KnowledgeSource) -> SourceOut:
    return SourceOut(
        id=source.id, name=source.name, kind=source.kind, config=source.config or {},
        has_secret=bool(source.secret), status=source.status, error=source.error,
        chunk_count=source.chunk_count, last_synced_at=source.last_synced_at, created_at=source.created_at,
    )


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(db: DbSession) -> list[SourceOut]:
    result = await db.execute(select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc()))
    return [_source_out(s) for s in result.scalars()]


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_202_ACCEPTED)
async def add_source(data: SourceIn, db: DbSession, background: BackgroundTasks) -> SourceOut:
    try:
        source = build_source(data.kind, data.name, data.config, data.secret)
    except SourceConfigError as exc:
        raise HTTPException(422, str(exc)) from exc
    source.status = "syncing"
    db.add(source)
    await db.flush()
    await db.commit()
    background.add_task(sync_in_background, source.id)
    return _source_out(source)


async def _get_source(db, source_id: int) -> KnowledgeSource:
    source = await db.get(KnowledgeSource, source_id)
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return source


@router.post("/sources/{source_id}/sync", response_model=SourceOut, status_code=status.HTTP_202_ACCEPTED)
async def resync_source(source_id: int, db: DbSession, background: BackgroundTasks) -> SourceOut:
    source = await _get_source(db, source_id)
    if source.status == "syncing":
        return _source_out(source)
    source.status, source.error = "syncing", None
    await db.commit()
    background.add_task(sync_in_background, source.id)
    return _source_out(source)


class ChunkOut(BaseModel):
    id: int
    title: str
    location: str
    content: str


@router.get("/sources/{source_id}/chunks", response_model=list[ChunkOut])
async def source_chunks(source_id: int, db: DbSession) -> list[ChunkOut]:
    await _get_source(db, source_id)
    result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id)
        .order_by(KnowledgeChunk.position).limit(50)
    )
    return [ChunkOut(id=c.id, title=c.title, location=c.location, content=c.content) for c in result.scalars()]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_source(source_id: int, db: DbSession) -> None:
    await delete_source(db, await _get_source(db, source_id))


# --------------------------------------------------------------------- ask
class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    language: str | None = None


class SourceRefOut(BaseModel):
    source_id: int
    source_name: str
    title: str
    location: str
    excerpt: str


class AskOut(BaseModel):
    answered: bool
    answer: str
    reason: str
    language: str | None
    evidence: list[str]
    sources: list[SourceRefOut]


@router.post("/ask", response_model=AskOut)
async def ask(data: AskIn, db: DbSession, ai: AiServiceDep) -> AskOut:
    result = await KnowledgeAssistant(db, ai).answer(data.question, language=data.language)
    await log_query(db, data.question, result, channel="dashboard")
    return AskOut(
        answered=result.answered, answer=result.text, reason=result.reason, language=result.language,
        evidence=result.evidence,
        sources=[SourceRefOut(source_id=s.source_id, source_name=s.source_name, title=s.title,
                              location=s.location, excerpt=s.excerpt) for s in result.sources],
    )


class QueryOut(BaseModel):
    id: int
    phone_number: str | None
    channel: str
    question: str
    answer: str
    answered: bool
    reason: str
    language: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/queries", response_model=list[QueryOut])
async def recent_queries(db: DbSession, unanswered: bool = False,
                         limit: int = Query(50, ge=1, le=200)) -> list[QueryOut]:
    query = select(KnowledgeQuery).order_by(KnowledgeQuery.created_at.desc()).limit(limit)
    if unanswered:
        query = query.where(KnowledgeQuery.answered.is_(False))
    return [QueryOut.model_validate(q) for q in (await db.execute(query)).scalars()]
