import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

/**
 * Reenvio de correos rebotados.
 *
 * Cuando un correo no se puede entregar, el servidor lo devuelve al remitente y el mensaje
 * desaparece de la cola: ya no sirve "reintentar". Esta pantalla recupera el original
 * (del propio rebote o de la carpeta Enviados) y lo vuelve a enviar SOLO a los
 * destinatarios que fallaron, sin duplicarlo a quienes si lo recibieron.
 */

interface CuentaConRebotes { cuenta: string; rebotes: number }

interface Rebote {
  uid_rebote: string;
  message_id: string;
  asunto: string;
  fecha_original: string;
  destinatarios_fallidos: string[];
  motivo: string;
  trae_copia: boolean;
  reenviable: boolean;
}

export function Rebotados() {
  const [cuentas, setCuentas] = useState<CuentaConRebotes[]>([]);
  const [cuenta, setCuenta] = useState("");
  const [busqueda, setBusqueda] = useState("");     // permite escribir una cuenta a mano
  const [rebotes, setRebotes] = useState<Rebote[]>([]);
  const [cargando, setCargando] = useState(false);
  const [aviso, setAviso] = useState("");

  // Cuentas con rebotes recientes (se sacan del log del servidor, es barato).
  useEffect(() => {
    api.get<CuentaConRebotes[]>("/resend/cuentas").then(setCuentas).catch(() => {});
  }, []);

  const cargarRebotes = (dir: string) => {
    if (!dir) return;
    setCuenta(dir);
    setCargando(true);
    setAviso("");
    api.get<Rebote[]>(`/resend/rebotes/${encodeURIComponent(dir)}?dias=15`)
      .then(setRebotes)
      .catch((e) => { setRebotes([]); setAviso(`No se pudieron leer los rebotes: ${e}`); })
      .finally(() => setCargando(false));
  };

  const reenviar = async (r: Rebote) => {
    const destinos = r.destinatarios_fallidos.join(", ");
    if (!confirm(
      `Reenviar "${r.asunto}"\n\nSe enviara de nuevo a:\n${destinos}\n\n` +
      `El correo saldra tal cual lo escribio ${cuenta} (mismo asunto, cuerpo y adjuntos).\n` +
      `Solo se envia a los destinatarios que fallaron. Queda registrado en la auditoria.\n\nContinuar?`
    )) return;

    try {
      await api.post("/resend/enviar", {
        cuenta,
        uid_rebote: r.uid_rebote,
        message_id: r.message_id,
        destinatarios: r.destinatarios_fallidos,
      });
      setAviso(`Reenviado a ${destinos}`);
    } catch (e) {
      setAviso(`No se pudo reenviar: ${e}`);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130"
            title="Recupera correos que el servidor devolvio al remitente y los vuelve a enviar.">
          Correos rebotados {rebotes.length > 0 && `(${rebotes.length})`}
        </h1>
      </div>

      <SectionHelp
        titulo="¿Cómo funciona esta sección?"
        items={[
          { titulo: "Qué es un correo rebotado", desc: "El servidor intentó entregarlo durante días, no pudo y se lo devolvió al remitente. Ya no está en la cola, así que 'reintentar' no sirve: hay que volver a enviarlo." },
          { titulo: "De dónde sale el mensaje", desc: "Se recupera el original del propio rebote (que suele traerlo adjunto) o, si no, de la carpeta Enviados del remitente. Se reenvía tal cual: mismo remitente, asunto, cuerpo, adjuntos e hilo de conversación." },
          { titulo: "A quién se le reenvía", desc: "Solo a los destinatarios que fallaron. Quien sí lo recibió la primera vez no recibe un duplicado." },
          { titulo: "Cuándo usarla", desc: "Después de corregir la causa del fallo (por ejemplo, un problema de entrega con el servidor del destinatario). Cada reenvío queda registrado en la auditoría del panel." },
          { titulo: "No recuperable", desc: "Aparece cuando el rebote no trae copia del mensaje y tampoco está en Enviados. Es típico de cuentas que envían desde un sistema externo, como el ERP: ahí hay que regenerar el correo en ese sistema." },
        ]}
      />

      {/* Seleccion de cuenta: sugeridas por el log, o escrita a mano */}
      <div className="flex flex-wrap gap-2 items-center">
        <select
          className="border rounded px-3 py-2 text-sm"
          value={cuenta}
          onChange={(e) => cargarRebotes(e.target.value)}
        >
          <option value="">Cuentas con rebotes recientes...</option>
          {cuentas.map((c) => (
            <option key={c.cuenta} value={c.cuenta}>{c.cuenta} ({c.rebotes})</option>
          ))}
        </select>

        <input
          className="border rounded px-3 py-2 text-sm w-72"
          placeholder="...o escribir una cuenta y buscar"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") cargarRebotes(busqueda.trim()); }}
        />
        <button
          className="px-3 py-2 text-sm rounded bg-ms-blue text-white"
          onClick={() => cargarRebotes(busqueda.trim() || cuenta)}
        >
          Buscar rebotes
        </button>
        {cargando && <span className="text-sm text-gray-500">Leyendo el buzon...</span>}
      </div>

      {aviso && <div className="text-sm p-3 rounded bg-gray-50 border">{aviso}</div>}

      {rebotes.length > 0 && (
        <table className="w-full text-sm border">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-2">Asunto</th>
              <th className="text-left p-2">Fecha original</th>
              <th className="text-left p-2">No le llego a</th>
              <th className="text-left p-2">Motivo</th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rebotes.map((r) => (
              <tr key={r.uid_rebote} className="border-t align-top">
                <td className="p-2">{r.asunto || "(sin asunto)"}</td>
                <td className="p-2 whitespace-nowrap">{r.fecha_original}</td>
                <td className="p-2">{r.destinatarios_fallidos.join(", ")}</td>
                <td className="p-2 text-gray-600">{r.motivo}</td>
                <td className="p-2 text-right">
                  {r.reenviable ? (
                    <button
                      className="px-3 py-1 rounded bg-ms-blue text-white"
                      onClick={() => reenviar(r)}
                    >
                      Reenviar
                    </button>
                  ) : (
                    <span className="text-xs text-gray-500"
                          title="El rebote no trae copia del mensaje y no esta en Enviados (tipico de cuentas que envian desde un sistema externo, como el ERP).">
                      No recuperable
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!cargando && cuenta && rebotes.length === 0 && (
        <div className="text-sm text-gray-500">Sin rebotes en los ultimos 15 dias para {cuenta}.</div>
      )}
    </div>
  );
}
