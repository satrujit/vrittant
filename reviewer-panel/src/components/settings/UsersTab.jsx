import { useState, useEffect, useCallback, useMemo } from 'react';
import { UserPlus, MoreHorizontal, Users, Trash2, RotateCcw, Search, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  fetchOrgUsers, createUser, updateUser,
  updateUserRole, updateUserEntitlements,
} from '../../services/api';
import UserFormModal from './UserFormModal';
import EntitlementsModal from './EntitlementsModal';
import { useI18n } from '../../i18n';

const ROLE_STYLES = {
  reporter: 'bg-blue-50 text-blue-700 hover:bg-blue-50',
  reviewer: 'bg-amber-50 text-amber-700 hover:bg-amber-50',
  org_admin: 'bg-emerald-50 text-emerald-700 hover:bg-emerald-50',
};

const ROLE_LABELS = {
  reporter: 'Reporter',
  reviewer: 'Reviewer',
  org_admin: 'Org Admin',
};

const ROLE_FILTERS = [
  { value: 'all', label: 'All Roles' },
  { value: 'reporter', label: 'Reporters' },
  { value: 'reviewer', label: 'Reviewers' },
  { value: 'org_admin', label: 'Org Admins' },
];

const PAGE_SIZE = 20;

function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function UsersTab() {
  const { t } = useI18n();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [entitlementsUser, setEntitlementsUser] = useState(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [page, setPage] = useState(1);

  const loadUsers = useCallback(async () => {
    try {
      const data = await fetchOrgUsers({ includeInactive: showDeleted });
      setUsers(data.reporters || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [showDeleted]);

  useEffect(() => { setLoading(true); loadUsers(); }, [loadUsers]);

  const handleCreate = async (form) => {
    await createUser(form);
    await loadUsers();
  };

  const handleEdit = async (form) => {
    await updateUser(editUser.id, {
      name: form.name,
      email: form.email,
      area_name: form.area_name,
      categories: form.categories,
      regions: form.regions,
    });
    setEditUser(null);
    await loadUsers();
  };

  const handleToggleActive = async (u) => {
    await updateUser(u.id, { is_active: !u.is_active });
    await loadUsers();
  };

  const handleRoleChange = async (u, newRole) => {
    await updateUserRole(u.id, newRole);
    await loadUsers();
  };

  const handleEntitlements = async (pageKeys) => {
    await updateUserEntitlements(entitlementsUser.id, pageKeys);
    await loadUsers();
  };

  // Client-side filter — small dataset (typically <100 users), so no need
  // for server-side search. Match name / phone / email / area, case-insensitive.
  const filteredUsers = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return users.filter((u) => {
      if (roleFilter !== 'all' && u.user_type !== roleFilter) return false;
      if (!q) return true;
      return [u.name, u.phone, u.email, u.area_name]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(q));
    });
  }, [users, searchQuery, roleFilter]);

  // Reset to first page when filters change so user isn't stranded on an empty page.
  useEffect(() => { setPage(1); }, [searchQuery, roleFilter, showDeleted]);

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pagedUsers = filteredUsers.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        {t('common.loading')}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-lg font-semibold tracking-tight">{t('settings.users.title')}</h2>
          <Badge variant="secondary" className="text-xs">
            {t('settings.users.userCount', { count: filteredUsers.length })}
          </Badge>
        </div>
        <Button onClick={() => setShowAddModal(true)} size="sm">
          <UserPlus className="w-4 h-4 mr-2" />
          {t('settings.users.addUser')}
        </Button>
      </div>

      {/* Filters toolbar — search · role · show deleted */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          <Input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('settings.users.searchPlaceholder', 'Search users...')}
            className="h-8 w-[260px] pl-8 pr-7 text-xs"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground outline-none focus:border-primary"
        >
          {ROLE_FILTERS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>

        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none ml-auto">
          <Checkbox
            checked={showDeleted}
            onCheckedChange={(v) => setShowDeleted(!!v)}
          />
          {t('settings.users.showDeleted')}
        </label>
      </div>

      {/* Table or Empty State */}
      {users.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 border rounded-lg border-dashed">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-muted mb-4">
            <Users className="w-6 h-6 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium mb-1">{t('settings.users.noUsers')}</h3>
          <p className="text-sm text-muted-foreground mb-4">{t('settings.users.noUsersDesc')}</p>
          <Button onClick={() => setShowAddModal(true)} size="sm">
            <UserPlus className="w-4 h-4 mr-2" />
            {t('settings.users.addUser')}
          </Button>
        </div>
      ) : filteredUsers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 border rounded-lg border-dashed text-sm text-muted-foreground">
          {t('settings.users.noMatches', 'No users match your search.')}
        </div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[250px]">{t('settings.users.name')}</TableHead>
                <TableHead>{t('settings.users.phone')}</TableHead>
                <TableHead>{t('settings.users.role')}</TableHead>
                <TableHead>{t('settings.users.area')}</TableHead>
                <TableHead>{t('settings.users.status')}</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagedUsers.map((u) => (
                <TableRow key={u.id} className={!u.is_active ? 'opacity-50' : ''}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-semibold shrink-0">
                        {getInitials(u.name)}
                      </div>
                      <div>
                        <div className="font-medium">{u.name}</div>
                        {u.email && <div className="text-xs text-muted-foreground">{u.email}</div>}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.phone}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={ROLE_STYLES[u.user_type] || ''}>
                      {ROLE_LABELS[u.user_type] || u.user_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.area_name || '—'}</TableCell>
                  <TableCell>
                    {u.is_active ? (
                      <Badge variant="secondary" className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50">{t('settings.users.active')}</Badge>
                    ) : (
                      <Badge variant="destructive">{t('settings.users.deleted')}</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {u.is_active && (
                          <>
                            <DropdownMenuItem onClick={() => setEditUser(u)}>
                              {t('settings.users.edit')}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setEntitlementsUser(u)}>
                              {t('settings.users.entitlements')}
                            </DropdownMenuItem>
                          </>
                        )}
                        {u.user_type !== 'org_admin' && u.is_active && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => handleRoleChange(u, u.user_type === 'reporter' ? 'reviewer' : 'reporter')}>
                              {t('settings.users.makeRole', { role: u.user_type === 'reporter' ? t('settings.userForm.reviewer') : t('settings.userForm.reporter') })}
                            </DropdownMenuItem>
                          </>
                        )}
                        {u.user_type !== 'org_admin' && (
                          <>
                            {u.is_active && <DropdownMenuSeparator />}
                            <DropdownMenuItem
                              onClick={() => handleToggleActive(u)}
                              className={u.is_active ? 'text-destructive focus:text-destructive' : 'text-emerald-600 focus:text-emerald-600'}
                            >
                              {u.is_active ? (
                                <><Trash2 className="w-4 h-4 mr-2" />{t('settings.users.deleteUser')}</>
                              ) : (
                                <><RotateCcw className="w-4 h-4 mr-2" />{t('settings.users.restoreUser')}</>
                              )}
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <div className="flex items-center justify-end gap-2 border-t px-3 py-2">
              <span className="text-xs text-muted-foreground tabular-nums">
                Page {pageSafe} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage(Math.max(1, pageSafe - 1))}
                disabled={pageSafe === 1}
                aria-label="Previous page"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage(Math.min(totalPages, pageSafe + 1))}
                disabled={pageSafe === totalPages}
                aria-label="Next page"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
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
