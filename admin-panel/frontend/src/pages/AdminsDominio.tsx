import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../api/auth";
import { SectionHelp } from "../components/SectionHelp";
import { AdminDominioForm, AdminDominio } from "./admins-dominio/AdminDominioForm";
import { AuditoriaDominio } from "./admins-dominio/AuditoriaDominio";
import { SolicitudesDominio } from "./admins-dominio/SolicitudesDominio";

export function AdminsDominio() {
  const { user } = useAuth();
  const [lista, setLista] = useState<AdminDominio[]>([]);
  const [dominios, setDominios] = useState<string[]>([]);
  const [editando, setEditando] = useState<AdminDominio | "nuevo" | null>(null);
  const [error, setError] = useState("");
  const [portal, setPortal] = useState("");
  const [portales, setPortales] = useState<Record<string, string>>({});
  const [copiado, setCopiado] = useState(false);

  const cargar = () => api.get<AdminDominio[]>("/admins-dominio").then(setLista).catch((e) => setError(e.message));
  useEffect(() => {
    cargar();
    api.get<{ url: string | null; por_dominio?: Record<string, string> }>("/segundo-factor/portal-dominio")
      .then((r) => { setPortal(r.url || ""); setPortales(r.por_dominio || {}); }).catch(() => {});
    api.get<{ domain: string }[]>("/domains").then((d) => setDominios(d.map((x) => x.domain))).catch(() => {});
  }, []);

  const eliminar = async (a: AdminDominio) => {
    if (!confirm(`Eliminar al administrador de dominio "${a.username}"? Pierde el acceso al portal al instante. Las cuentas de correo de su dominio no se tocan.`)) return;
    await api.del(`/admins-dominio/${a.id}`);
    cargar();
  };

  if (user?.role !== "superadmin") return <div className="p-8 text-ms-red">Acceso restringido a superadmins</div>;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-ms-gray-130">Administradores de dominio</h1>
        <SectionHelp titulo="Administradores de dominio" items={[
          { titulo: "Qué es", desc: "Personas que administran SOLO las cuentas y alias de los dominios que se les asignan. Entran por un portal aparte (otro puerto), no por este panel; su dirección se muestra arriba de la lista, con un botón para copiarla." },
          { titulo: "Qué pueden hacer", desc: "Crear cuentas, editar nombre y cuota, cambiar contraseñas, activar o desactivar cuentas y gestionar alias dentro de sus dominios." },
          { titulo: "Qué no pueden hacer", desc: "Ver otros dominios, eliminar cuentas, leer correo, reenviar fuera de su dominio ni tocar la configuración del servidor." },
          { titulo: "Segundo factor", desc: "Es obligatorio: tras cambiar su contraseña, el portal le pide configurar un código en el teléfono. Si pierde el teléfono, edítalo aquí y marca «Restablecer segundo factor»." },
          { titulo: "Eliminar cuentas", desc: "El administrador de dominio solo puede pedirlo; la cuenta queda desactivada y aparece abajo, en Solicitudes, para que la confirmes o la rechaces." },
          { titulo: "Contraseña inicial", desc: "La que se pone aquí es temporal: el portal obliga a cambiarla en la primera entrada." },
        ]} />
        <button onClick={() => setEditando("nuevo")} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo administrador de dominio</button>
      </div>

      {portal && (
        <div className="bg-ms-blue-lighter rounded border border-ms-blue/20 px-4 py-2.5 text-sm text-ms-gray-130 flex items-center gap-3 flex-wrap">
          <span>{Object.keys(portales).length ? "Portal general (los dominios con portal propio muestran el suyo en la lista):" : "Los administradores de dominio entran por:"}</span>
          <a href={portal} target="_blank" rel="noreferrer" className="font-medium text-ms-blue hover:underline">{portal}</a>
          <button onClick={() => { navigator.clipboard?.writeText(portal); setCopiado(true); setTimeout(() => setCopiado(false), 2000); }}
            title="Copia la dirección del portal para enviársela al administrador de dominio"
            className="px-2 py-0.5 border border-ms-blue/40 rounded text-xs text-ms-blue hover:bg-white">{copiado ? "Copiada" : "Copiar"}</button>
        </div>
      )}

      {error && <div className="text-ms-red text-sm">{error}</div>}

      <div className="bg-white rounded border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Usuario</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominios</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Estado</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Última entrada</th>
            <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {lista.map((a) => (
              <tr key={a.id} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5"><div className="font-medium text-ms-gray-130">{a.username}</div><div className="text-xs text-ms-gray-60">{a.display_name}</div></td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-90">
                  {a.dominios.length ? a.dominios.join(", ") : <span className="text-ms-red">Sin dominios</span>}
                  {/* Portal por el que entra: el de su empresa si lo tiene; si no, el general de arriba. */}
                  {Array.from(new Set<string>(a.dominios.map((d) => portales[d.toLowerCase()]).filter((u): u is string => !!u))).map((u) => (
                    <div key={u} className="mt-0.5 flex items-center gap-2">
                      <a href={u} target="_blank" rel="noreferrer" className="text-ms-blue hover:underline">{u}</a>
                      <button onClick={() => navigator.clipboard?.writeText(u)} title="Copia la dirección del portal de esta empresa" className="text-[10px] text-ms-blue border border-ms-blue/40 rounded px-1 hover:bg-ms-blue-lighter">Copiar</button>
                    </div>
                  ))}
                </td>
                <td className="px-4 py-2.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${a.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{a.active ? "Activo" : "Inactivo"}</span>
                  {a.must_change_password && <div className="text-[10px] text-ms-gray-60 mt-0.5">clave temporal</div>}
                  <div className={`text-[10px] mt-0.5 ${a.totp_enabled ? "text-ms-green" : "text-ms-gray-60"}`}>{a.totp_enabled ? "segundo factor activo" : "segundo factor pendiente"}</div>
                </td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-60">{a.last_login ? new Date(a.last_login).toLocaleString() : "Nunca"}</td>
                <td className="px-4 py-2.5 text-right space-x-3 whitespace-nowrap">
                  <button onClick={() => setEditando(a)} className="text-ms-blue text-xs hover:underline">Editar</button>
                  <button onClick={() => eliminar(a)} className="text-ms-red text-xs hover:underline">Eliminar</button>
                </td>
              </tr>
            ))}
            {!lista.length && <tr><td colSpan={5} className="px-4 py-6 text-center text-ms-gray-60 text-sm">Todavía no hay administradores de dominio.</td></tr>}
          </tbody>
        </table>
      </div>

      {editando && (
        <AdminDominioForm actual={editando === "nuevo" ? null : editando} dominios={dominios}
          onCerrar={() => setEditando(null)} onGuardado={() => { setEditando(null); cargar(); }} />
      )}

      <SolicitudesDominio />

      <AuditoriaDominio />
    </div>
  );
}
