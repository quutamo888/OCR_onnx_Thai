import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routers.system import router as system_router
from server.routers.auth import router as auth_router
from server.routers.export import router as export_router
from server.routers.admin import router as admin_router
from server.routers.ocr import router as ocr_router

app = FastAPI()
app.include_router(system_router)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(export_router)
app.include_router(admin_router, prefix="/api/admin")
app.include_router(ocr_router, prefix="/api/ocr")

client = TestClient(app)


# --- System Router Tests ---

def test_health_endpoint():
    with patch("server.routers.system.is_cache_healthy", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "healthy")
        assert "version" not in data
        assert "service" not in data


def test_api_health_endpoint():
    with patch("server.routers.system.is_cache_healthy", return_value=True):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" not in data
        assert "service" not in data


def test_system_engine_logs_requires_admin():
    response = client.get("/api/engine/logs")
    assert response.status_code == 401

    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}):
        res_user = client.get("/api/engine/logs", headers={"Authorization": "Bearer user_token"})
        assert res_user.status_code == 403

    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}), \
         patch("server.routers.system.get_recent_engine_logs", return_value=["log line 1"]):
        res_admin = client.get("/api/engine/logs", headers={"Authorization": "Bearer admin_token"})
        assert res_admin.status_code == 200
        assert res_admin.json() == {"logs": ["log line 1"]}


# --- Auth Router Tests ---

def test_auth_me_unauthorized():
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_me_authorized():
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        assert response.json()["username"] == "officer1"


def test_auth_login_success():
    with patch("server.routers.auth.auth_login", return_value={"token": "jwt_token", "user": {"username": "admin"}}):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
        assert response.status_code == 200
        assert response.json()["token"] == "jwt_token"


def test_auth_login_invalid():
    with patch("server.routers.auth.auth_login", return_value=None), \
         patch("server.routers.auth.log_audit"):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert response.status_code == 401


def test_auth_login_real_admin_success():
    # Test real un-mocked auth_login with default admin credentials
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@Ocr2026!"})
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["role"] == "admin"


def test_auth_change_password():
    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}), \
         patch("server.routers.auth.change_user_password", return_value=(True, "เปลี่ยนรหัสผ่านเรียบร้อย")):
        response = client.post(
            "/api/auth/change-password",
            headers={"Authorization": "Bearer valid_token"},
            json={"old_password": "Admin@Ocr2026!", "new_password": "newSecurePassword2026"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


def test_admin_reset_user_password():
    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}), \
         patch("server.routers.admin.admin_reset_user_password", return_value=(True, "รีเซ็ตเรียบร้อย")):
        response = client.post(
            "/api/admin/users/officer1/reset-password",
            headers={"Authorization": "Bearer valid_token"},
            json={"new_password": "newPassWord123"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


# --- Export Router Tests ---

def test_export_docx_success():
    fake_job = {"filename": "test_doc.pdf", "user_id": "officer1"}
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}), \
         patch("server.routers.export.get_job", return_value=fake_job), \
         patch("server.routers.export.export_document_docx", return_value=io.BytesIO(b"fake_docx_content")):
        response = client.get("/api/ocr/export/docx/job123", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        assert response.content == b"fake_docx_content"
        assert "Content-Disposition" in response.headers


def test_export_xlsx_success():
    fake_job = {"filename": "test_table.pdf", "user_id": "officer1"}
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}), \
         patch("server.routers.export.get_job", return_value=fake_job), \
         patch("server.routers.export.export_document_xlsx", return_value=io.BytesIO(b"fake_xlsx_content")):
        response = client.get("/api/ocr/export/xlsx/job123", headers={"Authorization": "Bearer valid_token"})
        assert response.status_code == 200
        assert response.content == b"fake_xlsx_content"
        assert "Content-Disposition" in response.headers


def test_export_custom_markdown():
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}):
        response = client.post(
            "/api/ocr/export/txt",
            headers={"Authorization": "Bearer valid_token"},
            json={"markdown": "Hello Text"}
        )
        assert response.status_code == 200
        assert response.content == b"Hello Text"


# --- Admin Router Tests ---

def test_admin_metrics_forbidden():
    with patch("server.core.dependencies.verify_token", return_value={"username": "user1", "role": "user"}):
        response = client.get("/api/admin/metrics", headers={"Authorization": "Bearer token"})
        assert response.status_code == 403


