import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface QueueMsg { queue_id: string; queue_name: string; arrival_time: number; message_size: number; sender: string; recipients: { address: string; delay_reason: string }[] }

export function Queue() {
  const [queue, setQueue] = useState<QueueMsg[]>([]);
  const [loading, setLoading] = useState(false);

  const load = () => { setLoading(true); api.get<QueueMsg[]>("/queue").then(setQueue).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const action = async (act: string, qid?: string) => {
    if (act === "delete_all") {
      if (!confirm("PRECAUCION EXTREMA: Esto eliminara TODOS los correos en cola permanentemente. Ningun destinatario los recibira. Solo usar en emergencias. Continuar?")) return;
    } else if (act.includes("all")) {
      if (!confirm("Aplicar a TODOS los mensajes en cola? Se registra en auditoria.")) return;
    } else if (act === "delete") {
      if (!confirm("PRECAUCION: Eliminar este correo de la cola permanentemente? El destinatario NO lo recibira. Se registra en auditoria.")) return;
    }
    await api.post("/queue/action", { action: act, queue_id: qid });
    load();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130" title="Gestion de la cola de correos de Postfix. Muestra correos pendientes de envio.">Colas de correo ({queue.length})</h1>
        <div className="flex gap-2">
          <button onClick={load} title="Recarga la lista de correos en cola. Solo lectura, no modifica nada." className="px-3 py-1.5 border border-ms-gray-40 rounded text-xs text-ms-gray-130 hover:bg-ms-gray-20">Actualizar</button>
          <button onClick={() => action("flush_all")} title="Forzar envio: Reintenta enviar TODOS los correos en cola inmediatamente. Util si hubo un problema temporal. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-xs hover:bg-ms-blue-dark">Flush todo</button>
          <button onClick={() => action("requeue_all")} title="Reencola todos los mensajes para reprocesarlos. Util para aplicar cambios de configuración. Se registra en auditoria." className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-xs hover:bg-ms-blue-lighter">Requeue todo</button>
          <button onClick={() => action("delete_all")} title="PRECAUCION EXTREMA: Elimina TODOS los correos en cola. Ningun destinatario los recibira. Solo usar en emergencias. Se registra en auditoria." className="px-3 py-1.5 bg-ms-red text-white rounded text-xs hover:bg-red-700">Eliminar todo</button>
          <SectionHelp
            titulo="Colas de correo"
            items={[
              { titulo: "Para qué sirve", desc: "Muestra los correos que Postfix aún no ha podido entregar y siguen esperando en la cola. Si la cola está vacía, todo el correo fluye con normalidad." },
              { titulo: "Columnas", desc: "Queue ID (identificador del mensaje en Postfix), remitente, destinatarios, razón del retraso (por qué no se ha entregado), y tamaño del mensaje." },
              { titulo: "Flush", desc: "Fuerza un reintento de envío inmediato, de un correo o de toda la cola. Es la acción segura de primera opción cuando hubo un problema temporal (DNS, destino caído)." },
              { titulo: "Hold y Requeue", desc: "Hold retiene un correo para que no se envíe hasta liberarlo. Requeue todo reencola los mensajes para reprocesarlos, útil tras cambiar la configuración de Postfix." },
              { titulo: "Eliminar", desc: "Descarta el correo definitivamente: el destinatario nunca lo recibirá y no hay forma de recuperarlo. Usar solo en emergencias (spam masivo, cola atascada)." },
              { titulo: "Auditoría", desc: "Todas las acciones sobre la cola quedan registradas en auditoría con usuario y fecha." },
            ]}
          />
        </div>
      </div>

      {queue.length === 0 ? (
        <div className="bg-white rounded border border-ms-gray-30 p-12 text-center text-ms-gray-60">Cola vacia - todos los correos han sido entregados</div>
      ) : (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Queue ID</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Remitente</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Destinatario</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Razon</th>
              <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Tamano</th>
              <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
            </tr></thead>
            <tbody className="divide-y divide-ms-gray-30">
              {queue.map((m) => (
                <tr key={m.queue_id} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2.5 font-mono text-xs text-ms-gray-130">{m.queue_id}</td>
                  <td className="px-4 py-2.5 text-xs text-ms-gray-130">{m.sender}</td>
                  <td className="px-4 py-2.5 text-xs text-ms-gray-130">{m.recipients.map((r) => r.address).join(", ")}</td>
                  <td className="px-4 py-2.5 text-xs text-ms-red max-w-[200px] truncate">{m.recipients[0]?.delay_reason || "-"}</td>
                  <td className="px-4 py-2.5 text-right text-xs text-ms-gray-60">{(m.message_size / 1024).toFixed(0)} KB</td>
                  <td className="px-4 py-2.5 text-right space-x-1">
                    <button onClick={() => action("flush", m.queue_id)} title="Reintenta enviar este correo inmediatamente. Util si hubo un problema temporal. Se registra en auditoria." className="text-ms-blue text-xs hover:underline">Flush</button>
                    <button onClick={() => action("hold", m.queue_id)} title="Retiene este correo en la cola. No se enviara hasta que se libere manualmente. Se registra en auditoria." className="text-yellow-600 text-xs hover:underline">Hold</button>
                    <button onClick={() => action("delete", m.queue_id)} title="PRECAUCION: Elimina el correo de la cola permanentemente. El destinatario NO lo recibira. Se registra en auditoria." className="text-ms-red text-xs hover:underline">Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
