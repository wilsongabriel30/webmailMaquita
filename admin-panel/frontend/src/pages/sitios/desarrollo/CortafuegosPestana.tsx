import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { campo, type EstadoWaf, type Exclusion, type Hacer, type ModoWaf, type Suceso } from "./tipos";

const MODOS: { id: ModoWaf; nombre: string; ayuda: string }[] = [
  { id: "bloquear", nombre: "Bloquear", ayuda: "Rechaza (403) las peticiones que superan la puntuación de OWASP CRS." },
  { id: "detectar", nombre: "Solo detectar", ayuda: "Anota lo que habría bloqueado, sin bloquear: útil para probar antes." },
  { id: "apagado", nombre: "Apagado", ayuda: "Sin cortafuegos de aplicaciones en este sitio (siguen los límites por IP y fail2ban)." },
];

/* Cortafuegos de aplicaciones web del sitio: ModSecurity con las reglas OWASP CRS completas y las excepciones de la
   aplicación (WordPress, Joomla, catálogo). Cada cambio se comprueba con nginx antes de aplicarse. */
export function CortafuegosPestana({ dominio, ocupado, hacer }: { dominio: string; ocupado: boolean; hacer: Hacer }) {
  const ruta = `/sitios/${dominio}/cortafuegos`;
  const [estado, setEstado] = useState<EstadoWaf | null>(null);
  const [ajustes, setAjustes] = useState<{ modo: ModoWaf; paranoia: 1 | 2; exclusiones: Exclusion[] } | null>(null);
  const [sucesos, setSucesos] = useState<Suceso[] | null>(null);
  const [nueva, setNueva] = useState({ regla: "", ruta: "" });
  const [error, setError] = useState("");

  const poner = (e: EstadoWaf) => { setEstado(e); setAjustes({ modo: e.modo, paranoia: e.paranoia, exclusiones: e.exclusiones }); };
  const verBloqueos = () => api.get<{ sucesos: Suceso[] }>(`${ruta}/bloqueos?cuantos=50`).then((r) => setSucesos(r.sucesos)).catch((e) => setError(e.message));
  useEffect(() => { api.get<EstadoWaf>(ruta).then(poner).catch((e) => setError(e.message)); verBloqueos(); }, [dominio]);

  if (!ajustes || !estado) return <p className="text-sm text-ms-gray-60">{error || "Cargando…"}</p>;
  const excluir = (regla: number, rutaRegla: string | null) => {
    if (ajustes.exclusiones.some((x) => x.regla === regla && x.ruta === rutaRegla)) return;
    setAjustes({ ...ajustes, exclusiones: [...ajustes.exclusiones, { regla, ruta: rutaRegla }] });
  };
  const anadir = () => {
    const regla = Number(nueva.regla);
    if (!Number.isInteger(regla) || regla < 900000 || regla > 999999) { setError("El número de regla de OWASP CRS tiene 6 cifras (9xxxxx)."); return; }
    setError(""); excluir(regla, nueva.ruta.trim() || null); setNueva({ regla: "", ruta: "" });
  };
  const guardar = () => hacer("Cortafuegos guardado.", async () => poner(await api.put<EstadoWaf>(ruta, ajustes)));

  return (
    <div className="space-y-4 text-sm">
      <p className="text-xs text-ms-gray-90">Perfil de la aplicación: <strong>{estado.perfil}</strong> (sus excepciones de siempre se mantienen).</p>
      <div className="space-y-1">
        {MODOS.map((m) => (
          <label key={m.id} className="flex items-start gap-2">
            <input type="radio" name="modo-waf" checked={ajustes.modo === m.id} onChange={() => setAjustes({ ...ajustes, modo: m.id })} />
            <span><strong>{m.nombre}</strong> <span className="text-xs text-ms-gray-90">— {m.ayuda}</span></span>
          </label>
        ))}
      </div>
      <label className="flex items-center gap-2">
        Nivel de paranoia
        <select className={campo} value={ajustes.paranoia} disabled={ajustes.modo === "apagado"}
          onChange={(e) => setAjustes({ ...ajustes, paranoia: Number(e.target.value) as 1 | 2 })}>
          <option value={1}>1 — el de serie, pocos falsos positivos</option>
          <option value={2}>2 — detecta más, con más falsos positivos</option>
        </select>
      </label>

      <div className="space-y-1">
        <h3 className="font-semibold">Exclusiones ({ajustes.exclusiones.length} de {estado.maximo})</h3>
        <p className="text-xs text-ms-gray-90">Una regla que bloquea algo legítimo se puede excluir en todo el sitio o solo en una ruta. Las de puntuación de CRS no se excluyen: para no bloquear, use «Solo detectar».</p>
        <ul className="divide-y divide-ms-gray-30">
          {ajustes.exclusiones.map((x, i) => (
            <li key={`${x.regla}-${x.ruta}`} className="flex justify-between py-1">
              <span><code>{x.regla}</code> <span className="text-xs text-ms-gray-90">{x.ruta ? `solo en ${x.ruta}` : "en todo el sitio"}</span></span>
              <button onClick={() => setAjustes({ ...ajustes, exclusiones: ajustes.exclusiones.filter((_, j) => j !== i) })} className="text-ms-red hover:underline text-xs">Quitar</button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          <input className={`${campo} w-28`} placeholder="942100" inputMode="numeric" value={nueva.regla} onChange={(e) => setNueva({ ...nueva, regla: e.target.value.trim() })} />
          <input className={`${campo} flex-1 min-w-40`} placeholder="Ruta (opcional), p. ej. /wp-admin/admin-ajax.php" value={nueva.ruta} onChange={(e) => setNueva({ ...nueva, ruta: e.target.value })} />
          <button onClick={anadir} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded">Añadir</button>
        </div>
      </div>
      {error && <p className="text-ms-red">{error}</p>}
      <button disabled={ocupado} onClick={guardar} className="px-4 py-2 bg-ms-blue text-white rounded disabled:opacity-50">Guardar</button>

      <div className="border-t border-ms-gray-30 pt-3 space-y-2">
        <div className="flex justify-between items-center">
          <h3 className="font-semibold">Últimos bloqueos y detecciones</h3>
          <button onClick={verBloqueos} className="text-ms-blue hover:underline text-xs">Actualizar</button>
        </div>
        {sucesos && sucesos.length === 0 && <p className="text-xs text-ms-gray-60">Nada registrado.</p>}
        <ul className="divide-y divide-ms-gray-30 text-xs">
          {sucesos?.map((s, i) => (
            <li key={i} className="py-1.5 space-y-0.5">
              <div>
                <span className={s.accion === "bloqueado" ? "text-ms-red font-medium" : "text-amber-700 font-medium"}>{s.accion === "bloqueado" ? "Bloqueado" : "Detectado"}</span>
                {" "}{s.fecha} · {s.ip} · <code>{s.metodo} {s.ruta}</code>{s.codigo ? ` · ${s.codigo}` : ""}
              </div>
              {s.reglas.map((r) => (
                <div key={r.id} className="pl-3 flex justify-between gap-2">
                  <span><code>{r.id}</code> {r.mensaje}</span>
                  <span className="whitespace-nowrap space-x-2">
                    <button onClick={() => excluir(r.id, s.ruta || null)} className="text-ms-blue hover:underline">Excluir en esta ruta</button>
                    <button onClick={() => excluir(r.id, null)} className="text-ms-blue hover:underline">Excluir esta regla</button>
                  </span>
                </div>
              ))}
            </li>
          ))}
        </ul>
        <p className="text-xs text-ms-gray-60">Tras excluir, pulse «Guardar». No se muestran consultas ni datos enviados: pueden llevar contraseñas o datos personales.</p>
      </div>
    </div>
  );
}
