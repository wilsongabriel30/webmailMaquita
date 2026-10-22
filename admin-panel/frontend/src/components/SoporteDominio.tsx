import { useState } from "react";
import { api } from "../api/client";

// «Entrar como soporte»: vale de un solo uso para abrir el portal de dominio (8444) como el cliente,
// sin su contraseña ni su segundo factor. Solo lectura salvo que se elija «con acciones».
interface Props { dominio: string; onCerrar: () => void }
interface Vale { url: string; modo: string; valido_segundos: number }

export function SoporteDominio({ dominio, onCerrar }: Props) {
  const [modo, setModo] = useState<"solo_lectura" | "con_acciones">("solo_lectura");
  const [motivo, setMotivo] = useState("");
  const [vale, setVale] = useState<Vale | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const pedir = async () => {
    setOcupado(true); setError("");
    try { setVale(await api.post<Vale>("/admins-dominio/soporte", { dominio, modo, motivo })); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo crear el vale"); }
    setOcupado(false);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 overflow-auto py-10" onClick={onCerrar}>
      <div className="bg-white rounded border border-ms-gray-30 p-5 w-[28rem] max-w-[94vw] space-y-3" onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-label={`Entrar como soporte a ${dominio}`}>
        <h2 className="text-base font-semibold text-ms-gray-130">Entrar como soporte a {dominio}</h2>
        <p className="text-xs text-ms-gray-60">Abre el portal de este dominio como lo ve su administrador, sin conocer su contraseña ni su segundo factor. La sesión dura poco, se ve marcada como soporte y queda en la auditoría del dominio.</p>
        {!vale ? (
          <>
            <label className="flex items-start gap-2 text-sm"><input type="radio" checked={modo === "solo_lectura"} onChange={() => setModo("solo_lectura")} className="mt-1" />
              <span><b>Solo lectura</b> (recomendado): ver sin poder cambiar nada.</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="radio" checked={modo === "con_acciones"} onChange={() => setModo("con_acciones")} className="mt-1" />
              <span><b>Con acciones</b>: permite cambiar; cada acción queda auditada como del soporte.</span></label>
            <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={255} placeholder="Motivo (p. ej. número de incidencia)"
              className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            {error && <div className="text-ms-red text-sm">{error}</div>}
            <div className="flex justify-end gap-2">
              <button onClick={onCerrar} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
              <button onClick={pedir} disabled={ocupado} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Crear enlace de soporte</button>
            </div>
          </>
        ) : (
          <>
            <div className={`text-xs rounded px-2 py-1 ${vale.modo === "solo_lectura" ? "bg-yellow-50 text-yellow-800" : "bg-red-50 text-ms-red"}`}>
              {vale.modo === "solo_lectura" ? "Solo lectura" : "Con acciones (auditadas)"} · un solo uso · válido {Math.round(vale.valido_segundos / 60)} min</div>
            <a href={vale.url} target="_blank" rel="noopener noreferrer" onClick={() => setTimeout(onCerrar, 300)}
              className="block w-full py-2.5 text-center bg-ms-blue hover:bg-ms-blue-dark text-white font-medium rounded text-sm">Abrir el portal como soporte</a>
            <p className="text-[11px] text-ms-gray-60">El enlace deja de valer al usarse. Si lo necesita otra persona, cree otro.</p>
          </>
        )}
      </div>
    </div>
  );
}
