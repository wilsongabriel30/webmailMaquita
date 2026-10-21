import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { campo, tamano } from "./datosComun";

interface Registro { existe: boolean; lineas: string[]; bytes?: number; recortado: boolean }
const TIPOS = [
  { id: "error", titulo: "Errores de nginx" },
  { id: "acceso", titulo: "Accesos" },
  { id: "php", titulo: "Errores de PHP" },
];

/* Últimas líneas de los registros del sitio, con filtro de texto simple. */
export function RegistrosPestana({ dominio }: { dominio: string }) {
  const [tipo, setTipo] = useState("error");
  const [lineas, setLineas] = useState(200);
  const [filtro, setFiltro] = useState("");
  const [datos, setDatos] = useState<Registro | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = async () => {
    setOcupado(true); setError("");
    try {
      const q = `lineas=${lineas}` + (filtro.trim() ? `&filtro=${encodeURIComponent(filtro.trim())}` : "");
      setDatos(await api.get<Registro>(`/sitios/${dominio}/registros/${tipo}?${q}`));
    } catch (e) { setError((e as Error).message); setDatos(null); } finally { setOcupado(false); }
  };
  useEffect(() => { cargar(); }, [dominio, tipo]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select value={tipo} onChange={(e) => setTipo(e.target.value)} className={campo}>
          {TIPOS.map((t) => <option key={t.id} value={t.id}>{t.titulo}</option>)}
        </select>
        <select value={lineas} onChange={(e) => setLineas(Number(e.target.value))} className={campo}>
          {[50, 200, 500, 1000].map((n) => <option key={n} value={n}>Últimas {n} líneas</option>)}
        </select>
        <input value={filtro} maxLength={100} onChange={(e) => setFiltro(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cargar()}
          placeholder="Filtrar (p. ej. 404, wp-login, Fatal)" className={`${campo} flex-1 min-w-48`} />
        <button onClick={cargar} disabled={ocupado} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Ver</button>
      </div>
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {datos && !datos.existe && <p className="text-sm text-ms-gray-60">Este registro todavía no existe (no ha habido nada que anotar).</p>}
      {datos?.existe && (
        <>
          <p className="text-[11px] text-ms-gray-60">{datos.lineas.length} líneas · registro de {tamano(datos.bytes)}{datos.recortado ? " (se leen sus últimos 8 MB)" : ""}. Los registros se rotan cada semana.</p>
          <pre className="bg-ms-gray-20 border rounded p-2 text-[11px] max-h-[55vh] overflow-auto whitespace-pre-wrap break-all">{datos.lineas.join("\n") || "(ninguna línea coincide)"}</pre>
        </>
      )}
    </div>
  );
}
