/**
 * Bloqueos por escribir a muchas personas a la vez (vigilante de envío masivo), dentro de
 * «Alertas de seguridad»: qué pasó, a quién iba el correo y la decisión, en lenguaje llano.
 *   · «Es correcto»: se le permite escribir a esas listas y la cuenta se reactiva.
 *   · «Reactivar la cuenta»: fue suyo, sin dar permisos.
 *   · «Dejar bloqueada»: se marca como revisado y la cuenta queda como está.
 * Debajo, «Permisos para escribir a listas»: darlos por adelantado (sin esperar a un bloqueo) y quitarlos.
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
interface Lista { address: string; name: string; miembros: number; }

const fecha = (t: string) => new Date(t).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" });
const RESOLUCION: Record<string, string> = { autorizado: "Se permitió y se reactivó", reactivado: "Se reactivó sin dar permisos", sin_cambios: "Revisado, sin cambios" };

export function EnviosMasivos({ envios, alCambiar, avisar }: { envios: Envio[]; alCambiar: () => void; avisar: (ok: boolean, texto: string) => void }) {
  const [ocupado, setOcupado] = useState(0);
  const [permisos, setPermisos] = useState<Permiso[]>([]);
  const [listas, setListas] = useState<Lista[]>([]);
  const [umbral, setUmbral] = useState(0);
  const [cuenta, setCuenta] = useState("");
  const [lista, setLista] = useState("");

  const cargarPermisos = () => api.get<{ permisos: Permiso[] }>("/alertas-seguridad/envios/permisos").then((r) => setPermisos(r.permisos)).catch(() => setPermisos([]));
  useEffect(() => { cargarPermisos(); }, [envios.length]);
  useEffect(() => {
    api.get<{ listas: Lista[]; umbral: number }>("/alertas-seguridad/envios/listas").then((r) => { setListas(r.listas); setUmbral(r.umbral); }).catch(() => setListas([]));
  }, []);

  const darPermiso = async () => {
    const quien = cuenta.trim().toLowerCase();
    if (!quien.includes("@") || !lista) { avisar(false, "Escriba la dirección completa de la persona y elija una lista."); return; }
    try {
      await api.post("/alertas-seguridad/envios/permisos", { cuenta: quien, listas: [lista] });
      avisar(true, `Listo: ${quien} ya puede escribir a ${lista} sin que se bloquee su cuenta.`);
      setCuenta(""); setLista("");
      cargarPermisos(); alCambiar();
    } catch (err: any) { avisar(false, err?.message || "No se pudo dar el permiso"); }
  };

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

  if (envios.length === 0 && listas.length === 0) return null;
  return (
    <section className="mb-6">
      {envios.length > 0 && <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Cuentas bloqueadas por escribir a muchas personas</h2>}
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
      {listas.length > 0 && (
        <div className="mt-4 bg-white border border-ms-gray-30 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-ms-gray-160">Permisos para escribir a listas</h3>
          <p className="text-xs text-ms-gray-110 mt-1">
            El sistema bloquea una cuenta que escribe a {umbral > 0 ? `${umbral} personas de fuera o más` : "demasiadas personas de fuera"} en pocos minutos. El correo entre cuentas de la casa
            no cuenta. Si alguien necesita escribir a una lista que tiene miembros de fuera (proveedores, gestorías externas…), dele aquí el permiso <b>antes</b> de que envíe:
            no se le bloqueará por esa lista. El permiso es permanente hasta que se quite y no cambia quién puede escribir a la lista.
          </p>
          <div className="flex flex-wrap items-end gap-2 mt-3">
            <label className="text-xs text-ms-gray-130">Persona (su correo)
              <input value={cuenta} onChange={(ev) => setCuenta(ev.target.value)} placeholder="nombre@dominio" type="email"
                className="block mt-1 w-64 border border-ms-gray-60 rounded px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-ms-gray-130">Puede escribir a la lista
              <select value={lista} onChange={(ev) => setLista(ev.target.value)} className="block mt-1 w-72 border border-ms-gray-60 rounded px-2 py-1.5 text-sm bg-white">
                <option value="">Elija una lista…</option>
                {listas.map((l) => <option key={l.address} value={l.address}>{l.address} ({l.miembros} {l.miembros === 1 ? "persona" : "personas"})</option>)}
              </select>
            </label>
            <button onClick={darPermiso} className="px-3 py-2 bg-ms-blue text-white rounded text-xs">Dar permiso</button>
          </div>
          {permisos.length === 0
            ? <p className="text-xs text-ms-gray-110 mt-3">Todavía no se ha dado ningún permiso.</p>
            : (
              <table className="w-full text-xs mt-3">
                <thead><tr className="text-left text-ms-gray-110"><th className="py-1">Persona</th><th>Puede escribir a</th><th>Lo concedió</th><th>Cuándo</th><th></th></tr></thead>
                <tbody>{permisos.map((p) => (
                  <tr key={p.id} className="border-t border-ms-gray-10"><td className="py-1">{p.username}</td><td>{p.lista}</td><td>{p.creado_por}</td><td>{fecha(p.creado)}</td>
                    <td className="text-right"><button onClick={() => quitar(p)} className="text-red-600 hover:underline">Quitar</button></td></tr>
                ))}</tbody>
              </table>
            )}
        </div>
      )}
    </section>
  );
}
