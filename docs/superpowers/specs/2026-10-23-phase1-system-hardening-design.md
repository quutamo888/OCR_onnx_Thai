# Phase 1: System Hardening & Version Suppression Design Spec

**Date:** 2026-10-23
**Status:** Approved

## 1. Objective
Harden the ThaiOCR ONNX system for production deployment by eliminating version/fingerprint disclosure across all layers (Nginx, FastAPI, Rust Worker), locking down unauthenticated diagnostic endpoints, isolating internal Docker ports, preventing client IP spoofing, and upgrading password hashing to per-user random salts with full backward compatibility.

## 2. Changes by Component

### 2.1 Version & Fingerprint Suppression
- **`nginx/nginx.conf`**:
  - Add `server_tokens off;` in the `http` block so Nginx version numbers are removed from `Server` headers and default error pages.
  - Add `proxy_hide_header X-Powered-By;` and security headers (`Referrer-Policy`, `Permissions-Policy`) at the HTTPS gateway block.
- **`rust_worker/src/main.rs`**:
  - Strip `"service"`, `"engine"`, and `"platform"` fields from `/health` response, returning only `{"status": "healthy"}`.
- **`server/core/config.py` & `server/main.py`**:
  - Set `VERSION: str = ""` (no version number exposed).
  - Omit `version` disclosure in FastAPI initialization when API docs are disabled.
- **`server/routers/system.py`**:
  - Remove `"service"` identifier from `/health` and `/api/health` responses.

### 2.2 Access Control & Network Isolation
- **`server/routers/system.py`**:
  - Require admin authentication (`Depends(require_admin)`) on `GET /api/engine/logs`.
- **`docker-compose.yml`**:
  - Change `garage` (`3900`, `3902`, `3903`) and `redis` (`6379`) from host-published `ports:` to internal `expose:` so only `thai-ocr-gateway` (`8843:443`) is reachable from the host network.
  - Externalize sensitive environment variables (`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`, `APP_SECRET_KEY`) using `${VAR:-default}` syntax.

### 2.3 Client IP Integrity & Password Hashing Hardening
- **`server/core/dependencies.py`**:
  - Update `get_client_ip(request)` to prioritize `X-Real-IP` (set directly by Nginx `$remote_addr`) before falling back to `X-Forwarded-For` or `request.client.host`.
- **`server/routers/ocr.py` & `server/routers/admin.py`**:
  - Use `get_client_ip(request)` consistently for rate limiting and audit logging instead of hardcoded `"127.0.0.1"` or raw `request.client.host`.
- **`server/db.py` & `server/auth.py`**:
  - Update `hash_password(password)` to generate a random 16-byte hex salt per hash (`pbkdf2_sha256$<salt>$<digest>`).
  - Add `verify_password(password, stored_hash)` supporting both the new salted format and legacy static-salt SHA-256 PBKDF2 hashes using constant-time `hmac.compare_digest`.
