from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from server.auth import (
    login as auth_login,
    change_user_password,
    verify_token,
    generate_token,
    verify_totp_code,
    get_super_admin_user_info,
    create_webauthn_challenge,
    verify_webauthn_assertion,
    ADMIN_USER,
)
from server.core.dependencies import get_current_user, get_client_ip
from server.core.security import rate_limiter
from server.db import log_audit, get_admin_security_settings, list_admin_passkeys

router = APIRouter(tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class Verify2FARequest(BaseModel):
    mfa_token: str
    code: str


class PasskeyAssertionRequest(BaseModel):
    credential_id: str
    client_data_json: str
    authenticator_data: str
    signature: str
    challenge_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.get("/security-options")
async def get_public_security_options():
    """Return public login methods enabled for Super Admin (e.g. Passkey button visibility)."""
    sec = get_admin_security_settings()
    has_passkeys = len(list_admin_passkeys()) > 0
    return {
        "passkey_enabled": bool(sec.get("passkey_enabled") == 1 and has_passkeys),
        "totp_enabled": bool(sec.get("totp_enabled") == 1),
    }


@router.post("/login")
async def login_endpoint(req: LoginRequest, request: Request):
    ip_addr = get_client_ip(request)
    if not rate_limiter.is_allowed(f"login:{ip_addr}", max_requests=8, window_seconds=60):
        log_audit("RATE_LIMIT_LOGIN", req.username, ip_addr, "Rate limit exceeded on login")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="มีคำขอเข้าสู่ระบบบ่อยเกินไป เพื่อความปลอดภัยกรุณารอ 1 นาที"
        )

    auth_res = auth_login(req.username, req.password, client_ip=ip_addr)
    if not auth_res:
        log_audit("LOGIN_FAILED", req.username, ip_addr, "Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง หรือไม่มีสิทธิ์เข้าใช้งาน"
        )
    return auth_res


@router.post("/verify-2fa")
async def verify_2fa_endpoint(req: Verify2FARequest, request: Request):
    """Verify Super Admin 6-digit TOTP code to complete login."""
    ip_addr = get_client_ip(request)
    if not rate_limiter.is_allowed(f"2fa:{ip_addr}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="กรอกรหัส 2FA บ่อยเกินไป กรุณารอสักครู่"
        )

    payload = verify_token(req.mfa_token, allow_special=True)
    if not payload or payload.get("type") != "mfa_pending" or payload.get("username") != ADMIN_USER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="เซสชันยืนยันตัวตน 2 ชั้นหมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่"
        )

    sec = get_admin_security_settings()
    if not verify_totp_code(sec.get("totp_secret", ""), req.code):
        log_audit("LOGIN_2FA_FAILED", ADMIN_USER, ip_addr, "Invalid TOTP 2FA code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="รหัส OTP 6 หลักไม่ถูกต้องหรือหมดอายุ"
        )

    user_info = get_super_admin_user_info()
    token = generate_token(user_info)
    log_audit("LOGIN_2FA_SUCCESS", ADMIN_USER, ip_addr, "Super Admin completed 2FA (TOTP) login")
    return {"token": token, "user": user_info}


@router.post("/passkey/login-options")
async def passkey_login_options_endpoint(request: Request):
    """Issue WebAuthn challenge and allowed credential IDs for Super Admin Passkey login."""
    sec = get_admin_security_settings()
    passkeys = list_admin_passkeys()
    if sec.get("passkey_enabled") != 1 or not passkeys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ระบบ Passkey ยังไม่ได้เปิดใช้งานสำหรับผู้ดูแลระบบ"
        )

    challenge_b64, challenge_token = create_webauthn_challenge(purpose="login")
    return {
        "challenge": challenge_b64,
        "challenge_token": challenge_token,
        "timeout": 60000,
        "userVerification": "preferred",
        "allowCredentials": [
            {"type": "public-key", "id": pk["id"]}
            for pk in passkeys
        ],
    }


@router.post("/passkey/login-verify")
async def passkey_login_verify_endpoint(req: PasskeyAssertionRequest, request: Request):
    """Verify WebAuthn Passkey assertion and issue Super Admin JWT."""
    ip_addr = get_client_ip(request)
    if not rate_limiter.is_allowed(f"passkey:{ip_addr}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="มีคำขอยืนยัน Passkey บ่อยเกินไป กรุณารอสักครู่"
        )

    sec = get_admin_security_settings()
    if sec.get("passkey_enabled") != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ระบบ Passkey ปิดการใช้งานอยู่"
        )

    user_info = verify_webauthn_assertion(
        credential_id=req.credential_id,
        client_data_b64=req.client_data_json,
        authenticator_data_b64=req.authenticator_data,
        signature_b64=req.signature,
        challenge_token=req.challenge_token,
    )
    if not user_info:
        log_audit("LOGIN_PASSKEY_FAILED", ADMIN_USER, ip_addr, "Passkey assertion verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="การยืนยันตัวตนด้วย Passkey ไม่สำเร็จ"
        )

    token = generate_token(user_info)
    log_audit("LOGIN_PASSKEY_SUCCESS", ADMIN_USER, ip_addr, f"Super Admin logged in via Passkey ({req.credential_id[:12]}...)")
    return {"token": token, "user": user_info}


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    return user


@router.post("/change-password")
async def change_password_endpoint(
    req: ChangePasswordRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    ip_addr = get_client_ip(request)
    success, msg = change_user_password(user["username"], req.old_password, req.new_password, ip=ip_addr)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"status": "success", "message": msg}
