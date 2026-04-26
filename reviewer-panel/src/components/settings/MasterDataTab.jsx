import { useState, useEffect, useMemo } from 'react';
import { fetchOrgConfig, updateOrgConfig } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../i18n';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, Trash2 } from 'lucide-react';

const LANG_MAP = { odia: 'or', english: 'en', hindi: 'hi' };

function EditableTable({ columns, rows, onChange, emptyMessage }) {
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
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((c) => (
              <TableHead key={c.key}>{c.label}</TableHead>
            ))}
            <TableHead className="w-[50px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, idx) => (
            <TableRow key={idx}>
              {columns.map((c) => (
                <TableCell key={c.key}>
                  {c.type === 'boolean' ? (
                    <Checkbox
                      checked={!!row[c.key]}
                      onCheckedChange={(checked) => updateRow(idx, c.key, checked)}
                    />
                  ) : c.type === 'number' ? (
                    <Input
                      type="number"
                      value={row[c.key] ?? ''}
                      onChange={(e) => updateRow(idx, c.key, parseInt(e.target.value) || 0)}
                      className="w-20"
                    />
                  ) : (
                    <Input
                      value={row[c.key] ?? ''}
                      onChange={(e) => updateRow(idx, c.key, e.target.value)}
                    />
                  )}
                </TableCell>
              ))}
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeRow(idx)}
                  className="h-8 w-8"
                >
                  <Trash2 className="w-4 h-4 text-destructive" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={columns.length + 1} className="text-center text-muted-foreground py-6">
                {emptyMessage}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <Button variant="outline" size="sm" onClick={addRow}>
        <Plus className="w-4 h-4 mr-1" /> {columns[0]?.addLabel}
      </Button>
    </div>
  );
}

