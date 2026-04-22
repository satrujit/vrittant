import { useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader,
  DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { useI18n } from '../../i18n';

function UserFormModal({ isOpen, onClose, onSubmit, user }) {
  const { t } = useI18n();
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

  const handleChange = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim()) { setError(t('settings.userForm.nameRequired')); return; }
    if (!isEdit && !form.phone.trim()) { setError(t('settings.userForm.phoneRequired')); return; }
    // Ensure phone has +91 prefix
    const submitForm = { ...form };
    if (!isEdit && submitForm.phone) {
      const digits = submitForm.phone.replace(/[^\d]/g, '');
      if (!submitForm.phone.startsWith('+')) {
        submitForm.phone = '+91' + digits.replace(/^91/, '');
      }
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
      <DialogContent className="sm:max-w-[425px]">
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
            <Label htmlFor="area">{t('settings.userForm.area')}</Label>
            <Input
              id="area"
              value={form.area_name}
              onChange={handleChange('area_name')}
              placeholder={t('settings.userForm.areaPlaceholder')}
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
