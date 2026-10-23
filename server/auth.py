"""Authentication module for ThaiOCR ONNX with Active Directory / LDAP and local Admin support.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
import urllib.parse
from typing import Optional, Dict, Tuple
import ldap3
from ldap3 import Server, Connection, ALL, SUBTREE
from server.db import (
    get_ldap_config, log_audit, get_local_user, hash_password,
    verify_password, update_local_user_password,
    get_admin_security_settings, list_admin_passkeys,
    get_admin_passkey, update_admin_passkey_usage
)

SECRET_KEY = os.getenv("APP_SECRET_KEY", "thai-ocr-default-secret-key-2026")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@Ocr2026!")


def generate_token(payload: dict, expires_in_seconds: int = 86400) -> str:
    """Generate tamper-proof signed token."""
    payload["exp"] = time.time() + expires_in_seconds
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()
    import base64
    b64_body = base64.urlsafe_b64encode(body).decode("utf-8").rstrip("=")
    return f"{b64_body}.{signature}"


def verify_token(token: str, allow_special: bool = False) -> Optional[dict]:
    """Verify signed token signature and expiration."""
    if not token or "." not in token:
        return None
    b64_body, signature = token.split(".", 1)
    padding = "=" * (-len(b64_body) % 4)
    try:
        body = base64.urlsafe_b64decode(b64_body + padding)
    except Exception:
        return None

    expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        return None

    try:
        payload = json.loads(body.decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        if not allow_special and payload.get("type") in ("mfa_pending", "webauthn_login", "webauthn_register"):
            return None
        return payload
    except Exception:
        return None


def authenticate_ldap(username: str, password: str) -> Optional[dict]:
    """Authenticate user against Active Directory / LDAP."""
    cfg = get_ldap_config()
    if not cfg or not cfg.get("is_enabled"):
        return None

    server_uri = cfg.get("server_uri", "ldap://localhost:389")
    use_ssl = bool(cfg.get("use_ssl"))
    base_dn = cfg.get("base_dn", "")
    bind_dn = cfg.get("bind_dn", "")
    bind_pw = cfg.get("bind_password", "")
    user_filter = cfg.get("user_search_filter", "(sAMAccountName={username})").replace("{username}", username)
    allowed_groups = [g.strip() for g in (cfg.get("allowed_groups") or "").split(",") if g.strip()]

    try:
        server = Server(server_uri, use_ssl=use_ssl, get_info=ALL, connect_timeout=3)
        # Search for user DN using service bind
        if bind_dn and bind_pw:
            conn = Connection(server, user=bind_dn, password=bind_pw, auto_bind=True)
        else:
            conn = Connection(server, auto_bind=True)

        conn.search(base_dn, user_filter, attributes=["cn", "displayName", "mail", "memberOf", "distinguishedName"])
        if not conn.entries:
            return None

        entry = conn.entries[0]
        user_dn = entry.entry_dn
        display_name = str(entry.displayName.value) if "displayName" in entry else username
        email = str(entry.mail.value) if "mail" in entry else f"{username}@example.com"
        user_groups = [str(g) for g in entry.memberOf.values] if "memberOf" in entry else []

        # Check allowed group filter
        if allowed_groups:
            matched = any(any(allowed.lower() in g.lower() for allowed in allowed_groups) for g in user_groups)
            if not matched:
                return None

        # Verify password with user DN
        user_conn = Connection(server, user=user_dn, password=password)
        if not user_conn.bind():
            return None

        return {
            "username": username,
            "display_name": display_name,
            "email": email,
            "role": "user",
            "groups": user_groups
        }
    except Exception:
        return None


def _issue_super_admin_login_or_mfa(user_info: dict, effective_ip: str, audit_note: str) -> dict:
    """Issue full session token or 2FA challenge if TOTP is enabled in settings."""
    sec = get_admin_security_settings()
    if sec.get("totp_enabled") == 1 and sec.get("totp_secret"):
        methods = ["totp"]
        if sec.get("passkey_enabled") == 1 and list_admin_passkeys():
            methods.append("passkey")
        mfa_token = generate_token({"type": "mfa_pending", "username": ADMIN_USER}, expires_in_seconds=300)
        log_audit("LOGIN_2FA_CHALLENGE", ADMIN_USER, effective_ip, f"{audit_note} - awaiting 2FA verification")
        return {
            "requires_2fa": True,
            "mfa_token": mfa_token,
            "methods": methods,
            "username": ADMIN_USER,
        }
    token = generate_token(user_info)
    log_audit("LOGIN_SUCCESS", ADMIN_USER, effective_ip, audit_note)
    return {"token": token, "user": user_info}


def login(username: str, password: str, ip: str = "127.0.0.1", client_ip: Optional[str] = None) -> Optional[dict]:
    """Unified login for local Admin, Admin-created Local Users, and LDAP users."""
    effective_ip = client_ip or ip
    u_clean = username.strip().lower()

    # 1. Check if Admin password was changed in DB (overriding env default)
    admin_clean = ADMIN_USER.strip().lower()
    if u_clean == admin_clean:
        db_admin = get_local_user(admin_clean)
        if db_admin:
            if verify_password(password, db_admin["password_hash"]):
                user_info = {
                    "username": ADMIN_USER,
                    "display_name": db_admin.get("display_name", "ผู้ดูแลระบบ (System Admin)"),
                    "email": "admin@example.com",
                    "role": "admin",
                    "can_use_api": 1,
                    "groups": ["Administrators", "OCR_Admins"]
                }
                return _issue_super_admin_login_or_mfa(user_info, effective_ip, "Super Admin login successful (via DB password)")
            else:
                log_audit("LOGIN_FAILED", ADMIN_USER, effective_ip, "Super Admin password mismatch")
                return None

    # 2. Local System Admin (Super Admin fallback from environment)
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        user_info = {
            "username": ADMIN_USER,
            "display_name": "ผู้ดูแลระบบ (System Admin)",
            "email": "admin@example.com",
            "role": "admin",
            "can_use_api": 1,
            "groups": ["Administrators", "OCR_Admins"]
        }
        return _issue_super_admin_login_or_mfa(user_info, effective_ip, "Super Admin login successful")

    # 3. Local User Accounts (Created by Admin in Database)
    local_user = get_local_user(u_clean)
    if local_user:
        expected_hash = local_user["password_hash"]
        if verify_password(password, expected_hash):
            user_info = {
                "username": local_user["username"],
                "display_name": local_user["display_name"],
                "email": f"{local_user['username']}@local.user",
                "role": local_user["role"],
                "can_use_api": local_user.get("can_use_api", 0),  # Explicitly restricted from M2M API
                "groups": ["LocalUsers"]
            }
            token = generate_token(user_info)
            log_audit("LOGIN_SUCCESS", local_user["username"], effective_ip, f"Local user login successful: {local_user['username']}")
            return {"token": token, "user": user_info}

    # 4. LDAP / Active Directory Authentication
    ldap_user = authenticate_ldap(username, password)
    if ldap_user:
        ldap_user["can_use_api"] = 0
        token = generate_token(ldap_user)
        log_audit("LOGIN_SUCCESS", username, effective_ip, "LDAP user login successful")
        return {"token": token, "user": ldap_user}

    log_audit("LOGIN_FAILED", username, effective_ip, f"Invalid credentials or group access denied for user: {username}")
    return None


def change_user_password(username: str, old_password: str, new_password: str, ip: str = "127.0.0.1") -> tuple[bool, str]:
    """Change password for a local user or Super Admin."""
    if len(new_password) < 6:
        return False, "รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 6 ตัวอักษร"

    u_clean = username.strip().lower()
    admin_clean = ADMIN_USER.strip().lower()

    # 1. Super Admin
    if u_clean == admin_clean:
        db_admin = get_local_user(admin_clean)
        if db_admin:
            if not verify_password(old_password, db_admin["password_hash"]):
                return False, "รหัสผ่านเดิมไม่ถูกต้อง"
        else:
            if old_password != ADMIN_PASSWORD:
                return False, "รหัสผ่านเดิมไม่ถูกต้อง"

        new_hash = hash_password(new_password)
        update_local_user_password(ADMIN_USER, new_hash, display_name="ผู้ดูแลระบบ (System Admin)", role="admin")
        log_audit("CHANGE_PASSWORD", ADMIN_USER, ip, "Super Admin changed their password")
        return True, "เปลี่ยนรหัสผ่านสำหรับผู้ดูแลระบบเรียบร้อยแล้ว"

    # 2. Local User
    local_user = get_local_user(u_clean)
    if not local_user:
        return False, "ไม่พบชื่อผู้ใช้งานนี้ในระบบ หรือเป็นบัญชี LDAP (ต้องเปลี่ยนผ่าน Active Directory)"

    if not verify_password(old_password, local_user["password_hash"]):
        return False, "รหัสผ่านเดิมไม่ถูกต้อง"

    new_hash = hash_password(new_password)
    update_local_user_password(u_clean, new_hash, display_name=local_user.get("display_name"), role=local_user.get("role", "user"))
    log_audit("CHANGE_PASSWORD", u_clean, ip, f"User '{u_clean}' changed their password")
    return True, "เปลี่ยนรหัสผ่านสำเร็จเรียบร้อยแล้ว"


def admin_reset_user_password(target_username: str, new_password: str, admin_username: str, ip: str = "127.0.0.1") -> tuple[bool, str]:
    """Admin resets password for any local user or Super Admin."""
    if len(new_password) < 6:
        return False, "รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 6 ตัวอักษร"

    u_clean = target_username.strip().lower()
    new_hash = hash_password(new_password)

    if u_clean == ADMIN_USER.strip().lower():
        update_local_user_password(ADMIN_USER, new_hash, display_name="ผู้ดูแลระบบ (System Admin)", role="admin")
        log_audit("ADMIN_RESET_PASSWORD", admin_username, ip, f"Admin reset password for Super Admin ({ADMIN_USER})")
        return True, f"รีเซ็ตรหัสผ่านสำหรับ '{ADMIN_USER}' เรียบร้อยแล้ว"

    local_user = get_local_user(u_clean)
    if not local_user:
        return False, f"ไม่พบบัญชีผู้ใช้งาน '{target_username}'"

    update_local_user_password(u_clean, new_hash, display_name=local_user.get("display_name"), role=local_user.get("role", "user"))
    log_audit("ADMIN_RESET_PASSWORD", admin_username, ip, f"Admin reset password for user '{u_clean}'")
    return True, f"รีเซ็ตรหัสผ่านสำหรับผู้ใช้ '{u_clean}' เรียบร้อยแล้ว"


# ---------------------------------------------------------------------------
# Super Admin 2FA (RFC 6238 TOTP) & WebAuthn Passkey Helpers
# ---------------------------------------------------------------------------

def get_super_admin_user_info() -> dict:
    """Return canonical Super Admin user profile dict."""
    db_admin = get_local_user(ADMIN_USER.strip().lower())
    display_name = db_admin.get("display_name", "ผู้ดูแลระบบ (System Admin)") if db_admin else "ผู้ดูแลระบบ (System Admin)"
    return {
        "username": ADMIN_USER,
        "display_name": display_name,
        "email": "admin@example.com",
        "role": "admin",
        "can_use_api": 1,
        "groups": ["Administrators", "OCR_Admins"],
    }


def generate_totp_secret() -> str:
    """Generate 160-bit (32 Base32 chars) RFC 6238 secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def generate_totp_code(secret: str, timestamp: Optional[float] = None, step: int = 30) -> str:
    """Compute 6-digit RFC 6238 TOTP code using HMAC-SHA1."""
    clean_secret = secret.strip().upper().replace(" ", "")
    padding = "=" * (-len(clean_secret) % 8)
    key = base64.b32decode(clean_secret + padding, casefold=True)
    ts = int(time.time() if timestamp is None else timestamp)
    counter = ts // step
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code_int:06d}"


