"""M2 graph + hybrid retrieval tests (apply path without live Mistral).

Ingest handler is asserted to require MistralProvider — live calls are not
made in CI; FakeAI is never imported by the ingest kind module.
"""

from __future__ import annotations

import inspect
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.graph import service as graph_service
from src.pipeline.contracts._common import (
    ClaimType,
    ExtractedClaim,
    ProposedNode,
    ReviewSeed,
)
from src.pipeline.contracts.claim_extraction import ClaimExtractionOutput
from src.pipeline.contracts.decomposition import DecompositionOutput
from src.pipeline.contracts.linking import LinkingOutput, LinkProposal
from src.pipeline.trace import AgentTrace
from src.retrieval.hybrid import rrf_fuse
from tests.test_auth import _reset_all


def _register(client: TestClient, email: str) -> str:
    _reset_all()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "username": "".join(c if c.isalnum() or c=="_" else "_" for c in email.split("@")[0].lower())[:32], "name": "T"},  # noqa: E501
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str, org_id: str | None = None, team_id: str | None = None) -> dict[str, str]:  # noqa: E501
    headers = {"Authorization": f"Bearer {token}"}
    if org_id:
        headers["X-Org-Id"] = org_id
    if team_id:
        headers["X-Team-Id"] = team_id
    return headers


@pytest.fixture
def tenant(client: TestClient) -> dict[str, str]:
    token = _register(client, f"g-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "G"}, headers=_auth(token))
    assert org.status_code == 201
    org_id = org.json()["id"]
    team = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "T"},
        headers=_auth(token, org_id),
    )
    assert team.status_code == 201
    return {"token": token, "org": org_id, "team": team.json()["id"]}


def test_rrf_k_is_60() -> None:
    from src.retrieval import hybrid as hybrid_mod

    assert hybrid_mod.RRF_K == 60
    scores = rrf_fuse(
        [uuid.uuid4(), uuid.uuid4()],
        [uuid.uuid4()],
        k=60,
    )
    assert scores


def test_ingest_kind_wires_mistral_not_fake() -> None:
    from src.jobs.kinds import ingest_document as mod

    src = inspect.getsource(mod.handle_ingest_document)
    assert "get_mistral_provider" in src
    assert "from src.lib.ai.fakes" not in inspect.getsource(mod)
    assert "FakeAIProvider(" not in inspect.getsource(mod)


def _trace(stage: str, output: BaseModel) -> AgentTrace:
    return AgentTrace(
        stage=stage,
        model="mistral-large-latest",
        contract_version="1.0.0",
        input_hash="abc",
        output=output,
    )


@pytest.mark.asyncio
async def test_apply_decomposition_and_list_nodes(
    client: TestClient, tenant: dict[str, str]
) -> None:
    from src.lib.database import async_session_factory

    org_id = UUID(tenant["org"])
    team_id = UUID(tenant["team"])
    out = DecompositionOutput(
        nodes=[
            ProposedNode(
                tmp_id="n1",
                label="Auth",
                type="topic",
                summary="Authentication flows",
            )
        ],
        edges=[],
    )
    async with async_session_factory() as session:
        mapping = await graph_service.apply_decomposition(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            out=out,
            trace=_trace("decomposition", out),
        )
        await session.commit()
        assert "n1" in mapping

    listed = client.get(
        f"/api/teams/{tenant['team']}/nodes",
        headers=_auth(tenant["token"], tenant["org"], tenant["team"]),
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) >= 1
    node_id = listed.json()[0]["id"]
    hist = client.get(
        f"/api/nodes/{node_id}/history",
        headers=_auth(tenant["token"], tenant["org"], tenant["team"]),
    )
    assert hist.status_code == 200
    assert hist.json()[0]["version"] == 1


@pytest.mark.asyncio
async def test_apply_claims_and_linking(
    client: TestClient, tenant: dict[str, str]
) -> None:
    from src.lib.database import async_session_factory

    org_id = UUID(tenant["org"])
    team_id = UUID(tenant["team"])
    decomp = DecompositionOutput(
        nodes=[
            ProposedNode(tmp_id="a", label="A", type="topic", summary="sa"),
            ProposedNode(tmp_id="b", label="B", type="topic", summary="sb"),
        ]
    )
    async with async_session_factory() as session:
        mapping = await graph_service.apply_decomposition(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            out=decomp,
            trace=_trace("decomposition", decomp),
        )
        claims_out = ClaimExtractionOutput(
            claims=[
                ExtractedClaim(
                    node_tmp_id="a",
                    text="Users must MFA",
                    claim_type=ClaimType.requirement,
                    span_start=0,
                    span_end=14,
                    confidence=0.9,
                )
            ]
        )
        await graph_service.apply_claims(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            tmp_to_node=mapping,
            out=claims_out,
            trace=_trace("claim_extraction", claims_out),
            embeddings={"Users must MFA": [0.1, 0.2, 0.3]},
            model_version="mistral-embed",
        )
        link_out = LinkingOutput(
            links=[
                LinkProposal(
                    new_node_tmp_id="a",
                    existing_node_id=str(mapping["b"]),
                    relation="related",
                    confidence=0.4,
                    rationale="weak",
                )
            ],
            review_items=[
                ReviewSeed(reason="manual", new_node_tmp_id="a", confidence=0.4)
            ],
        )
        await graph_service.apply_linking(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            tmp_to_node=mapping,
            out=link_out,
            trace=_trace("linking", link_out),
        )
        await session.commit()

        from sqlalchemy import select

        from src.graph.models import ReviewSeed as ReviewSeedRow

        seeds = (
            await session.execute(
                select(ReviewSeedRow).where(ReviewSeedRow.team_id == team_id)
            )
        ).scalars().all()
        assert len(seeds) >= 1


