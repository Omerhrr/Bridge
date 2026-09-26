"""Knowledge ingestion: fetch a source and turn it into searchable chunks.

Supported sources
  website       crawl a site (same host, bounded page count)
  google_doc    a Google Doc shared "anyone with the link can view"
  google_sheet  a Google Sheet shared the same way (each row becomes facts)
  database      a read-only SELECT against PostgreSQL or MySQL
  text          text typed or pasted in the dashboard (FAQ, price list …)

Outbound fetches are restricted to public hosts (no private / loopback /
link-local addresses) so a source can't be used to probe internal networks.
"""
from __future__ import annotations

import asyncio
import csv
import io
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import httpx

from app.core.config import settings

MAX_RESPONSE_BYTES = 3_000_000
MAX_PAGES = 30
MAX_DB_ROWS = 2000
CHUNK_CHARS = 900
ROWS_PER_CHUNK = 8
USER_AGENT = "BridgeKnowledgeBot/1.0 (+https://bridge.rogan.live)"

_SKIP_EXTENSIONS = re.compile(
    r"\.(pdf|jpe?g|png|gif|webp|svg|ico|css|js|zip|rar|mp[34]|mov|avi|docx?|xlsx?|pptx?|xml|json)$", re.I
)


class IngestError(RuntimeError):
    """A source could not be read; the message is shown to the user."""


@dataclass
class Chunk:
    content: str
    title: str = ""
    location: str = ""


# ------------------------------------------------------------------ safety
def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified)


async def assert_public_host(host: str | None) -> None:
    if not host:
        raise IngestError("The address has no host name")
    if settings.allow_private_sources:
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise IngestError(f"Could not resolve {host}") from exc
    for info in infos:
        if not _is_public_ip(info[4][0]):
            raise IngestError(f"{host} points to a private network address, which is not allowed")


async def fetch(url: str, client: httpx.AsyncClient) -> httpx.Response:
    """GET a public URL, validating every redirect hop."""
    for _ in range(6):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise IngestError("Only http(s) addresses are supported")
        await assert_public_host(parsed.hostname)
        try:
            resp = await client.get(url, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise IngestError(f"Could not reach {parsed.hostname}: {exc.__class__.__name__}") from exc
        if resp.is_redirect and resp.headers.get("location"):
            url = urljoin(url, resp.headers["location"])
            continue
        if len(resp.content) > MAX_RESPONSE_BYTES:
            raise IngestError("The page is too large to import")
        return resp
    raise IngestError("Too many redirects")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0), headers={"User-Agent": USER_AGENT})


