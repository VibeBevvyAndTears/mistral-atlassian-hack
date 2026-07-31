# ruff: noqa: E501, S105
#!/usr/bin/env python3
"""Demo: Team A document → package → Team B channel post.

Walks the real cross-team delivery path against a running API:

  register → org → Team A + Team B → profiles → paste doc on A
  → wait ingest (optional nodes) → create package → send
  → poll channel posts → list post sources

Usage (from repo root, with `mise dev:web` running):

  uv run --directory apps/api python scripts/demo_team_a_to_b_flow.py

  # or point at another host:
  API_BASE=http://127.0.0.1:8000 uv run --directory apps/api \\
    python scripts/demo_team_a_to_b_flow.py

Writes credentials + IDs to apps/api/.data/demo_a_to_b_last.json for UI follow-up.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
OUT_PATH = Path(__file__).resolve().parents[1] / ".data" / "demo_a_to_b_last.json"
DOC_WAIT_S = float(os.environ.get("DEMO_DOC_WAIT_S", "90"))
POST_WAIT_S = float(os.environ.get("DEMO_POST_WAIT_S", "180"))
POLL_S = float(os.environ.get("DEMO_POLL_S", "3"))


class StepError(RuntimeError):
    pass


def _log(step: str, msg: str, **extra: Any) -> None:
    payload = {"step": step, "msg": msg, **extra}
    print(json.dumps(payload, default=str), flush=True)


def _raise(resp: httpx.Response, step: str) -> None:
    try:
        detail = resp.json()
    except Exception:
        detail = resp.text
    raise StepError(f"{step} failed HTTP {resp.status_code}: {detail}")


def _auth(token: str, org_id: str | None = None, team_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if org_id:
        headers["X-Org-Id"] = org_id
    if team_id:
        headers["X-Team-Id"] = team_id
    return headers


def _wait_doc(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    team_id: str,
    doc_id: str,
    timeout_s: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        resp = client.get(
            f"/api/documents/{doc_id}",
            headers=_auth(token, org_id, team_id),
        )
        if resp.status_code != 200:
            _raise(resp, "poll_document")
        last = resp.json()
        status = last.get("status")
        _log("poll_document", "document status", status=status, doc_id=doc_id)
        if status in {"ready", "failed", "error"}:
            return last
        time.sleep(POLL_S)
    return last


def _wait_posts(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    team_id: str,
    channel_id: str,
    timeout_s: float,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = client.get(
            f"/api/channels/{channel_id}/posts",
            headers=_auth(token, org_id, team_id),
            params={"sort": "newest"},
        )
        if resp.status_code != 200:
            _raise(resp, "poll_posts")
        posts = resp.json().get("items") or []
        _log("poll_posts", "channel feed", count=len(posts), channel_id=channel_id)
        if posts:
            return posts
        time.sleep(POLL_S)
    return []


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"demo-a2b-{suffix}@example.com"
    username = f"demo_a2b_{suffix}"
    password = "password123"
    doc_text = (
        "Ship plan for Team A → Team B handoff.\n"
        "We release Friday. Rollback window is 2 hours.\n"
        "Owner: platform lead. Risk: dependency on auth service.\n"
    )

    _log("start", "demo A→B flow", api_base=API_BASE, email=email)

    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        # 1. Register
        reg = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": password,
                "username": username,
                "name": "Demo A2B",
            },
        )
        if reg.status_code != 201:
            _raise(reg, "register")
        token = reg.json()["access_token"]
        _log("register", "ok", email=email, username=username)

        # 2. Org + two teams
        org = client.post("/api/orgs", json={"name": f"Demo Org {suffix}"}, headers=_auth(token))
        if org.status_code not in (200, 201):
            _raise(org, "create_org")
        org_id = org.json()["id"]
        _log("create_org", "ok", org_id=org_id)

        team_a = client.post(
            f"/api/orgs/{org_id}/teams",
            json={"name": "Team A (Sender)"},
            headers=_auth(token, org_id),
        )
        if team_a.status_code not in (200, 201):
            _raise(team_a, "create_team_a")
        team_a_id = team_a.json()["id"]
        _log("create_team_a", "ok", team_id=team_a_id)

        team_b = client.post(
            f"/api/orgs/{org_id}/teams",
            json={"name": "Team B (Receiver)"},
            headers=_auth(token, org_id),
        )
        if team_b.status_code not in (200, 201):
            _raise(team_b, "create_team_b")
        team_b_id = team_b.json()["id"]
        _log("create_team_b", "ok", team_id=team_b_id)

        for tid, label in ((team_a_id, "A"), (team_b_id, "B")):
            put = client.put(
                f"/api/teams/{tid}/profile",
                json={"data": {"tone": "plain", "role": f"team_{label.lower()}"}},
                headers=_auth(token, org_id, tid),
            )
            if put.status_code != 200:
                _raise(put, f"profile_team_{label}")
            _log(f"profile_team_{label}", "ok")

        # 3. Paste document on Team A
        pasted = client.post(
            f"/api/teams/{team_a_id}/documents/paste",
            json={"text": doc_text, "filename": "handoff-notes.txt"},
            headers=_auth(token, org_id, team_a_id),
        )
        if pasted.status_code != 201:
            _raise(pasted, "paste_document")
        doc = pasted.json()
        doc_id = doc["id"]
        job_id = doc.get("job_id")
        _log(
            "paste_document",
            "queued",
            doc_id=doc_id,
            job_id=job_id,
            status=doc.get("status"),
            filename=doc.get("filename"),
        )

        doc_final = _wait_doc(
            client,
            token=token,
            org_id=org_id,
            team_id=team_a_id,
            doc_id=doc_id,
            timeout_s=DOC_WAIT_S,
        )
        _log(
            "ingest",
            "document settled (or timed out)",
            status=doc_final.get("status"),
            doc_id=doc_id,
        )

        # 4. Optional: attach graph nodes produced by ingest
        nodes_resp = client.get(
            f"/api/teams/{team_a_id}/nodes",
            headers=_auth(token, org_id, team_a_id),
        )
        included_node_ids: list[str] = []
        if nodes_resp.status_code == 200:
            nodes = nodes_resp.json()
            for n in nodes:
                if n.get("document_id") == doc_id:
                    included_node_ids.append(n["id"])
            if not included_node_ids and nodes:
                # Fall back to any team nodes if document_id not populated yet
                included_node_ids = [n["id"] for n in nodes[:3]]
            _log(
                "list_nodes",
                "ok",
                total=len(nodes),
                included=len(included_node_ids),
                labels=[n.get("label") for n in nodes[:5]],
            )
        else:
            _log("list_nodes", "skipped", status_code=nodes_resp.status_code)

        # 5. Ensure channel + create package
        ch = client.post(
            f"/api/orgs/{org_id}/channels",
            json={"team_a_id": team_a_id, "team_b_id": team_b_id},
            headers=_auth(token, org_id, team_a_id),
        )
        if ch.status_code not in (200, 201):
            _raise(ch, "ensure_channel")
        channel_id = ch.json()["id"]
        _log("ensure_channel", "ok", channel_id=channel_id)

        pkg_body: dict[str, Any] = {
            "title": f"Handoff notes ({suffix})",
            "body": (
                "Team A is sharing ship-plan notes with Team B.\n"
                "Please review Friday release + rollback window."
            ),
            "target_team_id": team_b_id,
            "bypass_incomplete_pipeline": True,
        }
        if included_node_ids:
            pkg_body["included_node_ids"] = included_node_ids

        pkg = client.post(
            f"/api/teams/{team_a_id}/packages",
            json=pkg_body,
            headers=_auth(token, org_id, team_a_id),
        )
        if pkg.status_code != 201:
            _raise(pkg, "create_package")
        package = pkg.json()
        package_id = package["id"]
        _log(
            "create_package",
            "ok",
            package_id=package_id,
            channel_id=package.get("channel_id"),
            checklist_ok=package.get("checklist", {}).get("ok"),
            bypassed=package.get("bypassed_checks"),
            included_node_ids=package.get("included_node_ids"),
        )

        # 6. Send
        sent = client.post(
            f"/api/packages/{package_id}/send",
            headers=_auth(token, org_id, team_a_id),
        )
        if sent.status_code != 200:
            _raise(sent, "send_package")
        send_body = sent.json()
        _log(
            "send_package",
            "enqueued",
            status=send_body.get("status"),
            job_id=send_body.get("job_id"),
        )

        # 7. Poll feed as Team B
        posts = _wait_posts(
            client,
            token=token,
            org_id=org_id,
            team_id=team_b_id,
            channel_id=channel_id,
            timeout_s=POST_WAIT_S,
        )
        if not posts:
            _log(
                "done",
                "send enqueued but no post yet — worker may still be adapting; "
                "open Team B channels in the UI with the IDs below",
                channel_id=channel_id,
            )
        else:
            post = posts[0]
            post_id = post["id"]
            _log(
                "post_arrived",
                "Team B sees post",
                post_id=post_id,
                priority=post.get("ai_priority"),
                topic_tags=post.get("topic_tags"),
                adapted_preview=(post.get("adapted_body") or "")[:160],
            )
            sources = client.get(
                f"/api/posts/{post_id}/sources",
                headers=_auth(token, org_id, team_b_id),
            )
            if sources.status_code == 200:
                src = sources.json()
                _log(
                    "post_sources",
                    "ok",
                    package_title=src.get("package_title"),
                    documents=[
                        {"id": d.get("id"), "filename": d.get("filename"), "status": d.get("status")}
                        for d in src.get("documents") or []
                    ],
                )
            else:
                _log("post_sources", "failed", status_code=sources.status_code, body=sources.text)

        state = {
            "api_base": API_BASE,
            "email": email,
            "username": username,
            "password": password,
            "org_id": org_id,
            "team_a_id": team_a_id,
            "team_b_id": team_b_id,
            "channel_id": channel_id,
            "package_id": package_id,
            "document_id": doc_id,
            "document_status": doc_final.get("status"),
            "included_node_ids": included_node_ids,
            "posts": [{"id": p.get("id"), "ai_priority": p.get("ai_priority")} for p in posts],
            "web_urls": {
                # Prefer localhost (matches NEXT_PUBLIC_API_URL default) over 127.0.0.1
                "login": "http://localhost:3000/en/login",
                "team_a_documents": (
                    f"http://localhost:3000/en/teams/{team_a_id}/documents"
                    f"?orgId={org_id}"
                ),
                "team_a_compose": (
                    f"http://localhost:3000/en/teams/{team_a_id}/compose"
                    f"?orgId={org_id}"
                ),
                "team_b_channels": (
                    f"http://localhost:3000/en/teams/{team_b_id}/channels"
                    f"?orgId={org_id}"
                ),
            },
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(state, indent=2) + "\n")
        _log("state_written", str(OUT_PATH), **{k: state[k] for k in ("email", "org_id", "team_a_id", "team_b_id", "channel_id")})

        print("\n=== UI follow-up ===", flush=True)
        print(f"Sign in:  {email} / {password}", flush=True)
        print(f"Team A docs:     {state['web_urls']['team_a_documents']}", flush=True)
        print(f"Team A compose:  {state['web_urls']['team_a_compose']}", flush=True)
        print(f"  (target team UUID = {team_b_id})", flush=True)
        print(f"Team B channels: {state['web_urls']['team_b_channels']}", flush=True)
        print(f"  Channel UUID:  {channel_id}", flush=True)
        print(f"State file:      {OUT_PATH}", flush=True)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StepError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
    except httpx.ConnectError as exc:
        print(
            f"ERROR: cannot reach API at {API_BASE} — is `mise dev:web` running?\n{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from exc
