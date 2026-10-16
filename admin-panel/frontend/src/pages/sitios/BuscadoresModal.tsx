import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Prueba { titulo: string; ok: boolean; detalle: string }
interface Estado { pruebas: Prueba[]; indexnow: boolean; ultimo_aviso?: { fecha: string; codigo: number; urls: number } | null }

/* Visibilidad del sitio en buscadores y asistentes de IA, aviso por IndexNow y verificación de Google. */
export function BuscadoresModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [est, setEst] = useState<Estado | null>(null);
  const [mensaje, setMensaje] = useState("Revisando el sitio como lo vería un buscador…");
  const [codigo, setCodigo] = useState("");

  const revisar = () => api.get<Estado>(`/sitios/${dominio}/buscadores`).then((d) => { setEst(d); setMensaje(""); }).catch((e) => setMensaje(e.message));
  useEffect(() => { revisar(); }, [dominio]);

  const avisar = async () => {
    setMensaje("Avisando a los buscadores…");
    try { const r = await api.post<{ avisadas: number; resultado: string }>(`/sitios/${dominio}/avisar`); setMensaje(`IndexNow: ${r.resultado} (${r.avisadas} direcciones).`); revisar(); }
    catch (e) { setMensaje((e as Error).message); }
  };
  const verificarGoogle = async () => {
    setMensaje("Añadiendo el registro de verificación a la zona DNS…");
    try { await api.post(`/sitios/${dominio}/google`, { codigo }); setMensaje("Registro añadido. En Search Console pulse «Verificar» (el DNS puede tardar unos minutos)."); setCodigo(""); }
    catch (e) { setMensaje((e as Error).message); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-xl p-5 space-y-4 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-ms-gray-130">Buscadores e IA — {dominio}</h2>
        {est && (
          <ul className="space-y-1.5 text-sm">
            {est.pruebas.map((p) => (
              <li key={p.titulo} className="flex gap-2">
                <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${p.ok ? "bg-green-500" : "bg-amber-400"}`} />
                <span>{p.titulo}{p.detalle && <span className="text-xs text-ms-gray-60"> — {p.detalle}</span>}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="border-t border-ms-gray-30 pt-3 space-y-2">
          <h3 className="text-sm font-semibold">Bing, Yandex y otros (IndexNow)</h3>
          <p className="text-xs text-ms-gray-90">Se les avisa al momento. WordPress además avisa solo cada vez que se publica algo.
            {est?.ultimo_aviso && <> Último aviso: {est.ultimo_aviso.fecha} ({est.ultimo_aviso.urls} direcciones, respuesta {est.ultimo_aviso.codigo}).</>}</p>
          <button onClick={avisar} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Avisar ahora</button>
        </div>
        <div className="border-t border-ms-gray-30 pt-3 space-y-2">
          <h3 className="text-sm font-semibold">Google (Search Console)</h3>
          <p className="text-xs text-ms-gray-90">Google no admite avisos. 1) En search.google.com/search-console añada la propiedad de tipo «Dominio» con <b>{dominio}</b>. 2) Pegue aquí el registro TXT que le da: se pone solo en la zona DNS. 3) Pulse «Verificar» en Search Console y envíe el mapa del sitio (<code>/sitemap.xml</code>, o <code>/wp-sitemap.xml</code> en WordPress).</p>
          <div className="flex gap-2">
            <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="google-site-verification=…" className="flex-1 px-3 py-1.5 border border-ms-gray-40 rounded text-sm font-mono" />
            <button onClick={verificarGoogle} disabled={!codigo.trim()} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Añadir</button>
          </div>
        </div>
        {mensaje && <p className="text-sm text-ms-gray-90">{mensaje}</p>}
        <div className="text-right"><button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm">Cerrar</button></div>
      </div>
    </div>
  );
}
