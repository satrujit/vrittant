import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Archive, Users, Columns3, Newspaper, Trophy, LogOut, Settings, LayoutGrid, Megaphone } from 'lucide-react';
import { useI18n } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';
import { getInitialsFromName, getMediaUrl } from '../../services/api';
import { cn } from '@/lib/utils';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';

const NAV_ITEMS = [
  { key: 'dashboard',   path: '/',           icon: LayoutDashboard, labelKey: 'nav.dashboard',   entitlementKey: 'dashboard' },
  { key: 'allStories',  path: '/stories',    icon: Archive,         labelKey: 'nav.allStories',  entitlementKey: 'stories' },
  { key: 'reporters',   path: '/reporters',  icon: Users,           labelKey: 'Users',           entitlementKey: 'reporters' },
  { key: 'leaderboard', path: '/leaderboard', icon: Trophy,          labelKey: 'Leaderboard',     entitlementKey: 'dashboard' },
  { key: 'pageBuckets', path: '/buckets',    icon: Columns3,        labelKey: 'nav.pageBuckets', entitlementKey: 'editions' },
  { key: 'newsFeed',    path: '/news-feed',  icon: Newspaper,       labelKey: 'nav.newsFeed',    entitlementKey: 'news_feed' },
  { key: 'widgets',     path: '/widgets',    icon: LayoutGrid,      labelKey: 'Widgets',         entitlementKey: 'dashboard' },
  { key: 'ads',         path: '/ads',        icon: Megaphone,       labelKey: 'nav.ads',         entitlementKey: 'ads' },
];

const navItemBase =
  'flex items-center gap-3 py-2 px-3 rounded-lg no-underline text-[0.8125rem] font-medium transition-all duration-150 cursor-pointer';

const navItemInactive =
  'text-muted-foreground hover:bg-accent hover:text-foreground';

const navItemActive =
  'bg-primary/10 text-primary';

/** Small Vrittant wordmark — slanted orange V with overlapping letters */
function VrittantWordmark() {
  return (
    <div className="flex items-center gap-1 opacity-80 hover:opacity-100 transition-opacity duration-150">
      <svg width="16" height="14" viewBox="80 100 160 110" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M112 122C128 202 192 202 208 122" stroke="#FA6C38" strokeWidth="19.2" strokeLinecap="round" strokeLinejoin="round"/>
        <path opacity="0.7" d="M128 138C140 186 180 186 192 138" stroke="#FA6C38" strokeWidth="12.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path opacity="0.4" d="M144 154C148 174 172 174 176 154" stroke="#FA6C38" strokeWidth="6.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      <span className="text-xs font-bold text-foreground tracking-[-0.07em]">
        <span className="text-[#FA6C38] italic font-extrabold -mr-px">V</span>rittant
      </span>
    </div>
  );
}

function Sidebar() {
  const { t } = useI18n();
  const { user, logout, hasEntitlement } = useAuth();

  const visibleNavItems = NAV_ITEMS.filter((item) =>
    hasEntitlement(item.entitlementKey)
  );
  const isOrgAdmin = user?.user_type === 'org_admin';

  const initials = user?.name ? getInitialsFromName(user.name) : '?';

  return (
    <aside className="fixed inset-y-0 left-0 w-[240px] h-screen flex flex-col bg-card border-r border-border py-3 z-[100]">
      {/* Newspaper brand logo — dynamic from org */}
      <div className="flex items-center justify-center px-5 py-2 mb-5">
        {user?.org?.logo_url ? (
          <img
            src={getMediaUrl(user.org.logo_url)}
            alt={user?.org?.name || 'Organization'}
            className="max-w-[180px] h-auto object-contain"
            onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling && (e.target.nextSibling.style.display = 'block'); }}
          />
        ) : null}
        {!user?.org?.logo_url && (
          <span className="text-xl font-bold text-foreground tracking-tight">{user?.org?.name || 'Vrittant'}</span>
        )}
      </div>

      {/* Powered by Vrittant */}
      <div className="flex items-center justify-end px-5 -mt-3 mb-3">
        <div className="flex items-center gap-1 opacity-80">
          <span className="text-[10px] text-muted-foreground">Powered by</span>
          <VrittantWordmark />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1 px-2 flex-1">
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.key}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                cn(navItemBase, isActive ? navItemActive : navItemInactive)
              }
            >
              <Icon size={20} className="shrink-0" />
              <span className="whitespace-nowrap overflow-hidden text-ellipsis">{t(item.labelKey)}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Settings — org_admin only */}
      {isOrgAdmin && (
        <div className="px-2 border-t border-border pt-2">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(navItemBase, isActive ? navItemActive : navItemInactive)
            }
          >
            <Settings size={20} className="shrink-0" />
            <span className="whitespace-nowrap overflow-hidden text-ellipsis">{t('nav.settings')}</span>
          </NavLink>
        </div>
      )}

      {/* Bottom: Profile with popover logout */}
      <div className="mt-auto border-t border-border pt-2 px-2 pb-3">
        <Popover>
          <PopoverTrigger asChild>
            <button className="flex items-center gap-2 w-full px-3 py-2 rounded-lg hover:bg-accent transition-colors cursor-pointer bg-transparent border-none text-left">
              <div className="size-[28px] rounded-full bg-[#3D3B8E] text-white flex items-center justify-center text-[10px] font-semibold shrink-0">
                {initials}
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-[11px] font-semibold text-foreground truncate">{user?.name || ''}</span>
                <span className="text-[10px] text-muted-foreground truncate">{user?.user_type || ''}</span>
              </div>
            </button>
          </PopoverTrigger>
          <PopoverContent side="top" align="start" className="w-[200px] p-1 z-[200]">
            <button
              onClick={logout}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-destructive hover:bg-destructive/10 transition-colors cursor-pointer bg-transparent border-none"
            >
              <LogOut size={14} />
              {t('auth.logout')}
            </button>
          </PopoverContent>
        </Popover>
      </div>
    </aside>
  );
}

export default Sidebar;
