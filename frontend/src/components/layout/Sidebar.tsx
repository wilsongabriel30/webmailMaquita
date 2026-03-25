import { useLocation } from 'react-router-dom';
import { MailSidebar } from './MailSidebar';

export function Sidebar() {
  const loc = useLocation();
  if (loc.pathname.startsWith('/admin')) return null;
  if (loc.pathname.startsWith('/calendar')) return <Placeholder title="Calendario" />;
  if (loc.pathname.startsWith('/contacts')) return <Placeholder title="Contactos" />;
  if (loc.pathname.startsWith('/settings')) return <Placeholder title="Ajustes" />;
  return <MailSidebar />;
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="w-[228px] bg-[#faf9f8] border-r border-[#edebe9] flex flex-col shrink-0 p-4">
      <h2 className="text-[14px] font-semibold text-[#323130]">{title}</h2>
      <p className="text-[12px] text-[#a19f9d] mt-1">Proximamente</p>
    </div>
  );
}
