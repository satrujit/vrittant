import { useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader,
  DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { useI18n } from '../../i18n';

// Keep in sync with the sidebar entitlementKey values (Sidebar.jsx). Adding
// a new page = add it here so org_admins can grant it. New keys also need
// a backfill migration for existing users created before the page existed.
const ALL_PAGE_KEYS = ['dashboard', 'stories', 'review', 'editions', 'reporters', 'social_export', 'news_feed'];

function EntitlementsModal({ isOpen, onClose, onSubmit, userName, currentEntitlements }) {
  const { t } = useI18n();
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
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>{t('settings.entitlements.title')}</DialogTitle>
          <DialogDescription>
            {t('settings.entitlements.subtitle')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1 py-2">
          {ALL_PAGE_KEYS.map((key) => (
            <div
              key={key}
              className="flex items-center space-x-3 rounded-md px-2 py-2.5 hover:bg-muted/50 transition-colors"
            >
              <Checkbox
                id={key}
                checked={selected.has(key)}
                onCheckedChange={() => toggle(key)}
              />
              <Label
                htmlFor={key}
                className="text-sm font-normal cursor-pointer flex-1"
              >
                {t(`settings.entitlements.pages.${key}`) || key}
              </Label>
            </div>
          ))}
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>{t('settings.entitlements.cancel')}</Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? t('common.saving') : t('settings.entitlements.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default EntitlementsModal;
