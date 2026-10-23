"""OCR Pipeline Service for Image & PDF processing using Windows OneOCR.

Supports:
1. Native Windows execution (calls oneocr.dll directly)
2. Linux Container Bridge execution (forwards to Windows Worker via OCR_WORKER_URL)
"""

import io
import os
import sys
import time
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF

try:
    import requests
except ImportError:
    requests = None

from server.logger import logger

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "oneocr"))
sys.path.insert(0, str(REPO_DIR))

# Worker URL when running inside Docker container
OCR_WORKER_URL = os.getenv("OCR_WORKER_URL", "http://host.docker.internal:8001")
OCR_WORKER_SECRET_TOKEN = os.getenv("OCR_WORKER_SECRET_TOKEN", os.getenv("WORKER_SECRET_TOKEN", ""))
WORKER_CA_CERT = os.getenv("WORKER_CA_CERT")
WORKER_CLIENT_CERT = os.getenv("WORKER_CLIENT_CERT")
WORKER_CLIENT_KEY = os.getenv("WORKER_CLIENT_KEY")


def _get_worker_request_kwargs() -> dict:
    """Prepare security headers and mTLS certificates for Worker communication."""
    kwargs = {}
    headers = {}
    if OCR_WORKER_SECRET_TOKEN:
        headers["X-Worker-Token"] = OCR_WORKER_SECRET_TOKEN
    if headers:
        kwargs["headers"] = headers

    if WORKER_CLIENT_CERT and WORKER_CLIENT_KEY and os.path.exists(WORKER_CLIENT_CERT) and os.path.exists(WORKER_CLIENT_KEY):
        kwargs["cert"] = (WORKER_CLIENT_CERT, WORKER_CLIENT_KEY)
    if WORKER_CA_CERT and os.path.exists(WORKER_CA_CERT):
        kwargs["verify"] = WORKER_CA_CERT
    elif os.getenv("WORKER_INSECURE_SKIP_VERIFY", "false").lower() == "true":
        kwargs["verify"] = False
    return kwargs


_engine = None


def get_engine():
    global _engine
    if sys.platform != "win32":
        return None  # Will use OCR_WORKER_URL bridge
    if _engine is None:
        import oneocr
        logger.info("Initializing Windows Native OneOCR Engine...")
        _engine = oneocr.OcrEngine()
        logger.info("Windows Native OneOCR Engine ready.")
    return _engine


def process_via_worker(file_bytes: bytes, filename: str, dpi: int = 150) -> dict:
    """Forward OCR request to Windows Worker Service (running on host)."""
    worker_endpoint = f"{OCR_WORKER_URL.rstrip('/')}/ocr/document"
    logger.info(f"Forwarding document '{filename}' to Windows OCR Worker at {worker_endpoint}...")
    try:
        files = {"file": (filename, file_bytes)}
        data = {"dpi": dpi}
        resp = requests.post(worker_endpoint, files=files, data=data, timeout=300, **_get_worker_request_kwargs())
        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_msg = resp.json().get("detail", err_msg)
            except Exception:
                pass
            logger.error(f"Worker returned error {resp.status_code}: {err_msg}")
            raise RuntimeError(f"OCR Worker Error: {err_msg}")
        return resp.json()
    except requests.exceptions.ConnectionError:
        err_msg = (
            f"ไม่สามารถเชื่อมต่อ Windows OneOCR Worker ได้ที่ {worker_endpoint}\n"
            f"เนื่องจาก oneocr.dll รันบน Windows Native เท่านั้น กรุณาสตาร์ท Worker บนเครื่อง Windows ด้วยคำสั่ง: python ocr_worker.py"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)


