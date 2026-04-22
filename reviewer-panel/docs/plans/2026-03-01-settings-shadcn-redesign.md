# Settings Page Redesign with shadcn/ui — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all custom CSS on the Settings page with Tailwind v4 + shadcn/ui for a polished admin experience. First step toward app-wide adoption.

**Architecture:** Install Tailwind CSS v4 and shadcn/ui into the existing Vite + React 19 project. Tailwind and CSS Modules coexist — other pages keep their `.module.css` files untouched. Settings components are rewritten to use shadcn primitives and Tailwind utility classes exclusively.

**Tech Stack:** React 19, Vite 7, Tailwind CSS v4, shadcn/ui, lucide-react (already installed)

---

## Task 1: Install Tailwind CSS v4 for Vite

**Files:**
- Modify: `package.json` (new deps)
- Modify: `src/index.css` (add Tailwind import)
- Modify: `vite.config.js` (add Tailwind plugin)

**Step 1: Install Tailwind CSS v4 + Vite plugin**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
npm install tailwindcss @tailwindcss/vite
```

**Step 2: Add Tailwind Vite plugin**

In `vite.config.js`, add the Tailwind plugin:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
  },
})
```

**Step 3: Add Tailwind import to CSS**

At the very top of `src/index.css`, add:

```css
@import "tailwindcss";
```

**Step 4: Verify Tailwind works**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build 2>&1 | tail -5
```

Expected: Build succeeds with no errors.

**Step 5: Commit**

```bash
git add package.json package-lock.json vite.config.js src/index.css
git commit -m "feat: install Tailwind CSS v4 with Vite plugin"
```

---

## Task 2: Install and Initialize shadcn/ui

**Files:**
- Create: `src/lib/utils.js`
- Create: `components.json`
- Modify: `package.json` (new deps from shadcn init)
- Modify: `src/index.css` (shadcn CSS variables)

**Step 1: Install shadcn dependencies**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
npm install class-variance-authority clsx tailwind-merge
```

**Step 2: Create utility file**

Create `src/lib/utils.js`:

```js
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

**Step 3: Run shadcn init**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
npx shadcn@latest init
```

When prompted:
- Style: **New York**
- Base color: **Neutral**
- CSS file: `src/index.css`
- CSS variables: **yes**
- Import alias for components: `@/components`
- Import alias for utils: `@/lib`

If `npx shadcn@latest init` prompts fail non-interactively, create `components.json` manually — see Step 3b.

**Step 3b: Manual components.json fallback**

Create `components.json` at project root:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "",
    "css": "src/index.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

**Step 4: Configure path aliases in Vite**

Add to `vite.config.js`:

```js
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
  },
})
```

**Step 5: Configure shadcn primary color as brand coral (#FA6C38)**

In `src/index.css`, after the Tailwind import and shadcn's generated variables, set the primary HSL to match #FA6C38 (which is HSL 19, 95%, 60%):

Find the `:root` / `@theme` section shadcn created and set:

```css
--primary: 19 95% 60%;
--primary-foreground: 0 0% 100%;
```

**Step 6: Verify build**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build 2>&1 | tail -5
```

Expected: Build succeeds.

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: initialize shadcn/ui with coral primary color"
```

---

## Task 3: Add shadcn Components

**Files:**
- Create: `src/components/ui/button.jsx`
- Create: `src/components/ui/badge.jsx`
- Create: `src/components/ui/card.jsx`
- Create: `src/components/ui/dialog.jsx`
- Create: `src/components/ui/dropdown-menu.jsx`
- Create: `src/components/ui/input.jsx`
- Create: `src/components/ui/label.jsx`
- Create: `src/components/ui/select.jsx`
- Create: `src/components/ui/separator.jsx`
- Create: `src/components/ui/switch.jsx`
- Create: `src/components/ui/table.jsx`
- Create: `src/components/ui/tabs.jsx`
- Create: `src/components/ui/collapsible.jsx`
- Create: `src/components/ui/checkbox.jsx`

**Step 1: Install all shadcn components**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
npx shadcn@latest add button badge card dialog dropdown-menu input label select separator switch table tabs collapsible checkbox
```

This installs the components to `src/components/ui/` and adds any required Radix UI dependencies to `package.json`.

**Step 2: Verify all component files exist**

```bash
ls src/components/ui/
```

Expected: All 14 `.jsx` files listed above.

**Step 3: Verify build**

```bash
npx vite build 2>&1 | tail -5
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add shadcn UI components for Settings redesign"
```

---

## Task 4: Rewrite SettingsPage.jsx with shadcn Tabs

**Files:**
- Rewrite: `src/pages/SettingsPage.jsx`
- Delete: `src/pages/SettingsPage.module.css`

**Step 1: Rewrite SettingsPage.jsx**

Replace the entire file. Use shadcn `Tabs` component. Remove CSS Module import. Use Tailwind classes for layout.

```jsx
import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Settings } from 'lucide-react';
import UsersTab from '../components/settings/UsersTab';
import OrgTab from '../components/settings/OrgTab';
import MasterDataTab from '../components/settings/MasterDataTab';

