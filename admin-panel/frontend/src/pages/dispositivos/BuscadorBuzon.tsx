import { useEffect, useState } from "react";
import { api } from "../../api/client";

// Buscador de buzones (autocompletado sobre /mailboxes/search/autocomplete) para asignar un código a una persona.

interface Buzon { username: string; name?: string }

export function BuscadorBuzon({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [q, setQ] = useState(value);
  const [opciones, setOpciones] = useState<Buzon[]>([]);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => { setQ(value); }, [value]);
  useEffect(() => {
    if (!abierto || q.trim().length < 2) { setOpciones([]); return; }
    const t = setTimeout(() => {
      api.get<Buzon[]>(`/mailboxes/search/autocomplete?q=${encodeURIComponent(q.trim())}&limit=8`).then(setOpciones).catch(() => setOpciones([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, abierto]);

  return (
    <div className="relative mt-1">
      <input value={q} placeholder="Nombre o correo (opcional)" onFocus={() => setAbierto(true)}
        onChange={(e) => { setQ(e.target.value); onChange(e.target.value.trim()); setAbierto(true); }}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        className="block w-64 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" />
      {abierto && opciones.length > 0 && <ul className="absolute z-20 mt-1 w-72 bg-white border border-ms-gray-30 rounded shadow-lg max-h-56 overflow-y-auto">
        {opciones.map((b) => <li key={b.username}><button type="button" onMouseDown={() => { onChange(b.username); setQ(b.username); setAbierto(false); }}
          className="w-full text-left px-3 py-1.5 text-sm hover:bg-ms-gray-10"><div>{b.name || b.username}</div>{b.name && <div className="text-xs text-ms-gray-60">{b.username}</div>}</button></li>)}
      </ul>}
    </div>
  );
}
