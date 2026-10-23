"""Windows Native OCR Engine Worker Service for ThaiOCR ONNX.

Runs natively on Windows Host to execute oneocr.dll / onnxruntime.dll.
Provides REST API for Docker containers or remote callers.
"""

import io
import json
import os
import sys
import time
from pathlib import Path
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import fitz

# Security Configurations
ALLOWED_IPS_RAW = os.getenv("ALLOWED_IPS", "127.0.0.1,::1,localhost")
ALLOWED_IPS = {ip.strip() for ip in ALLOWED_IPS_RAW.split(",") if ip.strip()}
WORKER_SECRET_TOKEN = os.getenv("OCR_WORKER_SECRET_TOKEN", os.getenv("WORKER_SECRET_TOKEN", ""))

# Ensure oneocr and server packages are accessible
REPO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_DIR / "oneocr"))
sys.path.insert(0, str(REPO_DIR))

import oneocr
from pdf_to_md import recognize_with_orientation_check, format_page_markdown
from server.logger import logger, get_recent_engine_logs

app = FastAPI(title="ThaiOCR Windows Worker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_enforcement_middleware(request: Request, call_next):
    """Enforce Level 1 (Permit IP) and Level 2 (Shared Secret Token) on all endpoints."""
    client_ip = request.client.host if request.client else "unknown"

    # 1. Level 1: Permit IP Filtering
    if ALLOWED_IPS and "*" not in ALLOWED_IPS:
        # Check direct IP, localhost aliases, or forwarded header if behind trusted proxy
        is_permitted = (
            client_ip in ALLOWED_IPS
            or (client_ip == "127.0.0.1" and "localhost" in ALLOWED_IPS)
            or (client_ip == "::1" and "localhost" in ALLOWED_IPS)
        )
        if not is_permitted:
            logger.warning(f"[SECURITY ALERT] Blocked unauthorized connection from unpermitted IP: {client_ip} to {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": f"Access Forbidden: IP '{client_ip}' is not permitted to access this worker."}
            )

    # 2. Level 2: Shared Secret Token Verification
    if WORKER_SECRET_TOKEN:
        token = request.headers.get("X-Worker-Token")
        if not token or token != WORKER_SECRET_TOKEN:
            logger.warning(f"[SECURITY ALERT] Invalid or missing X-Worker-Token from IP {client_ip} for {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Access Denied: Invalid or missing X-Worker-Token header."}
            )

    return await call_next(request)

_engine = None


def get_worker_engine() -> oneocr.OcrEngine:
    global _engine
    if _engine is None:
        logger.info("Initializing Windows OneOCR Engine via DLL...")
        t0 = time.time()
        try:
            _engine = oneocr.OcrEngine()
            dt = time.time() - t0
            logger.info(f"OneOCR Engine initialized successfully in {dt:.2f}s (Platform: {sys.platform})")
        except Exception as e:
            logger.error(f"Failed to load OneOCR DLL: {e}", exc_info=True)
            raise
    return _engine


@app.on_event("startup")
def startup_event():
    try:
        get_worker_engine()
        logger.info("ThaiOCR Worker Service started and ready on port 8001.")
    except Exception as e:
        logger.error(f"Worker startup failed: {e}")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ThaiOCR Windows Worker",
        "platform": sys.platform,
        "engine_ready": _engine is not None,
        "timestamp": time.time()
    }


@app.get("/logs")
def get_logs(lines: int = 100):
    return {"logs": get_recent_engine_logs(lines)}


