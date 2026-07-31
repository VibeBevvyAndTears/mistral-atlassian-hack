"""M1 cross-tenant access tests — foreign org/team → 404 not 403."""

from __future__ import annotations

import io
import uuid

import pytest
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


@pytest.fixture
def two_tenants(client: TestClient) -> dict[str, str]:
    token_a = _register(client, f"a-{uuid.uuid4().hex[:8]}@example.com")
    org_a = client.post(
        "/api/orgs",
        json={"name": "Org A"},
        headers=_auth(token_a),
    )
    assert org_a.status_code == 201, org_a.text
    org_a_id = org_a.json()["id"]

    team_a = client.post(
        f"/api/orgs/{org_a_id}/teams",
        json={"name": "Team A"},
        headers=_auth(token_a, org_a_id),
    )
    assert team_a.status_code == 201, team_a.text
    team_a_id = team_a.json()["id"]

    # Seed profile for GET tests
    put = client.put(
        f"/api/teams/{team_a_id}/profile",
        json={"data": {"tone": "formal"}},
        headers=_auth(token_a, org_a_id, team_a_id),
    )
    assert put.status_code == 200, put.text

    token_b = _register(client, f"b-{uuid.uuid4().hex[:8]}@example.com")
    org_b = client.post(
        "/api/orgs",
        json={"name": "Org B"},
        headers=_auth(token_b),
    )
    assert org_b.status_code == 201
    org_b_id = org_b.json()["id"]
    team_b = client.post(
        f"/api/orgs/{org_b_id}/teams",
        json={"name": "Team B"},
        headers=_auth(token_b, org_b_id),
    )
    assert team_b.status_code == 201
    team_b_id = team_b.json()["id"]

    return {
        "token_a": token_a,
        "org_a": org_a_id,
        "team_a": team_a_id,
        "token_b": token_b,
        "org_b": org_b_id,
        "team_b": team_b_id,
    }


def test_m1_cross_tenant_create_team_returns_404(
    client: TestClient, two_tenants: dict[str, str]
) -> None:
    t = two_tenants
    # User B forges Org A's id
    resp = client.post(
        f"/api/orgs/{t['org_a']}/teams",
        json={"name": "Hijack"},
        headers=_auth(t["token_b"], t["org_a"]),
    )
    assert resp.status_code == 404


def test_m1_cross_tenant_profile_returns_404(
    client: TestClient, two_tenants: dict[str, str]
) -> None:
    t = two_tenants
    resp = client.get(
        f"/api/teams/{t['team_a']}/profile",
        headers=_auth(t["token_b"], t["org_a"], t["team_a"]),
    )
    assert resp.status_code == 404


def test_m1_cross_tenant_document_get_returns_404(
    client: TestClient, two_tenants: dict[str, str]
) -> None:
    t = two_tenants
    upload = client.post(
        f"/api/teams/{t['team_a']}/documents",
        headers=_auth(t["token_a"], t["org_a"], t["team_a"]),
        files={"file": ("spec.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]

    resp = client.get(
        f"/api/documents/{doc_id}",
        headers=_auth(t["token_b"], t["org_b"], t["team_b"]),
    )
    assert resp.status_code == 404


def test_m1_happy_path_org_team_profile_document(
    client: TestClient, two_tenants: dict[str, str]
) -> None:
    t = two_tenants
    profile = client.get(
        f"/api/teams/{t['team_a']}/profile",
        headers=_auth(t["token_a"], t["org_a"], t["team_a"]),
    )
    assert profile.status_code == 200
    assert profile.json()["version"] == 1

    invite = client.post(
        f"/api/teams/{t['team_a']}/invites",
        json={"email": "new@example.com", "role": "member"},
        headers=_auth(t["token_a"], t["org_a"], t["team_a"]),
    )
    assert invite.status_code == 201
    assert "token" in invite.json()
