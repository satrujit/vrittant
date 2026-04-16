# Org Admin Settings UI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Settings page to the reviewer-panel with three tabs (Users, Organization, Master Data) for org_admin users.

**Architecture:** Single SettingsPage component at `/settings` with tab state. Each tab is a separate component. API functions added to existing `services/api.js`. Sidebar shows Settings only for `org_admin` users. Uses existing Modal component for forms.

**Tech Stack:** React 19, React Router, CSS Modules, lucide-react icons, existing Modal component

---

### Task 1: API Functions

**Files:**
- Modify: `src/services/api.js` (add new functions at end, before Auth API section)

**Step 1: Add org admin API functions**

Add these functions to `src/services/api.js` before the `// ── Auth API ──` comment (around line 380):

```javascript
// ── Org Admin API ──

export async function fetchOrgUsers() {
  return apiFetch('/admin/reporters');
}

export async function createUser(data) {
  return apiFetch('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateUser(id, data) {
  return apiFetch(`/admin/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateUserRole(id, userType) {
  return apiFetch(`/admin/users/${id}/role`, {
    method: 'PUT',
    body: JSON.stringify({ user_type: userType }),
  });
}

export async function updateUserEntitlements(id, pageKeys) {
  return apiFetch(`/admin/users/${id}/entitlements`, {
    method: 'PUT',
    body: JSON.stringify({ page_keys: pageKeys }),
  });
}

export async function updateOrg(data) {
  return apiFetch('/admin/org', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function uploadOrgLogo(file) {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/admin/org/logo`, {
    method: 'PUT',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
  });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  return resp.json();
}

export async function fetchOrgConfig() {
  return apiFetch('/admin/config');
}

export async function updateOrgConfig(data) {
  return apiFetch('/admin/config', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteStory(id) {
  return apiFetch(`/admin/stories/${id}`, { method: 'DELETE' });
}
```

Note: `uploadOrgLogo` does NOT use `apiFetch` because `apiFetch` sets `Content-Type: application/json`. For file uploads we need `FormData` with no explicit Content-Type (browser sets it with boundary).

**Step 2: Verify**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npm run dev`
Open browser, check console for no import errors.

**Step 3: Commit**

```bash
git add src/services/api.js
git commit -m "feat: add org admin API functions"
```

---

### Task 2: Settings Route and Sidebar Nav Item

**Files:**
- Modify: `src/App.jsx` (add route)
- Modify: `src/components/layout/Sidebar.jsx` (add Settings nav item)
- Create: `src/pages/SettingsPage.jsx` (stub)
- Create: `src/pages/SettingsPage.module.css` (stub)

**Step 1: Create stub SettingsPage**

Create `src/pages/SettingsPage.jsx`:

```jsx
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import styles from './SettingsPage.module.css';

const TABS = ['Users', 'Organization', 'Master Data'];

function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState(0);

  if (user?.user_type !== 'org_admin') {
    return <Navigate to="/" replace />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Settings</h1>
      </div>
      <div className={styles.tabs}>
        {TABS.map((tab, i) => (
          <button
            key={tab}
            className={`${styles.tab} ${i === activeTab ? styles.tabActive : ''}`}
            onClick={() => setActiveTab(i)}
          >
            {tab}
          </button>
        ))}
      </div>
      <div className={styles.content}>
        {activeTab === 0 && <div>Users tab placeholder</div>}
        {activeTab === 1 && <div>Organization tab placeholder</div>}
        {activeTab === 2 && <div>Master Data tab placeholder</div>}
      </div>
    </div>
  );
}

export default SettingsPage;
```

Create `src/pages/SettingsPage.module.css`:

```css
.page {
  padding: var(--vr-space-xl);
  max-width: 1000px;
}

.header {
  margin-bottom: var(--vr-space-lg);
}

.title {
  font-family: var(--vr-font-display);
  font-size: var(--vr-text-2xl);
  font-weight: var(--vr-weight-bold);
  color: var(--vr-heading);
  margin: 0;
}

.tabs {
  display: flex;
  gap: var(--vr-space-xs);
  border-bottom: 1px solid var(--vr-border);
  margin-bottom: var(--vr-space-xl);
}

.tab {
  padding: var(--vr-space-sm) var(--vr-space-lg);
  border: none;
  background: none;
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-medium);
  color: var(--vr-section);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--vr-transition-fast);
  margin-bottom: -1px;
}

