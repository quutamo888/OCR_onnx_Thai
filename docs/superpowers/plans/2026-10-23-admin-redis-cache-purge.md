# Admin Redis OCR Cache Purge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Redis OCR cache purge functionality (both per-task and full bulk flush) for Local Admin users across Backend API and Frontend UI.

**Architecture:** 
1. Cache layer: Add `purge_cached_ocr` and `purge_all_cached_ocr` in `server/cache.py` using non-blocking Redis SCAN.
2. Admin router: Expose `POST /api/admin/cache/purge/{job_id}` and `POST /api/admin/cache/purge-all` guarded by `require_admin` in `server/routers/admin.py`.
3. Frontend UI: Add "ล้างแคช" action button in History table for completed tasks (admin only) and "ล้างแคช OCR ทั้งหมด" in Admin dashboard in `frontend/src/App.jsx`.

**Tech Stack:** Python 3.11, FastAPI, Redis 7, React, Vite, Tailwind CSS, Lucide Icons, pytest.

## Global Constraints

- Strict Admin role authorization (`require_admin` returning 403 Forbidden for non-admin users).
- Non-blocking Redis operations: Do NOT use `FLUSHDB`; use `client.scan_iter("ocr_cache:*")` to protect download tickets (`ticket:dl:*`).
- All admin purge actions must record an audit entry in `audit_logs` table (`log_audit`).
- Maintain full compatibility with current React UI theme and state management.

---

### Task 1: Cache Layer Purge Functions (`server/cache.py`)

**Files:**
- Modify: `server/cache.py`
- Create: `tests/test_cache_purge.py`

**Interfaces:**
- Produces:
  - `server.cache.purge_cached_ocr(file_hash: str) -> bool`
  - `server.cache.purge_all_cached_ocr() -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cache_purge.py`:
```python
from unittest.mock import MagicMock, patch
from server.cache import purge_cached_ocr, purge_all_cached_ocr


def test_purge_cached_ocr_success():
    mock_redis = MagicMock()
    mock_redis.delete.return_value = 1
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        assert purge_cached_ocr("abc123hash") is True
        mock_redis.delete.assert_called_once_with("ocr_cache:abc123hash")


def test_purge_cached_ocr_not_found():
    mock_redis = MagicMock()
    mock_redis.delete.return_value = 0
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        assert purge_cached_ocr("missing_hash") is False


def test_purge_cached_ocr_no_client():
    with patch("server.cache.get_redis_client", return_value=None):
        assert purge_cached_ocr("any_hash") is False


def test_purge_all_cached_ocr():
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = ["ocr_cache:hash1", "ocr_cache:hash2"]
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        count = purge_all_cached_ocr()
        assert count == 2
        mock_redis.delete.assert_called_once_with("ocr_cache:hash1", "ocr_cache:hash2")


def test_purge_all_cached_ocr_empty():
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = []
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        count = purge_all_cached_ocr()
        assert count == 0
        mock_redis.delete.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cache_purge.py -v`
Expected: FAIL (ImportError: cannot import name 'purge_cached_ocr')

- [ ] **Step 3: Implement purge functions in `server/cache.py`**

Add to `server/cache.py`:
```python
def purge_cached_ocr(file_hash: str) -> bool:
    """Delete a specific OCR cache key by file hash."""
    client = get_redis_client()
    if not client or not file_hash:
        return False
    try:
        deleted = client.delete(f"ocr_cache:{file_hash}")
        if deleted > 0:
            logger.info(f"Purged OCR cache for hash {file_hash[:12]}...")
            return True
    except Exception as e:
        logger.warning(f"Error purging Redis key ocr_cache:{file_hash}: {e}")
    return False


def purge_all_cached_ocr() -> int:
    """Safely delete all OCR cache keys using non-blocking SCAN iteration."""
    client = get_redis_client()
    if not client:
        return 0
    total_deleted = 0
    try:
        keys_batch = []
        for key in client.scan_iter(match="ocr_cache:*", count=100):
            keys_batch.append(key)
            if len(keys_batch) >= 100:
                client.delete(*keys_batch)
                total_deleted += len(keys_batch)
                keys_batch = []
        if keys_batch:
            client.delete(*keys_batch)
            total_deleted += len(keys_batch)
        logger.info(f"Purged {total_deleted} OCR cache keys from Redis.")
    except Exception as e:
        logger.warning(f"Error purging all OCR cache keys: {e}")
    return total_deleted
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cache_purge.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/cache.py tests/test_cache_purge.py
git commit -m "feat(cache): add targeted and bulk redis ocr cache purge methods"
```

