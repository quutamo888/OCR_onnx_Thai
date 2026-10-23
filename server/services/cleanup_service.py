from server.db import get_expired_jobs, delete_job
from server.storage import storage
from server.logger import logger


def cleanup_expired_data(max_age_days: int = 3) -> int:
    """Auto-delete jobs and associated Garage S3/local files older than max_age_days."""
    max_age_seconds = max_age_days * 86400
    expired = get_expired_jobs(max_age_seconds)
    purged = 0
    for job in expired:
        jid = job["id"]
        if job.get("s3_input_key"):
            storage.delete_object(job["s3_input_key"])
        if job.get("s3_text_key"):
            storage.delete_object(job["s3_text_key"])
        if job.get("s3_md_key"):
            storage.delete_object(job["s3_md_key"])
        delete_job(jid)
        purged += 1
    if purged > 0:
        logger.info(f"[Retention Policy] Auto-purged {purged} jobs/files older than {max_age_days} days.")
    return purged
