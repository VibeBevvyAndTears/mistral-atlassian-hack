"""M7 eval tests — goldens, gate script, FakeAI sentinel."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_auth import _reset_all

API_ROOT = Path(__file__).resolve().parents[1]


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


def test_no_fake_ai_on_prod_paths() -> None:
    modules = [
        "src.jobs.kinds.ingest_document",
        "src.jobs.kinds.send_package",
        "src.jobs.kinds.regenerate_rendition",
        "src.review.service",
    ]
    for name in modules:
        mod = __import__(name, fromlist=["*"])
        src = inspect.getsource(mod)
        assert "FakeAIProvider(" not in src, name
        assert "get_mistral_provider" in src, name


def test_eval_gate_script_passes_fixtures() -> None:
    script = API_ROOT / "scripts" / "eval_regression_gate.py"
    fixtures = API_ROOT / "tests" / "fixtures" / "golden_examples.json"
    assert fixtures.exists()
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(script), "--fixtures", str(fixtures)],
        cwd=str(API_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] in ("passed", "skipped")


def test_golden_crud_and_run(client: TestClient) -> None:
    token = _register(client, f"m7-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "M7"}, headers=_auth(token)).json()[
        "id"
    ]
    team = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Eval"},
        headers=_auth(token, org),
    ).json()["id"]

    created = client.post(
        f"/api/orgs/{org}/eval/goldens",
        json={
            "kind": "conflict",
            "input_json": {"actual": {"is_conflict": True}},
            "expected_json": {"is_conflict": True},
            "notes": "unit",
        },
        headers=_auth(token, org, team),
    )
    assert created.status_code == 201, created.text

    listed = client.get(
        f"/api/orgs/{org}/eval/goldens",
        headers=_auth(token, org, team),
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    run = client.post(
        f"/api/orgs/{org}/eval/run",
        headers=_auth(token, org, team),
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] in ("passed", "skipped", "failed")
