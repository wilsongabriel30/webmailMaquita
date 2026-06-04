import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Domain { domain: string; description: string; mailbox_count: number; alias_count: number; active: boolean; created: string }

export function Domains() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ domain: "", description: "", mailboxes: 0, maxquota: 0 });

  const load = () => api.get<Domain[]>("/domains").then(setDomains);
  useEffect(() => { load(); }, []);

  const create = async () => {
    await api.post("/domains", form);
    setShowForm(false); setForm({ domain: "", description: "", mailboxes: 0, maxquota: 0 }); load();
  };
  const del = async (d: string) => { if (confirm(`PRECAUCION EXTREMA: Se eliminara el dominio ${d} y potencialmente todos los buzónes asociados. Verificar que no haya usuarios activos antes de eliminar. Continuar?`)) { await api.del(`/domains/${d}`); load(); } };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Dominios aceptados</h1>
        <button onClick={() => setShowForm(!showForm)} title="Agrega un nuevo dominio al servidor de correo. Asegurese de que los registros DNS (MX, SPF, DKIM) esten configurados. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Agregar dominio</button>
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

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominio</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Descripcion</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Numero de buzónes de correo creados en este dominio.">Buzónes</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Numero de alias de correo configurados en este dominio.">Alias</th>
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
                  <button onClick={() => del(d.domain)} title="PRECAUCION EXTREMA: Elimina el dominio y potencialmente todos los buzónes asociados. Verificar que no haya usuarios activos antes de eliminar. Se registra en auditoria." className="text-ms-red hover:underline text-xs">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {domains.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Sin dominios configurados</div>}
      </div>
    </div>
  );
}
