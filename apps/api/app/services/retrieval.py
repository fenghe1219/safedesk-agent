from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User

EMBEDDING_DIMENSION = 192
MIN_RELEVANCE = 0.2

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+")
_STOPWORDS = {
    "的",
    "了",
    "是",
    "在",
    "我",
    "你",
    "他",
    "她",
    "它",
    "们",
    "和",
    "与",
    "及",
    "或",
    "就",
    "都",
    "也",
    "还",
    "有",
    "没有",
    "一个",
    "这个",
    "那个",
    "怎么",
    "如何",
    "为什么",
    "可以",
    "需要",
    "现在",
    "今天",
    "一直",
    "提示",
}


@dataclass(frozen=True)
class RetrievalHit:
    document: KnowledgeDocument
    chunk: KnowledgeChunk
    lexical: float
    semantic: float
    score: float


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for part in _TOKEN_RE.findall(text.lower()):
        if part.isascii():
            if len(part) >= 2 and part not in _STOPWORDS:
                tokens.append(part)
            continue
        if part in _STOPWORDS:
            continue
        chars = [char for char in part if char not in _STOPWORDS]
        tokens.extend(chars)
        tokens.extend(part[index : index + 2] for index in range(len(part) - 1))
        tokens.extend(part[index : index + 3] for index in range(len(part) - 2))
    return tokens


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    for token, count in Counter(tokenize(text)).items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % EMBEDDING_DIMENSION
        sign = 1.0 if (value >> 8) & 1 else -1.0
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def acl_allows(acl: dict[str, Any] | None, department: str) -> bool:
    if not acl:
        return True
    departments = acl.get("departments") or []
    return not departments or department in departments or "全员" in departments


async def retrieve_chunks(
    db: AsyncSession,
    query: str,
    requester: User,
    limit: int = 5,
) -> list[RetrievalHit]:
    result = await db.execute(
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.doc_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.status == "READY")
    )
    rows = result.all()
    if not rows:
        return []

    query_terms = Counter(tokenize(query))
    if not query_terms:
        return []
    query_vector = embed_text(query)
    hits: list[RetrievalHit] = []

    for chunk, document in rows:
        if not acl_allows(document.acl, requester.department):
            continue
        chunk_terms = Counter(tokenize(f"{document.title} {chunk.section} {chunk.content}"))
        matched = 0.0
        total = 0.0
        for term, count in query_terms.items():
            weight = 1.0 + min(len(term), 4) * 0.25
            total += count * weight
            if term in chunk_terms:
                matched += min(count, chunk_terms[term]) * weight
        lexical = matched / total if total else 0.0
        semantic = max(0.0, cosine(query_vector, chunk.embedding or []))
        score = lexical * 0.72 + semantic * 0.28
        if score >= MIN_RELEVANCE:
            hits.append(
                RetrievalHit(
                    document=document,
                    chunk=chunk,
                    lexical=round(lexical, 4),
                    semantic=round(semantic, 4),
                    score=round(score, 4),
                )
            )

    hits.sort(key=lambda item: (item.score, item.lexical), reverse=True)
    return hits[:limit]


def select_quote(content: str, query: str, max_length: int = 260) -> str:
    query_terms = set(tokenize(query))
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        paragraphs = [content.strip()]
    ranked = sorted(
        paragraphs,
        key=lambda part: sum(1 for term in tokenize(part) if term in query_terms),
        reverse=True,
    )
    quote = ranked[0] if ranked else content.strip()
    if len(quote) <= max_length:
        return quote
    cut = quote[:max_length]
    boundary = max(cut.rfind("。"), cut.rfind("\n"), cut.rfind("；"))
    if boundary >= 80:
        return quote[: boundary + 1]
    return cut.rstrip()
