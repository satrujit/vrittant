import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Settings } from 'lucide-react';
import UsersTab from '../components/settings/UsersTab';
import OrgTab from '../components/settings/OrgTab';
import MasterDataTab from '../components/settings/MasterDataTab';
import { useI18n } from '../i18n';
import { PageHeader } from '../components/common';

function SettingsPage() {
  const { user } = useAuth();
  const { t } = useI18n();

  if (user?.user_type !== 'org_admin') {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        icon={Settings}
        title={t('settings.title')}
        subtitle={t('settings.subtitle')}
      />

      <Tabs defaultValue="users" className="space-y-6">
        <TabsList>
          <TabsTrigger value="users">{t('settings.tabs.users')}</TabsTrigger>
          <TabsTrigger value="organization">{t('settings.tabs.organization')}</TabsTrigger>
          <TabsTrigger value="master-data">{t('settings.tabs.masterData')}</TabsTrigger>
        </TabsList>
        <TabsContent value="users"><UsersTab /></TabsContent>
        <TabsContent value="organization"><OrgTab /></TabsContent>
        <TabsContent value="master-data"><MasterDataTab /></TabsContent>
      </Tabs>
    </div>
  );
}

export default SettingsPage;