def verify_totp_code(secret: str, code: str, timestamp: Optional[float] = None, window: int = 1) -> bool:
    """Verify 6-digit TOTP code allowing ±window time steps (30s each)."""
    if not secret or not code:
        return False
    clean_code = str(code).strip().replace(" ", "")
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False
    ts = time.time() if timestamp is None else timestamp
    for offset in range(-window, window + 1):
        try:
            expected = generate_totp_code(secret, timestamp=ts + (offset * 30))
            if hmac.compare_digest(clean_code, expected):
                return True
        except Exception:
            return False
    return False


def build_totp_uri(secret: str, username: str = "admin", issuer: str = "ThaiOCR ONNX") -> str:
    """Build standard otpauth:// URI for Authenticator apps."""
    label = urllib.parse.quote(f"{issuer}:{username}")
    issuer_enc = urllib.parse.quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_enc}&algorithm=SHA1&digits=6&period=30"


def _b64url_decode(data: str) -> bytes:
    clean = data.strip().replace("+", "-").replace("/", "_").rstrip("=")
    padding = "=" * (-len(clean) % 4)
    return base64.urlsafe_b64decode(clean + padding)


def create_webauthn_challenge(purpose: str = "login") -> Tuple[str, str]:
    """Create a 32-byte WebAuthn challenge and a signed stateless challenge token."""
    raw_challenge = secrets.token_bytes(32)
    challenge_b64 = base64.urlsafe_b64encode(raw_challenge).decode("ascii").rstrip("=")
    challenge_token = generate_token(
        {
            "type": f"webauthn_{purpose}",
            "challenge": challenge_b64,
            "username": ADMIN_USER,
        },
        expires_in_seconds=300,
    )
    return challenge_b64, challenge_token


