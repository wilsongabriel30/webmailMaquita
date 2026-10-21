import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Elemento { id: string; ruta: string; fecha: string }

/* Papelera del administrador de archivos: lo borrado se guarda 30 días y se puede recuperar en su sitio. */
export function ArchivosPapelera({ dominio, onVolver }: { dominio: string; onVolver: () => void }) {
  const [elementos, setElementos] = useState<Elemento[] | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = () => api.get<{ elementos: Elemento[] }>(`/sitios/${dominio}/archivos-papelera`).then((d) => setElementos(d.elementos)).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [dominio]);
  const hacer = async (fn: () => Promise<unknown>) => {
    setOcupado(true); setError("");
    try { await fn(); await cargar(); } catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <button onClick={onVolver} className="text-sm text-ms-blue hover:underline">← Volver a los archivos</button>
        <button onClick={() => confirm("¿Vaciar la papelera? Lo que contiene se borra para siempre.") && hacer(() => api.del(`/sitios/${dominio}/archivos-papelera`))}
          disabled={ocupado || !elementos?.length} className="ml-auto px-3 py-1.5 border border-ms-gray-40 rounded text-sm text-ms-red disabled:opacity-50">Vaciar papelera</button>
      </div>
      {error && <p className="text-sm text-ms-red">{error}</p>}
      <table className="w-full text-sm">
        <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr><th className="text-left px-2 py-1.5">Estaba en</th><th className="text-left px-2 py-1.5">Borrado</th><th /></tr></thead>
        <tbody className="divide-y divide-ms-gray-30">
          {elementos?.map((e) => (
            <tr key={e.id}>
              <td className="px-2 py-1 break-all">{e.ruta}</td>
              <td className="px-2 py-1 text-xs whitespace-nowrap">{e.fecha}</td>
              <td className="px-2 py-1 text-right"><button onClick={() => hacer(() => api.post(`/sitios/${dominio}/archivos-papelera/${e.id}/recuperar`))} disabled={ocupado} className="text-ms-blue hover:underline text-xs">Recuperar</button></td>
            </tr>
          ))}
          {elementos && elementos.length === 0 && <tr><td colSpan={3} className="px-2 py-4 text-center text-ms-gray-60">La papelera está vacía.</td></tr>}
        </tbody>
      </table>
      <p className="text-[11px] text-ms-gray-60">Lo que lleva más de 30 días en la papelera se borra solo cada noche.</p>
    </div>
  );
}
