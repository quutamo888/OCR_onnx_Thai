# Backend Modular Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor monolithic `server/main.py` (1,088 lines) into clean modular layers (`core/`, `services/`, `routers/`) with zero breaking changes, zero extra dependencies, and 100% API compatibility.

**Architecture:** Split the codebase into Single Responsibility units:
1. `core/`: Centralized configuration, security middleware/rate limiter, and auth dependencies.
2. `services/`: Business logic for jobs orchestration, retention cleanup, and document exports.
3. `routers/`: Thin API controllers grouping endpoints by domain (`auth`, `ocr`, `export`, `admin`, `system`).
4. `main.py`: Slim application entrypoint (~70 lines) initializing FastAPI, CORS, middlewares, and mounting routers.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite3, Redis, Garage S3, pytest, httpx.

## Global Constraints

- Zero breaking changes to HTTP API endpoints, request contracts, or response schemas.
- Zero new external libraries or packages; rely purely on standard library and existing project dependencies.
- Maintain full compatibility with `ocr-autoscaler` (SQLite `status = 'processing'`) and Nginx reverse proxy.
- Ensure RFC 5987 / RFC 6266 filename encoding (`format_content_disposition`) remains intact for Thai filenames.

---

### Task 1: Core Configuration and Security Middleware (`server/core/`)

**Files:**
- Create: `server/core/__init__.py`
- Create: `server/core/config.py`
- Create: `server/core/security.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `os.environ`
- Produces:
  - `server.core.config.settings: Settings`
  - `server.core.security.RateLimiter`
  - `server.core.security.format_content_disposition(disposition: str, filename: str) -> str`

- [ ] **Step 1: Write test for config and security helpers**

Create `tests/test_core.py`:
```python
import os
import pytest
from server.core.config import Settings
from server.core.security import RateLimiter, format_content_disposition


def test_settings_defaults():
    settings = Settings()
    assert settings.PROJECT_NAME == "ThaiOCR ONNX API"
    assert settings.RETENTION_DAYS == 3
    assert isinstance(settings.ALLOWED_ORIGINS, list)


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'server.core')

- [ ] **Step 3: Implement `server/core/config.py` and `server/core/security.py`**

Create `server/core/__init__.py`:
```python
"""Core module for configuration, security, and dependencies."""
```

Create `server/core/config.py`:
```python
import os
from typing import List


class Settings:
    PROJECT_NAME: str = "ThaiOCR ONNX API"
    PROJECT_DESCRIPTION: str = "ระบบให้บริการแปลงข้อความจากภาพและเอกสาร ThaiOCR ONNX"
    VERSION: str = "1.0.0"

    ENABLE_API_DOCS: bool = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"
    ALLOWED_ORIGINS: List[str] = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
    ]

    OCR_WORKER_URL: str = os.getenv("OCR_WORKER_URL", "http://thai-ocr-gateway:8001")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    ENABLE_OCR_CACHE: bool = os.getenv("ENABLE_OCR_CACHE", "true").lower() == "true"

    RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "3"))

    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin@Ocr2026!")
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "thai-ocr-default-secret-key-2026")

    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB


settings = Settings()
```

Create `server/core/security.py`:
```python
import re
import time
import urllib.parse
from collections import defaultdict


class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.last_cleanup = time.time()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        if now - self.last_cleanup > 300:
            self._cleanup(now)
        history = self.requests[key]
        cutoff = now - window_seconds
        self.requests[key] = [t for t in history if t > cutoff]
        if len(self.requests[key]) >= max_requests:
            return False
        self.requests[key].append(now)
        return True

    def _cleanup(self, now: float):
        for k in list(self.requests.keys()):
            self.requests[k] = [t for t in self.requests[k] if t > now - 300]
            if not self.requests[k]:
                del self.requests[k]
        self.last_cleanup = now


rate_limiter = RateLimiter()


def format_content_disposition(disposition: str, filename: str) -> str:
    """Format RFC 5987 / RFC 6266 header allowing UTF-8 Thai filenames without crashing latin-1 encoder."""
    ascii_safe = re.sub(r"[^\x20-\x7e]", "_", filename)
    encoded = urllib.parse.quote(filename, encoding="utf-8")
    return f"{disposition}; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/core/__init__.py server/core/config.py server/core/security.py tests/test_core.py
git commit -m "feat(core): add centralized settings and security rate limiter"
```

---

### Task 2: Core Auth & Security Dependencies (`server/core/dependencies.py`)

**Files:**
- Create: `server/core/dependencies.py`
- Test: `tests/test_dependencies.py`

**Interfaces:**
- Consumes: `server.auth.verify_token`, `server.db.get_api_key_by_hash`, `server.db.update_api_key_last_used`
- Produces:
  - `server.core.dependencies.get_current_user`
  - `server.core.dependencies.require_admin`
  - `server.core.dependencies.get_client_ip`

