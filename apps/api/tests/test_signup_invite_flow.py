"""Signup with username, invite by username/email, accept invite."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

import src.lib.rate_limit as rate_limit_module


def _reset_rate_limiter() -> None:
    rate_limit_module._rate_limiter_registry.clear()


def _register(
    client: TestClient,
    *,
    email: str,
    username: str,
    password: str = "password123",  # noqa: S107
) -> str:
    _reset_rate_limiter()
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "username": username,
            "name": username,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_requires_username_and_exposes_it_on_me(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    token = _register(
        client,
        email=f"owner-{suffix}@example.com",
        username=f"owner_{suffix}",
    )
    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["username"] == f"owner_{suffix}"


def test_duplicate_username_is_rejected(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    first = client.post(
        "/api/auth/register",
        json={
            "email": f"one-{suffix}@example.com",
            "password": "password123",
            "username": f"same_{suffix}",
        },
    )
    second = client.post(
        "/api/auth/register",
        json={
            "email": f"two-{suffix}@example.com",
            "password": "password123",
            "username": f"same_{suffix}",
        },
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Username already taken"


def test_invite_by_username_adds_existing_member(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    owner = _register(client, email=f"own-{suffix}@example.com", username=f"own_{suffix}")  # noqa: E501
    invitee = _register(client, email=f"inv-{suffix}@example.com", username=f"inv_{suffix}")  # noqa: E501

    org = client.post("/api/orgs", headers=_auth(owner), json={"name": "Acme"})
    assert org.status_code == 201
    org_id = org.json()["id"]

    team = client.post(
        f"/api/orgs/{org_id}/teams",
        headers={**_auth(owner), "X-Org-Id": org_id},
        json={"name": "Platform"},
    )
    assert team.status_code == 201
    team_id = team.json()["id"]

    invite = client.post(
        f"/api/teams/{team_id}/invites",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
        json={"username": f"inv_{suffix}", "role": "member"},
    )
    assert invite.status_code == 201, invite.text
    body = invite.json()
    assert body["added_immediately"] is True
    assert body["email"] == f"inv-{suffix}@example.com"

    members = client.get(
        f"/api/teams/{team_id}/members",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
    )
    assert members.status_code == 200
    usernames = {m["username"] for m in members.json()}
    assert f"inv_{suffix}" in usernames

    # invitee can accept token again (idempotent membership)
    accept = client.post(
        "/api/invites/accept",
        headers=_auth(invitee),
        json={"token": body["token"]},
    )
    assert accept.status_code == 200
    assert accept.json()["added_immediately"] is True


def test_invite_by_email_pending_then_accept(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    owner = _register(client, email=f"lead-{suffix}@example.com", username=f"lead_{suffix}")  # noqa: E501
    org = client.post("/api/orgs", headers=_auth(owner), json={"name": "Org"})
    org_id = org.json()["id"]
    team = client.post(
        f"/api/orgs/{org_id}/teams",
        headers={**_auth(owner), "X-Org-Id": org_id},
        json={"name": "Team"},
    )
    team_id = team.json()["id"]

    pending_email = f"newbie-{suffix}@example.com"
    invite = client.post(
        f"/api/teams/{team_id}/invites",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
        json={"email": pending_email, "role": "viewer"},
    )
    assert invite.status_code == 201
    assert invite.json()["added_immediately"] is False
    token = invite.json()["token"]

    newbie = _register(client, email=pending_email, username=f"newbie_{suffix}")
    accept = client.post(
        "/api/invites/accept",
        headers=_auth(newbie),
        json={"token": token},
    )
    assert accept.status_code == 200

    members = client.get(
        f"/api/teams/{team_id}/members",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
    )
    assert any(m["email"] == pending_email for m in members.json())


def test_pending_invite_auto_applied_on_registration(client: TestClient) -> None:
    """A pending invite (invitee had no account yet) is applied at registration —
    no manual /api/invites/accept step required."""
    suffix = uuid.uuid4().hex[:8]
    owner = _register(client, email=f"lead2-{suffix}@example.com", username=f"lead2_{suffix}")  # noqa: E501
    org = client.post("/api/orgs", headers=_auth(owner), json={"name": "Org2"})
    org_id = org.json()["id"]
    team = client.post(
        f"/api/orgs/{org_id}/teams",
        headers={**_auth(owner), "X-Org-Id": org_id},
        json={"name": "Team2"},
    )
    team_id = team.json()["id"]

    pending_email = f"autonewbie-{suffix}@example.com"
    invite = client.post(
        f"/api/teams/{team_id}/invites",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
        json={"email": pending_email, "role": "member"},
    )
    assert invite.status_code == 201
    assert invite.json()["added_immediately"] is False

    newbie = _register(client, email=pending_email, username=f"autonewbie_{suffix}")

    members = client.get(
        f"/api/teams/{team_id}/members",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
    )
    assert members.status_code == 200
    matching = [m for m in members.json() if m["email"] == pending_email]
    assert len(matching) == 1
    assert matching[0]["role"] == "member"

    me = client.get("/api/auth/me", headers=_auth(newbie))
    assert me.status_code == 200


def test_archive_team_and_org(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    owner = _register(client, email=f"archowner-{suffix}@example.com", username=f"archowner_{suffix}")  # noqa: E501
    member = _register(client, email=f"archmember-{suffix}@example.com", username=f"archmember_{suffix}")  # noqa: E501

    org = client.post("/api/orgs", headers=_auth(owner), json={"name": "ArchOrg"})
    org_id = org.json()["id"]
    team = client.post(
        f"/api/orgs/{org_id}/teams",
        headers={**_auth(owner), "X-Org-Id": org_id},
        json={"name": "ArchTeam"},
    )
    team_id = team.json()["id"]

    invite = client.post(
        f"/api/teams/{team_id}/invites",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
        json={"email": f"archmember-{suffix}@example.com", "role": "member"},
    )
    assert invite.status_code == 201, invite.text

    # a plain member cannot archive the team or the org
    forbidden_team = client.post(
        f"/api/teams/{team_id}/archive",
        headers={**_auth(member), "X-Org-Id": org_id, "X-Team-Id": team_id},
    )
    assert forbidden_team.status_code == 403
    forbidden_org = client.post(
        f"/api/orgs/{org_id}/archive",
        headers={**_auth(member), "X-Org-Id": org_id},
    )
    assert forbidden_org.status_code == 403

    # the team's own lead can archive it; it drops out of the picker
    archive_team = client.post(
        f"/api/teams/{team_id}/archive",
        headers={**_auth(owner), "X-Org-Id": org_id, "X-Team-Id": team_id},
    )
    assert archive_team.status_code == 204, archive_team.text

    mine = client.get("/api/orgs", headers=_auth(owner))
    org_entry = next(o for o in mine.json() if o["org_id"] == org_id)
    assert org_entry["teams"] == []

    # the org owner can archive the org; it drops out entirely
    archive_org = client.post(
        f"/api/orgs/{org_id}/archive",
        headers={**_auth(owner), "X-Org-Id": org_id},
    )
    assert archive_org.status_code == 204, archive_org.text

    mine_after = client.get("/api/orgs", headers=_auth(owner))
    assert all(o["org_id"] != org_id for o in mine_after.json())
