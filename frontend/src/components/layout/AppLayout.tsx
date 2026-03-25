import { useEffect } from 'react';
import { Topbar } from './Topbar';
import { NavRail } from './NavRail';
import { Sidebar } from './Sidebar';
import { Outlet } from 'react-router-dom';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';
import { useThemeStore } from '../../store/themeStore';

export function AppLayout() {
  useKeyboardShortcuts();
  const dark = useThemeStore((s) => s.dark);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#f3f2f1]">
      <Topbar />
      <div className="flex-1 flex overflow-hidden">
        <NavRail />
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
