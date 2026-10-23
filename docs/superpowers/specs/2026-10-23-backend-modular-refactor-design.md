# Design Spec: Modular Backend Refactor & Hybrid Processing Architecture

- **Date:** 2026-10-23
- **Status:** Approved
- **Scope:** Refactoring `server/` Backend API into modular layers without adding external dependencies.

---

## 1. Background & Motivation

ไฟล์ `server/main.py` ปัจจุบันมีขนาด 1,088 บรรทัด ทำหน้าที่หลายอย่างพร้อมกัน (God File):
1. ควบคุม HTTP Endpoints ทั้งหมด (Auth, OCR Jobs, Admin, Metrics, Export, Files)
2. จัดการ Business Logic และการเรียงลำดับคำขอ OCR (Validation, Storage, Worker call, DB updates)
3. กำหนดค่าตัวแปรระบบ (`os.getenv`) กระจัดกระจาย
4. ควบคุม Middleware (CORS, Security Headers, Rate Limiter) และ Dependency Injection

**เป้าหมาย:**
- แยกความรับผิดชอบ (Separation of Concerns) ให้ชัดเจน
- ทำให้โค้ดสะอาด อ่านง่าย และสะดวกต่อการเพิ่มฟังก์ชันในอนาคต
- รองรับการประมวลผลทั้งแบบทันที (Fast Path) และแบบเบื้องหลัง (Background Path)
- คงความเข้ากันได้ 100% กับ Frontend, Nginx Gateway, และ Docker Autoscaler (Zero Breaking Changes)
- ไม่เพิ่มไลบรารีภายนอกที่ไม่จำเป็น (YAGNI / Zero Extra Bloat)

---

## 2. Target Architecture & Directory Layout

จัดระเบียบ `server/` ให้อยู่ในโครงสร้างแบบ Modular Router-Service-Core:

```text
server/
├── core/                       # การตั้งค่าและความปลอดภัยแกนกลาง
│   ├── __init__.py
│   ├── config.py               # รวบรวม Environment Variables และ System Constants ทั้งหมด
│   ├── security.py             # Security Headers Middleware, RateLimiter, File Safety
│   └── dependencies.py         # FastAPI Depends: get_current_user, require_admin, verify_api_key
│
├── routers/                    # API Endpoints (Thin Controllers)
│   ├── __init__.py
│   ├── auth.py                 # /api/auth/login, /api/auth/verify, /api/auth/me
│   ├── ocr.py                  # /api/ocr/upload, /api/ocr/stream, /api/ocr/jobs, /api/ocr/jobs/{id}, /api/ocr/file/*
│   ├── export.py               # /api/ocr/export/docx, /api/ocr/export/xlsx
│   ├── admin.py                # /api/admin/ldap, /api/admin/users, /api/admin/api-keys, /api/admin/metrics, /api/admin/audit-logs
│   └── system.py               # /health, /api/engine/logs, /api/system/info
│
├── services/                   # Business Logic ไม่ผูกติดกับ HTTP Context
│   ├── __init__.py
│   ├── job_service.py          # ตรวจสอบไฟล์, บันทึกสถานะ, จัดการคิวงาน OCR
│   ├── cleanup_service.py      # นโยบายลบไฟล์และ Job หมดอายุ (Data Retention 3-7 วัน)
│   └── export_service.py       # จัดเตรียมข้อมูลส่งออก Docx, Xlsx
│
├── main.py                     # Entry point (~60-80 บรรทัด): Setup FastAPI, Middleware, include_router
├── db.py                       # Data Access Layer (คงเดิม)
├── cache.py                    # Redis Cache & Download Tickets (คงเดิม)
├── storage.py                  # Garage S3 & Local Storage Adapter (คงเดิม)
└── ocr_service.py              # Worker HTTP Client (คงเดิม)
```

---

## 3. Detailed Component Design

