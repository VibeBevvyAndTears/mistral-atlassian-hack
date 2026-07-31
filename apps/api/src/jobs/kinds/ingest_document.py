"""ingest_document job kind — Mistral-wired Decomposition → Claims → Linking.

Production path always uses ``MistralProvider`` (mistral-large-latest + mistral-embed).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import get_mistral_provider
from src.ai.mistral import MistralProvider
from src.graph import service as graph_service
from src.jobs import queue as job_queue
from src.jobs.queue import Job
from src.lib.config import settings
from src.pipeline.contracts._common import Chunk
from src.pipeline.contracts.claim_extraction import (
    CONTRACT_VERSION as CLAIM_CV,
)
from src.pipeline.contracts.claim_extraction import (
    ClaimExtractionInput,
    ClaimExtractionOutput,
)
from src.pipeline.contracts.decomposition import (
    CONTRACT_VERSION as DECOMP_CV,
)
from src.pipeline.contracts.decomposition import (
    DecompositionInput,
    DecompositionOutput,
)
from src.pipeline.contracts.linking import (
    CONTRACT_VERSION as LINK_CV,
)
from src.pipeline.contracts.linking import (
    LinkingInput,
    LinkingOutput,
)
from src.pipeline.errors import AgentContractError
from src.pipeline.runner import AgentStage, run_agent
from src.retrieval.hybrid import candidates_for_linking, hybrid_search
from src.tenancy.models import SourceDocument

logger = logging.getLogger(__name__)

STEP_INGEST = "ingestion"
STEP_DECOMP = "decomposition"
STEP_CLAIMS = "claim_extraction"
STEP_LINK = "linking"
STEP_CONFLICT = "conflict_intra"


async def _load_chunks(filename: str, storage_uri: str | None) -> list[Chunk]:
    """Load blob + parse text with character offsets (FR-3.1 / FR-3.2).

    Scanned/image PDFs use Mistral OCR (`mistral-ocr-latest`).
    """
    from src.ai import get_mistral_provider
    from src.documents.parse import (
        DocumentParseError,
        chunks_from_text,
        extract_text_async,
    )
    from src.lib.storage.factory import get_storage_provider

    if not storage_uri or not storage_uri.startswith("local://"):
        raise DocumentParseError("Document blob unavailable for parsing")
    rest = storage_uri.removeprefix("local://")
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise DocumentParseError("Invalid storage URI")
    try:
        data = await get_storage_provider().download(bucket, key)
    except FileNotFoundError as exc:
        raise DocumentParseError("Document blob missing from storage") from exc

    ocr = None
    try:
        ocr = get_mistral_provider()
    except (ValueError, RuntimeError):
        ocr = None
    parsed = await extract_text_async(filename, data, ocr_provider=ocr)
    return [
        Chunk(text=t, span_start=s, span_end=e, heading_path=None)
        for t, s, e in chunks_from_text(parsed.text)
    ]


async def handle_ingest_document(job: Job, session: AsyncSession) -> None:
    """Run ingest pipeline with live MistralProvider."""
    from src.documents.parse import DocumentParseError

    payload = job.payload or {}
    document_id = UUID(str(payload["document_id"]))
    team_id = UUID(str(payload["team_id"]))
    org_id = UUID(str(payload["org_id"]))

    doc = await session.get(SourceDocument, document_id)
    if doc is None or doc.org_id != org_id:
        raise RuntimeError(f"document {document_id} not found")

    steps = dict(job.completed_steps or {})

    # Always construct real Mistral provider — no FakeAI on this path.
    provider: MistralProvider = get_mistral_provider()

    if STEP_INGEST not in steps:
        doc.status = "running"
        await session.flush()
        try:
            chunks = await _load_chunks(doc.filename, doc.storage_uri)
        except DocumentParseError as exc:
            doc.status = "failed"
            await session.flush()
            raise RuntimeError(f"ingest_parse_failed: {exc}") from exc
        await job_queue.complete_step(
            session,
            job.id,
            STEP_INGEST,
            {"chunks": len(chunks), "filename": doc.filename},
        )
        steps[STEP_INGEST] = True
    else:
        chunks = await _load_chunks(doc.filename, doc.storage_uri)

    tmp_to_node: dict[str, UUID] = {}

    if STEP_DECOMP not in steps:
        try:
            decomp_out, decomp_trace = await run_agent(
                AgentStage.decomposition,
                DecompositionInput(
                    document_id=str(document_id),
                    team_id=str(team_id),
                    chunks=chunks,
                ),
                DecompositionOutput,
                provider=provider,
                contract_version=DECOMP_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
        except AgentContractError:
            doc.status = "needs_manual_review"
            await session.flush()
            raise

        tmp_to_node = await graph_service.apply_decomposition(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=document_id,
            out=decomp_out,
            trace=decomp_trace,
            job_id=job.id,
        )
        await job_queue.complete_step(
            session,
            job.id,
            STEP_DECOMP,
            {
                "nodes": len(tmp_to_node),
                "model": decomp_trace.model,
                "tmp_to_node": {k: str(v) for k, v in tmp_to_node.items()},
            },
        )
        steps[STEP_DECOMP] = True
    else:
        raw_map = (job.completed_steps or {}).get(STEP_DECOMP, {})
        stored = raw_map.get("tmp_to_node") if isinstance(raw_map, dict) else None
        if isinstance(stored, dict) and stored:
            tmp_to_node = {str(k): UUID(str(v)) for k, v in stored.items()}
        else:
            from sqlalchemy import select

            from src.graph.models import Node

            nodes = (
                await session.execute(
                    select(Node).where(
                        Node.document_id == document_id,
                        Node.org_id == org_id,
                        Node.team_id == team_id,
                    )
                )
            ).scalars().all()
            for i, n in enumerate(nodes):
                tmp_to_node[f"n{i}"] = n.id
            for n in nodes:
                tmp_to_node[str(n.id)] = n.id

    if STEP_CLAIMS not in steps:
        try:
            claim_out, claim_trace = await run_agent(
                AgentStage.claim_extraction,
                ClaimExtractionInput(
                    document_id=str(document_id),
                    team_id=str(team_id),
                    chunks=chunks,
                ),
                ClaimExtractionOutput,
                provider=provider,
                contract_version=CLAIM_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
        except AgentContractError:
            doc.status = "needs_manual_review"
            await session.flush()
            raise

        embeddings: dict[str, list[float]] = {}
        for extracted in claim_out.claims:
            vec = await provider.embed(extracted.text)
            embeddings[extracted.text] = vec

        await graph_service.apply_claims(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=document_id,
            tmp_to_node=tmp_to_node,
            out=claim_out,
            trace=claim_trace,
            embeddings=embeddings,
            model_version=settings.MISTRAL_EMBED_MODEL,
            job_id=job.id,
        )
        await job_queue.complete_step(
            session,
            job.id,
            STEP_CLAIMS,
            {"claims": len(claim_out.claims), "model": claim_trace.model},
        )
        steps[STEP_CLAIMS] = True

    if STEP_LINK not in steps:
        query_text = chunks[0].text if chunks else doc.filename
        query_embedding = await provider.embed(query_text)
        hits = await hybrid_search(
            session,
            org_id=org_id,
            team_id=team_id,
            query_text=query_text,
            query_embedding=query_embedding,
            model_version=settings.MISTRAL_EMBED_MODEL,
        )
        candidates = candidates_for_linking(hits)
        from sqlalchemy import select

        from src.graph.models import Node

        nodes = (
            await session.execute(
                select(Node).where(
                    Node.document_id == document_id,
                    Node.team_id == team_id,
                )
            )
        ).scalars().all()
        from src.pipeline.contracts._common import ProposedNode

        new_nodes = [
            ProposedNode(
                tmp_id=str(n.id),
                label=n.label,
                type=n.node_type,
                summary=n.summary,
            )
            for n in nodes
        ]
        # Remap tmp ids to stable ids for linking when resuming
        for n in nodes:
            tmp_to_node[str(n.id)] = n.id

        try:
            link_out, link_trace = await run_agent(
                AgentStage.linking,
                LinkingInput(
                    team_id=str(team_id),
                    new_nodes=new_nodes,
                    candidates=candidates,
                ),
                LinkingOutput,
                provider=provider,
                contract_version=LINK_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
        except AgentContractError:
            doc.status = "needs_manual_review"
            await session.flush()
            raise

        await graph_service.apply_linking(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=document_id,
            tmp_to_node=tmp_to_node,
            out=link_out,
            trace=link_trace,
            job_id=job.id,
        )
        await job_queue.complete_step(
            session,
            job.id,
            STEP_LINK,
            {"links": len(link_out.links), "model": link_trace.model},
        )

    if STEP_CONFLICT not in steps:
        from sqlalchemy import select

        from src.conflict import service as conflict_service
        from src.graph.models import Claim
        from src.pipeline.contracts._common import ClaimRef, ConflictScope
        from src.pipeline.contracts.conflict import (
            CONTRACT_VERSION as CONFLICT_CV,
        )
        from src.pipeline.contracts.conflict import (
            ConflictInput,
            ConflictOutput,
        )

        claims = (
            await session.execute(
                select(Claim).where(
                    Claim.org_id == org_id,
                    Claim.team_id == team_id,
                    Claim.document_id == document_id,
                )
            )
        ).scalars().all()
        claim_refs = [ClaimRef(claim_id=str(c.id), text=c.text) for c in claims]

        # Design §6.1: conflict contract failure → skip findings (prefer false negative)
        try:
            conflict_out, conflict_trace = await run_agent(
                AgentStage.conflict,
                ConflictInput(
                    scope=ConflictScope.intra_team,
                    subject_team_id=str(team_id),
                    counterpart_team_id=None,
                    claims=claim_refs,
                ),
                ConflictOutput,
                provider=provider,
                contract_version=CONFLICT_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
            await conflict_service.apply_conflict(
                session,
                org_id=org_id,
                team_id=team_id,
                document_id=document_id,
                out=conflict_out,
                trace=conflict_trace,
                job_id=job.id,
            )
            await job_queue.complete_step(
                session,
                job.id,
                STEP_CONFLICT,
                {
                    "conflicts": len(conflict_out.conflicts),
                    "model": conflict_trace.model,
                },
            )
        except AgentContractError as exc:
            logger.warning("intra-team conflict stage skipped: %s", exc)
            await job_queue.complete_step(
                session,
                job.id,
                STEP_CONFLICT,
                {"conflicts": 0, "skipped": True, "error": str(exc)},
            )

        await conflict_service.promote_decision_claims(
            session, org_id=org_id, team_id=team_id, document_id=document_id
        )

    doc.status = "ready"
    await session.flush()
    logger.info(
        "ingest_document completed",
        extra={"job_id": str(job.id), "document_id": str(document_id)},
    )
