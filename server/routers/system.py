import time
from fastapi import APIRouter, Depends
from server.core.dependencies import require_admin
from server.logger import get_recent_engine_logs
from server.cache import is_cache_healthy
from server.storage import storage

router = APIRouter(tags=["System"])


@router.get("/health")
@router.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "storage": storage.is_healthy(),
        "redis_cache": is_cache_healthy(),
        "timestamp": time.time()
    }


@router.get("/api/engine/logs")
async def get_logs(lines: int = 50, admin: dict = Depends(require_admin)):
    return {"logs": get_recent_engine_logs(lines)}
