"""M3 conflict / decisions tests."""

from __future__ import annotations

import inspect
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.conflict import service as conflict_service
from src.graph import service as graph_service
from src.pipeline.contracts._common import (
    ClaimType,
    ConflictClass,
    ConflictSeverity,
    ExtractedClaim,
    MatchedVia,
    ProposedNode,
)
from src.pipeline.contracts.claim_extraction import ClaimExtractionOutput
from src.pipeline.contracts.conflict import ConflictItem, ConflictOutput
from src.pipeline.contracts.decomposition import DecompositionOutput
from src.pipeline.trace import AgentTrace
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
    token = _register(client, f"c-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "C"}, headers=_auth(token))
    org_id = org.json()["id"]
    team = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "T"},
        headers=_auth(token, org_id),
    )
    return {"token": token, "org": org_id, "team": team.json()["id"]}


def test_ingest_conflict_step_uses_mistral() -> None:
    from src.jobs.kinds import ingest_document as mod

    src = inspect.getsource(mod.handle_ingest_document)
    assert "STEP_CONFLICT" in inspect.getsource(mod)
    assert "get_mistral_provider" in inspect.getsource(mod)
    assert "AgentStage.conflict" in src
    assert "FakeAIProvider(" not in inspect.getsource(mod)


def _trace(stage: str, output: object) -> AgentTrace:
    return AgentTrace(
        stage=stage,
        model="mistral-large-latest",
        contract_version="1.0.0",
        input_hash="x",
        output=output,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_apply_conflict_propose_resolve_and_decisions(
    client: TestClient, tenant: dict[str, str]
) -> None:
    from src.lib.database import async_session_factory

    org_id = UUID(tenant["org"])
    team_id = UUID(tenant["team"])

    async with async_session_factory() as session:
        decomp = DecompositionOutput(
            nodes=[
                ProposedNode(tmp_id="n1", label="A", type="topic", summary="a"),
                ProposedNode(tmp_id="n2", label="B", type="topic", summary="b"),
            ]
        )
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
                    node_tmp_id="n1",
                    text="Ship Friday",
                    claim_type=ClaimType.decision,
                    span_start=0,
                    span_end=11,
                    confidence=0.9,
                ),
                ExtractedClaim(
                    node_tmp_id="n2",
                    text="Ship Monday",
                    claim_type=ClaimType.fact,
                    span_start=0,
                    span_end=11,
                    confidence=0.8,
                ),
            ]
        )
        claims = await graph_service.apply_claims(
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
        assert len(claims) == 2
        conflict_out = ConflictOutput(
            conflicts=[
                ConflictItem(
                    claim_a_id=str(claims[0].id),
                    claim_b_id=str(claims[1].id),
                    class_=ConflictClass.contradiction,
                    severity=ConflictSeverity.high,
                    rationale="Dates conflict",
                    matched_via=MatchedVia.both,
                )
            ]
        )
        await conflict_service.apply_conflict(
            session,
            org_id=org_id,
            team_id=team_id,
            document_id=None,
            out=conflict_out,
            trace=_trace("conflict", conflict_out),
        )
        await conflict_service.promote_decision_claims(
            session, org_id=org_id, team_id=team_id
        )
        await session.commit()

    listed = client.get(
        f"/api/teams/{tenant['team']}/review-items",
        headers=_auth(tenant["token"], tenant["org"], tenant["team"]),
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) >= 1
    item_id = listed.json()[0]["id"]

    proposed = client.post(
        f"/api/review-items/{item_id}/propose",
        json={"resolution": "keep_a"},
        headers=_auth(tenant["token"], tenant["org"], tenant["team"]),
    )
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["status"] == "proposed"

    resolved = client.post(
        f"/api/review-items/{item_id}/resolve",
        json={"resolution": "keep_both"},
        headers=_auth(tenant["token"], tenant["org"], tenant["team"]),
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"

    decisions = client.get(
        f"/api/teams/{tenant['team']}/decisions",
        headers=_auth(tenant["token"], tenant["org"], tenant["team"]),
    )
    assert decisions.status_code == 200
    assert any(d["title"] == "Ship Friday" for d in decisions.json())


def test_review_items_cross_tenant_404(client: TestClient, tenant: dict[str, str]) -> None:  # noqa: E501
    token_b = _register(client, f"z-{uuid.uuid4().hex[:8]}@example.com")
    org_b = client.post("/api/orgs", json={"name": "Z"}, headers=_auth(token_b)).json()["id"]  # noqa: E501
    team_b = client.post(
        f"/api/orgs/{org_b}/teams",
        json={"name": "ZT"},
        headers=_auth(token_b, org_b),
    ).json()["id"]
    resp = client.get(
        f"/api/teams/{tenant['team']}/review-items",
        headers=_auth(token_b, tenant["org"], tenant["team"]),
    )
    assert resp.status_code == 404
    # own team empty ok
    own = client.get(
        f"/api/teams/{team_b}/review-items",
        headers=_auth(token_b, org_b, team_b),
    )
    assert own.status_code == 200
    assert own.json() == []
