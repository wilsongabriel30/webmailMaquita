import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Forward { address: string; goto: string; domain: string; active: boolean; has_mailbox: boolean }

export function Forwarding() {
  const [forwards, setForwards] = useState<Forward[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ address: "", goto: "", keep_copy: true });

  const load = () => api.get<Forward[]>("/forwarding").then(setForwards);
  useEffect(() => { load(); }, []);

  const create = async () => { await api.post("/forwarding", form); setShowForm(false); setForm({ address: "", goto: "", keep_copy: true }); load(); };
  const del = async (a: string) => { if (confirm(`Se eliminara el reenvio de ${a}. Los correos dejaran de copiarse al destino. Continuar?`)) { await api.del(`/forwarding/${a}`); load(); } };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Reenvíos ({forwards.length})</h1>
        <div className="flex items-center gap-2">
          <SectionHelp
            titulo="Reenvíos de correo"
            items={[
              { titulo: "Para qué sirve", desc: "Configura que los correos que llegan a una dirección (origen) se envíen automáticamente a otra (destino). Útil cuando alguien está de vacaciones, cambió de correo o quiere recibir copias en otra cuenta." },
              { titulo: "Mantener copia", desc: "Si el reenvío se crea con la casilla marcada, el correo original queda también en el buzón de origen. Si no, solo llega al destino y el buzón de origen no lo conserva." },
              { titulo: "Columna Buzón", desc: "Indica si la dirección de origen tiene un buzón real en el servidor (Sí) o es solo una dirección que redirige (No)." },
              { titulo: "Columna Estado", desc: "Activo = el reenvío está funcionando. Inactivo = está definido pero no reenvía correos." },
              { titulo: "Eliminar", desc: "Quita el reenvío: los correos dejan de copiarse al destino y siguen llegando solo al buzón de origen. Se registra en auditoría." },
            ]}
          />
          <button onClick={() => setShowForm(!showForm)} title="Reenvia una copia de todos los correos entrantes a otra dirección. El original se mantiene en el buzón. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo reenvio</button>
        </div>
      </div>

      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Origen (user@domain)" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} title="Dirección de correo de origen cuyos correos se reenviaran." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            <input placeholder="Destino (forward@domain)" value={form.goto} onChange={(e) => setForm({ ...form, goto: e.target.value })} title="Dirección de destino donde se reenviaran copias de los correos." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          </div>
          <label className="flex items-center gap-2 text-sm text-ms-gray-130" title="Si esta activo, el correo original permanece en el buzón de origen ademas de reenviarse. Si se desactiva, solo se reenvia.">
            <input type="checkbox" checked={form.keep_copy} onChange={(e) => setForm({ ...form, keep_copy: e.target.checked })} title="Mantener una copia del correo en el buzón original ademas de reenviarlo al destino." className="accent-ms-blue" />
            Mantener copia en buzón original
          </label>
          <div className="flex gap-2">
            <button onClick={create} title="Reenvia una copia de todos los correos entrantes a otra dirección. El original se mantiene en el buzón. Se registra en auditoria." className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Crear reenvio</button>
            <button onClick={() => setShowForm(false)} title="Cancela la creación del reenvio y cierra el formulario. No se realizan cambios." className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Origen</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Destino</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominio</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Indica si el origen tiene un buzón de correo asociado.">Buzón</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Estado actual del reenvio. Activo = reenvia correos. Inactivo = no reenvia.">Estado</th>
            <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {forwards.map((f) => (
              <tr key={f.address} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5 font-medium text-ms-gray-130">{f.address}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{f.goto}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{f.domain}</td>
                <td className="px-4 py-2.5 text-center">{f.has_mailbox ? <span className="text-ms-green text-xs">Si</span> : <span className="text-ms-gray-60 text-xs">No</span>}</td>
                <td className="px-4 py-2.5 text-center"><span className={`px-2 py-0.5 rounded text-[10px] font-medium ${f.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{f.active ? "Activo" : "Inactivo"}</span></td>
                <td className="px-4 py-2.5 text-right"><button onClick={() => del(f.address)} title="Elimina el reenvio. Los correos dejaran de copiarse al destino. Se registra en auditoria." className="text-ms-red text-xs hover:underline">Eliminar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {forwards.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Sin reenvios configurados</div>}
      </div>
    </div>
  );
}
