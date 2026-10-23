# Design Spec: Admin Redis OCR Cache Purge Feature

- **Date:** 2026-10-23
- **Status:** Approved
- **Scope:** Add targeted per-task and bulk Redis OCR cache purge capabilities for Local Admin users across Backend API and Frontend UI.

---

## 1. Background & Motivation

ระบบ OneOCR มีระบบ In-Memory Redis Cache (`ocr_cache:<file_hash>`) ซึ่งให้ผลลัพธ์ทันที (~45ms) เมื่ออัปโหลดไฟล์ที่มีเนื้อหาและแฮช SHA-256 ซ้ำเดิม

อย่างไรก็ตาม ในกรณีที่:
1. ต้องการบังคับให้เอนจิน OCR คำนวณใหม่จริง (เช่น หลังอัปเดตโมเดลหรือต้องการผลลัพธ์สด)
2. ผู้ดูแลระบบ (Local Admin) ต้องการล้างแคชของเอกสารฉบับใดฉบับหนึ่ง หรือล้างแคชสะสมทั้งหมดเพื่อคืนหน่วยความจำ

ปัจจุบันยังไม่มีปุ่มสั่งล้างแคชผ่านหน้า Web Portal สำหรับผู้ดูแลระบบ

---

## 2. Architectural Design & Boundaries

### 2.1 Backend Layer (`server/`)

1. **`server/cache.py` (Cache Interface Extensions):**
   - `purge_cached_ocr(file_hash: str) -> bool`:
     ลบคีย์ `ocr_cache:{file_hash}` ใน Redis คืนค่า `True` หากพบคีย์และลบสำเร็จ
   - `purge_all_cached_ocr() -> int`:
     ใช้ `client.scan_iter(match="ocr_cache:*", count=100)` เพื่อวนลบทีละ batch อย่างปลอดภัย (Non-blocking / Zero latency spike) และคืนจำนวนคีย์ที่ถูกลบไปทั้งหมด
     *หมายเหตุ:* ไม่ใช้ `FLUSHDB` เพื่อป้องกันการลบตั๋วดาวน์โหลด `ticket:dl:*` ที่กำลังใช้งานอยู่

2. **`server/routers/admin.py` (New Admin Endpoints):**
   - `POST /api/admin/cache/purge-all`:
     - ต้องมีสิทธิ์ Admin (`require_admin`)
     - เรียก `purge_all_cached_ocr()`
     - บันทึก Audit Log (`log_audit("PURGE_ALL_CACHE", admin_user, ip, f"Purged {count} keys")`)
     - คืน JSON: `{"status": "success", "purged_count": count, "message": "ล้างแคช OCR ทั้งหมดเรียบร้อยแล้ว"}`
   - `POST /api/admin/cache/purge/{job_id}`:
     - ต้องมีสิทธิ์ Admin (`require_admin`)
     - ดึง `job = get_job(job_id)`
     - หาก `job` ไม่มี ให้คืน 404
     - อ่านไฟล์ต้นฉบับจาก `storage.get_object(job["s3_input_key"])` เพื่อคำนวณ `file_hash = compute_file_hash(file_bytes)`
     - เรียก `purge_cached_ocr(file_hash)`
     - บันทึก Audit Log (`log_audit("PURGE_TASK_CACHE", admin_user, ip, f"Job {job_id} ({file_hash[:8]})")`)
     - คืน JSON: `{"status": "success", "job_id": job_id, "file_hash": file_hash, "message": "ล้างแคชสำหรับเอกสารนี้เรียบร้อยแล้ว"}`

### 2.2 Frontend UI Layer (`frontend/src/App.jsx`)

1. **History Table (ตารางประวัติงาน):**
   - ในคอลัมน์ "ตรวจดู / จัดการ":
   - เพิ่มปุ่ม **"ล้างแคช"** (ไอคอน `ZapOff` หรือ `RotateCcw`)
   - แสดงเฉพาะเมื่อ `currentUser?.role === 'admin'` และ `job.status === 'completed'`
   - เมื่อกด จะมี confirm popup: *"คุณต้องการล้างแคชของเอกสาร '{filename}' ใช่หรือไม่?"*
   - เมื่อสำเร็จ: แสดง toast/alert แจ้งเตือน และอัปเดตสถานะ

2. **Admin Dashboard Modal (หน้าต่างผู้ดูแลระบบ):**
   - ในแท็บแดชบอร์ด / เมตริก:
   - เพิ่มการ์ด **"การจัดการแคช Redis (OCR Cache)"**
   - แสดงสถานะการเชื่อมต่อ Redis
   - มีปุ่ม **"ล้างแคช OCR ทั้งหมด (Purge All)"**
   - เมื่อกด จะมี confirm popup: *"คุณแน่ใจหรือไม่ที่จะล้างแคช OCR ทั้งหมดในระบบ?"*
   - แจ้งจำนวนรายการแคชที่ถูกล้างออกไป

---

## 3. Security & Resilience

- **Authorization Gating:** ทั้ง 2 endpoints ถูกป้องกันด้วย `require_admin` (HTTP 403 Forbidden สำหรับผู้ใช้ทั่วไป)
- **Rate Limiting:** มีการตรวจสอบผ่าน Security Gateway ป้องกันการกดย้ำถี่ยิบ
- **Audit Logging:** บันทึกประวัติการสั่งล้างแคชทุกครั้งลงตาราง `audit_logs` ใน SQLite (ระบุ IP, username, เวลา, และจำนวนคีย์)
- **Non-blocking Operations:** การล้างแคชทั้งหมดใช้ `scan_iter` ไม่ทำให้ Redis Event Loop สะดุด

---

## 4. Verification & Testing Strategy

1. **Unit Tests (`tests/test_cache_purge.py`):**
   - ทดสอบ `purge_cached_ocr` ทั้งกรณีพบคีย์และไม่พบคีย์
   - ทดสอบ `purge_all_cached_ocr` ด้วย mock redis client ตรวจสอบว่าเรียก `scan_iter` และ `delete` ถูกต้อง
2. **Endpoint Tests (`tests/test_admin_purge.py`):**
   - ทดสอบเรียก `POST /api/admin/cache/purge-all` ด้วยสิทธิ์ผู้ใช้ทั่วไป -> ได้รับ 403 Forbidden
   - ทดสอบเรียก `POST /api/admin/cache/purge-all` ด้วยสิทธิ์ Admin -> ได้รับ 200 OK
   - ทดสอบเรียก `POST /api/admin/cache/purge/{job_id}` ด้วยสิทธิ์ Admin -> ได้รับ 200 OK
3. **Frontend Integration Test:**
   - ทดสอบคลิกปุ่มล้างแคชบน UI และตรวจสอบ Network Request
