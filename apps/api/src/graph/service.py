"""Graph write services — co-transactional with agent_traces (M2)."""

from __future__ import annotations

import difflib
import json
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.models import (
    AgentTraceRow,
    Claim,
    ClaimEmbedding,
    Edge,
    Node,
    NodeDiffResponse,
    NodeHistory,
    NodeHistoryResponse,
    NodeResponse,
    ReviewSeed,
)
from src.pipeline.contracts.claim_extraction import ClaimExtractionOutput
from src.pipeline.contracts.decomposition import DecompositionOutput
from src.pipeline.contracts.linking import LinkingOutput
from src.pipeline.trace import AgentTrace

LINK_CONFIDENCE_THRESHOLD = 0.7


def _trace_output(trace: AgentTrace) -> dict[str, Any]:
    out = trace.output
    if hasattr(out, "model_dump"):
        return out.model_dump(mode="json")  # type: ignore[no-any-return]
    return dict(out) if isinstance(out, dict) else {"value": out}


async def _persist_trace(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    trace: AgentTrace,
    job_id: UUID | None,
    document_id: UUID | None,
) -> AgentTraceRow:
    row = AgentTraceRow(
        id=uuid.uuid4(),
        org_id=org_id,
        team_id=team_id,
        job_id=job_id,
        document_id=document_id,
        stage=trace.stage,
        model=trace.model,
        prompt_version=trace.prompt_version,
        contract_version=trace.contract_version,
        input_hash=trace.input_hash,
        output=_trace_output(trace),
        cost_usd=trace.cost_usd,
        latency_ms=trace.latency_ms,
    )
    db.add(row)
    return row


async def apply_decomposition(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    document_id: UUID | None,
    out: DecompositionOutput,
    trace: AgentTrace,
    job_id: UUID | None = None,
) -> dict[str, UUID]:
    """Write nodes/edges + AgentTrace. Returns tmp_id → node_id map."""
    await _persist_trace(
        db,
        org_id=org_id,
        team_id=team_id,
        trace=trace,
        job_id=job_id,
        document_id=document_id,
    )
    tmp_to_id: dict[str, UUID] = {}
    for proposed in out.nodes:
        node_id = uuid.uuid4()
        tmp_to_id[proposed.tmp_id] = node_id
        node = Node(
            id=node_id,
            org_id=org_id,
            team_id=team_id,
            document_id=document_id,
            label=proposed.label[:255],
            node_type=proposed.type,
            summary=proposed.summary,
            search_text=f"{proposed.label} {proposed.summary}",
            version=1,
        )
        db.add(node)
        db.add(
            NodeHistory(
                id=uuid.uuid4(),
                node_id=node_id,
                org_id=org_id,
                team_id=team_id,
                version=1,
                snapshot={
                    "label": proposed.label,
                    "type": proposed.type,
                    "summary": proposed.summary,
                },
                source="decomposition",
            )
        )
    await db.flush()
    for proposed in out.nodes:
        parent_tmp = proposed.parent_tmp_id
        if parent_tmp and parent_tmp in tmp_to_id:
            node = await db.get(Node, tmp_to_id[proposed.tmp_id])
            if node is not None:
                node.parent_id = tmp_to_id[parent_tmp]
    for edge in out.edges:
        if edge.from_tmp_id not in tmp_to_id or edge.to_tmp_id not in tmp_to_id:
            continue
        db.add(
            Edge(
                id=uuid.uuid4(),
                org_id=org_id,
                team_id=team_id,
                from_node_id=tmp_to_id[edge.from_tmp_id],
                to_node_id=tmp_to_id[edge.to_tmp_id],
                relation=edge.relation,
            )
        )
    await db.flush()
    return tmp_to_id


async def apply_claims(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    document_id: UUID | None,
    tmp_to_node: dict[str, UUID],
    out: ClaimExtractionOutput,
    trace: AgentTrace,
    embeddings: dict[str, list[float]],
    model_version: str,
    job_id: UUID | None = None,
) -> list[Claim]:
    await _persist_trace(
        db,
        org_id=org_id,
        team_id=team_id,
        trace=trace,
        job_id=job_id,
        document_id=document_id,
    )
    created: list[Claim] = []
    for extracted in out.claims:
        node_id = tmp_to_node.get(extracted.node_tmp_id)
        if node_id is None:
            continue
        claim = Claim(
            id=uuid.uuid4(),
            org_id=org_id,
            team_id=team_id,
            node_id=node_id,
            document_id=document_id,
            text=extracted.text,
            claim_type=str(extracted.claim_type),
            span_start=extracted.span_start,
            span_end=extracted.span_end,
            confidence=extracted.confidence,
        )
        db.add(claim)
        created.append(claim)
        vec = embeddings.get(extracted.text) or embeddings.get(str(claim.id))
        if vec:
            db.add(
                ClaimEmbedding(
                    id=uuid.uuid4(),
                    claim_id=claim.id,
                    org_id=org_id,
                    team_id=team_id,
                    model_version=model_version,
                    embedding=vec,
                )
            )
    await db.flush()
    # Embed by claim id after flush if keyed by text
    for claim in created:
        if claim.id in {c.id for c in created}:
            vec = embeddings.get(claim.text)
            if vec is None:
                continue
            existing = await db.execute(
                select(ClaimEmbedding).where(
                    ClaimEmbedding.claim_id == claim.id,
                    ClaimEmbedding.model_version == model_version,
                )
            )
            if existing.scalar_one_or_none() is None:
                db.add(
                    ClaimEmbedding(
                        id=uuid.uuid4(),
                        claim_id=claim.id,
                        org_id=org_id,
                        team_id=team_id,
                        model_version=model_version,
                        embedding=vec,
                    )
                )
    await db.flush()
    return created