def test_resolve_tmp_node_id_maps_llm_prefix_variants() -> None:
    """Regression: claim extraction emits tmp_N while decomposition uses node_N."""
    node_1 = uuid.uuid4()
    node_2 = uuid.uuid4()
    mapping = {"node_1": node_1, "node_2": node_2}
    assert graph_service.resolve_tmp_node_id(mapping, "tmp_1") == node_1
    assert graph_service.resolve_tmp_node_id(mapping, "tmp_2") == node_2
    assert graph_service.resolve_tmp_node_id(mapping, "node_1") == node_1
    assert graph_service.resolve_tmp_node_id(mapping, "n1") == node_1
    assert graph_service.resolve_tmp_node_id({}, "tmp_1") is None
    # Unknown id still falls back to first mapped node (avoid silent claim drop)
    assert graph_service.resolve_tmp_node_id(mapping, "orphan_x") in {node_1, node_2}


@pytest.mark.asyncio
async def test_apply_claims_persists_when_tmp_prefix_mismatches(
    client: TestClient, tenant: dict[str, str]
) -> None:
    """Claims must persist when LLM uses tmp_1 but decomp used node_1."""
    from sqlalchemy import select

    from src.graph.models import Claim
    from src.lib.database import async_session_factory

    org_id = UUID(tenant["org"])
    team_id = UUID(tenant["team"])
    decomp = DecompositionOutput(
        nodes=[
            ProposedNode(tmp_id="node_1", label="Ship", type="decision", summary="s"),
        ]
    )
    async with async_session_factory() as session:
        mapping = await graph_service.apply_decomposition(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            out=decomp,
            trace=_trace("decomposition", decomp),
        )
        claims_out = ClaimExtractionOutput(
            claims=[
                ExtractedClaim(
                    node_tmp_id="tmp_1",
                    text="We will ship on Friday",
                    claim_type=ClaimType.decision,
                    span_start=0,
                    span_end=22,
                    confidence=0.95,
                )
            ]
        )
        created = await graph_service.apply_claims(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            tmp_to_node=mapping,
            out=claims_out,
            trace=_trace("claim_extraction", claims_out),
            embeddings={},
            model_version="mistral-embed",
        )
        await session.commit()
        assert len(created) == 1
        assert created[0].node_id == mapping["node_1"]
        rows = (
            await session.execute(select(Claim).where(Claim.team_id == team_id))
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].text == "We will ship on Friday"


@pytest.mark.asyncio
async def test_apply_linking_resolves_tmp_prefix_mismatch(
    client: TestClient, tenant: dict[str, str]
) -> None:
    """Link edges must resolve tmp_N → node_N the same way claims do."""
    from sqlalchemy import select

    from src.graph.models import Edge
    from src.lib.database import async_session_factory

    org_id = UUID(tenant["org"])
    team_id = UUID(tenant["team"])
    decomp = DecompositionOutput(
        nodes=[
            ProposedNode(tmp_id="node_1", label="A", type="topic", summary="a"),
            ProposedNode(tmp_id="node_2", label="B", type="topic", summary="b"),
        ]
    )
    async with async_session_factory() as session:
        mapping = await graph_service.apply_decomposition(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            out=decomp,
            trace=_trace("decomposition", decomp),
        )
        link_out = LinkingOutput(
            links=[
                LinkProposal(
                    new_node_tmp_id="tmp_1",
                    existing_node_id=str(mapping["node_2"]),
                    relation="related",
                    confidence=0.95,
                    rationale="aligned",
                )
            ],
            review_items=[],
        )
        await graph_service.apply_linking(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            tmp_to_node=mapping,
            out=link_out,
            trace=_trace("linking", link_out),
        )
        await session.commit()
        edges = (
            await session.execute(select(Edge).where(Edge.team_id == team_id))
        ).scalars().all()
        assert len(edges) == 1
        assert edges[0].from_node_id == mapping["node_1"]
        assert edges[0].to_node_id == mapping["node_2"]


def test_nodes_cross_tenant_404(client: TestClient, tenant: dict[str, str]) -> None:
    token_b = _register(client, f"x-{uuid.uuid4().hex[:8]}@example.com")
    org_b = client.post("/api/orgs", json={"name": "B"}, headers=_auth(token_b))
    org_b_id = org_b.json()["id"]
    client.post(
        f"/api/orgs/{org_b_id}/teams",
        json={"name": "TB"},
        headers=_auth(token_b, org_b_id),
    )
    resp = client.get(
        f"/api/teams/{tenant['team']}/nodes",
        headers=_auth(token_b, tenant["org"], tenant["team"]),
    )
    assert resp.status_code == 404
