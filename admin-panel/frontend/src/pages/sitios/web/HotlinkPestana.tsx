import { useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo, type EstadoWeb, type PropsPestana } from "./tipos";

const separar = (texto: string) => texto.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);

/* Protección contra hotlinking: otras páginas no pueden mostrar las imágenes del sitio gastando su tráfico. */
export function HotlinkPestana({ dominio, estado, ocupado, hacer }: PropsPestana) {
  const h = estado.hotlink;
  const [activo, setActivo] = useState(h.activo);
  const [extensiones, setExtensiones] = useState(h.extensiones.join(", "));
  const [permitidos, setPermitidos] = useState(h.permitidos.join("\n"));
  const [buscadores, setBuscadores] = useState(h.buscadores);

  const guardar = () => hacer(activo ? "Protección contra hotlinking activa." : "Protección contra hotlinking desactivada.", () =>
    api.put<EstadoWeb>(`/sitios/${dominio}/web/hotlink`, { activo, extensiones: separar(extensiones), permitidos: separar(permitidos), buscadores }));

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />Activar la protección</label>
      <p className="text-xs text-ms-gray-90">Con la protección activa, estos archivos solo se muestran dentro del propio sitio (y sus alias), en los dominios permitidos o al abrir el enlace directo. Desde otra página, el visitante recibe un error 403.</p>
      <label className="block text-xs text-ms-gray-90">Extensiones protegidas
        <input value={extensiones} onChange={(e) => setExtensiones(e.target.value)} className={`${campo} w-full font-mono`} />
      </label>
      <label className="block text-xs text-ms-gray-90">Otros dominios que sí pueden mostrarlos (uno por línea; «*.example.com» para todos sus subdominios)
        <textarea value={permitidos} onChange={(e) => setPermitidos(e.target.value)} rows={3} className={`${campo} w-full font-mono`} placeholder="example.com" />
      </label>
      <label className="flex items-center gap-2 text-xs text-ms-gray-90"><input type="checkbox" checked={buscadores} onChange={(e) => setBuscadores(e.target.checked)} />Permitir a los buscadores (vistas previas de imágenes en Google, Bing, DuckDuckGo…)</label>
      <button disabled={ocupado} onClick={guardar} className={botonPrincipal}>Guardar</button>
    </div>
  );
}
