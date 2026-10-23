"""ThaiOCR - Dynamic Docker Compose Auto-Scaler.

Features:
- Monitors SQLite queue: SELECT COUNT(*) FROM jobs WHERE status = 'processing'
- Fast reactive scale-up (spins up more workers immediately when queue arrives)
- Safe idle cooldown scale-down (waits IDLE_COOLDOWN_SEC before scaling down to save RAM/CPU)
- Zero downtime: uses `docker compose up -d --no-recreate --scale rust-ocr-worker=N`
"""

import os
import sqlite3
import subprocess
import time

MIN_WORKERS = int(os.getenv("MIN_WORKERS", "1"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "6"))
IDLE_COOLDOWN_SEC = int(os.getenv("IDLE_COOLDOWN_SEC", "60"))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "3"))

DB_PATH = os.getenv("DB_PATH", "/app/data/ocr_engine.db")
COMPOSE_FILE = os.getenv("COMPOSE_FILE", "/workspace/docker-compose.yml")
SERVICE_NAME = os.getenv("SERVICE_NAME", "rust-ocr-worker")


def get_processing_job_count() -> int:
    """Read number of active processing jobs from SQLite DB."""
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'processing'")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        print(f"[Autoscaler] DB query error: {e}", flush=True)
        return 0


def get_current_worker_count() -> int:
    """Get number of currently running worker containers."""
    try:
        cmd = ["docker", "compose", "-f", COMPOSE_FILE, "ps", "-q", "--status", "running", SERVICE_NAME]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        return len(lines)
    except Exception as e:
        print(f"[Autoscaler] docker compose ps error: {e}", flush=True)
        return 1


def scale_workers(target_count: int):
    """Scale workers using docker compose --scale without recreating existing containers."""
    target_count = max(MIN_WORKERS, min(MAX_WORKERS, target_count))
    print(f"[Autoscaler] Scaling '{SERVICE_NAME}' to {target_count} instances...", flush=True)
    try:
        cmd = [
            "docker", "compose", "-f", COMPOSE_FILE,
            "up", "-d", "--no-recreate",
            "--scale", f"{SERVICE_NAME}={target_count}",
            SERVICE_NAME
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[Autoscaler] Scale completed: {target_count} workers active.", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"[Autoscaler] Scale command failed: {e.stderr}", flush=True)


def main():
    print("==================================================================", flush=True)
    print("      ThaiOCR - Dynamic Docker Compose Auto-Scaler Active         ", flush=True)
    print("==================================================================", flush=True)
    print(f"[Config] Min Workers: {MIN_WORKERS} | Max Workers: {MAX_WORKERS}", flush=True)
    print(f"[Config] Cooldown: {IDLE_COOLDOWN_SEC}s | Interval: {CHECK_INTERVAL_SEC}s", flush=True)
    print(f"[Config] Compose File: {COMPOSE_FILE} | DB: {DB_PATH}", flush=True)

    idle_since = None

    while True:
        try:
            active_jobs = get_processing_job_count()
            current_workers = get_current_worker_count()
            now = time.time()

            if active_jobs > 0:
                idle_since = None
                # Calculation: 1 job -> 2 workers, 2 jobs -> 3 workers, etc.
                desired = min(MAX_WORKERS, max(2, active_jobs + 1))
                if desired > current_workers:
                    print(f"[Autoscaler] Active jobs: {active_jobs} -> Scaling UP from {current_workers} to {desired}", flush=True)
                    scale_workers(desired)
            else:
                # System is idle (0 processing jobs)
                if current_workers > MIN_WORKERS:
                    if idle_since is None:
                        idle_since = now
                        print(f"[Autoscaler] All jobs completed. Idle countdown started ({IDLE_COOLDOWN_SEC}s)...", flush=True)
                    elif (now - idle_since) >= IDLE_COOLDOWN_SEC:
                        print(f"[Autoscaler] Idle for {IDLE_COOLDOWN_SEC}s -> Scaling DOWN from {current_workers} to {MIN_WORKERS}", flush=True)
                        scale_workers(MIN_WORKERS)
                        idle_since = None
                else:
                    idle_since = None

        except Exception as ex:
            print(f"[Autoscaler Loop Error]: {ex}", flush=True)

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