function SettingsPage() {
  const { user } = useAuth();

  if (user?.user_type !== 'org_admin') {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
          <Settings className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground">Manage your organization, users, and configuration.</p>
        </div>
      </div>

      <Tabs defaultValue="users" className="space-y-6">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="organization">Organization</TabsTrigger>
          <TabsTrigger value="master-data">Master Data</TabsTrigger>
        </TabsList>
        <TabsContent value="users"><UsersTab /></TabsContent>
        <TabsContent value="organization"><OrgTab /></TabsContent>
        <TabsContent value="master-data"><MasterDataTab /></TabsContent>
      </Tabs>
    </div>
  );
}

export default SettingsPage;
```

**Step 2: Delete SettingsPage.module.css**

```bash
rm src/pages/SettingsPage.module.css
```

**Step 3: Verify build**

```bash
npx vite build 2>&1 | tail -5
```

**Step 4: Commit**

```bash
git add src/pages/SettingsPage.jsx
git rm src/pages/SettingsPage.module.css
git commit -m "feat: rewrite SettingsPage with shadcn Tabs"
```

---

## Task 5: Rewrite UsersTab.jsx

**Files:**
- Rewrite: `src/components/settings/UsersTab.jsx`
- Delete: `src/components/settings/UsersTab.module.css`

**Step 1: Rewrite UsersTab.jsx**

Full rewrite using shadcn Table, Badge, Button, DropdownMenu. Key changes:
- Header with user count Badge + "Add User" Button (primary)
- Table with avatar initials + name in first column
- Role as color-coded Badge
- Status as Badge (green/red)
- Actions as DropdownMenu (three-dot icon) with Edit, Entitlements, Disable/Enable items
- Empty state with Users icon + "No users yet" + Add User button
- Replace `Modal` usage with shadcn `Dialog` (import from UserFormModal / EntitlementsModal)

Use these shadcn imports:
```jsx
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { UserPlus, MoreHorizontal, Users } from 'lucide-react';
```

Role badge variants:
- reporter → `<Badge variant="secondary" className="bg-blue-50 text-blue-700">`
- reviewer → `<Badge variant="secondary" className="bg-amber-50 text-amber-700">`
- org_admin → `<Badge variant="secondary" className="bg-emerald-50 text-emerald-700">`

Status badge:
- active → `<Badge variant="secondary" className="bg-emerald-50 text-emerald-700">Active</Badge>`
- disabled → `<Badge variant="destructive">Disabled</Badge>`

Avatar initials: `<div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-semibold">{initials}</div>`

**Step 2: Delete UsersTab.module.css**

```bash
rm src/components/settings/UsersTab.module.css
```

**Step 3: Verify build**

**Step 4: Commit**

```bash
git add src/components/settings/UsersTab.jsx
git rm src/components/settings/UsersTab.module.css
git commit -m "feat: rewrite UsersTab with shadcn Table, Badge, DropdownMenu"
```

---

## Task 6: Rewrite UserFormModal.jsx with shadcn Dialog

**Files:**
- Rewrite: `src/components/settings/UserFormModal.jsx`

**Step 1: Rewrite UserFormModal.jsx**

Replace custom `Modal` import with shadcn `Dialog`. Use shadcn `Input`, `Label`, `Select`, `Button`.

```jsx
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
```

Dialog structure:
```jsx
<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
  <DialogContent className="sm:max-w-[425px]">
    <DialogHeader>
      <DialogTitle>{isEdit ? 'Edit User' : 'Add New User'}</DialogTitle>
    </DialogHeader>
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* fields */}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={saving}>{saving ? 'Saving...' : isEdit ? 'Update' : 'Add User'}</Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
```

Each field:
```jsx
<div className="space-y-2">
  <Label htmlFor="name">Name</Label>
  <Input id="name" value={form.name} onChange={...} placeholder="Full name" required />
</div>
```

Role field uses shadcn Select (not native `<select>`).

**Step 2: Verify build**

**Step 3: Commit**

```bash
git add src/components/settings/UserFormModal.jsx
git commit -m "feat: rewrite UserFormModal with shadcn Dialog, Input, Select"
```

---

## Task 7: Rewrite EntitlementsModal.jsx with shadcn Dialog + Checkbox

**Files:**
- Rewrite: `src/components/settings/EntitlementsModal.jsx`

**Step 1: Rewrite EntitlementsModal.jsx**

Replace custom `Modal` with shadcn `Dialog`. Replace native checkboxes with shadcn `Checkbox`.

```jsx
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
```

