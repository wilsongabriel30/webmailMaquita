import { useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo, type EstadoWeb, type PropsPestana } from "./tipos";

const CADUCIDAD: Record<string, string> = {
  off: "Sin caché (siempre se descargan)", "1h": "1 hora", "1d": "1 día", "7d": "7 días", "30d": "30 días (de serie)", "180d": "6 meses", "365d": "1 año",
};

/* Optimización para conexiones lentas (ADSL rural, satélite): compresión, caché del navegador y caché de página. */
export function OptimizacionPestana({ dominio, estado, ocupado, hacer }: PropsPestana) {
  const o = estado.optimizacion;
  const [compresion, setCompresion] = useState(o.compresion);
  const [estaticos, setEstaticos] = useState(o.estaticos);
  const [cache, setCache] = useState(o.cache_pagina);
  const [minutos, setMinutos] = useState(String(o.cache_minutos));

  const guardar = () => hacer("Optimización aplicada.", () => api.put<EstadoWeb>(`/sitios/${dominio}/web/optimizacion`,
    { compresion, estaticos, cache_pagina: cache, cache_minutos: Number(minutos) || 10 }));
  const purgar = () => hacer("", async () => {
    const r = await api.post<{ purgados: number }>(`/sitios/${dominio}/web/purgar`);
    alert(`Caché de página vaciada (${r.purgados} copias).`);
  });

  return (
    <div className="space-y-4">
      <p className="text-xs text-ms-gray-90">Pensado para quien entra desde el campo por ADSL o por satélite: menos datos por la línea y menos viajes al servidor.</p>
      <section className="space-y-1">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={compresion} onChange={(e) => setCompresion(e.target.checked)} />Comprimir páginas, CSS, JavaScript, SVG y fuentes ({o.brotli ? "gzip y brotli" : "gzip"})</label>
        <p className="text-[11px] text-ms-gray-60 ml-6">Suele reducir el texto a la cuarta parte. Las imágenes y los vídeos ya vienen comprimidos.</p>
      </section>
      <section className="space-y-1">
        <label className="text-sm">Caché del navegador para CSS, JavaScript, imágenes y fuentes{" "}
          <select value={estaticos} onChange={(e) => setEstaticos(e.target.value)} className={campo}>
            {(o.caducidades || Object.keys(CADUCIDAD)).map((c) => <option key={c} value={c}>{CADUCIDAD[c] || c}</option>)}
          </select>
        </label>
        <p className="text-[11px] text-ms-gray-60">El visitante no los vuelve a descargar en cada página. Si cambia un archivo y no se ve, cambie su nombre o añada «?v=2» al enlace.</p>
      </section>
      <section className="space-y-1">
        <label className={`flex items-center gap-2 text-sm ${o.php ? "" : "opacity-50"}`}>
          <input type="checkbox" disabled={!o.php} checked={cache} onChange={(e) => setCache(e.target.checked)} />Caché de página (sitios PHP: WordPress, Joomla…)
        </label>
        {cache && <label className="text-xs text-ms-gray-90 ml-6">Cada copia dura <input value={minutos} onChange={(e) => setMinutos(e.target.value.replace(/\D/g, ""))} className={`${campo} w-16`} /> minutos</label>}
        <p className="text-[11px] text-ms-gray-60 ml-6">Las páginas se sirven sin pasar por PHP durante esos minutos y, si PHP se cae, se sirve la última copia. Nunca se usa con la sesión iniciada, en la administración, el carrito, las búsquedas ni los formularios: quien edita ve siempre lo último. Tras publicar algo urgente, vacíe la caché.</p>
      </section>
      <div className="flex gap-2">
        <button disabled={ocupado} onClick={guardar} className={botonPrincipal}>Guardar</button>
        {o.cache_pagina && <button disabled={ocupado} onClick={purgar} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm disabled:opacity-50">Vaciar la caché de página</button>}
      </div>
    </div>
  );
}
