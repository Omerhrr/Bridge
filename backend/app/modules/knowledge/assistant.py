"""Grounded question answering over the business's knowledge base.

Pipeline
  1. Understand   LLM detects the customer's language and rewrites the
                  question into search keywords (so a Hausa question can
                  find English documents).
  2. Retrieve     BM25 over the synced chunks.
  3. Answer       LLM answers ONLY from the retrieved passages and must quote
                  its evidence verbatim.
  4. Verify       Bridge checks the quotes really exist in the passages and
                  that every number in the answer appears in them. Anything
                  that fails verification is replaced by the business's
                  fallback message: the customer never receives an
                  unsupported claim.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.modules.ai.languages import language_name, normalize_language
from app.modules.ai.llm import chat_json
from app.modules.knowledge.models import BusinessProfile, KnowledgeChunk, KnowledgeSource
from app.modules.knowledge.search import bm25_rank

logger = get_logger("bridge.knowledge")

MAX_CONTEXT_CHUNKS = 6
MAX_ANSWER_CHARS = 459  # three SMS segments

DEFAULT_FALLBACK = "Sorry, I don't have that information right now."


@dataclass
class SourceRef:
    chunk_id: int
    source_id: int
    source_name: str
    title: str
    location: str
    excerpt: str


@dataclass
class AnswerResult:
    answered: bool
    text: str
    language: str | None = None
    reason: str = ""  # answered | no_knowledge | no_match | not_in_sources | unverified | ai_unavailable | disabled
    sources: list[SourceRef] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


# ----------------------------------------------------------- verification
def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[‘’“”\"'`]", "", text)
    return re.sub(r"\s+", " ", text).strip(" .,;:!?-")


def _numbers(text: str) -> set[str]:
    # "1,500.00" -> "1500.00", "+254 712 345 678" -> "254712345678"
    compact = re.sub(r"(?<=\d)[,\s](?=\d)", "", text)
    found = set()
    for number in re.findall(r"\d+(?:\.\d+)?", compact):
        found.add(number)
        if "." in number:
            whole, _, frac = number.partition(".")
            if set(frac) == {"0"}:
                found.add(whole)  # "1500.00" also supports "1500"
    return found


def verify_answer(answer: str, evidence: list[str], context: str) -> tuple[bool, list[str]]:
    """Return (ok, verified_quotes). A grounded answer needs at least one
    verbatim quote from the context, and no number the context lacks."""
    haystack = _norm(context)
    verified = [q for q in evidence if isinstance(q, str) and len(_norm(q)) >= 3 and _norm(q) in haystack]
    if not verified:
        return False, []
    context_numbers = _numbers(context)
    for number in _numbers(answer):
        if number not in context_numbers and number.split(".")[0] not in context_numbers:
            return False, verified
    return True, verified


# ------------------------------------------------------------------ pipeline
class KnowledgeAssistant:
    def __init__(self, session: AsyncSession, ai=None):
        self.session = session
        self.ai = ai

    async def profile(self) -> BusinessProfile:
        profile = (await self.session.execute(select(BusinessProfile).limit(1))).scalar_one_or_none()
        if profile is None:
            profile = BusinessProfile()
            self.session.add(profile)
            await self.session.flush()
        return profile

    async def is_available(self) -> bool:
        """Enabled, backed by a model, and at least one source is ready."""
        if not settings.ai_configured:
            return False
        profile = await self.profile()
        if not profile.assistant_enabled:
            return False
        ready = await self.session.execute(
            select(KnowledgeSource.id).where(KnowledgeSource.status == "ready", KnowledgeSource.chunk_count > 0).limit(1)
        )
        return ready.scalar_one_or_none() is not None

    async def _fallback(self, profile: BusinessProfile, language: str | None, reason: str,
                        sources: list[SourceRef] | None = None) -> AnswerResult:
        message = profile.fallback_message.strip() or DEFAULT_FALLBACK
        if profile.contact and profile.contact not in message:
            message = f"{message} Contact: {profile.contact}"
        if language and language != "en" and self.ai is not None:
            try:
                result = await self.ai.translation.translate(message, source="auto", target=language)
                message = result.text
            except Exception:
                pass
        return AnswerResult(answered=False, text=message, language=language, reason=reason, sources=sources or [])

    async def _welcome(self, profile: BusinessProfile, language: str | None) -> AnswerResult:
        name = profile.name or "us"
        message = f"Hello! Thanks for texting {name}. Ask me any question, e.g. about our services, prices or opening hours."
        if language and language != "en" and self.ai is not None:
            try:
                message = (await self.ai.translation.translate(message, source="en", target=language)).text
            except Exception:
                pass
        return AnswerResult(answered=False, text=message, language=language, reason="not_a_question")

    async def _understand(self, question: str) -> tuple[str | None, str, bool]:
        """Return (customer_language, search_query, is_question)."""
        data = await chat_json(
            "You prepare a knowledge-base search. Given a customer's message, reply as json: "
            '{"language": <ISO 639-1 code of the message, ISO 639-3 if no 2-letter code>, '
            '"is_question": <false only for greetings, thanks or small talk with no request>, '
            '"question_en": <the question in English>, '
            '"keywords": [<5-12 search keywords in English and in the original language, '
            "including synonyms, product names and likely words used on a business website>]}",
            question,
            max_tokens=250,
        )
        language = normalize_language(str(data.get("language") or ""))
        keywords = data.get("keywords") or []
        query = " ".join([question, str(data.get("question_en") or ""),
                          " ".join(str(k) for k in keywords if isinstance(k, (str, int, float)))])
        return language, query, data.get("is_question") is not False

    async def _retrieve(self, query: str) -> list[tuple[KnowledgeChunk, str]]:
        rows = (await self.session.execute(
            select(KnowledgeChunk, KnowledgeSource.name)
            .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
            .where(KnowledgeSource.status == "ready")
        )).all()
        by_id = {chunk.id: (chunk, name) for chunk, name in rows}
        documents = [(chunk.id, f"{chunk.title}\n{chunk.content}") for chunk, _ in rows]
        ranked = bm25_rank(query, documents, limit=MAX_CONTEXT_CHUNKS)
        return [by_id[r.chunk_id] for r in ranked]

    async def answer(self, question: str, *, language: str | None = None) -> AnswerResult:
        question = (question or "").strip()
        profile = await self.profile()
        if not profile.assistant_enabled:
            return AnswerResult(False, "", language, reason="disabled")
        if not question:
            return await self._fallback(profile, language, "no_match")
        if not settings.ai_configured:
            # Without a model Bridge can't compose answers safely.
            return await self._fallback(profile, language, "ai_unavailable")
        if not await self.is_available():
            return await self._fallback(profile, language, "no_knowledge")

        try:
            detected, query, is_question = await self._understand(question)
            language = language or detected
            if not is_question:
                return await self._welcome(profile, language)
            retrieved = await self._retrieve(query)
        except Exception as exc:
            log_event(logger, "knowledge.understand_failed", error=str(exc))
            return await self._fallback(profile, language, "ai_unavailable")
        if not retrieved:
            return await self._fallback(profile, language, "no_match")

        sources = [
            SourceRef(chunk.id, chunk.source_id, name, chunk.title, chunk.location, chunk.content[:280])
            for chunk, name in retrieved
        ]
        context = "\n\n".join(
            f"[S{i + 1}] {chunk.title} ({chunk.location})\n{chunk.content}" for i, (chunk, _) in enumerate(retrieved)
        )
        business = profile.name or "this business"
        about = f" About the business: {profile.description.strip()}" if profile.description.strip() else ""
        reply_language = language_name(language) if language else "the same language as the customer's message"
        try:
            data = await chat_json(
                f"You are the SMS assistant for {business}.{about}\n"
                "Answer the customer's question using ONLY the facts in the CONTEXT passages. Rules:\n"
                "- If the passages do not clearly contain the answer, set answerable to false. Do not guess.\n"
                "- Never use outside knowledge. Never invent prices, dates, times, phone numbers, "
                "addresses, links, stock levels or policies.\n"
                f"- Write the answer in {reply_language}, plain text for SMS, under 300 characters, friendly and direct.\n"
                "- evidence: 1-3 short quotes copied EXACTLY (verbatim, in the passage's original language) "
                "from the passages that support the answer.\n"
                'Reply as json: {"answerable": true|false, "answer": "...", "evidence": ["..."], "sources": ["S1"]}',
                f"CONTEXT:\n{context}\n\nCUSTOMER QUESTION:\n{question}",
                max_tokens=600,
            )
        except Exception as exc:
            log_event(logger, "knowledge.answer_failed", error=str(exc))
            return await self._fallback(profile, language, "ai_unavailable", sources)

        answer = str(data.get("answer") or "").strip()
        evidence = [str(q) for q in (data.get("evidence") or []) if q]
        if not data.get("answerable") or not answer:
            return await self._fallback(profile, language, "not_in_sources", sources)
        ok, verified = verify_answer(answer, evidence, context)
        if not ok:
            log_event(logger, "knowledge.unverified_answer_blocked", answer=answer[:200])
            return await self._fallback(profile, language, "unverified", sources)

        cited = {str(s).strip().upper() for s in (data.get("sources") or [])}
        used = [ref for i, ref in enumerate(sources) if f"S{i + 1}" in cited] or sources[:1]
        if len(answer) > MAX_ANSWER_CHARS:
            answer = answer[:MAX_ANSWER_CHARS - 1].rsplit(" ", 1)[0] + "…"
        log_event(logger, "knowledge.answered", language=language, sources=[r.source_id for r in used])
        return AnswerResult(True, answer, language, "answered", used, verified)
