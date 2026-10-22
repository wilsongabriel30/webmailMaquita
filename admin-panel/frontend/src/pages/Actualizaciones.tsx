import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { ArchivosSistema, type ArchivosSistemaInforme, totalesArchivos } from "./actualizaciones/ArchivosSistema";

interface Disponible { buscado: string; canal: string; ref: string | null; nueva: boolean; commit?: string; firmada?: boolean | null; notas?: string; cambios?: string[] }
interface Progreso {
  estado: string; paso?: string; desde: string; hasta: string; inicio: string; fin?: string; error?: string;
  version?: string; fallos_antes?: number; fallos_despues?: number; registro?: string; archivos_sistema?: ArchivosSistemaInforme;
}
interface Estado {
  actual: { commit: string; version: string; cambios_locales: string[] };
  config: { canal: string; automatico: boolean };
  disponible: Disponible | null; firmantes: boolean; progreso: Progreso | null; historial: Progreso[];
}

const ESTADO: Record<string, [string, string]> = {
  "en curso": ["En curso", "bg-amber-50 text-amber-700"], terminada: ["Instalada", "bg-green-50 text-ms-green"],
  revertida: ["Revertida (se volvió a la anterior)", "bg-red-50 text-ms-red"], fallida: ["Falló", "bg-red-50 text-ms-red"],
  interrumpida: ["Interrumpida", "bg-red-50 text-ms-red"],
};
const caja = "bg-white rounded border border-ms-gray-30 p-5 space-y-3";

