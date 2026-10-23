"""Security guardrails for ThaiOCR ONNX System.

Guarantees:
1. Strict file extension and multi-extension blocking (no shell scripts, binaries, or exploit payloads).
2. Magic byte / header verification for valid PDF and image formats.
3. Content inspection against script shebangs and command execution signatures.
4. Deep format validation via PyMuPDF (PDF) and Pillow (Images) before processing.
5. Safe filename normalization to prevent path traversal and shell injection.
"""

import io
import re
from pathlib import Path
from typing import Tuple
from PIL import Image
import fitz  # PyMuPDF
from fastapi import HTTPException

# Explicit allowed extensions
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# Dangerous extensions that must NEVER appear anywhere in the filename
DANGEROUS_EXTENSIONS = {
    ".sh", ".bash", ".zsh", ".ksh", ".csh", ".bat", ".cmd", ".ps1", ".psm1",
    ".exe", ".com", ".scr", ".pif", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".py", ".pyw", ".pl", ".pm", ".rb", ".php", ".php3", ".php4", ".php5", ".phtml",
    ".jsp", ".jspx", ".asp", ".aspx", ".cgi", ".elf", ".bin", ".jar", ".war", ".msi"
}

# Signatures for shell scripts and exploit code
EXPLOIT_SIGNATURES = [
    b"#!/bin/sh",
    b"#!/bin/bash",
    b"#!/bin/zsh",
    b"#!/usr/bin/env",
    b"#!/usr/bin/bash",
    b"#!/usr/bin/sh",
    b"#!/usr/bin/python",
    b"#!/usr/bin/perl",
    b"@echo off",
    b"<script",
    b"powershell -",
    b"/bin/bash -i",
    b"/bin/sh -i",
]


def sanitize_filename(filename: str) -> str:
    """Normalize and sanitize filename, preventing directory traversal and injection."""
    # Strip paths
    clean_name = Path(filename).name
    # Remove null bytes and non-printable characters
    clean_name = re.sub(r"[\x00-\x1f\x7f]", "", clean_name)
    # Remove dangerous shell metacharacters
    clean_name = re.sub(r"[;&|`$(){}<>\\]", "_", clean_name)
    # Collapse consecutive dots or underscores
    clean_name = re.sub(r"\.{2,}", ".", clean_name)
    return clean_name.strip()


def validate_file_safety(filename: str, file_bytes: bytes) -> Tuple[str, str]:
    """Validate file against shell scripts, exploits, and format integrity.

    Returns:
        (sanitized_filename, file_ext)
    Raises:
        HTTPException on any security violation or invalid structure.
    """
    clean_name = sanitize_filename(filename)
    lower_name = clean_name.lower()

    # 1. Check dangerous extensions anywhere in filename
    for dang in DANGEROUS_EXTENSIONS:
        if dang in lower_name:
            raise HTTPException(
                status_code=400,
                detail=f"ตรวจพบไฟล์สคริปต์/โปรแกรมอันตราย ({dang}) ไม่อนุญาตให้อัปโหลดเข้าสู่ระบบ"
            )

    # 2. Check primary extension
    ext = Path(clean_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"นามสกุลไฟล์ '{ext}' ไม่ได้รับอนุญาต รองรับเฉพาะเอกสาร PDF และไฟล์รูปภาพ"
        )

    # 3. Check file size limits (50MB max, > 0 bytes)
    size = len(file_bytes)
    if size == 0:
        raise HTTPException(status_code=400, detail="ไฟล์มีขนาดเป็น 0 ไบต์")
    if size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ขนาดไฟล์เกินขีดจำกัดความปลอดภัย 50MB")

    # 4. Check for shell script shebangs and exploit patterns in file header
    header_sample = file_bytes[:4096].lower()
    for sig in EXPLOIT_SIGNATURES:
        if sig.lower() in header_sample:
            raise HTTPException(
                status_code=400,
                detail="ตรวจพบเนื้อหาคำสั่ง Shell Script / Executable ในไฟล์ ปฏิเสธการประมวลผลเพื่อความปลอดภัย"
            )

    # 5. Magic Byte Verification & Deep Format Integrity Validation
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="โครงสร้างไฟล์ไม่ใช่เอกสาร PDF ที่ถูกต้อง (Magic byte mismatch)")
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if len(doc) == 0:
                doc.close()
                raise HTTPException(status_code=400, detail="ไฟล์ PDF ว่างเปล่าหรือไม่มีหน้าเอกสาร")
            doc.close()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"ไฟล์ PDF เสียหายหรือไม่สามารถเปิดอ่านได้: {str(e)}")
    else:
        # Image Magic Bytes
        is_valid_image = False
        if ext == ".png" and file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            is_valid_image = True
        elif ext in {".jpg", ".jpeg"} and file_bytes.startswith(b"\xff\xd8\xff"):
            is_valid_image = True
        elif ext == ".bmp" and file_bytes.startswith(b"BM"):
            is_valid_image = True
        elif ext == ".tiff" and (file_bytes.startswith(b"II*\x00") or file_bytes.startswith(b"MM\x00*")):
            is_valid_image = True
        elif ext == ".webp" and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
            is_valid_image = True

        if not is_valid_image:
            raise HTTPException(status_code=400, detail=f"Header ของไฟล์ภาพ {ext} ไม่ตรงตามมาตรฐานความปลอดภัย")

        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"ไฟล์รูปภาพไม่สมบูรณ์หรือเสียหาย: {str(e)}")

    return clean_name, ext
