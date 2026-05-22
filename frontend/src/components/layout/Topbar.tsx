import { PresenceSelector } from '../common/PresenceSelector';
import { useState, useEffect, useRef } from 'react';
import { useAuthStore } from '../../store/authStore';
import { useMailStore } from '../../store/mailStore';
import { useThemeStore } from '../../store/themeStore';
import { useNavigate } from 'react-router-dom';
import { getFolderDisplayName } from '../../folders';
import { SearchAdvanced } from "../common/SearchAdvanced";
import { useResponsive } from "../../hooks/useResponsive";

const appsIcon = 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z';
const bellIcon = 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9';
const settingsIcon = 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065zM15 12a3 3 0 11-6 0 3 3 0 016 0z';
const helpIcon = 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
const moonIcon = 'M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z';
const sunIcon = 'M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z';

export function Topbar() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const searchQuery = useMailStore(s => s.searchQuery);
  const setSearchQuery = useMailStore(s => s.setSearchQuery);
  const folders = useMailStore(s => s.folders);
  const setCurrentFolder = useMailStore(s => s.setCurrentFolder);
  const { dark, toggle: toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  const { isMobile, isTablet } = useResponsive();
  const [showApps, setShowApps] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission | 'unsupported'>(
    typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'unsupported'
  );
  const appsRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const helpRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  const handleLogout = async () => {
    try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }); } catch {}
    logout();
    navigate('/login');
  };

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (appsRef.current && !appsRef.current.contains(e.target as Node)) setShowApps(false);
      if (notificationsRef.current && !notificationsRef.current.contains(e.target as Node)) setShowNotifications(false);
      if (helpRef.current && !helpRef.current.contains(e.target as Node)) setShowHelp(false);
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) setShowProfile(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  useEffect(() => {
    const syncPermission = () => {
      setNotificationPermission(typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'unsupported');
    };
    syncPermission();
    window.addEventListener('focus', syncPermission);
    return () => window.removeEventListener('focus', syncPermission);
  }, []);

  const initials = user?.username?.split('@')[0]?.slice(0, 2)?.toUpperCase() || '?';
  const displayName = user?.username?.split('@')[0]?.replace(/\./g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || '';
  const displayEmail = user?.username || '';
  const excludedFromCount = ["Junk", "Spam", "Trash", "No deseado", "Papelera", "Correo no deseado"];
  const unreadFolders = (folders || []).filter((folder) => folder.unseen > 0);
  const unreadTotal = unreadFolders.filter((f) => !excludedFromCount.some((ex) => f.name.toLowerCase() === ex.toLowerCase())).reduce((total, folder) => total + folder.unseen, 0);
  const topUnreadFolders = [...unreadFolders]
    .sort((a, b) => b.unseen - a.unseen)
    .slice(0, 5);

  const permissionLabel =
    notificationPermission === 'granted' ? 'Activadas' :
    notificationPermission === 'default' ? 'Pendientes de permiso' :
    notificationPermission === 'denied' ? 'Bloqueadas por el navegador' :
    'No compatibles en este navegador';

  const requestBrowserNotifications = async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      setNotificationPermission('unsupported');
      return;
    }
    const permission = await Notification.requestPermission();
    setNotificationPermission(permission);
  };

  const openFolderFromNotifications = (folderName: string) => {
    setCurrentFolder(folderName);
    navigate('/');
    setShowNotifications(false);
  };

  const apps = [
    { name: 'Correo', icon: '\u2709\uFE0F', path: '/' },
    { name: 'Calendario', icon: '\uD83D\uDCC5', path: '/calendar' },
    { name: 'Contactos', icon: '\uD83D\uDC65', path: '/contacts' },
    { name: 'Tareas', icon: 'â', path: '/tasks' },
    ...(user?.is_admin ? [{ name: 'AdministraciÃ³n', icon: '\uD83D\uDEE1\uFE0F', path: '/admin' }] : []),
  ];

  return (
    <header role="banner" className="h-12 bg-[#0078d4] flex items-center px-3 gap-2 shrink-0 relative z-[100]">
      {/* Mobile hamburger */}
      {(isMobile || isTablet) && (
        <button onClick={() => window.dispatchEvent(new CustomEvent("toggle-mobile-drawer"))}
          className="w-8 h-8 rounded flex items-center justify-center text-white/80 hover:bg-white/15 transition-colors"
          title="MenÃº">
          <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}

      {/* Apps menu */}
      <div ref={appsRef} className="relative">
        <button onClick={() => setShowApps(!showApps)} title="Aplicaciones"
          className="w-8 h-8 rounded flex items-center justify-center text-white/80 hover:bg-white/15 transition-colors">
          <svg className="w-[18px] h-[18px]" fill="currentColor" viewBox="0 0 20 20">
            <path d={appsIcon} />
          </svg>
        </button>
        {showApps && (
          <div className="absolute left-0 top-full mt-1 w-52 bg-white rounded-lg shadow-xl border border-[#edebe9] z-[200] p-3 grid grid-cols-2 gap-1">
            {apps.map(a => (
              <button key={a.path} onClick={() => { navigate(a.path); setShowApps(false); }}
                className="flex flex-col items-center gap-1.5 p-3 rounded hover:bg-[#f3f2f1] transition-colors">
                <span className="text-xl">{a.icon}</span>
                <span className="text-[11px] text-[#323130]">{a.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Brand */}
      <div className="flex items-center gap-2 shrink-0">
        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <span className="topbar-logo-text text-white font-semibold text-[14px]">Maquita Mail</span>
      </div>

      {/* Search bar */}
      <div className="topbar-search flex-1 max-w-[680px] mx-auto">
        <SearchAdvanced
          value={searchQuery}
          onChange={setSearchQuery}
          onSearch={setSearchQuery}
          placeholder="Buscar en el correo (/ para enfocar)"
        />
      </div>

      {/* Right: Theme toggle + Notifications + Settings + Help + Profile */}
      <div className="flex items-center gap-0.5 shrink-0">
        <button onClick={toggleTheme} title={dark ? 'Modo claro' : 'Modo oscuro'}
          className="w-8 h-8 rounded flex items-center justify-center text-white/80 hover:bg-white/15 transition-colors">
          <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={dark ? sunIcon : moonIcon} />
          </svg>
        </button>
        <div ref={notificationsRef} className="relative">
          <button onClick={() => setShowNotifications(!showNotifications)} title="Notificaciones"
            className="relative w-8 h-8 rounded flex items-center justify-center text-white/80 hover:bg-white/15 transition-colors">
            <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={bellIcon} />
            </svg>
            {unreadTotal > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] px-1 rounded-full bg-[#d13438] text-white text-[10px] font-semibold flex items-center justify-center">
                {unreadTotal > 99 ? '99+' : unreadTotal}
              </span>
            )}
          </button>
          {showNotifications && (
            <div className="absolute right-0 top-full mt-1 w-80 bg-white rounded-lg shadow-xl border border-[#edebe9] z-[200] overflow-hidden">
              <div className="px-4 py-3 border-b border-[#edebe9]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[13px] font-semibold text-[#323130]">Notificaciones</p>
                    <p className="text-[11px] text-[#605e5c]">Estado del navegador: {permissionLabel}</p>
                  </div>
                  {notificationPermission === 'default' && (
                    <button
                      onClick={requestBrowserNotifications}
                      className="px-2.5 py-1 rounded bg-[#0078d4] text-white text-[11px] font-medium hover:bg-[#106ebe]"
                    >
                      Activar
                    </button>
                  )}
                </div>
              </div>
              <div className="px-4 py-3 border-b border-[#edebe9] bg-[#faf9f8]">
                <p className="text-[12px] font-medium text-[#323130]">
                  {unreadTotal > 0 ? `${unreadTotal} correo${unreadTotal > 1 ? 's' : ''} sin leer` : 'No hay correos sin leer'}
                </p>
                <p className="text-[11px] text-[#605e5c] mt-1">
                  {notificationPermission === 'granted'
                    ? 'Las alertas del navegador estÃ¡n activas para nuevos correos.'
                    : notificationPermission === 'denied'
                      ? 'Debes habilitar las notificaciones desde la configuraciÃ³n del navegador.'
                      : notificationPermission === 'unsupported'
                        ? 'Este navegador no expone notificaciones del sistema.'
                        : 'Puedes activar las notificaciones del navegador desde aquÃ­.'}
                </p>
              </div>
              <div className="py-1">
                {topUnreadFolders.length > 0 ? (
                  topUnreadFolders.map((folder) => (
                    <button
                      key={folder.name}
                      onClick={() => openFolderFromNotifications(folder.name)}
                      className="w-full px-4 py-2.5 text-left hover:bg-[#f3f2f1] transition-colors flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <p className="text-[12px] font-medium text-[#323130] truncate">{getFolderDisplayName(folder.name)}</p>
                        <p className="text-[11px] text-[#605e5c]">Abrir carpeta con pendientes</p>
                      </div>
                      <span className="shrink-0 min-w-[20px] h-[20px] px-1 rounded-full bg-[#deecf9] text-[#005a9e] text-[11px] font-semibold flex items-center justify-center">
                        {folder.unseen}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-6 text-center text-[12px] text-[#605e5c]">
                    No hay elementos pendientes para revisar.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        <button onClick={() => navigate('/settings')} title="ConfiguraciÃ³n"
          className="w-8 h-8 rounded flex items-center justify-center text-white/80 hover:bg-white/15 transition-colors">
          <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={settingsIcon} />
          </svg>
        </button>
        <div ref={helpRef} className="relative">
          <button onClick={() => setShowHelp(!showHelp)} title="Ayuda"
            className="w-8 h-8 rounded flex items-center justify-center text-white/80 hover:bg-white/15 transition-colors">
            <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={helpIcon} />
            </svg>
          </button>
          {showHelp && (
            <div className="absolute right-0 top-full mt-1 w-[340px] bg-white rounded-lg shadow-xl border border-[#edebe9] z-[200] overflow-hidden">
              <div className="px-4 py-3 border-b border-[#edebe9]">
                <p className="text-[13px] font-semibold text-[#323130]">Ayuda</p>
                <p className="text-[11px] text-[#605e5c] mt-1">GuÃ­a rÃ¡pida con funciones reales disponibles hoy en Maquita Mail.</p>
              </div>

              <div className="px-4 py-3 border-b border-[#edebe9]">
                <p className="text-[12px] font-semibold text-[#323130] mb-2">Acciones rÃ¡pidas</p>
                <div className="space-y-1.5 text-[12px] text-[#323130]">
                  <p><span className="font-medium">Buscar:</span> usa la barra superior o presiona <span className="font-mono text-[11px]">/</span>.</p>
                  <p><span className="font-medium">Vista:</span> puedes cambiar conversaciones, panel de lectura y vista previa desde la cinta.</p>
                  <p><span className="font-medium">Correo:</span> responder, reenviar, mover, archivar y eliminar ya estÃ¡n conectados al flujo real.</p>
                </div>
              </div>

              <div className="px-4 py-3 border-b border-[#edebe9] bg-[#faf9f8]">
                <p className="text-[12px] font-semibold text-[#323130] mb-2">Atajos de teclado</p>
                <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px] text-[#323130]">
                  <span className="font-mono text-[11px]">/</span><span>Enfocar la bÃºsqueda</span>
                  <span className="font-mono text-[11px]">N</span><span>Nuevo correo</span>
                  <span className="font-mono text-[11px]">R</span><span>Responder</span>
                  <span className="font-mono text-[11px]">Shift+R</span><span>Responder a todos</span>
                  <span className="font-mono text-[11px]">F</span><span>Reenviar</span>
                  <span className="font-mono text-[11px]">E</span><span>Archivar</span>
                  <span className="font-mono text-[11px]">Supr</span><span>Eliminar</span>
                </div>
              </div>

              <div className="px-4 py-3">
                <p className="text-[12px] font-semibold text-[#323130] mb-2">Soporte</p>
                <p className="text-[12px] text-[#323130]">Si necesitas ayuda operativa, escribe a <span className="font-medium">gestiontecnologia@maquita.org</span>.</p>
              </div>
            </div>
          )}
        </div>

        {/* Profile */}
        <div ref={profileRef} className="relative ml-1">
<PresenceSelector />
          <button onClick={() => setShowProfile(!showProfile)}
            className="w-8 h-8 rounded-full bg-[#106ebe] flex items-center justify-center text-white text-[11px] font-semibold hover:ring-2 hover:ring-white/30 transition-all">
            {initials}
          </button>
          {showProfile && (
            <div className="absolute right-0 top-full mt-1 w-64 bg-white rounded-lg shadow-xl border border-[#edebe9] z-[200] py-1">
              <div className="px-4 py-3 border-b border-[#edebe9] flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#0078d4] flex items-center justify-center text-white text-[14px] font-semibold shrink-0">
                  {initials}
                </div>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-[#323130] truncate">{displayName}</p>
                  <p className="text-[11px] text-[#605e5c] truncate">{displayEmail}</p>
                </div>
              </div>
              <button onClick={() => { navigate('/settings'); setShowProfile(false); }}
                className="w-full text-left px-4 py-2 text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2">
                <svg className="w-4 h-4 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={settingsIcon} />
                </svg>
                ConfiguraciÃ³n
              </button>
              <button onClick={() => {
                  setShowProfile(false);
                  // Check if installed
                  if (window.matchMedia('(display-mode: standalone)').matches) {
                    return;
                  }
                  if ((window as any).__pwaInstallPrompt) {
                    (window as any).__pwaInstallPrompt.prompt();
                  } else {
                    // iOS or no prompt available - dispatch event to show guide
                    if ((window as any).__pwaInstallFn) {
                      (window as any).__pwaInstallFn();
                    } else {
                      // Fallback: show manual instructions
                      const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                      if (isIOS) {
                        alert('Para instalar: toca Compartir > Agregar a pantalla de inicio');
                      } else {
                        alert('Para instalar: toca el men\u00fa del navegador (\u22ee) > Instalar aplicaci\u00f3n');
                      }
                    }
                  }
                }}
                className="w-full text-left px-4 py-2 text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2">
                <svg className="w-4 h-4 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                Instalar aplicaci\u00f3n
              </button>
              <a href="/webmail/downloads/MaquitaMail.apk" download="MaquitaMail.apk"
                className="w-full text-left px-4 py-2 text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2"
                onClick={() => setShowProfile(false)}>
                <svg className="w-4 h-4 text-[#3ddc84]" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 18c0 .55.45 1 1 1h1v3.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5V19h2v3.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5V19h1c.55 0 1-.45 1-1V7H6v11zM3.5 7C2.67 7 2 7.67 2 8.5v7c0 .83.67 1.5 1.5 1.5S5 16.33 5 15.5v-7C5 7.67 4.33 7 3.5 7zm17 0c-.83 0-1.5.67-1.5 1.5v7c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5v-7c0-.83-.67-1.5-1.5-1.5zm-4.97-5.84l1.3-1.3c.2-.2.2-.51 0-.71-.2-.2-.51-.2-.71 0l-1.48 1.48C13.85.55 12.95.25 12 .25s-1.85.3-2.64.83L7.88.59c-.2-.2-.51-.2-.71 0-.2.2-.2.51 0 .71l1.31 1.31C7.6 3.6 7 4.97 7 6h10c0-1.03-.6-2.4-1.47-3.84zM10 5H9V4h1v1zm5 0h-1V4h1v1z" />
                </svg>
                Descargar APK Android
              </a>
              <div className="h-px bg-[#edebe9] my-1" />
              <button onClick={handleLogout}
                className="w-full text-left px-4 py-2 text-[13px] text-[#a4262c] hover:bg-[#f3f2f1]">
                Cerrar sesiÃ³n
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

