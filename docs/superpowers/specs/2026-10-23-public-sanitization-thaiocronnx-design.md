# Design Spec: Public Release Sanitization for thaiOCRonnx

## Goal
Sanitize the entire repository to remove all traces of internal entity references, domains, and related default credentials so the project can be safely open-sourced as a generic, public repository on GitHub (`quutamo888/thaiOCRonnx`).

## Scope & Target Identifiers

### 1. Identity & Naming Replacements
- **Project Name:** Previous internal name -> `ThaiOCR ONNX`
- **Docker Containers & Hostnames:**
  - `legacy-ocr-app` -> `thai-ocr-app`
  - `legacy-ocr-gateway` -> `thai-ocr-gateway`
  - `legacy-ocr-redis` -> `thai-ocr-redis`
  - `legacy-ocr-autoscaler` -> `thai-ocr-autoscaler`
  - `legacy-ocr-garage` -> `thai-ocr-garage`
  - `legacy-ocr-web` -> `thai-ocr-web`
- **Rust Worker:**
  - Package name: `legacy_rust_ocr` -> `thai_rust_ocr`
  - Binary & environment name: `legacy_ocr` / `legacy_rust_ocr` -> `thai_ocr` / `thai_rust_ocr`
- **Frontend:**
  - `package.json` name: `legacy-oneocr-web` -> `thai-ocr-web`
  - UI Header, Title, Portal text, Help manuals
- **Database & Storage:**
  - Database name: `legacy_ocr.db` -> `ocr_engine.db`
  - S3 Bucket: `legacy-ocr-documents` -> `ocr-documents`

### 2. Credentials & Security Configurations
- **Admin Password:**
  - Old: `legacy@Admin2026`
  - New: `Admin@Ocr2026!`
- **Secret Key:**
  - Old: `legacy-ocr-secret-key-2026-production`
  - New: `thai-ocr-default-secret-key-2026`
- **Legacy Salt:**
  - Old: `legacy_ocr_user_salt_2026`
  - New: `thai_ocr_user_salt_2026`
- **API Key Format:**
  - Old prefix: `legacy_sk_live_...`
  - New prefix: `ocr_sk_live_...`
- **Session Tokens / Cookies / LocalStorage:**
  - Old: `legacy_token`, `legacy_ocr_token`
  - New: `ocr_session_token`, `thai_ocr_token`
- **LDAP Domain Defaults:**
  - Old: `ad.internal.example.org`, `DC=internal,DC=example,DC=org`, `Internal_OCR_Users`
  - New: `ad.example.com`, `DC=example,DC=com`, `OCR_Users`
- **Certificates & Scripts:**
  - `scripts/generate_tls_certs.py`, `scripts/generate_mtls_certs.py`
  - Change organization to generic `ThaiOCR Organization`

### 3. Frontend Dist & Static Bundles
- Remove stale `frontend/dist/`
- Rebuild via `npm run build` in `frontend/` so bundled assets reflect clean naming.

### 4. Git History Sanitization
- Remove existing `.git` directory to purge all historical commits containing sensitive entity names.
- Initialize fresh git repository:
  ```bash
  git init
  git add .
  git commit -m "feat: initial public release of thaiOCRonnx"
  git branch -M main
  git remote add origin https://github.com/quutamo888/thaiOCRonnx.git
  ```

## Verification Checklist
- [ ] Case-insensitive search for legacy organization keyword across entire project yields 0 matches (excluding `.git` if not wiped yet).
- [ ] Search for legacy Thai agency acronym yields 0 matches.
- [ ] Backend test suite passes (`pytest tests/`).
- [ ] Frontend builds without errors (`npm run build`).
