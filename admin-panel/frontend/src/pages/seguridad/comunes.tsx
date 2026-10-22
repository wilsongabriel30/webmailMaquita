import { useEffect, useState, type ReactNode } from "react";
import { api } from "../../api/client";
import type { Rango } from "./api";

/* Piezas comunes de los tableros de seguridad. */

export const caja = "bg-white rounded border border-ms-gray-30 p-4";
export const COLOR = {
  ok: "#107c10", fallo: "#d13438", azul: "#0078d4", naranja: "#d83b01", morado: "#5c2d91", amarillo: "#ffb900", gris: "#a19f9d",
};
export const SERVICIOS: Record<string, string> = {
  webmail: "Webmail", imap: "IMAP", pop3: "POP3", smtp: "SMTP (envío)", activesync: "ActiveSync", panel: "Panel",
};
export const COLOR_SERVICIO: Record<string, string> = {
  webmail: COLOR.azul, imap: COLOR.morado, pop3: COLOR.gris, smtp: COLOR.naranja, activesync: COLOR.ok, panel: COLOR.amarillo,
};

const regiones = (() => { try { return new Intl.DisplayNames(["es"], { type: "region" }); } catch { return null; } })();

export function nombrePais(codigo: string): string {
  if (codigo === "LAN") return "Red interna";
  if (!codigo || codigo === "--") return "Desconocido";
  try { return regiones?.of(codigo) || codigo; } catch { return codigo; }
}

export function fecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}

/* Etiqueta del eje: «21/10 14h» por hora o «21/10» por día (la fecha ya viene en la zona de los tableros). */
export function etiqueta(t: string, paso: string): string {
  const [dia, hora] = t.split("T");
  const [, m, d] = dia.split("-");
  return paso === "hour" ? `${d}/${m} ${hora?.slice(0, 2)}h` : `${d}/${m}`;
}

function hoyMenos(dias: number): string {
  const d = new Date(); d.setDate(d.getDate() - dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function rangoInicial(): Rango { return { desde: hoyMenos(6), hasta: hoyMenos(0) }; }

export function SelectorRango({ rango, cambiar }: { rango: Rango; cambiar: (r: Rango) => void }) {
  const atajo = (dias: number) => cambiar({ desde: hoyMenos(dias - 1), hasta: hoyMenos(0) });
  const cls = "px-2 py-1 border border-ms-gray-30 rounded text-xs";
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="text-ms-gray-90">Periodo:</span>
      <input type="date" value={rango.desde} max={rango.hasta} onChange={(e) => cambiar({ ...rango, desde: e.target.value })} className={cls} />
      <span>a</span>
      <input type="date" value={rango.hasta} min={rango.desde} onChange={(e) => cambiar({ ...rango, hasta: e.target.value })} className={cls} />
      {[1, 7, 30, 90, 365].map((d) => (
        <button key={d} onClick={() => atajo(d)} className={`${cls} hover:bg-ms-gray-20`}>{d === 1 ? "Hoy" : `${d} días`}</button>
      ))}
    </div>
  );
}

export function Kpi({ titulo, valor, ayuda, tono }: { titulo: string; valor: number | string | null | undefined; ayuda?: string; tono?: string }) {
  return (
    <div title={ayuda} className="bg-white rounded border border-ms-gray-30 p-3 min-w-[120px]">
      <p className="text-[11px] font-medium text-ms-gray-90 uppercase">{titulo}</p>
      <p className={`text-xl font-bold mt-0.5 ${tono || "text-ms-gray-130"}`}>
        {valor === null || valor === undefined ? "—" : typeof valor === "number" ? valor.toLocaleString("es") : valor}
      </p>
    </div>
  );
}

export function Seccion({ titulo, children, acciones }: { titulo: string; children: ReactNode; acciones?: ReactNode }) {
  return (
    <div className={caja}>
      <div className="flex items-center justify-between mb-3 gap-2">
        <h2 className="text-sm font-semibold text-ms-gray-130">{titulo}</h2>
        {acciones}
      </div>
      {children}
    </div>
  );
}

/* Carga una ruta del API y la vuelve a cargar cuando cambia. */
export function useDatos<T>(ruta: string | null): { datos: T | null; error: string; cargando: boolean; recargar: () => void } {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [vuelta, setVuelta] = useState(0);
  useEffect(() => {
    if (!ruta) return;
    let vivo = true;
    setCargando(true); setError("");
    api.get<T>(ruta).then((d) => { if (vivo) setDatos(d); })
      .catch((e: Error) => { if (vivo) setError(e.message); })
      .finally(() => { if (vivo) setCargando(false); });
    return () => { vivo = false; };
  }, [ruta, vuelta]);
  return { datos, error, cargando, recargar: () => setVuelta((v) => v + 1) };
}

export function Estado({ cargando, error, vacio }: { cargando: boolean; error: string; vacio?: boolean }) {
  if (error) return <p className="text-sm text-ms-red">{error}</p>;
  if (cargando) return <p className="text-sm text-ms-gray-60">Cargando…</p>;
  if (vacio) return <p className="text-sm text-ms-gray-60">Sin datos en el periodo. Si el recolector se acaba de instalar, los datos aparecen a los pocos minutos.</p>;
  return null;
}
