from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from server.core.dependencies import require_admin, get_client_ip
from server.db import (
    get_metrics, list_jobs, get_job, get_ldap_config, save_ldap_config,
    list_audit_logs, list_api_keys, generate_new_api_key,
    update_api_key_status, delete_api_key, list_local_users,
    create_local_user, update_local_user_status, delete_local_user,
    log_audit, get_admin_security_settings, save_admin_security_settings,
    save_admin_passkey, list_admin_passkeys, delete_admin_passkey
)
from server.auth import (
    admin_reset_user_password,
    generate_totp_secret,
    verify_totp_code,
    build_totp_uri,
    create_webauthn_challenge,
    verify_webauthn_client_data,
    ADMIN_USER,
)
from server.cache import purge_all_cached_ocr, purge_cached_ocr, compute_file_hash
from server.storage import storage
from server.logger import get_recent_engine_logs, logger

router = APIRouter(tags=["Admin"])


class LdapConfigRequest(BaseModel):
    server_uri: str
    use_ssl: bool = False
    base_dn: str
    bind_dn: Optional[str] = ""
    bind_password: Optional[str] = ""
    user_search_filter: str = "(sAMAccountName={username})"
    group_search_filter: Optional[str] = "(member={user_dn})"
    allowed_groups: Optional[str] = ""
    is_enabled: bool = True


class CreateApiKeyRequest(BaseModel):
    name: str
    allowed_ips: str = "*"
    rate_limit: int = 60
    expires_in_days: Optional[int] = 365


class UpdateApiKeyStatusRequest(BaseModel):
    is_active: bool


class CreateLocalUserRequest(BaseModel):
    username: str
    password: str
    display_name: str
    role: str = "user"


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class ResetUserPasswordRequest(BaseModel):
    new_password: str


@router.get("/metrics")
async def get_admin_metrics(admin: dict = Depends(require_admin)):
    metrics = get_metrics()
    s3_health = storage.is_healthy()
    return {
        **metrics,
        "storage": s3_health
    }


@router.get("/jobs")
async def get_admin_jobs(limit: int = 50, offset: int = 0, admin: dict = Depends(require_admin)):
    return list_jobs(limit=limit, offset=offset)


@router.get("/ldap-config")
async def get_admin_ldap_config(admin: dict = Depends(require_admin)):
    cfg = get_ldap_config()
    if cfg.get("bind_password"):
        cfg["bind_password"] = "********"
    return cfg


@router.post("/ldap-config")
async def update_admin_ldap_config(req: LdapConfigRequest, admin: dict = Depends(require_admin)):
    current = get_ldap_config()
    data = req.dict()
    if data.get("bind_password") == "********":
        data["bind_password"] = current.get("bind_password", "")
    save_ldap_config(data)
    log_audit("UPDATE_LDAP_CONFIG", admin["username"], "127.0.0.1", f"LDAP config updated by {admin['username']}")
    return {"status": "success", "message": "บันทึกการตั้งค่า LDAP เรียบร้อยแล้ว"}


@router.get("/engine-logs")
async def get_admin_engine_logs(lines: int = 100, admin: dict = Depends(require_admin)):
    return {"logs": get_recent_engine_logs(lines)}


@router.get("/audit-logs")
async def get_admin_audit_logs(limit: int = 100, admin: dict = Depends(require_admin)):
    return {"logs": list_audit_logs(limit)}


@router.get("/api-keys")
async def get_admin_api_keys(admin: dict = Depends(require_admin)):
    """List all registered API keys for external services."""
    return {"keys": list_api_keys()}