def test_admin_metrics_success():
    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}), \
         patch("server.routers.admin.get_metrics", return_value={"jobs_total": 42}), \
         patch("server.routers.admin.storage.is_healthy", return_value=True):
        response = client.get("/api/admin/metrics", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["jobs_total"] == 42


def test_admin_list_users():
    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}), \
         patch("server.routers.admin.list_local_users", return_value=[{"username": "officer1"}]):
        response = client.get("/api/admin/users", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert "users" in response.json()


def test_admin_api_keys():
    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}), \
         patch("server.routers.admin.list_api_keys", return_value=[{"id": "k1", "name": "service1"}]):
        response = client.get("/api/admin/api-keys", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert len(response.json()["keys"]) == 1


# --- OCR Router Tests ---

def test_ocr_jobs_list():
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}), \
         patch("server.routers.ocr.cleanup_expired_data"), \
         patch("server.routers.ocr.list_jobs", return_value=[{"id": "j1", "created_at": 100}]):
        response = client.get("/api/ocr/jobs", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_ocr_job_detail():
    fake_job = {
        "id": "j1",
        "user_id": "officer1",
        "filename": "doc.pdf",
        "s3_text_key": "txt_key",
        "s3_md_key": "md_key"
    }
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}), \
         patch("server.routers.ocr.get_job", return_value=fake_job), \
         patch("server.routers.ocr.storage.get_object", side_effect=[b"Hello text", b"# Hello md"]):
        response = client.get("/api/ocr/jobs/j1", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Hello text"
        assert data["markdown"] == "# Hello md"


def test_ocr_download_ticket():
    fake_job = {"id": "j1", "user_id": "officer1"}
    with patch("server.core.dependencies.verify_token", return_value={"username": "officer1", "role": "user"}), \
         patch("server.routers.ocr.get_job", return_value=fake_job), \
         patch("server.routers.ocr.issue_download_ticket", return_value="tkt_123"):
        response = client.post(
            "/api/ocr/tickets/download",
            headers={"Authorization": "Bearer token"},
            json={"job_id": "j1", "format": "docx"}
        )
        assert response.status_code == 200
        assert response.json()["ticket"] == "tkt_123"


def test_ocr_download_with_api_key():
    fake_job = {
        "id": "j1",
        "user_id": "service:finance_service",
        "filename": "doc.pdf",
        "s3_text_key": "outputs/j1/result.txt"
    }
    with patch("server.core.dependencies.hash_api_key", return_value="mock_hash"), \
         patch("server.core.dependencies.get_api_key_by_hash", return_value={"id": "k1", "name": "finance_service", "is_active": 1, "role": "service"}), \
         patch("server.core.dependencies.update_api_key_last_used"), \
         patch("server.routers.ocr.get_job", return_value=fake_job), \
         patch("server.routers.ocr.storage.get_object", return_value=b"Extracted OCR text"):
        response = client.get("/api/ocr/download/j1/txt", headers={"X-API-Key": "ocr_sk_test123"})
        assert response.status_code == 200
        assert response.content == b"Extracted OCR text"
        assert response.headers["content-type"].startswith("text/plain")


def test_ocr_download_with_ticket():
    fake_job = {
        "id": "j1",
        "user_id": "officer1",
        "filename": "doc.pdf",
        "s3_text_key": "outputs/j1/result.txt"
    }
    with patch("server.routers.ocr.consume_download_ticket", return_value={"user_id": "officer1", "role": "user"}), \
         patch("server.routers.ocr.get_job", return_value=fake_job), \
         patch("server.routers.ocr.storage.get_object", return_value=b"Extracted OCR text"):
        response = client.get("/api/ocr/download/j1/txt?ticket=valid_tkt")
        assert response.status_code == 200
        assert response.content == b"Extracted OCR text"


def test_ocr_get_source_file_with_api_key():
    fake_job = {
        "id": "j1",
        "user_id": "service:finance_service",
        "filename": "doc.pdf",
        "file_type": "pdf",
        "s3_input_key": "inputs/j1/doc.pdf"
    }
    with patch("server.core.dependencies.hash_api_key", return_value="mock_hash"), \
         patch("server.core.dependencies.get_api_key_by_hash", return_value={"id": "k1", "name": "finance_service", "is_active": 1, "role": "service"}), \
         patch("server.core.dependencies.update_api_key_last_used"), \
         patch("server.routers.ocr.get_job", return_value=fake_job), \
         patch("server.routers.ocr.storage.get_object", return_value=b"%PDF-1.4 dummy"):
        response = client.get("/api/ocr/file/j1", headers={"X-API-Key": "ocr_sk_test123"})
        assert response.status_code == 200
        assert response.content == b"%PDF-1.4 dummy"
        assert response.headers["content-type"] == "application/pdf"


# --- Super Admin 2FA (TOTP) & Passkey Router Tests ---

def test_admin_totp_setup_and_2fa_login_flow():
    from server.auth import generate_totp_code
    from server.db import save_admin_security_settings

    save_admin_security_settings(totp_enabled=False, totp_secret="", passkey_enabled=False)

    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}):
        # 1. Anti-lockout guard prevents enabling TOTP before setup
        bad_toggle = client.put(
            "/api/admin/security/settings",
            headers={"Authorization": "Bearer admin_token"},
            json={"totp_enabled": True}
        )
        assert bad_toggle.status_code == 400

        # 2. Setup TOTP secret
        setup_res = client.post("/api/admin/security/totp/setup", headers={"Authorization": "Bearer admin_token"})
        assert setup_res.status_code == 200
        secret = setup_res.json()["secret"]
        assert "otpauth://totp/" in setup_res.json()["otpauth_uri"]

        # 3. Verify and enable TOTP
        valid_code = generate_totp_code(secret)
        enable_res = client.post(
            "/api/admin/security/totp/verify-and-enable",
            headers={"Authorization": "Bearer admin_token"},
            json={"code": valid_code}
        )
        assert enable_res.status_code == 200
        assert enable_res.json()["totp_enabled"] is True

    # 4. Super Admin password login now requires 2FA
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@Ocr2026!"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data.get("requires_2fa") is True
    assert "mfa_token" in login_data
    assert "token" not in login_data

    # 4b. mfa_token must NOT be accepted as a session Bearer token
    bypass_attempt = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login_data['mfa_token']}"})
    assert bypass_attempt.status_code == 401

    # 5. Invalid 2FA code rejected
    bad_2fa = client.post("/api/auth/verify-2fa", json={"mfa_token": login_data["mfa_token"], "code": "000000"})
    assert bad_2fa.status_code == 401

    # 6. Valid 2FA code issues full JWT token
    good_2fa = client.post(
        "/api/auth/verify-2fa",
        json={"mfa_token": login_data["mfa_token"], "code": generate_totp_code(secret)}
    )
    assert good_2fa.status_code == 200
    assert "token" in good_2fa.json()
    assert good_2fa.json()["user"]["role"] == "admin"

    # Reset state for subsequent tests
    save_admin_security_settings(totp_enabled=False, totp_secret="", passkey_enabled=False)


