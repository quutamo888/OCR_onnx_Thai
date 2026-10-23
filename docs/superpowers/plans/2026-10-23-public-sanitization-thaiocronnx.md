# thaiOCRonnx Public Sanitization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all occurrences of legacy agency names, domains, and related credentials across the codebase, rebuild frontend artifacts, verify zero leaks with automated tests, and initialize a clean git repository for `https://github.com/quutamo888/thaiOCRonnx.git`.

**Architecture:** Systematic file-by-file string and credential sanitization across backend, frontend, worker, configurations, docs, and tests, followed by dist rebuilding, leak verification via grep, pytest suite execution, and fresh git initialization.

**Tech Stack:** Python (FastAPI, Pytest), React (Vite), Rust, Docker Compose, Git.

## Global Constraints
- Target clean generic name: `ThaiOCR ONNX` (`thaiOCRonnx`)
- Default admin password: `Admin@Ocr2026!`
- Default app secret key: `thai-ocr-default-secret-key-2026`
- API Key Prefix: `ocr_sk_live_...`
- Session cookie/storage: `ocr_session_token`, `thai_ocr_token`
- Absolutely 0 matches for case-insensitive legacy agency keywords in active files before git init.

---

### Task 1: Backend Code Sanitization

**Files:**
- Modify: `server/core/config.py`
- Modify: `server/core/dependencies.py`
- Modify: `server/auth.py`
- Modify: `server/db.py`
- Modify: `server/exporter.py`
- Modify: `server/logger.py`
- Modify: `server/main.py`
- Modify: `server/ocr_service.py`
- Modify: `server/routers/__init__.py`
- Modify: `server/routers/admin.py`
- Modify: `server/security.py`
- Modify: `server/storage.py`

- [ ] **Step 1: Replace legacy references in server/core/config.py and server/core/dependencies.py**
  Replace old project name with `ThaiOCR ONNX API`, legacy worker gateway URL with `http://thai-ocr-gateway:8001`, old password with `Admin@Ocr2026!`, old secret key with `thai-ocr-default-secret-key-2026`.
  In `dependencies.py`, replace legacy session token cookie with `ocr_session_token` and legacy key prefix with `ocr_sk_`.

- [ ] **Step 2: Replace legacy references in server/auth.py, server/db.py, server/storage.py, server/main.py, server/logger.py**
  Replace default admin password, secret key, issuer names (`ThaiOCR ONNX`), LDAP defaults (`ad.example.com`), DB path (`ocr_engine.db`), S3 bucket (`ocr-documents`), and Server response header (`ThaiOCR-Security-Gateway`).
  In `server/db.py`, replace legacy key prefix with `ocr_sk_live_` and legacy salt with `thai_ocr_user_salt_2026`.

- [ ] **Step 3: Replace legacy references in remaining server routers and modules**
  Sanitize docstrings and comments in `server/routers/admin.py`, `server/routers/__init__.py`, `server/exporter.py`, `server/ocr_service.py`, and `server/security.py`.

---

### Task 2: Worker, Docker & Deployment Scripts Sanitization

