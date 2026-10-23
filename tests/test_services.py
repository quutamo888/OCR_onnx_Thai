import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from server.services.cleanup_service import cleanup_expired_data
from server.services.export_service import export_document_docx, export_document_xlsx
from server.services.job_service import process_ocr_job


# --- Cleanup Service Tests ---

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


# --- Export Service Tests ---

def test_export_document_docx_not_found():
    with patch("server.services.export_service.get_job", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            export_document_docx("nonexistent_job", {"username": "user1", "role": "user"})
        assert exc_info.value.status_code == 404


def test_export_document_docx_forbidden():
    job = {"id": "job1", "user_id": "other_user", "filename": "doc.pdf"}
    with patch("server.services.export_service.get_job", return_value=job):
        with pytest.raises(HTTPException) as exc_info:
            export_document_docx("job1", {"username": "user1", "role": "user"})
        assert exc_info.value.status_code == 403


def test_export_document_docx_success():
    job = {
        "id": "job1",
        "user_id": "user1",
        "filename": "doc.pdf",
        "s3_md_key": "outputs/job1/result.md",
        "s3_input_key": "inputs/job1/doc.pdf"
    }
    with patch("server.services.export_service.get_job", return_value=job), \
         patch("server.services.export_service.storage.get_object", side_effect=[b"# Markdown", b"dummy_pdf_bytes"]), \
         patch("server.services.export_service.export_to_docx", return_value=b"fake_docx_bytes") as mock_export:
        res = export_document_docx("job1", {"username": "user1", "role": "user"})
        assert isinstance(res, io.BytesIO)
        assert res.getvalue() == b"fake_docx_bytes"
        mock_export.assert_called_once()


def test_export_document_xlsx_success():
    job = {
        "id": "job1",
        "user_id": "user1",
        "filename": "doc.pdf",
        "s3_md_key": "outputs/job1/result.md",
        "s3_input_key": "inputs/job1/doc.pdf"
    }
    with patch("server.services.export_service.get_job", return_value=job), \
         patch("server.services.export_service.storage.get_object", side_effect=[b"# Table Markdown", b"dummy_pdf_bytes"]), \
         patch("server.services.export_service.export_to_xlsx", return_value=b"fake_xlsx_bytes") as mock_export:
        res = export_document_xlsx("job1", {"username": "admin", "role": "admin"})
        assert isinstance(res, io.BytesIO)
        assert res.getvalue() == b"fake_xlsx_bytes"
        mock_export.assert_called_once()


# --- Job Service Tests ---

def test_process_ocr_job_success():
    fake_ocr_res = {
        "text": "Hello OCR",
        "markdown": "# Hello OCR",
        "page_count": 2,
        "pages": [{"page": 1}, {"page": 2}]
    }
    with patch("server.services.job_service.process_document", return_value=fake_ocr_res) as mock_process, \
         patch("server.services.job_service.storage.put_object") as mock_put, \
         patch("server.services.job_service.update_job_success") as mock_success, \
         patch("server.services.job_service.set_cached_ocr") as mock_cache, \
         patch("server.services.job_service.log_audit") as mock_audit, \
         patch("server.services.job_service.time.time", return_value=100.5):
        process_ocr_job(
            job_id="job123",
            file_bytes=b"fake_file_bytes",
            filename="sample.pdf",
            file_hash="hash123",
            user_id="user1",
            ip_addr="127.0.0.1",
            start_time=100.0
        )
        mock_process.assert_called_once_with(b"fake_file_bytes", filename="sample.pdf")
        assert mock_put.call_count == 2
        mock_success.assert_called_once_with(
            job_id="job123",
            page_count=2,
            latency_ms=500,
            s3_text_key="outputs/job123/result.txt",
            s3_md_key="outputs/job123/result.md"
        )
        mock_cache.assert_called_once_with(
            "hash123",
            {
                "text": "Hello OCR",
                "markdown": "# Hello OCR",
                "page_count": 2,
                "duration": 0.5,
                "cached_at": 100.5
            }
        )
        mock_audit.assert_called_once_with(
            "OCR_SUCCESS",
            "user1",
            "127.0.0.1",
            "Processed sample.pdf (2 pages, 0.50s)"
        )


def test_process_ocr_job_error():
    with patch("server.services.job_service.process_document", side_effect=RuntimeError("OCR engine crashed")) as mock_process, \
         patch("server.services.job_service.update_job_error") as mock_error, \
         patch("server.services.job_service.log_audit") as mock_audit:
        process_ocr_job(
            job_id="job123",
            file_bytes=b"fake_file_bytes",
            filename="sample.pdf",
            file_hash="hash123",
            user_id="user1",
            ip_addr="127.0.0.1",
            start_time=100.0
        )
        mock_process.assert_called_once_with(b"fake_file_bytes", filename="sample.pdf")
        mock_error.assert_called_once_with("job123", "OCR engine crashed")
        mock_audit.assert_called_once_with(
            "OCR_ERROR",
            "user1",
            "127.0.0.1",
            "Failed sample.pdf: OCR engine crashed"
        )
