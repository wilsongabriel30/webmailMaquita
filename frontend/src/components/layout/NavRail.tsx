import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

const navItems = [
  { path: '/', icon: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z', label: 'Correo' },
  { path: '/calendar', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z', label: 'Calendario' },
  { path: '/contacts', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z', label: 'Contactos' },
];

export function NavRail() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  return (
    <div className="w-[48px] bg-[#f3f2f1] border-r border-[#edebe9] flex flex-col items-center py-2 shrink-0">
      {navItems.map((item) => {
        const active = item.path === '/'
          ? location.pathname === '/' || location.pathname.startsWith('/mail')
          : location.pathname.startsWith(item.path);
        return (
          <button key={item.path} onClick={() => navigate(item.path)} title={item.label}
            className={`w-10 h-10 rounded-md flex items-center justify-center transition-colors mb-0.5 ${
              active ? 'bg-[#e1dfdd] text-[#0078d4]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'
            }`}>
            <svg className="w-[20px] h-[20px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
            </svg>
          </button>
        );
      })}
      {user?.is_admin && (
        <button onClick={() => navigate('/admin')} title="Admin"
          className={`w-10 h-10 rounded-md flex items-center justify-center transition-colors mt-auto ${
            location.pathname.startsWith('/admin') ? 'bg-[#e1dfdd] text-[#ca5010]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'
          }`}>
          <svg className="w-[20px] h-[20px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </button>
      )}
    </div>
  );
}