# ---------------------------------------------------------------- chunking
def _clean(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def chunk_text(text: str, title: str = "", location: str = "") -> list[Chunk]:
    """Split prose into ~CHUNK_CHARS pieces along paragraph/sentence lines."""
    text = _clean(text)
    if not text:
        return []
    pieces: list[str] = []
    for para in re.split(r"\n{2,}|\n(?=[-•*]\s)", text):
        para = para.strip()
        if len(para) <= CHUNK_CHARS:
            pieces.append(para)
            continue
        sentence_buf = ""
        for sentence in re.split(r"(?<=[.!?])\s+", para):
            if len(sentence_buf) + len(sentence) > CHUNK_CHARS and sentence_buf:
                pieces.append(sentence_buf.strip())
                sentence_buf = ""
            sentence_buf += sentence + " "
        if sentence_buf.strip():
            pieces.append(sentence_buf.strip())

    chunks: list[Chunk] = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + len(piece) > CHUNK_CHARS:
            chunks.append(Chunk(buf.strip(), title, location))
            buf = ""
        buf += piece + "\n\n"
    if buf.strip():
        chunks.append(Chunk(buf.strip(), title, location))
    return chunks


def chunk_rows(headers: list[str], rows: list[list], title: str, location: str) -> list[Chunk]:
    """Tabular data: each row becomes a 'Column: value; …' fact line."""
    headers = [str(h).strip() or f"Column {i + 1}" for i, h in enumerate(headers)]
    lines = []
    for row in rows:
        cells = [f"{h}: {str(v).strip()}" for h, v in zip(headers, row) if v not in (None, "") and str(v).strip()]
        if cells:
            lines.append("; ".join(cells))
    chunks = []
    for start in range(0, len(lines), ROWS_PER_CHUNK):
        block = lines[start:start + ROWS_PER_CHUNK]
        chunks.append(Chunk("\n".join(block), title, f"{location} rows {start + 1}-{start + len(block)}"))
    return chunks


# ----------------------------------------------------------------- website
def _html_to_text(html: str) -> tuple[str, str, list[str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "template", "form"]):
        tag.decompose()
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        description = meta["content"].strip()
    body = soup.body or soup
    # Block-level elements become paragraph breaks.
    for tag in body.find_all(["p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "br", "footer", "header"]):
        tag.insert_before("\n\n" if tag.name not in ("li", "br", "tr") else "\n")
    text = body.get_text(" ")
    if description:
        text = description + "\n\n" + text
    return title, _clean(text), links


async def ingest_website(url: str, max_pages: int = 10) -> list[Chunk]:
    start = url if re.match(r"^https?://", url, re.I) else f"https://{url}"
    host = urlparse(start).hostname
    max_pages = max(1, min(int(max_pages or 10), MAX_PAGES))
    queue, seen, chunks = [start], set(), []
    async with _client() as client:
        while queue and len(seen) < max_pages:
            page = queue.pop(0)
            if page in seen:
                continue
            seen.add(page)
            try:
                resp = await fetch(page, client)
            except IngestError:
                if page == start:
                    raise
                continue
            if resp.status_code >= 400:
                if page == start:
                    raise IngestError(f"{start} returned HTTP {resp.status_code}")
                continue
            if "html" not in resp.headers.get("content-type", "html"):
                continue
            title, text, links = _html_to_text(resp.text)
            chunks.extend(chunk_text(text, title=title or page, location=str(resp.url)))
            for href in links:
                absolute = urldefrag(urljoin(str(resp.url), href))[0].rstrip("/")
                parsed = urlparse(absolute)
                if (parsed.hostname == host and parsed.scheme in ("http", "https")
                        and not _SKIP_EXTENSIONS.search(parsed.path)
                        and absolute not in seen and absolute not in queue):
                    queue.append(absolute)
    if not chunks:
        raise IngestError("No readable text was found on the website")
    return chunks


# ------------------------------------------------------------------ google
_DOC_ID = re.compile(r"/document/d/([a-zA-Z0-9_-]{20,})")
_SHEET_ID = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})")
_SHARE_HINT = "Share it as 'Anyone with the link can view' and try again"


async def ingest_google_doc(url: str) -> list[Chunk]:
    match = _DOC_ID.search(url or "")
    if not match:
        raise IngestError("That doesn't look like a Google Docs link")
    export = f"https://docs.google.com/document/d/{match.group(1)}/export?format=txt"
    async with _client() as client:
        resp = await fetch(export, client)
    if resp.status_code >= 400 or "text/html" in resp.headers.get("content-type", ""):
        raise IngestError(f"Google refused access to the document. {_SHARE_HINT}")
    chunks = chunk_text(resp.content.decode("utf-8-sig", errors="replace"), title="Google Doc", location=url)
    if not chunks:
        raise IngestError("The document is empty")
    return chunks


async def ingest_google_sheet(url: str) -> list[Chunk]:
    match = _SHEET_ID.search(url or "")
    if not match:
        raise IngestError("That doesn't look like a Google Sheets link")
    parsed = urlparse(url)
    gid = (parse_qs(parsed.query).get("gid") or parse_qs(parsed.fragment).get("gid") or ["0"])[0]
    export = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv&gid={gid}"
    async with _client() as client:
        resp = await fetch(export, client)
    if resp.status_code >= 400 or "text/html" in resp.headers.get("content-type", ""):
        raise IngestError(f"Google refused access to the sheet. {_SHARE_HINT}")
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig", errors="replace"))))
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        raise IngestError("The sheet needs a header row and at least one data row")
    return chunk_rows(rows[0], rows[1:], title="Google Sheet", location=url)


# ---------------------------------------------------------------- database
_SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.I)
# Defence in depth only: the session itself is opened read-only.
_FORBIDDEN_SQL = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b", re.I)


def validate_query(query: str) -> str:
    query = (query or "").strip().rstrip(";").strip()
    if not _SELECT_ONLY.match(query):
        raise IngestError("Only SELECT queries are allowed")
    if ";" in query:
        raise IngestError("Use a single SELECT statement")
    # Strip string literals before looking for write keywords.
    bare = re.sub(r"'(?:[^']|'')*'", "''", query)
    if _FORBIDDEN_SQL.search(bare):
        raise IngestError("The query may only read data (SELECT)")
    return query


def normalize_db_url(url: str) -> tuple[str, str]:
    url = (url or "").strip()
    for prefix, target, dialect in (
        ("postgres://", "postgresql+asyncpg://", "postgresql"),
        ("postgresql://", "postgresql+asyncpg://", "postgresql"),
        ("postgresql+asyncpg://", "postgresql+asyncpg://", "postgresql"),
        ("mysql://", "mysql+aiomysql://", "mysql"),
        ("mysql+aiomysql://", "mysql+aiomysql://", "mysql"),
    ):
        if url.startswith(prefix):
            return target + url[len(prefix):], dialect
    raise IngestError("Use a postgresql:// or mysql:// connection string")


async def ingest_database(connection_url: str, query: str, title: str) -> list[Chunk]:
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    query = validate_query(query)
    url, dialect = normalize_db_url(connection_url)
    try:
        host = make_url(url).host
    except Exception as exc:
        raise IngestError("The connection string is not valid") from exc
    await assert_public_host(host)

    if dialect == "postgresql":
        connect_args = {"timeout": 10, "server_settings": {
            "default_transaction_read_only": "on", "statement_timeout": "15000"}}
    else:
        connect_args = {"connect_timeout": 10}
    engine = create_async_engine(url, connect_args=connect_args, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            if dialect == "mysql":
                await conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
                await conn.execute(text("SET SESSION MAX_EXECUTION_TIME=15000"))
            result = await conn.execute(text(query))
            headers = list(result.keys())
            rows = [list(r) for r in result.fetchmany(MAX_DB_ROWS)]
            await conn.rollback()
    except IngestError:
        raise
    except Exception as exc:
        # Driver messages can echo the DSN; keep only the first line and
        # never include the connection string itself.
        message = str(exc).splitlines()[0][:200] if str(exc) else exc.__class__.__name__
        raise IngestError(f"Database error: {message}") from exc
    finally:
        await engine.dispose()
    if not rows:
        raise IngestError("The query returned no rows")
    return chunk_rows(headers, rows, title=title, location="database")
