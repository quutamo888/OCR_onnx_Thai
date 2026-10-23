# Phase 2: Super Admin Passkey (WebAuthn) & 2FA (TOTP) Design Spec

**Date:** 2026-10-23
**Status:** Proposed for Review

## 1. Objective
Add optional Two-Factor Authentication (RFC 6238 TOTP) and Passkey (WebAuthn / FIDO2) authentication exclusively for the Super Admin account (`ADMIN_USER`), controllable via independent on/off toggles in the Admin Governance Settings UI.

When Passkey is enabled (`passkey_enabled = 1`), the Super Admin can:
1. Log in directly from the login screen in one click (**Passwordless Passkey Login**).
2. Complete the second factor step using a Passkey instead of typing a 6-digit TOTP code after password login.

When 2FA is enabled (`totp_enabled = 1`), password login for the Super Admin returns a short-lived challenge token (`mfa_token`, 5-minute expiry) requiring either a valid 6-digit TOTP code or a registered Passkey assertion before issuing the full session JWT.

## 2. Architecture & Data Model (`server/db.py`)

### 2.1 `admin_security_settings` Table (Singleton row `id = 1`)
| Column | Type | Default | Description |
|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY CHECK (id = 1)` | `1` | Singleton row |
| `totp_enabled` | `INTEGER` | `0` | `1` if TOTP 2FA is active on Super Admin login |
| `totp_secret` | `TEXT` | `""` | Base32 RFC 6238 secret (160-bit / 32 chars) |
| `passkey_enabled` | `INTEGER` | `0` | `1` if WebAuthn Passkey login & 2FA are active |
| `updated_at` | `REAL` | `time.time()` | Last modified timestamp |

### 2.2 `admin_passkeys` Table
| Column | Type | Description |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | Credential ID (base64url encoded) |
| `name` | `TEXT NOT NULL` | Friendly device label (e.g., `"Windows Hello - Admin PC"`) |
| `public_key` | `TEXT NOT NULL` | SPKI / COSE public key or attestation data (base64url) |
| `sign_count` | `INTEGER DEFAULT 0` | Signature counter for clone detection |
| `created_at` | `REAL NOT NULL` | Registration timestamp |
| `last_used_at` | `REAL` | Last successful authentication timestamp |

## 3. Cryptographic & Protocol Design (`server/auth.py`)

### 3.1 RFC 6238 TOTP (Pure Python `stdlib`)
- Uses `hmac`, `hashlib.sha1`, `struct`, `base64`, `secrets`, `time` (30-second time step, 6 digits, `±1` window tolerance for clock drift).
- Generates `otpauth://totp/ThaiOCR%20ONNX:admin?secret=<BASE32>&issuer=ThaiOCR%20ONNX` URI for QR code rendering in the browser.
- **Anti-Lockout Guard**: Enabling `totp_enabled = 1` requires verifying a live 6-digit code against the configured `totp_secret` first.

### 3.2 WebAuthn Passkey Flow
- **Challenge Generation**: Signed stateless challenge token (`generate_token({"type": "webauthn_challenge", "nonce": ..., "username": ADMIN_USER}, expires_in_seconds=300)`) so challenges work across workers without sticky memory.
- **Registration (`navigator.credentials.create`)**:
  - Client requests registration options from `POST /api/admin/security/passkeys/register-options`.
  - Browser creates credential with `pubKeyCredParams: [{alg: -7, type: "public-key"}, {alg: -257, type: "public-key"}]`.
  - Client sends `credential_id`, `client_data_json`, `attestation_object`, `public_key` (exported via `response.getPublicKey()` when supported), and `name` to `POST /api/admin/security/passkeys/register-verify`.
  - Server verifies challenge nonce, `type == "webauthn.create"`, origin, and stores the Passkey in `admin_passkeys`.
- **Authentication (`navigator.credentials.get`)**:
  - Client requests assertion options from `POST /api/auth/passkey/login-options` (returns challenge + registered `allowCredentials` IDs if `passkey_enabled == 1`).
  - Client sends assertion (`credential_id`, `client_data_json`, `authenticator_data`, `signature`, `challenge_token`) to `POST /api/auth/passkey/login-verify`.
  - Server verifies challenge token signature/expiry, `type == "webauthn.get"`, origin, RP ID hash (`sha256(rp_id)` in `authenticatorData[:32]`), User Present flag (`authenticatorData[32] & 0x01`), and matching active `credential_id` in `admin_passkeys` (plus ECDSA P-256 / RS256 signature verification when `cryptography` is available, with challenge+origin+RP-hash+credential-binding fallback marked with `# ponytail:`).
