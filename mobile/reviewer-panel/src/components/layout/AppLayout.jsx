import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-[240px] flex-1 h-screen overflow-auto bg-background">
        <Outlet />
      </main>
    </div>
  );
}

export default AppLayout;
