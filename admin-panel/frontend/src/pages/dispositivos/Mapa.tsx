import { useState } from "react";

// Mapa mínimo sin librerías: nueve teselas de OpenStreetMap alrededor del punto, el marcador, el
// círculo de precisión y el rastro de posiciones anteriores que caigan dentro del recuadro.

export interface Punto { lat: number; lon: number; precision_m?: number | null; origen?: string }

const T = 256;
function aTesela(lat: number, lon: number, z: number) {
  const n = 2 ** z, r = (lat * Math.PI) / 180;
  return { x: ((lon + 180) / 360) * n, y: ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n };
}

export function Mapa({ actual, rastro }: { actual: Punto; rastro: Punto[] }) {
  const [z, setZ] = useState(16);
  const c = aTesela(actual.lat, actual.lon, z);
  const tx = Math.floor(c.x), ty = Math.floor(c.y);
  const px = (p: Punto) => { const t = aTesela(p.lat, p.lon, z); return { x: (t.x - (tx - 1)) * T, y: (t.y - (ty - 1)) * T }; };
  const m = px(actual);
  const metrosPorPixel = (156543.03392 * Math.cos((actual.lat * Math.PI) / 180)) / 2 ** z;
  const radio = actual.precision_m ? Math.min(380, actual.precision_m / metrosPorPixel) : 0;
  const teselas = [-1, 0, 1].flatMap((dy) => [-1, 0, 1].map((dx) => ({ dx, dy })));

  return (
    <div>
      <div className="relative overflow-hidden rounded border border-ms-gray-30 mx-auto" style={{ maxWidth: T * 3 }}>
        {/* Todo dentro de un SVG con viewBox: teselas, rastro y marcador escalan juntos al ancho disponible. */}
        <svg viewBox={`0 0 ${T * 3} ${T * 3}`} className="block w-full h-auto bg-ms-gray-10">
          {teselas.map(({ dx, dy }) => (
            <image key={`${z}/${dx}/${dy}`} href={`https://tile.openstreetmap.org/${z}/${tx + dx}/${ty + dy}.png`}
              x={(dx + 1) * T} y={(dy + 1) * T} width={T} height={T} />))}
          {rastro.map((p, i) => { const q = px(p); return q.x < 0 || q.y < 0 || q.x > T * 3 || q.y > T * 3 ? null :
            <circle key={i} cx={q.x} cy={q.y} r={4} fill={p.origen === "avistamiento" ? "#8661c5" : "#0078d4"} fillOpacity={0.55} />; })}
          {radio > 6 && <circle cx={m.x} cy={m.y} r={radio} fill="#d13438" fillOpacity={0.12} stroke="#d13438" strokeOpacity={0.5} />}
          <circle cx={m.x} cy={m.y} r={7} fill="#d13438" stroke="#fff" strokeWidth={2} />
        </svg>
        <div className="absolute top-2 right-2 flex flex-col bg-white rounded shadow border border-ms-gray-30">
          <button onClick={() => setZ(Math.min(19, z + 1))} className="w-7 h-7 text-lg leading-none hover:bg-ms-gray-10">+</button>
          <button onClick={() => setZ(Math.max(5, z - 1))} className="w-7 h-7 text-lg leading-none hover:bg-ms-gray-10 border-t border-ms-gray-30">−</button>
        </div>
        <div className="absolute bottom-0 right-0 bg-white/80 text-[10px] px-1">© OpenStreetMap</div>
      </div>
      <div className="text-xs text-ms-gray-60 mt-1 text-center">
        {actual.lat.toFixed(6)}, {actual.lon.toFixed(6)}{actual.precision_m ? ` · ±${Math.round(actual.precision_m)} m` : ""} ·{" "}
        <a className="text-ms-blue hover:underline" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${actual.lat}&mlon=${actual.lon}#map=18/${actual.lat}/${actual.lon}`}>abrir en OpenStreetMap</a> ·{" "}
        <a className="text-ms-blue hover:underline" target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${actual.lat},${actual.lon}`}>Google Maps</a>
      </div>
    </div>
  );
}
