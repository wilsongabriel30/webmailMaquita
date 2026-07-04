import { useState, useEffect } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Cfg {
  umbral: number;
  macro_score: number;
  neurona_peso: number;
  extensiones_extra: string[];
  depuracion_dias: number;
}
interface Resp {
  config: Cfg;
  familias: Record<string, string[]>;
  neurona: { entrenada: boolean; bytes: number };
}

const FAM_LABEL: Record<string, string> = {
  ejecutables_scripts: "Ejecutables y scripts (bloqueo +5 / +6 dentro de comprimido)",
  imagenes_disco: "Imágenes de disco (bloqueo +5)",
  office_macros: "Office con macros (marca suave, configurable)",
  comprimidos_inspeccionados: "Comprimidos que se abren e inspeccionan con 7z",
};

export function AntispamAvanzado() {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [fam, setFam] = useState<Record<string, string[]>>({});
  const [neu, setNeu] = useState<{ entrenada: boolean; bytes: number }>({ entrenada: false, bytes: 0 });
  const [extraTxt, setExtraTxt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [verFam, setVerFam] = useState(false);
  // depuracion
  const [depDias, setDepDias] = useState(35);
  const [corriendo, setCorriendo] = useState(false);
  const [salida, setSalida] = useState("");

  useEffect(() => {
    api.get<Resp>("/antispam-avanzado")
      .then((d) => {
        setCfg(d.config); setFam(d.familias); setNeu(d.neurona);
        setExtraTxt((d.config.extensiones_extra || []).join(", "));
        setDepDias(d.config.depuracion_dias || 35);
      })
      .catch((e) => setMsg({ ok: false, text: e.message }))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    if (!cfg) return;
    setSaving(true); setMsg(null);
    const exts = extraTxt.split(/[,\s]+/).map((s) => s.trim().replace(/^\./, "").toLowerCase()).filter(Boolean);
    try {
      const r = await api.put<{ ok: boolean; config: Cfg }>("/antispam-avanzado", { ...cfg, extensiones_extra: exts });
      setCfg(r.config); setExtraTxt((r.config.extensiones_extra || []).join(", "));
      setMsg({ ok: true, text: "Configuración guardada. Aplica al correo que llegue desde ahora." });
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally { setSaving(false); }
  }

  async function depurar(borrar: boolean) {
    if (borrar && !confirm("¿Borrar los correos con adjuntos DAÑINOS (ejecutables/no inspeccionables) de los últimos " + depDias + " días? No toca los de macros. Esta acción no se puede deshacer.")) return;
    setCorriendo(true); setSalida(""); setMsg(null);
    try {
      const r = await api.post<{ salida: string; borrado: boolean }>("/antispam-avanzado/depurar", { dias: depDias, borrar });
      setSalida(r.salida || "(sin resultados)");
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally { setCorriendo(false); }
  }

  if (loading) return <div className="p-6 text-ms-gray-60">Cargando…</div>;
  if (!cfg) return <div className="p-6 text-red-700">No se pudo cargar la configuración.</div>;

  type NumKey = "umbral" | "macro_score" | "neurona_peso" | "depuracion_dias";
  const num = (k: NumKey) => cfg[k];
  const setNum = (k: NumKey, v: number) => setCfg({ ...cfg, [k]: v });

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Filtro Avanzado de Adjuntos"
          items={[
            { titulo: "Qué es", desc: "Filtro anti-malware que puntúa los adjuntos del correo entrante: ejecutables, scripts, imágenes de disco y comprimidos (se abren con 7z y se inspecciona su contenido). Según el puntaje total, el correo va a la carpeta Junk." },
            { titulo: "Umbral de spam", desc: "Puntaje total a partir del cual el correo se mueve a Junk. Bajarlo hace el filtro más estricto (más correos a Junk); subirlo lo hace más permisivo." },
            { titulo: "Office con macros", desc: "Puntaje que suma un documento de Office con macros. Con 2 solo lo marca sin mandarlo a Junk (recomendado); con 0 se ignoran las macros." },
            { titulo: "Neurona de spam", desc: "Clasificador que aprende de tu correo. Con peso 0 solo observa y aprende sin influir; al subir el peso, su opinión suma o resta al puntaje de spam." },
            { titulo: "Extensiones extra", desc: "Extensiones adicionales que quieras bloquear con puntaje fuerte (+5), sumadas a las familias ya bloqueadas por defecto." },
            { titulo: "Depuración", desc: "Revisa (reporte, no borra nada) o elimina definitivamente los correos con adjuntos dañinos inequívocos de los últimos N días. Nunca toca los correos marcados solo por macros." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-130 mb-1">Filtro Avanzado de Adjuntos</h1>
      <p className="text-sm text-ms-gray-60 mb-5">
        Afina el filtro anti-malware de adjuntos: detección dentro de comprimidos, manejo de
        Office con macros, la <b>neurona de spam</b> y la depuración mensual. Los cambios se
        aplican al correo que llegue <b>desde que guardas</b>.
      </p>

      {/* Configuracion */}
      <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Umbral de spam</label>
            <input type="number" min={1} max={15} className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
              title="Puntaje total de spam a partir del cual el correo se mueve a la carpeta Junk. Un valor más bajo hace el filtro más estricto (más correos a Junk); más alto, más permisivo. Default: 3."
              value={num("umbral")} onChange={(e) => setNum("umbral", parseInt(e.target.value || "3"))} />
            <p className="text-xs text-ms-gray-60 mt-1">Puntaje a partir del cual va a Junk (default 3).</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Puntaje Office-macros</label>
            <input type="number" min={0} max={6} className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
              title="Puntaje que suma un adjunto de Office con macros. Con 2 solo lo marca sin enviarlo a Junk (recomendado); con 0 ignora las macros; valores altos pueden mandar a Junk documentos legítimos con macros."
              value={num("macro_score")} onChange={(e) => setNum("macro_score", parseInt(e.target.value || "0"))} />
            <p className="text-xs text-ms-gray-60 mt-1">2 = marca sin enviar a Junk (recomendado). 0 = ignora.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Peso de la neurona</label>
            <input type="number" min={0} max={5} className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
              title="Influencia de la neurona de spam (clasificador que aprende de tu correo) en el puntaje final. Con 0 solo observa y aprende sin afectar la entrega; al subirlo, su veredicto suma o resta puntos de spam."
              value={num("neurona_peso")} onChange={(e) => setNum("neurona_peso", parseInt(e.target.value || "0"))} />
            <p className="text-xs text-ms-gray-60 mt-1">0 = solo observa y aprende (advisory). Subir para que influya.</p>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-ms-gray-130 mb-1">Extensiones extra a bloquear</label>
          <input className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm"
            title="Extensiones de archivo adicionales a bloquear con puntaje fuerte (+5), separadas por coma o espacio y sin punto. Se suman a las familias bloqueadas por defecto: los adjuntos con estas extensiones enviarán el correo a Junk."
            placeholder="ej: svg, xml, ace  (separadas por coma)"
            value={extraTxt} onChange={(e) => setExtraTxt(e.target.value)} />
          <p className="text-xs text-ms-gray-60 mt-1">Se suman a las familias ya bloqueadas. Bloqueo fuerte (+5).</p>
        </div>

        <div className="text-sm">
          <span className="text-ms-gray-130">Neurona: </span>
          {neu.entrenada
            ? <span className="text-green-600">entrenada ({neu.bytes} bytes de pesos)</span>
            : <span className="text-ms-gray-60">sin entrenar todavía</span>}
        </div>

        {msg && (
          <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.text}</div>
        )}

        <div className="flex gap-3 pt-1">
          <button onClick={save} disabled={saving}
            title="Guarda umbral, puntajes, peso de la neurona y extensiones extra en el servidor. Los cambios se aplican solo al correo que llegue a partir de ahora; no reclasifica lo ya recibido."
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-50">
            {saving ? "Guardando…" : "Guardar configuración"}
          </button>
          <button onClick={() => setVerFam(!verFam)}
            title="Muestra u oculta la lista de familias de extensiones que el filtro ya bloquea o inspecciona por defecto. Es solo informativo: no cambia ninguna configuración."
            className="px-4 py-2 border border-ms-gray-30 rounded text-sm font-medium">
            {verFam ? "Ocultar" : "Ver"} familias bloqueadas
          </button>
        </div>

        {verFam && (
          <div className="border-t border-ms-gray-30 pt-3 space-y-2">
            {Object.entries(fam).map(([k, v]: [string, string[]]) => (
              <div key={k}>
                <div className="text-xs font-medium text-ms-gray-130">{FAM_LABEL[k] || k}</div>
                <div className="text-xs text-ms-gray-60 break-words">{v.join(", ")}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Depuracion mensual */}
      <div className="bg-white rounded border border-ms-gray-30 p-5 mt-5">
        <h2 className="text-base font-semibold text-ms-gray-130 mb-1">Depuración de adjuntos peligrosos</h2>
        <p className="text-sm text-ms-gray-60 mb-3">
          Revisa los correos con adjuntos dañinos (en Junk). El reporte no borra nada.
          “Borrar dañinos” elimina solo los inequívocos (ejecutables / no inspeccionables);
          <b> nunca toca los de macros</b>.
        </p>
        <div className="flex items-end gap-3 mb-3">
          <div>
            <label className="block text-xs text-ms-gray-60 mb-1">Últimos N días</label>
            <input type="number" min={1} max={90} className="w-24 px-3 py-2 border border-ms-gray-30 rounded text-sm"
              title="Cuántos días hacia atrás revisa la depuración (1 a 90). Solo afecta al reporte y al borrado de esta sección, no al filtrado del correo entrante."
              value={depDias} onChange={(e) => setDepDias(parseInt(e.target.value || "35"))} />
          </div>
          <button onClick={() => depurar(false)} disabled={corriendo}
            title="Genera un reporte de los correos con adjuntos dañinos (en Junk) de los últimos N días. Es de solo lectura: no borra ni mueve ningún correo."
            className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-50">
            {corriendo ? "Ejecutando…" : "Ejecutar reporte"}
          </button>
          <button onClick={() => depurar(true)} disabled={corriendo}
            title="Elimina definitivamente los correos con adjuntos dañinos inequívocos (ejecutables o no inspeccionables) de los últimos N días. Nunca toca los marcados solo por macros. Pide confirmación y NO se puede deshacer."
            className="px-4 py-2 border border-red-300 text-red-700 rounded text-sm font-medium disabled:opacity-50">
            Borrar dañinos
          </button>
        </div>
        {salida && (
          <pre className="text-xs bg-ms-gray-10 border border-ms-gray-30 rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap">{salida}</pre>
        )}
      </div>
    </div>
  );
}
