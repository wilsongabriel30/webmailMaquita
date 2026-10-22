import { campo, PERFILES, type Permisos, type Perfil } from "./tipos";

/* Perfil de permisos (lectura, escritura, estructura, todo) o una lista a medida con los privilegios del motor. */
export function SelectorPermisos({ valor, privilegios, onCambio }: { valor: Permisos; privilegios: string[]; onCambio: (p: Permisos) => void }) {
  const lista = valor.lista || [];
  const alternar = (p: string) => onCambio({ perfil: "medida", lista: lista.includes(p) ? lista.filter((x) => x !== p) : [...lista, p] });
  return (
    <div className="space-y-2">
      <select className={campo} value={valor.perfil}
        onChange={(e) => { const perfil = e.target.value as Perfil; onCambio(perfil === "medida" ? { perfil, lista: ["SELECT"] } : { perfil }); }}>
        {PERFILES.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
      </select>
      <p className="text-xs text-ms-gray-90">{PERFILES.find((p) => p.id === valor.perfil)?.ayuda}</p>
      {valor.perfil === "medida" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-1 text-xs">
          {privilegios.map((p) => (
            <label key={p} className="flex items-center gap-1">
              <input type="checkbox" checked={lista.includes(p)} onChange={() => alternar(p)} /> {p}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

export function textoPermisos(p: Permisos): string {
  if (p.perfil === "medida") return (p.lista || []).join(", ");
  return PERFILES.find((x) => x.id === p.perfil)?.nombre || p.perfil;
}
