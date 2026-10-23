import os
from typing import List


class Settings:
    PROJECT_NAME: str = "ThaiOCR ONNX API"
    PROJECT_DESCRIPTION: str = "ระบบให้บริการแปลงข้อความจากภาพและเอกสาร ThaiOCR ONNX"
    VERSION: str = ""

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
