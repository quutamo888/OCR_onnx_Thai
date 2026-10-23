import io
from fastapi import HTTPException
from server.db import get_job
from server.storage import storage
from server.exporter import export_to_docx, export_to_xlsx


def export_document_docx(job_id: str, current_user: dict, job: dict = None) -> io.BytesIO:
    if job is None:
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

    docx_bytes = export_to_docx(input_file_bytes, job.get("filename", "document"), md_content)
    return io.BytesIO(docx_bytes) if isinstance(docx_bytes, bytes) else docx_bytes


def export_document_xlsx(job_id: str, current_user: dict, job: dict = None) -> io.BytesIO:
    if job is None:
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

    xlsx_bytes = export_to_xlsx(input_file_bytes, job.get("filename", "document"), md_content)
    return io.BytesIO(xlsx_bytes) if isinstance(xlsx_bytes, bytes) else xlsx_bytes