.tab:hover {
  color: var(--vr-heading);
}

.tabActive {
  color: var(--vr-brand-coral);
  border-bottom-color: var(--vr-brand-coral);
}

.content {
  min-height: 400px;
}
```

**Step 2: Add route in App.jsx**

In `src/App.jsx`, add import after line 14:
```javascript
import SettingsPage from './pages/SettingsPage';
```

Add route inside the `<Route element={<AppLayout />}>` block, after the buckets route (after line 31):
```jsx
                <Route path="/settings" element={<SettingsPage />} />
```

**Step 3: Add Settings to Sidebar**

In `src/components/layout/Sidebar.jsx`:

Add `Settings` icon to the import on line 2:
```javascript
import { LayoutDashboard, Archive, Users, Columns3, LogOut, Settings } from 'lucide-react';
```

After the `visibleNavItems` filter (after line 37), add:
```javascript
  const isOrgAdmin = user?.user_type === 'org_admin';
```

In the JSX, after the closing `</nav>` tag (line 76), before the bottom section (line 79), add:
```jsx
      {/* Settings — org_admin only */}
      {isOrgAdmin && (
        <div className={styles.settingsNav}>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
            }
          >
            <Settings size={20} className={styles.navIcon} />
            <span className={styles.navLabel}>Settings</span>
          </NavLink>
        </div>
      )}
```

In `src/components/layout/Sidebar.module.css`, add at the end:
```css
.settingsNav {
  padding: 0 var(--vr-space-sm);
  border-top: 1px solid var(--vr-border);
  padding-top: var(--vr-space-sm);
}
```

**Step 4: Verify**

Run dev server. Login as org_admin user (+918984336534). Verify:
- Settings item appears in sidebar
- Clicking it navigates to /settings
- Three tabs are visible and clickable
- Login as a reviewer — Settings should NOT appear

**Step 5: Commit**

```bash
git add src/pages/SettingsPage.jsx src/pages/SettingsPage.module.css src/App.jsx src/components/layout/Sidebar.jsx src/components/layout/Sidebar.module.css
git commit -m "feat: add Settings page route and sidebar nav item"
```

---

### Task 3: Users Tab

**Files:**
- Create: `src/components/settings/UsersTab.jsx`
- Create: `src/components/settings/UsersTab.module.css`
- Create: `src/components/settings/UserFormModal.jsx`
- Create: `src/components/settings/EntitlementsModal.jsx`
- Modify: `src/pages/SettingsPage.jsx` (replace placeholder)

**Step 1: Create UsersTab.module.css**

Create `src/components/settings/UsersTab.module.css`:

```css
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--vr-space-lg);
}

.addBtn {
  display: flex;
  align-items: center;
  gap: var(--vr-space-xs);
  padding: var(--vr-space-sm) var(--vr-space-lg);
  background: var(--vr-brand-coral);
  color: white;
  border: none;
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-medium);
  cursor: pointer;
  transition: opacity var(--vr-transition-fast);
}
.addBtn:hover { opacity: 0.9; }

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  text-align: left;
  padding: var(--vr-space-sm) var(--vr-space-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-xs);
  font-weight: var(--vr-weight-semibold);
  color: var(--vr-section);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--vr-border);
}

