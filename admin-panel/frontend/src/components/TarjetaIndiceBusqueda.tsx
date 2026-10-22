// Estado del índice de texto completo del correo y «Reindexar buzón» (panel → Servicios).
//
// El índice lo instala deploy/dovecot/fts (ajuste 63). Reindexar rehace el índice de una cuenta en
// segundo plano (p. ej. para que entren los adjuntos de correos antiguos); no toca los mensajes,
// tampoco los que están bajo retención legal.

import { useEffect, useState } from "react";
import { api } from "../api/client";

interface EstadoIndice {
  activo: boolean;
  motor: string | null;
  adjuntos: boolean;
  ocr: boolean;
  buzones_total: number;
  buzones_indexados: number;
  indexacion_inicial: "en curso" | "terminada" | "pendiente";
  herramientas: Record<string, boolean>;
  registro: string[];
}

const RE_BUZON = /^[a-z0-9][a-z0-9._+-]{0,63}@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/;

function Etiqueta({ si, texto }: { si: boolean; texto: string }) {
  return (
    <span
      className="inline-block px-2 py-0.5 rounded text-xs mr-2"
      style={si ? { background: "#dff6dd", color: "#107c10" } : { background: "#fde7e9", color: "#a4262c" }}
    >
      {texto}
    </span>
  );
}

export function TarjetaIndiceBusqueda() {
  const [estado, setEstado] = useState<EstadoIndice | null>(null);
  const [error, setError] = useState("");
  const [buzon, setBuzon] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);

  const cargar = () =>
    api.get<EstadoIndice>("/indice-busqueda")
      .then((e) => { setEstado(e); setError(""); })
      .catch((e: Error) => setError(e.message || "No se pudo leer el estado del índice"));
  useEffect(() => { cargar(); }, []);

  const valido = RE_BUZON.test(buzon.trim().toLowerCase());

  const reindexar = async () => {
    const b = buzon.trim().toLowerCase();
    if (!RE_BUZON.test(b)) return;
    if (!window.confirm(`¿Rehacer el índice de búsqueda de ${b}? Mientras se reconstruye, buscar dentro del texto en ese buzón puede tardar más. Los mensajes no se tocan.`)) return;
    setOcupado(true); setMensaje(null);
    try {
      const r = await api.post<{ carpetas?: number }>("/indice-busqueda/reindexar", { buzon: b });
      setMensaje({ ok: true, texto: `Reindexación de ${b} en marcha (${r?.carpetas ?? 0} carpetas, en segundo plano).` });
      setBuzon("");
      cargar();
    } catch (e: any) {
      setMensaje({ ok: false, texto: e.message || "No se pudo reindexar" });
    } finally {
      setOcupado(false);
    }
  };

  const faltan = estado ? Object.entries(estado.herramientas).filter(([, ok]) => !ok).map(([h]) => h) : [];

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-4 space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-ms-gray-130">Búsqueda de texto completo</h2>
        <p className="text-xs text-ms-gray-90">
          Índice de Dovecot (fts-flatcurve) para buscar en segundos por remitente, asunto, texto y adjuntos
          (PDF, Office, LibreOffice, comprimidos). La papelera y el correo no deseado no se indexan al llegar.
        </p>
      </div>

      {error && <p className="text-xs text-ms-gray-90">{error}</p>}

      {estado && (
        <div className="text-sm text-ms-gray-130 space-y-1">
          <div>
            <Etiqueta si={estado.activo} texto={estado.activo ? "Índice activo" : "Sin índice"} />
            <Etiqueta si={estado.adjuntos} texto={estado.adjuntos ? "Con texto de adjuntos" : "Sin adjuntos"} />
            {estado.ocr && <Etiqueta si texto="OCR activo" />}
          </div>
          <div className="text-xs text-ms-gray-90">
            Buzones indexados: <b>{estado.buzones_indexados}</b> de {estado.buzones_total} · Indexación inicial: {estado.indexacion_inicial}
          </div>
          {faltan.length > 0 && (
            <div className="text-xs text-amber-700">Herramientas no instaladas: {faltan.join(", ")} (esos formatos no se indexan).</div>
          )}
          {estado.registro.length > 0 && (
            <pre className="text-[11px] bg-ms-gray-10 rounded p-2 overflow-x-auto whitespace-pre-wrap">{estado.registro.join("\n")}</pre>
          )}
        </div>
      )}

      {mensaje && (
        <p className={`text-xs ${mensaje.ok ? "text-green-700" : "text-red-700"}`}>{mensaje.texto}</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="px-3 py-1.5 border border-ms-gray-30 rounded text-sm w-72 max-w-full"
          placeholder="buzón (persona@example.org)"
          aria-label="Buzón a reindexar"
          value={buzon}
          onChange={(e) => setBuzon(e.target.value)}
        />
        <button
          type="button"
          onClick={reindexar}
          disabled={!valido || ocupado || !estado?.activo}
          className="px-3 py-1.5 text-xs bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-40"
          title="Rehace el índice de este buzón en segundo plano (p. ej. para incluir los adjuntos de correos antiguos). No modifica los mensajes."
        >
          {ocupado ? "Reindexando…" : "Reindexar buzón"}
        </button>
      </div>
    </div>
  );
}