@app.post("/ocr/document")
async def process_document_endpoint(file: UploadFile = File(...), dpi: int = 150):
    filename = file.filename or "uploaded_file"
    file_bytes = await file.read()
    size_kb = len(file_bytes) / 1024

    logger.info(f"Incoming OCR request: '{filename}' ({size_kb:.1f} KB)")
    start_time = time.time()
    engine = get_worker_engine()

    lower_name = filename.lower()
    is_pdf = lower_name.endswith(".pdf")

    try:
        if is_pdf:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            logger.info(f"Processing PDF '{filename}' with {total_pages} pages...")

            md_pages = [f"# {filename}\n\n*ประมวลผลด้วยระบบ ThaiOCR ONNX*\n\n---\n"]
            text_pages = []
            page_summaries = []

            for idx in range(total_pages):
                page = doc[idx]
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                t_page = time.time()
                res, orient_label, angle, rotated = recognize_with_orientation_check(engine, img)
                page_md, has_table, cols = format_page_markdown(res.get("lines", []), idx + 1, orient_label)
                dt_page = time.time() - t_page

                md_pages.append(page_md)
                md_pages.append("\n---\n")

                page_text = res.get("text", "")
                text_pages.append(f"--- หน้า {idx + 1} ---\n{page_text}")
                page_summaries.append({"page": idx + 1, "orientation": orient_label, "has_table": has_table, "cols": cols})

                rot_info = f", rotated {angle:.1f}°" if rotated else ""
                table_info = f", table {cols} cols" if has_table else ""
                logger.info(f"[{idx+1}/{total_pages}] Page {idx+1}: {orient_label}{rot_info}{table_info} in {dt_page:.2f}s")

            doc.close()
            full_text = "\n\n".join(text_pages)
            full_md = "\n".join(md_pages).strip() + "\n"
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(f"Completed PDF '{filename}': {total_pages} pages in {latency_ms/1000:.2f}s ({latency_ms/total_pages:.1f}ms/page)")
            return {
                "page_count": total_pages,
                "text": full_text,
                "markdown": full_md,
                "latency_ms": latency_ms,
                "pages": page_summaries
            }
        else:
            # Single Image
            logger.info(f"Processing image '{filename}'...")
            img = Image.open(io.BytesIO(file_bytes))
            res, orient_label, angle, rotated = recognize_with_orientation_check(engine, img)
            page_md, has_table, cols = format_page_markdown(res.get("lines", []), 1, orient_label)

            full_text = res.get("text", "")
            full_md = f"# {filename}\n\n*ประมวลผลด้วยระบบ ThaiOCR ONNX*\n\n---\n\n{page_md}"
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(f"Completed image '{filename}': 1 page in {latency_ms/1000:.2f}s ({orient_label})")
            return {
                "page_count": 1,
                "text": full_text,
                "markdown": full_md,
                "latency_ms": latency_ms,
                "pages": [{"page": 1, "orientation": orient_label, "has_table": has_table, "cols": cols}]
            }
    except Exception as e:
        logger.error(f"Error processing document '{filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ocr/document/stream")
