import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Trabajo {
  id?: string;
  horario: string;
  orden: string;
  descripcion: string;
  activo: boolean;
  siguiente?: string | null;
  ultima?: string | null;
  resultado?: string | null;
  en_curso?: boolean;
}
interface Datos { carpeta: string; php: string; trabajos: Trabajo[] }

const COMUNES = [
  { etiqueta: "Una vez por minuto", horario: "* * * * *" },
  { etiqueta: "Cada 5 minutos", horario: "*/5 * * * *" },
  { etiqueta: "Dos veces por hora", horario: "0,30 * * * *" },
  { etiqueta: "Una vez por hora", horario: "0 * * * *" },
  { etiqueta: "Dos veces al día", horario: "0 0,12 * * *" },
  { etiqueta: "Una vez al día (3:00)", horario: "0 3 * * *" },
  { etiqueta: "Una vez a la semana (domingo 3:00)", horario: "0 3 * * 0" },
  { etiqueta: "El día 1 de cada mes (3:00)", horario: "0 3 1 * *" },
];
const CAMPOS = ["Minuto", "Hora", "Día", "Mes", "Día de la semana"];

/* Trabajos de cron del sitio, como en cPanel: horario de cinco campos, orden y salida de cada ejecución. */
export function TareasModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [lista, setLista] = useState<Trabajo[]>([]);
  const [campos, setCampos] = useState(["0", "3", "*", "*", "*"]);
  const [orden, setOrden] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [salida, setSalida] = useState<{ id: string; texto: string } | null>(null);

  const cargar = () => api.get<Datos>(`/sitios/${dominio}/tareas`).then((d) => { setDatos(d); setLista(d.trabajos); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [dominio]);

  const guardar = async (nueva: Trabajo[]) => {
    setOcupado(true); setError("");
    try {
      const d = await api.put<Datos>(`/sitios/${dominio}/tareas`, { trabajos: nueva.map(({ id, horario, orden, descripcion, activo }) => ({ id, horario, orden, descripcion, activo })) });
      setDatos(d); setLista(d.trabajos);
      return true;
    } catch (e) { setError((e as Error).message); return false; } finally { setOcupado(false); }
  };
  const agregar = async () => {
    if (await guardar([...lista, { horario: campos.join(" "), orden: orden.trim(), descripcion: descripcion.trim(), activo: true }])) {
      setOrden(""); setDescripcion("");
    }
  };
  const ejecutar = async (t: Trabajo) => {
    setError("");
    try { await api.post(`/sitios/${dominio}/tareas/${t.id}/ejecutar`); setTimeout(cargar, 2000); } catch (e) { setError((e as Error).message); }
  };
  const verSalida = async (t: Trabajo) => {
    try { const r = await api.get<{ registro: string }>(`/sitios/${dominio}/tareas/${t.id}/registro`); setSalida({ id: t.id!, texto: r.registro || "(sin salida todavía)" }); }
    catch (e) { setError((e as Error).message); }
  };
  const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4" onClick={onCerrar}>
      <div className="bg-white rounded shadow-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-base font-semibold text-ms-gray-130">Trabajos de cron de {dominio}</h2>
            <p className="text-xs text-ms-gray-90 mt-1">Ejecutan una orden o un script a la hora indicada, con el usuario del sitio y desde su carpeta pública. P. ej. borrar temporales cada semana o llamar al cron de su aplicación.</p>
          </div>
          <button onClick={onCerrar} className="text-ms-gray-90 text-sm hover:underline">Cerrar</button>
        </div>

        <div className="border border-ms-gray-30 rounded p-3 space-y-2">
          <b className="text-sm">Agregar un trabajo</b>
          <div className="flex flex-wrap items-center gap-2">
            <select onChange={(e) => e.target.value && setCampos(e.target.value.split(" "))} defaultValue="" className={campo}>
              <option value="">Configuración común…</option>
              {COMUNES.map((c) => <option key={c.horario} value={c.horario}>{c.etiqueta} ({c.horario})</option>)}
            </select>
          </div>
          <div className="grid grid-cols-5 gap-2">
            {CAMPOS.map((nombre, i) => (
              <label key={nombre} className="text-xs text-ms-gray-90">{nombre}
                <input value={campos[i]} onChange={(e) => setCampos(campos.map((c, j) => (j === i ? e.target.value.trim() : c)))} className={`${campo} w-full font-mono`} />
              </label>
            ))}
          </div>
          <input placeholder={`Orden, p. ej. ${datos?.php || "php"} ${datos?.carpeta || "publico"}/cron.php`} value={orden} onChange={(e) => setOrden(e.target.value)} className={`${campo} w-full font-mono`} />
          <input placeholder="Descripción (opcional)" maxLength={80} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className={`${campo} w-full`} />
          <button onClick={agregar} disabled={ocupado || !orden.trim()} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Agregar</button>
        </div>

        {error && <p className="text-sm text-ms-red">{error}</p>}

        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr>
            <th className="text-left px-2 py-1.5">Horario</th><th className="text-left px-2 py-1.5">Orden</th>
            <th className="text-left px-2 py-1.5">Última / próxima</th><th className="text-right px-2 py-1.5">Acciones</th></tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {lista.map((t) => (
              <tr key={t.id} className={t.activo ? "" : "opacity-60"}>
                <td className="px-2 py-1.5 font-mono text-xs whitespace-nowrap">{t.horario}</td>
                <td className="px-2 py-1.5"><div className="font-mono text-xs break-all">{t.orden}</div>{t.descripcion && <div className="text-[11px] text-ms-gray-60">{t.descripcion}</div>}</td>
                <td className="px-2 py-1.5 text-[11px]">
                  {t.en_curso ? <span className="text-ms-blue">ejecutándose…</span> : t.ultima ? <span className={t.resultado === "correcto" ? "text-ms-green" : "text-ms-red"}>{t.ultima}: {t.resultado}</span> : <span className="text-ms-gray-60">sin ejecutar</span>}
                  {t.activo && t.siguiente && <div className="text-ms-gray-60">próxima: {t.siguiente}</div>}
                  {!t.activo && <div className="text-ms-gray-60">en pausa</div>}
                </td>
                <td className="px-2 py-1.5 text-right whitespace-nowrap text-xs space-x-2">
                  <button onClick={() => ejecutar(t)} disabled={ocupado} className="text-ms-blue hover:underline">Ejecutar ahora</button>
                  <button onClick={() => verSalida(t)} className="text-ms-blue hover:underline">Salida</button>
                  <button onClick={() => guardar(lista.map((x) => (x.id === t.id ? { ...x, activo: !x.activo } : x)))} disabled={ocupado} className="text-ms-blue hover:underline">{t.activo ? "Pausar" : "Activar"}</button>
                  <button onClick={() => confirm("¿Quitar este trabajo?") && guardar(lista.filter((x) => x.id !== t.id))} disabled={ocupado} className="text-ms-red hover:underline">Quitar</button>
                </td>
              </tr>
            ))}
            {lista.length === 0 && <tr><td colSpan={4} className="px-2 py-4 text-center text-ms-gray-60 text-sm">Sin trabajos de cron.</td></tr>}
          </tbody>
        </table>

        {salida && (
          <div>
            <div className="flex justify-between text-xs mb-1"><b>Salida del trabajo</b><button onClick={() => setSalida(null)} className="hover:underline">Ocultar</button></div>
            <pre className="bg-ms-gray-20 border rounded p-2 text-[11px] max-h-64 overflow-auto whitespace-pre-wrap">{salida.texto}</pre>
          </div>
        )}
        <p className="text-[11px] text-ms-gray-60">Formato cron: minuto (0–59), hora (0–23), día (1–31), mes (1–12), día de la semana (0–6, 0 = domingo). «*» = todos, «*/15» = cada 15, «1-5» = de lunes a viernes. Cada ejecución dura como máximo una hora.</p>
      </div>
    </div>
  );
}
