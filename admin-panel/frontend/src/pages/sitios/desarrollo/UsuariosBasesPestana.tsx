import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { AccesoRemoto } from "./AccesoRemoto";
import { SelectorPermisos, textoPermisos } from "./SelectorPermisos";
import { campo, MOTOR, type Conexion, type Hacer, type ListadoUsuarios, type Permisos, type UsuarioBase } from "./tipos";

/* Usuarios adicionales de las bases del sitio: el servidor pone el nombre «u_<sitio>_<sufijo>» y la contraseña
   (se muestra una sola vez); aquí se eligen la base, el sufijo y los permisos. */
export function UsuariosBasesPestana({ dominio, ocupado, hacer, onClave }: {
  dominio: string; ocupado: boolean; hacer: Hacer; onClave: (c: Conexion) => void;
}) {
  const ruta = `/sitios/${dominio}/bases/usuarios`;
  const [datos, setDatos] = useState<ListadoUsuarios | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState<{ base: string; sufijo: string; permisos: Permisos }>({ base: "", sufijo: "", permisos: { perfil: "lectura" } });
  const [editando, setEditando] = useState<{ usuario: string; permisos: Permisos } | null>(null);
  const [remotoDe, setRemotoDe] = useState<string | null>(null);

  const cargar = () => api.get<ListadoUsuarios>(ruta).then((d) => {
    setDatos(d); setError("");
    setNuevo((n) => (n.base || !d.bases.length ? n : { ...n, base: d.bases[0].nombre }));
  }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [dominio]);

  const motorDe = (base: string) => datos?.bases.find((b) => b.nombre === base)?.motor || "mariadb";
  const tras = (r: ListadoUsuarios) => { setDatos(r); if (r.creado?.clave) onClave(r.creado); };

  const crear = () => hacer("Usuario creado.", async () => {
    tras(await api.post<ListadoUsuarios>(ruta, nuevo));
    setNuevo({ ...nuevo, sufijo: "", permisos: { perfil: "lectura" } });
  });
  const guardarPermisos = () => editando && hacer("Permisos cambiados.", async () => {
    tras(await api.put<ListadoUsuarios>(`${ruta}/${editando.usuario}/permisos`, { permisos: editando.permisos }));
    setEditando(null);
  });
  const clave = (u: UsuarioBase) => {
    if (!confirm(`Se generará una contraseña nueva para ${u.usuario}; la anterior deja de valer. ¿Continuar?`)) return;
    hacer("Contraseña nueva generada.", async () => tras(await api.post<ListadoUsuarios>(`${ruta}/${u.usuario}/clave`)));
  };
  const borrar = (u: UsuarioBase) => {
    if (!confirm(`Se borrará el usuario ${u.usuario} (también su acceso remoto). ¿Continuar?`)) return;
    hacer("Usuario borrado.", async () => tras(await api.del<ListadoUsuarios>(`${ruta}/${u.usuario}`)));
  };
  const remoto = (u: UsuarioBase, redes: string[], confirmarAmplia: boolean) => hacer("Acceso remoto guardado.", async () => {
    const r = await api.put<ListadoUsuarios>(`${ruta}/${u.usuario}/remoto`, { redes, confirmar_amplia: confirmarAmplia });
    tras(r); setRemotoDe(null);
    if (r.cortafuegos && r.cortafuegos !== "aplicado") alert(`Cortafuegos: ${r.cortafuegos}`);
  });

  if (!datos) return <p className="text-sm text-ms-gray-60">{error || "Cargando…"}</p>;
  return (
    <div className="space-y-4">
      <p className="text-xs text-ms-gray-90">
        Cada usuario entra solo a una base del sitio, con los permisos elegidos. Desde este servidor siempre; desde fuera, solo
        desde las IP que se indiquen y con TLS.
      </p>
      {datos.usuarios.length === 0 && <p className="text-sm text-ms-gray-60">Ningún usuario adicional.</p>}
      <ul className="text-sm divide-y divide-ms-gray-30">
        {datos.usuarios.map((u) => (
          <li key={u.usuario} className="py-2 space-y-2">
            <div className="flex justify-between gap-3 flex-wrap">
              <span>
                <code>{u.usuario}</code> <span className="text-xs text-ms-gray-60">en <code>{u.base}</code> ({MOTOR[u.motor]})</span>
                <span className="block text-xs text-ms-gray-90">Permisos: {textoPermisos(u.permisos)}
                  {u.remoto.length ? ` · Remoto con TLS: ${u.remoto.join(", ")}` : " · Solo desde este servidor"}</span>
              </span>
              <span className="space-x-3 text-xs whitespace-nowrap">
                <button disabled={ocupado} onClick={() => setEditando({ usuario: u.usuario, permisos: u.permisos })} className="text-ms-blue hover:underline disabled:opacity-50">Permisos</button>
                <button disabled={ocupado} onClick={() => setRemotoDe(remotoDe === u.usuario ? null : u.usuario)} className="text-ms-blue hover:underline disabled:opacity-50">Acceso remoto</button>
                <button disabled={ocupado} onClick={() => clave(u)} className="text-ms-blue hover:underline disabled:opacity-50">Nueva clave</button>
                <button disabled={ocupado} onClick={() => borrar(u)} className="text-ms-red hover:underline disabled:opacity-50">Borrar</button>
              </span>
            </div>
            {editando?.usuario === u.usuario && (
              <div className="border border-ms-gray-30 rounded p-3 space-y-2 bg-ms-gray-10">
                <SelectorPermisos valor={editando.permisos} privilegios={datos.privilegios[u.motor] || []} onCambio={(p) => setEditando({ ...editando, permisos: p })} />
                <div className="flex gap-2">
                  <button disabled={ocupado} onClick={guardarPermisos} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Guardar</button>
                  <button onClick={() => setEditando(null)} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm">Cancelar</button>
                </div>
              </div>
            )}
            {remotoDe === u.usuario && (
              <AccesoRemoto u={u} remoto={datos.remoto} maximo={datos.maximo_redes} ocupado={ocupado}
                onGuardar={(redes, amplia) => remoto(u, redes, amplia)} onCancelar={() => setRemotoDe(null)} />
            )}
          </li>
        ))}
      </ul>

      {datos.bases.length === 0 ? (
        <p className="text-xs text-ms-gray-60">El sitio no tiene bases todavía: créelas en «Bases».</p>
      ) : (
        <div className="border-t border-ms-gray-30 pt-3 space-y-2">
          <h3 className="text-sm font-semibold">Nuevo usuario ({datos.usuarios.length} de {datos.maximo})</h3>
          <div className="flex flex-wrap gap-2 items-center text-sm">
            <select className={campo} value={nuevo.base} onChange={(e) => setNuevo({ ...nuevo, base: e.target.value, permisos: { perfil: "lectura" } })}>
              {datos.bases.map((b) => <option key={b.nombre} value={b.nombre}>{b.nombre} ({MOTOR[b.motor]})</option>)}
            </select>
            <span className="text-ms-gray-90">u_…_</span>
            <input className={campo} placeholder="lector" maxLength={10} pattern="[a-z][a-z0-9]{1,9}" value={nuevo.sufijo}
              onChange={(e) => setNuevo({ ...nuevo, sufijo: e.target.value.trim().toLowerCase() })} />
          </div>
          <p className="text-xs text-ms-gray-60">De 2 a 10 minúsculas o números, empezando por una letra.</p>
          <SelectorPermisos valor={nuevo.permisos} privilegios={datos.privilegios[motorDe(nuevo.base)] || []} onCambio={(p) => setNuevo({ ...nuevo, permisos: p })} />
          <button disabled={ocupado || !/^[a-z][a-z0-9]{1,9}$/.test(nuevo.sufijo) || !nuevo.base} onClick={crear}
            className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Crear el usuario</button>
        </div>
      )}
    </div>
  );
}
