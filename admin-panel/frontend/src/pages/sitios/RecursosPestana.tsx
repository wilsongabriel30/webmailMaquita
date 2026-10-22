import { useEffect, useState } from "react";
import { api } from "../../api/client";

type Punto = [number, number | null, number | null];
interface Datos {
  instalado: boolean;
  intervalo: number;
  puntos: Punto[];
  resumen: { cpu_media: number | null; cpu_maxima: number | null; memoria_media_mb: number | null; memoria_maxima_mb: number | null };
  limites: { php_procesos: number; php_memoria_mb: number; app_memoria_mb?: number; app_cpu?: number };
}

const ANCHO = 640, ALTO = 160, IZQ = 44, DER = 8, ARR = 10, ABA = 22;
const cifra = (v: number | null | undefined, unidad: string) =>
  v == null ? "—" : `${v.toLocaleString("es", { maximumFractionDigits: 1 })} ${unidad}`;

/* Línea de las últimas 24 h; un hueco de más de 15 minutos (medición que faltó) corta la línea. */
function Grafico({ titulo, puntos, unidad, tope }: { titulo: string; puntos: [number, number | null][]; unidad: string; tope?: number }) {
  const ahora = Date.now() / 1000, desde = ahora - 86400;
  const valores = puntos.map((p) => p[1]).filter((v): v is number => typeof v === "number");
  const conTope = tope && Math.max(0, ...valores) >= tope * 0.5 ? tope : undefined;
  const maximo = Math.max(1, ...valores, conTope || 0) * 1.1;
  const x = (t: number) => IZQ + ((t - desde) / 86400) * (ANCHO - IZQ - DER);
  const y = (v: number) => ARR + (1 - v / maximo) * (ALTO - ARR - ABA);
  const tramos: string[][] = [];
  let actual: string[] = [], anterior: number | null = null;
  for (const [t, v] of puntos) {
    if (t < desde) continue;
    if (typeof v !== "number" || (anterior !== null && t - anterior > 900)) { if (actual.length) tramos.push(actual); actual = []; }
    if (typeof v === "number") actual.push(`${x(t).toFixed(1)},${y(v).toFixed(1)}`);
    anterior = t;
  }
  if (actual.length) tramos.push(actual);
  const resumen = valores.length ? `${titulo}: ahora ${cifra(valores[valores.length - 1], unidad)}, máximo ${cifra(Math.max(...valores), unidad)}` : `${titulo}: sin datos`;
  return (
    <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} className="w-full h-auto max-h-48 text-ms-blue" role="img" aria-label={resumen}>
      <title>{resumen}</title>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={IZQ} x2={ANCHO - DER} y1={y((maximo / 1.1) * f)} y2={y((maximo / 1.1) * f)} stroke="#eee" />
          <text x={IZQ - 4} y={y((maximo / 1.1) * f) + 4} textAnchor="end" fontSize="11" fill="#616161">{cifra((maximo / 1.1) * f, "")}</text>
        </g>
      ))}
      {[24, 12, 0].map((h) => (
        <text key={h} x={x(ahora - h * 3600)} y={ALTO - 6} fontSize="11" fill="#616161" textAnchor={h === 24 ? "start" : h === 0 ? "end" : "middle"}>{h ? `−${h} h` : "ahora"}</text>
      ))}
      {conTope && <line x1={IZQ} x2={ANCHO - DER} y1={y(conTope)} y2={y(conTope)} stroke="#b3261e" strokeDasharray="4 4" />}
      {tramos.map((t, i) => t.length === 1
        ? <circle key={i} cx={t[0].split(",")[0]} cy={t[0].split(",")[1]} r={2} fill="currentColor" />
        : <polyline key={i} points={t.join(" ")} fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round" />)}
    </svg>
  );
}

/* CPU y memoria del sitio (su PHP-FPM, sus tareas y su aplicación propia) en las últimas 24 h, cada 5 minutos. */
export function RecursosPestana({ dominio }: { dominio: string }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Datos>(`/sitios/${dominio}/recursos`).then(setDatos).catch((e) => setError(e.message)); }, [dominio]);

  if (error) return <p className="text-sm text-ms-red">{error}</p>;
  if (!datos) return <p className="text-sm text-ms-gray-60">Cargando…</p>;
  if (!datos.instalado) return <p className="text-sm text-ms-gray-60">La medición no está activa: aplique el ajuste 69 (deploy/ajustes/aplicar-ajustes.sh --aplicar).</p>;
  const { resumen: r, limites: l } = datos;
  return (
    <div className="space-y-3">
      {datos.puntos.length === 0 && <p className="text-sm text-ms-gray-60">Todavía no hay mediciones: la primera llega en unos 5 minutos.</p>}
      {datos.puntos.length > 0 && (
        <>
          <div className="flex flex-wrap gap-4 text-sm">
            <span>CPU media {cifra(r.cpu_media, "%")} · máxima {cifra(r.cpu_maxima, "%")}</span>
            <span>Memoria media {cifra(r.memoria_media_mb, "MB")} · máxima {cifra(r.memoria_maxima_mb, "MB")}</span>
          </div>
          <h3 className="text-sm font-semibold text-ms-gray-130">CPU (100 % = un núcleo)</h3>
          <Grafico titulo="CPU" unidad="%" tope={l.app_cpu} puntos={datos.puntos.map((p) => [p[0], p[1]])} />
          <h3 className="text-sm font-semibold text-ms-gray-130">Memoria</h3>
          <Grafico titulo="Memoria" unidad="MB" tope={l.app_memoria_mb} puntos={datos.puntos.map((p) => [p[0], p[2]])} />
        </>
      )}
      <p className="text-xs text-ms-gray-90">
        Límites: {l.php_procesos} procesos de PHP de {l.php_memoria_mb} MB cada uno
        {l.app_memoria_mb ? ` · aplicación propia: ${l.app_memoria_mb} MB y ${(l.app_cpu || 0) / 100} núcleos` : ""}.
      </p>
      <p className="text-[11px] text-ms-gray-60">PHP-FPM y las tareas se miden por el usuario del sitio en /proc (memoria PSS); la aplicación propia, por su grupo de control de systemd. Es orientativo: lo que nace y muere entre dos mediciones no se ve.</p>
    </div>
  );
}
