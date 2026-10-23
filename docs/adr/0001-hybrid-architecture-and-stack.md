# ADR 0001: สถาปัตยกรรมระบบ Web OCR ThaiOCR ONNX

## สถานะ
อนุมัติแล้ว (Approved)

## บริบท (Context)
ระบบต้องการให้บริการแปลงข้อความจากภาพและ PDF สแกน (OneOCR) ผ่าน Web โดยมีข้อกำหนด:
1. OneOCR ใช้โมเดลและ DLL เฉพาะของ Windows x64 (`oneocr.dll`, `onnxruntime.dll`) หรือ Rust Native บน Linux ประมวลผลบน CPU ล้วน ทำงานแบบ Offline 100%
2. รองรับผู้ใช้งานระบบและ Active Directory / LDAP พร้อมหน้า Admin จัดการและจำกัดสิทธิ์
3. จัดเก็บเอกสารและผลลัพธ์ผ่าน Garage Object Storage (S3-compatible)
4. มีหน้าจอแดชบอร์ดตรวจสอบ Latency, Error, และปริมาณงาน
5. รองรับการแพ็กเกจด้วย Docker

## การตัดสินใจ (Decision)
1. **สถาปัตยกรรมระบบ (Architecture):**
   - **Backend:** FastAPI (Python 3.11) ทำหน้าที่เป็น API Gateway, Authentication (LDAP), Job Queue, และ Proxy
   - **OCR Worker:** รันแยกส่วน รองรับทั้ง Rust Native บน Linux และ Windows Worker รันโมเดล OneOCR
   - **Database:** SQLite สำหรับเก็บข้อมูลผู้ใช้งาน สิทธิ์ API Keys และประวัติการทำรายการ
   - **Storage:** Garage Object Storage (S3-compatible) ทำงานแบบ On-Premise
   - **Frontend:** Single Page Application (SPA) ด้วย React, Vite, TailwindCSS
2. **การรักษาความปลอดภัย (Security):**
   - มีระบบจำกัดขนาดไฟล์และคัดกรองมัลแวร์เบื้องต้น
   - มีระบบ Rate Limiting ต่อผู้ใช้งานและต่อ IP ป้องกัน DoS
   - ลบไฟล์ชั่วคราวและผลลัพธ์ OCR อัตโนมัติหลังหมดอายุ (Data Retention)
   - หน้า Admin มี Audit Logging สำหรับติดตามการเข้าถึง

## ผลที่ตามมา (Consequences)
- ระบบปลอดภัยสูง เอกสารไม่รั่วไหลออกนอกเครือข่ายภายใน
- สามารถต่อกับ Garage S3 ทั้งแบบ Local Container ใน docker-compose หรือ Production Garage Cluster ภายนอกได้