@router.post("/api-keys")
async def create_admin_api_key(
    req: CreateApiKeyRequest,
    admin: dict = Depends(require_admin)
):
    """Generate a new API key for an external system. Returns full plain secret key once."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุชื่อระบบผู้ขอใช้งาน (Service Name)")

    record, plain_key = generate_new_api_key(
        name=req.name,
        allowed_ips=req.allowed_ips,
        created_by=admin["username"],
        rate_limit=req.rate_limit,
        expires_in_days=req.expires_in_days
    )
    log_audit("CREATE_API_KEY", admin["username"], "127.0.0.1", f"Created API key for '{req.name}' (IPs: {req.allowed_ips})")
    logger.info(f"Admin '{admin['username']}' created API key '{record['id']}' for service '{req.name}'")

    return {
        "status": "success",
        "key_record": record,
        "api_key": plain_key,
        "message": "สร้าง API Key สำเร็จ กรุณาคัดลอกและบันทึกเก็บไว้ เนื่องจากจะไม่แสดงซ้ำอีก"
    }


@router.put("/api-keys/{key_id}/status")
async def update_admin_api_key_status(
    key_id: str,
    req: UpdateApiKeyStatusRequest,
    admin: dict = Depends(require_admin)
):
    """Activate or revoke an external service API key."""
    success = update_api_key_status(key_id, req.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="API Key not found")
    action_str = "เปิดใช้งาน" if req.is_active else "ระงับการใช้งาน (Revoked)"
    log_audit("UPDATE_API_KEY_STATUS", admin["username"], "127.0.0.1", f"Updated API key {key_id} status to {action_str}")
    return {"status": "success", "key_id": key_id, "is_active": req.is_active}


@router.delete("/api-keys/{key_id}")
async def delete_admin_api_key(
    key_id: str,
    admin: dict = Depends(require_admin)
):
    """Permanently delete an API key."""
    success = delete_api_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API Key not found")
    log_audit("DELETE_API_KEY", admin["username"], "127.0.0.1", f"Deleted API key {key_id}")
    return {"status": "success", "message": "ลบ API Key เรียบร้อยแล้ว", "key_id": key_id}


@router.get("/users")
async def get_admin_local_users(admin: dict = Depends(require_admin)):
    """List all admin-managed local users."""
    return {"users": list_local_users()}


@router.post("/users")
async def create_admin_local_user(
    req: CreateLocalUserRequest,
    admin: dict = Depends(require_admin)
):
    """Create a new local user for Web Portal access (API disabled)."""
    u = req.username.strip().lower()
    if not u or not req.password:
        raise HTTPException(status_code=400, detail="กรุณาระบุ Username และ Password ให้ครบถ้วน")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีความยาวอย่างน้อย 6 ตัวอักษร")

    try:
        record = create_local_user(
            username=u,
            password=req.password,
            display_name=req.display_name or u,
            role=req.role if req.role in ("admin", "user") else "user",
            created_by=admin["username"]
        )
        log_audit("CREATE_LOCAL_USER", admin["username"], "127.0.0.1", f"Created user '{u}' (role: {record['role']})")
        logger.info(f"Admin '{admin['username']}' created local user '{u}'")
        return {"status": "success", "user": record, "message": f"สร้างผู้ใช้งาน '{u}' สำเร็จ"}
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail=f"ชื่อผู้ใช้งาน '{u}' มีอยู่ในระบบแล้ว")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{username}/status")
async def update_admin_local_user_status(
    username: str,
    req: UpdateUserStatusRequest,
    admin: dict = Depends(require_admin)
):
    """Enable or disable a local user account."""
    success = update_local_user_status(username, req.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    status_str = "เปิดใช้งาน" if req.is_active else "ระงับการใช้งาน"
    log_audit("UPDATE_USER_STATUS", admin["username"], "127.0.0.1", f"Updated user '{username}' status to {status_str}")
    return {"status": "success", "username": username, "is_active": req.is_active}


@router.delete("/users/{username}")
async def delete_admin_local_user(
    username: str,
    admin: dict = Depends(require_admin)
):
    """Permanently delete a local user account."""
    success = delete_local_user(username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit("DELETE_USER", admin["username"], "127.0.0.1", f"Deleted user '{username}'")
    return {"status": "success", "message": f"ลบผู้ใช้งาน '{username}' เรียบร้อยแล้ว"}


@router.post("/users/{username}/reset-password")
async def reset_user_password_endpoint(
    username: str,
    req: ResetUserPasswordRequest,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Admin resets password for any user account."""
    ip_addr = get_client_ip(request)
    success, msg = admin_reset_user_password(username, req.new_password, admin["username"], ip=ip_addr)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}


