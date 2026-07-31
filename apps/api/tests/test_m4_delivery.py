"""M4 delivery tests — checklist, channels, packages; Mistral wiring on send_package."""

from __future__ import annotations

import inspect
import uuid

from fastapi.testclient import TestClient

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


def _two_teams(client: TestClient) -> dict[str, str]:
    token = _register(client, f"m4-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "M4"}, headers=_auth(token)).json()
    org_id = org["id"]
    t1 = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "Sender"},
        headers=_auth(token, org_id),
    ).json()["id"]
    t2 = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "Receiver"},
        headers=_auth(token, org_id),
    ).json()["id"]
    # profile required for checklist
    put = client.put(
        f"/api/teams/{t1}/profile",
        json={"data": {"tone": "plain"}},
        headers=_auth(token, org_id, t1),
    )
    assert put.status_code == 200, put.text
    return {"token": token, "org": org_id, "team_a": t1, "team_b": t2}


def test_send_package_kind_uses_mistral() -> None:
    from src.jobs.kinds import send_package as mod

    src = inspect.getsource(mod)
    assert "get_mistral_provider" in src
    assert "FakeAIProvider(" not in src
    assert "AgentStage.adaptation" in src
    assert "AgentStage.judge" in src


def test_rendition_policy_fail_closed() -> None:
    from src.pipeline.contracts._common import DetailDepth, FidelityVerdict, FitVerdict
    from src.pipeline.contracts.judge import (
        AudienceFitResult,
        FidelityResult,
        JudgeOutput,
    )
    from src.pipeline.policies import RenditionAction, RenditionPolicy

    fail = JudgeOutput(
        fidelity=FidelityResult(verdict=FidelityVerdict.fail, rationale="x"),
        audience_fit=AudienceFitResult(
            verdict=FitVerdict.pass_ok,
            jargon_appropriate=True,
            detail_depth_match=DetailDepth.ok,
            rationale="y",
        ),
        overall_confidence=0.2,
    )
    assert (
        RenditionPolicy.on_verdict(fail, fidelity_attempt=0, fit_attempt=0)
        == RenditionAction.retry_fidelity
    )
    assert (
        RenditionPolicy.on_verdict(fail, fidelity_attempt=1, fit_attempt=0)
        == RenditionAction.show_original_with_warning
    )


def test_channel_package_checklist_and_send_enqueue(client: TestClient) -> None:
    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

    # idempotent pair
    ch2 = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_b"], "team_b_id": t["team_a"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert ch2.status_code == 201
    assert ch2.json()["id"] == channel_id

    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert pkg.status_code == 201, pkg.text
    body = pkg.json()
    assert body["checklist"]["ok"] is True
    assert body["channel_id"] == channel_id

    got = client.get(
        f"/api/packages/{body['id']}",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert got.status_code == 200

    sent = client.post(
        f"/api/packages/{body['id']}/send",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sending"
    assert sent.json()["job_id"] is not None

    feed = client.get(
        f"/api/channels/{channel_id}/posts",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert feed.status_code == 200
    assert feed.json() == []


def test_package_cross_tenant_404(client: TestClient) -> None:
    t = _two_teams(client)
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "X",
            "body": "Y",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()
    token_b = _register(client, f"out-{uuid.uuid4().hex[:8]}@example.com")
    org_b = client.post("/api/orgs", json={"name": "Other"}, headers=_auth(token_b)).json()["id"]  # noqa: E501
    team_b = client.post(
        f"/api/orgs/{org_b}/teams",
        json={"name": "OT"},
        headers=_auth(token_b, org_b),
    ).json()["id"]
    resp = client.get(
        f"/api/packages/{pkg['id']}",
        headers=_auth(token_b, t["org"], t["team_a"]),
    )
    assert resp.status_code == 404
    # sanity own scope
    _ = team_b