.table td {
  padding: var(--vr-space-sm) var(--vr-space-md);
  font-size: var(--vr-text-sm);
  color: var(--vr-body);
  border-bottom: 1px solid var(--vr-border);
  vertical-align: middle;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--vr-radius-full);
  font-size: var(--vr-text-xs);
  font-weight: var(--vr-weight-medium);
}
.badgeReporter { background: #EEF2FF; color: #4338CA; }
.badgeReviewer { background: #FFF7ED; color: #C2410C; }
.badgeOrgAdmin { background: #ECFDF5; color: #065F46; }
.badgeActive { background: #ECFDF5; color: #065F46; }
.badgeDisabled { background: #FEF2F2; color: #991B1B; }

.actions {
  display: flex;
  gap: var(--vr-space-xs);
}

.actionBtn {
  padding: 4px 10px;
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-sm);
  background: white;
  font-size: var(--vr-text-xs);
  color: var(--vr-body);
  cursor: pointer;
  transition: all var(--vr-transition-fast);
}
.actionBtn:hover {
  background: var(--vr-hover-bg);
  color: var(--vr-heading);
}
.actionBtnDanger:hover {
  background: #FEF2F2;
  color: #991B1B;
  border-color: #FCA5A5;
}

/* Form styles (for modals) */
.form { display: flex; flex-direction: column; gap: var(--vr-space-md); }
.field { display: flex; flex-direction: column; gap: var(--vr-space-xs); }
.field label {
  font-size: var(--vr-text-xs);
  font-weight: var(--vr-weight-semibold);
  color: var(--vr-section);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.field input, .field select {
  padding: var(--vr-space-sm) var(--vr-space-md);
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  color: var(--vr-body);
  outline: none;
  transition: border-color var(--vr-transition-fast);
}
.field input:focus, .field select:focus {
  border-color: var(--vr-brand-coral);
}
.submitBtn {
  padding: var(--vr-space-sm) var(--vr-space-lg);
  background: var(--vr-brand-coral);
  color: white;
  border: none;
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-medium);
  cursor: pointer;
  transition: opacity var(--vr-transition-fast);
  align-self: flex-end;
}
.submitBtn:hover { opacity: 0.9; }
.submitBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.checkboxGroup { display: flex; flex-direction: column; gap: var(--vr-space-sm); }
.checkboxItem {
  display: flex;
  align-items: center;
  gap: var(--vr-space-sm);
  font-size: var(--vr-text-sm);
  color: var(--vr-body);
}
.checkboxItem input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--vr-brand-coral);
}

.error {
  color: #DC2626;
  font-size: var(--vr-text-sm);
  margin-bottom: var(--vr-space-md);
}
```

**Step 2: Create UserFormModal**

Create `src/components/settings/UserFormModal.jsx`:

```jsx
import { useState } from 'react';
import Modal from '../common/Modal';
import styles from './UsersTab.module.css';

function UserFormModal({ isOpen, onClose, onSubmit, user }) {
  const isEdit = !!user;
  const [form, setForm] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    email: user?.email || '',
    area_name: user?.area_name || user?.areaName || '',
    user_type: user?.user_type || 'reporter',
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleChange = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim()) { setError('Name is required'); return; }
    if (!isEdit && !form.phone.trim()) { setError('Phone is required'); return; }
    setSaving(true);
    try {
      await onSubmit(form);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEdit ? 'Edit User' : 'Add User'}>
      <form onSubmit={handleSubmit} className={styles.form}>
        {error && <div className={styles.error}>{error}</div>}
        <div className={styles.field}>
          <label>Name</label>
          <input value={form.name} onChange={handleChange('name')} placeholder="Full name" required />
        </div>
        {!isEdit && (
          <div className={styles.field}>
            <label>Phone</label>
            <input value={form.phone} onChange={handleChange('phone')} placeholder="+91..." required />
          </div>
        )}
        <div className={styles.field}>
          <label>Email</label>
          <input value={form.email} onChange={handleChange('email')} placeholder="email@example.com" type="email" />
        </div>
        <div className={styles.field}>
          <label>Area</label>
          <input value={form.area_name} onChange={handleChange('area_name')} placeholder="Coverage area" />
        </div>
        {!isEdit && (
          <div className={styles.field}>
            <label>Role</label>
            <select value={form.user_type} onChange={handleChange('user_type')}>
              <option value="reporter">Reporter</option>
              <option value="reviewer">Reviewer</option>
            </select>
          </div>
        )}
        <button type="submit" className={styles.submitBtn} disabled={saving}>
          {saving ? 'Saving...' : isEdit ? 'Update' : 'Add User'}
        </button>
      </form>
    </Modal>
  );
}