### 3.1 `server/core/config.py`
รวบรวมตัวแปรสภาพแวดล้อมทั้งหมดพร้อม Type Annotations และ Safe Defaults:
- `PROJECT_NAME`: "ThaiOCR ONNX API"
- `ENABLE_API_DOCS`: ค่า boolean (Default: `False`)
- `ALLOWED_ORIGINS`: รายการ Origin สำหรับ CORS
- `OCR_WORKER_URL`: URL ของ OCR Worker (Default: `http://thai-ocr-gateway:8001`)
- `REDIS_URL`: URL ของ Redis (Default: `redis://redis:6379/0`)
- `RETENTION_DAYS`: อายุเก็บรักษาเอกสาร (Default: 3 วัน)
- `S3_*`: ข้อมูลการเชื่อมต่อ Garage S3
- `ADMIN_USER`, `ADMIN_PASSWORD`, `APP_SECRET_KEY`: คีย์ความปลอดภัย

### 3.2 `server/core/dependencies.py`
แยก Dependency Functions ออกจาก Endpoint Handlers:
- `get_current_user`: ตรวจสอบ Bearer Token (JWT) และรองรับ API Key Fallback
- `require_admin`: กรองสิทธิ์ผู้ดูแลระบบ (`role == 'admin'`)
- `get_optional_user`: ดึง User หากมี Token ส่งมา (สำหรับ Endpoint ที่เปิดสาธารณะบางส่วน)

### 3.3 `server/services/job_service.py`
รวมกระบวนการประมวลผลเอกสาร:
- `handle_upload(file, user, background_tasks)`:
  1. ตรวจสอบความปลอดภัยไฟล์ (`validate_file_safety`)
  2. คำนวณ SHA-256 และค้นหาผลลัพธ์จากแคช (`get_cached_ocr`)
  3. จัดเก็บไฟล์ต้นฉบับลง Garage S3/Local (`storage.put_object`)
  4. สร้างบันทึก Job ใน SQLite ด้วยสถานะ `'processing'` (`create_job`)
  5. หากเป็นภาพเดี่ยวหรือพบในแคช: ทำการประมวลผลทันที คืนผลลัพธ์แบบ Synchronous
  6. หากเป็น PDF หลายหน้า: ยิงเข้า `background_tasks.add_task` ทำงานเบื้องหลัง และคืนสถานะพร้อม `job_id` ทันที

### 3.4 `server/services/cleanup_service.py`
แยกฟังก์ชัน Retention Policy:
- `purge_expired_data(max_age_days: int)`: ลบไฟล์ต้นฉบับ, ไฟล์ text/markdown ใน S3 และลบ record ออกจาก DB
- เรียกใช้งานใน Background Task และตอนเริ่มต้นระบบ (Lifespan Startup)

### 3.5 `server/routers/*`
แต่ละ Router ทำหน้าที่เป็น Thin Controller:
- รับ Request และตรวจสอบ Parameter ด้วย Pydantic
- เรียกใช้ Service หรือ Data Access Layer
- คืนค่า Response ตามรูปแบบ API เดิม (100% Compatibility)

---

## 4. Error Handling & Standards

1. **Standardized Response:** รักษา Schema ของ Response เดิม เพื่อไม่ให้กระทบ Frontend
2. **Global Exception Handling:** จัดการดักจับข้อผิดพลาดที่ไม่คาดคิด บันทึกลง Logging และคืนข้อความที่ปลอดภัย ป้องกันการรั่วไหลของ Internal Stack Trace
3. **RFC 5987 / RFC 6266:** คงฟังก์ชัน `format_content_disposition` สำหรับดาวน์โหลดไฟล์ภาษาไทย

---

## 5. Verification & Testing Strategy

1. **Import & Syntax Verification:** ตรวจสอบความถูกต้องของโมดูลทั้งหมด (`python -m py_compile`)
2. **API Endpoint Smoke Test:**
   - ทดสอบ `/health`
   - ทดสอบ `/api/auth/login` และการขอ Token
   - ทดสอบ `/api/ocr/jobs`
   - ทดสอบ `/api/admin/metrics` (ตรวจสิทธิ์ Admin)
3. **OCR Processing Integrity:** ทดสอบ Upload ภาพตัวอย่าง และตรวจสอบว่าผลลัพธ์บันทึกลง Database และ Storage ครบถ้วน
