import asyncio
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock
from server.core.dependencies import require_admin, get_client_ip, get_current_user


def test_require_admin_success():
    admin_user = {"username": "admin", "role": "admin"}
    assert require_admin(admin_user) == admin_user


def test_require_admin_forbidden():
    regular_user = {"username": "officer1", "role": "user"}
    with pytest.raises(HTTPException) as exc_info:
        require_admin(regular_user)
    assert exc_info.value.status_code == 403


def test_get_client_ip_real_ip_priority():
    request = MagicMock()
    request.headers = {
        "X-Real-IP": "10.20.30.40",
        "X-Forwarded-For": "203.0.113.195, 70.41.3.18"
    }
    assert get_client_ip(request) == "10.20.30.40"


def test_get_client_ip_forwarded_for():
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    assert get_client_ip(request) == "203.0.113.195"


def test_get_client_ip_direct():
    request = MagicMock()
    request.headers = {}
    request.client.host = "192.168.1.50"
    assert get_client_ip(request) == "192.168.1.50"


def test_get_client_ip_fallback():
    request = MagicMock()
    request.headers = {}
    request.client = None
    assert get_client_ip(request) == "127.0.0.1"


def test_get_current_user_bearer_success(monkeypatch):
    request = MagicMock()
    request.cookies = {}
    monkeypatch.setattr("server.core.dependencies.verify_token", lambda token: {"username": "officer1", "role": "user"})
    user = asyncio.run(get_current_user(request=request, authorization="Bearer valid_token"))
    assert user["username"] == "officer1"
    assert user["role"] == "user"


def test_get_current_user_cookie_fallback(monkeypatch):
    request = MagicMock()
    request.cookies = {"ocr_session_token": "valid_cookie_token"}
    monkeypatch.setattr("server.core.dependencies.verify_token", lambda token: {"username": "cookie_user", "role": "user"})
    user = asyncio.run(get_current_user(request=request, authorization=None))
    assert user["username"] == "cookie_user"


def test_get_current_user_api_key_success(monkeypatch):
    request = MagicMock()
    request.cookies = {}
    updated_keys = []
    monkeypatch.setattr("server.core.dependencies.hash_api_key", lambda k: "mock_hash")
    monkeypatch.setattr(
        "server.core.dependencies.get_api_key_by_hash",
        lambda h: {"id": "key123", "name": "finance_service", "is_active": 1, "role": "service"}
    )
    monkeypatch.setattr("server.core.dependencies.update_api_key_last_used", lambda kid: updated_keys.append(kid))

    user = asyncio.run(get_current_user(request=request, authorization=None, x_api_key="ocr_sk_test"))
    assert user["username"] == "service:finance_service"
    assert user["role"] == "service"
    assert user["is_api_key"] is True
    assert user["key_id"] == "key123"
    assert updated_keys == ["key123"]


def test_get_current_user_unauthorized():
    request = MagicMock()
    request.cookies = {}
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(request=request, authorization=None, x_api_key=None))
    assert exc_info.value.status_code == 401
