import { useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader,
  DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { useI18n } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';

function normalizeRegions(value) {
  if (Array.isArray(value)) return value.map((s) => String(s).trim()).filter(Boolean);
  if (typeof value === 'string') {
    return value.split(',').map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

function UserFormModal({ isOpen, onClose, onSubmit, user }) {
  const { t, locale } = useI18n();
  const { config } = useAuth();
  const isEdit = !!user;

  const masterCategories = (config?.categories || []).filter((c) => c.is_active !== false);

  const [form, setForm] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    email: user?.email || '',
    area_name: user?.area_name || user?.areaName || '',
    user_type: user?.user_type || 'reporter',
    categories: Array.isArray(user?.categories) ? [...user.categories] : [],
    regionsText: Array.isArray(user?.regions) ? user.regions.join(', ') : '',
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleChange = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const toggleCategory = (key) => {
    setForm((f) => ({
      ...f,
      categories: f.categories.includes(key)
        ? f.categories.filter((k) => k !== key)
        : [...f.categories, key],
    }));
  };

  const isReporter = form.user_type === 'reporter';
  const isReviewer = form.user_type === 'reviewer';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim()) { setError(t('settings.userForm.nameRequired')); return; }
    if (!isEdit && !form.phone.trim()) { setError(t('settings.userForm.phoneRequired')); return; }
    if (isReporter && !form.area_name.trim()) {
      setError(t('settings.users.areaRequired'));
      return;
    }
    // Ensure phone has +91 prefix
    const submitForm = {
      name: form.name,
      email: form.email,
      area_name: form.area_name,
    };
    if (!isEdit) {
      submitForm.phone = form.phone;
      submitForm.user_type = form.user_type;
      if (submitForm.phone) {
        const digits = submitForm.phone.replace(/[^\d]/g, '');
        if (!submitForm.phone.startsWith('+')) {
          submitForm.phone = '+91' + digits.replace(/^91/, '');
        }
      }
    }
    // Reviewer scope (categories/regions) — only meaningful for reviewers, but
    // backend accepts empty arrays for other roles.
    if (isReviewer) {
      submitForm.categories = form.categories;
      submitForm.regions = normalizeRegions(form.regionsText);
    } else {
      submitForm.categories = [];
      submitForm.regions = [];
    }
    setSaving(true);
    try {
      await onSubmit(submitForm);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[480px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? t('settings.userForm.editTitle') : t('settings.userForm.addTitle')}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <p className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">
              {error}
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="name">{t('settings.userForm.name')}</Label>
            <Input
              id="name"
              value={form.name}
              onChange={handleChange('name')}
              placeholder={t('settings.userForm.namePlaceholder')}
              required
            />
          </div>
          {!isEdit && (
            <div className="space-y-2">
              <Label htmlFor="phone">{t('settings.userForm.phone')}</Label>
              <div className="flex">
                <span className="inline-flex items-center rounded-l-md border border-r-0 border-input bg-muted px-3 text-sm text-muted-foreground">
                  +91
                </span>
                <Input
                  id="phone"
                  className="rounded-l-none"
                  value={form.phone.startsWith('+91') ? form.phone.slice(3) : form.phone.replace(/^\+/, '')}
                  onChange={(e) => {
                    const val = e.target.value.replace(/[^\d\s]/g, '');
                    setForm((f) => ({ ...f, phone: '+91' + val.replace(/\s/g, '') }));
                  }}
                  placeholder="00000 00000"
                  type="tel"
                  inputMode="numeric"
                  required
                />
              </div>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="email">{t('settings.userForm.email')}</Label>
            <Input
              id="email"
              value={form.email}
              onChange={handleChange('email')}
              placeholder={t('settings.userForm.emailPlaceholder')}
              type="email"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="area">
              {t('settings.userForm.area')}
              {isReporter && <span className="text-destructive ml-0.5">*</span>}
            </Label>
            <Input
              id="area"
              value={form.area_name}
              onChange={handleChange('area_name')}
              placeholder={t('settings.userForm.areaPlaceholder')}
              required={isReporter}
            />
          </div>
          {!isEdit && (
            <div className="space-y-2">
              <Label>{t('settings.userForm.role')}</Label>
              <Select
                value={form.user_type}
                onValueChange={(val) => setForm((f) => ({ ...f, user_type: val }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="reporter">{t('settings.userForm.reporter')}</SelectItem>
                  <SelectItem value="reviewer">{t('settings.userForm.reviewer')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {isReviewer && (
            <>
              <div className="space-y-2">
                <Label>{t('settings.users.categories')}</Label>
                {masterCategories.length === 0 ? (
                  <p className="text-xs text-muted-foreground italic">—</p>
                ) : (
                  <div className="grid grid-cols-2 gap-2 border rounded-md p-3 max-h-40 overflow-y-auto">
                    {masterCategories.map((cat) => {
                      const checked = form.categories.includes(cat.key);
                      const label = (locale !== 'en' && cat.label_local) ? cat.label_local : (cat.label || cat.key);
                      return (
                        <label
                          key={cat.key}
                          className="flex items-center gap-2 text-sm cursor-pointer select-none"
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => toggleCategory(cat.key)}
                          />
                          <span>{label}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">{t('settings.users.categoriesHelp')}</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="regions">{t('settings.users.regions')}</Label>
                <Input
                  id="regions"
                  value={form.regionsText}
                  onChange={handleChange('regionsText')}
                  placeholder="Bhubaneswar, Cuttack, Puri"
                />
                <p className="text-xs text-muted-foreground">{t('settings.users.regionsHelp')}</p>
              </div>
            </>
          )}

          <DialogFooter className="gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {t('settings.userForm.cancel')}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? t('settings.userForm.saving') : isEdit ? t('settings.userForm.update') : t('settings.userForm.add')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default UserFormModal;
