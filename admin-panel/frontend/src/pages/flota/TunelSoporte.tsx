import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { AbrirTunel } from "./AbrirTunel";
import { CuentaAtras } from "./CuentaAtras";
import { fechaHora } from "./tipos";
import { CIERRE, COLOR_SITUACION, EstadoTunel, SITUACION, duracion } from "./tunelTipos";

// Túnel de soporte de un equipo (T-120): abrirlo por unos minutos, ver cuánto le queda y cerrarlo.
// Sirve para atender un equipo que está fuera de la red (un hotel, datos del celular).

interface Props { equipoId: string; nombre: string; firmaDisponible: boolean; onCambio: () => void }

export function TunelSoporte({ equipoId, nombre, firmaDisponible, onCambio }: Props) {
  const [d, setD] = useState<EstadoTunel | null>(null);
  const [minutos, setMinutos] = useState(30);
  const [abrir, setAbrir] = useState(false);
  const [error, setError] = useState("");
  const cargar = () => api.get<EstadoTunel>(`/flota/tunel/estado?equipo_id=${equipoId}`).then((r) => { setD(r); setError(""); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); const t = setInterval(cargar, 20000); return () => clearInterval(t); }, [equipoId]);

  const t = d?.tunel || null;
  const vivo = !!t && ["abriendo", "abierto", "cierre_solicitado"].includes(t.situacion);
  const hecho = () => { cargar(); onCambio(); };

  const cerrar = async () => {
    const motivo = prompt("Motivo del cierre (queda en el registro):");
    if (!motivo) return;
    try { await api.post("/flota/ordenes", { tipo: "cerrar_tunel_soporte", motivo, equipos: [equipoId] }); hecho(); } catch (e: any) { setError(e.message); }
  };
  const anular = async () => {
    if (!t || !confirm("¿Anular la solicitud? El equipo todavía no la ha recogido y el túnel no se abrirá.")) return;
    try { await api.del(`/flota/ordenes/${t.orden_id}`); hecho(); } catch (e: any) { setError(e.message); }
  };

  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 p-4 space-y-2 text-sm">
      <div className="flex items-center gap-3 flex-wrap">
        <h3 className="text-sm font-semibold mr-auto">Túnel de soporte</h3>
        {d && <>
          <select value={minutos} onChange={(e) => setMinutos(Number(e.target.value))} aria-label="Duración del túnel" className="px-2 py-1.5 border border-ms-gray-40 rounded text-sm">
            {d.ajustes.duraciones.map((m) => <option key={m} value={m}>{m} min</option>)}</select>
          <button disabled={!firmaDisponible} onClick={() => setAbrir(true)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-40">Abrir túnel de soporte</button>
          {t?.situacion === "solicitado"
            ? <button onClick={anular} className="px-3 py-1.5 border border-red-300 text-red-700 rounded text-sm">Anular solicitud</button>
            : <button disabled={!vivo || !firmaDisponible} onClick={cerrar} className="px-3 py-1.5 border border-red-300 text-red-700 rounded text-sm disabled:opacity-40">Cerrar túnel</button>}
        </>}
      </div>
      {error && <div className="text-xs px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      {!d && !error && <div className="text-xs text-ms-gray-60">Cargando…</div>}
      {d && !t && <p className="text-xs text-ms-gray-60">A este equipo todavía no se le ha abierto ningún túnel. Úselo para atender un equipo que está fuera de la red; se cierra solo al cumplirse el tiempo y cada apertura queda registrada.</p>}
      {t && <div className="text-xs space-y-1">
        <div><span className={`font-semibold ${COLOR_SITUACION[t.situacion]}`}>{SITUACION[t.situacion]}</span>
          {(t.situacion === "abierto" || t.situacion === "cierre_solicitado") && t.expira_en && <> · se cierra solo en <CuentaAtras hasta={t.expira_en} onFin={cargar} /> (a las {fechaHora(t.expira_en)})</>}
          {t.situacion === "cerrado" && <> · {fechaHora(t.cerrado_en)} · {CIERRE[t.cierre || ""] || t.cierre} · estuvo abierto {duracion(t.duracion_s)}</>}</div>
        <div className="text-ms-gray-90">Pedido por {t.emitida_por} el {fechaHora(t.emitida_en)} · {t.parametros.minutos} minutos · puerto {t.parametros.puerto_remoto} del servidor de túneles ({t.parametros.host}) · motivo: {t.motivo}</div>
        {t.situacion === "solicitado" && <div className="text-ms-gray-60">El equipo recoge sus órdenes cada 15 minutos como máximo. Si no la recoge antes de las {fechaHora(t.caduca_en)}, la orden caduca y el túnel no se abre.</div>}
        {t.situacion === "cierre_solicitado" && <div className="text-ms-gray-60">El equipo cerrará el túnel en cuanto recoja la orden de cierre (15 minutos como máximo).</div>}
        {(t.situacion === "abierto" || t.situacion === "cierre_solicitado") && <div className="text-ms-gray-60">Para entrar: desde el servidor de túneles, conéctese al puerto {t.parametros.puerto_remoto} local con la llave de soporte del equipo.</div>}
        {t.situacion === "no_abierto" && t.registro && <pre className="bg-ms-gray-10 rounded p-2 whitespace-pre-wrap max-h-40 overflow-auto">{t.registro}</pre>}
      </div>}
      {abrir && d && <AbrirTunel equipoId={equipoId} nombre={nombre} estado={d} minutos={minutos} onCerrar={() => setAbrir(false)} onHecho={() => { setAbrir(false); hecho(); }} />}
    </div>
  );
}