function Etiqueta({ estado }: { estado: string }) {
  const [texto, color] = ESTADO[estado] || [estado, "bg-ms-gray-20 text-ms-gray-90"];
  return <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${color}`}>{texto}</span>;
}

/* Versión instalada, versión disponible (firmada), instalar ahora, automático por la noche e historial. */
export function Actualizaciones() {
  const [est, setEst] = useState<Estado | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [canal, setCanal] = useState("estable");

  const cargar = () => api.get<Estado>("/actualizaciones").then((d) => { setEst(d); setCanal(d.config.canal); }).catch((e) => setMensaje(e.message));
  useEffect(() => { cargar(); }, []);
  // Mientras se instala, el panel se reinicia: se consulta cada 5 s y los cortes no cuentan como error.
  const enCurso = est?.progreso?.estado === "en curso";
  useEffect(() => {
    if (!enCurso) return;
    const t = setInterval(() => api.get<Estado>("/actualizaciones").then(setEst).catch(() => {}), 5000);
    return () => clearInterval(t);
  }, [enCurso]);

  const hacer = async (fn: () => Promise<unknown>) => {
    setOcupado(true); setMensaje("");
    try { await fn(); } catch (e) { setMensaje((e as Error).message); } finally { setOcupado(false); cargar(); }
  };
  const buscar = () => hacer(() => api.post("/actualizaciones/buscar"));
  const instalar = (ref: string) => {
    if (!confirm(`Se instalará ${ref}. El correo se corta unos 30 segundos al reiniciar los servicios y el proceso tarda varios minutos. Antes se respalda la base de datos y, si algo empeora, se vuelve solo a la versión actual. ¿Continuar?`)) return;
    hacer(() => api.post("/actualizaciones/aplicar", { ref }));
  };
  const guardar = (cambios: Partial<Estado["config"]>) => hacer(() => api.put("/actualizaciones/config", { ...est!.config, ...cambios }));

  if (!est) return <div className="p-6 text-sm text-ms-gray-60">{mensaje || "Cargando…"}</div>;
  const d = est.disponible;
  const p = est.progreso;

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <h1 className="text-xl font-semibold text-ms-gray-130">Actualizaciones</h1>
      <SectionHelp titulo="Actualizaciones" items={[
        { titulo: "De dónde vienen", desc: "Del repositorio del proyecto. En el canal «estable» solo se instalan versiones (vX.Y.Z) firmadas por el equipo: una versión sin firma válida no se instala nunca, aunque aparezca en el repositorio." },
        { titulo: "Qué hace al instalar", desc: "Valida el servidor, respalda la base de datos, cambia el código, aplica migraciones, dependencias, frontends del correo y del panel, las secciones instaladas y los ajustes del servidor, reinicia y vuelve a validar. Si quedan más fallos que antes, vuelve sola a la versión anterior." },
        { titulo: "Archivos del sistema", desc: "Al terminar se muestra qué archivos de configuración del servidor (DNS, nginx, fail2ban, correo, systemd, programas instalados, .env) creó, cambió o borró la actualización. Si alguno tenía un parche hecho a mano, se marca «tenía cambios locales» y su contenido anterior queda en una copia para recuperarlo." },
        { titulo: "Automático", desc: "Cada noche (03:30 más un margen al azar) busca y, si hay versión nueva firmada, la instala. El correo se corta unos 30 segundos al reiniciar." },
      ]} />

      <div className={caja}>
        <div className="flex flex-wrap items-center gap-3">
          <div><div className="text-xs text-ms-gray-60">Instalada</div><div className="text-lg font-mono">{est.actual.version}</div></div>
          <div className="ml-auto flex gap-2">
            <button onClick={buscar} disabled={ocupado || enCurso} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Buscar</button>
          </div>
        </div>
        {est.actual.cambios_locales.length > 0 && <p className="text-sm text-ms-red">Hay cambios locales en el código ({est.actual.cambios_locales.join(", ")}): no se actualizará hasta quitarlos o subirlos al repositorio.</p>}
        {!est.firmantes && est.config.canal.startsWith("estable") && <p className="text-sm text-ms-red">Falta la lista de firmantes: no se puede instalar ninguna versión estable.</p>}
        {d && (
          d.nueva ? (
            <div className="border-t border-ms-gray-30 pt-3 space-y-2">
              <p className="text-sm">Disponible: <b className="font-mono">{d.ref?.replace("origin/", "rama ")}</b>
                {d.canal.startsWith("estable") && (d.firmada ? <span className="ml-2 text-xs text-ms-green">firmada por el equipo</span> : <span className="ml-2 text-xs text-ms-red">sin firma válida: no se instalará</span>)}
                <span className="text-xs text-ms-gray-60"> · buscado {d.buscado}</span></p>
              {d.notas && <pre className="text-xs bg-ms-gray-10 p-2 rounded whitespace-pre-wrap max-h-48 overflow-auto">{d.notas}</pre>}
              {!d.notas && !!d.cambios?.length && <ul className="text-xs list-disc pl-5 max-h-48 overflow-auto">{d.cambios.map((c, i) => <li key={i}>{c}</li>)}</ul>}
              <button onClick={() => instalar(d.ref!)} disabled={ocupado || enCurso || (d.canal.startsWith("estable") && !d.firmada) || est.actual.cambios_locales.length > 0}
                className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Instalar ahora</button>
            </div>
          ) : <p className="text-sm text-ms-gray-90">Está al día ({d.ref ? `última del canal: ${d.ref.replace("origin/", "rama ")}` : "el canal no tiene versiones"}; buscado {d.buscado}).</p>
        )}
      </div>

      {p && (
        <div className={caja}>
          <h2 className="font-semibold text-ms-gray-130">Última actualización <Etiqueta estado={p.estado} /></h2>
          <p className="text-sm">{p.desde} → {p.hasta} · {p.inicio}{p.fin && ` – ${p.fin}`}</p>
          {p.estado === "en curso" && <p className="text-sm">Paso: <b>{p.paso}</b> (el panel puede dejar de responder un momento al reiniciarse).</p>}
          {p.error && <p className="text-sm text-ms-red whitespace-pre-wrap">{p.error}</p>}
          {p.fallos_antes !== undefined && <p className="text-xs text-ms-gray-90">Validación: {p.fallos_antes} fallos antes{p.fallos_despues !== undefined && `, ${p.fallos_despues} después`}. Registro completo: <code>{p.registro}</code></p>}
        </div>
      )}

      {p?.archivos_sistema && <ArchivosSistema informe={p.archivos_sistema} />}

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">Configuración</h2>
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={est.config.automatico} disabled={ocupado} onChange={(e) => guardar({ automatico: e.target.checked })} />
          Instalar solo cada noche las versiones nuevas firmadas</label>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>Canal:</span>
          <input value={canal} onChange={(e) => setCanal(e.target.value.trim())} className="px-2 py-1 border border-ms-gray-40 rounded text-sm font-mono w-56" />
          <button disabled={ocupado || canal === est.config.canal} onClick={() => guardar({ canal })} className="px-3 py-1 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Guardar</button>
          <span className="text-xs text-ms-gray-60">«estable» en producción. Una rama (p. ej. main) solo en servidores de prueba: sin firma.</span>
        </div>
      </div>

      {est.historial.length > 1 && (
        <div className={caja}>
          <h2 className="font-semibold text-ms-gray-130">Historial</h2>
          <ul className="text-sm space-y-1">{est.historial.map((h, i) => <li key={i} className="flex gap-2 items-center"><Etiqueta estado={h.estado} /> {h.desde} → {h.hasta} <span className="text-xs text-ms-gray-60">{h.inicio}</span>
            {h.archivos_sistema && <span className={`text-xs ${h.archivos_sistema.cambios_locales ? "text-ms-red" : "text-ms-gray-60"}`}>· {totalesArchivos(h.archivos_sistema)}</span>}</li>)}</ul>
        </div>
      )}
      {mensaje && <p className="text-sm text-ms-red">{mensaje}</p>}
    </div>
  );
}
