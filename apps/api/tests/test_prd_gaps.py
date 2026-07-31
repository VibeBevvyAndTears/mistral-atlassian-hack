"""PRD gap closeout tests — parse, checklist FR-9, leak sentinel, FakeAI."""

from __future__ import annotations

import inspect
import io
import uuid
import zipfile
from uuid import UUID

import pytest
from fastapi import HTTPException
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


def _auth(token: str, org_id: str | None = None, team_id: str | None = None) -> dict[str, str]:  # noqa: E501
    headers = {"Authorization": f"Bearer {token}"}
    if org_id:
        headers["X-Org-Id"] = org_id
    if team_id:
        headers["X-Team-Id"] = team_id
    return headers


def _docx_bytes(text: str) -> bytes:
    """Minimal DOCX (zip + document.xml) for parser tests."""
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
    return buf.getvalue()


def test_parse_txt_docx_and_empty() -> None:
    from src.documents.parse import DocumentParseError, extract_text

    parsed = extract_text("note.txt", b"Hello world\nShip Friday")
    assert "Ship Friday" in parsed.text
    assert parsed.text.find("Ship") >= 0

    docx = extract_text("spec.docx", _docx_bytes("Decision: launch Monday"))
    assert "launch Monday" in docx.text

    with pytest.raises(DocumentParseError):
        extract_text("empty.txt", b"")


