import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { abrirEnlace, tamano } from "./datosComun";

interface Copia { id: string; fecha: string; motivo: string; bases: { motor: string; nombre: string }[]; bytes: number }
interface Datos { copias: Copia[]; tope: number }

/* Copias del sitio que controla su dueño (archivos y bases): crear, descargar, restaurar y borrar. */
export function CopiasPestana({ dominio }: { dominio: string }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState("");

  const cargar = () => api.get<Datos>(`/sitios/${dominio}/copias`).then(setDatos).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [dominio]);

  const hacer = async (que: string, texto: string, fn: () => Promise<unknown>) => {
    setOcupado(que); setError(""); setMensaje("");
    try { await fn(); setMensaje(texto); await cargar(); }
    catch (e) { setError((e as Error).message); } finally { setOcupado(""); }
  };
  const descargar = (c: Copia) => hacer(c.id, "", async () => {
    abrirEnlace((await api.post<{ enlace: string }>(`/sitios/${dominio}/copias/${c.id}/descargar`)).enlace);
  });
  const restaurar = (c: Copia) => {
    if (!confirm(`¿Restaurar el sitio a la copia del ${c.fecha}? Los archivos y las bases vuelven a como estaban entonces; antes se hace una copia automática del estado actual.`)) return;
    hacer(c.id, "Sitio restaurado. La copia previa quedó en la lista por si hay que deshacerlo.", () => api.post(`/sitios/${dominio}/copias/${c.id}/restaurar`));
  };
  const borrar = (c: Copia) => confirm(`¿Borrar la copia del ${c.fecha}?`) && hacer(c.id, "Copia borrada.", () => api.del(`/sitios/${dominio}/copias/${c.id}`));
  const lleno = !!datos && datos.copias.length >= datos.tope;

  return (
    <div className="space-y-3">
      <p className="text-xs text-ms-gray-90">Una copia guarda la carpeta pública del sitio (y el código de su aplicación propia, si la tiene) y un volcado de cada base de datos, en un solo .tar.gz que se puede descargar. Es aparte de los respaldos automáticos del servidor. Como mucho {datos?.tope ?? 5} copias por sitio.</p>
      <button onClick={() => hacer("crear", "Copia creada.", () => api.post(`/sitios/${dominio}/copias`))} disabled={!!ocupado || lleno}
        className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">{ocupado === "crear" ? "Creando copia…" : "Crear copia ahora"}</button>
      {lleno && <span className="text-xs text-ms-gray-60 ml-2">Hay {datos?.tope} copias: borre una para crear otra o para poder restaurar (hace falta sitio para la copia previa).</span>}
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {mensaje && <p className="text-sm text-ms-green">{mensaje}</p>}
      <table className="w-full text-sm">
        <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr>
          <th className="text-left px-2 py-1.5">Fecha</th><th className="text-left px-2 py-1.5">Contenido</th>
          <th className="text-right px-2 py-1.5">Tamaño</th><th className="text-right px-2 py-1.5">Acciones</th></tr></thead>
        <tbody className="divide-y divide-ms-gray-30">
          {datos?.copias.map((c) => (
            <tr key={c.id}>
              <td className="px-2 py-1.5 whitespace-nowrap">{c.fecha}{c.motivo !== "manual" && <div className="text-[11px] text-ms-gray-60">{c.motivo}</div>}</td>
              <td className="px-2 py-1.5 text-xs">Archivos{c.bases.length ? ` y ${c.bases.length === 1 ? "1 base" : `${c.bases.length} bases`} (${c.bases.map((b) => b.nombre).join(", ")})` : ""}</td>
              <td className="px-2 py-1.5 text-right text-xs">{tamano(c.bytes)}</td>
              <td className="px-2 py-1.5 text-right whitespace-nowrap text-xs space-x-2">
                <button onClick={() => descargar(c)} disabled={!!ocupado} className="text-ms-blue hover:underline disabled:opacity-50">Descargar</button>
                <button onClick={() => restaurar(c)} disabled={!!ocupado || lleno} className="text-ms-blue hover:underline disabled:opacity-50">{ocupado === c.id ? "…" : "Restaurar"}</button>
                <button onClick={() => borrar(c)} disabled={!!ocupado} className="text-ms-red hover:underline disabled:opacity-50">Borrar</button>
              </td>
            </tr>
          ))}
          {datos && datos.copias.length === 0 && <tr><td colSpan={4} className="px-2 py-4 text-center text-ms-gray-60">Sin copias todavía.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