async def apply_linking(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    document_id: UUID | None,
    tmp_to_node: dict[str, UUID],
    out: LinkingOutput,
    trace: AgentTrace,
    job_id: UUID | None = None,
    confidence_threshold: float = LINK_CONFIDENCE_THRESHOLD,
) -> None:
    await _persist_trace(
        db,
        org_id=org_id,
        team_id=team_id,
        trace=trace,
        job_id=job_id,
        document_id=document_id,
    )
    for link in out.links:
        new_id = tmp_to_node.get(link.new_node_tmp_id)
        if new_id is None:
            continue
        existing: UUID | None = None
        if link.existing_node_id is not None:
            existing = UUID(str(link.existing_node_id))
        if existing is not None and link.confidence >= confidence_threshold:
            db.add(
                Edge(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    team_id=team_id,
                    from_node_id=new_id,
                    to_node_id=existing,
                    relation=link.relation,
                    confidence=link.confidence,
                )
            )
        elif link.confidence < confidence_threshold:
            db.add(
                ReviewSeed(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    team_id=team_id,
                    reason=(
                        f"Low-confidence link ({link.confidence:.2f}): "
                        f"{link.rationale}"
                    ),
                    new_node_tmp_id=link.new_node_tmp_id,
                    existing_node_id=existing,
                    confidence=link.confidence,
                    payload={"relation": link.relation},
                )
            )
    for seed in out.review_items:
        existing = (
            UUID(str(seed.existing_node_id))
            if seed.existing_node_id is not None
            else None
        )
        db.add(
            ReviewSeed(
                id=uuid.uuid4(),
                org_id=org_id,
                team_id=team_id,
                reason=seed.reason,
                new_node_tmp_id=seed.new_node_tmp_id,
                existing_node_id=existing,
                confidence=seed.confidence,
                payload={},
            )
        )
    await db.flush()


async def list_nodes(
    db: AsyncSession, *, org_id: UUID, team_id: UUID
) -> list[NodeResponse]:
    rows = (
        (
            await db.execute(
                select(Node)
                .where(Node.org_id == org_id, Node.team_id == team_id)
                .order_by(Node.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        NodeResponse(
            id=str(n.id),
            team_id=str(n.team_id),
            org_id=str(n.org_id),
            label=n.label,
            node_type=n.node_type,
            summary=n.summary,
            parent_id=str(n.parent_id) if n.parent_id else None,
            version=n.version,
            document_id=str(n.document_id) if n.document_id else None,
            created_at=n.created_at,
        )
        for n in rows
    ]


async def list_node_history(
    db: AsyncSession, *, org_id: UUID, team_id: UUID, node_id: UUID
) -> list[NodeHistoryResponse]:
    node = await db.get(Node, node_id)
    if node is None or node.org_id != org_id or node.team_id != team_id:
        return []
    rows = (
        (
            await db.execute(
                select(NodeHistory)
                .where(NodeHistory.node_id == node_id, NodeHistory.org_id == org_id)
                .order_by(NodeHistory.version.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        NodeHistoryResponse(
            id=str(h.id),
            node_id=str(h.node_id),
            version=h.version,
            snapshot=h.snapshot or {},
            source=h.source,
            created_at=h.created_at,
        )
        for h in rows
    ]


async def get_node_diff(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    node_id: UUID,
    from_version: int,
    to_version: int,
) -> NodeDiffResponse | None:
    node = await db.get(Node, node_id)
    if node is None or node.org_id != org_id or node.team_id != team_id:
        return None
    rows = (
        (
            await db.execute(
                select(NodeHistory).where(
                    NodeHistory.node_id == node_id,
                    NodeHistory.org_id == org_id,
                    NodeHistory.version.in_((from_version, to_version)),
                )
            )
        )
        .scalars()
        .all()
    )
    by_version = {row.version: row for row in rows}
    if from_version not in by_version or to_version not in by_version:
        return None
    before = json.dumps(
        by_version[from_version].snapshot or {},
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ).splitlines()
    after = json.dumps(
        by_version[to_version].snapshot or {},
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ).splitlines()
    diff = "\n".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"version-{from_version}",
            tofile=f"version-{to_version}",
            lineterm="",
        )
    )
    return NodeDiffResponse(
        node_id=str(node_id),
        from_version=from_version,
        to_version=to_version,
        diff=diff,
    )
