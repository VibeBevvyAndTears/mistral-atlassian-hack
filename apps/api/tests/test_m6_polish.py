"""M6 polish tests — glossary, feed filters, mark-read, draft stub, admin metrics."""

from __future__ import annotations

import inspect
import io
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


def _auth(
    token: str, org_id: str | None = None, team_id: str | None = None
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if org_id:
        headers["X-Org-Id"] = org_id
    if team_id:
        headers["X-Team-Id"] = team_id
    return headers


def _team(client: TestClient) -> dict[str, str]:
    token = _register(client, f"m6-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "M6"}, headers=_auth(token)).json()[
        "id"
    ]
    team = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Core"},
        headers=_auth(token, org),
    ).json()["id"]
    return {"token": token, "org": org, "team": team}


def test_profile_draft_uses_mistral_not_fake() -> None:
    from src.profiles import service as mod

    src = inspect.getsource(mod)
    assert "get_mistral_provider" in src
    assert "FakeAIProvider(" not in src


def test_glossary_crud(client: TestClient) -> None:
    t = _team(client)
    created = client.post(
        f"/api/teams/{t['team']}/glossary",
        json={
            "term": "SLA",
            "definition": "Service level agreement",
            "kind": "must_explain",
        },
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert created.status_code == 201, created.text
    term_id = created.json()["id"]

    listed = client.get(
        f"/api/teams/{t['team']}/glossary",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert listed.status_code == 200
    assert any(row["id"] == term_id for row in listed.json())

    deleted = client.delete(
        f"/api/teams/{t['team']}/glossary/{term_id}",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert deleted.status_code == 204


def test_feed_sort_and_mark_read(client: TestClient) -> None:
    t = _team(client)
    t2 = client.post(
        f"/api/orgs/{t['org']}/teams",
        json={"name": "Other"},
        headers=_auth(t["token"], t["org"]),
    ).json()["id"]
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team"], "team_b_id": t2},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

    for sort in ("newest", "oldest", "priority"):
        feed = client.get(
            f"/api/channels/{channel_id}/posts",
            params={"sort": sort, "unread_only": False},
            headers=_auth(t["token"], t["org"], t["team"]),
        )
        assert feed.status_code == 200, feed.text


def test_profile_draft_stub_and_admin_metrics(client: TestClient) -> None:
    t = _team(client)
    upload = client.post(
        f"/api/teams/{t['team']}/documents",
        headers=_auth(t["token"], t["org"], t["team"]),
        files={"file": ("note.txt", io.BytesIO(b"We ship Friday."), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]

    draft = client.post(
        f"/api/teams/{t['team']}/profile/draft-from-document",
        json={"document_ids": [doc_id]},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["generated_by"] == "deterministic_stub"

    metrics = client.get(
        f"/api/orgs/{t['org']}/admin/metrics",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert "trace_count" in body
    assert "post_count" in body
    assert "suggestion_count" in body


def test_list_my_orgs(client: TestClient) -> None:
    t = _team(client)

    mine = client.get("/api/orgs", headers=_auth(t["token"]))
    assert mine.status_code == 200, mine.text
    orgs = mine.json()
    assert len(orgs) == 1
    assert orgs[0]["org_id"] == t["org"]
    assert orgs[0]["role"] == "owner"
    assert len(orgs[0]["teams"]) == 1
    assert orgs[0]["teams"][0]["team_id"] == t["team"]
    assert orgs[0]["teams"][0]["role"] == "lead"

    other_token = _register(client, f"m6-other-{uuid.uuid4().hex[:8]}@example.com")
    empty = client.get("/api/orgs", headers=_auth(other_token))
    assert empty.status_code == 200, empty.text
    assert empty.json() == []


def test_post_history_panel_api(client: TestClient) -> None:
    """P1: in-post History endpoint returns timeline without leaving the feed."""
    import asyncio
    from uuid import UUID

    from src.channels.models import Post
    from src.lib.database import async_session_factory

    t = _team(client)
    t2 = client.post(
        f"/api/orgs/{t['org']}/teams",
        json={"name": "Other"},
        headers=_auth(t["token"], t["org"]),
    ).json()["id"]
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team"], "team_b_id": t2},
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

    pkg = client.post(
        f"/api/teams/{t['team']}/packages",
        json={
            "title": "Update",
            "body": "We ship Friday.",
            "target_team_id": t2,
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert pkg.status_code == 201, pkg.text
    package_id = pkg.json()["id"]
    post_id = uuid.uuid4()

    async def _seed() -> None:
        async with async_session_factory() as session:
            session.add(
                Post(
                    id=post_id,
                    org_id=UUID(t["org"]),
                    channel_id=UUID(channel_id),
                    package_id=UUID(package_id),
                    adapted_body="Adapted",
                    original_body="Original",
                    what_was_done="adapted for Other",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    hist = client.get(
        f"/api/posts/{post_id}/history",
        headers=_auth(t["token"], t["org"], t["team"]),
    )
    assert hist.status_code == 200, hist.text
    rows = hist.json()
    assert rows
    assert any(row["kind"] == "post" for row in rows)
