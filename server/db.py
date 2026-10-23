"""SQLite Database manager for ThaiOCR ONNX Web System.

Stores job history, latency metrics, audit logs, and LDAP configurations.
"""

import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "ocr_engine.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cur = conn.cursor()

    # Jobs Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        page_count INTEGER DEFAULT 1,
        status TEXT NOT NULL,
        error_msg TEXT,
        latency_ms INTEGER DEFAULT 0,
        s3_input_key TEXT,
        s3_text_key TEXT,
        s3_md_key TEXT,
        user_id TEXT NOT NULL,
        user_name TEXT,
        created_at REAL NOT NULL,
        finished_at REAL,
        progress_percent INTEGER DEFAULT 0
    )
    """)

    # Migration: Ensure progress_percent column exists for existing DB
    cur.execute("PRAGMA table_info(jobs)")
    cols = [r["name"] for r in cur.fetchall()]
    if "progress_percent" not in cols:
        cur.execute("ALTER TABLE jobs ADD COLUMN progress_percent INTEGER DEFAULT 0")

    # LDAP Configuration Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ldap_config (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        server_uri TEXT NOT NULL,
        use_ssl INTEGER DEFAULT 0,
        base_dn TEXT NOT NULL,
        bind_dn TEXT,
        bind_password TEXT,
        user_search_filter TEXT NOT NULL,
        group_search_filter TEXT,
        allowed_groups TEXT,
        is_enabled INTEGER DEFAULT 1,
        updated_at REAL NOT NULL
    )
    """)

    # Audit Logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        user_id TEXT,
        ip_address TEXT,
        details TEXT,
        created_at REAL NOT NULL
    )
    """)

    # API Keys for External Machine-to-Machine Systems
    cur.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        key_prefix TEXT NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        allowed_ips TEXT NOT NULL,
        rate_limit INTEGER DEFAULT 60,
        is_active INTEGER DEFAULT 1,
        created_by TEXT NOT NULL,
        created_at REAL NOT NULL,
        last_used_at REAL,
        expires_at REAL
    )
    """)

    # Local System Users managed by Admin
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        can_use_api INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_by TEXT NOT NULL,
        created_at REAL NOT NULL
    )
    """)

    # Default LDAP Config if not present
    cur.execute("SELECT id FROM ldap_config WHERE id = 1")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO ldap_config (
            id, server_uri, use_ssl, base_dn, bind_dn, bind_password,
            user_search_filter, group_search_filter, allowed_groups, is_enabled, updated_at
        ) VALUES (
            1, 'ldap://ad.example.com:389', 0, 'DC=example,DC=com',
            'CN=ocr_svc,OU=ServiceAccounts,DC=example,DC=com', '',
            '(sAMAccountName={username})', '(member={user_dn})', 'OCR_Users', 1, ?
        )
        """, (time.time(),))

    # Super Admin Security Settings (2FA TOTP & Passkey toggles)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_security_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        totp_enabled INTEGER DEFAULT 0,
        totp_secret TEXT DEFAULT '',
        passkey_enabled INTEGER DEFAULT 0,
        updated_at REAL NOT NULL
    )
    """)

    cur.execute("SELECT id FROM admin_security_settings WHERE id = 1")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO admin_security_settings (id, totp_enabled, totp_secret, passkey_enabled, updated_at)
        VALUES (1, 0, '', 0, ?)
        """, (time.time(),))

    # Super Admin WebAuthn Passkeys
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_passkeys (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        public_key TEXT NOT NULL,
        sign_count INTEGER DEFAULT 0,
        created_at REAL NOT NULL,
        last_used_at REAL
    )
    """)

    conn.commit()
    conn.close()


def create_job(job_id: str, filename: str, file_type: str, size_bytes: int, user_id: str, user_name: str, s3_input_key: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    now = time.time()
    cur.execute("""
    INSERT INTO jobs (id, filename, file_type, size_bytes, status, user_id, user_name, s3_input_key, created_at, progress_percent)
    VALUES (?, ?, ?, ?, 'processing', ?, ?, ?, ?, 0)
    """, (job_id, filename, file_type, size_bytes, user_id, user_name, s3_input_key, now))
    conn.commit()
    conn.close()
    return {"id": job_id, "status": "processing", "created_at": now, "progress_percent": 0}


def update_job_progress(job_id: str, percent: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE jobs
    SET progress_percent = ?
    WHERE id = ? AND status = 'processing'
    """, (percent, job_id))
    conn.commit()
    conn.close()