function MasterDataTab() {
  const { refreshUser, refreshConfig } = useAuth();
  const { t, setLocale } = useI18n();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const categoryColumns = useMemo(() => [
    { key: 'key', label: t('settings.masterData.key'), type: 'text', addLabel: t('settings.masterData.addRow') },
    { key: 'label', label: t('settings.masterData.label'), type: 'text' },
    { key: 'label_local', label: t('settings.masterData.localLabel'), type: 'text' },
    { key: 'is_active', label: t('settings.masterData.active'), type: 'boolean' },
  ], [t]);

  const pubTypeColumns = useMemo(() => [
    { key: 'key', label: t('settings.masterData.key'), type: 'text', addLabel: t('settings.masterData.addRow') },
    { key: 'label', label: t('settings.masterData.label'), type: 'text' },
    { key: 'label_local', label: t('settings.masterData.localLabel'), type: 'text' },
    { key: 'is_active', label: t('settings.masterData.active'), type: 'boolean' },
  ], [t]);

  const pageColumns = useMemo(() => [
    { key: 'name', label: t('settings.masterData.name'), type: 'text', addLabel: t('settings.masterData.addRow') },
    { key: 'name_local', label: t('settings.masterData.localLabel'), type: 'text' },
    { key: 'sort_order', label: t('settings.masterData.sortOrder'), type: 'number' },
    { key: 'is_active', label: t('settings.masterData.active'), type: 'boolean' },
  ], [t]);

  const priorityColumns = useMemo(() => [
    { key: 'key', label: t('settings.masterData.key'), type: 'text', addLabel: t('settings.masterData.addRow') },
    { key: 'label', label: t('settings.masterData.label'), type: 'text' },
    { key: 'label_local', label: t('settings.masterData.localLabel'), type: 'text' },
    { key: 'is_active', label: t('settings.masterData.active'), type: 'boolean' },
  ], [t]);

  // Email Forwarders: backend stores List[str] but the editor is the
  // generic row-of-fields component, so we wrap each string in a
  // {email: …} row and unwrap before sending. Lets us reuse the same
  // add/remove UX as the other tabs.
  const forwarderColumns = useMemo(() => [
    { key: 'email', label: t('settings.masterData.forwarderEmail'), type: 'text', addLabel: t('settings.masterData.addRow') },
  ], [t]);

  const contributorColumns = useMemo(() => [
    { key: 'email', label: t('settings.masterData.contributorEmail'), type: 'text', addLabel: t('settings.masterData.addRow') },
    { key: 'name', label: t('settings.masterData.contributorName'), type: 'text' },
  ], [t]);

  useEffect(() => {
    fetchOrgConfig()
      .then((cfg) => {
        if (!cfg) {
          setConfig(cfg);
          return;
        }
        // Wrap email_forwarders strings as {email} rows so EditableTable
        // can edit them. We unwrap before save in handleSave.
        setConfig({
          ...cfg,
          email_forwarders: (cfg.email_forwarders || []).map((s) =>
            typeof s === 'string' ? { email: s } : s
          ),
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage({ type: '', text: '' });
    try {
      // Unwrap the {email} row format used by the table editor back
      // into the plain List[str] the backend expects for forwarders.
      // Drop empty rows so an admin who clicked "+ Add" without
      // typing doesn't end up with a junk allowlist entry.
      const payload = {
        ...config,
        email_forwarders: (config.email_forwarders || [])
          .map((row) => (typeof row === 'string' ? row : row?.email || ''))
          .map((s) => s.trim().toLowerCase())
          .filter(Boolean),
        whitelisted_contributors: (config.whitelisted_contributors || [])
          .map((row) => ({
            email: (row?.email || '').trim().toLowerCase(),
            name: (row?.name || '').trim(),
          }))
          .filter((row) => row.email && row.email.includes('@')),
      };
      const updated = await updateOrgConfig(payload);
      setConfig(updated);
      await refreshUser();
      await refreshConfig();
      if (config.default_language && LANG_MAP[config.default_language]) {
        setLocale(LANG_MAP[config.default_language]);
      }
      setMessage({ type: 'success', text: t('settings.masterData.saved') });
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        {t('settings.masterData.loading')}
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        {t('settings.masterData.noConfig')}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Tabs defaultValue="categories">
        <TabsList>
          <TabsTrigger value="categories">{t('settings.masterData.categories')}</TabsTrigger>
          <TabsTrigger value="publication_types">{t('settings.masterData.publicationTypes')}</TabsTrigger>
          <TabsTrigger value="page_suggestions">{t('settings.masterData.pageSuggestions')}</TabsTrigger>
          <TabsTrigger value="priority_levels">{t('settings.masterData.priorityLevels')}</TabsTrigger>
          <TabsTrigger value="email_forwarders">{t('settings.masterData.emailForwarders')}</TabsTrigger>
          <TabsTrigger value="contributors">{t('settings.masterData.whitelistedContributors')}</TabsTrigger>
        </TabsList>

        <TabsContent value="categories">
          <Card>
            <CardContent className="pt-6">
              <EditableTable
                columns={categoryColumns}
                rows={config.categories || []}
                onChange={(rows) => setConfig((c) => ({ ...c, categories: rows }))}
                emptyMessage={t('settings.masterData.noItems')}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="publication_types">
          <Card>
            <CardContent className="pt-6">
              <EditableTable
                columns={pubTypeColumns}
                rows={config.publication_types || []}
                onChange={(rows) => setConfig((c) => ({ ...c, publication_types: rows }))}
                emptyMessage={t('settings.masterData.noItems')}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="page_suggestions">
          <Card>
            <CardContent className="pt-6">
              <EditableTable
                columns={pageColumns}
                rows={config.page_suggestions || []}
                onChange={(rows) => setConfig((c) => ({ ...c, page_suggestions: rows }))}
                emptyMessage={t('settings.masterData.noItems')}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="priority_levels">
          <Card>
            <CardContent className="pt-6">
              <EditableTable
                columns={priorityColumns}
                rows={config.priority_levels || []}
                onChange={(rows) => setConfig((c) => ({ ...c, priority_levels: rows }))}
                emptyMessage={t('settings.masterData.noItems')}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="email_forwarders">
          <Card>
            <CardContent className="pt-6 space-y-3">
              <p className="text-xs text-muted-foreground">
                {t('settings.masterData.emailForwardersHelp', 'Gateway addresses we trust to forward inbound reporter email into Vrittant. A message is dropped silently if the forwarding gateway (extracted from the Received: chain) is not in this list.')}
              </p>
              <EditableTable
                columns={forwarderColumns}
                rows={config.email_forwarders || []}
                onChange={(rows) => setConfig((c) => ({ ...c, email_forwarders: rows }))}
                emptyMessage={t('settings.masterData.noItems')}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="contributors">
          <Card>
            <CardContent className="pt-6 space-y-3">
              <p className="text-xs text-muted-foreground">
                {t('settings.masterData.whitelistedContributorsHelp', 'Email addresses of non-reporter contributors (columnists, external editorial writers) whose stories should be accepted. The first email from each new address auto-creates a passive reporter record so attribution and history work the same as for a regular reporter.')}
              </p>
              <EditableTable
                columns={contributorColumns}
                rows={config.whitelisted_contributors || []}
                onChange={(rows) => setConfig((c) => ({ ...c, whitelisted_contributors: rows }))}
                emptyMessage={t('settings.masterData.noItems')}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label>{t('settings.masterData.defaultLanguage')}</Label>
            <Select
              value={config.default_language || 'odia'}
              onValueChange={(val) => setConfig((c) => ({ ...c, default_language: val }))}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="odia">{t('settings.masterData.langOdia')}</SelectItem>
                <SelectItem value="english">{t('settings.masterData.langEnglish')}</SelectItem>
                <SelectItem value="hindi">{t('settings.masterData.langHindi')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {message.text && (
            <p className={message.type === 'success' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>
              {message.text}
            </p>
          )}
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? t('settings.masterData.saving') : t('settings.masterData.save')}
        </Button>
      </div>
    </div>
  );
}

export default MasterDataTab;
