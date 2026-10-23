from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from server.core.dependencies import get_current_user
from server.core.security import format_content_disposition
from server.db import get_job
from server.storage import storage
from server.exporter import export_to_docx, export_to_xlsx
from server.services.export_service import export_document_docx, export_document_xlsx

router = APIRouter(prefix="/api/ocr/export", tags=["Export"])


class ExportRequest(BaseModel):
    markdown: str
    filename: Optional[str] = "document"
    job_id: Optional[str] = None


@router.get("/docx/{job_id}")
async def export_docx_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(job_id)
    doc_io = export_document_docx(job_id, user, job=job)
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
    xlsx_io = export_document_xlsx(job_id, user, job=job)
    base_name = (job.get("filename") if job else "document").rsplit(".", 1)[0]
    out_name = f"{base_name}.xlsx"
    return Response(
        content=xlsx_io.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": format_content_disposition("attachment", out_name)}
    )


@router.post("/{format}")
async def export_custom_markdown(
    format: str,
    body: ExportRequest,
    user: dict = Depends(get_current_user)
):
    """Export custom/edited markdown directly to DOCX, XLSX, TXT or MD."""
    fmt = format.lower()
    base_name = Path(body.filename or "document").stem

    source_bytes = None
    if body.job_id:
        job = get_job(body.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if user.get("role") != "admin" and job.get("user_id") != user.get("username"):
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสารนี้")
        if job.get("s3_input_key"):
            source_bytes = storage.get_object(job["s3_input_key"])

    if fmt == "docx":
        data = export_to_docx(source_bytes, body.filename or "document.pdf", body.markdown)
        filename = f"{base_name}_reviewed.docx"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "xlsx":
        data = export_to_xlsx(source_bytes, body.filename or "document.pdf", body.markdown)
        filename = f"{base_name}_reviewed.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "txt":
        data = body.markdown.encode("utf-8")
        filename = f"{base_name}_reviewed.txt"
        media_type = "text/plain; charset=utf-8"
    elif fmt == "md":
        data = body.markdown.encode("utf-8")
        filename = f"{base_name}_reviewed.md"
        media_type = "text/markdown; charset=utf-8"
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported: docx, xlsx, txt, md")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": format_content_disposition("attachment", filename)}
    )
