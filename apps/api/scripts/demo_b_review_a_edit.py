# ruff: noqa: E501
#!/usr/bin/env python3
"""DEPRECATED — use demo_dual_approve_review.py instead.

Legacy demo for the pre-dual-approve loop (A respond applied immediately).
The product now requires both teams to approve before the graph edit applies:

  uv run --directory apps/api python scripts/demo_dual_approve_review.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
STATE_IN = Path(__file__).resolve().parents[1] / ".data" / "demo_conflict_then_send_last.json"
STATE_OUT = Path(__file__).resolve().parents[1] / ".data" / "demo_b_review_a_edit_last.json"
POLL_S = float(os.environ.get("DEMO_POLL_S", "3"))
REGEN_WAIT_S = float(os.environ.get("DEMO_REGEN_WAIT_S", "120"))


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


def _auth(token: str, org_id: str, team_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Team-Id": team_id,
    }


def _load_state() -> dict[str, Any]:
    if not STATE_IN.exists():
        raise StepError(
            f"Missing {STATE_IN}. Run scripts/demo_conflict_then_send.py first "
            "(or demo_team_a_to_b_flow.py and point STATE_IN at that file)."
        )
    return json.loads(STATE_IN.read_text())


def main() -> int:
    state = _load_state()
    email = state["email"]
    password = state["password"]
    org_id = state["org_id"]
    team_a = state["team_a_id"]
    team_b = state["team_b_id"]
    channel_id = state["channel_id"]
    posts = state.get("posts") or []
    if not posts:
        raise StepError("State has no posts — re-run the prior A→B send demo.")
    post_id = posts[0]["id"]

    _log(
        "start",
        "B review → A edit → B close (no dual-approve gate)",
        api_base=API_BASE,
        email=email,
        post_id=post_id,
    )
    _log(
        "product_note",
        "Dual-team approve-before-apply is NOT implemented. "
        "A Lead accept/edit applies the node change immediately; "
        "B close is thread acknowledgment only.",
    )

    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            _raise(login, "login")
        token = login.json()["access_token"]
        _log("login", "ok", email=email)

        # Resolve a package-included node for the suggestion target
        post = client.get(f"/api/posts/{post_id}", headers=_auth(token, org_id, team_b))
        if post.status_code != 200:
            _raise(post, "get_post")
        post_body = post.json()
        package_id = post_body.get("package_id") or state.get("package_id")
        _log(
            "get_post",
            "Team B sees post",
            post_id=post_id,
            adapted_preview=(post_body.get("adapted_body") or "")[:160],
            priority=post_body.get("ai_priority"),
            package_id=package_id,
        )

        pkg = client.get(
            f"/api/packages/{package_id}",
            headers=_auth(token, org_id, team_a),
        )
        if pkg.status_code != 200:
            _raise(pkg, "get_package")
        included = list(pkg.json().get("included_node_ids") or [])
        nodes = client.get(
            f"/api/teams/{team_a}/nodes",
            headers=_auth(token, org_id, team_a),
        )
        if nodes.status_code != 200:
            _raise(nodes, "list_nodes")
        node_rows = nodes.json()
        target_node = None
        for n in node_rows:
            if included and n["id"] in included:
                target_node = n
                break
        if target_node is None and node_rows:
            target_node = node_rows[0]
        if target_node is None:
            raise StepError("No nodes on Team A to target with a suggestion")
        node_id = target_node["id"]
        node_before = target_node.get("summary") or target_node.get("label")
        _log(
            "target_node",
            "picked package-included node",
            node_id=node_id,
            label=target_node.get("label"),
            summary_before=(node_before or "")[:160],
            version=target_node.get("version"),
        )

        # --- 1) Team B requests changes + proposes an edit ---
        action = client.post(
            f"/api/posts/{post_id}/review-actions",
            json={
                "action": "request_changes",
                "note": "Ship date still looks wrong for our team — please revise.",
            },
            headers=_auth(token, org_id, team_b),
        )
        if action.status_code != 201:
            _raise(action, "review_action_request_changes")
        _log(
            "b_request_changes",
            "Team B filed request_changes",
            action_id=action.json().get("id"),
            action=action.json().get("action"),
        )

        suggestion_text = (
            "Please change the ship date to Monday 09:00 UTC and call out that "
            "Friday is cancelled so Team B can update marketing."
        )
        sug = client.post(
            f"/api/posts/{post_id}/suggestions",
            json={
                "text": suggestion_text,
                "target_node_id": node_id,
                "suggestion_type": "edit_text",
            },
            headers=_auth(token, org_id, team_b),
        )
        if sug.status_code != 201:
            _raise(sug, "create_suggestion")
        suggestion = sug.json()
        sug_id = suggestion["id"]
        _log(
            "b_suggestion",
            "Team B asked Team A to edit",
            suggestion_id=sug_id,
            status=suggestion.get("status"),
            adapted_preview=(suggestion.get("adapted_preview") or "")[:160],
            target_node_id=suggestion.get("target_node_id"),
        )

        # Decisions should flip toward contested after request_changes
        decisions = client.get(
            f"/api/teams/{team_a}/decisions",
            headers=_auth(token, org_id, team_a),
        )
        if decisions.status_code == 200:
            contested = [
                d
                for d in decisions.json()
                if d.get("status") in {"contested", "proposed", "open", "agreed"}
            ]
            _log(
                "decisions_after_request",
                "Team A decision register snapshot",
                count=len(decisions.json()),
                statuses={
                    s: sum(1 for d in decisions.json() if d.get("status") == s)
                    for s in sorted({d.get("status") for d in decisions.json()})
                },
                sample=[
                    {
                        "id": d.get("id"),
                        "title": (d.get("title") or d.get("text") or "")[:80],
                        "status": d.get("status"),
                    }
                    for d in contested[:5]
                ],
            )

        # --- 2) Team A sees inbox and applies an edit (unilateral) ---
        inbox = client.get(
            f"/api/teams/{team_a}/suggestions",
            headers=_auth(token, org_id, team_a),
        )
        if inbox.status_code != 200:
            _raise(inbox, "list_suggestions")
        open_sugs = [s for s in inbox.json() if s.get("id") == sug_id]
        _log(
            "a_inbox",
            "Team A suggestion queue",
            total=len(inbox.json()),
            matching_open=len(open_sugs),
            status=open_sugs[0].get("status") if open_sugs else None,
        )

        edited = (
            "Ship Monday 09:00 UTC. Friday release is cancelled. "
            "Marketing must be corrected before handoff."
        )
        respond = client.post(
            f"/api/suggestions/{sug_id}/respond",
            json={
                "response": "edit",
                "edited_text": edited,
                "reason": "Accepted Team B feedback; updated ship date.",
            },
            headers=_auth(token, org_id, team_a),
        )
        if respond.status_code != 200:
            _raise(respond, "a_respond_edit")
        responded = respond.json()
        _log(
            "a_edit_applied",
            "Team A Lead applied edit WITHOUT waiting for Team B second approve",
            suggestion_id=sug_id,
            status=responded.get("status"),
            response=responded.get("response"),
            dual_approve_required=False,
        )

        # Confirm node changed immediately
        node_after = client.get(
            f"/api/teams/{team_a}/nodes",
            headers=_auth(token, org_id, team_a),
        )
        if node_after.status_code != 200:
            _raise(node_after, "list_nodes_after")
        updated = next((n for n in node_after.json() if n["id"] == node_id), None)
        _log(
            "node_after_a_edit",
            "source node updated on Team A",
            node_id=node_id,
            summary_before=(node_before or "")[:120],
            summary_after=(updated.get("summary") if updated else None),
            version_after=updated.get("version") if updated else None,
            change_applied_before_b_close=True,
        )

        # --- 3) Team B closes the thread (ack, not approve-to-apply) ---
        closed = client.post(
            f"/api/suggestions/{sug_id}/close",
            headers=_auth(token, org_id, team_b),
        )
        if closed.status_code != 200:
            _raise(closed, "b_close_suggestion")
        _log(
            "b_close",
            "Team B closed suggestion thread (acknowledgment)",
            status=closed.json().get("status"),
            note="Close does not gate apply — apply already happened on A respond",
        )

        # Optional: B finally agrees after seeing the edit
        agree = client.post(
            f"/api/posts/{post_id}/review-actions",
            json={"action": "agree", "note": "Monday plan looks good now."},
            headers=_auth(token, org_id, team_b),
        )
        # Unique per (post, team, user) — may 409 if already filed; that's fine
        _log(
            "b_agree_after",
            "Team B post-level agree (may already exist from request_changes uniqueness)",
            status_code=agree.status_code,
            body=agree.json() if agree.headers.get("content-type", "").startswith("application/json") else agree.text,
        )

        # Poll post for regen / updated flag
        deadline = time.monotonic() + REGEN_WAIT_S
        final_post = post_body
        while time.monotonic() < deadline:
            got = client.get(
                f"/api/posts/{post_id}",
                headers=_auth(token, org_id, team_b),
            )
            if got.status_code != 200:
                _raise(got, "poll_post")
            final_post = got.json()
            _log(
                "poll_post",
                "waiting for regen/update",
                updated_since_send=final_post.get("updated_since_send"),
                adapted_preview=(final_post.get("adapted_body") or "")[:160],
            )
            if final_post.get("updated_since_send") or (
                final_post.get("adapted_body")
                and final_post.get("adapted_body") != post_body.get("adapted_body")
            ):
                break
            time.sleep(POLL_S)

        comments = client.get(
            f"/api/posts/{post_id}/comments",
            headers=_auth(token, org_id, team_b),
        )
        # leave a closing comment from B
        note = client.post(
            f"/api/posts/{post_id}/comments",
            json={"body": "Thanks — Monday 09:00 UTC works for Team B."},
            headers=_auth(token, org_id, team_b),
        )
        _log(
            "b_comment",
            "Team B left follow-up comment",
            status_code=note.status_code,
            comments_before=len(comments.json()) if comments.status_code == 200 else None,
        )

        out = {
            "api_base": API_BASE,
            "email": email,
            "password": password,
            "org_id": org_id,
            "team_a_id": team_a,
            "team_b_id": team_b,
            "channel_id": channel_id,
            "post_id": post_id,
            "package_id": package_id,
            "suggestion_id": sug_id,
            "target_node_id": node_id,
            "dual_team_approve_before_apply": False,
            "flow": [
                "b_request_changes",
                "b_suggestion",
                "a_edit_applied_immediately",
                "b_close_thread",
            ],
            "node_summary_after": updated.get("summary") if updated else None,
            "post_adapted_after": (final_post.get("adapted_body") or "")[:300],
            "web_urls": {
                "login": "http://localhost:3000/en/login",
                "team_b_channels": (
                    f"http://localhost:3000/en/teams/{team_b}/channels?orgId={org_id}"
                ),
                "team_a_suggestions": (
                    f"http://localhost:3000/en/teams/{team_a}/suggestions?orgId={org_id}"
                ),
            },
        }
        STATE_OUT.parent.mkdir(parents=True, exist_ok=True)
        STATE_OUT.write_text(json.dumps(out, indent=2) + "\n")
        _log("state_written", str(STATE_OUT))

        print("\n=== Result ===", flush=True)
        print(
            "PASS: B requested changes + suggested edit; A applied edit; B closed thread.",
            flush=True,
        )
        print(
            "NOTE: Dual-team approve-before-apply is NOT in the product — "
            "A Lead respond applies the change immediately.",
            flush=True,
        )
        print(f"Sign in: {email} / {password}", flush=True)
        print(f"Team B channels: {out['web_urls']['team_b_channels']}", flush=True)
        print(f"  Channel UUID: {channel_id}", flush=True)
        print(f"Team A suggestions: {out['web_urls']['team_a_suggestions']}", flush=True)
        print(f"State: {STATE_OUT}", flush=True)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StepError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
    except httpx.ConnectError as exc:
        print(
            f"ERROR: cannot reach API at {API_BASE}\n{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from exc
