import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

/* Outlook-style nav rail — filled icons, blue active indicator */

const navItems = [
  {
    path: '/',
    label: 'Correo',
    color: '#0078d4',
    icon: (active: boolean) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill={active ? '#0078d4' : 'none'} stroke={active ? '#0078d4' : '#605e5c'} strokeWidth={active ? 0 : 1.5}>
        {active ? (
          <>
            <path d="M2 6a2 2 0 012-2h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" fill="#0078d4"/>
            <path d="M22 6l-10 7L2 6" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </>
        ) : (
          <>
            <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round"/>
          </>
        )}
      </svg>
    ),
  },
  {
    path: '/calendar',
    label: 'Calendario',
    color: '#0078d4',
    icon: (active: boolean) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        {active ? (
          <>
            <rect x="3" y="4" width="18" height="18" rx="2" fill="#0078d4"/>
            <path d="M8 2v4M16 2v4" stroke="#0078d4" strokeWidth="2" strokeLinecap="round"/>
            <path d="M3 10h18" stroke="white" strokeWidth="1.5"/>
            <rect x="7" y="13" width="3" height="3" rx="0.5" fill="white"/>
          </>
        ) : (
          <>
            <rect x="3" y="4" width="18" height="18" rx="2" stroke="#605e5c" strokeWidth="1.5"/>
            <path d="M8 2v4M16 2v4" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M3 10h18" stroke="#605e5c" strokeWidth="1.5"/>
          </>
        )}
      </svg>
    ),
  },
  {
    path: '/contacts',
    label: 'Contactos',
    color: '#0078d4',
    icon: (active: boolean) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        {active ? (
          <>
            <circle cx="12" cy="8" r="4" fill="#0078d4"/>
            <path d="M4 20c0-3.314 3.582-6 8-6s8 2.686 8 6" fill="#0078d4" opacity="0.7"/>
            <path d="M4 20c0-3.314 3.582-6 8-6s8 2.686 8 6" stroke="#0078d4" strokeWidth="1.5" strokeLinecap="round"/>
          </>
        ) : (
          <>
            <circle cx="12" cy="8" r="3.5" stroke="#605e5c" strokeWidth="1.5"/>
            <path d="M5 20c0-3 3.582-5.5 7-5.5s7 2.5 7 5.5" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round"/>
          </>
        )}
      </svg>
    ),
  },
  {
    path: '/files',
    label: 'Archivos',
    color: '#0078d4',
    icon: (active: boolean) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        {active ? (
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" fill="#0078d4"/>
        ) : (
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        )}
      </svg>
    ),
  },
  {
    path: '/tasks',
    label: 'Tareas',
    color: '#0078d4',
    icon: (active: boolean) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        {active ? (
          <>
            <rect x="4" y="3" width="16" height="18" rx="2" fill="#0078d4"/>
            <path d="M9 12l2 2 4-4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <rect x="8" y="5" width="8" height="2" rx="1" fill="white" opacity="0.6"/>
          </>
        ) : (
          <>
            <rect x="4" y="3" width="16" height="18" rx="2" stroke="#605e5c" strokeWidth="1.5"/>
            <path d="M9 12l2 2 4-4" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M9 5h6" stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round"/>
          </>
        )}
      </svg>
    ),
  },
  {
    path: '/asistente',
    label: 'Asistente',
    color: '#0078d4',
    icon: (active: boolean) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={active ? '#0078d4' : '#605e5c'} strokeWidth="1.5">
        <path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8L12 3z" fill={active ? '#0078d4' : 'none'} strokeLinejoin="round"/>
        <path d="M5 16l.9 2.1L8 19l-2.1.9L5 22l-.9-2.1L2 19l2.1-.9L5 16z" fill={active ? '#0078d4' : 'none'} strokeLinejoin="round"/>
      </svg>
    ),
  },
];

export function NavRail() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  return (
    <div className="w-[48px] bg-[#f3f2f1] border-r border-[#edebe9] flex flex-col items-center py-1 shrink-0">
      {navItems.map((item) => {
        const active = item.path === '/'
          ? location.pathname === '/' || location.pathname.startsWith('/mail')
          : location.pathname.startsWith(item.path);
        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            title={item.label}
            onDragOver={(e) => {
              if ((item.path === '/calendar' || item.path === '/tasks') && e.dataTransfer.types.includes('application/x-mail-meta')) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
                setDropTarget(item.path);
              }
            }}
            onDragLeave={() => setDropTarget(null)}
            onDrop={(e) => {
              if (item.path !== '/calendar' && item.path !== '/tasks') return;
              const meta = e.dataTransfer.getData('application/x-mail-meta');
              if (!meta) return;
              e.preventDefault();
              setDropTarget(null);
              if (item.path === '/calendar') {
                try { sessionStorage.setItem('pending-event-from-mail', meta); } catch {}
                navigate('/calendar');
                return;
              }
              // Tareas: crear directamente con el asunto del correo
              try {
                const m = JSON.parse(meta);
                api.post('/tasks/tasks', {
                  title: m.subject || 'Tarea desde correo',
                  note: `Creada desde el correo de ${m.from || 'remitente desconocido'}`,
                }).then(() => {
                  showToast(`Tarea creada: ${(m.subject || '').slice(0, 60) || 'desde correo'}`);
                  window.dispatchEvent(new CustomEvent('refresh-tasks'));
                }).catch(() => showToast('No se pudo crear la tarea'));
              } catch {}
            }}
            className={`relative w-full flex items-center justify-center h-[44px] transition-colors group ${
              dropTarget === item.path ? 'bg-[#deecf9] ring-2 ring-inset ring-[#0078d4] rounded' : ''
            }`}
          >
            {/* Blue left indicator bar */}
            {active && (
              <div className="absolute left-0 top-[8px] bottom-[8px] w-[3px] rounded-r-full bg-[#0078d4]" />
            )}
            <div className={`w-[36px] h-[36px] rounded-md flex items-center justify-center transition-colors ${
              active ? 'bg-[#e1dfdd]' : 'hover:bg-[#e1dfdd]'
            }`}>
              {item.icon(active)}
            </div>
          </button>
        );
      })}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Admin button */}
      {user?.is_admin && (
        <button
          onClick={() => navigate('/admin')}
          title="Administración"
          className="relative w-full flex items-center justify-center h-[44px] transition-colors mb-1"
        >
          {location.pathname.startsWith('/admin') && (
            <div className="absolute left-0 top-[8px] bottom-[8px] w-[3px] rounded-r-full bg-[#ca5010]" />
          )}
          <div className={`w-[36px] h-[36px] rounded-md flex items-center justify-center transition-colors ${
            location.pathname.startsWith('/admin') ? 'bg-[#e1dfdd]' : 'hover:bg-[#e1dfdd]'
          }`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              {location.pathname.startsWith('/admin') ? (
                <>
                  <path d="M12 2l7.618 2.984A12.02 12.02 0 0120 9c0 5.591-3.824 10.29-9 11.622C5.824 19.29 2 14.591 2 9c0-1.042.133-2.052.382-3.016L12 2z" fill="#ca5010"/>
                  <path d="M9 12l2 2 4-4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </>
              ) : (
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  stroke="#605e5c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              )}
            </svg>
          </div>
        </button>
      )}
    </div>
  );
}
