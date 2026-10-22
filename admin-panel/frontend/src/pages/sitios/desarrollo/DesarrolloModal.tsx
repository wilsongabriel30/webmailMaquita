import { useState } from "react";
import { CredencialesModal, type Credencial } from "../CredencialesModal";
import { ClavesSshPestana } from "./ClavesSshPestana";
import { CortafuegosPestana } from "./CortafuegosPestana";
import { UsuariosBasesPestana } from "./UsuariosBasesPestana";
import { MOTOR, type Conexion } from "./tipos";

export type PestanaDesarrollo = "usuarios" | "cortafuegos" | "ssh";

const PESTANAS: { id: PestanaDesarrollo; nombre: string }[] = [
  { id: "usuarios", nombre: "Usuarios de bases" },
  { id: "cortafuegos", nombre: "Cortafuegos de aplicaciones" },
  { id: "ssh", nombre: "Claves SSH" },
];

/* Para desarrolladores (v1.11): usuarios de bases con permisos y acceso remoto con TLS, cortafuegos de aplicaciones
   web (OWASP CRS) y claves SSH de las cuentas SFTP del sitio. */
export function DesarrolloModal({ dominio, inicial = "usuarios", onCerrar }: { dominio: string; inicial?: PestanaDesarrollo; onCerrar: () => void }) {
  const [pestana, setPestana] = useState<PestanaDesarrollo>(inicial);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [credenciales, setCredenciales] = useState<{ titulo: string; items: Credencial[]; nota?: string } | null>(null);

  const hacer = async (texto: string, fn: () => Promise<unknown>) => {
    setOcupado(true); setError(""); setMensaje("");
    try { await fn(); setMensaje(texto); return true; } catch (e) { setError((e as Error).message); return false; } finally { setOcupado(false); }
  };
  const mostrarClave = (c: Conexion) => setCredenciales({
    titulo: `Usuario ${c.usuario}`,
    items: [
      { etiqueta: "Servidor (desde este servidor)", valor: `${c.servidor}:${c.puerto}` },
      ...(c.servidor_remoto ? [{ etiqueta: "Servidor (remoto, con TLS)", valor: `${c.servidor_remoto}:${c.puerto}` }] : []),
      { etiqueta: "Base", valor: `${c.base} (${MOTOR[c.motor]})` },
      { etiqueta: "Usuario", valor: c.usuario },
      { etiqueta: "Contraseña", valor: c.clave || "", secreto: true },
    ],
    nota: "Guarde la contraseña ahora: no se vuelve a mostrar. Si se pierde, genere otra con «Nueva clave».",
  });
  const boton = (activo: boolean) => `px-3 py-1.5 text-sm rounded-t border-b-2 whitespace-nowrap ${activo ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90"}`;
  const props = { dominio, ocupado, hacer };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-4xl p-5 space-y-3 max-h-[92vh] overflow-y-auto">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold text-ms-gray-130">Para desarrolladores — {dominio}</h2>
            <p className="text-xs text-ms-gray-90">Usuarios de bases, cortafuegos de aplicaciones web y claves SSH. Todo queda en la auditoría.</p>
          </div>
          <button onClick={onCerrar} className="text-sm text-ms-gray-90 hover:underline">Cerrar</button>
        </div>
        <div className="flex gap-1 border-b border-ms-gray-30 overflow-x-auto">
          {PESTANAS.map((p) => <button key={p.id} className={boton(pestana === p.id)} onClick={() => { setPestana(p.id); setMensaje(""); setError(""); }}>{p.nombre}</button>)}
        </div>
        {pestana === "usuarios" && <UsuariosBasesPestana {...props} onClave={mostrarClave} />}
        {pestana === "cortafuegos" && <CortafuegosPestana {...props} />}
        {pestana === "ssh" && <ClavesSshPestana {...props} />}
        {(mensaje || error) && <p className={`text-sm ${error ? "text-ms-red" : "text-ms-green"}`}>{error || mensaje}</p>}
      </div>
      {credenciales && <CredencialesModal {...credenciales} onCerrar={() => setCredenciales(null)} />}
    </div>
  );
}