def process_via_worker_stream(file_bytes: bytes, filename: str, dpi: int = 150):
    """Forward streaming OCR request to Windows Worker Service."""
    worker_endpoint = f"{OCR_WORKER_URL.rstrip('/')}/ocr/document/stream"
    logger.info(f"Forwarding document '{filename}' to Windows OCR Worker stream at {worker_endpoint}...")
    try:
        import json
        files = {"file": (filename, file_bytes)}
        data = {"dpi": dpi}
        resp = requests.post(worker_endpoint, files=files, data=data, timeout=600, stream=True, **_get_worker_request_kwargs())
        if resp.status_code != 200:
            err_msg = resp.text
            logger.error(f"Worker stream returned error {resp.status_code}: {err_msg}")
            yield {"status": "error", "error": f"OCR Worker Error: {err_msg}"}
            return

        for line in resp.iter_lines():
            if line:
                try:
                    payload = json.loads(line.decode("utf-8"))
                    yield payload
                except Exception as ex:
                    logger.warning(f"Failed to parse worker stream line: {ex}")
    except requests.exceptions.ConnectionError:
        err_msg = (
            f"ไม่สามารถเชื่อมต่อ Windows OneOCR Worker ได้ที่ {worker_endpoint}\n"
            f"กรุณาสตาร์ท Worker บนเครื่อง Windows: python ocr_worker.py"
        )
        logger.error(err_msg)
        yield {"status": "error", "error": err_msg}
    except Exception as e:
        err_msg = f"ข้อผิดพลาดการเชื่อมต่อ Worker: {str(e)}"
        logger.error(err_msg)
        yield {"status": "error", "error": err_msg}


