"""M5 review-loop tests for suggestions, comments, collapse, and Mistral wiring."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from uuid import UUID

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


def _two_teams(client: TestClient) -> dict[str, str]:
    token = _register(client, f"m5-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "M5"}, headers=_auth(token)).json()
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
    put = client.put(
        f"/api/teams/{t1}/profile",
        json={"data": {"tone": "plain"}},
        headers=_auth(token, org_id, t1),
    )
    assert put.status_code == 200, put.text
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    return {
        "token": token,
        "org": org_id,
        "team_a": t1,
        "team_b": t2,
        "user_id": me["id"],
    }


def _seed_post_with_node(
    *,
    org_id: str,
    team_a: str,
    team_b: str,
    user_id: str,
    channel_id: str,
    package_id: str,
) -> dict[str, str]:
    from src.channels.models import Post
    from src.graph.models import Node
    from src.lib.database import async_session_factory

    post_id = uuid.uuid4()
    node_id = uuid.uuid4()

    async def _run() -> None:
        from src.channels.models import Package

        async with async_session_factory() as session:
            session.add(
                Post(
                    id=post_id,
                    org_id=UUID(org_id),
                    channel_id=UUID(channel_id),
                    package_id=UUID(package_id),
                    adapted_body="Adapted body",
                    original_body="Original body",
                    what_was_done="adapted for Receiver",
                )
            )
            session.add(
                Node(
                    id=node_id,
                    org_id=UUID(org_id),
                    team_id=UUID(team_a),
                    label="Ship date",
                    node_type="topic",
                    summary="We ship Friday",
                    version=1,
                    search_text="Ship date We ship Friday",
                )
            )
            pkg = await session.get(Package, UUID(package_id))
            assert pkg is not None
            pkg.included_node_ids = [str(node_id)]
            await session.commit()

    asyncio.run(_run())
    return {"post_id": str(post_id), "node_id": str(node_id)}


def _bump_node_version(node_id: str) -> None:
    from src.graph.models import Node
    from src.lib.database import async_session_factory

    async def _run() -> None:
        async with async_session_factory() as session:
            node = await session.get(Node, UUID(node_id))
            assert node is not None
            node.version = node.version + 1
            await session.commit()

    asyncio.run(_run())


def test_regen_and_review_use_mistral() -> None:
    from src.jobs.kinds import regenerate_rendition as regen
    from src.review import service as review_svc

    regen_src = inspect.getsource(regen)
    review_src = inspect.getsource(review_svc)
    assert "get_mistral_provider" in regen_src
    assert "FakeAIProvider(" not in regen_src
    assert "get_mistral_provider" in review_src
    assert "FakeAIProvider(" not in review_src
    assert "AdaptationDirection.reverse" in review_src


def test_suggestion_review_action_comment_flow(client: TestClient) -> None:
    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert ch.status_code == 201, ch.text
    channel_id = ch.json()["id"]

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
    package_id = pkg.json()["id"]

    seeded = _seed_post_with_node(
        org_id=t["org"],
        team_a=t["team_a"],
        team_b=t["team_b"],
        user_id=t["user_id"],
        channel_id=channel_id,
        package_id=package_id,
    )

    sug = client.post(
        f"/api/posts/{seeded['post_id']}/suggestions",
        json={
            "text": "Please clarify Friday timezone",
            "target_node_id": seeded["node_id"],
            "suggestion_type": "request_clarification",
        },
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert sug.status_code == 201, sug.text
    sug_id = sug.json()["id"]
    assert sug.json()["status"] == "open"
    assert sug.json()["adapted_preview"]  # passthrough equals text on sqlite

    listed = client.get(
        f"/api/teams/{t['team_a']}/suggestions",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert listed.status_code == 200
    assert any(s["id"] == sug_id for s in listed.json())

    # Team A proposes accept — does NOT apply until Team B also approves
    proposed = client.post(
        f"/api/suggestions/{sug_id}/respond",
        json={"response": "accept"},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["status"] == "awaiting_approvals"
    assert str(t["team_a"]) in proposed.json()["approved_team_ids"]
    assert str(t["team_b"]) in proposed.json()["awaiting_team_ids"]

    # Node must still be unchanged before dual approve
    from src.graph.models import Node
    from src.lib.database import async_session_factory

    async def _node_summary() -> str:
        async with async_session_factory() as session:
            node = await session.get(Node, UUID(seeded["node_id"]))
            assert node is not None
            return node.summary

    assert asyncio.run(_node_summary()) == "We ship Friday"

    # Team B approves → apply
    approved = client.post(
        f"/api/suggestions/{sug_id}/approve",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "applied"
    assert set(approved.json()["approved_team_ids"]) == {t["team_a"], t["team_b"]}
    assert asyncio.run(_node_summary()) == "Please clarify Friday timezone"

    closed = client.post(
        f"/api/suggestions/{sug_id}/close",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    action = client.post(
        f"/api/posts/{seeded['post_id']}/review-actions",
        json={"action": "agree"},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert action.status_code == 201, action.text

    comment = client.post(
        f"/api/posts/{seeded['post_id']}/comments",
        json={"body": "Looks good from receiver side"},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert comment.status_code == 201, comment.text

    comments = client.get(
        f"/api/posts/{seeded['post_id']}/comments",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert comments.status_code == 200
    assert len(comments.json()) >= 1

    decisions = client.get(
        f"/api/teams/{t['team_a']}/decisions",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert decisions.status_code == 200


def test_proposer_can_cancel_open_and_awaiting(client: TestClient) -> None:
    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "Cancel demo",
            "body": "Ship Friday.",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    seeded = _seed_post_with_node(
        org_id=t["org"],
        team_a=t["team_a"],
        team_b=t["team_b"],
        user_id=t["user_id"],
        channel_id=ch,
        package_id=pkg,
    )

    # Cancel while open
    open_sug = client.post(
        f"/api/posts/{seeded['post_id']}/suggestions",
        json={"text": "Please change Friday", "target_node_id": seeded["node_id"]},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert open_sug.status_code == 201, open_sug.text
    open_id = open_sug.json()["id"]

    listed_b = client.get(
        f"/api/teams/{t['team_b']}/suggestions",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert listed_b.status_code == 200
    assert any(s["id"] == open_id for s in listed_b.json())

    cancelled_open = client.post(
        f"/api/suggestions/{open_id}/cancel",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert cancelled_open.status_code == 200, cancelled_open.text
    assert cancelled_open.json()["status"] == "cancelled"

    # Team A cannot cancel B's suggestion
    awaiting_sug = client.post(
        f"/api/posts/{seeded['post_id']}/suggestions",
        json={"text": "Another edit ask", "target_node_id": seeded["node_id"]},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert awaiting_sug.status_code == 201
    awaiting_id = awaiting_sug.json()["id"]
    proposed = client.post(
        f"/api/suggestions/{awaiting_id}/respond",
        json={"response": "accept"},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "awaiting_approvals"

    a_cancel = client.post(
        f"/api/suggestions/{awaiting_id}/cancel",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert a_cancel.status_code == 404

    b_cancel = client.post(
        f"/api/suggestions/{awaiting_id}/cancel",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert b_cancel.status_code == 200, b_cancel.text
    assert b_cancel.json()["status"] == "cancelled"

    # Cannot cancel after cancel
    again = client.post(
        f"/api/suggestions/{awaiting_id}/cancel",
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert again.status_code == 409


def test_stale_target_409(client: TestClient) -> None:
    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "X",
            "body": "Y",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    seeded = _seed_post_with_node(
        org_id=t["org"],
        team_a=t["team_a"],
        team_b=t["team_b"],
        user_id=t["user_id"],
        channel_id=ch,
        package_id=pkg,
    )
    sug = client.post(
        f"/api/posts/{seeded['post_id']}/suggestions",
        json={"text": "Edit claim", "target_node_id": seeded["node_id"]},
        headers=_auth(t["token"], t["org"], t["team_b"]),
    )
    assert sug.status_code == 201, sug.text
    _bump_node_version(seeded["node_id"])
    resp = client.post(
        f"/api/suggestions/{sug.json()['id']}/respond",
        json={"response": "accept"},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "stale_target"


def test_notification_collapse(client: TestClient) -> None:
    t = _two_teams(client)
    ch = client.post(
        f"/api/orgs/{t['org']}/channels",
        json={"team_a_id": t["team_a"], "team_b_id": t["team_b"]},
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    pkg = client.post(
        f"/api/teams/{t['team_a']}/packages",
        json={
            "title": "X",
            "body": "Y",
            "target_team_id": t["team_b"],
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(t["token"], t["org"], t["team_a"]),
    ).json()["id"]
    seeded = _seed_post_with_node(
        org_id=t["org"],
        team_a=t["team_a"],
        team_b=t["team_b"],
        user_id=t["user_id"],
        channel_id=ch,
        package_id=pkg,
    )
    for i in range(2):
        r = client.post(
            f"/api/posts/{seeded['post_id']}/suggestions",
            json={"text": f"Suggestion {i}"},
            headers=_auth(t["token"], t["org"], t["team_b"]),
        )
        assert r.status_code == 201, r.text

    notifs = client.get(
        "/api/notifications",
        headers=_auth(t["token"], t["org"], t["team_a"]),
    )
    assert notifs.status_code == 200
    suggestion_notifs = [
        n
        for n in notifs.json()
        if n.get("kind") == "suggestion_received"
        and (n.get("payload") or {}).get("post_id") == seeded["post_id"]
    ]
    assert len(suggestion_notifs) == 1
