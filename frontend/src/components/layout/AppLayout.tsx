import React, { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Topbar } from "./Topbar";
import { NavRail } from "./NavRail";
import { Sidebar } from "./Sidebar";
import { Outlet } from "react-router-dom";
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useThemeStore } from "../../store/themeStore";
import { useMailStore } from "../../store/mailStore";
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

  // Al volver a la vista de mail desde otra sección, resetear estado
  const prevIsMailRef = React.useRef(isMailRoute);
  useEffect(() => {
    if (isMailRoute && !prevIsMailRef.current) {
      const store = useMailStore.getState();
      // Limpiar mensaje seleccionado para evitar vista fantasma
      store.setSelectedMessage(null);
      // Resetear filtro para mostrar todos los mensajes
      if (store.filter !== 'all') {
        store.setFilter('all');
      }
      // Limpiar búsqueda
      if (store.searchQuery) {
        store.setSearchQuery('');
        store.setDebouncedSearchQuery('');
      }
      // Volver a INBOX si estaba en otra carpeta
      if (store.currentFolder !== 'INBOX') {
        store.setCurrentFolder('INBOX');
      }
    }
    prevIsMailRef.current = isMailRoute;
  }, [isMailRoute]);

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
      {/* Skip to content — accesibilidad (navegación por teclado) */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-[9999] focus:top-2 focus:left-2 focus:bg-[#0078d4] focus:text-white focus:px-4 focus:py-2 focus:rounded focus:text-sm">
        Ir al contenido principal
      </a>
      <OfflineBanner />
      <Topbar />
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop: show NavRail always, Sidebar only for mail */}
        {!isMobile && <nav role="navigation" aria-label="Navegación principal"><NavRail /></nav>}
        {!isMobile && !isTablet && showMailSidebar && <aside role="complementary" aria-label="Carpetas de correo"><Sidebar /></aside>}

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

        <main id="main-content" role="main" className="flex-1 flex flex-col overflow-hidden">
          <Outlet />
        </main>
        {/* Region de anuncios para lectores de pantalla */}
        <div aria-live="polite" aria-atomic="true" className="sr-only" id="a11y-announcer" />
      </div>
      <CommandPalette />
    </div>
  );
}