def test_admin_passkey_registration_and_passwordless_login():
    import base64
    import json
    import struct
    from server.db import save_admin_security_settings, list_admin_passkeys, delete_admin_passkey

    for pk in list_admin_passkeys():
        delete_admin_passkey(pk["id"])
    save_admin_security_settings(totp_enabled=False, totp_secret="", passkey_enabled=False)

    with patch("server.core.dependencies.verify_token", return_value={"username": "admin", "role": "admin"}):
        # 1. Anti-lockout guard prevents enabling passkey with 0 registered credentials
        bad_toggle = client.put(
            "/api/admin/security/settings",
            headers={"Authorization": "Bearer admin_token"},
            json={"passkey_enabled": True}
        )
        assert bad_toggle.status_code == 400

        # 2. Request registration options
        reg_opts = client.post("/api/admin/security/passkeys/register-options", headers={"Authorization": "Bearer admin_token"})
        assert reg_opts.status_code == 200
        reg_data = reg_opts.json()
        challenge = reg_data["challenge"]
        challenge_token = reg_data["challenge_token"]

        client_data_b64 = base64.urlsafe_b64encode(
            json.dumps({"type": "webauthn.create", "challenge": challenge, "origin": "https://localhost:8843"}).encode()
        ).decode().rstrip("=")

        reg_verify = client.post(
            "/api/admin/security/passkeys/register-verify",
            headers={"Authorization": "Bearer admin_token"},
            json={
                "credential_id": "passkey_cred_01",
                "name": "Admin MacBook TouchID",
                "public_key": "cose_pub_key_mock",
                "client_data_json": client_data_b64,
                "challenge_token": challenge_token,
            }
        )
        assert reg_verify.status_code == 200

        # 3. Enable passkey login in settings
        toggle_res = client.put(
            "/api/admin/security/settings",
            headers={"Authorization": "Bearer admin_token"},
            json={"passkey_enabled": True}
        )
        assert toggle_res.status_code == 200
        assert toggle_res.json()["passkey_enabled"] == 1

    # 4. Security options endpoint reports passkey_enabled = True
    sec_opts = client.get("/api/auth/security-options")
    assert sec_opts.status_code == 200
    assert sec_opts.json()["passkey_enabled"] is True

    # 5. Passwordless 1-click Passkey login flow
    login_opts = client.post("/api/auth/passkey/login-options")
    assert login_opts.status_code == 200
    l_data = login_opts.json()
    assert "passkey_cred_01" in [c["id"] for c in l_data["allowCredentials"]]

    get_client_data_b64 = base64.urlsafe_b64encode(
        json.dumps({"type": "webauthn.get", "challenge": l_data["challenge"], "origin": "https://localhost:8843"}).encode()
    ).decode().rstrip("=")
    # 32-byte rpIdHash + 1-byte flags (0x05 = UP+UV) + 4-byte signCount (1)
    auth_data_bytes = (b"\x00" * 32) + b"\x05" + struct.pack(">I", 1)
    auth_data_b64 = base64.urlsafe_b64encode(auth_data_bytes).decode().rstrip("=")
    sig_b64 = base64.urlsafe_b64encode(b"mock_ecdsa_signature_bytes").decode().rstrip("=")

    login_verify = client.post(
        "/api/auth/passkey/login-verify",
        json={
            "credential_id": "passkey_cred_01",
            "client_data_json": get_client_data_b64,
            "authenticator_data": auth_data_b64,
            "signature": sig_b64,
            "challenge_token": l_data["challenge_token"],
        }
    )
    assert login_verify.status_code == 200
    assert "token" in login_verify.json()
    assert login_verify.json()["user"]["role"] == "admin"

    # Cleanup
    delete_admin_passkey("passkey_cred_01")
    save_admin_security_settings(totp_enabled=False, totp_secret="", passkey_enabled=False)