---

### Task 2: Admin Purge API Endpoints (`server/routers/admin.py`)

**Files:**
- Modify: `server/routers/admin.py`
- Create: `tests/test_admin_purge.py`

**Interfaces:**
- Consumes:
  - `server.core.dependencies.require_admin`, `server.core.dependencies.get_client_ip`
  - `server.cache.purge_cached_ocr`, `server.cache.purge_all_cached_ocr`, `server.cache.compute_file_hash`
  - `server.db.get_job`, `server.db.log_audit`
  - `server.storage.storage`
- Produces:
  - `POST /api/admin/cache/purge-all`
  - `POST /api/admin/cache/purge/{job_id}`

- [ ] **Step 1: Write test for admin purge endpoints**

Create `tests/test_admin_purge.py`:
```python
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_purge_all_forbidden_for_user():
    user_token_payload = {"username": "officer1", "role": "user"}
    with patch("server.core.dependencies.verify_token", return_value=user_token_payload):
        res = client.post(
            "/api/admin/cache/purge-all",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 403


def test_purge_all_success_for_admin():
    admin_token_payload = {"username": "admin", "role": "admin"}
    with patch("server.core.dependencies.verify_token", return_value=admin_token_payload), \
         patch("server.routers.admin.purge_all_cached_ocr", return_value=5):
        res = client.post(
            "/api/admin/cache/purge-all",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["purged_count"] == 5


def test_purge_task_success_for_admin():
    admin_token_payload = {"username": "admin", "role": "admin"}
    fake_job = {
        "id": "job123",
        "filename": "test.pdf",
        "s3_input_key": "inputs/job123/test.pdf"
    }
    with patch("server.core.dependencies.verify_token", return_value=admin_token_payload), \
         patch("server.routers.admin.get_job", return_value=fake_job), \
         patch("server.routers.admin.storage.get_object", return_value=b"dummy_bytes"), \
         patch("server.routers.admin.compute_file_hash", return_value="hash123"), \
         patch("server.routers.admin.purge_cached_ocr", return_value=True):
        res = client.post(
            "/api/admin/cache/purge/job123",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["job_id"] == "job123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_purge.py -v`
Expected: FAIL (404 Not Found on endpoint)

- [ ] **Step 3: Implement purge endpoints in `server/routers/admin.py`**

In `server/routers/admin.py`, add endpoints:
```python
from server.cache import purge_all_cached_ocr, purge_cached_ocr, compute_file_hash
from server.storage import storage
from server.core.dependencies import get_client_ip


@router.post("/cache/purge-all")
async def purge_all_cache_endpoint(
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Purge all OCR result cache keys from Redis."""
    ip = get_client_ip(request)
    purged_count = purge_all_cached_ocr()
    log_audit("PURGE_ALL_CACHE", admin["username"], ip, f"Purged {purged_count} OCR cache keys")
    return {
        "status": "success",
        "purged_count": purged_count,
        "message": f"ล้างแคช OCR ทั้งหมดในระบบเรียบร้อยแล้ว ({purged_count} รายการ)"
    }


@router.post("/cache/purge/{job_id}")
async def purge_job_cache_endpoint(
    job_id: str,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Purge OCR cache for a specific completed job."""
    ip = get_client_ip(request)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    file_bytes = None
    if job.get("s3_input_key"):
        file_bytes = storage.get_object(job["s3_input_key"])

    if not file_bytes:
        raise HTTPException(status_code=400, detail="ไม่พบไฟล์ต้นฉบับสำหรับคำนวณแฮชแคช")

    file_hash = compute_file_hash(file_bytes)
    deleted = purge_cached_ocr(file_hash)

    log_audit("PURGE_JOB_CACHE", admin["username"], ip, f"Purged cache for job {job_id} ({file_hash[:8]}...) - found={deleted}")
    return {
        "status": "success",
        "job_id": job_id,
        "file_hash": file_hash,
        "found": deleted,
        "message": "ล้างแคชสำหรับเอกสารนี้เรียบร้อยแล้ว" if deleted else "ไม่พบรายการแคชที่ค้างอยู่ในระบบ (อาจหมดอายุแล้ว)"
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_purge.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/routers/admin.py tests/test_admin_purge.py
git commit -m "feat(admin): add endpoints for task and bulk redis cache purge"
```

