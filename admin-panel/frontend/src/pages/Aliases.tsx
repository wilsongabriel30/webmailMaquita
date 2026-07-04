import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Alias { address: string; goto: string; domain: string; active: boolean }

export function Aliases() {
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ address: "", goto: "" });

  const load = () => api.get<Alias[]>("/aliases").then(setAliases);
  useEffect(() => { load(); }, []);

  const create = async () => { await api.post("/aliases", form); setShowForm(false); setForm({ address: "", goto: "" }); load(); };
  const del = async (a: string) => { if (confirm(`Se eliminara el alias ${a}. Los correos enviados a esta dirección dejaran de redirigirse. Continuar?`)) { await api.del(`/aliases/${a}`); load(); } };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Alias ({aliases.length})</h1>
        <div className="flex items-center gap-2">
          <SectionHelp
            titulo="Alias de correo"
            items={[
              { titulo: "Para qué sirve", desc: "Un alias es una dirección de correo alternativa que no tiene buzón propio: todo lo que llega al alias se entrega en el buzón de destino. Ejemplo: info@dominio.com puede ser alias de juan.perez@dominio.com." },
              { titulo: "Diferencia con Reenvíos", desc: "El alias es una dirección virtual sin buzón. El reenvío copia correos de un buzón real hacia otra dirección. Use alias para direcciones genéricas (info, ventas, contacto)." },
              { titulo: "Columnas de la tabla", desc: "Alias = la dirección virtual. Destino = el buzón real que recibe. Dominio = a qué dominio pertenece el alias. Estado = si la redirección está funcionando (Activo) o pausada (Inactivo)." },
              { titulo: "Crear alias", desc: "Con el botón + Nuevo alias se indica la dirección virtual y el buzón de destino. Funciona de inmediato y se registra en auditoría." },
              { titulo: "Eliminar", desc: "Los correos enviados al alias empezarán a rebotar al remitente porque la dirección deja de existir. El buzón de destino no se toca." },
            ]}
          />
          <button onClick={() => setShowForm(!showForm)} title="Crea una redirección de correo. Los correos enviados al alias se entregan al destino. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo alias</button>
        </div>
      </div>
      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 grid grid-cols-2 gap-3">
          <input placeholder="alias@domain" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} title="Dirección de correo del alias (ej: info@dominio.com). Los correos a esta dirección se redirigen al destino." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <input placeholder="destino@domain" value={form.goto} onChange={(e) => setForm({ ...form, goto: e.target.value })} title="Dirección de destino donde se entregaran los correos del alias." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <div className="col-span-2 flex gap-2">
            <button onClick={create} title="Crea una redirección de correo. Los correos enviados al alias se entregan al destino. Se registra en auditoria." className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Crear</button>
            <button onClick={() => setShowForm(false)} title="Cancela la creación del alias y cierra el formulario. No se realizan cambios." className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          </div>
        </div>
      )}
      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Alias</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Destino</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominio</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Estado actual del alias. Activo = redirige correos. Inactivo = no redirige.">Estado</th>
            <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {aliases.map((a) => (
              <tr key={a.address} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5 font-medium text-ms-gray-130">{a.address}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{a.goto}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{a.domain}</td>
                <td className="px-4 py-2.5 text-center"><span className={`px-2 py-0.5 rounded text-[10px] font-medium ${a.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{a.active ? "Activo" : "Inactivo"}</span></td>
                <td className="px-4 py-2.5 text-right"><button onClick={() => del(a.address)} title="Elimina el alias. Los correos enviados a esta dirección dejaran de redirigirse. Se registra en auditoria." className="text-ms-red text-xs hover:underline">Eliminar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {aliases.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Sin alias configurados</div>}
      </div>
    </div>
  );
}
