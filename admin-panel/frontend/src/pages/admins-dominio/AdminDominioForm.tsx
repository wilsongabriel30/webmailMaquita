import { useState } from "react";
import { api } from "../../api/client";

export interface AdminDominio {
  id: number; username: string; display_name: string; active: boolean;
  must_change_password: boolean; last_login: string | null; dominios: string[];
}

interface Props { actual: AdminDominio | null; dominios: string[]; onCerrar: () => void; onGuardado: () => void }

const campo = "w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

export function AdminDominioForm({ actual, dominios, onCerrar, onGuardado }: Props) {
  const [usuario, setUsuario] = useState(actual?.username || "");
  const [nombre, setNombre] = useState(actual?.display_name || "");
  const [clave, setClave] = useState("");
  const [activa, setActiva] = useState(actual?.active ?? true);
  const [elegidos, setElegidos] = useState<string[]>(actual?.dominios || []);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  const alternar = (d: string) => setElegidos((e) => (e.includes(d) ? e.filter((x) => x !== d) : [...e, d]));

  const guardar = async () => {
    setError("");
    if (!elegidos.length) { setError("Asigna al menos un dominio"); return; }
    if (!actual && clave.length < 10) { setError("La contraseña inicial debe tener al menos 10 caracteres"); return; }
    setGuardando(true);
    try {
      if (actual) {
        await api.put(`/admins-dominio/${actual.id}`, { display_name: nombre, active: activa, dominios: elegidos, ...(clave ? { password: clave } : {}) });
      } else {
        await api.post("/admins-dominio", { username: usuario, display_name: nombre, password: clave, dominios: elegidos });
      }
      onGuardado();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar");
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 overflow-auto py-10" onClick={onCerrar}>
      <div className="bg-white rounded border border-ms-gray-30 p-5 w-[28rem] max-w-[94vw] space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-semibold text-ms-gray-130">{actual ? `Editar ${actual.username}` : "Nuevo administrador de dominio"}</h2>
        {!actual && <input placeholder="Usuario para entrar al portal" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoFocus className={campo} />}
        <input placeholder="Nombre de la persona" value={nombre} onChange={(e) => setNombre(e.target.value)} className={campo} />
        <input type="text" autoComplete="off" placeholder={actual ? "Contraseña nueva (vacío = no cambiar)" : "Contraseña inicial (mínimo 10)"} value={clave} onChange={(e) => setClave(e.target.value)} className={campo} />
        <p className="text-xs text-ms-gray-60">Es temporal: el portal obliga a cambiarla en la primera entrada. Cambiarla aquí cierra sus sesiones abiertas.</p>
        <div>
          <div className="text-xs font-medium text-ms-gray-90 mb-1">Dominios que administra</div>
          <div className="border border-ms-gray-30 rounded max-h-48 overflow-auto p-2 space-y-1">
            {dominios.map((d) => (
              <label key={d} className="flex items-center gap-2 text-sm text-ms-gray-130">
                <input type="checkbox" checked={elegidos.includes(d)} onChange={() => alternar(d)} />{d}
              </label>
            ))}
          </div>
        </div>
        {actual && (
          <label className="flex items-center gap-2 text-sm text-ms-gray-90">
            <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} />
            Cuenta activa (si se desmarca, no puede entrar y se cierran sus sesiones)
          </label>
        )}
        {error && <div className="text-ms-red text-xs">{error}</div>}
        <div className="flex gap-2 justify-end">
          <button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          <button onClick={guardar} disabled={guardando} className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-60">Guardar</button>
        </div>
      </div>
    </div>
  );
}
