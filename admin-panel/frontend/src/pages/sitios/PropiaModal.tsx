import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { AutenticacionGit } from "./AutenticacionGit";

interface Estado {
  tipo: string; git?: string; rama?: string; carpeta?: string; spa?: boolean; modo?: string; entrada?: string;
  puerto_publico?: number; protocolo?: string; cortafuegos?: string; activo: string; carpeta_servida?: string;
  variables?: string[]; registros?: string;
}

const NOMBRE_TIPO: Record<string, string> = { estatico: "Estática", python: "Python", node: "Node.js" };
const ESTADO: Record<string, [string, string]> = {
  active: ["En marcha", "bg-green-50 text-ms-green"], activating: ["Arrancando", "bg-amber-50 text-amber-700"],
  inactive: ["Detenida", "bg-ms-gray-20 text-ms-gray-90"], failed: ["Con fallos", "bg-red-50 text-ms-red"],
  nginx: ["La sirve nginx", "bg-green-50 text-ms-green"],
};

/* Gestionar una aplicación propia: estado, acciones, variables de entorno, registros y retirada. */
export function PropiaModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [est, setEst] = useState<Estado | null>(null);
  const [vars, setVars] = useState<{ clave: string; valor: string; guardada: boolean }[]>([]);
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState("");

  const recibir = (d: Estado) => { setEst(d); setVars((d.variables || []).map((clave) => ({ clave, valor: "", guardada: true }))); };
  const cargar = () => api.get<Estado>(`/sitios/${dominio}/propia`).then(recibir).catch((e) => setMensaje(e.message));
  useEffect(() => { cargar(); }, [dominio]);

  const hacer = async (texto: string, fn: () => Promise<Estado | void>) => {
    setOcupado(texto); setMensaje("");
    try { const d = await fn(); if (d) recibir(d); } catch (e) { setMensaje((e as Error).message); cargar(); } finally { setOcupado(""); }
  };
  const accion = (a: string, texto: string) => hacer(texto, () => api.post<Estado>(`/sitios/${dominio}/propia/accion`, { accion: a }));
  const guardarVars = () => hacer("Guardando y reiniciando…", () => api.put<Estado>(`/sitios/${dominio}/propia/entorno`, {
    variables: Object.fromEntries(vars.filter((v) => v.clave.trim()).map((v) => [v.clave.trim().toUpperCase(), v.guardada && !v.valor ? null : v.valor])),
  }));
  const quitar = () => {
    const c = prompt(`Se detendrá la aplicación, se cerrará su puerto y su código irá a la papelera.\nEscriba ${dominio} para confirmar:`);
    if (c !== dominio) return;
    hacer("Quitando…", async () => { await api.del(`/sitios/${dominio}/propia`, { confirmacion: c }); onCerrar(); });
  };

  const servicio = est && est.tipo !== "estatico";
  const [etiqueta, color] = ESTADO[est?.activo || ""] || [est?.activo || "", "bg-ms-gray-20 text-ms-gray-90"];
  const boton = "px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50";

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-3xl p-5 space-y-4 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-ms-gray-130">Aplicación propia — {dominio}</h2>
        {est && (
          <>
            <div className="text-sm space-y-1">
              <p><b>{NOMBRE_TIPO[est.tipo]}</b>{est.modo && ` (${est.modo.toUpperCase()})`}{est.entrada && <> · entrada <code>{est.entrada}</code></>}
                {" "}<span className={`px-2 py-0.5 rounded text-[11px] font-medium ${color}`}>{etiqueta}</span></p>
              <p className="text-xs text-ms-gray-90">{est.git ? <>Repositorio <code>{est.git}</code>{est.rama && <> · rama <code>{est.rama}</code></>}</> : <>Código subido por SFTP a la carpeta <code>{est.carpeta_servida || "app"}</code>.</>}
                {est.carpeta_servida && est.git && <> · se publica <code>{est.carpeta_servida}</code></>}{est.spa && " · una sola página"}</p>
              {est.puerto_publico && <p className="text-xs text-ms-gray-90">Puerto público {est.protocolo} {est.puerto_publico} (cortafuegos: {est.cortafuegos || "—"}).</p>}
            </div>
            {est.git && <AutenticacionGit dominio={dominio} repo={est.git} />}
            <div className="flex flex-wrap gap-2">
              {(est.git || servicio) && <button disabled={!!ocupado} onClick={() => accion("desplegar", est.git ? "Trayendo los cambios e instalando dependencias…" : "Instalando dependencias y reiniciando…")} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50" title={est.git ? "git pull, dependencias y reinicio" : "Dependencias (requirements.txt / package.json) y reinicio, tras subir cambios por SFTP"}>Desplegar</button>}
              {servicio && <>
                <button disabled={!!ocupado} onClick={() => accion("reiniciar", "Reiniciando…")} className={boton}>Reiniciar</button>
                {est.activo === "active" ? <button disabled={!!ocupado} onClick={() => accion("detener", "Deteniendo…")} className={boton}>Detener</button>
                  : <button disabled={!!ocupado} onClick={() => accion("iniciar", "Iniciando…")} className={boton}>Iniciar</button>}
              </>}
              <button disabled={!!ocupado} onClick={quitar} className="px-3 py-1.5 border border-ms-red text-ms-red rounded text-sm disabled:opacity-50 ml-auto">Quitar aplicación</button>
            </div>
            {servicio && (
              <div className="border-t border-ms-gray-30 pt-3 space-y-2">
                <h3 className="text-sm font-semibold">Variables de entorno</h3>
                <p className="text-xs text-ms-gray-90">Para claves de API, cadenas de conexión a la base de datos, etc. Los valores guardados no se muestran: déjelos vacíos para conservarlos. PORT, HOST y PUERTO_PUBLICO los pone el panel.</p>
                {vars.map((v, i) => (
                  <div key={i} className="flex gap-2">
                    <input value={v.clave} disabled={v.guardada} onChange={(e) => setVars(vars.map((x, j) => j === i ? { ...x, clave: e.target.value.toUpperCase() } : x))} placeholder="NOMBRE" className="w-56 px-2 py-1 border border-ms-gray-40 rounded text-sm font-mono disabled:bg-ms-gray-20" />
                    <input value={v.valor} type="password" autoComplete="new-password" onChange={(e) => setVars(vars.map((x, j) => j === i ? { ...x, valor: e.target.value } : x))} placeholder={v.guardada ? "•••••• (guardado)" : "valor"} className="flex-1 px-2 py-1 border border-ms-gray-40 rounded text-sm font-mono" />
                    <button onClick={() => setVars(vars.filter((_, j) => j !== i))} className="text-ms-red text-xs hover:underline">Quitar</button>
                  </div>
                ))}
                <div className="flex gap-2">
                  <button onClick={() => setVars([...vars, { clave: "", valor: "", guardada: false }])} className="text-ms-blue text-sm hover:underline">+ Variable</button>
                  <button disabled={!!ocupado} onClick={guardarVars} className={`${boton} ml-auto`}>Guardar y reiniciar</button>
                </div>
              </div>
            )}
            {servicio && (
              <div className="border-t border-ms-gray-30 pt-3 space-y-1">
                <div className="flex items-center"><h3 className="text-sm font-semibold">Registros</h3>
                  <button onClick={cargar} disabled={!!ocupado} className="text-ms-blue text-xs hover:underline ml-auto">Actualizar</button></div>
                <pre className="bg-ms-gray-130 text-white text-[11px] p-2 rounded max-h-64 overflow-auto whitespace-pre-wrap">{est.registros || "Sin registros todavía."}</pre>
              </div>
            )}
          </>
        )}
        {(ocupado || mensaje) && <p className="text-sm text-ms-gray-90 whitespace-pre-wrap">{ocupado || mensaje}</p>}
        <div className="text-right"><button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm">Cerrar</button></div>
      </div>
    </div>
  );
}