def process_document_stream(file_bytes: bytes, filename: str, dpi: int = 200):
    """Process PDF or Image and yield live progress % and page status events.

    Supports:
    1. High-Performance Rust OCR Worker (ort-onnx in Docker)
    2. Legacy Windows Worker stream
    3. Native Windows oneocr.dll local fallback
    """
    from pdf_to_md import recognize_with_orientation_check, format_page_markdown

    start_time = time.time()
    lower_name = filename.lower()
    is_pdf = lower_name.endswith(".pdf")
    worker_url = OCR_WORKER_URL.rstrip('/')

    # Check if worker is High-Performance Rust Worker
    is_rust_worker = False
    try:
        r = requests.get(f"{worker_url}/health", timeout=2, **_get_worker_request_kwargs())
        if r.status_code == 200:
            info = r.json()
            srv = info.get("service", "").lower()
            eng = info.get("engine", "").lower()
            if "rust" in srv or "rust" in eng or "rust" in worker_url or srv == "thaiocr rust worker":
                is_rust_worker = True
    except Exception:
        pass

    if is_rust_worker:
        logger.info(f"Using High-Performance Rust OCR Worker at {worker_url} for '{filename}'")
        if is_pdf:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            yield {
                "status": "init",
                "page": 0,
                "total_pages": total_pages,
                "percent": 0,
                "message": f"เตรียมประมวลผล PDF {total_pages} หน้า (Rust OCR Engine)..."
            }

            md_pages = [f"# {filename}\n\n*ประมวลผลด้วยระบบ OneOCR Rust Native - ThaiOCR ONNX*\n\n---\n"]
            text_pages = []
            page_summaries = []

            for idx in range(total_pages):
                page_num = idx + 1
                page = doc[idx]
                pix = page.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes("png")

                t_page = time.time()
                resp = requests.post(
                    f"{worker_url}/ocr/image",
                    data=img_bytes,
                    headers={"Content-Type": "image/png"},
                    timeout=120,
                    **_get_worker_request_kwargs()
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"Rust OCR Worker Error: {resp.text}")

                res = resp.json()
                page_md, has_table, cols = format_page_markdown(res.get("lines", []), page_num, "แนวตั้ง (Portrait)")
                dt_page = time.time() - t_page

                md_pages.append(page_md)
                md_pages.append("\n---\n")

                page_text = res.get("text", "")
                text_pages.append(f"--- หน้า {page_num} ---\n{page_text}")
                page_summaries.append({"page": page_num, "orientation": "แนวตั้ง (Portrait)", "has_table": has_table, "cols": cols})

                percent = int((page_num / total_pages) * 100)
                table_info = f", ตาราง {cols} คอลัมน์" if has_table else ""
                yield {
                    "status": "progress",
                    "page": page_num,
                    "total_pages": total_pages,
                    "percent": percent,
                    "message": f"หน้า {page_num}/{total_pages}: {table_info} ({dt_page:.2f}s)",
                    "page_result": {
                        "page": page_num,
                        "text": page_text,
                        "markdown": page_md,
                        "has_table": has_table,
                        "cols": cols,
                        "latency_ms": int(dt_page * 1000)
                    }
                }

            doc.close()
            full_text = "\n\n".join(text_pages)
            full_md = "\n".join(md_pages).strip() + "\n"
            latency_ms = int((time.time() - start_time) * 1000)

            yield {
                "status": "completed",
                "percent": 100,
                "result": {
                    "page_count": total_pages,
                    "text": full_text,
                    "markdown": full_md,
                    "latency_ms": latency_ms,
                    "pages": page_summaries
                }
            }
        else:
            # Single Image
            t_img = time.time()
            resp = requests.post(
                f"{worker_url}/ocr/image",
                data=file_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=120,
                **_get_worker_request_kwargs()
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Rust OCR Worker Error: {resp.text}")

            res = resp.json()
            page_md, has_table, cols = format_page_markdown(res.get("lines", []), 1, "แนวตั้ง (Portrait)")
            dt_img = time.time() - t_img
            latency_ms = int(dt_img * 1000)

            full_text = res.get("text", "")
            full_md = f"# {filename}\n\n*ประมวลผลด้วยระบบ OneOCR Rust Native - ThaiOCR ONNX*\n\n---\n\n{page_md}"

            yield {
                "status": "completed",
                "percent": 100,
                "result": {
                    "page_count": 1,
                    "text": full_text,
                    "markdown": full_md,
                    "latency_ms": latency_ms,
                    "pages": [{"page": 1, "orientation": "แนวตั้ง (Portrait)", "has_table": has_table, "cols": cols}]
                }
            }
        return

    # Fallback to legacy remote worker stream if on Linux and not Rust
    if sys.platform != "win32":
        for evt in process_via_worker_stream(file_bytes, filename, dpi):
            yield evt
        return

    # Native Windows Streaming Execution
    engine = get_engine()
    if is_pdf:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total_pages = len(doc)
        yield {
            "status": "init",
            "page": 0,
            "total_pages": total_pages,
            "percent": 0,
            "message": f"เตรียมประมวลผล PDF {total_pages} หน้า..."
        }

        md_pages = [f"# {filename}\n\n*ประมวลผลด้วยระบบ OCR - ThaiOCR ONNX*\n\n---\n"]
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
            table_info = f", ตาราง {cols} คอลัมน์" if has_table else ""
            yield {
                "status": "progress",
                "page": page_num,
                "total_pages": total_pages,
                "percent": percent,
                "message": f"หน้า {page_num}/{total_pages}: {orient_label}{table_info} ({dt_page:.2f}s)",
                "page_summary": {"page": page_num, "orientation": orient_label, "has_table": has_table, "cols": cols}
            }

        doc.close()
        full_text = "\n\n".join(text_pages)
        full_md = "\n".join(md_pages).strip() + "\n"
        latency_ms = int((time.time() - start_time) * 1000)

        yield {
            "status": "completed",
            "percent": 100,
            "result": {
                "page_count": total_pages,
                "text": full_text,
                "markdown": full_md,
                "latency_ms": latency_ms,
                "pages": page_summaries
            }
        }
    else:
        # Single Image
        yield {
            "status": "init",
            "page": 0,
            "total_pages": 1,
            "percent": 20,
            "message": "กำลังถอดความภาพด้วยระบบ OCR..."
        }

        img = Image.open(io.BytesIO(file_bytes))
        res, orient_label, angle, rotated = recognize_with_orientation_check(engine, img)
        page_md, has_table, cols = format_page_markdown(res.get("lines", []), 1, orient_label)

        full_text = res.get("text", "")
        full_md = f"# {filename}\n\n*ประมวลผลด้วยระบบ OCR - ThaiOCR ONNX*\n\n---\n\n{page_md}"
        latency_ms = int((time.time() - start_time) * 1000)

        yield {
            "status": "completed",
            "percent": 100,
            "result": {
                "page_count": 1,
                "text": full_text,
                "markdown": full_md,
                "latency_ms": latency_ms,
                "pages": [{"page": 1, "orientation": orient_label, "has_table": has_table, "cols": cols}]
            }
        }


def process_document(file_bytes: bytes, filename: str, dpi: int = 150) -> dict:
    """Process PDF or Image and return structured Text and Markdown."""
    last_res = None
    for evt in process_document_stream(file_bytes, filename, dpi):
        if evt.get("status") == "completed":
            last_res = evt.get("result")
        elif evt.get("status") == "error":
            raise RuntimeError(evt.get("error", "OCR Processing Error"))
    if last_res:
        return last_res
    raise RuntimeError("OCR processing failed to produce a result")
