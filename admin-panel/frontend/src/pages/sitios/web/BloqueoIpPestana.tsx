import { useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo, type EstadoWeb, type PropsPestana } from "./tipos";

/* IP bloqueadas solo en este sitio (el bloqueo de todo el servidor sigue en Seguridad → Cortafuegos). */
export function BloqueoIpPestana({ dominio, estado, ocupado, hacer }: PropsPestana) {
  const [texto, setTexto] = useState(estado.bloqueo.lista.join("\n"));
  const redes = texto.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);

  return (
    <div className="space-y-3">
      <p className="text-xs text-ms-gray-90">Direcciones o redes que reciben un error 403 en este sitio y solo en este: para cortar a quien abusa de un formulario o copia el contenido, sin tocar el correo ni los demás sitios. IPv4 o IPv6, una por línea; una red con su máscara (p. ej. <code>198.51.100.0/24</code> o <code>2001:db8::/32</code>).</p>
      <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={8} spellCheck={false} placeholder={"192.0.2.15\n203.0.113.0/24"} className={`${campo} w-full font-mono`} />
      <div className="flex items-center gap-3">
        <button disabled={ocupado} onClick={() => hacer(redes.length ? `${redes.length} IP o redes bloqueadas en ${dominio}.` : "Sin IP bloqueadas.", () => api.put<EstadoWeb>(`/sitios/${dominio}/web/bloqueo`, { redes }))} className={botonPrincipal}>Guardar</button>
        <span className="text-[11px] text-ms-gray-60">{redes.length} de {estado.bloqueo.maximo} como máximo</span>
      </div>
    </div>
  );
}