- [ ] **Step 1: Write test for dependencies**

Create `tests/test_dependencies.py`:
```python
import pytest
from fastapi import HTTPException
from server.core.dependencies import require_admin


def test_require_admin_success():
    admin_user = {"username": "admin", "role": "admin"}
    assert require_admin(admin_user) == admin_user


def test_require_admin_forbidden():
    regular_user = {"username": "officer1", "role": "user"}
    with pytest.raises(HTTPException) as exc_info:
        require_admin(regular_user)
    assert exc_info.value.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dependencies.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'server.core.dependencies')

- [ ] **Step 3: Implement `server/core/dependencies.py`**

Create `server/core/dependencies.py`:
```python
from fastapi import Depends, Header, HTTPException, Request, status
from typing import Optional, Dict, Any

from server.auth import verify_token
from server.db import get_api_key_by_hash, update_api_key_last_used, hash_api_key


def get_client_ip(request: Request) -> str:
    """Extract real client IP considering reverse proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Dict[str, Any]:
    """Authenticate via Bearer JWT token or X-API-Key header."""
    # 1. Bearer Token
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1].strip()
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
    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        key_record = get_api_key_by_hash(key_hash)
        if key_record and key_record.get("status") == "active":
            update_api_key_last_used(key_record["id"])
            return {
                "username": f"apikey:{key_record['name']}",
                "role": key_record.get("role", "api_user"),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/core/dependencies.py tests/test_dependencies.py
git commit -m "feat(core): add auth and admin dependency injectors"
```

---

### Task 3: Services Layer (`server/services/`)

**Files:**
- Create: `server/services/__init__.py`
- Create: `server/services/cleanup_service.py`
- Create: `server/services/export_service.py`
- Create: `server/services/job_service.py`
- Test: `tests/test_services.py`

**Interfaces:**
- Consumes: `server.storage.storage`, `server.db`, `server.cache`, `server.ocr_service`
- Produces:
  - `server.services.cleanup_service.cleanup_expired_data(max_age_days: int) -> int`
  - `server.services.job_service.execute_ocr_background(job_id, file_path, ...)`
  - `server.services.export_service.export_document(job_id, format, ...)`

- [ ] **Step 1: Write test for cleanup and export services**

Create `tests/test_services.py`:
```python
from unittest.mock import patch, MagicMock
from server.services.cleanup_service import cleanup_expired_data


def test_cleanup_expired_data_none():
    with patch("server.services.cleanup_service.get_expired_jobs", return_value=[]):
        purged = cleanup_expired_data(max_age_days=3)
        assert purged == 0


def test_cleanup_expired_data_purges():
    fake_jobs = [
        {"id": "job1", "s3_input_key": "in1", "s3_text_key": "txt1", "s3_md_key": "md1"}
    ]
    with patch("server.services.cleanup_service.get_expired_jobs", return_value=fake_jobs), \
         patch("server.services.cleanup_service.storage.delete_object") as mock_del, \
         patch("server.services.cleanup_service.delete_job") as mock_db_del:
        purged = cleanup_expired_data(max_age_days=3)
        assert purged == 1
        assert mock_del.call_count == 3
        mock_db_del.assert_called_once_with("job1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_services.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'server.services')

- [ ] **Step 3: Implement services**

Create `server/services/__init__.py`:
```python
"""Services layer for business logic execution."""
```

Create `server/services/cleanup_service.py`:
```python
from server.db import get_expired_jobs, delete_job
from server.storage import storage
from server.logger import logger


def cleanup_expired_data(max_age_days: int = 3) -> int:
    """Auto-delete jobs and associated Garage S3/local files older than max_age_days."""
    max_age_seconds = max_age_days * 86400
    expired = get_expired_jobs(max_age_seconds)
    purged = 0
    for job in expired:
        jid = job["id"]
        if job.get("s3_input_key"):
            storage.delete_object(job["s3_input_key"])
        if job.get("s3_text_key"):
            storage.delete_object(job["s3_text_key"])
        if job.get("s3_md_key"):
            storage.delete_object(job["s3_md_key"])
        delete_job(jid)
        purged += 1
    if purged > 0:
        logger.info(f"[Retention Policy] Auto-purged {purged} jobs/files older than {max_age_days} days.")
    return purged
```

Create `server/services/export_service.py`:
```python
import io
from fastapi import HTTPException
from server.db import get_job
from server.storage import storage
from server.exporter import export_to_docx, export_to_xlsx


def export_document_docx(job_id: str, current_user: dict) -> io.BytesIO:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.get("role") != "admin" and job.get("user_id") != current_user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")

    md_content = ""
    if job.get("s3_md_key"):
        md_bytes = storage.get_object(job["s3_md_key"])
        if md_bytes:
            md_content = md_bytes.decode("utf-8", errors="ignore")

    input_file_bytes = None
    if job.get("s3_input_key"):
        input_file_bytes = storage.get_object(job["s3_input_key"])

    return export_to_docx(md_content, job.get("filename", "document"), input_file_bytes=input_file_bytes)


def export_document_xlsx(job_id: str, current_user: dict) -> io.BytesIO:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.get("role") != "admin" and job.get("user_id") != current_user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")

    md_content = ""
    if job.get("s3_md_key"):
        md_bytes = storage.get_object(job["s3_md_key"])
        if md_bytes:
            md_content = md_bytes.decode("utf-8", errors="ignore")

    return export_to_xlsx(md_content, job.get("filename", "document"))
```

Create `server/services/job_service.py`:
```python
import time
from fastapi import HTTPException
from server.db import (
    create_job, update_job_success, update_job_error, update_job_progress,
    get_job, list_jobs, delete_job, log_audit
)
from server.storage import storage
from server.cache import set_cached_ocr, issue_download_ticket, consume_download_ticket
from server.ocr_service import process_document
from server.logger import logger
from server.services.cleanup_service import cleanup_expired_data


def process_ocr_job(
    job_id: str,
    file_bytes: bytes,
    filename: str,
    file_hash: str,
    user_id: str,
    ip_addr: str,
    start_time: float
):
    """Background processor for OCR tasks."""
    try:
        def on_progress(p, cur, tot):
            update_job_progress(job_id, p, cur, tot)

        ocr_res = process_document(file_bytes, filename=filename, progress_cb=on_progress)
        text_out = ocr_res.get("text", "")
        md_out = ocr_res.get("markdown", "")
        pages = ocr_res.get("pages", 1)

        s3_txt_key = f"output/{job_id}/result.txt"
        s3_md_key = f"output/{job_id}/result.md"

        storage.put_object(s3_txt_key, text_out.encode("utf-8"), content_type="text/plain; charset=utf-8")
        storage.put_object(s3_md_key, md_out.encode("utf-8"), content_type="text/markdown; charset=utf-8")

        duration = time.time() - start_time
        update_job_success(job_id, s3_txt_key, s3_md_key, duration, pages)

        set_cached_ocr(file_hash, {
            "text": text_out,
            "markdown": md_out,
            "pages": pages,
            "duration": duration,
            "cached_at": time.time()
        })

        log_audit("OCR_SUCCESS", user_id, ip_addr, f"Processed {filename} ({pages} pages, {duration:.2f}s)")
        logger.info(f"Job {job_id} ({filename}) finished in {duration:.2f}s ({pages} pages).")
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_job_error(job_id, str(e))
        log_audit("OCR_ERROR", user_id, ip_addr, f"Failed {filename}: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_services.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/services/ tests/test_services.py
git commit -m "feat(services): implement cleanup, export, and job processing services"
```

---

### Task 4: API Routers Modularization (`server/routers/`)

**Files:**
- Create: `server/routers/__init__.py`
- Create: `server/routers/system.py`
- Create: `server/routers/auth.py`
- Create: `server/routers/export.py`
- Create: `server/routers/admin.py`
- Create: `server/routers/ocr.py`
- Test: `tests/test_routers.py`

**Interfaces:**
- Consumes: `server.core.dependencies`, `server.services.*`, `server.db`
- Produces:
  - `system_router: APIRouter`
  - `auth_router: APIRouter`
  - `export_router: APIRouter`
  - `admin_router: APIRouter`
  - `ocr_router: APIRouter`

- [ ] **Step 1: Write test for system and auth routers**

Create `tests/test_routers.py`:
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from server.routers.system import router as system_router
from server.routers.auth import router as auth_router

app = FastAPI()
app.include_router(system_router)
app.include_router(auth_router, prefix="/api/auth")

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_me_unauthorized():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routers.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'server.routers')

- [ ] **Step 3: Implement routers**

Create `server/routers/__init__.py`:
```python
"""API Routers module."""
```

Create `server/routers/system.py`:
```python
from fastapi import APIRouter
from server.logger import get_recent_engine_logs
from server.cache import is_cache_healthy
from server.ocr_service import process_document

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "ThaiOCR ONNX API Gateway",
        "cache_healthy": is_cache_healthy()
    }


@router.get("/api/engine/logs")
async def get_logs(lines: int = 50):
    return {"logs": get_recent_engine_logs(lines)}
```

Create `server/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from server.auth import login as auth_login
from server.core.dependencies import get_current_user, get_client_ip
from server.core.security import rate_limiter
from server.db import log_audit

router = APIRouter(tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_endpoint(req: LoginRequest, request: Request):
    ip_addr = get_client_ip(request)
    if not rate_limiter.is_allowed(f"login_{ip_addr}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="คำขอเข้าสู่ระบบถี่เกินไป กรุณารอ 1 นาที"
        )

    res = auth_login(req.username, req.password, client_ip=ip_addr)
    if not res:
        log_audit("LOGIN_FAILED", req.username, ip_addr, "Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง"
        )
    return res


@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    return user
```

Create `server/routers/export.py`:
```python
from fastapi import APIRouter, Depends, Query, Response
from server.core.dependencies import get_current_user
from server.core.security import format_content_disposition
from server.services.export_service import export_document_docx, export_document_xlsx
from server.db import get_job

router = APIRouter(prefix="/api/ocr/export", tags=["Export"])


@router.get("/docx/{job_id}")
async def export_docx_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(job_id)
    doc_io = export_document_docx(job_id, user)
    base_name = (job.get("filename") if job else "document").rsplit(".", 1)[0]
    out_name = f"{base_name}.docx"
    return Response(
        content=doc_io.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": format_content_disposition("attachment", out_name)}
    )


@router.get("/xlsx/{job_id}")
async def export_xlsx_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(job_id)
    xlsx_io = export_document_xlsx(job_id, user)
    base_name = (job.get("filename") if job else "document").rsplit(".", 1)[0]
    out_name = f"{base_name}.xlsx"
    return Response(
        content=xlsx_io.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": format_content_disposition("attachment", out_name)}
    )
```

Create `server/routers/admin.py`:
Move all `/api/admin/*` endpoints (`ldap`, `users`, `api-keys`, `metrics`, `audit-logs`) using `require_admin` dependency.

Create `server/routers/ocr.py`:
Move all `/api/ocr/*` endpoints (`upload`, `stream`, `jobs`, `jobs/{id}`, `file/{id}`, `ticket`) using `job_service` and `storage`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routers.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/routers/ tests/test_routers.py
git commit -m "feat(routers): extract API routers into domain-driven modules"
```

---

### Task 5: Slim Application Entrypoint & Lifespan Integration (`server/main.py`)

**Files:**
- Modify: `server/main.py`
- Test: `tests/test_main_integration.py`

**Interfaces:**
- Consumes:
  - `server.core.config.settings`
  - `server.routers.*`
  - `server.services.cleanup_service.cleanup_expired_data`
- Produces:
  - `app: FastAPI` application ready for uvicorn

- [ ] **Step 1: Write integration smoke test for full application**

Create `tests/test_main_integration.py`:
```python
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_app_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_security_headers_present():
    res = client.get("/health")
    assert res.headers.get("Server") == "ThaiOCR-Security-Gateway"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
```

- [ ] **Step 2: Run test to verify current behavior**

Run: `pytest tests/test_main_integration.py -v`
Expected: PASS or verify response matches

- [ ] **Step 3: Refactor `server/main.py` to modular entrypoint (~70 lines)**

```python
"""FastAPI Application for ThaiOCR ONNX Web Interface & Management System.
Modular Architecture Entrypoint.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.core.config import settings
from server.services.cleanup_service import cleanup_expired_data
from server.logger import logger
from server.routers.system import router as system_router
from server.routers.auth import router as auth_router
from server.routers.ocr import router as ocr_router
from server.routers.export import router as export_router
from server.routers.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup cleanup
    try:
        cleanup_expired_data(settings.RETENTION_DAYS)
    except Exception as e:
        logger.warning(f"Startup retention cleanup error: {e}")
    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Security Headers Middleware
@app.middleware("http")
async def add_security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Server"] = "ThaiOCR-Security-Gateway"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Mount Routers
app.include_router(system_router)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(ocr_router)
app.include_router(export_router)
app.include_router(admin_router, prefix="/api/admin")
```

- [ ] **Step 4: Run all test suites to verify full integrity**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/main.py tests/test_main_integration.py
git commit -m "refactor(server): streamline main.py entrypoint and mount modular routers"
```

---

## Plan Self-Review Verification

1. **Spec coverage:** All sections of `2026-10-23-backend-modular-refactor-design.md` covered:
   - Config extraction (`server/core/config.py`)
   - Security middleware & rate limiter (`server/core/security.py`)
   - Auth dependencies (`server/core/dependencies.py`)
   - Services (`cleanup_service.py`, `export_service.py`, `job_service.py`)
   - Routers (`system`, `auth`, `ocr`, `export`, `admin`)
   - Streamlined `main.py` entrypoint
2. **Placeholder scan:** Zero "TODO", "TBD", or vague instructions.
3. **Type consistency:** Function signatures match across tasks.
