import { useState } from "react";
import { campo, MOTOR, type EstadoRemoto, type UsuarioBase } from "./tipos";

/* Acceso remoto de un usuario de base: IP o redes permitidas, siempre con TLS. Una red más amplia que /16 (IPv4) o
   /48 (IPv6) solo la acepta el servidor si el superadministrador lo confirma; a todo Internet (/0), nunca. */
export function AccesoRemoto({ u, remoto, maximo, ocupado, onGuardar, onCancelar }: {
  u: UsuarioBase; remoto: EstadoRemoto; maximo: number; ocupado: boolean;
  onGuardar: (redes: string[], confirmarAmplia: boolean) => void; onCancelar: () => void;
}) {
  const [texto, setTexto] = useState(u.remoto.join("\n"));
  const [amplia, setAmplia] = useState(false);
  const preparado = remoto[u.motor]?.activo;
  const redes = texto.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);
  return (
    <div className="border border-ms-gray-30 rounded p-3 space-y-2 bg-ms-gray-10">
      <h4 className="text-sm font-semibold">Acceso remoto de <code>{u.usuario}</code></h4>
      {!preparado && (
        <p className="text-xs bg-amber-50 border border-amber-200 rounded p-2">
          El acceso remoto a {MOTOR[u.motor]} todavía no está preparado en este servidor (TLS con el certificado del servidor y
          escucha en la red). Aplique el ajuste 72: <code>sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar</code>.
        </p>
      )}
      <p className="text-xs text-ms-gray-90">
        Una IP o red por línea (hasta {maximo}), p. ej. <code>192.0.2.10</code> o <code>198.51.100.0/24</code>. Solo se entra con TLS
        {remoto.host ? <> a <code>{remoto.host}:{remoto[u.motor].puerto}</code></> : null}; el puerto se abre en el cortafuegos solo para estas IP.
        {u.motor === "mariadb" && " MariaDB no admite redes IPv6: solo direcciones sueltas."} Vacío: solo desde este servidor.
      </p>
      <textarea className={`${campo} w-full font-mono`} rows={4} value={texto} onChange={(e) => setTexto(e.target.value)} />
      <label className="flex items-start gap-2 text-xs">
        <input type="checkbox" checked={amplia} onChange={(e) => setAmplia(e.target.checked)} />
        <span>Confirmo una red más amplia que /16 (IPv4) o /48 (IPv6). Solo vale para el superadministrador con segundo factor; a todo Internet no se abre nunca.</span>
      </label>
      <div className="flex gap-2">
        <button disabled={ocupado || (!preparado && redes.length > 0) || redes.length > maximo} onClick={() => onGuardar(redes, amplia)}
          className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Guardar</button>
        <button onClick={onCancelar} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm">Cancelar</button>
      </div>
    </div>
  );
}
