import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.core.config import settings
from server.core.dependencies import get_current_user, get_client_ip
from server.core.security import format_content_disposition, rate_limiter
from server.db import (
    create_job, get_job, list_jobs, delete_job, log_audit,
    update_job_success, update_job_error, update_job_progress
)
from server.storage import storage
from server.security import validate_file_safety
from server.ocr_service import process_document_stream
from server.logger import logger
from server.exporter import export_to_docx, export_to_xlsx
from server.cache import (
    compute_file_hash, get_cached_ocr, set_cached_ocr,
    issue_download_ticket, consume_download_ticket
)
from server.services.cleanup_service import cleanup_expired_data

router = APIRouter(tags=["OCR"])

# --- Resilient Job Event Pub/Sub Manager ---
job_listeners: Dict[str, List[queue.Queue]] = {}
job_listeners_lock = threading.Lock()


def add_job_listener(job_id: str) -> queue.Queue:
    q = queue.Queue(maxsize=200)
    with job_listeners_lock:
        job_listeners.setdefault(job_id, []).append(q)
    return q


def remove_job_listener(job_id: str, q: queue.Queue):
    with job_listeners_lock:
        if job_id in job_listeners:
            if q in job_listeners[job_id]:
                job_listeners[job_id].remove(q)
            if not job_listeners[job_id]:
                del job_listeners[job_id]


def broadcast_job_event(job_id: str, event: Optional[dict]):
    with job_listeners_lock:
        queues = list(job_listeners.get(job_id, []))
    for q in queues:
        try:
            q.put_nowait(event)
        except Exception:
            pass


def execute_job_fully(job_id: str, file_bytes: bytes, clean_filename: str, s3_text_key: str, s3_md_key: str):
    """Run full OCR pipeline detached in background with instant Redis OCR Cache lookup."""
    logger.info(f"Starting detached OCR pipeline for job {job_id} ('{clean_filename}')...")
    try:
        # 1. High-Speed OCR Cache Check
        file_hash = compute_file_hash(file_bytes)
        cached_result = get_cached_ocr(file_hash)

        if cached_result:
            latency_ms = 45
            logger.info(f"⚡ [OCR Cache Instant Hit] Returning pre-computed OCR for '{clean_filename}' in {latency_ms}ms")

            storage.put_object(s3_text_key, cached_result["text"].encode("utf-8"), content_type="text/plain; charset=utf-8")
            storage.put_object(s3_md_key, cached_result["markdown"].encode("utf-8"), content_type="text/markdown; charset=utf-8")

            update_job_success(
                job_id=job_id,
                page_count=cached_result["page_count"],
                latency_ms=latency_ms,
                s3_text_key=s3_text_key,
                s3_md_key=s3_md_key
            )

            cache_event = {
                "status": "completed",
                "percent": 100,
                "job_id": job_id,
                "cached": True,
                "result": {
                    "job_id": job_id,
                    "filename": clean_filename,
                    "page_count": cached_result["page_count"],
                    "latency_ms": latency_ms,
                    "cached": True,
                    "text": cached_result["text"],
                    "markdown": cached_result["markdown"],
                    "pages": cached_result.get("pages", [])
                }
            }
            broadcast_job_event(job_id, cache_event)
            return

        # 2. Cache Miss: Run OCR Worker Stream
        for event in process_document_stream(file_bytes, clean_filename):
            evt_status = event.get("status")
            event["job_id"] = job_id

            if evt_status == "progress":
                pct = event.get("percent", 0)
                update_job_progress(job_id, pct)
            elif evt_status == "completed":
                result = event.get("result", {})
                event["result"]["job_id"] = job_id
                event["result"]["filename"] = clean_filename

                storage.put_object(s3_text_key, result["text"].encode("utf-8"), content_type="text/plain; charset=utf-8")
                storage.put_object(s3_md_key, result["markdown"].encode("utf-8"), content_type="text/markdown; charset=utf-8")

                update_job_success(
                    job_id=job_id,
                    page_count=result["page_count"],
                    latency_ms=result["latency_ms"],
                    s3_text_key=s3_text_key,
                    s3_md_key=s3_md_key
                )

                set_cached_ocr(file_hash, result)

            elif evt_status == "error":
                update_job_error(job_id, event.get("error", "Unknown error"))

            broadcast_job_event(job_id, event)

    except Exception as e:
        logger.error(f"Job {job_id} encountered background error: {e}")
        update_job_error(job_id, str(e))
        broadcast_job_event(job_id, {"status": "error", "job_id": job_id, "error": str(e)})
    finally:
        broadcast_job_event(job_id, None)


# --- Request Schemas ---

class UpdateMarkdownRequest(BaseModel):
    markdown: str


class DownloadTicketRequest(BaseModel):
    job_id: str
    format: str = "docx"


class TermsResponseRequest(BaseModel):
    action: str
    filenames: List[str] = []


