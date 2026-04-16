import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { updateOrg, uploadOrgLogo, getMediaUrl } from '../../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Upload, Loader2 } from 'lucide-react';
import { useI18n } from '../../i18n';

function OrgTab() {
  const { user, refreshUser } = useAuth();
  const { t } = useI18n();
  const org = user?.org;
  const fileRef = useRef(null);

  const [form, setForm] = useState({ name: '' });
  const [logoUrl, setLogoUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    if (org) {
      setForm({ name: org.name || '' });
      setLogoUrl(org.logo_url ? getMediaUrl(org.logo_url) : '');
    }
  }, [org]);

  const handleSave = async () => {
    setSaving(true);
    setMessage({ type: '', text: '' });
    try {
      await updateOrg(form);
      await refreshUser();
      setMessage({ type: 'success', text: t('settings.org.updated') });
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to update' });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage({ type: '', text: '' });
    try {
      const result = await uploadOrgLogo(file);
      setLogoUrl(getMediaUrl(result.logo_url));
      await refreshUser();
      setMessage({ type: 'success', text: t('settings.org.logoUpdated') });
    } catch (err) {
      setMessage({ type: 'error', text: err.message || t('settings.org.uploadFailed') });
    } finally {
      setUploading(false);
    }
  };

  const triggerFileInput = () => {
    fileRef.current?.click();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('settings.org.title')}</CardTitle>
        <CardDescription>{t('settings.org.subtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Left column: Name */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">{t('settings.org.name')}</Label>
              <Input
                id="org-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder={t('settings.org.namePlaceholder')}
              />
            </div>
          </div>

          {/* Right column: Logo */}
          <div className="space-y-4">
            <Label>{t('settings.org.logo')}</Label>
            <div className="flex flex-col items-start gap-3">
              {logoUrl ? (
                <img
                  src={logoUrl}
                  alt="Organization logo"
                  className="w-32 h-16 object-contain border rounded-md p-1 bg-white"
                />
              ) : (
                <div className="w-32 h-16 border rounded-md flex items-center justify-center bg-muted/50">
                  <span className="text-xs text-muted-foreground">{t('settings.org.noLogo')}</span>
                </div>
              )}
              <Button variant="outline" size="sm" onClick={triggerFileInput} disabled={uploading}>
                {uploading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4 mr-2" />
                )}
                {uploading ? t('settings.org.uploading') : t('settings.org.uploadLogo')}
              </Button>
              <input
                type="file"
                ref={fileRef}
                style={{ display: 'none' }}
                accept=".png,.jpg,.jpeg,.webp,.svg"
                onChange={handleLogoUpload}
              />
            </div>
          </div>
        </div>

        <Separator />

        <div className="flex items-center justify-between">
          <div>
            {message.text && (
              <p className={message.type === 'success' ? 'text-sm text-emerald-600' : 'text-sm text-destructive'}>
                {message.text}
              </p>
            )}
          </div>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? t('settings.org.saving') : t('settings.org.saveChanges')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default OrgTab;