@pytest.mark.asyncio
async def test_mistral_ocr_fallback_for_empty_pdf(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: E501
    from src.documents import parse as parse_mod

    class _FakeOcr:
        async def ocr_document(self, data: bytes, *, filename: str = "document.pdf") -> str:  # noqa: E501
            assert data.startswith(b"%PDF")
            assert filename.endswith(".pdf")
            return "OCR: Ship Friday from scan"

    monkeypatch.setattr(
        parse_mod,
        "_parse_pdf_native",
        lambda _data: "",
    )
    # Minimal PDF header so sniff treats as PDF
    data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    parsed = await parse_mod.extract_text_async(
        "scan.pdf", data, ocr_provider=_FakeOcr()  # type: ignore[arg-type]
    )
    assert parsed.method == "mistral-ocr"
    assert "Ship Friday" in parsed.text


def test_mistral_provider_has_ocr() -> None:
    from src.ai import mistral as mod

    src = inspect.getsource(mod.MistralProvider)
    assert "ocr_document" in src
    assert "mistral-ocr-latest" in src or "DEFAULT_OCR_MODEL" in src
    assert "process_async" in src


def test_cross_team_leak_sentinel() -> None:
    from src.channels.containment import assert_claim_ids_contained

    assert_claim_ids_contained(
        allowed_claim_ids={"a", "b"}, referenced_claim_ids={"a", "b"}
    )
    with pytest.raises(HTTPException) as exc:
        assert_claim_ids_contained(
            allowed_claim_ids={"a"}, referenced_claim_ids={"a", "leaked"}
        )
    assert exc.value.status_code == 500
    assert exc.value.detail == "cross_team_leak_prevented"


def test_no_fake_ai_on_prod_paths() -> None:
    for name in (
        "src.jobs.kinds.ingest_document",
        "src.jobs.kinds.send_package",
        "src.jobs.kinds.regenerate_rendition",
        "src.review.service",
    ):
        mod = __import__(name, fromlist=["*"])
        src = inspect.getsource(mod)
        assert "FakeAIProvider(" not in src
        assert "get_mistral_provider" in src


def test_checklist_unowned_decision_fails(client: TestClient) -> None:
    import asyncio

    from src.channels.service import run_presend_checklist
    from src.conflict.models import Decision
    from src.lib.database import async_session_factory

    token = _register(client, f"gap-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "Gap"}, headers=_auth(token)).json()["id"]  # noqa: E501
    team = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Core"},
        headers=_auth(token, org),
    ).json()["id"]
    client.put(
        f"/api/teams/{team}/profile",
        json={"data": {"tone": "plain"}},
        headers=_auth(token, org, team),
    )

    async def _seed() -> None:
        async with async_session_factory() as session:
            # claim_id FK — use random UUID; SQLite tests may not enforce FK strictly
            session.add(
                Decision(
                    id=uuid.uuid4(),
                    org_id=UUID(org),
                    team_id=UUID(team),
                    claim_id=uuid.uuid4(),
                    title="Unowned",
                    body="Decide later",
                    source="test",
                    owner_team_id=None,
                    status="open",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    async def _check() -> dict:
        async with async_session_factory() as session:
            checks, _ = await run_presend_checklist(
                session,
                org_id=UUID(org),
                team_id=UUID(team),
                bypass_incomplete=True,
            )
            return checks

    checks = asyncio.run(_check())
    assert checks["no_unowned_decisions"] is False
    assert checks["ok"] is False
    assert "Unowned" in checks["unowned_decision_titles"]


def test_channel_decision_register_and_send_blocks_unowned(client: TestClient) -> None:
    import asyncio

    from src.conflict.models import Decision
    from src.lib.database import async_session_factory

    token = _register(client, f"dec-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post(
        "/api/orgs", json={"name": "DecOrg"}, headers=_auth(token)
    ).json()["id"]
    eng = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Engineering"},
        headers=_auth(token, org),
    ).json()["id"]
    mkt = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Marketing"},
        headers=_auth(token, org),
    ).json()["id"]
    design = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Design"},
        headers=_auth(token, org),
    ).json()["id"]
    client.put(
        f"/api/teams/{eng}/profile",
        json={"data": {"tone": "plain"}},
        headers=_auth(token, org, eng),
    )

    ch_mkt = client.post(
        f"/api/orgs/{org}/channels",
        json={"team_a_id": eng, "team_b_id": mkt},
        headers=_auth(token, org, eng),
    )
    assert ch_mkt.status_code == 201, ch_mkt.text
    ch_design = client.post(
        f"/api/orgs/{org}/channels",
        json={"team_a_id": eng, "team_b_id": design},
        headers=_auth(token, org, eng),
    )
    assert ch_design.status_code == 201, ch_design.text

    listed = client.get(
        f"/api/teams/{eng}/channels",
        headers=_auth(token, org, eng),
    )
    assert listed.status_code == 200
    peers = {c["peer_team_name"] for c in listed.json()}
    assert peers == {"Marketing", "Design"}

    async def _seed() -> None:
        async with async_session_factory() as session:
            session.add(
                Decision(
                    id=uuid.uuid4(),
                    org_id=UUID(org),
                    team_id=UUID(eng),
                    claim_id=uuid.uuid4(),
                    title="Region list",
                    body="No owner yet",
                    source="test",
                    owner_team_id=None,
                    status="open",
                    channel_id=UUID(ch_mkt.json()["id"]),
                )
            )
            session.add(
                Decision(
                    id=uuid.uuid4(),
                    org_id=UUID(org),
                    team_id=UUID(eng),
                    claim_id=uuid.uuid4(),
                    title="Palette",
                    body="Design-only",
                    source="test",
                    owner_team_id=UUID(eng),
                    status="open",
                    channel_id=UUID(ch_design.json()["id"]),
                )
            )
            await session.commit()

    asyncio.run(_seed())

    mkt_decisions = client.get(
        f"/api/channels/{ch_mkt.json()['id']}/decisions",
        params={"status": "all"},
        headers=_auth(token, org, eng),
    )
    assert mkt_decisions.status_code == 200, mkt_decisions.text
    titles = {d["title"] for d in mkt_decisions.json()}
    assert "Region list" in titles
    assert "Palette" not in titles

    design_decisions = client.get(
        f"/api/channels/{ch_design.json()['id']}/decisions",
        params={"status": "all"},
        headers=_auth(token, org, eng),
    )
    assert design_decisions.status_code == 200
    design_titles = {d["title"] for d in design_decisions.json()}
    assert "Palette" in design_titles
    assert "Region list" not in design_titles

    pkg = client.post(
        f"/api/teams/{eng}/packages",
        json={
            "title": "Handoff",
            "body": "Ship Friday",
            "target_team_id": mkt,
            "bypass_incomplete_pipeline": True,
        },
        headers=_auth(token, org, eng),
    )
    assert pkg.status_code == 201, pkg.text
    assert pkg.json()["checklist"]["ok"] is False
    assert pkg.json()["checklist"]["no_unowned_decisions"] is False

    sent = client.post(
        f"/api/packages/{pkg.json()['id']}/send",
        headers=_auth(token, org, eng),
    )
    assert sent.status_code == 400
    assert "owner" in sent.json()["detail"].lower()


def test_decision_filter_and_upload_empty(client: TestClient) -> None:
    token = _register(client, f"gap2-{uuid.uuid4().hex[:8]}@example.com")
    org = client.post("/api/orgs", json={"name": "Gap2"}, headers=_auth(token)).json()["id"]  # noqa: E501
    team = client.post(
        f"/api/orgs/{org}/teams",
        json={"name": "Core"},
        headers=_auth(token, org),
    ).json()["id"]

    listed = client.get(
        f"/api/teams/{team}/decisions",
        params={"status": "all"},
        headers=_auth(token, org, team),
    )
    assert listed.status_code == 200

    empty = client.post(
        f"/api/teams/{team}/documents",
        headers=_auth(token, org, team),
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert empty.status_code == 400

    ok = client.post(
        f"/api/teams/{team}/documents",
        headers=_auth(token, org, team),
        files={"file": ("note.txt", io.BytesIO(b"We ship Friday."), "text/plain")},
    )
    assert ok.status_code == 201, ok.text
