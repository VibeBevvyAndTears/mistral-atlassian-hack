# ruff: noqa: E501, S105
#!/usr/bin/env python3
"""Demo: AI priority ranking on the A↔B channel feed (sort=priority).

Sends three packages with clearly different urgency, waits for posts, then
compares newest vs priority sort on the shared channel.

Usage (mise dev:web running):

  uv run --directory apps/api python scripts/demo_priority_channel_sort.py
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
OUT_PATH = Path(__file__).resolve().parents[1] / ".data" / "demo_priority_channel_sort_last.json"
POST_WAIT_S = float(os.environ.get("DEMO_POST_WAIT_S", "180"))
POLL_S = float(os.environ.get("DEMO_POLL_S", "3"))


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


def _wait_posts(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    team_id: str,
    channel_id: str,
    min_count: int,
    timeout_s: float,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_s
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        resp = client.get(
            f"/api/channels/{channel_id}/posts",
            params={"sort": "newest"},
            headers=_auth(token, org_id, team_id),
        )
        if resp.status_code != 200:
            _raise(resp, "poll_posts")
        last = resp.json().get("items") or []
        if len(last) >= min_count and all(p.get("ai_priority") for p in last):
            return last
        _log("poll_posts", "waiting", count=len(last), with_priority=sum(1 for p in last if p.get("ai_priority")))
        time.sleep(POLL_S)
    return last


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"demo-prio-{suffix}@example.com"
    password = "password123"

    packages = [
        {
            "key": "low",
            "title": "FYI optional reading",
            "body": (
                "Optional FYI only. No action required this quarter. "
                "Background notes on office snack preferences for next all-hands."
            ),
        },
        {
            "key": "mid",
            "title": "Review requested this week",
            "body": (
                "Please review the draft rollout checklist this week when you have time. "
                "No production risk; soft deadline Friday."
            ),
        },
        {
            "key": "high",
            "title": "URGENT production blocker",
            "body": (
                "P0 BLOCKER: production outage affecting customer checkouts NOW. "
                "Immediate action required today — rollback decision needed within 1 hour. "
                "Deadline: today 17:00 UTC. Unanswered: who owns the hotfix?"
            ),
        },
    ]

    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        reg = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": password,
                "username": f"prio_{suffix}",
                "name": "Priority Demo",
            },
        )
        if reg.status_code not in (200, 201):
            _raise(reg, "register")
        token = reg.json()["access_token"]
        _log("register", "ok", email=email)

        org = client.post("/api/orgs", json={"name": f"Prio Org {suffix}"}, headers=_auth(token))
        if org.status_code not in (200, 201):
            _raise(org, "create_org")
        org_id = org.json()["id"]

        team_a = client.post(
            f"/api/orgs/{org_id}/teams",
            json={"name": "Team A Sender"},
            headers=_auth(token, org_id),
        )
        team_b = client.post(
            f"/api/orgs/{org_id}/teams",
            json={"name": "Team B Receiver"},
            headers=_auth(token, org_id),
        )
        if team_a.status_code not in (200, 201) or team_b.status_code not in (200, 201):
            raise StepError("create teams failed")
        team_a_id = team_a.json()["id"]
        team_b_id = team_b.json()["id"]

        for tid, label in ((team_a_id, "A"), (team_b_id, "B")):
            put = client.put(
                f"/api/teams/{tid}/profile",
                json={
                    "data": {
                        "tone": "plain",
                        "role": f"team_{label.lower()}",
                        "responsibilities": ["checkout reliability", "incident response"],
                    }
                },
                headers=_auth(token, org_id, tid),
            )
            if put.status_code != 200:
                _raise(put, f"profile_{label}")

        ch = client.post(
            f"/api/orgs/{org_id}/channels",
            json={"team_a_id": team_a_id, "team_b_id": team_b_id},
            headers=_auth(token, org_id, team_a_id),
        )
        if ch.status_code not in (200, 201):
            _raise(ch, "channel")
        channel_id = ch.json()["id"]
        _log("channel", "ok", channel_id=channel_id)

        # Send low → mid → high so newest-first would put high on top anyway;
        # we still check that priority sort returns ranked order with reasons.
        for item in packages:
            pkg = client.post(
                f"/api/teams/{team_a_id}/packages",
                json={
                    "title": item["title"],
                    "body": item["body"],
                    "target_team_id": team_b_id,
                    "bypass_incomplete_pipeline": True,
                },
                headers=_auth(token, org_id, team_a_id),
            )
            if pkg.status_code != 201:
                _raise(pkg, f"package_{item['key']}")
            package_id = pkg.json()["id"]
            send = client.post(
                f"/api/packages/{package_id}/send",
                headers=_auth(token, org_id, team_a_id),
            )
            if send.status_code not in (200, 202):
                _raise(send, f"send_{item['key']}")
            _log("send", "queued", key=item["key"], package_id=package_id)
            time.sleep(1.0)

        posts = _wait_posts(
            client,
            token=token,
            org_id=org_id,
            team_id=team_b_id,
            channel_id=channel_id,
            min_count=3,
            timeout_s=POST_WAIT_S,
        )
        if len(posts) < 3:
            raise StepError(f"Expected ≥3 posts, got {len(posts)}")

        newest = client.get(
            f"/api/channels/{channel_id}/posts",
            params={"sort": "newest"},
            headers=_auth(token, org_id, team_b_id),
        )
        by_pri = client.get(
            f"/api/channels/{channel_id}/posts",
            params={"sort": "priority"},
            headers=_auth(token, org_id, team_b_id),
        )
        if newest.status_code != 200:
            _raise(newest, "sort_newest")
        if by_pri.status_code != 200:
            _raise(by_pri, "sort_priority")

        newest_rows = newest.json().get("items") or []
        pri_rows = by_pri.json().get("items") or []

        def _summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            out = []
            for p in rows:
                out.append(
                    {
                        "id": p.get("id"),
                        "ai_priority": p.get("ai_priority"),
                        "ai_priority_reason": p.get("ai_priority_reason"),
                        "snippet": (p.get("adapted_body") or "")[:80],
                    }
                )
            return out

        newest_sum = _summarize(newest_rows)
        pri_sum = _summarize(pri_rows)
        _log("sort_newest", "ok", posts=newest_sum)
        _log("sort_priority", "ok", posts=pri_sum)

        ranked = [r["ai_priority"] for r in pri_sum if r["ai_priority"]]
        order = {"p0": 0, "P0": 0, "p1": 1, "P1": 1, "p2": 2, "P2": 2, "p3": 3, "P3": 3}
        ranks = [order.get(str(p), 99) for p in ranked]
        sorted_ok = ranks == sorted(ranks)
        has_reasons = all(r.get("ai_priority_reason") for r in pri_sum)

        # Prefer urgent content ranked at least as high as FYI when AI assigns distinct levels
        urgent = next((r for r in pri_sum if "BLOCKER" in (r.get("snippet") or "").upper() or "outage" in (r.get("snippet") or "").lower()), None)
        fyi = next((r for r in pri_sum if "FYI" in (r.get("snippet") or "").upper() or "snack" in (r.get("snippet") or "").lower()), None)
        relative_ok = True
        if urgent and fyi and urgent.get("ai_priority") and fyi.get("ai_priority"):
            relative_ok = order.get(str(urgent["ai_priority"]), 99) <= order.get(
                str(fyi["ai_priority"]), 99
            )

        verdict = {
            "ai_assigned_priorities": ranked,
            "priority_sort_monotonic": sorted_ok,
            "all_have_reasons": has_reasons,
            "urgent_ranked_above_or_equal_fyi": relative_ok,
            "pass": bool(ranked) and sorted_ok and has_reasons,
        }
        _log("verdict", "done", **verdict)

        out = {
            "email": email,
            "password": password,
            "org_id": org_id,
            "team_a_id": team_a_id,
            "team_b_id": team_b_id,
            "channel_id": channel_id,
            "newest": newest_sum,
            "priority": pri_sum,
            "verdict": verdict,
            "web_url": (
                f"http://localhost:3000/en/teams/{team_b_id}/channels"
                f"?orgId={org_id}"
            ),
        }
        OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
        _log("done", "wrote state", path=str(OUT_PATH))
        print("\n=== Channel priority filter ===", flush=True)
        print(f"Sign in: {email} / {password}", flush=True)
        print(f"Open Team B channels → set sort to Priority: {out['web_url']}", flush=True)
        print(f"Channel id: {channel_id}", flush=True)
        for i, r in enumerate(pri_sum, 1):
            print(
                f"  {i}. [{r['ai_priority']}] {r['ai_priority_reason']!r} — {r['snippet']!r}",
                flush=True,
            )
        if not verdict["pass"]:
            raise StepError(f"Priority ranking check failed: {verdict}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StepError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