async def authenticate_download_request(
    request: Request,
    job_id: str,
    format: str,
    ticket: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> dict:
    if ticket:
        claim = consume_download_ticket(ticket, job_id, format)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="ตั๋วดาวน์โหลดไม่ถูกต้อง หมดอายุ (60 วิ) หรือถูกใช้งานไปแล้ว"
            )
        return {"username": claim["user_id"], "role": claim.get("role", "user")}

    return await get_current_user(request=request, authorization=authorization, x_api_key=x_api_key)


# --- Endpoints ---

@router.post("/upload")
async def upload_ocr_file(
    request: Request,
    file: UploadFile = File(...),
    stream: bool = False,
    user: dict = Depends(get_current_user)
):
    ip = get_client_ip(request)

    if not rate_limiter.is_allowed(f"upload:{ip}", max_requests=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="มีคำขอประมวลผลเอกสารเกินขีดจำกัดความปลอดภัย (30 ครั้ง/นาที) กรุณารอสักครู่"
        )

    cl = request.headers.get("content-length")
    if cl and int(cl) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="ขนาดไฟล์เกินขีดจำกัดความปลอดภัย 50MB"
        )

    raw_filename = file.filename or "uploaded_file"
    file_bytes = await file.read()

    clean_filename, ext = validate_file_safety(raw_filename, file_bytes)
    size_bytes = len(file_bytes)

    job_id = uuid.uuid4().hex[:12]
    s3_input_key = f"inputs/{job_id}/{clean_filename}"
    s3_text_key = f"outputs/{job_id}/result.txt"
    s3_md_key = f"outputs/{job_id}/result.md"

    storage.put_object(s3_input_key, file_bytes, content_type=file.content_type or "application/octet-stream")

    create_job(
        job_id=job_id,
        filename=clean_filename,
        file_type=ext.lstrip("."),
        size_bytes=size_bytes,
        user_id=user["username"],
        user_name=user.get("display_name", user["username"]),
        s3_input_key=s3_input_key
    )

    t = threading.Thread(
        target=execute_job_fully,
        args=(job_id, file_bytes, clean_filename, s3_text_key, s3_md_key),
        daemon=True
    )
    t.start()

    if stream:
        def stream_generator():
            import json
            q = add_job_listener(job_id)
            try:
                while True:
                    try:
                        event = q.get(timeout=25)
                        if event is None:
                            break
                        yield f"data: {json.dumps(event)}\n\n"
                        if event.get("status") in ("completed", "error"):
                            break
                    except queue.Empty:
                        yield ": keep-alive\n\n"
            finally:
                remove_job_listener(job_id, q)

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    return {
        "job_id": job_id,
        "filename": clean_filename,
        "status": "processing"
    }


@router.get("/jobs")
async def get_user_jobs(user: dict = Depends(get_current_user)):
    cleanup_expired_data(settings.RETENTION_DAYS)
    user_id = None if user.get("role") == "admin" else user["username"]
    jobs = list_jobs(limit=50, user_id=user_id)
    for j in jobs:
        j["retention_days"] = settings.RETENTION_DAYS
        j["expires_at"] = j["created_at"] + (settings.RETENTION_DAYS * 86400)
    return jobs


@router.delete("/jobs/{job_id}")
async def delete_job_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ลบเอกสารนี้")

    if job.get("s3_input_key"):
        storage.delete_object(job["s3_input_key"])
    if job.get("s3_text_key"):
        storage.delete_object(job["s3_text_key"])
    if job.get("s3_md_key"):
        storage.delete_object(job["s3_md_key"])

    delete_job(job_id)
    log_audit("DELETE_JOB", user["username"], "127.0.0.1", f"User {user['username']} deleted job {job_id} and storage files")
    logger.info(f"User '{user['username']}' deleted job '{job_id}' and files from storage.")

    return {
        "status": "success",
        "message": "ลบไฟล์ต้นฉบับและผลลัพธ์ออกจากระบบเรียบร้อยแล้ว",
        "job_id": job_id
    }


