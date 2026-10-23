import time
from fastapi import Depends, Header, HTTPException, Request, status
from typing import Optional, Dict, Any

from server.auth import verify_token
from server.db import get_api_key_by_hash, update_api_key_last_used, hash_api_key, log_audit
from server.logger import logger


def get_client_ip(request: Request) -> str:
    """Extract real client IP prioritizing trusted X-Real-IP from reverse proxy."""
    real_ip = request.headers.get("X-Real-IP")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Dict[str, Any]:
    """Authenticate via Bearer JWT token, cookie fallback, or X-API-Key header."""
    client_ip = get_client_ip(request)

    # 1. Bearer Token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = verify_token(token)
        if payload:
            return payload

    # 2. Cookie fallback for direct browser downloads
    token_cookie = request.cookies.get("ocr_session_token")
    if token_cookie:
        payload = verify_token(token_cookie)
        if payload:
            return payload

    # 3. Machine-to-Machine API Key
    api_key_candidate = None
    if x_api_key:
        api_key_candidate = x_api_key.strip()
    elif authorization and (authorization.startswith("Api-Key ") or authorization.startswith("ocr_sk_")):
        api_key_candidate = authorization.replace("Api-Key ", "").strip()
    elif authorization and authorization.startswith("Bearer ocr_sk_"):
        api_key_candidate = authorization.split(" ", 1)[1].strip()

    if api_key_candidate:
        key_hash = hash_api_key(api_key_candidate)
        key_record = get_api_key_by_hash(key_hash)
        is_active = key_record and (key_record.get("status") == "active" or key_record.get("is_active") == 1)
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key ไม่ถูกต้อง ถูกระงับ หรือหมดอายุ"
            )

        if key_record.get("expires_at") and key_record["expires_at"] < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key หมดอายุการใช้งานแล้ว กรุณาติดต่อผู้ดูแลระบบ"
            )

        allowed_ips = [ip.strip() for ip in (key_record.get("allowed_ips") or "").split(",") if ip.strip()]
        if allowed_ips and "*" not in allowed_ips:
            ip_matched = (
                client_ip in allowed_ips
                or (client_ip == "127.0.0.1" and "localhost" in allowed_ips)
                or (client_ip == "::1" and "localhost" in allowed_ips)
            )
            if not ip_matched:
                log_audit("API_KEY_IP_BLOCKED", key_record["name"], client_ip, f"Blocked request: Client IP '{client_ip}' not in allowed list")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access Denied: หมายเลข IP เครื่องของคุณ ({client_ip}) ไม่ได้รับอนุญาตให้ใช้ API Key นี้"
                )

        update_api_key_last_used(key_record["id"])
        return {
            "username": f"service:{key_record['name']}",
            "display_name": key_record.get("name"),
            "role": key_record.get("role", "service"),
            "service_id": key_record["id"],
            "auth_type": "api_key",
            "is_api_key": True,
            "key_id": key_record["id"]
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="กรุณาเข้าสู่ระบบ หรือระบุ API Key ที่ถูกต้อง",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Enforce admin privileges."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="จำเป็นต้องมีสิทธิ์ผู้ดูแลระบบ (Admin) เท่านั้น"
        )
    return user
