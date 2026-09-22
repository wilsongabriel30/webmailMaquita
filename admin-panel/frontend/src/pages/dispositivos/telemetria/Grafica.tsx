// Gráfica de línea en SVG propio (sin librerías), como el mapa de la fase 2. Escala con el ancho
// disponible. Acepta una serie de puntos {t, v} y, opcionalmente, una banda mín-máx (resumen diario).

export interface Punto { t: number; v: number | null; min?: number | null; max?: number | null; marca?: boolean }

const W = 720, H = 180, PAD = { l: 36, r: 8, t: 10, b: 22 };

export function Grafica({ puntos, max, unidad, color = "#0078d4", titulo, umbral }: { puntos: Punto[]; max: number; unidad: string; color?: string; titulo: string; umbral?: number }) {
  const validos = puntos.filter((p) => p.v != null);
  if (validos.length < 2) return <div className="rounded border border-ms-gray-30 p-3 text-xs text-ms-gray-60">{titulo}: sin datos suficientes en este rango.</div>;
  const t0 = validos[0].t, t1 = validos[validos.length - 1].t || t0 + 1;
  const x = (t: number) => PAD.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - Math.min(max, Math.max(0, v)) / max) * (H - PAD.t - PAD.b);
  const linea = validos.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v as number).toFixed(1)}`).join(" ");
  const conBanda = validos.filter((p) => p.min != null && p.max != null);
  const banda = conBanda.length > 1
    ? conBanda.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.max as number).toFixed(1)}`).join(" ") + " " +
      [...conBanda].reverse().map((p) => `L${x(p.t).toFixed(1)},${y(p.min as number).toFixed(1)}`).join(" ") + " Z"
    : "";
  const etiquetasX = [0, 0.25, 0.5, 0.75, 1].map((f) => { const t = t0 + f * (t1 - t0); const d = new Date(t);
    return { x: x(t), texto: t1 - t0 > 2 * 86400000 ? d.toLocaleDateString("es-EC", { day: "2-digit", month: "2-digit" }) : d.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" }) }; });
  return (
    <div className="rounded border border-ms-gray-30 p-2">
      <div className="text-xs font-medium text-ms-gray-90 mb-1">{titulo}</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => <g key={f}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(f * max)} y2={y(f * max)} stroke="#edebe9" />
          <text x={PAD.l - 4} y={y(f * max) + 3} fontSize="9" textAnchor="end" fill="#605e5c">{Math.round(f * max)}{unidad}</text></g>)}
        {umbral != null && <line x1={PAD.l} x2={W - PAD.r} y1={y(umbral)} y2={y(umbral)} stroke="#d13438" strokeDasharray="4 3" />}
        {banda && <path d={banda} fill={color} fillOpacity={0.15} />}
        <path d={linea} fill="none" stroke={color} strokeWidth={1.5} />
        {validos.filter((p) => p.marca).map((p, i) => <circle key={i} cx={x(p.t)} cy={y(p.v as number)} r={2.5} fill="#107c10" />)}
        {etiquetasX.map((e, i) => <text key={i} x={e.x} y={H - 6} fontSize="9" textAnchor={i === 0 ? "start" : i === 4 ? "end" : "middle"} fill="#605e5c">{e.texto}</text>)}
      </svg>
    </div>
  );
}
