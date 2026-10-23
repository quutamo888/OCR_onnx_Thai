import React, { useState, useEffect, useRef } from 'react'
import {
  FileText, Upload, CheckCircle2, AlertCircle, Copy, Download,
  Shield, Activity, Settings, User, LogOut, ArrowRight, FileCheck,
  Server, HardDrive, RefreshCw, Layers, Clock, Check,
  ZoomIn, ZoomOut, RotateCcw, Maximize2, Split, Eye, Edit3, Save, X, ExternalLink,
  Trash2, ShieldAlert, AlertTriangle, FileSpreadsheet, Key, BookOpen, Plus, Ban,
  Zap, ZapOff
} from 'lucide-react'

/**
 * Safe Markdown Viewer Component.
 * Parses and renders Markdown syntax (Headings, Tables, Lists, Code, Blockquotes)
 * using pure React virtual DOM without dangerouslySetInnerHTML.
 * Guarantees zero script execution and prevents any code/HTML injection attacks.
 */
function SafeMarkdownViewer({ content }) {
  if (!content) {
    return <div className="text-slate-500 italic p-4 text-xs">ไม่มีเนื้อหา Markdown</div>
  }

  const lines = content.split('\n')
  const elements = []
  let i = 0

  const renderInline = (text) => {
    if (!text) return ''
    const parts = []
    let lastIdx = 0
    const inlineRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
    let match

    while ((match = inlineRegex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        parts.push(text.substring(lastIdx, match.index))
      }
      const m = match[0]
      if (m.startsWith('**') && m.endsWith('**')) {
        parts.push(<strong key={match.index} className="font-semibold text-slate-100">{m.slice(2, -2)}</strong>)
      } else if (m.startsWith('*') && m.endsWith('*')) {
        parts.push(<em key={match.index} className="italic text-slate-300">{m.slice(1, -1)}</em>)
      } else if (m.startsWith('`') && m.endsWith('`')) {
        parts.push(
          <code key={match.index} className="bg-slate-800 text-amber-300 px-1 py-0.5 rounded font-mono text-[11px] border border-slate-700/60">
            {m.slice(1, -1)}
          </code>
        )
      }
      lastIdx = inlineRegex.lastIndex
    }
    if (lastIdx < text.length) {
      parts.push(text.substring(lastIdx))
    }
    return parts.length > 0 ? parts : text
  }

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // 1. Code blocks: ```
    if (trimmed.startsWith('```')) {
      const lang = trimmed.slice(3).trim()
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // Skip closing ```
      elements.push(
        <div key={elements.length} className="my-2.5 rounded-lg overflow-hidden border border-slate-800 bg-slate-950">
          {lang && (
            <div className="bg-slate-900 px-3 py-1 text-[10px] font-mono text-slate-400 border-b border-slate-800">
              {lang}
            </div>
          )}
          <pre className="p-3 text-emerald-400 font-mono text-xs overflow-x-auto leading-relaxed whitespace-pre">
            <code>{codeLines.join('\n')}</code>
          </pre>
        </div>
      )
      continue
    }

    // 2. Tables: lines starting and ending with |
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const tableLines = []
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i].trim())
        i++
      }

      if (tableLines.length >= 2) {
        const headerCells = tableLines[0].split('|').slice(1, -1).map(c => c.trim())
        const isSep = tableLines[1].replace(/[\s|:-]/g, '').length === 0
        const rowStartIdx = isSep ? 2 : 1
        const dataRows = tableLines.slice(rowStartIdx).map(tl => tl.split('|').slice(1, -1).map(c => c.trim()))

        elements.push(
          <div key={elements.length} className="my-3 overflow-x-auto rounded-lg border border-slate-700/80 bg-slate-900/80 shadow-md">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-800 text-amber-300 font-semibold border-b border-slate-700">
                  {headerCells.map((h, hIdx) => (
                    <th key={hIdx} className="py-2 px-3 border-r border-slate-700/60 last:border-r-0">
                      {renderInline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {dataRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-800/50 transition">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="py-1.5 px-3 border-r border-slate-800/60 last:border-r-0 text-slate-200 font-mono">
                        {renderInline(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        continue
      }
    }

    // 3. Headings
    if (trimmed.startsWith('# ')) {
      elements.push(
        <h1 key={elements.length} className="text-lg font-bold text-amber-400 mt-4 mb-2 pb-1 border-b border-slate-800">
          {renderInline(trimmed.slice(2))}
        </h1>
      )
      i++
      continue
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <h2 key={elements.length} className="text-base font-semibold text-slate-100 mt-3 mb-1.5 pb-0.5 border-b border-slate-800/60">
          {renderInline(trimmed.slice(3))}
        </h2>
      )
      i++
      continue
    }
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h3 key={elements.length} className="text-sm font-semibold text-slate-200 mt-2.5 mb-1">
          {renderInline(trimmed.slice(4))}
        </h3>
      )
      i++
      continue
    }

    // 4. Horizontal Rules
    if (trimmed === '---' || trimmed === '***') {
      elements.push(<hr key={elements.length} className="my-3 border-slate-800" />)
      i++
      continue
    }

    // 5. Blockquotes
    if (trimmed.startsWith('>')) {
      elements.push(
        <blockquote key={elements.length} className="border-l-4 border-amber-500/70 pl-3 py-1 my-2 text-slate-300 italic text-xs bg-slate-900/40 rounded-r">
          {renderInline(trimmed.slice(1).trim())}
        </blockquote>
      )
      i++
      continue
    }

    // 6. Lists
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <div key={elements.length} className="flex items-start gap-2 my-0.5 text-xs text-slate-300">
          <span className="text-amber-400 font-bold">•</span>
          <span>{renderInline(trimmed.slice(2))}</span>
        </div>
      )
      i++
      continue
    }

    // 7. Empty line
    if (!trimmed) {
      elements.push(<div key={elements.length} className="h-1.5"></div>)
      i++
      continue
    }

    // 8. Normal paragraph
    elements.push(
      <p key={elements.length} className="text-xs text-slate-300 leading-relaxed my-1 select-text">
        {renderInline(trimmed)}
      </p>
    )
    i++
  }

  return (
    <div className="space-y-1 p-4 bg-slate-900/90 text-slate-200 rounded-xl font-sans min-h-full">
      {elements}
    </div>
  )
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('thai_ocr_token') || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [currentView, setCurrentView] = useState(() => {
    return window.location.hash === '#/admin' ? 'admin' : 'studio'
  })

  // Review & Compare Modal state
  const [reviewModalOpen, setReviewModalOpen] = useState(false)
  const [reviewJob, setReviewJob] = useState(null)
  const [reviewMarkdown, setReviewMarkdown] = useState('')
  const [reviewOriginalMarkdown, setReviewOriginalMarkdown] = useState('')
  const [reviewZoom, setReviewZoom] = useState(100)
  const [reviewMode, setReviewMode] = useState('split') // 'edit' | 'preview' | 'split'
  const [reviewSaving, setReviewSaving] = useState(false)
  const [reviewSaveStatus, setReviewSaveStatus] = useState('') // '' | 'saved' | 'error'
  const [reviewCopied, setReviewCopied] = useState(false)
  const [exportLoading, setExportLoading] = useState(null) // null | 'docx' | 'xlsx'

  // Login form state
  const [loginUsername, setLoginUsername] = useState('admin')
  const [loginPassword, setLoginPassword] = useState('Admin@Ocr2026!')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  // OCR multi-task state
  const [selectedFiles, setSelectedFiles] = useState([])
  const [activeTasks, setActiveTasks] = useState([])
  const [isDragging, setIsDragging] = useState(false)
  const [successNotice, setSuccessNotice] = useState(null)
  const [ocrError, setOcrError] = useState('')

  // History & Admin state
  const [recentJobs, setRecentJobs] = useState([])
  const [adminMetrics, setAdminMetrics] = useState(null)
  const [adminJobs, setAdminJobs] = useState([])
  const [ldapConfig, setLdapConfig] = useState(null)
  const [engineLogs, setEngineLogs] = useState([])
  const [adminTab, setAdminTab] = useState('metrics') // 'metrics' | 'ldap' | 'apikeys' | 'docs' | 'jobs' | 'logs'
  const [ldapSaveMsg, setLdapSaveMsg] = useState('')

  // API Keys state
  const [apiKeys, setApiKeys] = useState([])
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyIps, setNewKeyIps] = useState('*')
  const [newKeyExpiry, setNewKeyExpiry] = useState(365)
  const [createdKeySecret, setCreatedKeySecret] = useState(null)
  const [keyCopied, setKeyCopied] = useState(false)

  // Local Users Management state
  const [localUsers, setLocalUsers] = useState([])
  const [showCreateUserModal, setShowCreateUserModal] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [newUserRole, setNewUserRole] = useState('user')

  // Password Management state
  const [showChangePasswordModal, setShowChangePasswordModal] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPasswordVal, setNewPasswordVal] = useState('')
  const [confirmPasswordVal, setConfirmPasswordVal] = useState('')
  const [changePasswordLoading, setChangePasswordLoading] = useState(false)
  const [changePasswordError, setChangePasswordError] = useState('')
  const [resetTargetUser, setResetTargetUser] = useState(null)
  const [adminNewPassword, setAdminNewPassword] = useState('')
  const [resetPasswordLoading, setResetPasswordLoading] = useState(false)

  // Super Admin 2FA (TOTP) & Passkey (WebAuthn) state
  const [publicPasskeyEnabled, setPublicPasskeyEnabled] = useState(false)
  const [mfaStep, setMfaStep] = useState(null) // { mfa_token, methods, username }
  const [mfaCode, setMfaCode] = useState('')
  const [securitySettings, setSecuritySettings] = useState({
    totp_enabled: false,
    has_totp_secret: false,
    totp_secret_masked: '',
    passkey_enabled: false,
    passkeys: []
  })
  const [totpSetupData, setTotpSetupData] = useState(null) // { secret, otpauth_uri }
  const [totpVerifyCode, setTotpVerifyCode] = useState('')
  const [newPasskeyName, setNewPasskeyName] = useState('')
  const [securityMsg, setSecurityMsg] = useState('')
  const [securityError, setSecurityError] = useState('')
  const [securityLoading, setSecurityLoading] = useState(false)

  // Retention & Delete state
  const [showRetentionModal, setShowRetentionModal] = useState(false)
  const [deleteConfirmJob, setDeleteConfirmJob] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // OCR Disclaimer Terms Modal state
  const [showDisclaimerModal, setShowDisclaimerModal] = useState(false)
  const [disclaimerFiles, setDisclaimerFiles] = useState([])

  // One-Time Ticket Preview URL and Viewer state
  const [reviewSourceUrl, setReviewSourceUrl] = useState('')
  const [reviewSourceLoading, setReviewSourceLoading] = useState(false)
  const [reviewSourceError, setReviewSourceError] = useState('')
  const [imageNaturalSize, setImageNaturalSize] = useState({ width: 0, height: 0 })
  const [zoomMode, setZoomMode] = useState('fit') // 'fit' | 'custom' | 'actual'

  const fileInputRef = useRef(null)

  // Verify auth on mount & load public security options
  useEffect(() => {
    fetch('/api/auth/security-options')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) setPublicPasskeyEnabled(Boolean(d.passkey_enabled))
      })
      .catch(() => {})
  }, [showLoginModal])

  useEffect(() => {
    if (token) {
      fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(res => res.ok ? res.json() : null)
        .then(user => {
          if (user) {
            setCurrentUser(user)
            loadUserJobs(token)
          } else {
            handleLogout()
          }
        })
        .catch(() => handleLogout())
    }
  }, [token])

  // Auto-refresh jobs when any job is processing
  useEffect(() => {
    if (!token) return
    const hasProcessing = recentJobs.some(j => j.status === 'processing') || activeTasks.some(t => t.status === 'processing')
    if (hasProcessing) {
      const timer = setInterval(() => {
        loadUserJobs(token)
      }, 3000)
      return () => clearInterval(timer)
    }
  }, [recentJobs, activeTasks, token])

  // Synchronize hash changes and enforce admin role gate
  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash
      if (hash === '#/admin') {
        if (currentUser && currentUser.role === 'admin') {
          setCurrentView('admin')
          loadAdminData()
        } else {
          window.location.hash = '#/'
          setCurrentView('studio')
        }
      } else {
        setCurrentView('studio')
      }
    }

    if (window.location.hash === '#/admin') {
      if (currentUser && currentUser.role === 'admin') {
        setCurrentView('admin')
        loadAdminData()
      } else if (currentUser && currentUser.role !== 'admin') {
        window.location.hash = '#/'
        setCurrentView('studio')
      }
    }

    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [currentUser])

  const navigateToView = (view) => {
    if (view === 'admin') {
      if (!currentUser || currentUser.role !== 'admin') return
      window.location.hash = '#/admin'
      setCurrentView('admin')
      loadAdminData()
    } else {
      window.location.hash = '#/'
      setCurrentView('studio')
    }
  }

  const b64urlToUint8Array = (b64url) => {
    const padding = '='.repeat((4 - (b64url.length % 4)) % 4)
    const base64 = (b64url + padding).replace(/-/g, '+').replace(/_/g, '/')
    const raw = window.atob(base64)
    const out = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
    return out
  }

  const bufferToB64url = (buf) => {
    const bytes = new Uint8Array(buf)
    let binary = ''
    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
    return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  }

  const completeLoginSuccess = (data) => {
    localStorage.setItem('thai_ocr_token', data.token)
    setToken(data.token)
    setCurrentUser(data.user)
    setShowLoginModal(false)
    setMfaStep(null)
    setMfaCode('')
    loadUserJobs(data.token)
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginError('')
    setLoginLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'เข้าสู่ระบบไม่สำเร็จ')

      if (data.requires_2fa) {
        setMfaStep(data)
        setMfaCode('')
        return
      }

      completeLoginSuccess(data)
    } catch (err) {
      setLoginError(err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  const handleVerify2FA = async (e) => {
    e.preventDefault()
    if (!mfaStep || !mfaCode.trim()) return
    setLoginError('')
    setLoginLoading(true)
    try {
      const res = await fetch('/api/auth/verify-2fa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mfa_token: mfaStep.mfa_token, code: mfaCode.trim() })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'รหัส OTP ไม่ถูกต้อง')
      completeLoginSuccess(data)
    } catch (err) {
      setLoginError(err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  const handlePasskeyLogin = async () => {
    setLoginError('')
    if (!window.PublicKeyCredential || !navigator.credentials) {
      setLoginError('เบราว์เซอร์นี้ไม่รองรับ WebAuthn / Passkey (ต้องใช้งานผ่าน HTTPS หรือ localhost)')
      return
    }
    setLoginLoading(true)
    try {
      const optsRes = await fetch('/api/auth/passkey/login-options', { method: 'POST' })
      const optsData = await optsRes.json()
      if (!optsRes.ok) throw new Error(optsData.detail || 'ไม่สามารถเริ่มใช้งาน Passkey ได้')

      const publicKey = {
        challenge: b64urlToUint8Array(optsData.challenge),
        timeout: optsData.timeout || 60000,
        userVerification: optsData.userVerification || 'preferred',
        allowCredentials: (optsData.allowCredentials || []).map(c => ({
          type: 'public-key',
          id: b64urlToUint8Array(c.id)
        }))
      }

      const assertion = await navigator.credentials.get({ publicKey })
      if (!assertion) throw new Error('ยกเลิกการยืนยันตัวตนด้วย Passkey')

      const verifyRes = await fetch('/api/auth/passkey/login-verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          credential_id: bufferToB64url(assertion.rawId),
          client_data_json: bufferToB64url(assertion.response.clientDataJSON),
          authenticator_data: bufferToB64url(assertion.response.authenticatorData),
          signature: bufferToB64url(assertion.response.signature),
          challenge_token: optsData.challenge_token
        })
      })
      const verifyData = await verifyRes.json()
      if (!verifyRes.ok) throw new Error(verifyData.detail || 'การยืนยัน Passkey ไม่สำเร็จ')
      completeLoginSuccess(verifyData)
    } catch (err) {
      setLoginError(err.name === 'NotAllowedError' ? 'ยกเลิกหรือไม่ได้รับอนุญาตจากอุปกรณ์ Passkey' : err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('thai_ocr_token')
    setToken('')
    setCurrentUser(null)
    setRecentJobs([])
    window.location.hash = '#/'
    setCurrentView('studio')
  }

  const loadUserJobs = async (authToken) => {
    try {
      const res = await fetch('/api/ocr/jobs', {
        headers: { Authorization: `Bearer ${authToken}` }
      })
      if (res.ok) {
        const jobs = await res.json()
        setRecentJobs(jobs)

        // Resilient recovery: Sync processing jobs back into activeTasks without duplicating
        const processingJobs = jobs.filter(j => j.status === 'processing')
        setActiveTasks(prev => {
          // Collect all identifiers (jobId, taskId, filename) already present in activeTasks
          const activeJobIds = new Set()
          const activeFilenames = new Set()
          for (const t of prev) {
            if (t.jobId) activeJobIds.add(t.jobId)
            if (t.taskId) activeJobIds.add(t.taskId)
            if (t.result && t.result.id) activeJobIds.add(t.result.id)
            if (t.filename) activeFilenames.add(t.filename)
          }

          // Only restore jobs that are NOT already in activeTasks
          const restored = processingJobs
            .filter(j => !activeJobIds.has(j.id) && !activeFilenames.has(j.filename))
            .map(j => ({
              taskId: j.id,
              jobId: j.id,
              filename: j.filename,
              size: j.size_bytes,
              percent: j.progress_percent || 0,
              page: 0,
              total_pages: j.page_count || 1,
              message: `กำลังประมวลผล (${j.progress_percent || 0}%)...`,
              status: 'processing',
              error: null,
              result: null
            }))

          const updated = prev.map(t => {
            const match = jobs.find(j =>
              (t.jobId && j.id === t.jobId) ||
              (t.taskId && j.id === t.taskId) ||
              (t.result && t.result.id === j.id) ||
              (t.filename === j.filename && t.status === 'processing')
            )
            if (match) {
              const matchedJobId = match.id || t.jobId
              if (match.status === 'completed' && t.status !== 'completed') {
                return {
                  ...t,
                  jobId: matchedJobId,
                  status: 'completed',
                  percent: 100,
                  page: match.page_count || t.total_pages,
                  total_pages: match.page_count || t.total_pages,
                  result: match,
                  message: 'ประมวลผลเสร็จสมบูรณ์ 100%'
                }
              } else if (match.status === 'failed' && t.status !== 'error') {
                return {
                  ...t,
                  jobId: matchedJobId,
                  status: 'error',
                  error: match.error_msg || 'เกิดข้อผิดพลาดในการทำ OCR'
                }
              } else if (match.status === 'processing' && t.status === 'processing') {
                return {
                  ...t,
                  jobId: matchedJobId,
                  percent: Math.max(t.percent, match.progress_percent || 0),
                  message: t.message.includes('หน้า') ? t.message : `กำลังประมวลผล (${Math.max(t.percent, match.progress_percent || 0)}%)...`
                }
              }
            }
            return t
          })

          // Deduplicate the combined list strictly by unique filename / jobId
          const seenKeys = new Set()
          const combined = [...updated, ...restored].filter(item => {
            const key = item.jobId || item.filename
            if (seenKeys.has(key)) return false
            seenKeys.add(key)
            return true
          })

          return combined
        })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadAdminData = async () => {
    if (!token) return
    try {
      const [metricsRes, jobsRes, ldapRes, logsRes, keysRes, usersRes, secRes] = await Promise.all([
        fetch('/api/admin/metrics', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/admin/jobs', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/admin/ldap-config', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/admin/engine-logs', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/admin/api-keys', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/admin/users', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/admin/security-settings', { headers: { Authorization: `Bearer ${token}` } })
      ])
      if (metricsRes.ok) setAdminMetrics(await metricsRes.json())
      if (jobsRes.ok) setAdminJobs(await jobsRes.json())
      if (ldapRes.ok) setLdapConfig(await ldapRes.json())
      if (logsRes.ok) {
        const d = await logsRes.json()
        setEngineLogs(d.logs || [])
      }
      if (keysRes.ok) {
        const kd = await keysRes.json()
        setApiKeys(kd.keys || [])
      }
      if (usersRes.ok) {
        const ud = await usersRes.json()
        setLocalUsers(ud.users || [])
      }
      if (secRes.ok) {
        setSecuritySettings(await secRes.json())
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleToggleSecuritySetting = async (field, enabledValue) => {
    setSecurityMsg('')
    setSecurityError('')
    setSecurityLoading(true)
    try {
      const res = await fetch('/api/admin/security/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ [field]: enabledValue })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'ไม่สามารถเปลี่ยนการตั้งค่าได้')
      setSecuritySettings(prev => ({
        ...prev,
        totp_enabled: Boolean(data.totp_enabled),
        passkey_enabled: Boolean(data.passkey_enabled)
      }))
      setSecurityMsg(data.message || 'บันทึกการตั้งค่าเรียบร้อยแล้ว')
    } catch (err) {
      setSecurityError(err.message)
    } finally {
      setSecurityLoading(false)
    }
  }

  const handleSetupTotp = async () => {
    setSecurityMsg('')
    setSecurityError('')
    setSecurityLoading(true)
    try {
      const res = await fetch('/api/admin/security/totp/setup', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'สร้างรหัสลับ TOTP ไม่สำเร็จ')
      setTotpSetupData(data)
      setTotpVerifyCode('')
    } catch (err) {
      setSecurityError(err.message)
    } finally {
      setSecurityLoading(false)
    }
  }

  const handleVerifyAndEnableTotp = async (e) => {
    e.preventDefault()
    if (!totpVerifyCode.trim()) return
    setSecurityMsg('')
    setSecurityError('')
    setSecurityLoading(true)
    try {
      const res = await fetch('/api/admin/security/totp/verify-and-enable', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ code: totpVerifyCode.trim() })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'รหัส OTP ไม่ถูกต้อง')
      setTotpSetupData(null)
      setTotpVerifyCode('')
      setSecurityMsg(data.message)
      loadAdminData()
    } catch (err) {
      setSecurityError(err.message)
    } finally {
      setSecurityLoading(false)
    }
  }

  const handleRegisterPasskey = async (e) => {
    e.preventDefault()
    setSecurityMsg('')
    setSecurityError('')
    if (!window.PublicKeyCredential || !navigator.credentials) {
      setSecurityError('เบราว์เซอร์นี้ไม่รองรับการสร้าง Passkey (WebAuthn)')
      return
    }
    setSecurityLoading(true)
    try {
      const optsRes = await fetch('/api/admin/security/passkeys/register-options', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      })
      const optsData = await optsRes.json()
      if (!optsRes.ok) throw new Error(optsData.detail || 'ไม่สามารถขอข้อมูลลงทะเบียน Passkey ได้')

      const publicKey = {
        challenge: b64urlToUint8Array(optsData.challenge),
        rp: {
          name: optsData.rp?.name || 'ThaiOCR ONNX Security',
          id: window.location.hostname
        },
        user: {
          id: b64urlToUint8Array(optsData.user.id),
          name: optsData.user.name,
          displayName: optsData.user.displayName
        },
        pubKeyCredParams: optsData.pubKeyCredParams,
        timeout: optsData.timeout || 60000,
        attestation: 'none',
        AuthenticatorSelection: {
          userVerification: 'preferred'
        },
        excludeCredentials: (optsData.excludeCredentials || []).map(c => ({
          type: 'public-key',
          id: b64urlToUint8Array(c.id)
        }))
      }

      const cred = await navigator.credentials.create({ publicKey })
      if (!cred) throw new Error('ยกเลิกการสร้าง Passkey')

      let exportedPubKey = 'webauthn_cose_key'
      if (cred.response && typeof cred.response.getPublicKey === 'function') {
        const pkBuf = cred.response.getPublicKey()
        if (pkBuf) exportedPubKey = bufferToB64url(pkBuf)
      }

      const verifyRes = await fetch('/api/admin/security/passkeys/register-verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          credential_id: bufferToB64url(cred.rawId),
          name: newPasskeyName.trim() || `Passkey (${navigator.platform || 'Device'})`,
          public_key: exportedPubKey,
          client_data_json: bufferToB64url(cred.response.clientDataJSON),
          challenge_token: optsData.challenge_token
        })
      })
      const verifyData = await verifyRes.json()
      if (!verifyRes.ok) throw new Error(verifyData.detail || 'บันทึก Passkey ไม่สำเร็จ')
      setNewPasskeyName('')
      setSecurityMsg(verifyData.message)
      loadAdminData()
    } catch (err) {
      setSecurityError(err.name === 'NotAllowedError' ? 'ยกเลิกการลงทะเบียนจากอุปกรณ์' : err.message)
    } finally {
      setSecurityLoading(false)
    }
  }

  const handleDeletePasskey = async (credId) => {
    setSecurityMsg('')
    setSecurityError('')
    try {
      const res = await fetch(`/api/admin/security/passkeys/${encodeURIComponent(credId)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'ลบ Passkey ไม่สำเร็จ')
      setSecurityMsg(data.message)
      loadAdminData()
    } catch (err) {
      setSecurityError(err.message)
    }
  }

  const handleCreateApiKey = async (e) => {
    e.preventDefault()
    if (!newKeyName.trim()) return
    try {
      const res = await fetch('/api/admin/api-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: newKeyName.trim(),
          allowed_ips: newKeyIps.trim() || '*',
          expires_in_days: parseInt(newKeyExpiry, 10) || 365
        })
      })
      const data = await res.json()
      if (res.ok) {
        setCreatedKeySecret(data.api_key)
        setApiKeys(prev => [data.key_record, ...prev])
        setNewKeyName('')
        setNewKeyIps('*')
      } else {
        alert(data.detail || 'ไม่สามารถสร้าง API Key ได้')
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleToggleKeyStatus = async (keyId, currentStatus) => {
    try {
      const res = await fetch(`/api/admin/api-keys/${keyId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ is_active: !currentStatus })
      })
      if (res.ok) {
        setApiKeys(prev => prev.map(k => k.id === keyId ? { ...k, is_active: currentStatus ? 0 : 1 } : k))
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDeleteApiKey = async (keyId) => {
    if (!confirm('คุณแน่ใจหรือไม่ว่าต้องการลบ API Key นี้อย่างถาวร?')) return
    try {
      const res = await fetch(`/api/admin/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        setApiKeys(prev => prev.filter(k => k.id !== keyId))
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleCreateLocalUser = async (e) => {
    e.preventDefault()
    if (!newUsername.trim() || !newPassword) return
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword,
          display_name: newDisplayName.trim() || newUsername.trim(),
          role: newUserRole
        })
      })
      const data = await res.json()
      if (res.ok) {
        setLocalUsers(prev => [data.user, ...prev])
        setShowCreateUserModal(false)
        setNewUsername('')
        setNewPassword('')
        setNewDisplayName('')
        alert(`สร้างผู้ใช้ '${data.user.username}' สำเร็จเรียบร้อยแล้ว`)
      } else {
        alert(data.detail || 'ไม่สามารถสร้างผู้ใช้ได้')
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleToggleUserStatus = async (username, currentStatus) => {
    try {
      const res = await fetch(`/api/admin/users/${username}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ is_active: !currentStatus })
      })
      if (res.ok) {
        setLocalUsers(prev => prev.map(u => u.username === username ? { ...u, is_active: currentStatus ? 0 : 1 } : u))
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDeleteLocalUser = async (username) => {
    if (!confirm(`คุณแน่ใจหรือไม่ว่าต้องการลบผู้ใช้ '${username}' ออกจากระบบ?`)) return
    try {
      const res = await fetch(`/api/admin/users/${username}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        setLocalUsers(prev => prev.filter(u => u.username !== username))
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setChangePasswordError('')
    if (!oldPassword || !newPasswordVal) {
      setChangePasswordError('กรุณากรอกข้อมูลให้ครบถ้วน')
      return
    }
    if (newPasswordVal.length < 6) {
      setChangePasswordError('รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 6 ตัวอักษร')
      return
    }
    if (newPasswordVal !== confirmPasswordVal) {
      setChangePasswordError('รหัสผ่านใหม่และการยืนยันรหัสผ่านไม่ตรงกัน')
      return
    }

    setChangePasswordLoading(true)
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPasswordVal
        })
      })
      const data = await res.json()
      if (res.ok) {
        alert(data.message || 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว')
        setShowChangePasswordModal(false)
        setOldPassword('')
        setNewPasswordVal('')
        setConfirmPasswordVal('')
      } else {
        setChangePasswordError(data.detail || 'ไม่สามารถเปลี่ยนรหัสผ่านได้')
      }
    } catch (err) {
      setChangePasswordError(err.message)
    } finally {
      setChangePasswordLoading(false)
    }
  }

  const handleAdminResetPassword = async (e) => {
    e.preventDefault()
    if (!resetTargetUser || !adminNewPassword) return
    if (adminNewPassword.length < 6) {
      alert('รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 6 ตัวอักษร')
      return
    }

    setResetPasswordLoading(true)
    try {
      const res = await fetch(`/api/admin/users/${resetTargetUser}/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ new_password: adminNewPassword })
      })
      const data = await res.json()
      if (res.ok) {
        alert(data.message || `รีเซ็ตรหัสผ่านสำหรับ '${resetTargetUser}' สำเร็จ`)
        setResetTargetUser(null)
        setAdminNewPassword('')
      } else {
        alert(data.detail || 'ไม่สามารถรีเซ็ตรหัสผ่านได้')
      }
    } catch (err) {
      alert(err.message)
    } finally {
      setResetPasswordLoading(false)
    }
  }

  const handleSaveLdap = async (e) => {
    e.preventDefault()
    setLdapSaveMsg('')
    try {
      const res = await fetch('/api/admin/ldap-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(ldapConfig)
      })
      const data = await res.json()
      if (res.ok) {
        setLdapSaveMsg('บันทึกการตั้งค่า LDAP เรียบร้อยแล้ว')
        setTimeout(() => setLdapSaveMsg(''), 4000)
      } else {
        alert(data.detail || 'เกิดข้อผิดพลาดในการบันทึก')
      }
    } catch (e) {
      alert(e.message)
    }
  }

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

  // Drag & drop handlers
  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files)
    }
  }

  const handleFilesSelected = (fileList) => {
    if (!fileList || fileList.length === 0) return
    const valid = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'webp']
    const newFiles = []
    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i]
      const ext = f.name.split('.').pop().toLowerCase()
      if (valid.includes(ext)) {
        newFiles.push(f)
      } else {
        alert(`ไฟล์ ${f.name} นามสกุล .${ext} ไม่รองรับ กรุณาเลือกไฟล์ PDF หรือรูปภาพ`)
      }
    }
    if (newFiles.length > 0) {
      setSelectedFiles(prev => [...prev, ...newFiles])
      setSuccessNotice(null)
      setOcrError('')
    }
  }

  const removeSelectedFile = (idx) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx))
  }

  const dismissActiveTask = (taskId) => {
    setActiveTasks(prev => prev.filter(t => t.taskId !== taskId))
  }

  const startTaskForFile = async (file) => {
    if (!token) {
      setShowLoginModal(true)
      return
    }

    const taskId = 'task_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6)
    const newTask = {
      taskId,
      jobId: null,
      filename: file.name,
      size: file.size,
      percent: 0,
      page: 0,
      total_pages: 0,
      message: 'กำลังเริ่มส่งข้อมูล...',
      status: 'processing',
      error: null,
      result: null,
    }

    setActiveTasks(prev => {
      // Remove any existing card with exact same filename to avoid duplication
      const filtered = prev.filter(t => t.filename !== file.name)
      return [newTask, ...filtered]
    })

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/ocr/upload?stream=true', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'เกิดข้อผิดพลาดในการทำ OCR')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() // retain incomplete chunk

        for (const block of blocks) {
          const trimmed = block.trim()
          if (trimmed.startsWith('data: ')) {
            try {
              const evt = JSON.parse(trimmed.slice(6))
              if (evt.status === 'init' || evt.status === 'progress') {
                setActiveTasks(prev => prev.map(t => t.taskId === taskId ? {
                  ...t,
                  jobId: evt.job_id || t.jobId,
                  percent: evt.percent !== undefined ? evt.percent : t.percent,
                  page: evt.page || t.page,
                  total_pages: evt.total_pages || t.total_pages,
                  message: evt.message || t.message
                } : t))
              } else if (evt.status === 'completed') {
                const resObj = evt.result || {}
                const actualJobId = resObj.job_id || evt.job_id || t.jobId
                const completeResult = {
                  id: actualJobId,
                  job_id: actualJobId,
                  filename: resObj.filename || file.name,
                  page_count: resObj.page_count || 1,
                  status: 'completed',
                  latency_ms: resObj.latency_ms,
                  file_type: (resObj.filename || file.name).split('.').pop().toLowerCase(),
                  markdown: resObj.markdown
                }
                setActiveTasks(prev => prev.map(t => t.taskId === taskId ? {
                  ...t,
                  jobId: resObj.job_id || t.jobId,
                  percent: 100,
                  page: resObj.page_count || t.total_pages,
                  total_pages: resObj.page_count || t.total_pages,
                  message: 'ประมวลผลเสร็จสมบูรณ์ 100%',
                  status: 'completed',
                  result: completeResult
                } : t))
                setSuccessNotice(completeResult)
                loadUserJobs(token)
              } else if (evt.status === 'error') {
                throw new Error(evt.error || 'เกิดข้อผิดพลาดในการทำ OCR')
              }
            } catch (pErr) {
              console.warn('SSE parse error:', pErr)
            }
          }
        }
      }
    } catch (err) {
      setActiveTasks(prev => prev.map(t => t.taskId === taskId ? {
        ...t,
        status: 'error',
        error: err.message
      } : t))
    }
  }

  const handleRequestOCR = () => {
    if (!token) {
      setShowLoginModal(true)
      return
    }
    if (selectedFiles.length === 0) return
    setDisclaimerFiles([...selectedFiles])
    setShowDisclaimerModal(true)
  }

  const handleAcceptDisclaimer = async () => {
    setShowDisclaimerModal(false)
    const filesToRun = [...disclaimerFiles]
    setDisclaimerFiles([])
    setSelectedFiles([])

    // Log terms acceptance
    try {
      fetch('/api/ocr/terms-response', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          action: 'accept',
          filenames: filesToRun.map(f => f.name)
        })
      }).catch(err => console.warn('Audit log error:', err))
    } catch (_) {}

    // Execute tasks
    filesToRun.forEach(file => {
      startTaskForFile(file)
    })
  }

  const handleDeclineDisclaimer = async () => {
    setShowDisclaimerModal(false)
    const filesDeclined = [...disclaimerFiles]
    setDisclaimerFiles([])
    setSelectedFiles([]) // cancel staged files

    // Log terms decline
    try {
      fetch('/api/ocr/terms-response', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          action: 'decline',
          filenames: filesDeclined.map(f => f.name)
        })
      }).catch(err => console.warn('Audit log error:', err))
    } catch (_) {}
  }

  const handleStartAll = () => {
    handleRequestOCR()
  }

  const fetchSourceTicket = async (jobId) => {
    if (!token || !jobId) return
    setReviewSourceLoading(true)
    setReviewSourceError('')
    try {
      const ticketRes = await fetch('/api/ocr/tickets/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ job_id: jobId, format: 'source' })
      })
      if (ticketRes.ok) {
        const ticketData = await ticketRes.json()
        setReviewSourceUrl(`/api/ocr/file/${jobId}?ticket=${encodeURIComponent(ticketData.ticket)}`)
      } else {
        const errData = await ticketRes.json().catch(() => ({}))
        setReviewSourceError(errData.detail || 'ไม่สามารถออกตั๋วเข้าถึงไฟล์ต้นฉบับได้')
      }
    } catch (tErr) {
      console.warn('Failed to fetch preview ticket:', tErr)
      setReviewSourceError('เกิดข้อผิดพลาดในการโหลดตั๋วดูไฟล์ต้นฉบับ')
    } finally {
      setReviewSourceLoading(false)
    }
  }

  const handleOpenReview = async (job) => {
    if (!token) {
      setShowLoginModal(true)
      return
    }

    const targetJobId = job?.id || job?.job_id
    if (!targetJobId) {
      alert('ไม่พบรหัสงาน (Job ID)')
      return
    }

    setReviewZoom(100)
    setZoomMode('fit')
    setReviewMode('split')
    setReviewSaveStatus('')
    setReviewSourceUrl('')
    setReviewSourceError('')
    setImageNaturalSize({ width: 0, height: 0 })

    const fileType = (job.file_type || job.filename?.split('.').pop() || '').toLowerCase()
    const normalizedJob = {
      ...job,
      id: targetJobId,
      job_id: targetJobId,
      file_type: fileType
    }

    // Fetch source ticket immediately
    fetchSourceTicket(targetJobId)

    if (job.markdown) {
      setReviewJob(normalizedJob)
      setReviewMarkdown(job.markdown)
      setReviewOriginalMarkdown(job.markdown)
      setReviewModalOpen(true)
    } else {
      try {
        const res = await fetch(`/api/ocr/jobs/${targetJobId}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (res.ok) {
          const fullJob = await res.json()
          const mergedJob = {
            ...normalizedJob,
            ...fullJob,
            id: targetJobId,
            job_id: targetJobId,
            file_type: fileType || fullJob.file_type
          }
          setReviewJob(mergedJob)
          setReviewMarkdown(fullJob.markdown || '')
          setReviewOriginalMarkdown(fullJob.markdown || '')
          setReviewModalOpen(true)
        } else {
          alert('ไม่สามารถโหลดข้อมูลเอกสารได้')
        }
      } catch (e) {
        alert('เกิดข้อผิดพลาดในการโหลดเอกสาร: ' + e.message)
      }
    }
  }

  const handleSaveReviewMarkdown = async () => {
    if (!reviewJob) return
    setReviewSaving(true)
    setReviewSaveStatus('')
    try {
      const res = await fetch(`/api/ocr/jobs/${reviewJob.id}/markdown`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ markdown: reviewMarkdown })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'บันทึกไม่สำเร็จ')

      setReviewSaveStatus('saved')
      setReviewOriginalMarkdown(reviewMarkdown)
      setRecentJobs(prev => prev.map(j => j.id === reviewJob.id ? { ...j, markdown: reviewMarkdown } : j))
      if (successNotice && (successNotice.job_id === reviewJob.id || successNotice.id === reviewJob.id)) {
        setSuccessNotice(prev => ({ ...prev, markdown: reviewMarkdown }))
      }
      setTimeout(() => setReviewSaveStatus(''), 3000)
    } catch (err) {
      alert('เกิดข้อผิดพลาดในการบันทึก: ' + err.message)
      setReviewSaveStatus('error')
    } finally {
      setReviewSaving(false)
    }
  }

  const handleDownloadEditedMd = () => {
    handleDownloadExport('md')
  }

  const handleDownloadExport = async (format) => {
    if (!reviewJob) return
    const baseName = reviewJob.filename.replace(/\.[^/.]+$/, '')

    if (format === 'md') {
      const blob = new Blob([reviewMarkdown], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${baseName}_reviewed.md`
      a.click()
      URL.revokeObjectURL(url)
      return
    }

    try {
      setExportLoading(format)
      const resp = await fetch(`/api/ocr/export/${format}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          markdown: reviewMarkdown,
          filename: reviewJob.filename,
          job_id: reviewJob.id
        })
      })
      if (!resp.ok) throw new Error('Export failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${baseName}_reviewed.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export error:', err)
      alert(`เกิดข้อผิดพลาดในการสร้างไฟล์ ${format.toUpperCase()}: ${err.message}`)
    } finally {
      setExportLoading(null)
    }
  }

  const handleCopyReviewMarkdown = () => {
    navigator.clipboard.writeText(reviewMarkdown)
    setReviewCopied(true)
    setTimeout(() => setReviewCopied(false), 2000)
  }

  // Toggle Thai ⇄ Arabic numerals in the entire markdown document
  const handleToggleNumerals = () => {
    if (!reviewMarkdown) return
    const thaiDigits = ['๐', '๑', '๒', '๓', '๔', '๕', '๖', '๗', '๘', '๙']
    const arabicDigits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

    let thaiCount = 0
    let arabicCount = 0
    for (let i = 0; i < reviewMarkdown.length; i++) {
      const ch = reviewMarkdown[i]
      if (ch >= '๐' && ch <= '๙') thaiCount++
      else if (ch >= '0' && ch <= '9') arabicCount++
    }

    // If document currently has Thai numerals, convert to Arabic; otherwise convert to Thai
    const toArabic = thaiCount > 0

    let result = reviewMarkdown
    if (toArabic) {
      for (let i = 0; i < 10; i++) {
        result = result.replaceAll(thaiDigits[i], arabicDigits[i])
      }
    } else {
      for (let i = 0; i < 10; i++) {
        result = result.replaceAll(arabicDigits[i], thaiDigits[i])
      }
    }
    setReviewMarkdown(result)
  }

  const handleDownloadWithTicket = async (jobId, format) => {
    if (!token) {
      setShowLoginModal(true)
      return
    }
    try {
      const res = await fetch('/api/ocr/tickets/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ job_id: jobId, format })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'ขอรับตั๋วดาวน์โหลดไม่สำเร็จ')

      // Trigger download with One-Time Single-Use Ticket (Valid for 60s)
      window.location.href = `/api/ocr/download/${jobId}/${format}?ticket=${encodeURIComponent(data.ticket)}`
    } catch (err) {
      alert(`ไม่สามารถดาวน์โหลดไฟล์ได้: ${err.message}`)
    }
  }

  const getTimeRemaining = (createdAt) => {
    if (!createdAt) return '3 วัน'
    const expiresAt = (createdAt + 3 * 86400) * 1000
    const diffMs = expiresAt - Date.now()
    if (diffMs <= 0) return 'กำลังลบข้อมูล'
    const hours = Math.floor(diffMs / (1000 * 60 * 60))
    if (hours >= 24) {
      const days = Math.floor(hours / 24)
      const remHours = hours % 24
      return `${days} วัน ${remHours} ชม.`
    }
    return `${Math.max(1, hours)} ชม.`
  }

  const handleDeleteJob = async (jobId) => {
    if (!token) return
    setIsDeleting(true)
    try {
      const res = await fetch(`/api/ocr/jobs/${jobId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'ลบไม่สำเร็จ')

      setRecentJobs(prev => prev.filter(j => j.id !== jobId))
      setAdminJobs(prev => prev.filter(j => j.id !== jobId))
      if (reviewJob && reviewJob.id === jobId) {
        setReviewModalOpen(false)
        setReviewJob(null)
      }
      if (successNotice && (successNotice.job_id === jobId || successNotice.id === jobId)) {
        setSuccessNotice(null)
      }
      setDeleteConfirmJob(null)
    } catch (err) {
      alert('เกิดข้อผิดพลาดในการลบเอกสาร: ' + err.message)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Navigation */}
      <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-30 shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div
              onClick={() => navigateToView('studio')}
              className="flex items-center space-x-3 cursor-pointer group select-none"
              title="กลับสู่หน้า OCR Studio"
            >
              <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold text-lg shadow-inner group-hover:scale-105 transition-transform">
                OCR
              </div>
              <div>
                <div className="font-semibold text-base leading-tight tracking-wide flex items-center gap-2">
                  <span>ThaiOCR Portal</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                    Offline 100%
                  </span>
                </div>
                <p className="text-xs text-slate-400">ระบบประมวลผลข้อความ OCR</p>
              </div>
            </div>

            {/* Top Navbar Switcher for Admin */}
            {currentUser && currentUser.role === 'admin' && (
              <nav className="flex items-center bg-slate-800/90 p-1 rounded-xl border border-slate-700/80 text-xs">
                <button
                  type="button"
                  onClick={() => navigateToView('studio')}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition cursor-pointer ${
                    currentView === 'studio'
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>OCR Studio</span>
                </button>
                <button
                  type="button"
                  onClick={() => navigateToView('admin')}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition cursor-pointer ${
                    currentView === 'admin'
                      ? 'bg-amber-600 text-white shadow-xs'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                  }`}
                >
                  <Shield className="w-3.5 h-3.5 text-amber-300" />
                  <span>Admin Governance</span>
                </button>
              </nav>
            )}
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 text-xs text-slate-400 bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700/60">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>ระบบประมวลผลความเร็วสูง</span>
              <span className="text-slate-600">•</span>
              <span>ระบบจัดเก็บปลอดภัย</span>
            </div>

            {currentUser ? (
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2 bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700 text-xs">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-200 font-medium">{currentUser.display_name}</span>
                  <button
                    onClick={() => {
                      setChangePasswordError('')
                      setOldPassword('')
                      setNewPasswordVal('')
                      setConfirmPasswordVal('')
                      setShowChangePasswordModal(true)
                    }}
                    title="เปลี่ยนรหัสผ่าน"
                    className="ml-1 text-slate-400 hover:text-amber-300 transition cursor-pointer p-0.5 rounded hover:bg-slate-700/60"
                  >
                    <Key className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={handleLogout}
                    title="ออกจากระบบ"
                    className="ml-1 text-slate-400 hover:text-rose-400 transition cursor-pointer p-0.5 rounded hover:bg-slate-700/60"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowLoginModal(true)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all shadow-sm cursor-pointer flex items-center space-x-1.5"
              >
                <User className="w-3.5 h-3.5" />
                <span>เข้าสู่ระบบ (LDAP / Admin)</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Studio / Admin Area */}
      <main className={`${currentView === 'admin' && currentUser?.role === 'admin' ? 'max-w-7xl' : 'max-w-6xl'} mx-auto px-4 sm:px-6 py-6 flex-1 w-full space-y-6`}>
        {currentView === 'admin' && currentUser?.role === 'admin' ? (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
            {/* Admin Page Header */}
            <div className="bg-slate-900 text-white p-5 sm:p-6 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="font-bold text-lg leading-tight">Admin Backend Monitor & Governance</h2>
                  <p className="text-xs text-slate-400">ติดตามระบบ, ความเร็วประมวลผล (Latency), ผู้ใช้งาน, API Keys และตั้งค่า LDAP</p>
                </div>
              </div>

              <div className="flex items-center space-x-2.5">
                <button
                  onClick={loadAdminData}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center space-x-1.5 cursor-pointer border border-slate-700 transition"
                  title="รีเฟรชข้อมูล"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>รีเฟรชข้อมูล</span>
                </button>
                <button
                  onClick={() => navigateToView('studio')}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center space-x-1.5 cursor-pointer shadow-xs transition"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>กลับหน้า OCR Studio</span>
                </button>
              </div>
            </div>

            {/* Admin Tabs */}
            <div className="bg-slate-100 border-b border-slate-200 px-6 flex space-x-4 text-xs font-medium text-slate-600 overflow-x-auto">
              <button
                onClick={() => setAdminTab('metrics')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 ${
                  adminTab === 'metrics' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                ภาพรวมระบบ & Latency
              </button>
              <button
                onClick={() => setAdminTab('users')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 flex items-center gap-1.5 ${
                  adminTab === 'users' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                <User className="w-3.5 h-3.5" />
                <span>ผู้ใช้งานในระบบ ({localUsers.length})</span>
              </button>
              <button
                onClick={() => setAdminTab('apikeys')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 flex items-center gap-1.5 ${
                  adminTab === 'apikeys' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                <Key className="w-3.5 h-3.5" />
                <span>จัดการ API Keys ({apiKeys.length})</span>
              </button>
              <button
                onClick={() => setAdminTab('docs')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 flex items-center gap-1.5 ${
                  adminTab === 'docs' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>คู่มือเชื่อมต่อ API</span>
              </button>
              <button
                onClick={() => setAdminTab('ldap')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 ${
                  adminTab === 'ldap' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                จัดการการเชื่อมต่อ & ตัวกรอง LDAP
              </button>
              <button
                onClick={() => setAdminTab('jobs')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 ${
                  adminTab === 'jobs' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                รายการงานทั้งหมด ({adminJobs.length})
              </button>
              <button
                onClick={() => setAdminTab('logs')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 ${
                  adminTab === 'logs' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                บันทึก Engine Logs
              </button>
              <button
                onClick={() => setAdminTab('security')}
                className={`py-3.5 border-b-2 cursor-pointer transition shrink-0 flex items-center gap-1.5 ${
                  adminTab === 'security' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent hover:text-slate-900'
                }`}
              >
                <Shield className="w-3.5 h-3.5" />
                <span>ความปลอดภัย (Passkey & 2FA)</span>
              </button>
            </div>

            {/* Admin Page Body */}
            <div className="p-6 space-y-6">
              {adminTab === 'metrics' && adminMetrics && (
                <div className="space-y-6">
                  {/* KPI Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <p className="text-xs text-slate-500 font-medium">เอกสารทั้งหมด</p>
                      <p className="text-2xl font-bold text-slate-900 mt-1">{adminMetrics.total_jobs}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">{adminMetrics.total_pages} หน้าสะสม</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <p className="text-xs text-slate-500 font-medium">ความเร็วเฉลี่ย (Latency)</p>
                      <p className="text-2xl font-bold text-blue-600 mt-1">{(adminMetrics.avg_latency_ms / 1000).toFixed(2)} วิ</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">{adminMetrics.avg_latency_ms} ms / เอกสาร</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <p className="text-xs text-slate-500 font-medium">ความสำเร็จ (Success Rate)</p>
                      <p className="text-2xl font-bold text-emerald-600 mt-1">{adminMetrics.success_rate}%</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">ล้มเหลว {adminMetrics.failed_jobs} รายการ</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <p className="text-xs text-slate-500 font-medium">ระบบจัดเก็บไฟล์ (Storage)</p>
                      <p className="text-sm font-bold text-slate-800 mt-2 flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${adminMetrics.storage?.connected ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                        <span>{adminMetrics.storage?.connected ? 'พร้อมใช้งาน' : 'สำรองในเครื่อง'}</span>
                      </p>
                      <p className="text-[10px] text-slate-400 mt-1 truncate">ระบบความปลอดภัยข้อมูล</p>
                    </div>
                  </div>

                  {/* Daily stats table */}
                  {adminMetrics.daily_stats && (
                    <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                      <h4 className="text-xs font-semibold text-slate-700 mb-3">สถิติการใช้งานรายวัน (7 วันล่าสุด)</h4>
                      <div className="space-y-2">
                        {adminMetrics.daily_stats.map((day, i) => (
                          <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-slate-200/60 last:border-0">
                            <span className="font-medium text-slate-700">{day.day}</span>
                            <div className="flex items-center space-x-4">
                              <span className="text-slate-500">{day.count} รายการ</span>
                              <span className="text-blue-600 font-mono">{(day.avg_lat / 1000).toFixed(2)}s avg</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* OCR Cache Management Card */}
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
                </div>
              )}

              {adminTab === 'ldap' && ldapConfig && (
                <form onSubmit={handleSaveLdap} className="space-y-4">
                  {ldapSaveMsg && (
                    <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center space-x-2">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{ldapSaveMsg}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Server URI</label>
                      <input
                        type="text"
                        value={ldapConfig.server_uri || ''}
                        onChange={(e) => setLdapConfig({...ldapConfig, server_uri: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Base DN</label>
                      <input
                        type="text"
                        value={ldapConfig.base_dn || ''}
                        onChange={(e) => setLdapConfig({...ldapConfig, base_dn: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Bind DN (Service Account)</label>
                      <input
                        type="text"
                        value={ldapConfig.bind_dn || ''}
                        onChange={(e) => setLdapConfig({...ldapConfig, bind_dn: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Bind Password</label>
                      <input
                        type="password"
                        value={ldapConfig.bind_password || ''}
                        onChange={(e) => setLdapConfig({...ldapConfig, bind_password: e.target.value})}
                        placeholder="••••••••"
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">User Search Filter</label>
                    <input
                      type="text"
                      value={ldapConfig.user_search_filter || ''}
                      onChange={(e) => setLdapConfig({...ldapConfig, user_search_filter: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Allowed Groups Filter (คั่นด้วยจุลภาค ,)</label>
                    <input
                      type="text"
                      value={ldapConfig.allowed_groups || ''}
                      onChange={(e) => setLdapConfig({...ldapConfig, allowed_groups: e.target.value})}
                      placeholder="เช่น OCR_Users, Staff"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                    />
                    <p className="text-[11px] text-slate-500 mt-1">เฉพาะผู้ใช้ที่อยู่ในกลุ่มที่ระบุเท่านั้นจึงจะสามารถเข้าสู่ระบบและใช้งาน OCR ได้</p>
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-slate-200">
                    <label className="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(ldapConfig.is_enabled)}
                        onChange={(e) => setLdapConfig({...ldapConfig, is_enabled: e.target.checked ? 1 : 0})}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span>เปิดใช้งานการยืนยันตัวตนผ่าน LDAP (Enable LDAP)</span>
                    </label>

                    <button
                      type="submit"
                      className="px-5 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition cursor-pointer"
                    >
                      บันทึกการตั้งค่า LDAP
                    </button>
                  </div>
                </form>
              )}

              {adminTab === 'jobs' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                      <tr>
                        <th className="py-2 px-3">Job ID</th>
                        <th className="py-2 px-3">ชื่อไฟล์</th>
                        <th className="py-2 px-3">ผู้ใช้งาน</th>
                        <th className="py-2 px-3">หน้า</th>
                        <th className="py-2 px-3">Latency</th>
                        <th className="py-2 px-3">สถานะ</th>
                        <th className="py-2 px-3 text-right">ดาวน์โหลด</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {adminJobs.map((job) => (
                        <tr key={job.id} className="hover:bg-slate-50">
                          <td className="py-2 px-3 font-mono text-slate-500">{job.id}</td>
                          <td className="py-2 px-3 font-medium text-slate-800">{job.filename}</td>
                          <td className="py-2 px-3 text-slate-600">{job.user_name || job.user_id}</td>
                          <td className="py-2 px-3 text-slate-600">{job.page_count}</td>
                          <td className="py-2 px-3 font-mono text-slate-600">{(job.latency_ms / 1000).toFixed(2)}s</td>
                          <td className="py-2 px-3">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${
                              job.status === 'completed'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : job.status === 'processing'
                                ? 'bg-blue-50 text-blue-700 border-blue-200'
                                : 'bg-rose-50 text-rose-700 border-rose-200'
                            }`}
                            title={job.error_msg || ''}
                            >
                              {job.status === 'completed' ? 'สำเร็จ' : job.status === 'processing' ? `กำลังทำ ${job.progress_percent ? job.progress_percent + '%' : '...'}` : 'ผิดพลาด'}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right space-x-1">
                            {job.status === 'completed' && (
                              <button
                                onClick={() => handleOpenReview(job)}
                                className="text-blue-600 hover:underline mr-1 font-medium cursor-pointer"
                              >
                                รีวิว
                              </button>
                            )}
                            <button onClick={() => handleDownloadWithTicket(job.id, 'docx')} className="text-indigo-600 hover:underline cursor-pointer">DOCX</button>
                            <span>•</span>
                            <button onClick={() => handleDownloadWithTicket(job.id, 'xlsx')} className="text-emerald-600 hover:underline cursor-pointer">XLSX</button>
                            <span>•</span>
                            <button onClick={() => handleDownloadWithTicket(job.id, 'md')} className="text-blue-600 hover:underline cursor-pointer">MD</button>
                            <span>•</span>
                            <button onClick={() => handleDownloadWithTicket(job.id, 'txt')} className="text-slate-600 hover:underline cursor-pointer">TXT</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {adminTab === 'logs' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-slate-700">บันทึกการทำงานของระบบ (System Logs)</h4>
                    <span className="text-[11px] text-slate-500 font-mono">{engineLogs.length} บรรทัดล่าสุด</span>
                  </div>
                  <div className="bg-slate-950 text-slate-200 p-4 rounded-xl font-mono text-[11px] leading-relaxed max-h-[550px] overflow-auto border border-slate-800">
                    {engineLogs.length > 0 ? (
                      engineLogs.map((line, idx) => (
                        <div key={idx} className="hover:bg-slate-900 py-0.5 whitespace-pre-wrap">{line}</div>
                      ))
                    ) : (
                      <div className="text-slate-500 italic">ยังไม่มีประวัติ Log</div>
                    )}
                  </div>
                </div>
              )}

              {/* Local Users Management Tab */}
              {adminTab === 'users' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-semibold text-slate-800">จัดการผู้ใช้งานในระบบ (Local Web Users)</h4>
                      <p className="text-[11px] text-slate-500">บัญชีสำหรับเจ้าหน้าที่ล็อกอินใช้งานผ่าน Web Portal เท่านั้น (ถูกล็อกไม่ให้เข้าถึง M2M API)</p>
                    </div>
                    <button
                      onClick={() => setShowCreateUserModal(true)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 cursor-pointer shadow-sm transition"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>สร้างผู้ใช้ใหม่</span>
                    </button>
                  </div>

                  <div className="overflow-x-auto border border-slate-200 rounded-xl">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                        <tr>
                          <th className="py-2.5 px-3">Username</th>
                          <th className="py-2.5 px-3">ชื่อ-นามสกุล</th>
                          <th className="py-2.5 px-3">สิทธิ์ (Role)</th>
                          <th className="py-2.5 px-3">การเข้าถึง API</th>
                          <th className="py-2.5 px-3">สถานะ</th>
                          <th className="py-2.5 px-3 text-right">จัดการ</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {localUsers.length > 0 ? (
                          localUsers.map((u) => (
                            <tr key={u.username} className="hover:bg-slate-50/80">
                              <td className="py-2.5 px-3 font-semibold text-slate-800 font-mono">{u.username}</td>
                              <td className="py-2.5 px-3 text-slate-700">{u.display_name}</td>
                              <td className="py-2.5 px-3">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                                  u.role === 'admin' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-600 border-slate-200'
                                }`}>
                                  {u.role === 'admin' ? 'ผู้ดูแลระบบ' : 'ผู้ใช้ทั่วไป'}
                                </span>
                              </td>
                              <td className="py-2.5 px-3">
                                <span className="text-[11px] text-rose-600 font-medium flex items-center gap-1">
                                  <Ban className="w-3 h-3" />
                                  <span>ไม่มีสิทธิ์ใช้ API</span>
                                </span>
                              </td>
                              <td className="py-2.5 px-3">
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                  u.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'
                                }`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
                                  <span>{u.is_active ? 'เปิดใช้งาน' : 'ระงับการใช้งาน'}</span>
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-right space-x-2">
                                <button
                                  onClick={() => {
                                    setResetTargetUser(u.username)
                                    setAdminNewPassword('')
                                  }}
                                  className="text-[11px] text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
                                  title="ตั้งรหัสผ่านใหม่ให้ผู้ใช้นี้"
                                >
                                  รีเซ็ตรหัส
                                </button>
                                <button
                                  onClick={() => handleToggleUserStatus(u.username, u.is_active)}
                                  className={`text-[11px] font-medium hover:underline cursor-pointer ${
                                    u.is_active ? 'text-amber-600' : 'text-emerald-600'
                                  }`}
                                >
                                  {u.is_active ? 'ระงับ' : 'เปิดใช้'}
                                </button>
                                <button
                                  onClick={() => handleDeleteLocalUser(u.username)}
                                  className="text-[11px] text-rose-600 hover:text-rose-800 hover:underline cursor-pointer"
                                >
                                  ลบ
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="6" className="py-8 text-center text-slate-400 italic">
                              ยังไม่มีผู้ใช้งานแบบ Local ในระบบ (มีเฉพาะบัญชี Super Admin จาก Environment)
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* API Keys Management Tab */}
              {adminTab === 'apikeys' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-semibold text-slate-800">จัดการ API Keys สำหรับระบบภายนอก (Machine-to-Machine)</h4>
                      <p className="text-[11px] text-slate-500">อนุญาตให้เซิร์ฟเวอร์ระบบอื่นส่งเอกสารมาแปลงไฟล์ผ่าน REST API พร้อมระบบ IP Whitelisting</p>
                    </div>
                    <button
                      onClick={() => setShowCreateKeyModal(true)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1.5 cursor-pointer shadow-sm transition"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>สร้าง API Key ใหม่</span>
                    </button>
                  </div>

                  <div className="overflow-x-auto border border-slate-200 rounded-xl">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                        <tr>
                          <th className="py-2.5 px-3">ชื่อระบบ (Service)</th>
                          <th className="py-2.5 px-3">Key Prefix</th>
                          <th className="py-2.5 px-3">IP Whitelist</th>
                          <th className="py-2.5 px-3">ใช้งานล่าสุด</th>
                          <th className="py-2.5 px-3">สถานะ</th>
                          <th className="py-2.5 px-3 text-right">จัดการ</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {apiKeys.length > 0 ? (
                          apiKeys.map((k) => (
                            <tr key={k.id} className="hover:bg-slate-50/80">
                              <td className="py-2.5 px-3 font-semibold text-slate-800">
                                {k.name}
                                <span className="block text-[10px] text-slate-400 font-normal">สร้างโดย: {k.created_by}</span>
                              </td>
                              <td className="py-2.5 px-3 font-mono text-slate-600 font-semibold">{k.key_prefix}</td>
                              <td className="py-2.5 px-3">
                                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[11px] border border-slate-200">
                                  {k.allowed_ips || '*'}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-slate-500 text-[11px]">
                                {k.last_used_at ? new Date(k.last_used_at * 1000).toLocaleString('th-TH') : 'ยังไม่เคยใช้งาน'}
                              </td>
                              <td className="py-2.5 px-3">
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                  k.is_active
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                    : 'bg-rose-50 text-rose-700 border-rose-200'
                                }`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${k.is_active ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
                                  <span>{k.is_active ? 'เปิดใช้งาน' : 'ระงับ (Revoked)'}</span>
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-right space-x-2">
                                <button
                                  onClick={() => handleToggleKeyStatus(k.id, k.is_active)}
                                  className={`text-[11px] font-medium hover:underline cursor-pointer ${
                                    k.is_active ? 'text-amber-600' : 'text-emerald-600'
                                  }`}
                                >
                                  {k.is_active ? 'ระงับใช้งาน' : 'เปิดใช้งาน'}
                                </button>
                                <button
                                  onClick={() => handleDeleteApiKey(k.id)}
                                  className="text-[11px] text-rose-600 hover:text-rose-800 hover:underline cursor-pointer"
                                >
                                  ลบ
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="6" className="py-8 text-center text-slate-400 italic">
                              ยังไม่มีการสร้าง API Key สำหรับระบบภายนอก กดปุ่ม "สร้าง API Key ใหม่" เพื่อเริ่มต้น
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Developer API Documentation Tab */}
              {adminTab === 'docs' && (
                <div className="space-y-4 text-xs text-slate-700 leading-relaxed">
                  <div className="p-4 rounded-xl bg-blue-50/70 border border-blue-200 text-blue-950 flex items-start gap-3">
                    <BookOpen className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-sm">คู่มือการเชื่อมต่อ ThaiOCR ONNX REST API สำหรับระบบภายนอก</h4>
                      <p className="text-xs text-blue-800 mt-0.5">
                        ระบบภายนอกสามารถส่งคำขอผ่าน HTTP/HTTPS โดยแนบ <code>X-API-Key: ocr_sk_live_...</code> ใน Request Header พร้อมระบุ IP เครื่องที่ตรงกับที่ลงทะเบียนไว้
                      </p>
                    </div>
                  </div>

                  {/* Flow Steps */}
                  <div className="space-y-4">
                    {/* Step 1 */}
                    <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-slate-900">
                        <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs">1</span>
                        <span>ส่งเอกสารเข้ามาทำ OCR (POST /api/ocr/upload)</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        ส่งไฟล์เอกสาร PDF หรือรูปภาพ (PNG, JPG, TIFF) สูงสุด 50MB ผ่าน <code>multipart/form-data</code>
                      </p>
                      <pre className="p-3 bg-slate-900 text-emerald-400 rounded-lg font-mono text-[11px] overflow-x-auto whitespace-pre">
{`# ใช้งานผ่าน HTTPS (TLS 1.3) พอร์ต 8843
curl -k -X POST "https://localhost:8843/api/ocr/upload" \\
  -H "X-API-Key: ocr_sk_live_your_secret_key" \\
  -F "file=@/path/to/document.pdf"`}
                      </pre>
                      <p className="text-[11px] text-slate-500 font-mono">
                        Response: {`{"job_id": "a1b2c3d4e5f6", "filename": "document.pdf", "status": "processing"}`}
                      </p>
                    </div>

                    {/* Step 2 */}
                    <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-slate-900">
                        <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs">2</span>
                        <span>ตรวจสอบสถานะงาน (GET /api/ocr/jobs/{'{job_id}'})</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        ตรวจสอบว่าประมวลผลเสร็จแล้วหรือยัง พร้อมอ่านผลลัพธ์ข้อความ (Text / Markdown) ทันที
                      </p>
                      <pre className="p-3 bg-slate-900 text-emerald-400 rounded-lg font-mono text-[11px] overflow-x-auto whitespace-pre">
{`curl -k -X GET "https://localhost:8843/api/ocr/jobs/a1b2c3d4e5f6" \\
  -H "X-API-Key: ocr_sk_live_your_secret_key"`}
                      </pre>
                      <p className="text-[11px] text-slate-500 font-mono">
                        Response: {`{"id": "a1b2c3d4e5f6", "status": "completed", "page_count": 3, "text": "...", "markdown": "..."}`}
                      </p>
                    </div>

                    {/* Step 3 */}
                    <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-slate-900">
                        <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs">3</span>
                        <span>ดาวน์โหลดไฟล์ผลลัพธ์ (GET /api/ocr/download/{'{job_id}'}/{'{format}'})</span>
                      </div>
                      <p className="text-slate-600 text-[11px]">
                        รองรับรูปแบบ: <code>docx</code> (Word จัดรูปเล่มพร้อมรูป), <code>xlsx</code> (ตาราง Excel), <code>md</code> (Markdown), <code>txt</code> (ข้อความล้วน)
                      </p>
                      <pre className="p-3 bg-slate-900 text-emerald-400 rounded-lg font-mono text-[11px] overflow-x-auto whitespace-pre">
{`# ดาวน์โหลดเอกสาร Word (.DOCX) ผ่าน HTTPS
curl -k -X GET "https://localhost:8843/api/ocr/download/a1b2c3d4e5f6/docx" \\
  -H "X-API-Key: ocr_sk_live_your_secret_key" \\
  --output result.docx`}
                      </pre>
                    </div>

                    {/* Security Notice */}
                    <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-[11px] space-y-1">
                      <p className="font-semibold flex items-center gap-1.5">
                        <ShieldAlert className="w-4 h-4 text-amber-600" />
                        <span>ข้อกำหนดด้านความปลอดภัยเครือข่าย (Security Standards)</span>
                      </p>
                      <ul className="list-disc list-inside space-y-0.5 text-amber-800">
                        <li><strong>HTTPS / Strict TLS 1.3:</strong> เซิร์ฟเวอร์บังคับเชื่อมต่อผ่านพอร์ต 8843 ด้วยโปรโตคอล TLS 1.3 เท่านั้น (ใส่แฟล็ก <code>-k</code> หรือ <code>--insecure</code> ใน cURL หากใช้ Self-signed CA ของระบบ)</li>
                        <li><strong>IP Whitelist Binding:</strong> ทุกคำขอต้องส่งมาจากเครื่องเซิร์ฟเวอร์ที่มี IP Address ตรงกับที่ Admin ระบุไว้ในระบบเท่านั้น</li>
                        <li><strong>Data Retention 72 Hours:</strong> เอกสารต้นฉบับและผลลัพธ์ในระบบจะถูกลบทำลายอัตโนมัติภายใน 3 วัน</li>
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {adminTab === 'security' && (
                <div className="space-y-6">
                  <div className="bg-slate-900 text-white p-5 rounded-xl border border-slate-800 flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-sm flex items-center gap-2">
                        <Shield className="w-4 h-4 text-amber-400" />
                        <span>ตั้งค่าความปลอดภัยขั้นสูงสำหรับ Super Admin (Passkey & 2FA)</span>
                      </h4>
                      <p className="text-xs text-slate-400 mt-1">
                        เลือกเปิด-ปิดการยืนยันตัวตน 2 ชั้น (TOTP Authenticator) และระบบเข้าสู่ระบบด้วย Passkey (WebAuthn / FIDO2) ได้อย่างอิสระ
                      </p>
                    </div>
                  </div>

                  {securityMsg && (
                    <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                      <span>{securityMsg}</span>
                    </div>
                  )}

                  {securityError && (
                    <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{securityError}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Card 1: 2FA TOTP */}
                    <div className="p-5 rounded-xl border border-slate-200 bg-white space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h5 className="font-semibold text-sm text-slate-900">1. ยืนยันตัวตน 2 ชั้น (2FA — TOTP 6 หลัก)</h5>
                          <p className="text-xs text-slate-500 mt-0.5">
                            ใช้แอป Google Authenticator หรือ Microsoft Authenticator สร้างรหัส OTP 6 หลักทุกครั้งที่ Super Admin ล็อกอินด้วยรหัสผ่าน
                          </p>
                        </div>
                        <button
                          type="button"
                          disabled={securityLoading}
                          onClick={() => handleToggleSecuritySetting('totp_enabled', !securitySettings.totp_enabled)}
                          className={`px-3 py-1.5 rounded-full text-xs font-semibold cursor-pointer transition shrink-0 ${
                            securitySettings.totp_enabled
                              ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                              : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                          }`}
                        >
                          {securitySettings.totp_enabled ? 'เปิดใช้งานอยู่ (ON)' : 'ปิดอยู่ (OFF)'}
                        </button>
                      </div>

                      <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-600">สถานะรหัสลับ (TOTP Secret):</span>
                          <span className="font-mono font-semibold text-slate-800">
                            {securitySettings.has_totp_secret ? securitySettings.totp_secret_masked : 'ยังไม่ได้ตั้งค่า'}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={handleSetupTotp}
                          disabled={securityLoading}
                          className="w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition cursor-pointer"
                        >
                          {securitySettings.has_totp_secret ? 'สร้างรหัสลับ 2FA (TOTP) ใหม่' : 'ตั้งค่ารหัส 2FA (TOTP) ครั้งแรก'}
                        </button>
                      </div>

                      {totpSetupData && (
                        <form onSubmit={handleVerifyAndEnableTotp} className="p-4 rounded-xl bg-blue-50/70 border border-blue-200 space-y-3 text-xs">
                          <p className="font-semibold text-blue-950">
                            ขั้นตอนเปิดใช้งาน: นำรหัส Secret ด้านล่างไปเพิ่มในแอป Authenticator แล้วกรอกรหัส 6 หลักเพื่อยืนยัน
                          </p>
                          <div>
                            <label className="block text-[11px] text-slate-600 mb-1">Secret Key (Base32 สำหรับกรอกในแอป):</label>
                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                readOnly
                                value={totpSetupData.secret}
                                className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded font-mono text-xs select-all"
                              />
                              <button
                                type="button"
                                onClick={() => navigator.clipboard.writeText(totpSetupData.secret)}
                                className="px-2.5 py-1.5 bg-slate-800 text-white rounded text-[11px] cursor-pointer shrink-0"
                              >
                                คัดลอก
                              </button>
                            </div>
                          </div>
                          <div>
                            <label className="block text-[11px] text-slate-600 mb-1">OTPAuth URI:</label>
                            <input
                              type="text"
                              readOnly
                              value={totpSetupData.otpauth_uri}
                              className="w-full px-2.5 py-1 bg-white border border-slate-200 rounded font-mono text-[10px] text-slate-500 select-all"
                            />
                          </div>
                          <div className="flex items-center gap-2 pt-1">
                            <input
                              type="text"
                              inputMode="numeric"
                              maxLength={6}
                              required
                              value={totpVerifyCode}
                              onChange={(e) => setTotpVerifyCode(e.target.value)}
                              placeholder="กรอกรหัส OTP 6 หลัก"
                              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono tracking-widest"
                            />
                            <button
                              type="submit"
                              disabled={securityLoading}
                              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-xs shrink-0 cursor-pointer"
                            >
                              ยืนยันและเปิด 2FA
                            </button>
                          </div>
                        </form>
                      )}
                    </div>

                    {/* Card 2: Passkey (WebAuthn) */}
                    <div className="p-5 rounded-xl border border-slate-200 bg-white space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h5 className="font-semibold text-sm text-slate-900">2. ระบบ Passkey (WebAuthn / FIDO2)</h5>
                          <p className="text-xs text-slate-500 mt-0.5">
                            ใช้สแกนลายนิ้วมือ / ใบหน้า (Windows Hello, Touch ID) หรือ Security Key เพื่อเข้าสู่ระบบทันทีโดยไม่ต้องใช้รหัสผ่าน หรือใช้แทนรหัส OTP
                          </p>
                        </div>
                        <button
                          type="button"
                          disabled={securityLoading}
                          onClick={() => handleToggleSecuritySetting('passkey_enabled', !securitySettings.passkey_enabled)}
                          className={`px-3 py-1.5 rounded-full text-xs font-semibold cursor-pointer transition shrink-0 ${
                            securitySettings.passkey_enabled
                              ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                              : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                          }`}
                        >
                          {securitySettings.passkey_enabled ? 'เปิดใช้งานอยู่ (ON)' : 'ปิดอยู่ (OFF)'}
                        </button>
                      </div>

                      <form onSubmit={handleRegisterPasskey} className="flex items-center gap-2">
                        <input
                          type="text"
                          value={newPasskeyName}
                          onChange={(e) => setNewPasskeyName(e.target.value)}
                          placeholder="ชื่ออุปกรณ์ เช่น Windows Hello เครื่อง Admin"
                          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                        />
                        <button
                          type="submit"
                          disabled={securityLoading}
                          className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold shrink-0 cursor-pointer flex items-center gap-1.5"
                        >
                          <Key className="w-3.5 h-3.5 text-amber-400" />
                          <span>ลงทะเบียน Passkey</span>
                        </button>
                      </form>

                      <div className="space-y-2">
                        <p className="text-xs font-medium text-slate-700">
                          อุปกรณ์ Passkey ที่ลงทะเบียนไว้ ({securitySettings.passkeys?.length || 0})
                        </p>
                        {(!securitySettings.passkeys || securitySettings.passkeys.length === 0) ? (
                          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-500 text-center">
                            ยังไม่มี Passkey ที่ลงทะเบียน
                          </div>
                        ) : (
                          <div className="divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
                            {securitySettings.passkeys.map(pk => (
                              <div key={pk.id} className="p-2.5 bg-white flex items-center justify-between text-xs">
                                <div>
                                  <p className="font-semibold text-slate-800">{pk.name}</p>
                                  <p className="text-[10px] text-slate-400 font-mono">
                                    ID: {pk.id.slice(0, 16)}...
                                  </p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleDeletePasskey(pk.id)}
                                  className="px-2.5 py-1 text-rose-600 hover:bg-rose-50 rounded font-medium cursor-pointer"
                                >
                                  ลบ
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
        {/* Upload Dropzone Card */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-6">
            <h2 className="text-base font-semibold text-slate-900 mb-1 flex items-center gap-2">
              <Upload className="w-4 h-4 text-blue-600" />
              <span>อัปโหลดเอกสารเพื่อทำ OCR</span>
            </h2>
            <p className="text-xs text-slate-500 mb-4">
              รองรับไฟล์เอกสาร PDF (ทั้งแนวตั้งและแนวนอน) และไฟล์ภาพ PNG, JPG, JPEG, TIFF (ขนาดสูงสุด 50MB)
            </p>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                isDragging
                  ? 'border-blue-500 bg-blue-50/50 scale-[1.005]'
                  : 'border-slate-300 hover:border-blue-400 bg-slate-50/50 hover:bg-slate-50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleFilesSelected(e.target.files)
                  }
                  e.target.value = ''
                }}
              />

              <div className="max-w-sm mx-auto flex flex-col items-center">
                <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mb-3">
                  <Upload className="w-6 h-6" />
                </div>
                <p className="text-sm font-semibold text-slate-800">
                  ลากไฟล์มาวางที่นี่ หรือ <span className="text-blue-600 hover:underline">เลือกไฟล์จากเครื่อง (รองรับหลายไฟล์)</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  ส่งงานได้ต่อเนื่องโดยไม่ต้องรอคิว หรือเลือกหลายไฟล์พร้อมกัน
                </p>
              </div>
            </div>

            {/* Selected Files Staging List */}
            {selectedFiles.length > 0 && (
              <div className="mt-4 p-4 rounded-xl bg-blue-50/80 border border-blue-200/90 shadow-sm animate-in fade-in">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 pb-2.5 border-b border-blue-200/70">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-blue-600" />
                    <span className="text-xs font-semibold text-slate-800">
                      ไฟล์ที่เลือกเตรียมส่ง ({selectedFiles.length} ไฟล์)
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setSelectedFiles([])}
                      className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-900 transition cursor-pointer"
                    >
                      ยกเลิกทั้งหมด
                    </button>
                    <button
                      onClick={handleStartAll}
                      className="px-4 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm flex items-center space-x-1.5 cursor-pointer"
                    >
                      <span>เริ่มแปลงเอกสาร ({selectedFiles.length} ไฟล์)</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-blue-100 shadow-2xs">
                      <div className="flex items-center space-x-2.5 min-w-0">
                        <span className="w-7 h-7 rounded bg-blue-600 text-white text-[10px] font-bold uppercase flex items-center justify-center shrink-0">
                          {file.name.split('.').pop()}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-slate-900 truncate" title={file.name}>{file.name}</p>
                          <p className="text-[10px] text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                      </div>
                      <button
                        onClick={() => removeSelectedFile(idx)}
                        className="text-slate-400 hover:text-rose-500 transition p-1 cursor-pointer"
                        title="ลบไฟล์นี้"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Active Tasks Live Manager (Multi-Task Queue) */}
            {activeTasks.length > 0 && (
              <div className="mt-4 space-y-2.5 animate-in fade-in">
                <div className="flex items-center justify-between px-1">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                    <Layers className="w-4 h-4 text-amber-500" />
                    <span>งานที่กำลังประมวลผล / เพิ่งเสร็จสิ้น ({activeTasks.length})</span>
                  </div>
                  {activeTasks.some(t => t.status !== 'processing') && (
                    <button
                      onClick={() => setActiveTasks(prev => prev.filter(t => t.status === 'processing'))}
                      className="text-[11px] text-slate-500 hover:text-slate-700 cursor-pointer"
                    >
                      ล้างงานที่เสร็จแล้ว
                    </button>
                  )}
                </div>

                <div className="space-y-2">
                  {activeTasks.map((task) => (
                    <div
                      key={task.taskId}
                      className={`p-3.5 rounded-xl border transition-all ${
                        task.status === 'completed'
                          ? 'bg-emerald-950/80 border-emerald-800 text-white shadow-md'
                          : task.status === 'error'
                          ? 'bg-rose-950/80 border-rose-800 text-white shadow-md'
                          : 'bg-slate-900 border-slate-800 text-white shadow-md'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2 gap-2">
                        <div className="flex items-center space-x-2.5 min-w-0">
                          {task.status === 'processing' && (
                            <RefreshCw className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
                          )}
                          {task.status === 'completed' && (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                          )}
                          {task.status === 'error' && (
                            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                          )}
                          <div className="min-w-0">
                            <span className="font-semibold text-xs text-slate-100 truncate block" title={task.filename}>
                              {task.filename}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {(task.size / 1024 / 1024).toFixed(2)} MB
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {task.status === 'processing' && (
                            <>
                              {task.total_pages > 1 && (
                                <span className="text-[11px] text-slate-400 font-mono">
                                  หน้า {task.page}/{task.total_pages}
                                </span>
                              )}
                              <span className="px-2 py-0.5 rounded-full text-[11px] font-bold font-mono bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                {task.percent}%
                              </span>
                            </>
                          )}
                          {task.status === 'completed' && (
                            <>
                              {task.result?.cached ? (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono font-semibold flex items-center gap-1">
                                  ⚡ แคชความเร็วสูง (0.05s)
                                </span>
                              ) : (
                                <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                                  เสร็จสิ้น ({task.result?.page_count || 1} หน้า)
                                </span>
                              )}
                              <button
                                onClick={() => handleOpenReview(task.result)}
                                className="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1 cursor-pointer transition shadow-2xs"
                                title="เปิดตรวจดูไฟล์ต้นฉบับกับ Markdown"
                              >
                                <Eye className="w-3 h-3" />
                                <span>ตรวจดู</span>
                              </button>
                              <button
                                onClick={() => dismissActiveTask(task.taskId)}
                                className="p-1 rounded text-slate-400 hover:text-white transition cursor-pointer"
                                title="ปิดการแจ้งเตือนนี้"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                          {task.status === 'error' && (
                            <>
                              <span className="text-[11px] text-rose-400 font-medium">ล้มเหลว</span>
                              <button
                                onClick={() => dismissActiveTask(task.taskId)}
                                className="p-1 rounded text-slate-400 hover:text-white transition cursor-pointer"
                                title="ปิดการแจ้งเตือนนี้"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </div>

                      {task.status === 'processing' && (
                        <>
                          <div className="w-full bg-slate-800 rounded-full h-2 p-0.5 overflow-hidden border border-slate-700/80 my-1.5">
                            <div
                              className="bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 h-full rounded-full transition-all duration-300 ease-out"
                              style={{ width: `${Math.max(4, task.percent)}%` }}
                            ></div>
                          </div>
                          <div className="flex items-center justify-between text-[11px] text-slate-400">
                            <span className="truncate">{task.message || 'กำลังประมวลผล...'}</span>
                            <span className="text-[10px] text-emerald-400 font-mono shrink-0 ml-2">● High-Speed Worker</span>
                          </div>
                        </>
                      )}

                      {task.status === 'error' && (
                        <div className="text-[11px] text-rose-300 mt-1">
                          ข้อผิดพลาด: {task.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {ocrError && (
              <div className="mt-4 p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{ocrError}</span>
              </div>
            )}
          </div>
        </div>

        {/* Success Alert Banner: Guides user to the "ตรวจดู" button in history table */}
        {successNotice && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-950 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0 text-emerald-600">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <p className="font-semibold text-xs text-emerald-950">
                  ส่งงานและประมวลผล OCR สำเร็จ: <strong className="font-mono">{successNotice.filename}</strong> ({successNotice.page_count} หน้า, {(successNotice.latency_ms / 1000).toFixed(2)} วินาที)
                </p>
                <p className="text-[11px] text-emerald-700 mt-0.5">
                  ระบบได้บันทึกเอกสารลงในรายการประวัติเรียบร้อยแล้ว ท่านสามารถกดปุ่ม <span className="font-semibold underline">"ตรวจดู"</span> ในตารางด้านล่าง เพื่อเปิดหน้าต่างตรวจผลลัพธ์คู่กับไฟล์ต้นฉบับ
                </p>
              </div>
            </div>
            <button
              onClick={() => handleOpenReview(successNotice)}
              className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition flex items-center space-x-1.5 shrink-0 shadow-sm cursor-pointer"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>ตรวจดู</span>
            </button>
          </div>
        )}

        {/* Recent Jobs Section */}
        {recentJobs.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-3">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-500" />
                <span>ประวัติการประมวลผลล่าสุดของคุณ</span>
              </h3>
              <button
                onClick={() => setShowRetentionModal(true)}
                className="text-amber-700 hover:text-amber-800 text-[11px] font-medium flex items-center gap-1 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 cursor-pointer"
                title="คลิกเพื่อดูนโยบายการลบไฟล์อัตโนมัติ"
              >
                <ShieldAlert className="w-3 h-3 text-amber-600" />
                <span>นโยบายความปลอดภัย: ลบไฟล์ใน 3 วัน</span>
              </button>
            </div>

            {/* 3-Day Retention Policy Warning Banner */}
            <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-900 flex items-center justify-between gap-2">
              <div className="flex items-center space-x-2 text-xs">
                <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>การรักษาความมั่นคงปลอดภัยข้อมูล:</strong> เอกสารต้นฉบับและผลลัพธ์ในระบบจะถูก<strong>ลบอัตโนมัติภายใน 3 วัน (72 ชม.)</strong> หรือท่านสามารถกดปุ่ม <strong>"ลบ"</strong> เพื่อทำลายไฟล์ได้ทันที
                </span>
              </div>
              <button
                onClick={() => setShowRetentionModal(true)}
                className="text-amber-800 hover:text-amber-950 font-semibold text-[11px] underline shrink-0 cursor-pointer"
              >
                ดูรายละเอียด
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 border-y border-slate-200 text-slate-600 uppercase">
                  <tr>
                    <th className="py-2.5 px-3">ชื่อไฟล์</th>
                    <th className="py-2.5 px-3">จำนวนหน้า</th>
                    <th className="py-2.5 px-3">เวลาที่ใช้</th>
                    <th className="py-2.5 px-3">อายุไฟล์คงเหลือ</th>
                    <th className="py-2.5 px-3">สถานะ</th>
                    <th className="py-2.5 px-3 text-right">ตรวจดู / จัดการ</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentJobs.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-2.5 px-3 font-medium text-slate-900">{job.filename}</td>
                      <td className="py-2.5 px-3 text-slate-600">{job.page_count} หน้า</td>
                      <td className="py-2.5 px-3 text-slate-600 font-mono">
                        {(job.latency_ms / 1000).toFixed(2)} วิ
                        {job.latency_ms > 0 && job.latency_ms <= 100 && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded text-[9px] bg-amber-100 text-amber-800 font-sans font-semibold border border-amber-300/80 inline-flex items-center gap-0.5" title="ผลลัพธ์จาก OCR Cache อัตโนมัติ (ไม่ต้องคำนวณซ้ำ)">
                            ⚡ Cache
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200">
                          <Clock className="w-2.5 h-2.5" />
                          <span>{getTimeRemaining(job.created_at)}</span>
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${
                          job.status === 'completed'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : job.status === 'processing'
                            ? 'bg-blue-50 text-blue-700 border-blue-200'
                            : 'bg-rose-50 text-rose-700 border-rose-200'
                        }`}
                        title={job.error_msg || ''}
                        >
                          {job.status === 'completed' && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                          {job.status === 'processing' && <RefreshCw className="w-3 h-3 text-blue-600 animate-spin" />}
                          {job.status === 'failed' && <AlertCircle className="w-3 h-3 text-rose-600" />}
                          <span>
                            {job.status === 'completed'
                              ? 'สำเร็จ'
                              : job.status === 'processing'
                              ? `กำลังทำ ${(() => {
                                  const active = activeTasks.find(t => t.result?.id === job.id || t.filename === job.filename);
                                  const p = active ? active.percent : (job.progress_percent || 0);
                                  return p > 0 ? `${p}%` : '...';
                                })()}`
                              : 'ผิดพลาด'}
                          </span>
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right space-x-2">
                        {job.status === 'completed' ? (
                          <>
                            <button
                              onClick={() => handleOpenReview(job)}
                              className="px-2.5 py-1 rounded bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-[11px] font-medium inline-flex items-center gap-1 cursor-pointer transition mr-1"
                              title="เปิดตรวจดูไฟล์ต้นฉบับกับ Markdown"
                            >
                              <Eye className="w-3 h-3" />
                              <span>ตรวจดู</span>
                            </button>
                            <button
                              onClick={() => handleDownloadWithTicket(job.id, 'docx')}
                              className="text-indigo-600 hover:text-indigo-800 font-medium text-[11px] cursor-pointer"
                              title="ดาวน์โหลดเอกสาร Word (.DOCX)"
                            >
                              .DOCX
                            </button>
                            <span className="text-slate-300">|</span>
                            <button
                              onClick={() => handleDownloadWithTicket(job.id, 'xlsx')}
                              className="text-emerald-600 hover:text-emerald-800 font-medium text-[11px] cursor-pointer"
                              title="ดาวน์โหลดตาราง Excel (.XLSX)"
                            >
                              .XLSX
                            </button>
                            <span className="text-slate-300">|</span>
                            <button
                              onClick={() => handleDownloadWithTicket(job.id, 'md')}
                              className="text-blue-600 hover:text-blue-800 font-medium text-[11px] cursor-pointer"
                              title="ดาวน์โหลด .MD"
                            >
                              .MD
                            </button>
                            <span className="text-slate-300">|</span>
                            <button
                              onClick={() => handleDownloadWithTicket(job.id, 'txt')}
                              className="text-slate-600 hover:text-slate-800 font-medium text-[11px] cursor-pointer"
                              title="ดาวน์โหลด .TXT"
                            >
                              .TXT
                            </button>
                            <span className="text-slate-300">|</span>
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
                          </>
                        ) : job.status === 'processing' ? (
                          <span className="text-xs text-blue-600 font-medium inline-flex items-center gap-1 mr-2">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            <span>กำลังประมวลผล...</span>
                          </span>
                        ) : (
                          <span className="text-xs text-rose-500 font-mono truncate mr-2 max-w-[140px] inline-block" title={job.error_msg || ''}>
                            {job.error_msg || 'ล้มเหลว'}
                          </span>
                        )}
                        <button
                          onClick={() => setDeleteConfirmJob(job)}
                          className="p-1 px-1.5 rounded text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition cursor-pointer inline-flex items-center gap-0.5 text-[11px] font-medium"
                          title="ลบไฟล์และงานนี้ออกจากระบบทันที"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>ลบ</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
          </>
        )}
      </main>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-slate-900 text-white p-6 pb-5">
              <div className="flex items-center space-x-3 mb-2">
                <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold text-sm">
                  OCR
                </div>
                <div>
                  <h3 className="font-semibold text-base leading-tight">เข้าสู่ระบบ OCR Portal</h3>
                  <p className="text-xs text-slate-400">ThaiOCR System (Directory Service)</p>
                </div>
              </div>
            </div>

            {mfaStep ? (
              <form onSubmit={handleVerify2FA} className="p-6 space-y-4">
                {loginError && (
                  <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{loginError}</span>
                  </div>
                )}

                <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-900 text-xs">
                  <p className="font-semibold">ยืนยันตัวตน 2 ชั้น (2FA Security)</p>
                  <p className="text-[11px] text-blue-700 mt-0.5">
                    กรุณากรอกรหัส OTP 6 หลักจากแอป Authenticator ของผู้ดูแลระบบ
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">รหัส OTP 6 หลัก</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    required
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    placeholder="000000"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono tracking-widest text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {mfaStep.methods?.includes('passkey') && (
                  <button
                    type="button"
                    disabled={loginLoading}
                    onClick={handlePasskeyLogin}
                    className="w-full py-2 px-4 rounded-lg border border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-semibold flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Key className="w-4 h-4 text-amber-500" />
                    <span>ยืนยันด้วย Passkey แทนรหัส OTP</span>
                  </button>
                )}

                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => { setMfaStep(null); setMfaCode(''); setLoginError(''); }}
                    className="px-3 py-2 text-xs font-medium text-slate-600 hover:text-slate-900 cursor-pointer"
                  >
                    ย้อนกลับ
                  </button>
                  <button
                    type="submit"
                    disabled={loginLoading}
                    className="px-5 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm cursor-pointer disabled:opacity-50"
                  >
                    {loginLoading ? 'กำลังตรวจสอบ...' : 'ยืนยันรหัส 2FA'}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleLogin} className="p-6 space-y-4">
                {loginError && (
                  <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{loginError}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">ชื่อผู้ใช้งาน (LDAP / Admin)</label>
                  <input
                    type="text"
                    required
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    placeholder="ชื่อผู้ใช้งาน"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">รหัสผ่าน</label>
                  <input
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {publicPasskeyEnabled && (
                  <div className="pt-1">
                    <button
                      type="button"
                      disabled={loginLoading}
                      onClick={handlePasskeyLogin}
                      className="w-full py-2.5 px-4 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer shadow-sm"
                    >
                      <Key className="w-4 h-4 text-amber-400" />
                      <span>เข้าสู่ระบบด้วย Passkey (Super Admin)</span>
                    </button>
                  </div>
                )}

                <div className="flex items-center justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowLoginModal(false)}
                    className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-900 cursor-pointer"
                  >
                    ยกเลิก
                  </button>
                  <button
                    type="submit"
                    disabled={loginLoading}
                    className="px-5 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm cursor-pointer disabled:opacity-50"
                  >
                    {loginLoading ? 'กำลังตรวจสอบสิทธิ์...' : 'เข้าสู่ระบบ'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Create New API Key Modal */}
      {showCreateKeyModal && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <Key className="w-5 h-5 text-amber-400" />
                <h3 className="font-bold text-sm leading-tight">สร้าง API Key สำหรับระบบภายนอก</h3>
              </div>
              <button
                onClick={() => { setShowCreateKeyModal(false); setCreatedKeySecret(null); }}
                className="text-slate-400 hover:text-white transition cursor-pointer p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              {createdKeySecret ? (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                    <p className="font-semibold flex items-center gap-1.5 mb-1 text-amber-950">
                      <ShieldAlert className="w-4 h-4 text-amber-600" />
                      <span>บันทึก API Key นี้ทันที</span>
                    </p>
                    <p className="text-[11px] text-amber-800">
                      ระบบจะแสดงคีย์ลับฉบับเต็มเพียงครั้งเดียวเท่านั้น หากทำสูญหายจะต้องทำการสร้าง Key ใหม่
                    </p>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">Generated Secret API Key</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly
                        value={createdKeySecret}
                        className="w-full px-3 py-2 bg-slate-100 border border-slate-300 rounded-lg text-xs font-mono select-all text-slate-800 font-semibold"
                      />
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(createdKeySecret);
                          setKeyCopied(true);
                          setTimeout(() => setKeyCopied(false), 2000);
                        }}
                        className="px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium flex items-center gap-1 cursor-pointer shrink-0 shadow-sm transition"
                      >
                        {keyCopied ? <Check className="w-4 h-4 text-emerald-300" /> : <Copy className="w-4 h-4" />}
                        <span>{keyCopied ? 'คัดลอกแล้ว' : 'คัดลอก'}</span>
                      </button>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex justify-end">
                    <button
                      onClick={() => { setShowCreateKeyModal(false); setCreatedKeySecret(null); }}
                      className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-medium cursor-pointer"
                    >
                      เสร็จสิ้น & ปิดหน้าต่าง
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleCreateApiKey} className="space-y-4 text-xs">
                  <div>
                    <label className="block font-medium text-slate-700 mb-1">
                      ชื่อระบบผู้ขอใช้งาน (Service Name) <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="เช่น ระบบสารบรรณอิเล็กทรอนิกส์, ระบบรับเรื่องร้องเรียน"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-slate-700 mb-1">
                      IP Whitelist (หมายเลข IP เซิร์ฟเวอร์ต้นทาง) <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="เช่น 192.168.10.50, 10.0.5.21 (หรือ * หากไม่จำกัด)"
                      value={newKeyIps}
                      onChange={(e) => setNewKeyIps(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono focus:ring-1 focus:ring-blue-500"
                    />
                    <p className="text-[11px] text-slate-500 mt-1">
                      ระบบจะยอมรับคำขอเฉพาะจากเครื่องที่มี IP Address ตรงกับที่ระบุเท่านั้น คั่นด้วยจุลภาค (,)
                    </p>
                  </div>

                  <div>
                    <label className="block font-medium text-slate-700 mb-1">อายุการใช้งาน (วัน)</label>
                    <select
                      value={newKeyExpiry}
                      onChange={(e) => setNewKeyExpiry(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white focus:ring-1 focus:ring-blue-500"
                    >
                      <option value="90">90 วัน (3 เดือน)</option>
                      <option value="180">180 วัน (6 เดือน)</option>
                      <option value="365">365 วัน (1 ปี)</option>
                      <option value="730">730 วัน (2 ปี)</option>
                    </select>
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowCreateKeyModal(false)}
                      className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer"
                    >
                      ยกเลิก
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer shadow-sm transition"
                    >
                      สร้าง API Key
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      {showChangePasswordModal && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <Key className="w-5 h-5 text-amber-400" />
                <div>
                  <h3 className="font-bold text-sm leading-tight">เปลี่ยนรหัสผ่าน</h3>
                  <p className="text-[11px] text-slate-400">บัญชี: {currentUser?.username}</p>
                </div>
              </div>
              <button
                onClick={() => setShowChangePasswordModal(false)}
                className="text-slate-400 hover:text-white transition cursor-pointer p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleChangePassword} className="p-6 space-y-4 text-xs">
              {changePasswordError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{changePasswordError}</span>
                </div>
              )}

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  รหัสผ่านเดิม <span className="text-rose-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  placeholder="กรอกรหัสผ่านปัจจุบัน"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  รหัสผ่านใหม่ <span className="text-rose-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  placeholder="ความยาวอย่างน้อย 6 ตัวอักษร"
                  value={newPasswordVal}
                  onChange={(e) => setNewPasswordVal(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  ยืนยันรหัสผ่านใหม่ <span className="text-rose-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  placeholder="กรอกรหัสผ่านใหม่อีกครั้ง"
                  value={confirmPasswordVal}
                  onChange={(e) => setConfirmPasswordVal(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowChangePasswordModal(false)}
                  className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  ยกเลิก
                </button>
                <button
                  type="submit"
                  disabled={changePasswordLoading}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer shadow-sm transition disabled:opacity-50"
                >
                  {changePasswordLoading ? 'กำลังบันทึก...' : 'บันทึกรหัสผ่านใหม่'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Admin Reset User Password Modal */}
      {resetTargetUser && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <Key className="w-5 h-5 text-amber-400" />
                <div>
                  <h3 className="font-bold text-sm leading-tight">รีเซ็ตรหัสผ่านผู้ใช้</h3>
                  <p className="text-[11px] text-slate-400">สำหรับผู้ใช้: <span className="font-mono text-amber-300">{resetTargetUser}</span></p>
                </div>
              </div>
              <button
                onClick={() => { setResetTargetUser(null); setAdminNewPassword(''); }}
                className="text-slate-400 hover:text-white transition cursor-pointer p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAdminResetPassword} className="p-6 space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
                <p>
                  <strong>คำแนะนำผู้ดูแลระบบ:</strong> การตั้งรหัสผ่านใหม่จะมีผลทันที และผู้ใช้จะต้องใช้รหัสผ่านใหม่นี้ในการเข้าสู่ระบบ
                </p>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  รหัสผ่านใหม่สำหรับ {resetTargetUser} <span className="text-rose-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  placeholder="ความยาวอย่างน้อย 6 ตัวอักษร"
                  value={adminNewPassword}
                  onChange={(e) => setAdminNewPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => { setResetTargetUser(null); setAdminNewPassword(''); }}
                  className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  ยกเลิก
                </button>
                <button
                  type="submit"
                  disabled={resetPasswordLoading}
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-medium cursor-pointer shadow-sm transition disabled:opacity-50"
                >
                  {resetPasswordLoading ? 'กำลังบันทึก...' : 'บันทึกรหัสผ่านใหม่'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create New Local User Modal */}
      {showCreateUserModal && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <User className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-sm leading-tight">สร้างผู้ใช้งานใหม่ (Local User)</h3>
              </div>
              <button
                onClick={() => setShowCreateUserModal(false)}
                className="text-slate-400 hover:text-white transition cursor-pointer p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateLocalUser} className="p-6 space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-[11px] leading-relaxed">
                <p>
                  <strong>ข้อกำหนดสิทธิ์:</strong> บัญชี Local User นี้จะใช้สำหรับล็อกอินเข้า Web Portal เพื่อทำ OCR เท่านั้น <strong>จะไม่มีสิทธิ์เข้าถึง M2M REST API</strong> (หากต้องการใช้งานข้ามระบบ ให้ Admin สร้าง API Key ให้แทน)
                </p>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  ชื่อผู้ใช้งาน (Username) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="เช่น somchai_s, user01"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  รหัสผ่าน (Password) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  placeholder="อย่างน้อย 6 ตัวอักษร"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">ชื่อ-นามสกุล / สังกัด (Display Name)</label>
                <input
                  type="text"
                  placeholder="เช่น นายสมชาย สายใจ (กองคดี 1)"
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">ระดับสิทธิ์ (Role)</label>
                <select
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs bg-white focus:ring-1 focus:ring-blue-500"
                >
                  <option value="user">ผู้ใช้งานทั่วไป (Web Portal Only)</option>
                  <option value="admin">ผู้ดูแลระบบ (Admin)</option>
                </select>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateUserModal(false)}
                  className="px-3.5 py-2 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  ยกเลิก
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium cursor-pointer shadow-sm transition"
                >
                  บันทึกผู้ใช้
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Review & Compare Modal (เกือบเต็มจอ, แบ่ง 2 ซีก ซ้าย-ขวา) */}
      {reviewModalOpen && reviewJob && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-2 sm:p-4 animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl w-full h-full max-w-[98vw] max-h-[96vh] flex flex-col overflow-hidden text-white">
            {/* Modal Header */}
            <div className="bg-slate-950 px-5 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                  <Split className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-sm leading-tight text-slate-100">
                      ตรวจดูเอกสารต้นฉบับกับผลลัพธ์ Markdown
                    </h3>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-mono">
                      {reviewJob.filename}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {reviewJob.page_count} หน้า • {(reviewJob.latency_ms / 1000).toFixed(2)}s
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    ซีกซ้าย: เอกสารต้นฉบับ (พร้อมระบบ Zoom) | ซีกขวา: ผลลัพธ์ Markdown พร้อมกล่องแก้ไข
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {/* Save status notification */}
                {reviewSaveStatus === 'saved' && (
                  <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium bg-emerald-950/60 px-2.5 py-1 rounded border border-emerald-700/50">
                    <Check className="w-3.5 h-3.5" />
                    <span>บันทึก Markdown แล้ว</span>
                  </span>
                )}

                <button
                  onClick={handleSaveReviewMarkdown}
                  disabled={reviewSaving}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50 shadow-sm"
                  title="บันทึกการแก้ไข Markdown"
                >
                  {reviewSaving ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  <span>{reviewSaving ? 'กำลังบันทึก...' : 'บันทึก Markdown'}</span>
                </button>

                <div className="flex items-center space-x-1 bg-slate-800/80 p-0.5 rounded-lg border border-slate-700">
                  <span className="text-[11px] text-slate-400 px-2 font-medium">ส่งออก:</span>
                  <button
                    onClick={() => handleDownloadExport('docx')}
                    disabled={exportLoading === 'docx'}
                    className="px-2.5 py-1 rounded text-xs font-medium bg-indigo-600/90 hover:bg-indigo-500 text-white transition flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                    title="ดาวน์โหลด Word (.DOCX) พร้อมรูปและตารางเสมือนต้นฉบับ"
                  >
                    {exportLoading === 'docx' ? <RefreshCw className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
                    <span>Word (.DOCX)</span>
                  </button>

                  <button
                    onClick={() => handleDownloadExport('xlsx')}
                    disabled={exportLoading === 'xlsx'}
                    className="px-2.5 py-1 rounded text-xs font-medium bg-emerald-700 hover:bg-emerald-600 text-white transition flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                    title="ดาวน์โหลด Excel (.XLSX) จัดตารางข้อมูล"
                  >
                    {exportLoading === 'xlsx' ? <RefreshCw className="w-3 h-3 animate-spin" /> : <FileSpreadsheet className="w-3 h-3" />}
                    <span>Excel (.XLSX)</span>
                  </button>

                  <button
                    onClick={() => handleDownloadExport('md')}
                    className="px-2 py-1 rounded text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-200 transition flex items-center space-x-1 cursor-pointer"
                    title="ดาวน์โหลดไฟล์ .MD"
                  >
                    <Download className="w-3 h-3" />
                    <span>.MD</span>
                  </button>
                </div>

                <button
                  onClick={() => setDeleteConfirmJob(reviewJob)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-950/60 hover:bg-rose-600 text-rose-300 hover:text-white border border-rose-700/60 transition flex items-center space-x-1 cursor-pointer"
                  title="ลบไฟล์ต้นฉบับและผลลัพธ์ของงานนี้ออกจากระบบทันที"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>ลบงานนี้</span>
                </button>

                <button
                  onClick={() => setReviewModalOpen(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
                  title="ปิดหน้าต่าง"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Split Screen Container (50% Left / 50% Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 flex-1 min-h-0 divide-y lg:divide-y-0 lg:divide-x divide-slate-800">

              {/* LEFT SIDE: Source Document Viewer + Zoom Controls */}
              <div className="flex flex-col h-full min-h-0 bg-slate-950">
                {/* Left Toolbar */}
                <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0 text-xs">
                  <div className="flex items-center space-x-2 text-slate-300 font-medium">
                    <FileText className="w-4 h-4 text-blue-400" />
                    <span>ไฟล์ต้นฉบับ ({reviewJob.file_type?.toUpperCase()})</span>
                    {imageNaturalSize.width > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono hidden sm:inline-block">
                        {imageNaturalSize.width} × {imageNaturalSize.height} px
                      </span>
                    )}
                  </div>

                  {/* Zoom Toolbar */}
                  <div className="flex items-center space-x-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
                    <button
                      onClick={() => {
                        setReviewZoom(z => Math.max(25, z - 25))
                        setZoomMode('custom')
                      }}
                      className="p-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition cursor-pointer"
                      title="ซูมออก (-25%)"
                    >
                      <ZoomOut className="w-3.5 h-3.5" />
                    </button>

                    <span className="text-[11px] font-mono text-amber-300 px-1.5 min-w-[46px] text-center select-none">
                      {zoomMode === 'actual' ? '1:1' : `${reviewZoom}%`}
                    </span>

                    <button
                      onClick={() => {
                        setReviewZoom(z => Math.min(400, z + 25))
                        setZoomMode('custom')
                      }}
                      className="p-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition cursor-pointer"
                      title="ซูมเข้า (+25%)"
                    >
                      <ZoomIn className="w-3.5 h-3.5" />
                    </button>

                    <div className="w-[1px] h-3 bg-slate-800 mx-1"></div>

                    <button
                      onClick={() => {
                        setReviewZoom(100)
                        setZoomMode('fit')
                      }}
                      className={`px-2 py-0.5 rounded text-[11px] transition cursor-pointer ${
                        zoomMode === 'fit' && reviewZoom === 100
                          ? 'bg-blue-600/80 text-white font-medium'
                          : 'hover:bg-slate-800 text-slate-300 hover:text-white'
                      }`}
                      title="ปรับรูปภาพให้พอดีกับความกว้างของกรอบ (Fit Width)"
                    >
                      พอดีกรอบ
                    </button>

                    <button
                      onClick={() => {
                        setZoomMode('actual')
                      }}
                      className={`px-2 py-0.5 rounded text-[11px] transition cursor-pointer ${
                        zoomMode === 'actual'
                          ? 'bg-blue-600/80 text-white font-medium'
                          : 'hover:bg-slate-800 text-slate-300 hover:text-white'
                      }`}
                      title="แสดงขนาดจริงของรูปภาพ (1:1 Native Resolution)"
                    >
                      1:1
                    </button>

                    <button
                      onClick={() => {
                        setReviewZoom(100)
                        setZoomMode('fit')
                      }}
                      className="p-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition cursor-pointer"
                      title="รีเซ็ตเป็นพอดีกรอบ"
                    >
                      <RotateCcw className="w-3 h-3" />
                    </button>

                    {reviewSourceUrl && (
                      <a
                        href={reviewSourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition cursor-pointer ml-1"
                        title="เปิดไฟล์ในแท็บใหม่"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>

                {/* Left Viewer Viewport */}
                <div
                  className="flex-1 min-h-0 overflow-auto p-4 flex items-start justify-center relative bg-slate-950"
                  onWheel={(e) => {
                    if (e.ctrlKey) {
                      e.preventDefault()
                      if (e.deltaY < 0) {
                        setReviewZoom(z => Math.min(400, z + 15))
                        setZoomMode('custom')
                      } else {
                        setReviewZoom(z => Math.max(25, z - 15))
                        setZoomMode('custom')
                      }
                    }
                  }}
                >
                  {reviewJob.file_type?.toLowerCase() === 'pdf' ? (
                    <div className="w-full h-full flex flex-col">
                      {reviewSourceLoading ? (
                        <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                          <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
                          <span className="text-xs">กำลังโหลดเอกสาร PDF...</span>
                        </div>
                      ) : reviewSourceError ? (
                        <div className="flex flex-col items-center justify-center h-full text-rose-400 gap-2 p-4 text-center">
                          <AlertCircle className="w-6 h-6" />
                          <span className="text-xs">{reviewSourceError}</span>
                          <button
                            onClick={() => fetchSourceTicket(reviewJob.id)}
                            className="mt-2 px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-xs transition cursor-pointer"
                          >
                            ลองใหม่อีกครั้ง
                          </button>
                        </div>
                      ) : reviewSourceUrl ? (
                        <iframe
                          src={`${reviewSourceUrl}#zoom=${reviewZoom}`}
                          className="w-full h-full rounded-lg border border-slate-800 bg-slate-900"
                          title={reviewJob.filename}
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-xs text-slate-500">
                          ไม่พบเอกสารต้นฉบับ
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="w-full h-full overflow-auto flex items-start justify-center">
                      {reviewSourceLoading ? (
                        <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                          <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
                          <span className="text-xs">กำลังโหลดรูปภาพต้นฉบับ...</span>
                        </div>
                      ) : reviewSourceError ? (
                        <div className="flex flex-col items-center justify-center h-full text-rose-400 gap-2 p-4 text-center">
                          <AlertCircle className="w-6 h-6" />
                          <span className="text-xs">{reviewSourceError}</span>
                          <button
                            onClick={() => fetchSourceTicket(reviewJob.id)}
                            className="mt-2 px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-xs transition cursor-pointer"
                          >
                            ลองใหม่อีกครั้ง
                          </button>
                        </div>
                      ) : reviewSourceUrl ? (
                        <div className="w-full flex items-start justify-center">
                          <img
                            src={reviewSourceUrl}
                            alt={reviewJob.filename}
                            onLoad={(e) => {
                              setImageNaturalSize({
                                width: e.target.naturalWidth,
                                height: e.target.naturalHeight
                              })
                            }}
                            onError={() => {
                              setReviewSourceError('ไม่สามารถโหลดภาพต้นฉบับได้ (ตั๋วอาจหมดอายุหรือไม่มีไฟล์)')
                            }}
                            style={{
                              width: zoomMode === 'actual' ? 'auto' : `${reviewZoom}%`,
                              maxWidth: zoomMode === 'actual' ? 'none' : (reviewZoom <= 100 ? '100%' : 'none'),
                              height: 'auto',
                              objectFit: 'contain',
                              transition: 'width 0.12s ease-out'
                            }}
                            className="shadow-2xl rounded border border-slate-700/80 block select-none"
                          />
                        </div>
                      ) : (
                        <div className="flex items-center justify-center h-full text-xs text-slate-500">
                          ไม่พบรูปภาพต้นฉบับ
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* RIGHT SIDE: Markdown Review, Editor, & Safe Preview */}
              <div className="flex flex-col h-full min-h-0 bg-slate-900">
                {/* Right Toolbar */}
                <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0 text-xs">
                  {/* Mode switcher tabs */}
                  <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      onClick={() => setReviewMode('edit')}
                      className={`px-2.5 py-1 rounded font-medium transition cursor-pointer flex items-center gap-1 ${
                        reviewMode === 'edit' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Edit3 className="w-3 h-3" />
                      <span>แก้ไข (Editor)</span>
                    </button>
                    <button
                      onClick={() => setReviewMode('split')}
                      className={`px-2.5 py-1 rounded font-medium transition cursor-pointer flex items-center gap-1 ${
                        reviewMode === 'split' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Split className="w-3 h-3" />
                      <span>แยกหน้า (Split)</span>
                    </button>
                    <button
                      onClick={() => setReviewMode('preview')}
                      className={`px-2.5 py-1 rounded font-medium transition cursor-pointer flex items-center gap-1 ${
                        reviewMode === 'preview' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>แสดงผล (Preview)</span>
                    </button>
                  </div>

                  <div className="flex items-center space-x-2">
                    {/* Toggle Thai ⇄ Arabic Numerals */}
                    <button
                      onClick={handleToggleNumerals}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs flex items-center gap-1.5 transition cursor-pointer border border-slate-700 hover:border-slate-600 shadow-2xs group"
                      title="สลับการแปลงตัวเลขทั้งเอกสาร ระหว่างเลขไทย (๑ ๒ ๓) กับเลขอารบิก (1 2 3)"
                    >
                      <span className="font-mono font-bold text-[10px] bg-slate-950 px-1 py-0.5 rounded border border-slate-700 text-amber-300 group-hover:text-amber-200">
                        ๑๒๓ ⇄ 123
                      </span>
                      <span className="hidden sm:inline text-[11px] text-slate-300">สลับเลขไทย/อารบิก</span>
                    </button>

                    <button
                      onClick={handleCopyReviewMarkdown}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1 transition cursor-pointer border border-slate-700"
                      title="คัดลอกข้อความ Markdown"
                    >
                      {reviewCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{reviewCopied ? 'คัดลอกแล้ว' : 'คัดลอก'}</span>
                    </button>

                    <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400">
                      <Shield className="w-3 h-3" />
                      <span>Safe Sandbox (No Script Exec)</span>
                    </div>
                  </div>
                </div>

                {/* Right Content Area: depends on reviewMode */}
                <div className="flex-1 min-h-0 flex flex-col p-3 overflow-hidden">
                  {reviewMode === 'edit' && (
                    <div className="flex-1 min-h-0 flex flex-col">
                      <div className="text-[11px] text-slate-400 mb-1 flex justify-between">
                        <span>กล่องแก้ไขเนื้อหา Markdown (พิมพ์หรือแก้ไขข้อความที่ถอดความได้)</span>
                        <span className="font-mono">{reviewMarkdown.length} อักขระ</span>
                      </div>
                      <textarea
                        value={reviewMarkdown}
                        onChange={(e) => setReviewMarkdown(e.target.value)}
                        placeholder="พิมพ์หรือแก้ไข Markdown..."
                        className="flex-1 min-h-0 w-full p-4 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed border border-slate-800 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                      />
                    </div>
                  )}

                  {reviewMode === 'preview' && (
                    <div className="flex-1 min-h-0 overflow-auto border border-slate-800 rounded-xl bg-slate-950 p-2">
                      <SafeMarkdownViewer content={reviewMarkdown} />
                    </div>
                  )}

                  {reviewMode === 'split' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 flex-1 min-h-0">
                      {/* Sub Left: Editor */}
                      <div className="flex flex-col h-full min-h-0">
                        <div className="text-[11px] text-slate-400 mb-1 flex justify-between">
                          <span>แก้ไขข้อความ Markdown</span>
                          <span className="font-mono">{reviewMarkdown.length} ตัวอักษร</span>
                        </div>
                        <textarea
                          value={reviewMarkdown}
                          onChange={(e) => setReviewMarkdown(e.target.value)}
                          className="flex-1 min-h-0 w-full p-3 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed border border-slate-800 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                        />
                      </div>

                      {/* Sub Right: Live Safe Preview */}
                      <div className="flex flex-col h-full min-h-0">
                        <div className="text-[11px] text-slate-400 mb-1">
                          <span>ตัวอย่างผลลัพธ์จัดรูปเล่ม (Live Safe Render)</span>
                        </div>
                        <div className="flex-1 min-h-0 overflow-auto border border-slate-800 rounded-xl bg-slate-950 p-2">
                          <SafeMarkdownViewer content={reviewMarkdown} />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer bar */}
                <div className="px-4 py-2 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    <span>ระบบรองรับการแสดงผลตาราง Markdown, หัวข้อ และข้อความภาษาไทย</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {reviewOriginalMarkdown !== reviewMarkdown && (
                      <button
                        onClick={() => setReviewMarkdown(reviewOriginalMarkdown)}
                        className="text-amber-400 hover:underline cursor-pointer"
                      >
                        คืนค่าเดิม (Reset changes)
                      </button>
                    )}
                  </div>
                </div>

              </div>

            </div>
          </div>
        </div>
      )}

      {/* 3-Day Data Retention Policy Warning Modal */}
      {showRetentionModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-amber-500 text-slate-950 p-5 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <ShieldAlert className="w-5 h-5 text-slate-950" />
                <h3 className="font-bold text-base leading-tight">นโยบายความมั่นคงปลอดภัยและการลบข้อมูล (3 วัน)</h3>
              </div>
              <button
                onClick={() => setShowRetentionModal(false)}
                className="text-slate-900 hover:text-white transition cursor-pointer p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs text-slate-700 leading-relaxed">
              <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <strong>เอกสารราชการทั้งหมดจะถูกลบถาวรภายใน 72 ชั่วโมง</strong>
                  <p className="mt-1 text-[11px] text-amber-800">
                    เพื่อป้องกันการรั่วไหลของข้อมูลลับและข้อมูลธุรกรรมทางการเงิน ไฟล์ต้นฉบับ (PDF / รูปภาพ) และผลลัพธ์ (Markdown / Plain Text) จะถูกลบออกจากระบบจัดเก็บอัตโนมัติเมื่อครบ 3 วัน
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold text-slate-900">คำแนะนำสำหรับผู้ใช้งาน:</h4>
                <ul className="list-disc list-inside space-y-1 text-slate-600 pl-1">
                  <li>กรุณาดาวน์โหลดไฟล์ผลลัพธ์ (<strong>.MD</strong> หรือ <strong>.TXT</strong>) เก็บไว้ในเครื่องคอมพิวเตอร์ของท่านทันทีหลังการประมวลผล</li>
                  <li>หากงานเอกสารใดเสร็จสิ้นแล้ว ท่านสามารถกดปุ่ม <strong>"ลบ"</strong> ในตารางประวัติเพื่อทำลายข้อมูลออกจากระบบได้ทันทีโดยไม่ต้องรอให้ครบ 3 วัน</li>
                  <li>เมื่อเอกสารครบ 3 วัน ระบบจะกวาดล้างทั้งไฟล์และประวัติการทำงานออกจากฐานข้อมูลอย่างสมบูรณ์</li>
                </ul>
              </div>

              <div className="pt-3 border-t border-slate-200 flex justify-end">
                <button
                  onClick={() => setShowRetentionModal(false)}
                  className="px-5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition cursor-pointer"
                >
                  รับทราบนโยบาย
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmJob && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="bg-rose-600 text-white p-5 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <Trash2 className="w-5 h-5 text-white" />
                <h3 className="font-bold text-base leading-tight">ยืนยันการลบเอกสารและงาน OCR</h3>
              </div>
              <button
                onClick={() => setDeleteConfirmJob(null)}
                className="text-rose-200 hover:text-white transition cursor-pointer p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs text-slate-700">
              <p>ท่านต้องการลบเอกสารต่อไปนี้ออกจากระบบใช่หรือไม่?</p>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="font-semibold text-slate-900 text-sm truncate">{deleteConfirmJob.filename}</div>
                <div className="text-[11px] text-slate-500 mt-1 flex gap-3">
                  <span>Job ID: <strong className="font-mono text-slate-700">{deleteConfirmJob.id}</strong></span>
                  <span>•</span>
                  <span>จำนวน: <strong>{deleteConfirmJob.page_count} หน้า</strong></span>
                </div>
              </div>

              <div className="p-3 bg-rose-50 rounded-lg border border-rose-200 text-rose-800 text-[11px] flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span>
                  <strong>คำเตือน:</strong> ไฟล์ต้นฉบับและผลลัพธ์ OCR ทั้งหมดจะถูกลบทันทีอย่างถาวร ไม่สามารถกู้คืนได้
                </span>
              </div>

              <div className="pt-2 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setDeleteConfirmJob(null)}
                  disabled={isDeleting}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition font-medium cursor-pointer"
                >
                  ยกเลิก
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteJob(deleteConfirmJob.id)}
                  disabled={isDeleting}
                  className="px-5 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold transition cursor-pointer disabled:opacity-50 flex items-center space-x-1.5 shadow-sm"
                >
                  {isDeleting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>กำลังลบข้อมูล...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>ยืนยันการลบถาวร</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* OCR Terms & Disclaimer Confirmation Modal */}
      {showDisclaimerModal && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="bg-slate-900 text-white p-5 pb-4 border-b border-slate-800 flex items-center justify-between shrink-0">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-base leading-tight text-white">
                    ข้อตกลงและคำชี้แจงการใช้งานระบบแปลงเอกสาร (OCR)
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    ThaiOCR ONNX System (ระบบประมวลผลข้อความ OCR)
                  </p>
                </div>
              </div>
              <button
                onClick={handleDeclineDisclaimer}
                className="text-slate-400 hover:text-white transition cursor-pointer p-1 rounded-lg"
                title="ปิดหน้าต่าง"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-4 text-xs text-slate-700 leading-relaxed">
              {/* Target Files Summary */}
              <div className="p-3 bg-blue-50/70 rounded-xl border border-blue-200/80 flex items-center justify-between gap-2">
                <div className="flex items-center space-x-2 min-w-0">
                  <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                  <span className="font-medium text-slate-800 text-[11px] truncate">
                    เอกสารที่ส่งประมวลผล ({disclaimerFiles.length} ไฟล์):{' '}
                    <strong className="text-blue-700 font-mono">
                      {disclaimerFiles.map(f => f.name).join(', ')}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Legal & Operational Notices */}
              <div className="space-y-3">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2.5">
                  <div className="flex items-start gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">๑</span>
                    <div>
                      <strong className="text-slate-900 block text-xs">ลักษณะและวัตถุประสงค์ของเทคโนโลยี OCR:</strong>
                      <p className="text-slate-600 mt-0.5 text-[11px]">
                        การแปลง OCR (Optical Character Recognition) คือการรู้จำอักขระจากภาพเอกสารสแกนเพื่อแปลงเป็นชุดข้อมูลดิจิทัลที่คอมพิวเตอร์สามารถสืบค้นและนำไปประมวลผลต่อได้ (Machine-Readable Text) มิใช่การจัดพิมพ์เอกสารจำลองต้นฉบับใหม่
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 pt-2 border-t border-slate-200/60">
                    <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">๒</span>
                    <div>
                      <strong className="text-slate-900 block text-xs">ข้อจำกัดด้านการจัดวางรูปเล่มและตาราง:</strong>
                      <p className="text-slate-600 mt-0.5 text-[11px]">
                        ระบบไม่สามารถจัดวางรูปแบบ หน้ากระดาษ ตำแหน่งตาราง หรือระยะบรรทัดให้ตรงกับเอกสารต้นฉบับได้ 100% โดยผลลัพธ์จะถูกจัดระเบียบในโครงสร้าง Markdown สำหรับนำไปจัดทำรูปเล่มต่อ
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 pt-2 border-t border-slate-200/60">
                    <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-800 font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">๓</span>
                    <div>
                      <strong className="text-amber-950 block text-xs">หน้าที่ในการตรวจสอบและสอบทาน (Mandatory Verification):</strong>
                      <p className="text-amber-900 mt-0.5 text-[11px]">
                        ความถูกต้องแม่นยำขึ้นอยู่กับความคมชัดของเอกสารต้นฉบับ ผลลัพธ์อาจมีอักขระหรือตัวเลขคลาดเคลื่อนได้ <strong>ผู้ใช้งานจำเป็นต้องตรวจสอบและสอบทาน (Review & Verify) ความถูกต้องกับเอกสารต้นฉบับก่อนนำข้อความไปใช้อ้างอิงหรือปฏิบัติราชการทุกครั้ง</strong>
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 pt-2 border-t border-slate-200/60">
                    <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-800 font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">๔</span>
                    <div>
                      <strong className="text-slate-900 block text-xs">นโยบายการจัดเก็บและทำลายข้อมูลอัตโนมัติ:</strong>
                      <p className="text-slate-600 mt-0.5 text-[11px]">
                        เอกสารต้นฉบับและผลลัพธ์จะถูกจัดเก็บภายในเครือข่ายความมั่นคงปลอดภัย และจะถูก<strong>ลบทำลายออกจากระบบโดยอัตโนมัติภายใน 3 วัน (72 ชั่วโมง)</strong> หรือผู้ใช้สามารถกดลบทำลายไฟล์ได้ทันทีที่ตารางประวัติ
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 pt-2 border-t border-slate-200/60">
                    <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-800 font-bold text-[11px] flex items-center justify-center shrink-0 mt-0.5">๕</span>
                    <div>
                      <strong className="text-slate-900 block text-xs">การรักษาความมั่นคงปลอดภัยข้อมูลและเอกสารลับ:</strong>
                      <p className="text-slate-600 mt-0.5 text-[11px]">
                        การประมวลผลเอกสารลับ เอกสารสำคัญ หรือข้อมูลส่วนบุคคล (PDPA) ต้องเป็นไปตามอำนาจหน้าที่ตามกฎหมายและระเบียบสำนักนายกรัฐมนตรีว่าด้วยการรักษาความปลอดภัยแห่งชาติ
                      </p>
                    </div>
                  </div>
                </div>

                <div className="text-[11px] text-slate-500 italic flex items-center gap-1.5 px-1">
                  <Shield className="w-3.5 h-3.5 text-slate-400" />
                  <span>ระบบจะทำการบันทึกประวัติการยอมรับหรือปฏิเสธเงื่อนไขของผู้ใช้งาน (Audit Log) เพื่อความโปร่งใสและตรวจสอบได้</span>
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-end space-x-3 shrink-0">
              <button
                type="button"
                onClick={handleDeclineDisclaimer}
                className="px-4 py-2 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-100 font-medium text-xs transition cursor-pointer"
              >
                ไม่ใช้งาน
              </button>
              <button
                type="button"
                onClick={handleAcceptDisclaimer}
                className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs transition shadow-sm flex items-center space-x-1.5 cursor-pointer"
              >
                <Check className="w-4 h-4" />
                <span>ยอมรับ</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
        <p>ThaiOCR ONNX Web Portal • ระบบบริการรู้จำอักขระและแปลงเอกสาร (OCR)</p>
        <p className="text-[11px] text-slate-400 mt-1">ประมวลผลภายในระบบเครือข่ายความมั่นคงปลอดภัยสูง (Offline 100%)</p>
      </footer>
    </div>
  )
}
