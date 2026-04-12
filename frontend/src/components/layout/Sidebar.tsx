import { useLocation } from "react-router-dom";
import { MailSidebar } from "./MailSidebar";

export function Sidebar() {
  const loc = useLocation();
  const path = loc.pathname.replace(/^\/webmail/, "");
  if (path.startsWith("/admin")) return null;
  if (path.startsWith("/calendar")) return null;
  if (path.startsWith("/contacts")) return null;  // ContactsSidebar is inside ContactsView
  if (path.startsWith("/settings")) return <Placeholder title="Ajustes" />;
  return <MailSidebar />;
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="w-[228px] bg-[#faf9f8] border-r border-[#edebe9] flex flex-col shrink-0 p-4">
      <h2 className="text-[14px] font-semibold text-[#323130]">{title}</h2>
    </div>
  );
}
