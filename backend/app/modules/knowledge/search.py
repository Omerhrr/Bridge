"""Keyword retrieval (BM25) over knowledge chunks.

DeepSeek offers no embeddings endpoint, so retrieval is lexical. To handle
questions asked in other languages, the assistant first rewrites the question
into search keywords in the knowledge base's language (see assistant.py) and
searches with those.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = set(
    "a an and are as at be but by for from has have how i if in into is it its me my of on or our "
    "so that the their them then there these they this to was we what when where which who why will "
    "with you your do does can could would should please tell about any".split()
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in _TOKEN.findall(text.lower()):
        if raw in _STOPWORDS or (len(raw) < 2 and not raw.isdigit()):
            continue
        # Light plural folding: "prices" -> "price", "hours" -> "hour".
        if len(raw) > 4 and raw.endswith("s") and not raw.endswith("ss"):
            raw = raw[:-1]
        tokens.append(raw)
    return tokens


@dataclass
class ScoredChunk:
    chunk_id: int
    score: float


def bm25_rank(query: str, documents: list[tuple[int, str]], limit: int = 6,
              k1: float = 1.5, b: float = 0.75) -> list[ScoredChunk]:
    query_terms = set(tokenize(query))
    if not query_terms or not documents:
        return []
    doc_tokens = [(doc_id, Counter(tokenize(text))) for doc_id, text in documents]
    lengths = [sum(counts.values()) for _, counts in doc_tokens]
    avg_len = (sum(lengths) / len(lengths)) or 1.0
    n = len(doc_tokens)
    df = Counter()
    for _, counts in doc_tokens:
        for term in query_terms & counts.keys():
            df[term] += 1

    scored = []
    for (doc_id, counts), length in zip(doc_tokens, lengths):
        score = 0.0
        for term in query_terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg_len))
        if score > 0:
            scored.append(ScoredChunk(doc_id, score))
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]
