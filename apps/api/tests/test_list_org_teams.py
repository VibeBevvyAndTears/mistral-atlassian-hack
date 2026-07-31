"""List org teams / my teams for channel sidebar."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.test_m1_cross_tenant import _auth, _register


def test_list_org_teams_and_mine_only(client: TestClient) -> None:
    token = _register(client, f"list-teams-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "List Org"}, headers=_auth(token))
    assert org.status_code == 201, org.text
    org_id = org.json()["id"]

    team_a = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "Alpha"},
        headers=_auth(token, org_id),
    )
    team_b = client.post(
        f"/api/orgs/{org_id}/teams",
        json={"name": "Beta"},
        headers=_auth(token, org_id),
    )
    assert team_a.status_code == 201, team_a.text
    assert team_b.status_code == 201, team_b.text

    all_teams = client.get(
        f"/api/orgs/{org_id}/teams",
        headers=_auth(token, org_id, team_a.json()["id"]),
    )
    assert all_teams.status_code == 200, all_teams.text
    names = {row["name"] for row in all_teams.json()}
    assert names == {"Alpha", "Beta"}

    mine = client.get(
        f"/api/orgs/{org_id}/teams",
        params={"mine_only": True},
        headers=_auth(token, org_id, team_a.json()["id"]),
    )
    assert mine.status_code == 200, mine.text
    mine_names = {row["name"] for row in mine.json()}
    assert mine_names == {"Alpha", "Beta"}


def test_list_org_teams_cross_tenant_404(client: TestClient) -> None:
    token_a = _register(client, f"a-{uuid.uuid4().hex[:8]}@example.com")
    org_a = client.post("/api/orgs", json={"name": "A"}, headers=_auth(token_a)).json()
    team_a = client.post(
        f"/api/orgs/{org_a['id']}/teams",
        json={"name": "TA"},
        headers=_auth(token_a, org_a["id"]),
    ).json()

    token_b = _register(client, f"b-{uuid.uuid4().hex[:8]}@example.com")
    org_b = client.post("/api/orgs", json={"name": "B"}, headers=_auth(token_b)).json()

    resp = client.get(
        f"/api/orgs/{org_a['id']}/teams",
        headers=_auth(token_b, org_a["id"], team_a["id"]),
    )
    assert resp.status_code == 404

    # B with own org header but forged path still 404 (scope.org_id != path)
    resp2 = client.get(
        f"/api/orgs/{org_a['id']}/teams",
        headers=_auth(token_b, org_b["id"]),
    )
    assert resp2.status_code == 404