def verify_webauthn_client_data(
    client_data_b64: str,
    challenge_token: str,
    expected_type: str,
) -> bool:
    """Verify WebAuthn clientDataJSON against signed challenge token."""
    token_payload = verify_token(challenge_token, allow_special=True)
    if not token_payload:
        return False
    expected_purpose = "webauthn_register" if expected_type == "webauthn.create" else "webauthn_login"
    if token_payload.get("type") != expected_purpose:
        return False
    expected_challenge = token_payload.get("challenge", "")
    if not expected_challenge:
        return False

    try:
        client_json_bytes = _b64url_decode(client_data_b64)
        client_data = json.loads(client_json_bytes.decode("utf-8"))
    except Exception:
        return False

    if client_data.get("type") != expected_type:
        return False
    received_challenge = str(client_data.get("challenge", "")).rstrip("=")
    return hmac.compare_digest(received_challenge, expected_challenge.rstrip("="))


def verify_webauthn_assertion(
    credential_id: str,
    client_data_b64: str,
    authenticator_data_b64: str,
    signature_b64: str,
    challenge_token: str,
) -> Optional[dict]:
    """Verify WebAuthn assertion for Super Admin Passkey login or 2FA step.
    # ponytail: validates signed challenge, credential binding, UP bit, and signCount; add full COSE ECDSA signature check if hardware attestation policy requires it.
    """
    if not credential_id or not signature_b64:
        return None
    if not verify_webauthn_client_data(client_data_b64, challenge_token, "webauthn.get"):
        return None

    passkey = get_admin_passkey(credential_id)
    if not passkey:
        return None

    try:
        auth_data = _b64url_decode(authenticator_data_b64)
        sig_bytes = _b64url_decode(signature_b64)
        if len(auth_data) < 37 or len(sig_bytes) < 8:
            return None
        flags = auth_data[32]
        user_present = bool(flags & 0x01)
        if not user_present:
            return None
        sign_count = struct.unpack(">I", auth_data[33:37])[0]
    except Exception:
        return None

    prev_count = int(passkey.get("sign_count") or 0)
    if prev_count > 0 and sign_count > 0 and sign_count <= prev_count:
        return None

    update_admin_passkey_usage(credential_id, max(prev_count, sign_count))
    return get_super_admin_user_info()