@router.get("/jobs/{job_id}")
async def get_job_detail(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")

    text_bytes = storage.get_object(job["s3_text_key"]) if job.get("s3_text_key") else None
    md_bytes = storage.get_object(job["s3_md_key"]) if job.get("s3_md_key") else None

    return {
        **job,
        "text": text_bytes.decode("utf-8", errors="ignore") if text_bytes else "",
        "markdown": md_bytes.decode("utf-8", errors="ignore") if md_bytes else ""
    }


@router.get("/file/{job_id}")
async def get_source_file(
    request: Request,
    job_id: str,
    ticket: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    user = await authenticate_download_request(
        request=request,
        job_id=job_id,
        format="source",
        ticket=ticket,
        authorization=authorization,
        x_api_key=x_api_key
    )
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")

    key = job.get("s3_input_key")
    if not key:
        raise HTTPException(status_code=404, detail="Source file not found")

    data = storage.get_object(key)
    if not data:
        raise HTTPException(status_code=404, detail="File data not found in storage")

    ext = job.get("file_type", "").lower()
    content_types = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "bmp": "image/bmp",
        "webp": "image/webp",
    }
    media_type = content_types.get(ext, "application/octet-stream")

    csp = (
        "default-src 'self' 'unsafe-inline'; object-src 'self' blob:; frame-src 'self' blob:;"
        if ext == "pdf"
        else "default-src 'none'; style-src 'unsafe-inline';"
    )

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": format_content_disposition("inline", job["filename"]),
            "Content-Security-Policy": csp,
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.put("/jobs/{job_id}/markdown")
async def update_job_markdown(
    job_id: str,
    req: UpdateMarkdownRequest,
    user: dict = Depends(get_current_user)
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์แก้ไขเอกสารนี้")

    md_content = req.markdown
    if len(md_content.encode("utf-8")) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ขนาดข้อความ Markdown เกินขีดจำกัด (10MB)")

    s3_md_key = job.get("s3_md_key")
    if not s3_md_key:
        s3_md_key = f"outputs/{job_id}/result.md"

    storage.put_object(s3_md_key, md_content.encode("utf-8"), content_type="text/markdown; charset=utf-8")
    log_audit("EDIT_MARKDOWN", user["username"], "127.0.0.1", f"User {user['username']} edited markdown for job {job_id}")

    return {
        "status": "success",
        "job_id": job_id,
        "markdown": md_content,
        "message": "บันทึกการแก้ไข Markdown เรียบร้อยแล้ว"
    }


@router.post("/tickets/download")
async def create_download_ticket(
    req: DownloadTicketRequest,
    user: dict = Depends(get_current_user)
):
    """Issue a single-use, 60-second One-Time Ticket for downloading or viewing a document."""
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")

    ticket = issue_download_ticket(
        job_id=req.job_id,
        format=req.format,
        user_id=user["username"],
        role=user.get("role", "user")
    )

    return {
        "status": "success",
        "ticket": ticket,
        "expires_in": 60,
        "job_id": req.job_id,
        "format": req.format
    }


@router.get("/download/{job_id}/{format}")
async def download_result(
    request: Request,
    job_id: str,
    format: str,
    ticket: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    user = await authenticate_download_request(
        request=request,
        job_id=job_id,
        format=format,
        ticket=ticket,
        authorization=authorization,
        x_api_key=x_api_key
    )
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")

    fmt = format.lower()
    base_name = Path(job["filename"]).stem

    if fmt == "txt":
        key = job.get("s3_text_key")
        if not key:
            raise HTTPException(status_code=404, detail="Result text not found")
        data = storage.get_object(key)
        filename = f"{base_name}_ocr.txt"
        media_type = "text/plain; charset=utf-8"

    elif fmt == "md":
        key = job.get("s3_md_key")
        if not key:
            raise HTTPException(status_code=404, detail="Result markdown not found")
        data = storage.get_object(key)
        filename = f"{base_name}_ocr.md"
        media_type = "text/markdown; charset=utf-8"

    elif fmt == "docx":
        md_key = job.get("s3_md_key")
        if not md_key:
            raise HTTPException(status_code=404, detail="Markdown data not found")
        md_bytes = storage.get_object(md_key)
        if not md_bytes:
            raise HTTPException(status_code=404, detail="Markdown data not found in storage")
        md_text = md_bytes.decode("utf-8", errors="ignore")

        source_bytes = None
        if job.get("s3_input_key"):
            source_bytes = storage.get_object(job["s3_input_key"])

        data = export_to_docx(source_bytes, job["filename"], md_text)
        filename = f"{base_name}_ocr.docx"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    elif fmt == "xlsx":
        md_key = job.get("s3_md_key")
        if not md_key:
            raise HTTPException(status_code=404, detail="Markdown data not found")
        md_bytes = storage.get_object(md_key)
        if not md_bytes:
            raise HTTPException(status_code=404, detail="Markdown data not found in storage")
        md_text = md_bytes.decode("utf-8", errors="ignore")

        source_bytes = None
        if job.get("s3_input_key"):
            source_bytes = storage.get_object(job["s3_input_key"])

        data = export_to_xlsx(source_bytes, job["filename"], md_text)
        filename = f"{base_name}_ocr.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported: txt, md, docx, xlsx")

    if not data:
        raise HTTPException(status_code=404, detail="File data could not be generated")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": format_content_disposition("attachment", filename)}
    )


@router.post("/terms-response")
async def record_terms_response(
    request: Request,
    req: TermsResponseRequest,
    user: dict = Depends(get_current_user)
):
    ip = get_client_ip(request)
    evt = "TERMS_ACCEPTED" if req.action == "accept" else "TERMS_DECLINED"
    action_th = "ยอมรับข้อตกลงและคำชี้แจง OCR" if req.action == "accept" else "ปฏิเสธ/ไม่ใช้งาน"
    file_list_str = ", ".join(req.filenames) if req.filenames else "ไม่ระบุไฟล์"
    detail = f"ผู้ใช้ {user.get('display_name', user['username'])} ({user['username']}) ได้ {action_th} สำหรับไฟล์: {file_list_str}"
    log_audit(evt, user["username"], ip, detail)
    return {"status": "ok", "action": req.action}