async def process_document_stream_endpoint(file: UploadFile = File(...), dpi: int = 150):
    filename = file.filename or "uploaded_file"
    file_bytes = await file.read()
    size_kb = len(file_bytes) / 1024

    logger.info(f"Incoming streaming OCR request: '{filename}' ({size_kb:.1f} KB)")

    def event_stream():
        start_time = time.time()
        engine = get_worker_engine()
        lower_name = filename.lower()
        is_pdf = lower_name.endswith(".pdf")

        try:
            if is_pdf:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc)
                logger.info(f"Streaming PDF '{filename}' ({total_pages} pages)...")

                yield json.dumps({
                    "status": "init",
                    "page": 0,
                    "total_pages": total_pages,
                    "percent": 0,
                    "message": f"เตรียมประมวลผล PDF {total_pages} หน้า..."
                }) + "\n"

                md_pages = [f"# {filename}\n\n*ประมวลผลด้วยระบบ ThaiOCR ONNX*\n\n---\n"]
                text_pages = []
                page_summaries = []

                for idx in range(total_pages):
                    page_num = idx + 1
                    page = doc[idx]
                    pix = page.get_pixmap(dpi=dpi)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))

                    t_page = time.time()
                    res, orient_label, angle, rotated = recognize_with_orientation_check(engine, img)
                    page_md, has_table, cols = format_page_markdown(res.get("lines", []), page_num, orient_label)
                    dt_page = time.time() - t_page

                    md_pages.append(page_md)
                    md_pages.append("\n---\n")

                    page_text = res.get("text", "")
                    text_pages.append(f"--- หน้า {page_num} ---\n{page_text}")
                    page_summaries.append({"page": page_num, "orientation": orient_label, "has_table": has_table, "cols": cols})

                    percent = int((page_num / total_pages) * 100)
                    rot_info = f", rotated {angle:.1f}°" if rotated else ""
                    table_info = f", ตาราง {cols} cols" if has_table else ""
                    logger.info(f"Stream [{page_num}/{total_pages}] {orient_label}{rot_info}{table_info} in {dt_page:.2f}s ({percent}%)")

                    yield json.dumps({
                        "status": "progress",
                        "page": page_num,
                        "total_pages": total_pages,
                        "percent": percent,
                        "message": f"หน้า {page_num}/{total_pages}: {orient_label}{table_info} ({dt_page:.2f}s)",
                        "page_summary": {"page": page_num, "orientation": orient_label, "has_table": has_table, "cols": cols}
                    }) + "\n"

                doc.close()
                full_text = "\n\n".join(text_pages)
                full_md = "\n".join(md_pages).strip() + "\n"
                latency_ms = int((time.time() - start_time) * 1000)

                yield json.dumps({
                    "status": "completed",
                    "percent": 100,
                    "result": {
                        "page_count": total_pages,
                        "text": full_text,
                        "markdown": full_md,
                        "latency_ms": latency_ms,
                        "pages": page_summaries
                    }
                }) + "\n"
            else:
                # Single Image
                yield json.dumps({
                    "status": "init",
                    "page": 0,
                    "total_pages": 1,
                    "percent": 15,
                    "message": "กำลังถอดความภาพด้วยระบบ OCR..."
                }) + "\n"

                img = Image.open(io.BytesIO(file_bytes))
                res, orient_label, angle, rotated = recognize_with_orientation_check(engine, img)
                page_md, has_table, cols = format_page_markdown(res.get("lines", []), 1, orient_label)

                full_text = res.get("text", "")
                full_md = f"# {filename}\n\n*ประมวลผลด้วยระบบ ThaiOCR ONNX*\n\n---\n\n{page_md}"
                latency_ms = int((time.time() - start_time) * 1000)

                yield json.dumps({
                    "status": "completed",
                    "percent": 100,
                    "result": {
                        "page_count": 1,
                        "text": full_text,
                        "markdown": full_md,
                        "latency_ms": latency_ms,
                        "pages": [{"page": 1, "orientation": orient_label, "has_table": has_table, "cols": cols}]
                    }
                }) + "\n"
        except Exception as e:
            logger.error(f"Error in stream processing '{filename}': {e}", exc_info=True)
            yield json.dumps({"status": "error", "error": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn
    import ssl

    worker_host = os.getenv("WORKER_HOST", "0.0.0.0")
    worker_port = int(os.getenv("WORKER_PORT", "8001"))
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    ssl_ca_certs = os.getenv("SSL_CA_CERTS")

    ssl_kwargs = {}
    if ssl_keyfile and ssl_certfile and os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
        logger.info(f"Starting Worker with TLS encryption (Cert: {ssl_certfile})")
        ssl_kwargs["ssl_keyfile"] = ssl_keyfile
        ssl_kwargs["ssl_certfile"] = ssl_certfile
        if ssl_ca_certs and os.path.exists(ssl_ca_certs):
            logger.info(f"Enabling mTLS Mutual Authentication with CA: {ssl_ca_certs}")
            ssl_kwargs["ssl_ca_certs"] = ssl_ca_certs
            ssl_kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED

    logger.info(f"Starting ThaiOCR Worker on {worker_host}:{worker_port} (Permitted IPs: {ALLOWED_IPS_RAW})")
    uvicorn.run("ocr_worker:app", host=worker_host, port=worker_port, reload=False, **ssl_kwargs)
