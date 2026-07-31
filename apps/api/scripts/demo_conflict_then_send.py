# ruff: noqa: E501, S105
#!/usr/bin/env python3
"""Demo: Team A conflicting document → resolve → send to Team B.

Narrative this script exercises:

  1. Paste baseline doc on Team A (existing knowledge)
  2. Paste a second doc that contradicts that plan (update)
  3. Show open review-items block package send (checklist gate)
  4. Resolve all open conflicts
  5. Create package + send → Team B channel post

Note on product behavior: intra-team conflict detection runs on claims
extracted from the *current* ingest document. The second paste therefore
restates the prior Friday plan *and* the Monday correction so the scanner
sees both sides in one ConflictInput (how the product works today).

Usage (from repo root, with `mise dev:web` running):

  uv run --directory apps/api python scripts/demo_conflict_then_send.py

Writes state to apps/api/.data/demo_conflict_then_send_last.json
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
OUT_PATH = Path(__file__).resolve().parents[1] / ".data" / "demo_conflict_then_send_last.json"
DOC_WAIT_S = float(os.environ.get("DEMO_DOC_WAIT_S", "120"))
REVIEW_WAIT_S = float(os.environ.get("DEMO_REVIEW_WAIT_S", "60"))
POST_WAIT_S = float(os.environ.get("DEMO_POST_WAIT_S", "180"))
POLL_S = float(os.environ.get("DEMO_POLL_S", "3"))

DOC1_TEXT = """\
Team A release plan (baseline).
Decision: We will ship on Friday.
Constraint: Rollback window is 2 hours after Friday cutover.
Owner: platform lead.
"""

# Restates Friday + introduces Monday contradiction so ingest conflict_intra fires.
DOC2_TEXT = """\
Update to Team A release plan — conflicts with the existing Friday decision.

