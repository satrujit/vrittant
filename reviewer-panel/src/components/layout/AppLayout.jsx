import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useSidebarCollapsed } from '../../hooks/useSidebarCollapsed';
import { cn } from '@/lib/utils';

function AppLayout() {
  const [collapsed] = useSidebarCollapsed();
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main
        className={cn(
          'flex-1 h-screen overflow-auto bg-background transition-[margin] duration-200',
          collapsed ? 'ml-[64px]' : 'ml-[240px]'
        )}
      >
        <Outlet />
      </main>
    </div>
  );
}

export default AppLayout;