- **Anti-Lockout Guard**: Enabling `passkey_enabled = 1` requires at least 1 registered Passkey in `admin_passkeys`.

## 4. API Endpoints

### 4.1 Public / Login Auth Endpoints (`server/routers/auth.py`)
- `GET /api/auth/security-options` — Returns `{"passkey_enabled": bool}` so the Login Modal knows whether to render the **"เข้าสู่ระบบด้วย Passkey"** button.
- `POST /api/auth/login` —
  - For regular/LDAP users: unchanged.
  - For Super Admin (`admin`): after valid password, checks `get_admin_security_settings()`.
  - If `totp_enabled == 1`: returns `{"requires_2fa": True, "mfa_token": "<5-min signed token>", "methods": ["totp", ...("passkey" if passkey_enabled and has_passkeys else [])]}` instead of final `token`.
- `POST /api/auth/verify-2fa` — Accepts `{"mfa_token": str, "code": str}`, verifies `mfa_token` (`type == "mfa_pending"`) and 6-digit TOTP code, logs `LOGIN_2FA_SUCCESS`, and returns `{"token": jwt, "user": user_info}`.
- `POST /api/auth/passkey/login-options` — Returns WebAuthn challenge + `allowCredentials` list when `passkey_enabled == 1`.
- `POST /api/auth/passkey/login-verify` — Verifies WebAuthn assertion (works both for 1-click Passwordless login from Login screen and for completing a pending 2FA step), logs `LOGIN_PASSKEY_SUCCESS`, and returns `{"token": jwt, "user": user_info}`.

### 4.2 Super Admin Settings Endpoints (`server/routers/admin.py`)
- `GET /api/admin/security-settings` — Returns `totp_enabled`, `has_totp_secret`, `passkey_enabled`, and `passkeys` list.
- `POST /api/admin/security/totp/setup` — Generates a fresh Base32 secret and `otpauth_uri` for QR setup.
- `POST /api/admin/security/totp/verify-and-enable` — Verifies a 6-digit OTP code and sets `totp_enabled = 1`.
- `PUT /api/admin/security/settings` — Toggles `totp_enabled` / `passkey_enabled` on or off (enforcing anti-lockout guards).
- `POST /api/admin/security/passkeys/register-options` — Issues WebAuthn creation options for Super Admin.
- `POST /api/admin/security/passkeys/register-verify` — Saves new Passkey credential and logs `REGISTER_PASSKEY`.
- `DELETE /api/admin/security/passkeys/{cred_id}` — Deletes a Passkey (auto-disables `passkey_enabled` if the last Passkey is removed).

## 5. Frontend UI (`frontend/src/App.jsx`)
1. **Admin Governance Page**:
   - New tab: **`ความปลอดภัย (Passkey & 2FA)`**.
   - **Card 1: 2FA (TOTP Authenticator)** — Toggle switch (On/Off), "ตั้งค่า QR Code ใหม่" button, inline QR code + Base32 secret copy + 6-digit confirmation input.
   - **Card 2: Passkey (WebAuthn / FIDO2)** — Toggle switch (On/Off), device name input + "ลงทะเบียน Passkey บนอุปกรณ์นี้" button, and table of registered Passkeys with delete button.
2. **Login Modal**:
   - When `passkey_enabled` is true, displays a **"เข้าสู่ระบบด้วย Passkey (ไม่ต้องใช้รหัสผ่าน)"** button on the primary login form.
   - When password login returns `requires_2fa: true`, transitions the modal to the **2FA Verification Step**: 6-digit OTP input + (if `passkey_enabled` is also active) a button to verify via Passkey instead.

## 6. Testing Strategy
- Unit tests for TOTP generation, verification (`±1` time window), and invalid code rejection.
- Unit & integration tests for Super Admin login when `totp_enabled=0` vs `totp_enabled=1` (`requires_2fa` challenge flow -> `/api/auth/verify-2fa`).
- Unit & integration tests for Passkey registration, toggle anti-lockout guards, 1-click Passkey login, and Passkey deletion auto-disabling `passkey_enabled`.
