import time
from server.db import update_job_success, update_job_error, log_audit
from server.storage import storage
from server.cache import set_cached_ocr
from server.ocr_service import process_document
from server.logger import logger


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
        ocr_res = process_document(file_bytes, filename=filename)
        text_out = ocr_res.get("text", "")
        md_out = ocr_res.get("markdown", "")
        page_count = ocr_res.get("page_count", 1)

        s3_txt_key = f"outputs/{job_id}/result.txt"
        s3_md_key = f"outputs/{job_id}/result.md"

        storage.put_object(s3_txt_key, text_out.encode("utf-8"), content_type="text/plain; charset=utf-8")
        storage.put_object(s3_md_key, md_out.encode("utf-8"), content_type="text/markdown; charset=utf-8")

        duration = time.time() - start_time
        latency_ms = int(duration * 1000)

        update_job_success(
            job_id=job_id,
            page_count=page_count,
            latency_ms=latency_ms,
            s3_text_key=s3_txt_key,
            s3_md_key=s3_md_key
        )

        set_cached_ocr(file_hash, {
            "text": text_out,
            "markdown": md_out,
            "page_count": page_count,
            "duration": duration,
            "cached_at": time.time()
        })

        log_audit("OCR_SUCCESS", user_id, ip_addr, f"Processed {filename} ({page_count} pages, {duration:.2f}s)")
        logger.info(f"Job {job_id} ({filename}) finished in {duration:.2f}s ({page_count} pages).")
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_job_error(job_id, str(e))
        log_audit("OCR_ERROR", user_id, ip_addr, f"Failed {filename}: {e}")
