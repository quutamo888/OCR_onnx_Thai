# Super Admin Passkey & 2FA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional RFC 6238 TOTP 2FA and WebAuthn Passkey authentication (both 1-click passwordless login and 2nd-factor fallback) for Super Admin, controlled via toggles in Admin Governance Settings.

**Architecture:** Store singleton settings in `admin_security_settings` and Passkey credentials in `admin_passkeys` within SQLite (`server/db.py`). Implement RFC 6238 TOTP and stateless signed WebAuthn challenge verification in `server/auth.py` using pure Python stdlib. Expose login/MFA/Passkey endpoints in `server/routers/auth.py` and management/toggle endpoints in `server/routers/admin.py`, wired to the React UI (`frontend/src/App.jsx`).

**Tech Stack:** Python 3.11+ (stdlib `hmac`, `hashlib`, `struct`, `base64`, `secrets`, `time`), FastAPI, SQLite, React 18 + Tailwind CSS, Browser WebAuthn API (`navigator.credentials`).

## Global Constraints
- Pure Python stdlib for TOTP and challenge signing — no new external pip dependencies required.
- Anti-lockout guard: `totp_enabled` cannot be switched on without a verified `totp_secret`; `passkey_enabled` cannot be switched on unless at least 1 Passkey exists in `admin_passkeys`.
- Deleting the last Passkey automatically resets `passkey_enabled = 0`.

---

### Task 1: Database Schema & TOTP/Passkey Core Helpers (`server/db.py` & `server/auth.py`)

**Files:**
- Modify: `server/db.py`
- Modify: `server/auth.py`
- Test: `tests/test_core.py`

- [x] **Step 1: Write failing tests in `tests/test_core.py` for TOTP generation/verification, security settings, and passkey CRUD**
- [x] **Step 2: Run `python -m pytest tests/test_core.py` to verify failure**
- [x] **Step 3: Implement DB tables (`admin_security_settings`, `admin_passkeys`) in `server/db.py` and TOTP + WebAuthn helpers in `server/auth.py`**
- [x] **Step 4: Run `python -m pytest tests/test_core.py` to verify pass**

### Task 2: Auth & Admin Router Endpoints (`server/routers/auth.py` & `server/routers/admin.py`)

**Files:**
- Modify: `server/routers/auth.py`
- Modify: `server/routers/admin.py`
- Test: `tests/test_routers.py`

- [x] **Step 1: Write failing tests in `tests/test_routers.py` for 2FA login challenge, `/api/auth/verify-2fa`, Passkey login flow, and Admin security settings toggles**
- [x] **Step 2: Run `python -m pytest tests/test_routers.py` to verify failure**
- [x] **Step 3: Implement endpoints in `server/routers/auth.py` and `server/routers/admin.py`**
- [x] **Step 4: Run `python -m pytest` to verify all tests pass**

### Task 3: Frontend Login Modal & Admin Governance Security Tab (`frontend/src/App.jsx`)

**Files:**
- Modify: `frontend/src/App.jsx`

- [x] **Step 1: Add WebAuthn base64url helpers, 1-click Passkey Login button, and 2FA OTP/Passkey step in Login Modal**
- [x] **Step 2: Add `ความปลอดภัย (Passkey & 2FA)` tab in Admin Governance with independent toggles, TOTP QR setup, and Passkey device management**
- [x] **Step 3: Build frontend (`npm run build` in `frontend/`) and verify bundle compiles cleanly**
