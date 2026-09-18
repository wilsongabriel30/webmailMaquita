import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { Codigos } from "./dispositivos/Codigos";
import { Equipos } from "./dispositivos/Equipos";
import { FichaEquipo } from "./dispositivos/FichaEquipo";
import { Mensajes } from "./dispositivos/Mensajes";
import { Equipo } from "./dispositivos/tipos";

// Teléfonos institucionales (fase 1): inventario y asignación, último estado que reporta cada
// equipo, mensajes urgentes con acuse y códigos de enrolamiento. Los teléfonos hablan con el
// webmail (/api/dispositivos); aquí se administra.

interface Resumen { activos: number; sin_contacto: number; perdidos: number; limitados: number; eventos_sin_revisar: number }
type Pestana = "equipos" | "mensajes" | "codigos";

export function Dispositivos() {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [res, setRes] = useState<Resumen | null>(null);
  const [pestana, setPestana] = useState<Pestana>("equipos");
  const [abierto, setAbierto] = useState<number | null>(null);
  const [error, setError] = useState("");

  const cargar = () => Promise.all([
    api.get<{ equipos: Equipo[] }>("/dispositivos/equipos").then((r) => setEquipos(r.equipos)),
    api.get<Resumen>("/dispositivos/resumen").then(setRes),
  ]).catch((e) => setError(e.message));
  useEffect(() => { cargar(); const t = setInterval(cargar, 60000); return () => clearInterval(t); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div><h1 className="text-xl font-semibold text-ms-gray-130">Teléfonos institucionales</h1>
          <p className="text-sm text-ms-gray-60">Inventario, estado y mensajes urgentes de los celulares de la organización.</p></div>
        <SectionHelp titulo="Teléfonos institucionales" items={[
          { titulo: "Cómo entra un teléfono", desc: "Se instala la app Maquita y se escribe un código de enrolamiento creado aquí. Sin código vigente no se activa la gestión. Equipo nuevo o restaurado de fábrica: control completo. Teléfono ya en uso: modo limitado (la persona puede quitar permisos o desinstalar; si lo hace, queda un evento)." },
          { titulo: "Qué reporta", desc: "Cada 15 minutos: batería, almacenamiento, red, versión de Android y de la app, Play Protect. No se leen mensajes, fotos ni contenido." },
          { titulo: "Inventario", desc: "Nombre, custodio, centro de costo, sede, IMEI, serie, factura, fecha y valor de compra. La depreciación se calcula en línea recta con la vida útil indicada (36 meses por defecto)." },
          { titulo: "Mensajes urgentes", desc: "Llegan al teléfono en su siguiente reporte, a pantalla completa, y exigen tocar «Leído». Aquí se ve quién lo leyó y cuándo." },
          { titulo: "Auditoría", desc: "Códigos, ediciones, bajas y mensajes quedan en la auditoría del panel." },
        ]} />
      </div>
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      {res && <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {([["Activos", res.activos, false], ["Sin reportar en 24 h", res.sin_contacto, res.sin_contacto > 0], ["Perdidos o robados", res.perdidos, res.perdidos > 0],
          ["En modo limitado", res.limitados, false], ["Eventos por revisar", res.eventos_sin_revisar, res.eventos_sin_revisar > 0]] as [string, number, boolean][]).map(([t, n, alerta]) => (
          <div key={t} className={`rounded-lg border p-3 ${alerta ? "bg-red-50 border-red-200" : "bg-white border-ms-gray-30"}`}>
            <div className="text-2xl font-semibold">{n}</div><div className="text-xs text-ms-gray-60">{t}</div></div>))}
      </div>}
      <div className="flex gap-1 border-b border-ms-gray-30">
        {([["equipos", "Equipos"], ["mensajes", "Mensajes urgentes"], ["codigos", "Códigos de enrolamiento"]] as [Pestana, string][]).map(([k, t]) => (
          <button key={k} onClick={() => { setPestana(k); setAbierto(null); }}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${pestana === k ? "border-ms-blue text-ms-blue font-medium" : "border-transparent text-ms-gray-90 hover:text-ms-gray-130"}`}>{t}</button>))}
      </div>
      {pestana === "equipos" && (abierto ? <FichaEquipo id={abierto} onCerrar={() => setAbierto(null)} onCambio={cargar} /> : <Equipos equipos={equipos} onAbrir={setAbierto} />)}
      {pestana === "mensajes" && <Mensajes equipos={equipos} />}
      {pestana === "codigos" && <Codigos />}
    </div>
  );
}
