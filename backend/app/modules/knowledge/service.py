"""Knowledge source management: create, sync and remove sources, and log
the questions the assistant answers."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.logging import get_logger, log_event
from app.modules.knowledge import ingest
from app.modules.knowledge.assistant import AnswerResult
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeQuery, KnowledgeSource

logger = get_logger("bridge.knowledge.sync")

SOURCE_KINDS = ("website", "google_doc", "google_sheet", "database", "text")
MAX_TEXT_CHARS = 200_000


class SourceConfigError(ValueError):
    pass


def build_source(kind: str, name: str, config: dict, secret: str | None) -> KnowledgeSource:
    """Validate user input for a new source (before anything is fetched)."""
    if kind not in SOURCE_KINDS:
        raise SourceConfigError(f"Unknown source type '{kind}'")
    config = dict(config or {})
    clean: dict = {}
    if kind in ("website", "google_doc", "google_sheet"):
        url = str(config.get("url") or "").strip()
        if not url:
            raise SourceConfigError("A link is required")
        clean["url"] = url
        if kind == "website":
            clean["max_pages"] = max(1, min(int(config.get("max_pages") or 10), ingest.MAX_PAGES))
        if kind == "google_doc" and not ingest._DOC_ID.search(url):
            raise SourceConfigError("That doesn't look like a Google Docs link")
        if kind == "google_sheet" and not ingest._SHEET_ID.search(url):
            raise SourceConfigError("That doesn't look like a Google Sheets link")
    elif kind == "database":
        if not secret:
            raise SourceConfigError("A connection string is required")
        try:
            ingest.normalize_db_url(secret)
            clean["query"] = ingest.validate_query(str(config.get("query") or ""))
        except ingest.IngestError as exc:
            raise SourceConfigError(str(exc)) from exc
        clean["dialect"] = "mysql" if secret.strip().startswith("mysql") else "postgresql"
    elif kind == "text":
        text = str(config.get("text") or "").strip()
        if not text:
            raise SourceConfigError("Add some text")
        if len(text) > MAX_TEXT_CHARS:
            raise SourceConfigError("The text is too long (200,000 characters max)")
        clean["text"] = text

    default_names = {"website": clean.get("url"), "google_doc": "Google Doc", "google_sheet": "Google Sheet",
                     "database": "Database", "text": "Business notes"}
    return KnowledgeSource(
        name=(name or "").strip() or default_names[kind] or kind,
        kind=kind,
        config=clean,
        secret=encrypt_secret(secret.strip()) if kind == "database" and secret else None,
        status="pending",
    )


async def fetch_chunks(source: KnowledgeSource) -> list[ingest.Chunk]:
    cfg = source.config or {}
    if source.kind == "website":
        return await ingest.ingest_website(cfg["url"], cfg.get("max_pages", 10))
    if source.kind == "google_doc":
        return await ingest.ingest_google_doc(cfg["url"])
    if source.kind == "google_sheet":
        return await ingest.ingest_google_sheet(cfg["url"])
    if source.kind == "database":
        return await ingest.ingest_database(decrypt_secret(source.secret or ""), cfg["query"], source.name)
    if source.kind == "text":
        return ingest.chunk_text(cfg["text"], title=source.name, location="Business notes")
    raise ingest.IngestError(f"Unsupported source type '{source.kind}'")


async def sync_source(session: AsyncSession, source: KnowledgeSource) -> KnowledgeSource:
    """Fetch the source and replace its chunks. Errors are stored on the
    source (status=error) rather than raised."""
    source.status = "syncing"
    source.error = None
    await session.flush()
    try:
        chunks = await fetch_chunks(source)
    except (ingest.IngestError, ValueError) as exc:
        source.status, source.error = "error", str(exc)
        log_event(logger, "knowledge.sync_failed", source_id=source.id, error=str(exc))
        return source
    except Exception as exc:  # unexpected: keep the message generic
        source.status, source.error = "error", f"Import failed ({exc.__class__.__name__})"
        logger.exception("knowledge.sync_crashed", extra={"extra_fields": {"source_id": source.id}})
        return source

    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id))
    for position, chunk in enumerate(chunks):
        session.add(KnowledgeChunk(source_id=source.id, title=chunk.title[:500],
                                   location=chunk.location[:1000], content=chunk.content, position=position))
    source.chunk_count = len(chunks)
    source.status = "ready"
    source.last_synced_at = datetime.now(timezone.utc)
    await session.flush()
    log_event(logger, "knowledge.synced", source_id=source.id, chunks=len(chunks))
    return source


async def sync_in_background(source_id: int) -> None:
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        source = await session.get(KnowledgeSource, source_id)
        if source is None:
            return
        await sync_source(session, source)
        await session.commit()


async def delete_source(session: AsyncSession, source: KnowledgeSource) -> None:
    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id))
    await session.delete(source)


async def log_query(session: AsyncSession, question: str, result: AnswerResult, *,
                    phone: str | None = None, channel: str = "sms") -> None:
    session.add(KnowledgeQuery(
        phone_number=phone, channel=channel, question=question[:2000], answer=result.text,
        answered=result.answered, reason=result.reason, language=result.language,
        source_ids=sorted({s.source_id for s in result.sources}),
    ))
    await session.flush()


async def reset_stuck_syncs(session: AsyncSession) -> None:
    """A restart during a sync leaves sources 'syncing' forever; mark them."""
    stuck = await session.execute(select(KnowledgeSource).where(KnowledgeSource.status == "syncing"))
    for source in stuck.scalars():
        source.status = "error"
        source.error = "Sync was interrupted by a restart. Sync again."
