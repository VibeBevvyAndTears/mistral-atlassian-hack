# ruff: noqa: E501
#!/usr/bin/env python3
"""Demo: dual-team approve before applying a suggested edit.

Flow:
  1. Reuse post from demo_conflict_then_send_last.json
  2. Team B: request_changes + suggestion
  3. Team A Lead: edit/propose → status=awaiting_approvals (NOT applied yet)
  4. Assert node unchanged
  5. Team B: approve → both approved → applied
  6. Team B: close thread

Usage:
  uv run --directory apps/api python scripts/demo_dual_approve_review.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
STATE_IN = Path(__file__).resolve().parents[1] / ".data" / "demo_conflict_then_send_last.json"
STATE_OUT = Path(__file__).resolve().parents[1] / ".data" / "demo_dual_approve_last.json"


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


def main() -> int:
    if not STATE_IN.exists():
        raise StepError(f"Missing {STATE_IN} — run demo_conflict_then_send.py first")
    state = json.loads(STATE_IN.read_text())
    email = state["email"]
    password = state["password"]
    org_id = state["org_id"]
    team_a = state["team_a_id"]
    team_b = state["team_b_id"]
    post_id = state["posts"][0]["id"]
    package_id = state["package_id"]

    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        login = client.post("/api/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            _raise(login, "login")
        token = login.json()["access_token"]
        _log("login", "ok", email=email, post_id=post_id)

        pkg = client.get(f"/api/packages/{package_id}", headers=_auth(token, org_id, team_a))
        if pkg.status_code != 200:
            _raise(pkg, "get_package")
        included = list(pkg.json().get("included_node_ids") or [])
        nodes = client.get(f"/api/teams/{team_a}/nodes", headers=_auth(token, org_id, team_a))
        if nodes.status_code != 200:
            _raise(nodes, "list_nodes")
        node = next((n for n in nodes.json() if n["id"] in included), None) or nodes.json()[0]
        node_id = node["id"]
        summary_before = node.get("summary")
        version_before = node.get("version")
        _log("target_node", "ok", node_id=node_id, summary=summary_before, version=version_before)

        # Fresh suggestion each run
        sug = client.post(
            f"/api/posts/{post_id}/suggestions",
            json={
                "text": "Ship Monday 09:00 UTC; Friday cancelled for marketing sync.",
                "target_node_id": node_id,
                "suggestion_type": "edit_text",
            },
            headers=_auth(token, org_id, team_b),
        )
        if sug.status_code != 201:
            _raise(sug, "create_suggestion")
        sug_id = sug.json()["id"]
        _log("b_suggest", "ok", suggestion_id=sug_id, status=sug.json()["status"])

        edited = (
            "Ship Monday 09:00 UTC. Friday release is cancelled. "
            "Marketing correction required before handoff."
        )
        proposed = client.post(
            f"/api/suggestions/{sug_id}/respond",
            json={"response": "edit", "edited_text": edited, "reason": "Aligned with B feedback"},
            headers=_auth(token, org_id, team_a),
        )
        if proposed.status_code != 200:
            _raise(proposed, "a_propose")
        body = proposed.json()
        if body["status"] != "awaiting_approvals":
            raise StepError(f"Expected awaiting_approvals, got {body['status']}")
        _log(
            "a_propose",
            "staged — not applied yet",
            status=body["status"],
            approved=body.get("approved_team_ids"),
            awaiting=body.get("awaiting_team_ids"),
            proposed_text=body.get("proposed_text"),
        )

        mid = client.get(f"/api/teams/{team_a}/nodes", headers=_auth(token, org_id, team_a))
        mid_node = next(n for n in mid.json() if n["id"] == node_id)
        if mid_node.get("summary") != summary_before:
            raise StepError("Node changed before Team B approved — dual-approve broken")
        _log("assert_not_applied", "node unchanged before B approve", version=mid_node.get("version"))

        approved = client.post(
            f"/api/suggestions/{sug_id}/approve",
            headers=_auth(token, org_id, team_b),
        )
        if approved.status_code != 200:
            _raise(approved, "b_approve")
        ab = approved.json()
        if ab["status"] != "applied":
            raise StepError(f"Expected applied after both approvals, got {ab['status']}")
        _log(
            "b_approve_applied",
            "both teams approved — change applied",
            status=ab["status"],
            approved=ab.get("approved_team_ids"),
        )

        after = client.get(f"/api/teams/{team_a}/nodes", headers=_auth(token, org_id, team_a))
        after_node = next(n for n in after.json() if n["id"] == node_id)
        if after_node.get("summary") != edited:
            raise StepError(f"Node summary not updated: {after_node.get('summary')!r}")
        _log(
            "node_applied",
            "ok",
            summary_after=after_node.get("summary"),
            version_after=after_node.get("version"),
        )

        closed = client.post(
            f"/api/suggestions/{sug_id}/close",
            headers=_auth(token, org_id, team_b),
        )
        if closed.status_code != 200:
            _raise(closed, "b_close")
        _log("b_close", "ok", status=closed.json()["status"])

        out = {
            "email": email,
            "password": password,
            "org_id": org_id,
            "team_a_id": team_a,
            "team_b_id": team_b,
            "post_id": post_id,
            "suggestion_id": sug_id,
            "node_id": node_id,
            "dual_team_approve_before_apply": True,
            "web_urls": {
                "team_a_suggestions": (
                    f"http://localhost:3000/en/teams/{team_a}/suggestions?orgId={org_id}"
                ),
                "team_b_channels": (
                    f"http://localhost:3000/en/teams/{team_b}/channels?orgId={org_id}"
                ),
            },
        }
        STATE_OUT.write_text(json.dumps(out, indent=2) + "\n")
        _log("done", "PASS dual-approve flow", state=str(STATE_OUT))
        print("\n=== UI ===", flush=True)
        print(f"Sign in: {email} / {password}", flush=True)
        print(f"Team A suggestions: {out['web_urls']['team_a_suggestions']}", flush=True)
        print(f"Team B channels: {out['web_urls']['team_b_channels']}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StepError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
