import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Topbar } from "./Topbar";
import { NavRail } from "./NavRail";
import { Sidebar } from "./Sidebar";
import { Outlet } from "react-router-dom";
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useThemeStore } from "../../store/themeStore";
import { CommandPalette } from "../common/CommandPalette";
import { useResponsive } from "../../hooks/useResponsive";
import { OfflineBanner } from "../common/OfflineBanner";

export function AppLayout() {
  useKeyboardShortcuts();
  useWebSocket();
  const dark = useThemeStore((s) => s.dark);
  const { isMobile, isTablet, drawerOpen, closeDrawer, toggleDrawer } = useResponsive();
  const location = useLocation();

  // Only show mail sidebar on mail routes (index, /)
  const isMailRoute = location.pathname === '/' || location.pathname === '/webmail' || location.pathname === '/webmail/';
  const showMailSidebar = isMailRoute;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  useEffect(() => {
    const handler = () => toggleDrawer();
    window.addEventListener("toggle-mobile-drawer", handler);
    return () => window.removeEventListener("toggle-mobile-drawer", handler);
  }, [toggleDrawer]);

  useEffect(() => {
    if (drawerOpen) closeDrawer();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#f3f2f1]">
      <OfflineBanner />
      <Topbar />
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop: show NavRail always, Sidebar only for mail */}
        {!isMobile && <NavRail />}
        {!isMobile && !isTablet && showMailSidebar && <Sidebar />}

        {/* Tablet: show Sidebar in drawer only for mail */}
        {isTablet && drawerOpen && showMailSidebar && (
          <>
            <div className="fixed inset-0 bg-black/30 z-40" onClick={closeDrawer} />
            <div className="fixed left-[48px] top-[40px] bottom-0 z-50 animate-slideIn">
              <Sidebar />
            </div>
          </>
        )}

        {/* Mobile: show NavRail + Sidebar in full drawer */}
        {isMobile && drawerOpen && (
          <>
            <div className="fixed inset-0 bg-black/30 z-40" onClick={closeDrawer} />
            <div className="fixed left-0 top-[40px] bottom-0 z-50 flex animate-slideIn">
              <NavRail />
              {showMailSidebar && <Sidebar />}
            </div>
          </>
        )}

        <div className="flex-1 flex flex-col overflow-hidden">
          <Outlet />
        </div>
      </div>
      <CommandPalette />
    </div>
  );
}
