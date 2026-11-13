import { useState } from "react";
import { api } from "../../api/client";
import { EstadoTunel } from "./tunelTipos";

// Abrir un túnel de soporte hacia un equipo. Da acceso remoto, así que pide motivo y escribir CONFIRMO.
// La clave privada (modo manual) solo viaja dentro de la orden firmada: aquí se borra al emitir y el
// servidor no la guarda en el registro ni la devuelve.

interface Props { equipoId: string; nombre: string; estado: EstadoTunel; minutos: number; onCerrar: () => void; onHecho: () => void }

export function AbrirTunel({ equipoId, nombre, estado, minutos, onCerrar, onHecho }: Props) {
  const a = estado.ajustes;
  const [f, setF] = useState({
    minutos, ubicacion: a.host_fuera || !a.host_red ? "fuera" : "red", host: "", puerto: String(estado.puerto_sugerido), clave: "", motivo: "", confirmacion: "",
  });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const hostElegido = f.ubicacion === "red" ? a.host_red : a.host_fuera;
  const listo = f.motivo.trim().length >= 5 && f.confirmacion === "CONFIRMO" && (hostElegido || f.host.trim()) && !enviando;

  const emitir = async () => {
    setEnviando(true); setError("");
    const parametros: Record<string, unknown> = { minutos: f.minutos };
    if (hostElegido) parametros.ubicacion = f.ubicacion; else parametros.host = f.host.trim();
    if (!a.automatico) {
      if (f.puerto.trim()) parametros.puerto_remoto = Number(f.puerto);
      if (f.clave.trim()) parametros.clave = f.clave;
    }
    try {
      await api.post("/flota/ordenes", { tipo: "abrir_tunel_soporte", motivo: f.motivo, confirmacion: f.confirmacion, equipos: [equipoId], parametros });
      setF({ ...f, clave: "" });
      onHecho();
    } catch (e: any) { setError(e.message); } finally { setEnviando(false); }
  };

  const campo = "mt-1 block w-full px-2.5 py-1.5 border border-ms-gray-40 rounded";
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-lg p-5 space-y-3 text-sm max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold text-base">Abrir túnel de soporte hacia {nombre}</h3>
        <p className="text-xs text-ms-gray-60">El equipo abrirá una conexión de salida y temporal hacia el servidor de túneles. Se cierra sola al cumplirse el tiempo. Para entrar al equipo sigue haciendo falta, además, la llave de soporte de Tecnología.</p>
        <label className="block text-xs">Duración
          <select value={f.minutos} onChange={(e) => setF({ ...f, minutos: Number(e.target.value) })} className={campo}>
            {a.duraciones.map((m) => <option key={m} value={m}>{m} minutos</option>)}</select></label>
        {(a.host_fuera || a.host_red) ? <div className="text-xs space-y-1">¿Dónde está el equipo?
          {a.host_fuera && <label className="flex items-center gap-2"><input type="radio" checked={f.ubicacion === "fuera"} onChange={() => setF({ ...f, ubicacion: "fuera" })} />Fuera de la red (internet): {a.host_fuera}</label>}
          {a.host_red && <label className="flex items-center gap-2"><input type="radio" checked={f.ubicacion === "red"} onChange={() => setF({ ...f, ubicacion: "red" })} />En la red interna o conectado a la VPN: {a.host_red}</label>}
        </div> : <label className="block text-xs">Dirección del servidor de túneles
          <input value={f.host} onChange={(e) => setF({ ...f, host: e.target.value })} className={campo} /></label>}
        {a.automatico
          ? <p className="text-xs text-ms-gray-90 bg-ms-gray-10 rounded px-3 py-2">El servidor creará una clave nueva para este equipo, la registrará en el servidor de túneles y anulará la anterior. No hace falta pegar nada.</p>
          : <>
            <label className="block text-xs">Puerto de este equipo en el servidor de túneles ({a.puerto_min}-{a.puerto_max})
              <input type="number" min={a.puerto_min} max={a.puerto_max} value={f.puerto} onChange={(e) => setF({ ...f, puerto: e.target.value })} className="mt-1 block w-32 px-2.5 py-1.5 border border-ms-gray-40 rounded" />
              <span className="block mt-1 text-ms-gray-60">{estado.puerto_asignado ? `Este equipo ya tiene asignado el ${estado.puerto_asignado}.` : `Primer túnel de este equipo: se propone el ${estado.puerto_sugerido}.`} Debe ser el mismo puerto con el que se registró su clave en el servidor de túneles.</span></label>
            <label className="block text-xs">Clave privada del túnel de este equipo (opcional)
              <textarea value={f.clave} onChange={(e) => setF({ ...f, clave: e.target.value })} rows={4} spellCheck={false} autoComplete="off" placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" className={`${campo} font-mono text-[11px]`} />
              <span className="block mt-1 text-ms-gray-60">Si la deja vacía, el equipo usará la clave que ya tenga instalada. La clave viaja solo dentro de la orden firmada; no queda en el registro ni se vuelve a mostrar, y el equipo la borra al cerrar el túnel.</span></label>
          </>}
        <label className="block text-xs">Motivo (queda en el registro)
          <input value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} placeholder="Ej: la persona pidió ayuda con su equipo desde fuera de la oficina" className={campo} /></label>
        <label className="block text-xs text-red-700">Esta orden da acceso remoto al equipo: escriba CONFIRMO
          <input value={f.confirmacion} onChange={(e) => setF({ ...f, confirmacion: e.target.value })} className="mt-1 block w-40 px-2.5 py-1.5 border border-red-300 rounded" /></label>
        {error && <div className="px-3 py-2 rounded bg-red-50 text-red-700 text-xs">{error}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onCerrar} className="px-3 py-1.5 border border-ms-gray-40 rounded">Cancelar</button>
          <button disabled={!listo} onClick={emitir} className="px-3 py-1.5 bg-ms-blue text-white rounded disabled:opacity-40">Firmar y abrir túnel</button>
        </div>
      </div>
    </div>
  );
}
