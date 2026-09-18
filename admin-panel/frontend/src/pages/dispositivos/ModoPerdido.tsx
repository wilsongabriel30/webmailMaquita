import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Equipo, fechaHora } from "./tipos";

interface Comando { id: number; tipo: string; estado: string; motivo?: string; creado_por: string; creado_en: string; entregado_en?: string; terminado_en?: string; resultado?: { detalle?: string } }
const NOMBRE: Record<string, string> = { localizar: "Localizar ahora", alarma: "Hacer sonar", bloquear: "Bloquear pantalla", desbloquear: "Fin del modo perdido", borrar: "Borrado remoto", respaldar: "Respaldo pedido" };

/** Modo perdido y comandos a distancia. Todo pide motivo y queda en la auditoría. */
export function ModoPerdido({ equipo, onCambio }: { equipo: Equipo; onCambio: () => void }) {
  const [comandos, setComandos] = useState<Comando[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const completo = equipo.modo === "propietario";
  const perdido = equipo.estado === "perdido";

  const cargar = () => api.get<{ comandos: Comando[] }>(`/dispositivos/equipos/${equipo.id}/comandos`).then((r) => setComandos(r.comandos)).catch(() => {});
  useEffect(() => { cargar(); const t = setInterval(cargar, 30000); return () => clearInterval(t); }, [equipo.id]);
  const hecho = (t: string) => { setMsg({ ok: true, t }); cargar(); onCambio(); };
  const fallo = (e: any) => setMsg({ ok: false, t: e.message });

  const declarar = async () => {
    const motivo = prompt("¿Qué pasó? (robo, extravío, dónde y cuándo). Queda en la auditoría:");
    if (!motivo) return;
    const telefono = prompt("Teléfono de contacto que se mostrará en la pantalla bloqueada (opcional):") || "";
    try { const r = await api.post<{ bloqueo_encolado: boolean }>(`/dispositivos/equipos/${equipo.id}/perdido`, { motivo, telefono });
      hecho(r.bloqueo_encolado ? "Declarado perdido. En su próximo reporte el teléfono se bloqueará, enviará su posición y reportará cada 5 minutos." : "Declarado perdido. Está en modo limitado: enviará su posición, pero no se puede bloquear a distancia."); }
    catch (e) { fallo(e); }
  };
  const recuperar = async () => {
    const motivo = prompt("¿Cómo se recuperó? Queda en la auditoría:"); if (!motivo) return;
    try { await api.post(`/dispositivos/equipos/${equipo.id}/recuperado`, { motivo }); hecho("Equipo recuperado: vuelve al funcionamiento normal."); } catch (e) { fallo(e); }
  };
  const comando = async (tipo: string) => {
    const motivo = prompt(`${NOMBRE[tipo]} — motivo (queda en la auditoría):`); if (!motivo) return;
    const cuerpo: Record<string, string> = { tipo, motivo };
    if (tipo === "borrar") {
      const c = prompt(`BORRADO REMOTO: el teléfono se restablece de fábrica y se pierde TODO lo que no esté respaldado. No se puede deshacer y el equipo dejará de reportar.\n\nPara confirmar escriba exactamente: BORRAR ${equipo.id}`);
      if (!c) return; cuerpo.confirmacion = c;
    }
    try { await api.post(`/dispositivos/equipos/${equipo.id}/comandos`, cuerpo); hecho(`«${NOMBRE[tipo]}» enviado: se ejecuta en el próximo reporte del teléfono.`); } catch (e) { fallo(e); }
  };
  const anular = async (id: number) => { try { await api.del(`/dispositivos/comandos/${id}`); cargar(); } catch (e) { fallo(e); } };
  const boton = "px-3 py-1.5 text-sm rounded border disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div className={`rounded-lg p-4 border ${perdido ? "bg-red-50 border-red-200" : "bg-white border-ms-gray-30"}`}>
      <h3 className="text-sm font-semibold mb-1">{perdido ? `Equipo PERDIDO desde ${fechaHora(equipo.perdido_en)}` : "Pérdida o robo"}</h3>
      {perdido && <p className="text-sm mb-2">{equipo.perdido_motivo}</p>}
      {msg && <div className={`text-sm px-3 py-2 mb-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-white text-red-700 border border-red-200"}`}>{msg.t}</div>}
      <div className="flex flex-wrap gap-2">
        {!perdido ? <button onClick={declarar} className={`${boton} border-ms-red/40 text-ms-red hover:bg-red-50`}>Declarar perdido o robado</button>
          : <button onClick={recuperar} className={`${boton} border-green-600/40 text-green-700 bg-white hover:bg-green-50`}>Marcar como recuperado</button>}
        <button onClick={() => comando("localizar")} className={`${boton} border-ms-gray-40 bg-white hover:bg-ms-gray-10`}>Localizar ahora</button>
        <button onClick={() => comando("alarma")} className={`${boton} border-ms-gray-40 bg-white hover:bg-ms-gray-10`}>Hacer sonar</button>
        <button onClick={() => comando("bloquear")} disabled={!completo} title={completo ? "" : "Solo en equipos con control completo"} className={`${boton} border-ms-gray-40 bg-white hover:bg-ms-gray-10`}>Bloquear pantalla</button>
        <button onClick={() => comando("borrar")} disabled={!completo || !perdido} title={!completo ? "Solo en equipos con control completo" : !perdido ? "Primero declare el equipo como perdido" : "Solo superadministradores"} className={`${boton} border-ms-red/40 text-ms-red bg-white hover:bg-red-50`}>Borrado remoto</button>
      </div>
      {!completo && <p className="text-xs text-ms-gray-60 mt-2">Equipo en modo limitado: se puede localizar y hacer sonar, pero Android no permite bloquearlo ni borrarlo a distancia.</p>}
      {comandos.length > 0 && <ul className="text-sm mt-3 space-y-1">
        {comandos.slice(0, 8).map((c) => <li key={c.id} className="flex justify-between gap-2">
          <span>{NOMBRE[c.tipo] || c.tipo} <span className="text-xs text-ms-gray-60">· {c.creado_por} · {fechaHora(c.creado_en)}{c.motivo ? ` · ${c.motivo}` : ""}</span></span>
          <span className="text-xs shrink-0">{c.estado === "pendiente" ? <>esperando al teléfono · <button onClick={() => anular(c.id)} className="text-ms-blue hover:underline">anular</button></>
            : c.estado === "entregado" ? `entregado ${fechaHora(c.entregado_en)}` : `${c.estado} ${fechaHora(c.terminado_en)}${c.resultado?.detalle ? ` · ${c.resultado.detalle}` : ""}`}</span>
        </li>)}
      </ul>}
    </div>
  );
}
