# Dedicated Admin Governance Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Admin Backend Monitor from a popup modal into a full-page dedicated view in `frontend/src/App.jsx` with a Top Navigation switcher and URL hash synchronization (`#/admin`).

**Architecture:**
1. State & Routing: Add `currentView` ('studio' | 'admin') with bidirectional synchronization to `window.location.hash` (`#/admin`).
2. Header Navbar: Add mode switcher buttons in header (OCR Studio vs Admin Governance) with role gating (`currentUser?.role === 'admin'`).
3. View Separation: Extract and render Admin Monitor as full-width page layout (`max-w-7xl`) inside `<main>` when `currentView === 'admin'`; completely retire `showAdminModal`.

**Tech Stack:** React 19, Tailwind CSS, Lucide Icons, Vite.

## Global Constraints

- Role safety: Admin page is only accessible when `currentUser?.role === 'admin'`. Non-admin or unauthenticated access falls back to Studio view.
- URL Hash Sync: `#/admin` and `#/studio` (or `#/`) synchronize with browser history and back/forward navigation.
- No regression on existing 8 Admin sub-tabs (Metrics & Cache, Users, API Keys, Docs, LDAP, Jobs, Audit, Logs).
- Zero external router libraries; use React standard state + native hashchange listener.

---

### Task 1: Navigation State & Top Navbar Switcher (`frontend/src/App.jsx`)

**Files:**
- Modify: `frontend/src/App.jsx`
- Test: `npm --prefix frontend run build`

- [ ] **Step 1: Add `currentView` state and hash listener in `frontend/src/App.jsx`**

Add state and effect:
```javascript
const [currentView, setCurrentView] = useState(() => {
  return window.location.hash === '#/admin' ? 'admin' : 'studio'
})

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

  window.addEventListener('hashchange', onHashChange)
  return () => window.removeEventListener('hashchange', onHashChange)
}, [currentUser])

// Switch view helper
const navigateToView = (view) => {
  if (view === 'admin' && currentUser?.role !== 'admin') return
  window.location.hash = view === 'admin' ? '#/admin' : '#/'
  setCurrentView(view)
  if (view === 'admin') {
    loadAdminData()
  }
}
```

- [ ] **Step 2: Add Top Navbar Switcher in Header**

Replace the old `Admin Monitor` modal button in Header with a responsive Top Navigation Switcher:
```jsx
{/* View Switcher for logged in Admin */}
{currentUser && currentUser.role === 'admin' && (
  <nav className="flex items-center bg-slate-800/90 p-1 rounded-xl border border-slate-700/80 text-xs">
    <button
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
```

- [ ] **Step 3: Verify build**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Commit changes**

```bash
git add frontend/src/App.jsx
git commit -m "feat(ui): add top navbar view switcher and hash routing"
```

---

### Task 2: Dedicated Full-Page Admin View & Modal Retirement (`frontend/src/App.jsx`)

**Files:**
- Modify: `frontend/src/App.jsx`
- Test: `npm --prefix frontend run build`

- [ ] **Step 1: Render Studio View or Admin View conditionally in `<main>`**

In `frontend/src/App.jsx`:
When `currentView === 'admin' && currentUser?.role === 'admin'`, render full-width Admin Dashboard view:
```jsx
<main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex-1 w-full space-y-6">
  {currentView === 'admin' && currentUser?.role === 'admin' ? (
    /* Full-width Admin Dashboard Card */
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
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

      {/* Admin Tabs Bar */}
      ...
      {/* Admin Content Area (8 tabs) */}
      ...
    </div>
  ) : (
    /* Standard OCR Studio Content */
    ...
  )}
</main>
```

- [ ] **Step 2: Remove the old `showAdminModal` wrapper**

Remove lines associated with `showAdminModal && (<div className="fixed inset-0 ..."> ... </div>)`.

- [ ] **Step 3: Verify build**

Run: `npm --prefix frontend run build`
Expected: PASS with no JSX or styling errors.

- [ ] **Step 4: Commit changes**

```bash
git add frontend/src/App.jsx
git commit -m "refactor(ui): convert admin monitor from modal to dedicated full page"
```

---

### Task 3: Integration Verification & Docker Rebuild

**Files:**
- Modify: `docker-compose.yml` (if needed)
- Test: `docker compose build thai-ocr-app && docker compose up -d --no-deps thai-ocr-app`

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest tests/ -v`
Expected: 60 passed

- [ ] **Step 2: Rebuild Docker Image**

Run: `docker compose build thai-ocr-app`
Expected: Docker build succeeds.

- [ ] **Step 3: Restart Container & Verify Gateway**

Run: `docker compose up -d --no-deps thai-ocr-app`
Run: `curl -k -s https://localhost:8843/health`
Expected: Status healthy.

- [ ] **Step 4: Commit and finalize**

```bash
git commit -m "build: rebuild container with full-page admin governance"
```