def update_job_success(job_id: str, page_count: int, latency_ms: int, s3_text_key: str, s3_md_key: str):
    conn = get_connection()
    cur = conn.cursor()
    now = time.time()
    cur.execute("""
    UPDATE jobs
    SET status = 'completed', page_count = ?, latency_ms = ?, s3_text_key = ?, s3_md_key = ?, finished_at = ?, progress_percent = 100
    WHERE id = ?
    """, (page_count, latency_ms, s3_text_key, s3_md_key, now, job_id))
    conn.commit()
    conn.close()


def update_job_error(job_id: str, error_msg: str, latency_ms: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    now = time.time()
    cur.execute("""
    UPDATE jobs
    SET status = 'failed', error_msg = ?, latency_ms = ?, finished_at = ?
    WHERE id = ?
    """, (error_msg, latency_ms, now, job_id))
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_job(job_id: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    job = dict(row)
    cur.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return job


def get_expired_jobs(max_age_seconds: int = 3 * 86400) -> List[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cutoff_time = time.time() - max_age_seconds
    cur.execute("SELECT * FROM jobs WHERE created_at < ?", (cutoff_time,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_and_mark_stale_jobs(timeout_seconds: int = 600):
    """Mark jobs that have been processing for longer than timeout_seconds as failed (hung or crashed)."""
    conn = get_connection()
    cur = conn.cursor()
    stale_cutoff = time.time() - timeout_seconds
    cur.execute("""
    UPDATE jobs
    SET status = 'failed', error_msg = 'การประมวลผลหมดเวลา (Timeout / Task Interrupted)'
    WHERE status = 'processing' AND created_at < ?
    """, (stale_cutoff,))
    conn.commit()
    conn.close()


def list_jobs(limit: int = 50, offset: int = 0, user_id: Optional[str] = None) -> List[dict]:
    check_and_mark_stale_jobs()
    conn = get_connection()
    cur = conn.cursor()
    if user_id:
        cur.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (user_id, limit, offset))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_metrics() -> dict:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM jobs")
    total_jobs = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS completed FROM jobs WHERE status = 'completed'")
    completed_jobs = cur.fetchone()["completed"]

    cur.execute("SELECT COUNT(*) AS failed FROM jobs WHERE status = 'failed'")
    failed_jobs = cur.fetchone()["failed"]

    cur.execute("SELECT AVG(latency_ms) AS avg_latency FROM jobs WHERE status = 'completed'")
    avg_latency = cur.fetchone()["avg_latency"] or 0

    cur.execute("SELECT SUM(page_count) AS total_pages FROM jobs WHERE status = 'completed'")
    total_pages = cur.fetchone()["total_pages"] or 0

    cur.execute("""
    SELECT strftime('%Y-%m-%d', datetime(created_at, 'unixepoch', 'localtime')) AS day,
           COUNT(*) AS count,
           AVG(latency_ms) AS avg_lat
    FROM jobs
    GROUP BY day
    ORDER BY day DESC
    LIMIT 7
    """)
    daily_stats = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "success_rate": round((completed_jobs / max(1, total_jobs)) * 100, 1),
        "avg_latency_ms": round(avg_latency),
        "total_pages": total_pages,
        "daily_stats": daily_stats[::-1]
    }


def get_ldap_config() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ldap_config WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


def save_ldap_config(cfg: dict):
    conn = get_connection()
    cur = conn.cursor()
    now = time.time()
    cur.execute("""
    UPDATE ldap_config
    SET server_uri = ?, use_ssl = ?, base_dn = ?, bind_dn = ?, bind_password = ?,
        user_search_filter = ?, group_search_filter = ?, allowed_groups = ?, is_enabled = ?, updated_at = ?
    WHERE id = 1
    """, (
        cfg.get("server_uri"),
        1 if cfg.get("use_ssl") else 0,
        cfg.get("base_dn"),
        cfg.get("bind_dn"),
        cfg.get("bind_password", ""),
        cfg.get("user_search_filter"),
        cfg.get("group_search_filter"),
        cfg.get("allowed_groups"),
        1 if cfg.get("is_enabled", True) else 0,
        now
    ))
    conn.commit()
    conn.close()


def log_audit(event_type: str, user_id: str, ip_address: str, details: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO audit_logs (event_type, user_id, ip_address, details, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (event_type, user_id, ip_address, details, time.time()))
    conn.commit()
    conn.close()


def list_audit_logs(limit: int = 100) -> List[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# API Key Management for External Machine-to-Machine Systems
# ---------------------------------------------------------------------------

def hash_api_key(raw_key: str) -> str:
    """Hash raw API key using SHA-256 for secure storage."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_new_api_key(
    name: str,
    allowed_ips: str,
    created_by: str,
    rate_limit: int = 60,
    expires_in_days: Optional[int] = 365
) -> Tuple[dict, str]:
    """Generate high-entropy API key for an external service.
    Returns (key_record, plain_secret_key).
    Note: plain_secret_key is only returned once upon creation!
    """
    raw_token = secrets.token_hex(24)
    plain_key = f"ocr_sk_live_{raw_token}"
    key_prefix = plain_key[:18] + "..."
    key_hash = hash_api_key(plain_key)
    key_id = secrets.token_hex(8)

    now = time.time()
    expires_at = now + (expires_in_days * 86400) if expires_in_days else None

    # Clean allowed IPs (comma separated)
    clean_ips = ",".join([ip.strip() for ip in allowed_ips.split(",") if ip.strip()])
    if not clean_ips:
        clean_ips = "*"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO api_keys (
        id, name, key_prefix, key_hash, allowed_ips, rate_limit, is_active, created_by, created_at, expires_at
    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
    """, (
        key_id, name.strip(), key_prefix, key_hash, clean_ips, rate_limit, created_by, now, expires_at
    ))
    conn.commit()
    conn.close()

    record = {
        "id": key_id,
        "name": name.strip(),
        "key_prefix": key_prefix,
        "allowed_ips": clean_ips,
        "rate_limit": rate_limit,
        "is_active": 1,
        "created_by": created_by,
        "created_at": now,
        "expires_at": expires_at,
        "last_used_at": None
    }
    return record, plain_key


def list_api_keys() -> List[dict]:
    """List all API keys (excluding secret hashes)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, name, key_prefix, allowed_ips, rate_limit, is_active, created_by, created_at, last_used_at, expires_at
    FROM api_keys
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_api_key_by_hash(key_hash: str) -> Optional[dict]:
    """Retrieve active API key record matching hash."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1", (key_hash,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_api_key_status(key_id: str, is_active: bool) -> bool:
    """Activate or revoke an API key."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE api_keys SET is_active = ? WHERE id = ?", (1 if is_active else 0, key_id))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def delete_api_key(key_id: str) -> bool:
    """Permanently delete an API key."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def update_api_key_last_used(key_id: str):
    """Update last used timestamp for an API key."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (time.time(), key_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Local User Management (Admin Managed Accounts)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash user password using PBKDF2-HMAC-SHA256 with a unique random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against salted PBKDF2 hash or legacy static-salt hash."""
    import hmac
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_digest = parts
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return hmac.compare_digest(candidate, expected_digest)
    # ponytail: legacy static salt fallback; remove once all existing users rotate password
    legacy_salt = "thai_ocr_user_salt_2026"
    legacy_candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), legacy_salt.encode("utf-8"), 100_000).hex()
    return hmac.compare_digest(legacy_candidate, stored_hash)


def create_local_user(username: str, password: str, display_name: str, role: str = "user", created_by: str = "admin") -> dict:
    """Create a new local user account."""
    u = username.strip().lower()
    pw_hash = hash_password(password)
    disp = display_name.strip() or u
    now = time.time()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (username, password_hash, display_name, role, can_use_api, is_active, created_by, created_at)
    VALUES (?, ?, ?, ?, 0, 1, ?, ?)
    """, (u, pw_hash, disp, role, created_by, now))
    conn.commit()
    conn.close()

    return {
        "username": u,
        "display_name": disp,
        "role": role,
        "can_use_api": 0,
        "is_active": 1,
        "created_by": created_by,
        "created_at": now
    }


def get_local_user(username: str) -> Optional[dict]:
    """Get user by username for authentication."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username.strip().lower(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_local_users() -> List[dict]:
    """List all local users without password hashes."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT username, display_name, role, can_use_api, is_active, created_by, created_at
    FROM users
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_local_user_status(username: str, is_active: bool) -> bool:
    """Activate or deactivate a local user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_active = ? WHERE username = ?", (1 if is_active else 0, username.strip().lower()))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def update_local_user_password(username: str, new_password_hash: str, display_name: Optional[str] = None, role: str = "user") -> bool:
    """Update password hash for a local user, or insert if super admin not yet in DB."""
    u = username.strip().lower()
    now = time.time()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE username = ?", (u,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_password_hash, u))
    else:
        disp = (display_name or u).strip()
        cur.execute("""
        INSERT INTO users (username, password_hash, display_name, role, can_use_api, is_active, created_by, created_at)
        VALUES (?, ?, ?, ?, 1 if ? = 'admin' else 0, 1, 'system', ?)
        """, (u, new_password_hash, disp, role, role, now))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def delete_local_user(username: str) -> bool:
    """Permanently delete a local user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = ?", (username.strip().lower(),))
    affected = cur.rowcount > 0
    conn.commit()
    conn.close()
    return affected


# ---------------------------------------------------------------------------
# Super Admin Security Settings (2FA TOTP & WebAuthn Passkeys)
# ---------------------------------------------------------------------------

def get_admin_security_settings() -> dict:
    """Get singleton security settings for Super Admin."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin_security_settings WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"id": 1, "totp_enabled": 0, "totp_secret": "", "passkey_enabled": 0, "updated_at": 0.0}
    return dict(row)


def save_admin_security_settings(
    totp_enabled: Optional[bool] = None,
    totp_secret: Optional[str] = None,
    passkey_enabled: Optional[bool] = None,
) -> dict:
    """Update Super Admin 2FA / Passkey settings."""
    current = get_admin_security_settings()
    new_totp_enabled = current["totp_enabled"] if totp_enabled is None else (1 if totp_enabled else 0)
    new_totp_secret = current["totp_secret"] if totp_secret is None else totp_secret.strip()
    new_passkey_enabled = current["passkey_enabled"] if passkey_enabled is None else (1 if passkey_enabled else 0)
    now = time.time()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE admin_security_settings
    SET totp_enabled = ?, totp_secret = ?, passkey_enabled = ?, updated_at = ?
    WHERE id = 1
    """, (new_totp_enabled, new_totp_secret, new_passkey_enabled, now))
    conn.commit()
    conn.close()
    return get_admin_security_settings()


def save_admin_passkey(cred_id: str, name: str, public_key: str, sign_count: int = 0) -> dict:
    """Register or replace a WebAuthn Passkey for Super Admin."""
    now = time.time()
    clean_name = name.strip() or "Passkey Device"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO admin_passkeys (id, name, public_key, sign_count, created_at, last_used_at)
    VALUES (?, ?, ?, ?, ?, NULL)
    """, (cred_id.strip(), clean_name, public_key.strip(), sign_count, now))
    conn.commit()
    conn.close()
    return {
        "id": cred_id.strip(),
        "name": clean_name,
        "sign_count": sign_count,
        "created_at": now,
        "last_used_at": None,
    }


def list_admin_passkeys() -> List[dict]:
    """List all registered Super Admin Passkeys (excluding raw public key material)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, name, sign_count, created_at, last_used_at
    FROM admin_passkeys
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_admin_passkey(cred_id: str) -> Optional[dict]:
    """Get a single registered Passkey including public_key by credential ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin_passkeys WHERE id = ?", (cred_id.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_admin_passkey_usage(cred_id: str, sign_count: int = 0):
    """Record last_used_at timestamp and updated sign_count on Passkey assertion."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE admin_passkeys
    SET last_used_at = ?, sign_count = ?
    WHERE id = ?
    """, (time.time(), sign_count, cred_id.strip()))
    conn.commit()
    conn.close()


def delete_admin_passkey(cred_id: str) -> bool:
    """Delete a Super Admin Passkey. Auto-disables passkey_enabled if none remain."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM admin_passkeys WHERE id = ?", (cred_id.strip(),))
    affected = cur.rowcount > 0
    cur.execute("SELECT COUNT(*) AS cnt FROM admin_passkeys")
    remaining = cur.fetchone()["cnt"]
    if remaining == 0:
        cur.execute("UPDATE admin_security_settings SET passkey_enabled = 0, updated_at = ? WHERE id = 1", (time.time(),))
    conn.commit()
    conn.close()
    return affected


init_db()