@router.post("/cache/purge-all")
async def purge_all_cache_endpoint(
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Purge all OCR result cache keys from Redis."""
    ip = get_client_ip(request)
    purged_count = purge_all_cached_ocr()
    log_audit("PURGE_ALL_CACHE", admin["username"], ip, f"Purged {purged_count} OCR cache keys")
    return {
        "status": "success",
        "purged_count": purged_count,
        "message": f"ล้างแคช OCR ทั้งหมดในระบบเรียบร้อยแล้ว ({purged_count} รายการ)"
    }


@router.post("/cache/purge/{job_id}")
async def purge_job_cache_endpoint(
    job_id: str,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Purge OCR cache for a specific completed job."""
    ip = get_client_ip(request)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    file_bytes = None
    if job.get("s3_input_key"):
        file_bytes = storage.get_object(job["s3_input_key"])

    if not file_bytes:
        raise HTTPException(status_code=400, detail="ไม่พบไฟล์ต้นฉบับสำหรับคำนวณแฮชแคช")

    file_hash = compute_file_hash(file_bytes)
    deleted = purge_cached_ocr(file_hash)

    log_audit("PURGE_JOB_CACHE", admin["username"], ip, f"Purged cache for job {job_id} ({file_hash[:8]}...) - found={deleted}")
    return {
        "status": "success",
        "job_id": job_id,
        "file_hash": file_hash,
        "found": deleted,
        "message": "ล้างแคชสำหรับเอกสารนี้เรียบร้อยแล้ว" if deleted else "ไม่พบรายการแคชที่ค้างอยู่ในระบบ (อาจหมดอายุแล้ว)"
    }


# ---------------------------------------------------------------------------
# Super Admin Security Settings (Passkey & 2FA TOTP Toggles)
# ---------------------------------------------------------------------------

class UpdateSecuritySettingsRequest(BaseModel):
    totp_enabled: Optional[bool] = None
    passkey_enabled: Optional[bool] = None


class VerifyTotpSetupRequest(BaseModel):
    code: str


class RegisterPasskeyVerifyRequest(BaseModel):
    credential_id: str
    name: str = "Passkey Device"
    public_key: str = ""
    client_data_json: str
    challenge_token: str


@router.get("/security-settings")
async def get_admin_security_settings_endpoint(admin: dict = Depends(require_admin)):
    """Get Super Admin 2FA (TOTP) & Passkey settings and registered Passkeys."""
    cfg = get_admin_security_settings()
    passkeys = list_admin_passkeys()
    has_secret = bool(cfg.get("totp_secret"))
    return {
        "totp_enabled": bool(cfg.get("totp_enabled") == 1),
        "has_totp_secret": has_secret,
        "totp_secret_masked": (cfg["totp_secret"][:4] + "••••" + cfg["totp_secret"][-4:]) if has_secret else "",
        "passkey_enabled": bool(cfg.get("passkey_enabled") == 1),
        "passkeys": passkeys,
        "updated_at": cfg.get("updated_at"),
    }


@router.put("/security/settings")
async def update_admin_security_settings_endpoint(
    req: UpdateSecuritySettingsRequest,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Toggle Super Admin 2FA (TOTP) or Passkey options on/off with anti-lockout guards."""
    ip = get_client_ip(request)
    current = get_admin_security_settings()
    passkeys = list_admin_passkeys()

    if req.totp_enabled is True and not current.get("totp_secret"):
        raise HTTPException(
            status_code=400,
            detail="กรุณาตั้งค่าและยืนยันรหัส QR Code 2FA (TOTP) ก่อนเปิดใช้งานสวิตช์นี้"
        )

    if req.passkey_enabled is True and len(passkeys) == 0:
        raise HTTPException(
            status_code=400,
            detail="กรุณาลงทะเบียน Passkey อย่างน้อย 1 อุปกรณ์ก่อนเปิดใช้งานสวิตช์นี้"
        )

    updated = save_admin_security_settings(
        totp_enabled=req.totp_enabled,
        passkey_enabled=req.passkey_enabled,
    )
    log_audit(
        "UPDATE_SECURITY_SETTINGS",
        admin["username"],
        ip,
        f"Updated security settings: totp_enabled={updated['totp_enabled']}, passkey_enabled={updated['passkey_enabled']}",
    )
    return {
        "status": "success",
        "totp_enabled": updated["totp_enabled"],
        "passkey_enabled": updated["passkey_enabled"],
        "message": "บันทึกการตั้งค่าความปลอดภัยเรียบร้อยแล้ว",
    }


@router.post("/security/totp/setup")
async def setup_admin_totp_endpoint(
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Generate a new TOTP secret and otpauth URI for Super Admin."""
    ip = get_client_ip(request)
    secret = generate_totp_secret()
    save_admin_security_settings(totp_secret=secret)
    uri = build_totp_uri(secret, username=ADMIN_USER, issuer="ThaiOCR ONNX")
    log_audit("SETUP_TOTP_SECRET", admin["username"], ip, "Generated new TOTP secret for Super Admin")
    return {
        "status": "success",
        "secret": secret,
        "otpauth_uri": uri,
        "issuer": "ThaiOCR ONNX",
        "account": ADMIN_USER,
    }


@router.post("/security/totp/verify-and-enable")
async def verify_and_enable_totp_endpoint(
    req: VerifyTotpSetupRequest,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Verify a 6-digit TOTP code against stored secret and enable 2FA."""
    ip = get_client_ip(request)
    cfg = get_admin_security_settings()
    secret = cfg.get("totp_secret", "")
    if not secret:
        raise HTTPException(status_code=400, detail="ยังไม่ได้สร้างรหัสลับ TOTP กรุณากดตั้งค่าใหม่")

    if not verify_totp_code(secret, req.code):
        raise HTTPException(status_code=400, detail="รหัส OTP 6 หลักไม่ถูกต้อง กรุณาตรวจสอบเวลาในโทรศัพท์แล้วลองอีกครั้ง")

    save_admin_security_settings(totp_enabled=True)
    log_audit("ENABLE_TOTP_2FA", admin["username"], ip, "Verified and enabled TOTP 2FA for Super Admin")
    return {
        "status": "success",
        "totp_enabled": True,
        "message": "ยืนยันรหัสสำเร็จ และเปิดใช้งาน 2FA (TOTP) เรียบร้อยแล้ว",
    }


@router.post("/security/passkeys/register-options")
async def register_passkey_options_endpoint(admin: dict = Depends(require_admin)):
    """Generate WebAuthn credential creation options for Super Admin."""
    import base64
    challenge_b64, challenge_token = create_webauthn_challenge(purpose="register")
    user_id_b64 = base64.urlsafe_b64encode(ADMIN_USER.encode("utf-8")).decode("ascii").rstrip("=")
    existing = list_admin_passkeys()
    return {
        "challenge": challenge_b64,
        "challenge_token": challenge_token,
        "rp": {"name": "ThaiOCR ONNX Security", "id": ""},
        "user": {
            "id": user_id_b64,
            "name": ADMIN_USER,
            "displayName": "ผู้ดูแลระบบ (Super Admin)",
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257}, # RS256
        ],
        "timeout": 60000,
        "attestation": "none",
        "excludeCredentials": [{"type": "public-key", "id": pk["id"]} for pk in existing],
    }


@router.post("/security/passkeys/register-verify")
async def register_passkey_verify_endpoint(
    req: RegisterPasskeyVerifyRequest,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Verify WebAuthn registration clientDataJSON and store Passkey credential."""
    ip = get_client_ip(request)
    if not req.credential_id.strip():
        raise HTTPException(status_code=400, detail="ไม่พบรหัส Credential ID จากอุปกรณ์")

    if not verify_webauthn_client_data(req.client_data_json, req.challenge_token, "webauthn.create"):
        raise HTTPException(status_code=400, detail="การตรวจสอบ Challenge ของ Passkey ไม่ผ่านหรือหมดอายุ")

    record = save_admin_passkey(
        cred_id=req.credential_id,
        name=req.name or "Passkey Device",
        public_key=req.public_key or "webauthn_public_key",
        sign_count=0,
    )
    log_audit("REGISTER_PASSKEY", admin["username"], ip, f"Registered Passkey '{record['name']}' ({record['id'][:12]}...)")
    return {
        "status": "success",
        "passkey": record,
        "passkeys": list_admin_passkeys(),
        "message": f"ลงทะเบียน Passkey '{record['name']}' เรียบร้อยแล้ว",
    }


@router.delete("/security/passkeys/{cred_id}")
async def delete_passkey_endpoint(
    cred_id: str,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Remove a registered Super Admin Passkey."""
    ip = get_client_ip(request)
    deleted = delete_admin_passkey(cred_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ไม่พบรายการ Passkey ที่ต้องการลบ")

    cfg = get_admin_security_settings()
    log_audit("DELETE_PASSKEY", admin["username"], ip, f"Deleted Passkey {cred_id[:12]}...")
    return {
        "status": "success",
        "passkeys": list_admin_passkeys(),
        "passkey_enabled": bool(cfg.get("passkey_enabled") == 1),
        "message": "ลบ Passkey เรียบร้อยแล้ว",
    }

