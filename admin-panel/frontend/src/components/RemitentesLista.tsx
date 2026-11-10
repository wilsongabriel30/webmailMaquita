// Quién puede ENVIAR a una lista (panel de administración, 09/11/2026).
// Es lo único que aplica Postfix (servicio maquita-politica-listas): con al menos una persona aquí, solo esas
// cuentas autenticadas pueden escribir a la lista y al resto se le rechaza con un mensaje claro. Sin nadie,
// la lista queda abierta. Se guarda en mail_groups.allowed_senders (PUT /groups/{id}).
// La columna «Envía» de cada miembro NO restringe el envío: es solo informativa.
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

interface Sugerencia { username: string; name: string }

interface Props {
  grupoId: number;
  direccion: string;
  autorizados: string;               // texto guardado: direcciones separadas por coma
  onGuardado: (nuevo: string) => void;
}

const EMAIL_RE = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

function separar(texto: string): string[] {
  return (texto || "").split(/[\s,;]+/).map((x) => x.trim().toLowerCase()).filter(Boolean);
}

export function RemitentesLista({ grupoId, direccion, autorizados, onGuardado }: Props) {
  const [lista, setLista] = useState<string[]>(separar(autorizados));
  const [nuevo, setNuevo] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { setLista(separar(autorizados)); setError(""); }, [autorizados, grupoId]);
  const [sugerencias, setSugerencias] = useState<Sugerencia[]>([]);
  const temporizador = useRef<any>(null);

  // Buscar por nombre o correo mientras se escribe (mismo autocompletado que «Agregar miembro»).
  const escribir = (q: string) => {
    setNuevo(q);
    setError("");
    if (temporizador.current) clearTimeout(temporizador.current);
    if (q.trim().length < 2) { setSugerencias([]); return; }
    temporizador.current = setTimeout(() => {
      api.get<Sugerencia[]>(`/mailboxes/search/autocomplete?q=${encodeURIComponent(q.trim())}&limit=8`)
        .then((d) => setSugerencias(d.filter((x) => !lista.includes(x.username.toLowerCase()))))
        .catch(() => setSugerencias([]));
    }, 250);
  };

  const guardar = async (siguiente: string[]) => {
    setGuardando(true);
    setError("");
    try {
      const texto = siguiente.join(", ");
      await api.put(`/groups/${grupoId}`, { allowed_senders: texto });
      setLista(siguiente);
      onGuardado(texto);
    } catch (e: any) {
      setError(e?.detail || e?.message || "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  };

  const agregar = (elegido?: string) => {
    const correo = (elegido ?? nuevo).trim().toLowerCase();
    setSugerencias([]);
    if (!EMAIL_RE.test(correo)) { setError("Escriba una dirección de correo válida."); return; }
    if (lista.includes(correo)) { setError("Esa persona ya está autorizada."); return; }
    setNuevo("");
    guardar([...lista, correo]);
  };

  const quitar = (correo: string) => {
    const aviso = lista.length === 1
      ? `Si quita a ${correo}, la lista ${direccion} quedará ABIERTA: cualquiera podrá escribirle. ¿Continuar?`
      : `¿Quitar a ${correo}? Ya no podrá enviar correos a ${direccion}.`;
    if (!confirm(aviso)) return;
    guardar(lista.filter((x) => x !== correo));
  };

  return (
    <div className="bg-amber-50 rounded border border-amber-200 p-4">
      <h3 className="text-sm font-semibold text-ms-gray-130">Quién puede enviar a esta lista</h3>
      <p className="text-xs text-ms-gray-60 mt-0.5 mb-3">
        {lista.length > 0
          ? "Solo estas cuentas pueden escribir a la lista; a cualquier otra el servidor le rechaza el envío. El cambio aplica en menos de un minuto, sin límite de destinatarios para quien está autorizado."
          : "Lista abierta: cualquiera puede escribirle. Agregue cuentas para limitar quién envía."}
      </p>
      <div className="flex gap-2 mb-2">
        <div className="flex-1 relative">
          <input value={nuevo} onChange={(e) => escribir(e.target.value)} disabled={guardando}
            placeholder="Escriba el nombre o el correo de la persona…"
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregar(sugerencias.length === 1 ? sugerencias[0].username : undefined); } if (e.key === "Escape") setSugerencias([]); }}
            onBlur={() => setTimeout(() => setSugerencias([]), 150)}
            className="w-full px-3 py-1.5 border border-ms-gray-30 rounded text-sm bg-white" />
          {sugerencias.length > 0 && (
            <ul className="absolute left-0 right-0 top-full mt-1 bg-white border border-ms-gray-30 rounded shadow-lg z-20 max-h-56 overflow-y-auto">
              {sugerencias.map((su) => (
                <li key={su.username}>
                  <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => agregar(su.username)}
                    className="w-full text-left px-3 py-1.5 hover:bg-ms-blue-lighter/60">
                    <span className="block text-sm text-ms-gray-130">{su.name || su.username}</span>
                    {su.name && <span className="block text-[11px] text-ms-gray-60">{su.username}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button onClick={() => agregar()} disabled={guardando || !nuevo.trim()}
          title="Autoriza a esta cuenta a enviar correos a la lista. No hace falta que sea miembro."
          className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">
          Autorizar
        </button>
      </div>
      {error && <p className="text-xs text-ms-red mb-2">{error}</p>}
      {lista.length > 0 && (
        <div className="space-y-1">
          {lista.map((c) => (
            <div key={c} className="flex items-center justify-between py-1 px-2 rounded bg-white border border-amber-100">
              <span className="text-sm text-ms-gray-130">{c}</span>
              <button onClick={() => quitar(c)} disabled={guardando} title={`Quitar a ${c}: ya no podrá enviar a ${direccion}.`}
                className="text-xs text-ms-red hover:underline disabled:opacity-50">Quitar</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