export default UserFormModal;
```

**Step 3: Create EntitlementsModal**

Create `src/components/settings/EntitlementsModal.jsx`:

```jsx
import { useState } from 'react';
import Modal from '../common/Modal';
import styles from './UsersTab.module.css';

const ALL_PAGE_KEYS = ['dashboard', 'stories', 'review', 'editions', 'reporters', 'social_export'];

function EntitlementsModal({ isOpen, onClose, onSubmit, userName, currentEntitlements }) {
  const [selected, setSelected] = useState(new Set(currentEntitlements || []));
  const [saving, setSaving] = useState(false);

  const toggle = (key) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await onSubmit([...selected]);
      onClose();
    } catch {
      // error handled by parent
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Entitlements — ${userName}`}>
      <div className={styles.checkboxGroup}>
        {ALL_PAGE_KEYS.map((key) => (
          <label key={key} className={styles.checkboxItem}>
            <input
              type="checkbox"
              checked={selected.has(key)}
              onChange={() => toggle(key)}
            />
            {key}
          </label>
        ))}
      </div>
      <div style={{ marginTop: 'var(--vr-space-lg)', textAlign: 'right' }}>
        <button className={styles.submitBtn} onClick={handleSubmit} disabled={saving}>
          {saving ? 'Saving...' : 'Save Entitlements'}
        </button>
      </div>
    </Modal>
  );
}

export default EntitlementsModal;
```

**Step 4: Create UsersTab**

Create `src/components/settings/UsersTab.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { UserPlus } from 'lucide-react';
import {
  fetchOrgUsers, createUser, updateUser,
  updateUserRole, updateUserEntitlements,
} from '../../services/api';
import UserFormModal from './UserFormModal';
import EntitlementsModal from './EntitlementsModal';
import styles from './UsersTab.module.css';

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [entitlementsUser, setEntitlementsUser] = useState(null);

  const loadUsers = useCallback(async () => {
    try {
      const data = await fetchOrgUsers();
      setUsers(data.reporters || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const handleCreate = async (form) => {
    await createUser(form);
    loadUsers();
  };

  const handleEdit = async (form) => {
    await updateUser(editUser.id, {
      name: form.name,
      email: form.email,
      area_name: form.area_name,
    });
    setEditUser(null);
    loadUsers();
  };

  const handleToggleActive = async (u) => {
    await updateUser(u.id, { is_active: !u.is_active });
    loadUsers();
  };

  const handleRoleChange = async (u, newRole) => {
    await updateUserRole(u.id, newRole);
    loadUsers();
  };

  const handleEntitlements = async (pageKeys) => {
    await updateUserEntitlements(entitlementsUser.id, pageKeys);
    loadUsers();
  };

  if (loading) return <div>Loading users...</div>;

  return (
    <div>
      <div className={styles.header}>
        <span>{users.length} user{users.length !== 1 ? 's' : ''}</span>
        <button className={styles.addBtn} onClick={() => setShowAddModal(true)}>
          <UserPlus size={16} /> Add User
        </button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Phone</th>
            <th>Role</th>
            <th>Area</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.name}</td>
              <td>{u.phone}</td>
              <td>
                <select
                  value={u.user_type}
                  onChange={(e) => handleRoleChange(u, e.target.value)}
                  style={{ border: 'none', background: 'none', fontSize: 'inherit', cursor: 'pointer' }}
                  disabled={u.user_type === 'org_admin'}
                >
                  <option value="reporter">Reporter</option>
                  <option value="reviewer">Reviewer</option>
                  {u.user_type === 'org_admin' && <option value="org_admin">Org Admin</option>}
                </select>
              </td>
              <td>{u.area_name || '—'}</td>
              <td>
                <span className={`${styles.badge} ${u.is_active ? styles.badgeActive : styles.badgeDisabled}`}>
                  {u.is_active ? 'Active' : 'Disabled'}
                </span>
              </td>
              <td>
                <div className={styles.actions}>
                  <button className={styles.actionBtn} onClick={() => setEditUser(u)}>Edit</button>
                  <button className={styles.actionBtn} onClick={() => setEntitlementsUser(u)}>Entitlements</button>
                  <button
                    className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                    onClick={() => handleToggleActive(u)}
                    disabled={u.user_type === 'org_admin'}
                  >
                    {u.is_active ? 'Disable' : 'Enable'}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showAddModal && (
        <UserFormModal isOpen onClose={() => setShowAddModal(false)} onSubmit={handleCreate} />
      )}
      {editUser && (
        <UserFormModal isOpen onClose={() => setEditUser(null)} onSubmit={handleEdit} user={editUser} />
      )}
      {entitlementsUser && (
        <EntitlementsModal
          isOpen
          onClose={() => setEntitlementsUser(null)}
          onSubmit={handleEntitlements}
          userName={entitlementsUser.name}
          currentEntitlements={(entitlementsUser.entitlements || []).map((e) => e.page_key || e)}
        />
      )}
    </div>
  );
}

export default UsersTab;
```

**Step 5: Wire up in SettingsPage**

In `src/pages/SettingsPage.jsx`, add import and replace placeholder:

Add import:
```javascript
import UsersTab from '../components/settings/UsersTab';
```

Replace `{activeTab === 0 && <div>Users tab placeholder</div>}` with:
```jsx
        {activeTab === 0 && <UsersTab />}
```

**Step 6: Verify**

Login as org_admin. Navigate to Settings > Users tab. Verify:
- Users table displays
- Add User button opens modal
- Edit, Entitlements, Disable buttons work
- Role dropdown changes role

**Step 7: Commit**

```bash
git add src/components/settings/ src/pages/SettingsPage.jsx
git commit -m "feat: add Users tab to Settings page"
```

---

### Task 4: Organization Tab

**Files:**
- Create: `src/components/settings/OrgTab.jsx`
- Create: `src/components/settings/OrgTab.module.css`
- Modify: `src/pages/SettingsPage.jsx` (replace placeholder)

**Step 1: Create OrgTab.module.css**

Create `src/components/settings/OrgTab.module.css`:

```css
.form {
  display: flex;
  flex-direction: column;
  gap: var(--vr-space-lg);
  max-width: 500px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--vr-space-xs);
}

.field label {
  font-size: var(--vr-text-xs);
  font-weight: var(--vr-weight-semibold);
  color: var(--vr-section);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field input {
  padding: var(--vr-space-sm) var(--vr-space-md);
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  color: var(--vr-body);
  outline: none;
  transition: border-color var(--vr-transition-fast);
}

.field input:focus {
  border-color: var(--vr-brand-coral);
}

.colorRow {
  display: flex;
  align-items: center;
  gap: var(--vr-space-md);
}

.colorSwatch {
  width: 36px;
  height: 36px;
  border-radius: var(--vr-radius-md);
  border: 1px solid var(--vr-border);
  flex-shrink: 0;
}

.logoPreview {
  width: 120px;
  height: 60px;
  object-fit: contain;
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-md);
  padding: var(--vr-space-xs);
}

.uploadBtn {
  padding: var(--vr-space-sm) var(--vr-space-lg);
  border: 1px dashed var(--vr-border);
  border-radius: var(--vr-radius-md);
  background: white;
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  color: var(--vr-body);
  cursor: pointer;
  transition: all var(--vr-transition-fast);
}

.uploadBtn:hover {
  border-color: var(--vr-brand-coral);
  color: var(--vr-brand-coral);
}

.saveBtn {
  padding: var(--vr-space-sm) var(--vr-space-xl);
  background: var(--vr-brand-coral);
  color: white;
  border: none;
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-medium);
  cursor: pointer;
  align-self: flex-start;
  transition: opacity var(--vr-transition-fast);
}

.saveBtn:hover { opacity: 0.9; }
.saveBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.success {
  color: #059669;
  font-size: var(--vr-text-sm);
}

.error {
  color: #DC2626;
  font-size: var(--vr-text-sm);
}
```

**Step 2: Create OrgTab**

Create `src/components/settings/OrgTab.jsx`:

```jsx
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { updateOrg, uploadOrgLogo, getMediaUrl } from '../../services/api';
import styles from './OrgTab.module.css';

function OrgTab() {
  const { user } = useAuth();
  const org = user?.org;
  const fileRef = useRef(null);

  const [form, setForm] = useState({ name: '', theme_color: '#FA6C38' });
  const [logoUrl, setLogoUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    if (org) {
      setForm({ name: org.name || '', theme_color: org.theme_color || '#FA6C38' });
      setLogoUrl(org.logo_url ? getMediaUrl(org.logo_url) : '');
    }
  }, [org]);

  const handleSave = async () => {
    setSaving(true);
    setMessage({ type: '', text: '' });
    try {
      await updateOrg(form);
      setMessage({ type: 'success', text: 'Organization updated' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to update' });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await uploadOrgLogo(file);
      setLogoUrl(getMediaUrl(result.logo_url));
      setMessage({ type: 'success', text: 'Logo updated' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Upload failed' });
    }
  };

  return (
    <div className={styles.form}>
      <div className={styles.field}>
        <label>Organization Name</label>
        <input
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
      </div>

      <div className={styles.field}>
        <label>Theme Color</label>
        <div className={styles.colorRow}>
          <div className={styles.colorSwatch} style={{ background: form.theme_color }} />
          <input
            value={form.theme_color}
            onChange={(e) => setForm((f) => ({ ...f, theme_color: e.target.value }))}
            placeholder="#FA6C38"
            maxLength={7}
          />
        </div>
      </div>

      <div className={styles.field}>
        <label>Logo</label>
        {logoUrl && <img src={logoUrl} alt="Org logo" className={styles.logoPreview} />}
        <input
          type="file"
          ref={fileRef}
          accept=".png,.jpg,.jpeg,.webp,.svg"
          onChange={handleLogoUpload}
          style={{ display: 'none' }}
        />
        <button className={styles.uploadBtn} onClick={() => fileRef.current?.click()}>
          Upload new logo
        </button>
      </div>

      {message.text && (
        <div className={message.type === 'success' ? styles.success : styles.error}>
          {message.text}
        </div>
      )}

      <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
        {saving ? 'Saving...' : 'Save Changes'}
      </button>
    </div>
  );
}

export default OrgTab;
```

**Step 3: Wire up in SettingsPage**

Add import:
```javascript
import OrgTab from '../components/settings/OrgTab';
```

Replace `{activeTab === 1 && <div>Organization tab placeholder</div>}` with:
```jsx
        {activeTab === 1 && <OrgTab />}
```

**Step 4: Verify**

Settings > Organization tab. Verify: name and color are pre-filled, logo shows, upload works, save works.

**Step 5: Commit**

```bash
git add src/components/settings/OrgTab.jsx src/components/settings/OrgTab.module.css src/pages/SettingsPage.jsx
git commit -m "feat: add Organization tab to Settings page"
```

---

### Task 5: Master Data Tab

**Files:**
- Create: `src/components/settings/MasterDataTab.jsx`
- Create: `src/components/settings/MasterDataTab.module.css`
- Modify: `src/pages/SettingsPage.jsx` (replace placeholder)

**Step 1: Create MasterDataTab.module.css**

Create `src/components/settings/MasterDataTab.module.css`:

```css
.sections {
  display: flex;
  flex-direction: column;
  gap: var(--vr-space-xl);
}

.section {
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-lg);
  overflow: hidden;
}

.sectionHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--vr-space-md) var(--vr-space-lg);
  background: var(--vr-hover-bg);
  cursor: pointer;
  user-select: none;
}

.sectionTitle {
  font-family: var(--vr-font-display);
  font-size: var(--vr-text-base);
  font-weight: var(--vr-weight-semibold);
  color: var(--vr-heading);
  margin: 0;
}

.sectionBody {
  padding: var(--vr-space-lg);
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  text-align: left;
  padding: var(--vr-space-xs) var(--vr-space-sm);
  font-size: var(--vr-text-xs);
  font-weight: var(--vr-weight-semibold);
  color: var(--vr-section);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--vr-border);
}

.table td {
  padding: var(--vr-space-xs) var(--vr-space-sm);
  border-bottom: 1px solid var(--vr-border);
}

.table input {
  padding: 4px 8px;
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-sm);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  width: 100%;
  box-sizing: border-box;
}

.table input:focus {
  outline: none;
  border-color: var(--vr-brand-coral);
}

.table input[type="number"] {
  width: 60px;
}

.table input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--vr-brand-coral);
}

.addRowBtn {
  margin-top: var(--vr-space-sm);
  padding: 4px 12px;
  border: 1px dashed var(--vr-border);
  border-radius: var(--vr-radius-sm);
  background: white;
  font-size: var(--vr-text-xs);
  color: var(--vr-section);
  cursor: pointer;
}
.addRowBtn:hover { border-color: var(--vr-brand-coral); color: var(--vr-brand-coral); }

.removeBtn {
  padding: 2px 8px;
  border: none;
  background: none;
  color: #DC2626;
  font-size: var(--vr-text-xs);
  cursor: pointer;
}
.removeBtn:hover { text-decoration: underline; }

.langField {
  display: flex;
  align-items: center;
  gap: var(--vr-space-md);
  padding: var(--vr-space-md) 0;
}

.langField label {
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-semibold);
  color: var(--vr-section);
}

.langField select {
  padding: var(--vr-space-sm) var(--vr-space-md);
  border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
}

.footer {
  display: flex;
  gap: var(--vr-space-md);
  align-items: center;
  margin-top: var(--vr-space-lg);
}

.saveBtn {
  padding: var(--vr-space-sm) var(--vr-space-xl);
  background: var(--vr-brand-coral);
  color: white;
  border: none;
  border-radius: var(--vr-radius-md);
  font-family: var(--vr-font-body);
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-medium);
  cursor: pointer;
}
.saveBtn:hover { opacity: 0.9; }
.saveBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.success { color: #059669; font-size: var(--vr-text-sm); }
.error { color: #DC2626; font-size: var(--vr-text-sm); }
```

**Step 2: Create MasterDataTab**

Create `src/components/settings/MasterDataTab.jsx`:

```jsx
import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Plus } from 'lucide-react';
import { fetchOrgConfig, updateOrgConfig } from '../../services/api';
import styles from './MasterDataTab.module.css';

function EditableTable({ columns, rows, onChange }) {
  const updateRow = (idx, field, value) => {
    const updated = rows.map((r, i) => (i === idx ? { ...r, [field]: value } : r));
    onChange(updated);
  };

  const addRow = () => {
    const empty = {};
    columns.forEach((c) => {
      if (c.type === 'boolean') empty[c.key] = true;
      else if (c.type === 'number') empty[c.key] = rows.length + 1;
      else empty[c.key] = '';
    });
    onChange([...rows, empty]);
  };

  const removeRow = (idx) => onChange(rows.filter((_, i) => i !== idx));

  return (
    <div>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((c) => <th key={c.key}>{c.label}</th>)}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((c) => (
                <td key={c.key}>
                  {c.type === 'boolean' ? (
                    <input
                      type="checkbox"
                      checked={!!row[c.key]}
                      onChange={(e) => updateRow(idx, c.key, e.target.checked)}
                    />
                  ) : c.type === 'number' ? (
                    <input
                      type="number"
                      value={row[c.key] ?? ''}
                      onChange={(e) => updateRow(idx, c.key, parseInt(e.target.value) || 0)}
                    />
                  ) : (
                    <input
                      value={row[c.key] ?? ''}
                      onChange={(e) => updateRow(idx, c.key, e.target.value)}
                    />
                  )}
                </td>
              ))}
              <td><button className={styles.removeBtn} onClick={() => removeRow(idx)}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className={styles.addRowBtn} onClick={addRow}><Plus size={12} /> Add row</button>
    </div>
  );
}

function CollapsibleSection({ title, defaultOpen, children }) {
  const [open, setOpen] = useState(defaultOpen ?? true);
  return (
    <div className={styles.section}>
      <div className={styles.sectionHeader} onClick={() => setOpen(!open)}>
        <h3 className={styles.sectionTitle}>{title}</h3>
        {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
      </div>
      {open && <div className={styles.sectionBody}>{children}</div>}
    </div>
  );
}

const CATEGORY_COLS = [
  { key: 'key', label: 'Key', type: 'text' },
  { key: 'label', label: 'Label', type: 'text' },
  { key: 'label_local', label: 'Local Label', type: 'text' },
  { key: 'is_active', label: 'Active', type: 'boolean' },
];

const PUB_TYPE_COLS = [
  { key: 'key', label: 'Key', type: 'text' },
  { key: 'label', label: 'Label', type: 'text' },
  { key: 'is_active', label: 'Active', type: 'boolean' },
];

const PAGE_COLS = [
  { key: 'name', label: 'Name', type: 'text' },
  { key: 'sort_order', label: 'Sort Order', type: 'number' },
  { key: 'is_active', label: 'Active', type: 'boolean' },
];

const PRIORITY_COLS = [
  { key: 'key', label: 'Key', type: 'text' },
  { key: 'label', label: 'Label', type: 'text' },
  { key: 'label_local', label: 'Local Label', type: 'text' },
  { key: 'is_active', label: 'Active', type: 'boolean' },
];

function MasterDataTab() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchOrgConfig()
      .then(setConfig)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage({ type: '', text: '' });
    try {
      const updated = await updateOrgConfig(config);
      setConfig(updated);
      setMessage({ type: 'success', text: 'Master data saved' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div>Loading config...</div>;
  if (!config) return <div>No config found</div>;

  return (
    <div className={styles.sections}>
      <CollapsibleSection title="Categories">
        <EditableTable
          columns={CATEGORY_COLS}
          rows={config.categories || []}
          onChange={(rows) => setConfig((c) => ({ ...c, categories: rows }))}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Publication Types">
        <EditableTable
          columns={PUB_TYPE_COLS}
          rows={config.publication_types || []}
          onChange={(rows) => setConfig((c) => ({ ...c, publication_types: rows }))}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Page Suggestions">
        <EditableTable
          columns={PAGE_COLS}
          rows={config.page_suggestions || []}
          onChange={(rows) => setConfig((c) => ({ ...c, page_suggestions: rows }))}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Priority Levels">
        <EditableTable
          columns={PRIORITY_COLS}
          rows={config.priority_levels || []}
          onChange={(rows) => setConfig((c) => ({ ...c, priority_levels: rows }))}
        />
      </CollapsibleSection>

      <div className={styles.langField}>
        <label>Default Language</label>
        <select
          value={config.default_language || 'odia'}
          onChange={(e) => setConfig((c) => ({ ...c, default_language: e.target.value }))}
        >
          <option value="odia">Odia</option>
          <option value="english">English</option>
          <option value="hindi">Hindi</option>
        </select>
      </div>

      <div className={styles.footer}>
        <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Master Data'}
        </button>
        {message.text && (
          <span className={message.type === 'success' ? styles.success : styles.error}>
            {message.text}
          </span>
        )}
      </div>
    </div>
  );
}

export default MasterDataTab;
```

**Step 3: Wire up in SettingsPage**

Add import:
```javascript
import MasterDataTab from '../components/settings/MasterDataTab';
```

Replace `{activeTab === 2 && <div>Master Data tab placeholder</div>}` with:
```jsx
        {activeTab === 2 && <MasterDataTab />}
```

**Step 4: Verify**

Settings > Master Data tab. Verify:
- All 4 sections load with data from API
- Sections are collapsible
- Can edit rows, add rows, remove rows
- Default language dropdown works
- Save button persists changes

**Step 5: Commit**

```bash
git add src/components/settings/MasterDataTab.jsx src/components/settings/MasterDataTab.module.css src/pages/SettingsPage.jsx
git commit -m "feat: add Master Data tab to Settings page"
```

---

### Task 6: Final Verification

**Step 1: Full smoke test**

Start backend: `cd /Users/admin/Desktop/newsflow-api && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

Start frontend: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npm run dev`

Login as org_admin (+918984336534). Verify all three tabs work end-to-end:
- Users: add, edit, disable, change role, manage entitlements
- Organization: change name, color, upload logo
- Master Data: edit categories, save, reload page to confirm persistence

Login as reviewer (+918280103897). Verify Settings does NOT appear in sidebar.

**Step 2: Commit any fixes**

```bash
git add -A && git commit -m "fix: settings page polish and fixes"
```
