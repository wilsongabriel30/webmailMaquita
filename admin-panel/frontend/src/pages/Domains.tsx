import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { SoporteDominio } from "../components/SoporteDominio";
import { useAuth } from "../api/auth";

import { EnrutamientoCorreo } from "./dominios/EnrutamientoCorreo";

interface Domain { domain: string; description: string; mailbox_count: number; alias_count: number; active: boolean; created: string }

export function Domains() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [soporte, setSoporte] = useState<string | null>(null);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [enrutar, setEnrutar] = useState("");
  const [form, setForm] = useState({ domain: "", description: "", mailboxes: 0, maxquota: 0 });

  const load = () => api.get<Domain[]>("/domains").then(setDomains);
  useEffect(() => { load(); }, []);

  const create = async () => {
    await api.post("/domains", form);
    setShowForm(false); setForm({ domain: "", description: "", mailboxes: 0, maxquota: 0 }); load();
  };
  const del = async (d: string) => { if (confirm(`PRECAUCION EXTREMA: Se eliminara el dominio ${d} y potencialmente todos los buzones asociados. Verificar que no haya usuarios activos antes de eliminar. Continuar?`)) { await api.del(`/domains/${d}`); load(); } };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Dominios aceptados</h1>
        <div className="flex items-center gap-2">
          <SectionHelp titulo="Dominios aceptados" items={[
            { titulo: "Para qué sirve", desc: "Lista los dominios para los que este servidor acepta y entrega correo. Solo se pueden crear buzones y alias en dominios registrados aquí." },
            { titulo: "Agregar dominio", desc: "Registra un dominio nuevo. Antes de agregarlo, configure sus registros DNS (MX apuntando a este servidor, SPF, DKIM y DMARC); puede validarlos en la sección Verificación DNS." },
            { titulo: "Columnas Buzones y Alias", desc: "Muestran cuántas cuentas de correo y cuántos alias existen en cada dominio, para dimensionar su uso antes de cualquier cambio." },
            { titulo: "Estado", desc: "Activo significa que el dominio acepta correo entrante; Inactivo hace que el servidor lo rechace." },
            { titulo: "Marca y portal", desc: "Abre la configuración de ese dominio en Portales por empresa: logo, icono, color, textos y el nombre de servidor propio (mail.<empresa>) por el que entra la empresa." },
            { titulo: "Entrar como soporte", desc: "Solo superadmin, con sesión abierta con segundo factor. Abre el portal de dominio (8444) como lo ve su administrador, sin su contraseña ni su código: solo lectura por defecto, o con acciones (cada una queda auditada como del soporte). Un solo uso; la sesión dura una hora como máximo." },
            { titulo: "Enrutamiento", desc: "Para dominios cuyo correo vive en otro servidor: MX de respaldo (acepta y guarda en cola mientras el principal no responde) o reenvío fijo a otro servidor, con lista opcional de destinatarios válidos y TLS obligatorio. Se registra en auditoría." },
            { titulo: "Eliminar", desc: "PRECAUCIÓN EXTREMA: borra el dominio y potencialmente todos sus buzones. Verifique que no queden usuarios activos antes de hacerlo. Se registra en auditoría." },
          ]} />
          <button onClick={() => navigate("/portales")} title="Abre Portales por empresa: logo, icono, color, textos y nombre de servidor propio de cada dominio." className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm hover:bg-ms-blue-lighter">Marca y portales</button>
          <button onClick={() => setShowForm(!showForm)} title="Agrega un nuevo dominio al servidor de correo. Asegurese de que los registros DNS (MX, SPF, DKIM) esten configurados. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Agregar dominio</button>
        </div>
      </div>

      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 grid grid-cols-2 gap-3">
          <input placeholder="dominio.com" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} title="Nombre del dominio a agregar (ej: empresa.com). Debe tener DNS configurado correctamente." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <input placeholder="Descripcion" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} title="Descripcion opcional del dominio para referencia interna." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <div className="col-span-2 flex gap-2">
            <button onClick={create} title="Agrega un nuevo dominio al servidor de correo. Asegurese de que los registros DNS (MX, SPF, DKIM) esten configurados. Se registra en auditoria." className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Crear</button>
            <button onClick={() => setShowForm(false)} title="Cancela la creación del dominio y cierra el formulario. No se realizan cambios." className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          </div>
        </div>
      )}

      {enrutar && <EnrutamientoCorreo dominio={enrutar} onCerrar={() => setEnrutar("")} />}

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominio</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Descripcion</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Número de buzones de correo creados en este dominio.">Buzones</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Número de alias de correo configurados en este dominio.">Alias</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Estado actual del dominio. Activo = acepta correos. Inactivo = rechaza correos.">Estado</th>
              <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ms-gray-30">
            {domains.map((d) => (
              <tr key={d.domain} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5 font-medium text-ms-gray-130">{d.domain}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{d.description || "-"}</td>
                <td className="px-4 py-2.5 text-center">{d.mailbox_count}</td>
                <td className="px-4 py-2.5 text-center">{d.alias_count}</td>
                <td className="px-4 py-2.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${d.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{d.active ? "Activo" : "Inactivo"}</span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button onClick={() => navigate(`/portales?dominio=${encodeURIComponent(d.domain)}`)} title="Logo, icono, color, textos y nombre de servidor propio de este dominio (Portales por empresa)." className="text-ms-blue hover:underline text-xs mr-4">Marca y portal</button>
                  {user?.role === "superadmin" && (
                    <button onClick={() => setSoporte(d.domain)} title="Abre el portal de este dominio como su administrador, para darle soporte (solo lectura por defecto). Queda en la auditoría." className="text-ms-blue hover:underline text-xs mr-4">Entrar como soporte</button>
                  )}

                  <button onClick={() => setEnrutar(d.domain)} title="MX de respaldo o reenvío del correo de este dominio a otro servidor." className="text-ms-blue hover:underline text-xs mr-4">Enrutamiento</button>
                  <button onClick={() => del(d.domain)} title="PRECAUCION EXTREMA: Elimina el dominio y potencialmente todos los buzones asociados. Verificar que no haya usuarios activos antes de eliminar. Se registra en auditoria." className="text-ms-red hover:underline text-xs">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {domains.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Sin dominios configurados</div>}
      </div>
      {soporte && <SoporteDominio dominio={soporte} onCerrar={() => setSoporte(null)} />}
    </div>
  );
}