**Files:**
- Modify: `rust_worker/Cargo.toml`
- Modify: `rust_worker/Dockerfile`
- Modify: `rust_worker/src/main.rs`
- Modify: `rust_worker/src/engine.rs`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.ubuntu.yml`
- Modify: `Dockerfile`
- Modify: `nginx/nginx.conf`
- Modify: `autoscaler/autoscaler.py`
- Modify: `ocr_worker.py`
- Modify: `scripts/deploy_windows_worker.ps1`
- Modify: `scripts/setup_firewall_permit_ip.bat`
- Modify: `scripts/generate_tls_certs.py`
- Modify: `scripts/generate_mtls_certs.py`
- Modify: `oem/install.bat`
- Modify: `oem/run_ocr_worker.bat`
- Modify: `run_worker.bat`
- Modify: `setup-ubuntu.sh`

- [ ] **Step 1: Sanitize rust_worker**
  In `rust_worker/Cargo.toml`, change name to `thai_rust_ocr`.
  In `rust_worker/src/main.rs` and `engine.rs`, update banner and ort env name to `thai_ocr`.
  In `rust_worker/Dockerfile`, update target binary path to `thai_rust_ocr`.

- [ ] **Step 2: Sanitize docker-compose files and nginx**
  In `docker-compose.yml` and `docker-compose.ubuntu.yml`:
  Rename containers `legacy-ocr-*` to `thai-ocr-*`.
  Update environment variables and DB paths (`/app/data/ocr_engine.db`).
  In `nginx/nginx.conf`, change upstream to `thai-ocr-app:8000`.

- [ ] **Step 3: Sanitize scripts and batch files**
  Replace all legacy organization strings in `scripts/`, `oem/`, and root `.bat` / `.sh` files with `ThaiOCR`.
  In `scripts/generate_tls_certs.py` and `scripts/generate_mtls_certs.py`, replace organization names and common names.

---

### Task 3: Frontend Code Sanitization & Rebuild

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/index.html`
- Modify: `frontend/src/App.jsx`
- Rebuild: `frontend/dist/`

- [ ] **Step 1: Sanitize frontend source files**
  In `frontend/package.json`, rename legacy package name to `thai-ocr-web`.
  In `frontend/index.html`, change title to `ThaiOCR ONNX Web Portal`.
  In `frontend/src/App.jsx`, replace:
  - `localStorage` key `legacy_ocr_token` -> `thai_ocr_token`
  - default login password `legacy@Admin2026` -> `Admin@Ocr2026!`
  - WebAuthn RP name `Legacy OneOCR Security` -> `ThaiOCR ONNX Security`
  - Legacy Thai agency strings -> "ThaiOCR ONNX Portal"
  - Header / titles / footer texts
  - API documentation examples (`legacy_sk_live_...` -> `ocr_sk_live_...`)

- [ ] **Step 2: Build frontend distribution**
  Run `npm run build` inside `frontend/` to produce clean bundles in `frontend/dist/`.

---

### Task 4: Tests, Config & Documentation Sanitization

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `GLOSSARY.md`
- Modify: `tests/test_core.py`
- Modify: `tests/test_dependencies.py`
- Modify: `tests/test_main_integration.py`
- Modify: `tests/test_routers.py`
- Clean/Delete: Obsolete internal entity spec docs under `docs/superpowers/`

- [ ] **Step 1: Sanitize .env.example, README.md, GLOSSARY.md**
  Replace all legacy references, LDAP configs, S3 bucket names, and passwords.

- [ ] **Step 2: Sanitize tests**
  Update tests in `tests/test_core.py`, `tests/test_dependencies.py`, `tests/test_main_integration.py`, and `tests/test_routers.py` to match new default admin passwords, headers, project names, cookies, and tokens.

- [ ] **Step 3: Clean obsolete docs**
  Remove or sanitize any past docs that specifically name legacy internal entities.

- [ ] **Step 4: Run pytest test suite**
  Execute `pytest tests/` to verify all tests pass.

---

### Task 5: Zero-Leak Verification & Fresh Git Repo Initialization

- [ ] **Step 1: Verify 0 occurrences of legacy agency keywords**
  Run ripgrep / grep across the entire codebase excluding `.git` to guarantee 0 matches.

- [ ] **Step 2: Initialize fresh Git repository**
  Remove `.git` directory.
  Run:
  ```bash
  git init
  git add .
  git commit -m "feat: initial public release of thaiOCRonnx"
  git branch -M main
  git remote add origin https://github.com/quutamo888/thaiOCRonnx.git
  ```

- [ ] **Step 3: Verify git status and log**
  Confirm single clean commit with remote set to `https://github.com/quutamo888/thaiOCRonnx.git`.
