# Design Spec: Dedicated Full-Page Admin Governance & Monitor

- **Date:** 2026-10-23
- **Status:** Approved
- **Scope:** Refactor Admin Backend Monitor from a popup modal into a dedicated full-width page view with a Top Navbar switcher and URL hash routing (`#/admin`).

---

## 1. Background & Problem Statement

ปัจจุบันหน้าต่าง **Admin Backend Monitor & Governance** แสดงผลในรูปแบบ Popup Modal ขนาดจำกัด (`max-w-4xl` และ `max-h-[90vh]`):
- มีเนื้อหาครอบคลุมถึง 8 แท็บสำคัญ (System Metrics, User Management, API Keys, API Docs, LDAP Config, System-wide Jobs, Audit Logs, Engine Logs)
- ตารางต่าง ๆ เช่น รายชื่อผู้ใช้, ตาราง API Keys, ประวัติเอกสาร และ Audit Logs มีคอลัมน์จำนวนมาก เมื่ออยู่ใน Modal เล็กทำให้ต้องเลื่อนแถบแนวนอนและแนวตั้งพร้อมกัน อ่านข้อมูลยากและอึดอัด
- ไม่รองรับการ Bookmark URL หรือใช้ปุ่ม Back/Forward ของเบราว์เซอร์

---

## 2. Architectural Design

### 2.1 Navigation & URL Routing
- ใช้ State `currentView`: `'studio'` | `'admin'`
- ซิงก์กับ `window.location.hash`:
  - `#/admin`: เปิดหน้า Admin Governance (ตรวจสอบสิทธิ์ `currentUser?.role === 'admin'`)
  - `#/` หรือ `#/studio`: เปิดหน้า OCR Studio
  - ฟัง Event `hashchange` ใน `useEffect` เพื่อให้การกดปุ่ม Back/Forward ในเบราว์เซอร์ทำงานได้ทันที
- หากผู้ใช้ยังไม่ได้ล็อกอินหรือไม่มีสิทธิ์ Admin แล้วเข้า URL `#/admin`: ระบบจะสลับกลับไปยังหน้า `studio` โดยอัตโนมัติ

### 2.2 Top Navbar Switcher
- ใน Header แถบด้านบน:
  - เพิ่มปุ่มสลับหน้าจอ (Tab Switcher) เด่นชัด:
    - **OCR Studio:** ไอคอน `Layers` / `FileText`
    - **Admin Governance:** ไอคอน `Shield` / `Activity` (แสดงเฉพาะเมื่อล็อกอินเป็น `role === 'admin'`)
  - กดปุ่มสลับจะเปลี่ยน `currentView` และอัปเดต `window.location.hash` ทันที พร้อมโหลดข้อมูล Admin ล่าสุด (`loadAdminData()`)

### 2.3 Full-Page Admin View (`max-w-7xl`)
- เลิกใช้ `showAdminModal` และ Modal Wrapper กึ่งโปร่งใส
- เรนเดอร์เป็น Full-Page Component ภายใน `main`:
  - **Dashboard Header:** ชื่อหน้า, คำอธิบายสั้น, ปุ่มรีเฟรชข้อมูล (`loadAdminData`)
  - **Sub-Tabs:** 8 แท็บขยายเต็มจอ รองรับ Responsive:
    1. ภาพรวม & Latency (รวมการ์ดจัดการ Redis Cache)
    2. ผู้ใช้งานในระบบ (`localUsers`)
    3. จัดการ API Keys (`apiKeys`)
    4. คู่มือเชื่อมต่อ API (`docs`)
    5. ตั้งค่า Active Directory / LDAP (`ldap`)
    6. ประวัติเอกสารทั้งหมดในระบบ (`jobs`)
    7. บันทึก Audit Logs (`audit`)
    8. บันทึกการทำงานระบบ Engine Logs (`logs`)
- ตารางทุกอันได้รับพื้นที่แสดงผลเต็มความกว้าง ไม่ต้องตัดตกหรือเลื่อนแนวนอนซ้อน

---

## 3. Security & Access Control

- สิทธิ์การเข้าถึงหน้า Admin ถูกควบคุมทั้ง 2 ชั้น:
  - **Client-Side:** เช็ค `currentUser?.role === 'admin'` ก่อนเรนเดอร์หน้า Admin View หากไม่มีสิทธิ์จะ fallback ไปหน้า Studio
  - **Server-Side:** ทุก API Endpoint ภายใต้ `/api/admin/*` มี `require_admin` ป้องกันระดับเซิร์ฟเวอร์อย่างเข้มงวด

---

## 4. Testing & Verification

1. **Vite Build Verification:** ทดสอบ `npm --prefix frontend run build` ตรวจสอบความถูกต้องของ JSX / Tailwind และไม่มี Build Error
2. **Pytest Integration Verification:** ทดสอบ `python -m pytest tests/ -v` ยืนยันว่า Backend API และ Endpoint ทั้งหมดทำงานได้ปกติ
3. **Manual Navigation Checks:**
   - สลับระหว่าง Studio และ Admin หน้าจอปรับเปลี่ยนทันที
   - URL hash เปลี่ยนเป็น `#/admin` เมื่ออยู่หน้า Admin
   - เข้าผ่าน URL `#/admin` โดยตรง โหลดหน้า Admin สำเร็จเมื่อมีสิทธิ์