---

### Task 3: Frontend UI Integration (`frontend/src/App.jsx`)

**Files:**
- Modify: `frontend/src/App.jsx`
- Test: `npm --prefix frontend run build`

- [ ] **Step 1: Add handler functions in `frontend/src/App.jsx`**

Add functions `handlePurgeJobCache(job)` and `handlePurgeAllCache()`:
```javascript
const handlePurgeJobCache = async (job) => {
  if (!confirm(`คุณต้องการล้างแคช Redis สำหรับเอกสาร '${job.filename}' ใช่หรือไม่?\nการประมวลผลไฟล์นี้ในครั้งถัดไปจะส่งไปคำนวณใหม่โดยตรง`)) return
  try {
    const res = await fetch(`/api/admin/cache/purge/${job.id}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    if (res.ok) {
      alert(data.message || 'ล้างแคชเรียบร้อยแล้ว')
    } else {
      alert(data.detail || 'ไม่สามารถล้างแคชได้')
    }
  } catch (err) {
    alert(`ข้อผิดพลาด: ${err.message}`)
  }
}

const handlePurgeAllCache = async () => {
  if (!confirm('คำเตือน: คุณต้องการล้างแคช OCR ทั้งหมดใน Redis ใช่หรือไม่?\nเอกสารที่มีการอัปโหลดซ้ำจะต้องประมวลผลใหม่ทั้งหมด')) return
  try {
    const res = await fetch('/api/admin/cache/purge-all', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    if (res.ok) {
      alert(data.message || 'ล้างแคชทั้งหมดเรียบร้อยแล้ว')
    } else {
      alert(data.detail || 'ไม่สามารถล้างแคชได้')
    }
  } catch (err) {
    alert(`ข้อผิดพลาด: ${err.message}`)
  }
}
```

- [ ] **Step 2: Add Per-Task Purge Button in History Table**

In `recentJobs.map((job) => ...)` inside History table, for completed tasks, if `currentUser?.role === 'admin'`:
```jsx
{currentUser?.role === 'admin' && (
  <button
    onClick={() => handlePurgeJobCache(job)}
    className="px-2 py-1 rounded bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 text-[11px] font-medium inline-flex items-center gap-1 cursor-pointer transition"
    title="ล้างแคช Redis ของเอกสารนี้ (บังคับคำนวณใหม่หากอัปโหลดซ้ำ)"
  >
    <ZapOff className="w-3 h-3" />
    <span>ล้างแคช</span>
  </button>
)}
```

- [ ] **Step 3: Add Purge All Cache Button in Admin Dashboard Modal**

Inside the Admin modal, add a section/card for Cache Management:
```jsx
<div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center justify-between">
  <div>
    <h4 className="font-semibold text-slate-800 text-sm flex items-center gap-1.5">
      <Zap className="w-4 h-4 text-amber-600" />
      <span>การจัดการ OCR Cache (Redis)</span>
    </h4>
    <p className="text-xs text-slate-500 mt-0.5">
      ล้างแคชผลลัพธ์ OCR ทั้งหมดในหน่วยความจำ Redis เพื่อบังคับให้คำนวณใหม่
    </p>
  </div>
  <button
    type="button"
    onClick={handlePurgeAllCache}
    className="px-3.5 py-2 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-medium cursor-pointer transition inline-flex items-center gap-1.5"
  >
    <ZapOff className="w-3.5 h-3.5" />
    <span>ล้างแคช OCR ทั้งหมด</span>
  </button>
</div>
```

- [ ] **Step 4: Verify Frontend Build**

Run: `npm --prefix frontend run build`
Expected: Build succeeds without syntax or JSX errors.

- [ ] **Step 5: Run Full Test Suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 6: Commit changes**

```bash
git add frontend/src/App.jsx
git commit -m "feat(ui): add per-task and bulk redis cache purge buttons for admin"
```

---

## Plan Self-Review Verification

1. **Spec coverage:** Covered both single-job purge (`POST /api/admin/cache/purge/{job_id}`) and bulk purge (`POST /api/admin/cache/purge-all`) and UI placements.
2. **Placeholder scan:** No placeholders or vague TODOs.
3. **Type consistency:** Matches parameters and return formats across layers.
