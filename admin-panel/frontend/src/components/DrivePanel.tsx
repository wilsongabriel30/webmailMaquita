/**
 * DrivePanel — cuota del Drive (Almacén) y vínculo con una persona del directorio central.
 *
 * Dos usos: dentro del formulario de alta (controlado por el padre: gb/setGb, persona/setPersona; el
 * padre guarda tras crear el buzón) y sobre un buzón existente (prop `correo`: carga el estado y
 * guarda al pulsar). Modo «nómina»: la persona puede buscarse y vincularse; modo «local»: solo cuota.
 */
import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface DriveConfig { modo: string; cuota_defecto_gb: number }
interface Persona { id: number; full_name: string; email: string; username?: string }
interface Estado { usuario_id: number | null; vinculado_a: Persona | null; cuota_gb: number; cuota_efectiva_gb: number; usado_gb: number }

interface Props {
  cfg: DriveConfig;
  correo?: string;
  gb?: string; setGb?: (v: string) => void;
  persona?: Persona | null; setPersona?: (p: Persona | null) => void;
  onCerrar?: () => void;
}

export function DrivePanel({ cfg, correo, gb, setGb, persona, setPersona, onCerrar }: Props) {
  const controlado = !correo;
  const [gbLocal, setGbLocal] = useState<string>(String(cfg.cuota_defecto_gb));
  const [personaLocal, setPersonaLocal] = useState<Persona | null>(null);
  const [estado, setEstado] = useState<Estado | null>(null);
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<Persona[]>([]);
  const [msg, setMsg] = useState("");
  const valorGb = controlado ? (gb ?? "") : gbLocal;
  const ponerGb = controlado ? (setGb ?? (() => {})) : setGbLocal;
  const valorPersona = controlado ? (persona ?? null) : personaLocal;
  const ponerPersona = controlado ? (setPersona ?? (() => {})) : setPersonaLocal;

  useEffect(() => {
    if (!correo) return;
    api.get<Estado>(`/drive/estado?correo=${encodeURIComponent(correo)}`).then((e) => {
      setEstado(e); setGbLocal(String(e.cuota_gb || 0)); setPersonaLocal(e.vinculado_a);
    }).catch((e: any) => setMsg(e?.message || "No se pudo leer el estado"));
  }, [correo]);

  useEffect(() => {
    if (cfg.modo !== "nomina" || q.trim().length < 2) { setResultados([]); return; }
    const t = setTimeout(() => {
      api.get<{ personas: Persona[] }>(`/drive/directorio?q=${encodeURIComponent(q.trim())}`).then((r) => setResultados(r.personas || [])).catch(() => setResultados([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, cfg.modo]);

  const guardar = async () => {
    if (!correo) return;
    setMsg("");
    try {
      if (cfg.modo === "nomina") await api.post("/drive/enlace", { correo, usuario_id: personaLocal ? personaLocal.id : null });
      const r = await api.post<{ cuota_efectiva_gb: number }>("/drive/cuota", { correo, cuota_gb: parseFloat(gbLocal || "0") || 0 });
      setMsg(`Guardado. Cuota efectiva del Drive: ${r.cuota_efectiva_gb} GB.`);
      if (onCerrar) setTimeout(onCerrar, 1200);
    } catch (e: any) { setMsg(e?.message || "No se pudo guardar"); }
  };

  return (
    <div className="space-y-2 pt-2">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Cuota del Drive (GB)</label>
          <input type="number" min={0} step={0.5} value={valorGb} onChange={(e) => ponerGb(e.target.value)}
            title="Espacio de archivos de esta persona en el Drive. 0 = la cuota de la organización. Independiente de la cuota del buzón de correo."
            className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <span className="text-[10px] text-ms-gray-60 mt-0.5 block">
            0 = la de la organización ({cfg.cuota_defecto_gb} GB).{estado ? ` Usa ${estado.usado_gb} GB de ${estado.cuota_efectiva_gb} GB.` : ""}
          </span>
        </div>
        {cfg.modo === "nomina" && (
          <div>
            <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Persona del directorio (Raíces)</label>
            {valorPersona ? (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-ms-gray-130">{valorPersona.full_name} <span className="text-ms-gray-60 text-xs">({valorPersona.email})</span></span>
                <button onClick={() => ponerPersona(null)} className="text-xs text-red-600 hover:underline">quitar</button>
              </div>
            ) : (
              <>
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre o correo…"
                  title="Solo hace falta si el correo del buzón NO es el que la persona tiene en el directorio (por ejemplo, alguien creado en Raíces con un correo personal). Vincula el buzón a esa persona para que vea su Drive."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
                {resultados.length > 0 && (
                  <ul className="border border-ms-gray-40 rounded mt-1 max-h-40 overflow-auto text-sm bg-white">
                    {resultados.map((r) => (
                      <li key={r.id}><button onClick={() => { ponerPersona(r); setQ(""); setResultados([]); }} className="w-full text-left px-3 py-1 hover:bg-ms-gray-20">
                        {r.full_name} <span className="text-ms-gray-60 text-xs">({r.email})</span></button></li>
                    ))}
                  </ul>
                )}
                <span className="text-[10px] text-ms-gray-60 mt-0.5 block">Si el correo del buzón ya está en el directorio, no hace falta vincular.</span>
              </>
            )}
          </div>
        )}
      </div>
      {!controlado && (
        <div className="flex items-center gap-3">
          <button onClick={guardar} className="px-3 py-1.5 bg-teal-600 text-white rounded text-xs font-medium hover:bg-teal-700">Guardar Drive</button>
          {msg && <span className="text-xs text-ms-gray-90">{msg}</span>}
        </div>
      )}
    </div>
  );
}