Earlier approved plan: We will ship on Friday.
Correction / new decision: The release date is Monday; Friday is cancelled.
Constraint: Friday ship is no longer valid.
Risk: Marketing already announced Friday — must be corrected before handoff to Team B.
"""


class StepError(RuntimeError):
    pass


def _log(step: str, msg: str, **extra: Any) -> None:
    print(json.dumps({"step": step, "msg": msg, **extra}, default=str), flush=True)


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


def _list_review_items(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    team_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    params = {"status": status} if status else None
    resp = client.get(
        f"/api/teams/{team_id}/review-items",
        headers=_auth(token, org_id, team_id),
        params=params,
    )
    if resp.status_code != 200:
        _raise(resp, "list_review_items")
    return resp.json()


def _wait_open_reviews(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    team_id: str,
    timeout_s: float,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_s
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        last = _list_review_items(
            client, token=token, org_id=org_id, team_id=team_id, status="open"
        )
        _log("poll_review_items", "open conflicts", count=len(last))
        if last:
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
    min_count: int = 1,
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
        if len(posts) >= min_count:
            return posts
        time.sleep(POLL_S)
    return []


def _paste(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    team_id: str,
    text: str,
    filename: str,
) -> dict[str, Any]:
    pasted = client.post(
        f"/api/teams/{team_id}/documents/paste",
        json={"text": text, "filename": filename},
        headers=_auth(token, org_id, team_id),
    )
    if pasted.status_code != 201:
        _raise(pasted, f"paste_{filename}")
    return pasted.json()


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"demo-conflict-{suffix}@example.com"
    username = f"demo_conflict_{suffix}"
    password = "password123"

    _log("start", "demo conflict → resolve → send", api_base=API_BASE, email=email)

    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        # --- bootstrap ---
        reg = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": password,
                "username": username,
                "name": "Demo Conflict",
            },
        )
        if reg.status_code != 201:
            _raise(reg, "register")
        token = reg.json()["access_token"]
        _log("register", "ok", email=email)

        org = client.post(
            "/api/orgs",
            json={"name": f"Conflict Demo Org {suffix}"},
            headers=_auth(token),
        )
        if org.status_code not in (200, 201):
            _raise(org, "create_org")
        org_id = org.json()["id"]

        team_a = client.post(
            f"/api/orgs/{org_id}/teams",
            json={"name": "Team A (Sender)"},
            headers=_auth(token, org_id),
        )
        if team_a.status_code not in (200, 201):
            _raise(team_a, "create_team_a")
        team_a_id = team_a.json()["id"]

        team_b = client.post(
            f"/api/orgs/{org_id}/teams",
            json={"name": "Team B (Receiver)"},
            headers=_auth(token, org_id),
        )
        if team_b.status_code not in (200, 201):
            _raise(team_b, "create_team_b")
        team_b_id = team_b.json()["id"]

        for tid, label in ((team_a_id, "A"), (team_b_id, "B")):
            put = client.put(
                f"/api/teams/{tid}/profile",
                json={"data": {"tone": "plain", "role": f"team_{label.lower()}"}},
                headers=_auth(token, org_id, tid),
            )
            if put.status_code != 200:
                _raise(put, f"profile_team_{label}")
        _log("bootstrap", "ok", org_id=org_id, team_a_id=team_a_id, team_b_id=team_b_id)

        # --- 1. Existing document ---
        doc1 = _paste(
            client,
            token=token,
            org_id=org_id,
            team_id=team_a_id,
            text=DOC1_TEXT,
            filename="baseline-friday-plan.txt",
        )
        doc1_id = doc1["id"]
        _log("paste_doc1", "queued baseline", doc_id=doc1_id, status=doc1.get("status"))
        doc1_final = _wait_doc(
            client,
            token=token,
            org_id=org_id,
            team_id=team_a_id,
            doc_id=doc1_id,
            timeout_s=DOC_WAIT_S,
        )
        if doc1_final.get("status") != "ready":
            raise StepError(f"doc1 not ready: {doc1_final.get('status')}")
        open_after_doc1 = _list_review_items(
            client, token=token, org_id=org_id, team_id=team_a_id, status="open"
        )
        _log(
            "after_doc1",
            "baseline ingested",
            open_conflicts=len(open_after_doc1),
            status=doc1_final.get("status"),
        )

        # --- 2. Conflicting update document ---
        doc2 = _paste(
            client,
            token=token,
            org_id=org_id,
            team_id=team_a_id,
            text=DOC2_TEXT,
            filename="update-monday-conflict.txt",
        )
        doc2_id = doc2["id"]
        _log("paste_doc2", "queued conflicting update", doc_id=doc2_id, status=doc2.get("status"))
        doc2_final = _wait_doc(
            client,
            token=token,
            org_id=org_id,
            team_id=team_a_id,
            doc_id=doc2_id,
            timeout_s=DOC_WAIT_S,
        )
        if doc2_final.get("status") != "ready":
            raise StepError(f"doc2 not ready: {doc2_final.get('status')}")

        open_items = _wait_open_reviews(
            client,
            token=token,
            org_id=org_id,
            team_id=team_a_id,
            timeout_s=REVIEW_WAIT_S,
        )
        if not open_items:
            all_items = _list_review_items(
                client, token=token, org_id=org_id, team_id=team_a_id
            )
            raise StepError(
                "No open review-items after conflicting paste. "
                f"all_items={len(all_items)}. "
                "Mistral may have skipped conflict_intra — re-run or harden DOC2_TEXT."
            )
        _log(
            "conflicts_detected",
            "open review-items block send",
            count=len(open_items),
            items=[
                {
                    "id": i.get("id"),
                    "class": i.get("conflict_class"),
                    "severity": i.get("severity"),
                    "rationale": (i.get("rationale") or "")[:160],
                    "status": i.get("status"),
                }
                for i in open_items
            ],
        )

        # --- 3. Prove checklist gate while open ---
        blocked = client.post(
            f"/api/teams/{team_a_id}/packages",
            json={
                "title": f"Should be blocked ({suffix})",
                "body": "Trying to send before resolving conflicts.",
                "target_team_id": team_b_id,
                "bypass_incomplete_pipeline": True,
            },
            headers=_auth(token, org_id, team_a_id),
        )
        if blocked.status_code != 201:
            _raise(blocked, "create_package_while_blocked")
        blocked_pkg = blocked.json()
        checklist = blocked_pkg.get("checklist") or {}
        _log(
            "checklist_while_open",
            "package created but checklist should fail",
            package_id=blocked_pkg.get("id"),
            checklist_ok=checklist.get("ok"),
            no_unresolved_review_items=checklist.get("no_unresolved_review_items"),
            checks={k: checklist.get(k) for k in (
                "team_profile_present",
                "pipeline_complete",
                "no_unresolved_review_items",
                "no_unowned_decisions",
                "no_dangling_excluded_refs",
                "no_unknown_receiving_terms",
            )},
        )
        if checklist.get("no_unresolved_review_items") is not False:
            raise StepError(
                "Expected no_unresolved_review_items=false while conflicts are open"
            )

        send_blocked = client.post(
            f"/api/packages/{blocked_pkg['id']}/send",
            headers=_auth(token, org_id, team_a_id),
        )
        _log(
            "send_while_open",
            "expected refusal",
            status_code=send_blocked.status_code,
            body=send_blocked.json() if send_blocked.headers.get("content-type", "").startswith("application/json") else send_blocked.text,
        )
        if send_blocked.status_code == 200:
            raise StepError("Send unexpectedly succeeded while open conflicts exist")

        # --- 4. Resolve all open conflicts ---
        resolved_ids: list[str] = []
        for item in open_items:
            item_id = item["id"]
            # Prefer keep_b = accept the Monday correction in DOC2
            res = client.post(
                f"/api/review-items/{item_id}/resolve",
                json={"resolution": "keep_b"},
                headers=_auth(token, org_id, team_a_id),
            )
            if res.status_code != 200:
                _raise(res, f"resolve_{item_id}")
            resolved_ids.append(item_id)
            _log(
                "resolve",
                "ok",
                item_id=item_id,
                resolution=res.json().get("resolved_resolution"),
                status=res.json().get("status"),
            )

        still_open = _list_review_items(
            client, token=token, org_id=org_id, team_id=team_a_id, status="open"
        )
        if still_open:
            raise StepError(f"Still have {len(still_open)} open review-items after resolve")
        _log("resolve_all", "no open conflicts remain", resolved=resolved_ids)

        # --- 5. Create package + send ---
        ch = client.post(
            f"/api/orgs/{org_id}/channels",
            json={"team_a_id": team_a_id, "team_b_id": team_b_id},
            headers=_auth(token, org_id, team_a_id),
        )
        if ch.status_code not in (200, 201):
            _raise(ch, "ensure_channel")
        channel_id = ch.json()["id"]

        nodes_resp = client.get(
            f"/api/teams/{team_a_id}/nodes",
            headers=_auth(token, org_id, team_a_id),
        )
        included_node_ids: list[str] = []
        if nodes_resp.status_code == 200:
            nodes = nodes_resp.json()
            for n in nodes:
                if n.get("document_id") in {doc1_id, doc2_id}:
                    included_node_ids.append(n["id"])
            if not included_node_ids:
                included_node_ids = [n["id"] for n in nodes[:5]]
            _log("list_nodes", "ok", total=len(nodes), included=len(included_node_ids))

        pkg_body: dict[str, Any] = {
            "title": f"Resolved ship-date handoff ({suffix})",
            "body": (
                "Team A resolved the Friday vs Monday ship conflict (kept Monday).\n"
                "Sharing the corrected plan with Team B."
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
            _raise(pkg, "create_package_after_resolve")
        package = pkg.json()
        package_id = package["id"]
        cl = package.get("checklist") or {}
        _log(
            "create_package_after_resolve",
            "ok",
            package_id=package_id,
            checklist_ok=cl.get("ok"),
            no_unresolved_review_items=cl.get("no_unresolved_review_items"),
        )
        if cl.get("ok") is not True:
            raise StepError(f"Checklist still failing after resolve: {cl}")

        sent = client.post(
            f"/api/packages/{package_id}/send",
            json={"acknowledge_conflicts": True},
            headers=_auth(token, org_id, team_a_id),
        )
        if sent.status_code != 200:
            _raise(sent, "send_package")
        _log(
            "send_package",
            "enqueued",
            status=sent.json().get("status"),
            job_id=sent.json().get("job_id"),
        )

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
                "send enqueued but no post yet — check worker / UI channels",
                channel_id=channel_id,
            )
        else:
            post = posts[0]
            _log(
                "post_arrived",
                "Team B sees post after conflict resolve",
                post_id=post.get("id"),
                priority=post.get("ai_priority"),
                topic_tags=post.get("topic_tags"),
                adapted_preview=(post.get("adapted_body") or "")[:200],
                attached_conflicts=post.get("attached_conflicts"),
            )

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
            "document_ids": {"baseline": doc1_id, "conflict_update": doc2_id},
            "resolved_review_item_ids": resolved_ids,
            "blocked_package_id": blocked_pkg.get("id"),
            "posts": [{"id": p.get("id"), "ai_priority": p.get("ai_priority")} for p in posts],
            "web_urls": {
                "login": "http://localhost:3000/en/login",
                "team_a_documents": (
                    f"http://localhost:3000/en/teams/{team_a_id}/documents?orgId={org_id}"
                ),
                "team_a_conflicts": (
                    f"http://localhost:3000/en/teams/{team_a_id}/review-items?orgId={org_id}"
                ),
                "team_a_compose": (
                    f"http://localhost:3000/en/teams/{team_a_id}/compose?orgId={org_id}"
                ),
                "team_b_channels": (
                    f"http://localhost:3000/en/teams/{team_b_id}/channels?orgId={org_id}"
                ),
            },
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(state, indent=2) + "\n")
        _log("state_written", str(OUT_PATH), email=email, org_id=org_id)

        print("\n=== UI follow-up ===", flush=True)
        print(f"Sign in:  {email} / {password}", flush=True)
        print(f"Conflicts: {state['web_urls']['team_a_conflicts']}", flush=True)
        print(f"Compose:   {state['web_urls']['team_a_compose']}", flush=True)
        print(f"  target team UUID = {team_b_id}", flush=True)
        print(f"Team B:    {state['web_urls']['team_b_channels']}", flush=True)
        print(f"  Channel UUID: {channel_id}", flush=True)
        print(f"State file: {OUT_PATH}", flush=True)

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
