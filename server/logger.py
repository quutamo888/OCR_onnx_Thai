"""Engine Logger for ThaiOCR ONNX System.

Logs engine lifecycle, DLL calls, OCR processing, orientation corrections, and errors.
Writes to data/logs/engine.log and console.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "engine.log"

logger = logging.getLogger("thai_ocr_engine")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [Engine] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler (10 MB per file, max 5 backups)
    fh = RotatingFileHandler(str(LOG_FILE), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def get_recent_engine_logs(max_lines: int = 100) -> list[str]:
    """Read recent lines from engine.log for Admin UI inspection."""
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-max_lines:]
    except Exception as e:
        return [f"Error reading engine log: {e}"]
