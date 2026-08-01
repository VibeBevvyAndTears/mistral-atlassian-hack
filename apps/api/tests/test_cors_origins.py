"""Regression: local web may be opened via localhost or 127.0.0.1."""

from fastapi.testclient import TestClient

from src.lib.config import get_settings
from src.main import app


def test_cors_allows_localhost_and_loopback_web_origins() -> None:
    settings = get_settings()
    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "http://127.0.0.1:3000" in settings.CORS_ORIGINS

    with TestClient(app) as client:
        for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
            response = client.options(
                "/api/auth/login",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == origin
