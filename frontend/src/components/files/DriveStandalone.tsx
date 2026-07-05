import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { FilesView } from './FilesView';

/* Almacén como PRODUCTO independiente (estilo Google Drive):
   URL propia (/drive), pantalla completa solo de archivos, y el lanzador de
   aplicaciones (cuadrícula) arriba a la derecha para saltar a Correo,
   Calendario, Contactos o Tareas — la misma sesión sirve para todo. */

interface Branding { org_name?: string; logo_url?: string; }

const APPS = [
  { ruta: '/', etiqueta: 'Correo', icono: '✉️', detalle: 'Bandeja de entrada' },
  { ruta: '/calendar', etiqueta: 'Calendario', icono: '📅', detalle: 'Eventos y reuniones' },
  { ruta: '/contacts', etiqueta: 'Contactos', icono: '👤', detalle: 'Directorio' },
  { ruta: '/tasks', etiqueta: 'Tareas', icono: '✅', detalle: 'Pendientes' },
  { ruta: '/drive', etiqueta: 'Archivos', icono: '📁', detalle: 'Tu nube (estás aquí)' },
];

export function DriveStandalone() {
  const navigate = useNavigate();
  const user = useAuthStore(s => s.user);
  const logoutStore = useAuthStore(s => s.logout);
  const [branding, setBranding] = useState<Branding>({});
  const [menuApps, setMenuApps] = useState(false);
  const [menuUsuario, setMenuUsuario] = useState(false);

  useEffect(() => {
    fetch('/api/branding').then(r => r.ok ? r.json() : {}).then(setBranding).catch(() => {});
    document.title = 'Archivos — Almacén';
  }, []);

  useEffect(() => {
    const cerrar = () => { setMenuApps(false); setMenuUsuario(false); };
    window.addEventListener('click', cerrar);
    return () => window.removeEventListener('click', cerrar);
  }, []);

  const cerrarSesion = async () => {
    try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }); } catch { /* la cookie expira sola */ }
    logoutStore();
    navigate('/login');
  };

  const iniciales = (user?.username || '?').slice(0, 2).toUpperCase();

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-[#1b1a19]">
      {/* Cabecera estilo Drive */}
      <header className="flex items-center gap-3 px-4 py-2 border-b border-[#edebe9] dark:border-[#3b3a39] bg-white dark:bg-[#252423]">
        <div className="flex items-center gap-2 select-none">
          {branding.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-8 w-8 object-contain rounded" />
          ) : (
            <span className="text-2xl">☁️</span>
          )}
          <span className="text-lg font-semibold text-[#323130] dark:text-[#e0e0e0]">
            {branding.org_name ? `${branding.org_name} Archivos` : 'Archivos'}
          </span>
        </div>
        <div className="flex-1" />

        {/* Lanzador de aplicaciones (cuadrícula, como Drive) */}
        <div className="relative">
          <button onClick={e => { e.stopPropagation(); setMenuApps(v => !v); setMenuUsuario(false); }}
            title="Aplicaciones: Correo, Calendario, Contactos, Tareas"
            className="w-10 h-10 rounded-full hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39] flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="#605e5c">
              {[2, 10, 18].flatMap(y => [2, 10, 18].map(x => (
                <circle key={`${x}${y}`} cx={x + 1} cy={y + 1} r="2" />
              )))}
            </svg>
          </button>
          {menuApps && (
            <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded-xl shadow-xl p-3 z-50"
              onClick={e => e.stopPropagation()}>
              <div className="grid grid-cols-3 gap-2">
                {APPS.map(app => (
                  <button key={app.ruta}
                    onClick={() => { setMenuApps(false); navigate(app.ruta); }}
                    title={app.detalle}
                    className={`flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39] ${app.ruta === '/drive' ? 'bg-[#deecf9] dark:bg-[#004578]' : ''}`}>
                    <span className="text-2xl">{app.icono}</span>
                    <span className="text-xs text-[#323130] dark:text-[#e0e0e0]">{app.etiqueta}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Usuario */}
        <div className="relative">
          <button onClick={e => { e.stopPropagation(); setMenuUsuario(v => !v); setMenuApps(false); }}
            title={user?.username || ''}
            className="w-9 h-9 rounded-full bg-[#0078d4] text-white text-sm font-semibold flex items-center justify-center hover:opacity-90">
            {iniciales}
          </button>
          {menuUsuario && (
            <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded-xl shadow-xl py-2 z-50"
              onClick={e => e.stopPropagation()}>
              <div className="px-4 py-2 border-b border-[#f3f2f1] dark:border-[#3b3a39]">
                <div className="text-sm font-semibold text-[#323130] dark:text-[#e0e0e0] truncate">{user?.username}</div>
                <div className="text-xs text-[#a19f9d]">Sesión del correo institucional</div>
              </div>
              <button onClick={() => navigate('/settings')}
                className="block w-full text-left px-4 py-2 text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                ⚙️ Configuración
              </button>
              <button onClick={cerrarSesion}
                className="block w-full text-left px-4 py-2 text-sm text-[#d13438] hover:bg-[#fde7e9]">
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </header>

      {/* El explorador ocupa todo el resto */}
      <div className="flex-1 min-h-0">
        <FilesView />
      </div>
    </div>
  );
}
