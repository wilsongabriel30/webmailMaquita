import { useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo, type EstadoWeb, type PropsPestana } from "./tipos";

type Respuesta = EstadoWeb & { carpeta: string; usuario: string; clave?: string };

/* Carpetas con usuario y contraseña (autenticación básica). La contraseña generada se muestra una sola vez. */
export function PrivacidadPestana({ dominio, estado, ocupado, hacer, onClave }: PropsPestana & { onClave: (carpeta: string, usuario: string, clave: string) => void }) {
  const carpetas = estado.privacidad.carpetas;
  const [carpeta, setCarpeta] = useState("");
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [propia, setPropia] = useState(false);

  const agregar = (ruta: string, nombre: string, secreto?: string) => hacer(`Acceso de ${nombre} a ${ruta} guardado.`, async () => {
    const r = await api.post<Respuesta>(`/sitios/${dominio}/web/privacidad`, { carpeta: ruta, usuario: nombre, clave: secreto || null });
    if (r.clave) onClave(r.carpeta, r.usuario, r.clave);
    return r;
  });
  const quitar = (ruta: string, nombre?: string) => {
    if (!confirm(nombre ? `¿Quitar el acceso de ${nombre} a ${ruta}?` : `¿Quitar la contraseña de ${ruta}? La carpeta volverá a ser pública.`)) return;
    const consulta = `carpeta=${encodeURIComponent(ruta)}${nombre ? `&usuario=${encodeURIComponent(nombre)}` : ""}`;
    hacer(nombre ? "Acceso quitado." : "La carpeta ya no pide contraseña.", () => api.del<EstadoWeb>(`/sitios/${dominio}/web/privacidad?${consulta}`));
  };
  const enviar = async () => {
    if (await agregar(carpeta.trim(), usuario.trim(), propia ? clave : undefined)) { setUsuario(""); setClave(""); }
  };

  return (
    <div className="space-y-3">
      <div className="border border-ms-gray-30 rounded p-3 space-y-2">
        <b className="text-sm">Proteger una carpeta o añadir un usuario</b>
        <div className="flex flex-wrap items-center gap-2">
          <input placeholder="/privado" value={carpeta} onChange={(e) => setCarpeta(e.target.value)} className={`${campo} font-mono w-48`} />
          <input placeholder="usuario" value={usuario} onChange={(e) => setUsuario(e.target.value)} className={`${campo} w-40`} autoComplete="off" />
          <label className="text-xs text-ms-gray-90"><input type="checkbox" checked={propia} onChange={(e) => setPropia(e.target.checked)} className="mr-1" />Poner yo la contraseña</label>
          {propia && <input type="password" placeholder="mínimo 8 caracteres" value={clave} onChange={(e) => setClave(e.target.value)} className={`${campo} w-48`} autoComplete="new-password" />}
          <button disabled={ocupado || !carpeta.trim() || !usuario.trim() || (propia && clave.length < 8)} onClick={enviar} className={botonPrincipal}>Guardar</button>
        </div>
        <p className="text-[11px] text-ms-gray-60">El navegador pedirá usuario y contraseña al entrar en la carpeta y en todo lo que hay dentro. Si el usuario ya existe, se le cambia la contraseña. Las contraseñas se guardan cifradas fuera de la carpeta pública. Use HTTPS para que no viajen a la vista.</p>
      </div>

      {carpetas.map((c) => (
        <div key={c.ruta} className="border border-ms-gray-30 rounded p-3">
          <div className="flex justify-between items-center">
            <div><span className="font-mono text-sm">{c.ruta}</span> <span className="text-xs text-ms-gray-60">«{c.nombre}»</span></div>
            <button disabled={ocupado} onClick={() => quitar(c.ruta)} className="text-xs text-ms-red hover:underline">Quitar la protección</button>
          </div>
          <div className="flex flex-wrap gap-2 mt-2">
            {c.usuarios.map((u) => (
              <span key={u} className="px-2 py-0.5 bg-ms-gray-20 rounded text-xs">
                {u}
                <button disabled={ocupado} onClick={() => agregar(c.ruta, u)} title="Contraseña nueva (se muestra una vez)" className="ml-2 text-ms-blue hover:underline">nueva clave</button>
                <button disabled={ocupado} onClick={() => quitar(c.ruta, u)} title="Quitar este usuario" className="ml-2 text-ms-red hover:underline">quitar</button>
              </span>
            ))}
          </div>
        </div>
      ))}
      {carpetas.length === 0 && <p className="text-sm text-ms-gray-60 text-center py-3">Ninguna carpeta pide contraseña.</p>}
    </div>
  );
}
