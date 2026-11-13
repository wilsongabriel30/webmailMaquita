/**
 * Bloqueos por escribir a muchas personas a la vez (vigilante de envío masivo), dentro de
 * «Alertas de seguridad»: qué pasó, a quién iba el correo y la decisión, en lenguaje llano.
 *   · «Es correcto»: se le permite escribir a esas listas y la cuenta se reactiva.
 *   · «Reactivar la cuenta»: fue suyo, sin dar permisos.
 *   · «Dejar bloqueada»: se marca como revisado y la cuenta queda como está.
 */
import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface Destino { lista: string; destinatarios: number; es_lista: boolean; autorizada: boolean; }
export interface Envio {
  id: number; cuenta: string; nombre: string; cuando: string; destinatarios: number; mensajes: number;
  destinos: Destino[]; activa: boolean; existe: boolean; atendido: string | null; atendido_por: string;
  resolucion: string; titulo: string; que_paso: string; que_hacer: string; estado: string; listas_por_autorizar: string[];
}
interface Permiso { id: number; username: string; lista: string; creado_por: string; creado: string; }

const fecha = (t: string) => new Date(t).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" });
const RESOLUCION: Record<string, string> = { autorizado: "Se permitió y se reactivó", reactivado: "Se reactivó sin dar permisos", sin_cambios: "Revisado, sin cambios" };

export function EnviosMasivos({ envios, alCambiar, avisar }: { envios: Envio[]; alCambiar: () => void; avisar: (ok: boolean, texto: string) => void }) {
  const [ocupado, setOcupado] = useState(0);
  const [permisos, setPermisos] = useState<Permiso[]>([]);
  const [verPermisos, setVerPermisos] = useState(false);

  const cargarPermisos = () => api.get<{ permisos: Permiso[] }>("/alertas-seguridad/envios/permisos").then((r) => setPermisos(r.permisos)).catch(() => setPermisos([]));
  useEffect(() => { cargarPermisos(); }, [envios.length]);

  const hacer = async (e: Envio, accion: "autorizar" | "reactivar" | "mantener", pregunta: string, hecho: string) => {
    if (!window.confirm(pregunta)) return;
    setOcupado(e.id);
    try {
      await api.post(`/alertas-seguridad/envios/${e.id}/${accion}`, accion === "autorizar" ? { listas: e.listas_por_autorizar } : {});
      avisar(true, hecho);
      alCambiar();
      cargarPermisos();
    } catch (err: any) { avisar(false, err?.message || "No se pudo completar"); }
    setOcupado(0);
  };

  const quitar = async (p: Permiso) => {
    if (!window.confirm(`Quitar el permiso de ${p.username} para escribir a ${p.lista}.\n\nSi vuelve a escribir a esa lista y supera el límite, su cuenta se bloqueará.`)) return;
    try { await api.del(`/alertas-seguridad/envios/permisos/${p.id}`); avisar(true, "Permiso quitado."); cargarPermisos(); alCambiar(); }
    catch (err: any) { avisar(false, err?.message || "No se pudo quitar el permiso"); }
  };

  if (envios.length === 0 && permisos.length === 0) return null;
  return (
    <section className="mb-6">
      <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Cuentas bloqueadas por escribir a muchas personas</h2>
      <div className="space-y-3">
        {envios.map((e) => {
          const listas = e.listas_por_autorizar.join(" y ");
          return (
            <div key={e.id} className={`bg-white border rounded-lg p-4 ${e.atendido ? "border-ms-gray-30 opacity-75" : "border-amber-300"}`}>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs rounded px-2 py-0.5 ${e.atendido ? "bg-green-100 text-green-700" : e.activa ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-700"}`}>
                  {e.atendido ? "REVISADO" : e.activa ? "POR REVISAR" : "CUENTA BLOQUEADA"}
                </span>
                <span className="text-sm font-semibold text-ms-gray-160">{e.cuenta}</span>
                <span className="text-xs text-ms-gray-110">{fecha(e.cuando)}</span>
              </div>
              <p className="text-sm font-medium text-ms-gray-160 mt-2">{e.titulo}</p>
              <p className="text-sm text-ms-gray-130 mt-1">{e.que_paso}</p>
              {e.atendido
                ? <p className="text-xs text-ms-gray-110 mt-2">{RESOLUCION[e.resolucion] || "Revisado"} · {e.atendido_por} · {fecha(e.atendido)}</p>
                : <p className="text-sm text-ms-gray-160 mt-1"><b>Qué hacer:</b> {e.que_hacer}</p>}
              {!e.atendido && e.existe && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {e.listas_por_autorizar.length > 0 && (
                    <button disabled={ocupado === e.id} onClick={() => hacer(e, "autorizar",
                      `Permitir que ${e.cuenta} escriba a ${listas}${e.activa ? "" : " y reactivar su cuenta"}.\n\nNo se le volverá a bloquear por escribir a esas listas. El permiso se puede quitar después en esta misma pantalla.`,
                      `Listo: ${e.cuenta} ya puede escribir a ${listas}${e.activa ? "" : " y su cuenta está activa"}.`)}
                      className="px-3 py-2 bg-ms-blue text-white rounded text-xs disabled:opacity-50">
                      Es correcto: permitir{e.activa ? "" : " y reactivar"}
                    </button>
                  )}
                  {!e.activa && (
                    <button disabled={ocupado === e.id} onClick={() => hacer(e, "reactivar",
                      `Reactivar la cuenta de ${e.cuenta} sin darle ningún permiso.\n\nSi vuelve a escribir a tantas personas, se bloqueará otra vez.`,
                      `La cuenta de ${e.cuenta} está activa otra vez.`)}
                      className="px-3 py-2 border border-ms-gray-60 text-ms-gray-160 rounded text-xs disabled:opacity-50">
                      Reactivar la cuenta
                    </button>
                  )}
                  <button disabled={ocupado === e.id} onClick={() => hacer(e, "mantener",
                    e.activa ? `Marcar como revisado el aviso de ${e.cuenta}.` : `Dejar bloqueada la cuenta de ${e.cuenta}.\n\nÚselo si la persona no reconoce el envío: cambie su contraseña antes de reactivarla.`,
                    e.activa ? "Aviso marcado como revisado." : `La cuenta de ${e.cuenta} sigue bloqueada. Cambie su contraseña antes de reactivarla.`)}
                    className="px-3 py-2 border border-ms-gray-60 text-ms-gray-130 rounded text-xs disabled:opacity-50">
                    {e.activa ? "Marcar como revisado" : "No fue esa persona: dejar bloqueada"}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {permisos.length > 0 && (
        <div className="mt-3">
          <button onClick={() => setVerPermisos(!verPermisos)} aria-expanded={verPermisos} className="text-xs text-ms-blue">
            {verPermisos ? "Ocultar" : "Ver"} los {permisos.length} permisos concedidos para escribir a listas
          </button>
          {verPermisos && (
            <table className="w-full text-xs mt-2 bg-white border border-ms-gray-30 rounded">
              <thead><tr className="text-left text-ms-gray-110"><th className="p-2">Cuenta</th><th>Puede escribir a</th><th>Lo concedió</th><th>Cuándo</th><th></th></tr></thead>
              <tbody>{permisos.map((p) => (
                <tr key={p.id} className="border-t border-ms-gray-10"><td className="p-2">{p.username}</td><td>{p.lista}</td><td>{p.creado_por}</td><td>{fecha(p.creado)}</td>
                  <td className="text-right pr-2"><button onClick={() => quitar(p)} className="text-red-600 hover:underline">Quitar</button></td></tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
