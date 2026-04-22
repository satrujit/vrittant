import { useState, useEffect, useCallback } from 'react';
import { UserPlus, MoreHorizontal, Users, Trash2, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold tracking-tight">{t('settings.users.title')}</h2>
          <Badge variant="secondary" className="text-xs">
            {t('settings.users.userCount', { count: users.length })}
          </Badge>
          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none ml-2">
            <Checkbox
              checked={showDeleted}
              onCheckedChange={(v) => setShowDeleted(!!v)}
            />
            {t('settings.users.showDeleted')}
          </label>
        </div>
        <Button onClick={() => setShowAddModal(true)} size="sm">
          <UserPlus className="w-4 h-4 mr-2" />
          {t('settings.users.addUser')}
        </Button>
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
              {users.map((u) => (
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