Each entitlement as:
```jsx
<div className="flex items-center space-x-3 py-2">
  <Checkbox id={key} checked={selected.has(key)} onCheckedChange={() => toggle(key)} />
  <Label htmlFor={key} className="text-sm font-normal cursor-pointer capitalize">
    {key.replace('_', ' ')}
  </Label>
</div>
```

**Step 2: Verify build**

**Step 3: Commit**

```bash
git add src/components/settings/EntitlementsModal.jsx
git commit -m "feat: rewrite EntitlementsModal with shadcn Dialog, Checkbox"
```

---

## Task 8: Rewrite OrgTab.jsx with shadcn Card

**Files:**
- Rewrite: `src/components/settings/OrgTab.jsx`
- Delete: `src/components/settings/OrgTab.module.css`

**Step 1: Rewrite OrgTab.jsx**

Use shadcn `Card`, `Input`, `Label`, `Button`, `Separator`. Two-column layout with Tailwind grid.

```jsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
```

Layout:
```jsx
<Card>
  <CardHeader>
    <CardTitle>Organization Profile</CardTitle>
    <CardDescription>Update your organization name, branding, and logo.</CardDescription>
  </CardHeader>
  <CardContent className="space-y-6">
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      {/* Left: Name + Theme Color */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="org-name">Organization Name</Label>
          <Input id="org-name" value={form.name} onChange={...} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="theme-color">Theme Color</Label>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md border" style={{ background: form.theme_color }} />
            <Input id="theme-color" value={form.theme_color} onChange={...} className="w-32" maxLength={7} />
            <input type="color" value={form.theme_color} onChange={...} className="w-10 h-10 cursor-pointer rounded border-0" />
          </div>
        </div>
      </div>
      {/* Right: Logo */}
      <div className="space-y-4">
        <Label>Logo</Label>
        {logoUrl && <img src={logoUrl} alt="Logo" className="w-32 h-16 object-contain border rounded-md p-1" />}
        <Button variant="outline" onClick={() => fileRef.current?.click()}>Upload new logo</Button>
        <input type="file" ref={fileRef} className="hidden" accept=".png,.jpg,.jpeg,.webp,.svg" onChange={handleLogoUpload} />
      </div>
    </div>
    <Separator />
    <div className="flex items-center justify-between">
      {message.text && <p className={message.type === 'success' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>{message.text}</p>}
      <Button onClick={handleSave} disabled={saving} className="ml-auto">{saving ? 'Saving...' : 'Save Changes'}</Button>
    </div>
  </CardContent>
</Card>
```

**Step 2: Delete OrgTab.module.css**

```bash
rm src/components/settings/OrgTab.module.css
```

**Step 3: Verify build**

**Step 4: Commit**

```bash
git add src/components/settings/OrgTab.jsx
git rm src/components/settings/OrgTab.module.css
git commit -m "feat: rewrite OrgTab with shadcn Card, Input, Label"
```

---

## Task 9: Rewrite MasterDataTab.jsx with shadcn Card + Collapsible

**Files:**
- Rewrite: `src/components/settings/MasterDataTab.jsx`
- Delete: `src/components/settings/MasterDataTab.module.css`

**Step 1: Rewrite MasterDataTab.jsx**

Each section in a `Card` with `Collapsible`. Inline editing via shadcn `Input` and `Checkbox`. Add/Remove row with `Button`.

```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChevronDown, Plus, Trash2 } from 'lucide-react';
```

EditableTable uses shadcn Table with Input/Checkbox cells. Remove button per row uses `<Button variant="ghost" size="icon"><Trash2 className="w-4 h-4 text-destructive" /></Button>`.

Add row: `<Button variant="outline" size="sm"><Plus className="w-4 h-4 mr-1" /> Add row</Button>`.

Default Language uses shadcn Select.

Save button at bottom: `<Button onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Save Master Data'}</Button>`.

**Step 2: Delete MasterDataTab.module.css**

```bash
rm src/components/settings/MasterDataTab.module.css
```

**Step 3: Verify build**

**Step 4: Commit**

```bash
git add src/components/settings/MasterDataTab.jsx
git rm src/components/settings/MasterDataTab.module.css
git commit -m "feat: rewrite MasterDataTab with shadcn Card, Collapsible, Table"
```

---

## Task 10: Visual Verification + Final Cleanup

**Step 1: Full build check**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build 2>&1 | tail -10
```

Expected: Build succeeds, 0 errors.

**Step 2: Visual test in browser**

Open `http://localhost:5174/settings` and verify:
- Users tab: table renders, Add User button works, dropdown actions work
- Organization tab: card layout, inputs, color picker, logo upload
- Master Data tab: collapsible sections, editable tables, save button

**Step 3: Check no stale CSS Module imports remain**

```bash
grep -r "module.css" src/components/settings/ src/pages/SettingsPage.jsx
```

Expected: No results.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Settings page shadcn migration — delete all custom CSS"
```
