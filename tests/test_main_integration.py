import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server.main import app, lifespan

client = TestClient(app)


def test_app_health():
    with patch("server.routers.system.is_cache_healthy", return_value=True):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"


def test_security_headers_present():
    with patch("server.routers.system.is_cache_healthy", return_value=True):
        res = client.get("/health")
        assert res.headers.get("Server") == "ThaiOCR-Security-Gateway"
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert res.headers.get("X-XSS-Protection") == "1; mode=block"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_cors_headers_present():
    res = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert res.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


def test_auth_route_mounted():
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_ocr_route_mounted():
    res = client.get("/api/ocr/jobs")
    assert res.status_code == 401


def test_admin_route_mounted():
    res = client.get("/api/admin/metrics")
    assert res.status_code == 401


@pytest.mark.anyio
async def test_lifespan_executes_cleanup():
    with patch("server.main.cleanup_expired_data") as mock_cleanup:
        async with lifespan(app):
            mock_cleanup.assert_called_once()
