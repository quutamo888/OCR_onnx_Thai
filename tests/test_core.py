import os
import pytest
from server.core.config import Settings
from server.core.security import RateLimiter, format_content_disposition


def test_settings_defaults():
    settings = Settings()
    assert settings.PROJECT_NAME == "ThaiOCR ONNX API"
    assert settings.VERSION == ""
    assert settings.RETENTION_DAYS == 3
    assert isinstance(settings.ALLOWED_ORIGINS, list)


def test_password_hashing_random_salt_and_legacy_compat():
    import hashlib
    from server.db import hash_password, verify_password

    h1 = hash_password("MySecret123!")
    h2 = hash_password("MySecret123!")
    assert h1 != h2  # Per-hash random salt
    assert h1.startswith("pbkdf2_sha256$")
    assert verify_password("MySecret123!", h1) is True
    assert verify_password("WrongPass", h1) is False

    # Backward compatibility with legacy static salt hash
    legacy_salt = "thai_ocr_user_salt_2026"
    legacy_hash = hashlib.pbkdf2_hmac("sha256", b"LegacyPass99", legacy_salt.encode("utf-8"), 100_000).hex()
    assert verify_password("LegacyPass99", legacy_hash) is True
    assert verify_password("WrongPass", legacy_hash) is False


def test_totp_generation_and_verification():
    from server.auth import generate_totp_secret, generate_totp_code, verify_totp_code, build_totp_uri

    secret = generate_totp_secret()
    assert len(secret) == 32
    code = generate_totp_code(secret, timestamp=1700000000)
    assert len(code) == 6
    assert code.isdigit()

    assert verify_totp_code(secret, code, timestamp=1700000000) is True
    # Adjacent 30s window (+30s) still valid
    assert verify_totp_code(secret, code, timestamp=1700000025) is True
    # Far window invalid
    assert verify_totp_code(secret, code, timestamp=1700000300) is False
    assert verify_totp_code(secret, "000000", timestamp=1700000000) is False

    uri = build_totp_uri(secret, "admin")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={secret}" in uri


def test_admin_security_settings_and_passkeys_db():
    from server.db import (
        get_admin_security_settings,
        save_admin_security_settings,
        save_admin_passkey,
        list_admin_passkeys,
        get_admin_passkey,
        delete_admin_passkey,
    )

    # Clear existing passkeys for clean test state
    for pk in list_admin_passkeys():
        delete_admin_passkey(pk["id"])
    save_admin_security_settings(totp_enabled=False, totp_secret="JBSWY3DPEHPK3PXP", passkey_enabled=False)

    cfg = get_admin_security_settings()
    assert cfg["totp_enabled"] == 0
    assert cfg["passkey_enabled"] == 0
    assert cfg["totp_secret"] == "JBSWY3DPEHPK3PXP"

    # Register a passkey
    pk = save_admin_passkey("cred_test_1", "Windows Hello PC", "pub_key_b64")
    assert pk["id"] == "cred_test_1"
    assert len(list_admin_passkeys()) == 1
    assert get_admin_passkey("cred_test_1")["name"] == "Windows Hello PC"

    # Enable passkey setting
    save_admin_security_settings(passkey_enabled=True)
    assert get_admin_security_settings()["passkey_enabled"] == 1

    # Deleting the last passkey auto-disables passkey_enabled
    assert delete_admin_passkey("cred_test_1") is True
    assert list_admin_passkeys() == []
    assert get_admin_security_settings()["passkey_enabled"] == 0


def test_format_content_disposition_thai():
    header = format_content_disposition("attachment", "เอกสาร_ทดสอบ.pdf")
    assert 'filename*="UTF-8\'\'' in header or "filename*=UTF-8''" in header
    assert "attachment" in header


def test_rate_limiter():
    limiter = RateLimiter()
    key = "test_ip"
    assert limiter.is_allowed(key, max_requests=2, window_seconds=10) is True
    assert limiter.is_allowed(key, max_requests=2, window_seconds=10) is True
    assert limiter.is_allowed(key, max_requests=2, window_seconds=10) is False
