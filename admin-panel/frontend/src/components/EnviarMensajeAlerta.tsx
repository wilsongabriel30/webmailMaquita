/**
 * Botón «Enviar mensaje» de una alerta de «Alertas de seguridad»: escribe a la persona cuya cuenta
 * tiene intentos fallidos repetidos desde un celular u otro programa de correo.
 * Abre un cuadro con el mensaje ya redactado (asunto y texto, editables) y el destinatario fijo.
 * Debajo del botón queda «Mensaje enviado el … por …». Si ya se le escribió en las últimas
 * 24 horas, pide confirmación antes de enviar otro (el servidor también lo exige).
 */
import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface MensajeAlerta {
  se_puede_enviar: boolean; asunto: string; cuerpo: string;
  enviado: string | null; enviado_por: string; reciente: boolean;
}

const fecha = (t: string) => new Date(t).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" });

export function EnviarMensajeAlerta({ cuenta, mensaje, alCambiar, avisar }: { cuenta: string; mensaje?: MensajeAlerta; alCambiar: () => void; avisar: (ok: boolean, texto: string) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [asunto, setAsunto] = useState("");
  const [cuerpo, setCuerpo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!abierto) return;
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape" && !enviando) setAbierto(false); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierto, enviando]);

  if (!mensaje) return null;
  const enviado = mensaje.enviado ? `Mensaje enviado el ${fecha(mensaje.enviado)} por ${mensaje.enviado_por}` : "";
  if (!mensaje.se_puede_enviar) return enviado ? <p className="text-xs text-ms-gray-110 mt-2">{enviado}</p> : null;

  const abrir = () => { setAsunto(mensaje.asunto); setCuerpo(mensaje.cuerpo); setError(""); setAbierto(true); };

  const enviar = async () => {
    if (!asunto.trim() || !cuerpo.trim()) { setError("Escriba el asunto y el texto del mensaje."); return; }
    if (mensaje.reciente && !window.confirm(`Ya se envió un mensaje a ${cuenta} el ${fecha(mensaje.enviado || "")} (lo envió ${mensaje.enviado_por}).\n\n¿Quiere enviarle otro?`)) return;
    setEnviando(true); setError("");
    try {
      await api.post("/alertas-seguridad/mensajes", { cuenta, asunto, cuerpo, confirmar: mensaje.reciente });
      setAbierto(false);
      avisar(true, `Mensaje enviado a ${cuenta}.`);
      alCambiar();
    } catch (e) { setError(e instanceof Error && e.message ? e.message : "No se pudo enviar el mensaje"); }
    setEnviando(false);
  };

  return (
    <div className="mt-2 flex items-center gap-3 flex-wrap">
      <button onClick={abrir} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-xs hover:bg-ms-blue hover:text-white" title="Abre un mensaje ya redactado para la persona: que revise la contraseña guardada en su celular. Puede corregirlo antes de enviarlo.">Enviar mensaje</button>
      {enviado && <span className="text-xs text-ms-gray-110">{enviado}</span>}
      {abierto && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => { if (!enviando) setAbierto(false); }}>
          <div role="dialog" aria-modal="true" aria-label={`Mensaje para ${cuenta}`} className="bg-white rounded border border-ms-gray-30 w-full max-w-2xl max-h-[92vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-ms-gray-160">Mensaje para la persona</h3>
            <p className="text-xs text-ms-gray-110 mt-1 mb-3">Revise el texto y corríjalo si hace falta. Se envía solo a esta cuenta y queda registrado quién lo envió.</p>
            {mensaje.reciente && <div className="text-xs mb-3 px-3 py-2 rounded bg-amber-50 text-amber-800">Ya se le escribió el {fecha(mensaje.enviado || "")} (lo envió {mensaje.enviado_por}). Al enviar se le pedirá confirmar.</div>}
            <label className="block text-xs text-ms-gray-110 mb-1">Para</label>
            <input type="text" value={cuenta} readOnly title="El destinatario es la cuenta de la alerta y no se puede cambiar." className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm bg-ms-gray-10 text-ms-gray-130 mb-3" />
            <label className="block text-xs text-ms-gray-110 mb-1" htmlFor={`asunto-${cuenta}`}>Asunto</label>
            <input id={`asunto-${cuenta}`} type="text" value={asunto} maxLength={150} onChange={(e) => setAsunto(e.target.value)} className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue mb-3" />
            <label className="block text-xs text-ms-gray-110 mb-1" htmlFor={`cuerpo-${cuenta}`}>Mensaje</label>
            <textarea id={`cuerpo-${cuenta}`} value={cuerpo} maxLength={4000} rows={16} onChange={(e) => setCuerpo(e.target.value)} className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            {error && <div className="text-sm mt-3 px-3 py-2 rounded bg-red-50 text-red-600">{error}</div>}
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setAbierto(false)} disabled={enviando} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90 disabled:opacity-50">Cancelar</button>
              <button onClick={enviar} disabled={enviando} className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">{enviando ? "Enviando…" : "Enviar"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
