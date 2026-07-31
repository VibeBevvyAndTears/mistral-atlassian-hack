"""Hybrid retrieval — dense (cosine) + lexical (token overlap) RRF k=60 (T2-B).

Postgres path can later use pgvector / tsvector; SQLite/tests use in-memory
math over claim_embeddings JSON + claim text.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.models import Claim, ClaimEmbedding

RRF_K = 60


@dataclass
class HybridHit:
    claim_id: UUID
    node_id: UUID
    text: str
    score: float
    matched_via: str  # embedding | bm25 | both


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rrf_fuse(
    dense_ranked: list[UUID],
    lexical_ranked: list[UUID],
    *,
    k: int = RRF_K,
) -> dict[UUID, float]:
    scores: dict[UUID, float] = {}
    for rank, cid in enumerate(dense_ranked, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    for rank, cid in enumerate(lexical_ranked, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return scores


async def hybrid_search(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    query_text: str,
    query_embedding: list[float],
    limit: int = 20,
    model_version: str | None = None,
) -> list[HybridHit]:
    """Return top claims for a team via RRF of dense + lexical ranks."""
    claim_rows = (
        await db.execute(
            select(Claim).where(Claim.org_id == org_id, Claim.team_id == team_id)
        )
    ).scalars().all()
    if not claim_rows:
        return []

    claim_by_id = {c.id: c for c in claim_rows}
    emb_stmt = select(ClaimEmbedding).where(
        ClaimEmbedding.org_id == org_id,
        ClaimEmbedding.team_id == team_id,
    )
    if model_version:
        emb_stmt = emb_stmt.where(ClaimEmbedding.model_version == model_version)
    embeddings = (await db.execute(emb_stmt)).scalars().all()
    emb_by_claim: dict[UUID, list[float]] = {}
    for row in embeddings:
        vec = row.embedding if isinstance(row.embedding, list) else []
        emb_by_claim[row.claim_id] = [float(x) for x in vec]

    dense_scored: list[tuple[UUID, float]] = []
    for cid, vec in emb_by_claim.items():
        dense_scored.append((cid, _cosine(query_embedding, vec)))
    dense_scored.sort(key=lambda t: t[1], reverse=True)
    dense_ranked = [cid for cid, score in dense_scored if score > 0]

    q_tokens = _tokenize(query_text)
    lex_scored: list[tuple[UUID, float]] = []
    for c in claim_rows:
        tokens = _tokenize(c.text)
        if not tokens or not q_tokens:
            continue
        overlap = len(q_tokens & tokens) / len(q_tokens | tokens)
        lex_scored.append((c.id, overlap))
    lex_scored.sort(key=lambda t: t[1], reverse=True)
    lexical_ranked = [cid for cid, score in lex_scored if score > 0]

    fused = rrf_fuse(dense_ranked, lexical_ranked, k=RRF_K)
    ranked = sorted(fused.items(), key=lambda t: t[1], reverse=True)[:limit]

    hits: list[HybridHit] = []
    dense_set = set(dense_ranked[:limit])
    lex_set = set(lexical_ranked[:limit])
    for cid, score in ranked:
        claim = claim_by_id.get(cid)
        if claim is None:
            continue
        via = (
            "both"
            if cid in dense_set and cid in lex_set
            else "embedding"
            if cid in dense_set
            else "bm25"
        )
        hits.append(
            HybridHit(
                claim_id=cid,
                node_id=claim.node_id,
                text=claim.text,
                score=score,
                matched_via=via,
            )
        )
    return hits


def candidates_for_linking(hits: list[HybridHit]) -> list[dict[str, Any]]:
    return [
        {
            "claim_id": str(h.claim_id),
            "node_id": str(h.node_id),
            "text": h.text,
            "score": h.score,
            "matched_via": h.matched_via,
        }
        for h in hits
    ]
