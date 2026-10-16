import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { AvisoPendiente } from "./cortafuegos/AvisoPendiente";
import { NOMBRE_JAULA, NOMBRE_ORIGEN, puertoCubierto, type Config, type Estado, type Origen, type Servicio } from "./cortafuegos/tipos";

const caja = "bg-white rounded border border-ms-gray-30 p-5 space-y-3";
const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

export function Cortafuegos() {
  const [est, setEst] = useState<Estado | null>(null);
  const [conf, setConf] = useState<Config | null>(null);
  const [adminTexto, setAdminTexto] = useState("");
  const [extra, setExtra] = useState({ puertos: "", protocolo: "tcp" as "tcp" | "udp", origen: "todos" as "todos" | "admin", descripcion: "" });
  const [bloqueo, setBloqueo] = useState({ red: "", motivo: "" });
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = () => api.get<Estado>("/cortafuegos").then((d) => {
    setEst(d); setConf(d.config); setAdminTexto(d.config.admin.join("\n")); setError("");
  }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const aplicar = async () => {
    if (!conf) return;
    setOcupado(true); setError("");
    try {
      await api.put("/cortafuegos", { ...conf, admin: adminTexto.split(/[\s,]+/).filter(Boolean) });
      await cargar();
    } catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };
  const confirmar = async () => { await api.post("/cortafuegos/confirmar"); cargar(); };
  const deshacer = async () => { await api.post("/cortafuegos/deshacer"); cargar(); };
  const desbloquear = async (jaula: string, ip: string) => {
    try { await api.post("/cortafuegos/desbloquear", { jaula, ip }); cargar(); } catch (e) { setError((e as Error).message); }
  };

  if (!est || !conf) return <div className="p-6 text-sm text-ms-gray-60">{error || "Cargando…"}</div>;
  const ipAdminOk = adminTexto.split(/[\s,]+/).some((a) => a && (a === est.su_ip || a.includes("/")));

  return (
    <div className="p-6 space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Cortafuegos</h1>
        <SectionHelp titulo="Cortafuegos" items={[
          { titulo: "Para qué sirve", desc: "Decide qué puertos del servidor se pueden usar desde Internet. Todo lo que no esté abierto aquí se descarta, aunque haya un programa escuchando." },
          { titulo: "Origen", desc: "«Todo Internet»: cualquiera. «Solo administración»: solo las IP o redes de la lista (SSH y panel deben quedar así). «Cerrado»: nadie." },
          { titulo: "Seguridad al cambiar", desc: "Los cambios se aplican a prueba: si no los confirma en 60 segundos, se deshacen solos. Así una regla equivocada no le deja fuera. Tampoco se acepta una configuración que le cierre el panel a su propia IP." },
          { titulo: "Puertos adicionales", desc: "Para aplicaciones propias que necesiten un puerto (p. ej. 8080). Las aplicaciones web normales no lo necesitan: se publican por los puertos 80/443." },
          { titulo: "fail2ban", desc: "IP bloqueadas automáticamente por intentos de contraseña, rastreos o abusos. Se pueden desbloquear desde aquí." },
        ]} />
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-ms-red rounded px-4 py-2 text-sm">{error}</div>}
      {!est.activo && <div className="bg-amber-50 border border-amber-200 rounded px-4 py-2 text-sm">El cortafuegos no está activo. Instálelo con <code>sudo bash deploy/webmail/instalar-app.sh cortafuegos</code>.</div>}
      {est.pendiente_hasta && <AvisoPendiente hasta={est.pendiente_hasta} onConfirmar={confirmar} onDeshacer={deshacer} />}

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">Servicios</h2>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-ms-gray-30">
            {(Object.entries(est.servicios) as [string, Servicio][]).map(([clave, s]) => (
              <tr key={clave}>
                <td className="py-2 pr-3">{s.titulo}<div className="text-xs text-ms-gray-60 font-mono">{[s.tcp && `tcp ${s.tcp.replace(":", "–")}`, s.udp && `udp ${s.udp}`].filter(Boolean).join(" · ")}</div></td>
                <td className="py-2 text-right">
                  <select value={conf.servicios[clave]} onChange={(e) => setConf({ ...conf, servicios: { ...conf.servicios, [clave]: e.target.value as Origen } })} className={campo}>
                    {(Object.keys(NOMBRE_ORIGEN) as Origen[]).map((o) => <option key={o} value={o}>{NOMBRE_ORIGEN[o]}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">IP de administración</h2>
        <p className="text-xs text-ms-gray-90">Una IP o red por línea (p. ej. 203.0.113.7 o 203.0.113.0/24). Su IP ahora: <span className="font-mono">{est.su_ip}</span></p>
        <textarea value={adminTexto} onChange={(e) => setAdminTexto(e.target.value)} rows={4} className={`${campo} w-full font-mono`} />
        {!ipAdminOk && <p className="text-xs text-amber-700">Su IP no parece estar en la lista: el panel se negará a aplicar una configuración que le deje fuera.</p>}
      </div>

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">Puertos adicionales</h2>
        {conf.extras.map((e, i) => (
          <div key={i} className="flex items-center gap-3 text-sm">
            <span className="font-mono">{e.protocolo} {e.puertos}</span><span>{NOMBRE_ORIGEN[e.origen]}</span><span className="text-ms-gray-60">{e.descripcion}</span>
            <button onClick={() => setConf({ ...conf, extras: conf.extras.filter((_, j) => j !== i) })} className="text-ms-red text-xs hover:underline ml-auto">Quitar</button>
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <input value={extra.puertos} onChange={(e) => setExtra({ ...extra, puertos: e.target.value })} placeholder="8080 o 5000-5010" className={`${campo} w-36`} />
          <select value={extra.protocolo} onChange={(e) => setExtra({ ...extra, protocolo: e.target.value as "tcp" | "udp" })} className={campo}><option>tcp</option><option>udp</option></select>
          <select value={extra.origen} onChange={(e) => setExtra({ ...extra, origen: e.target.value as "todos" | "admin" })} className={campo}>
            <option value="todos">Todo Internet</option><option value="admin">Solo administración</option></select>
          <input value={extra.descripcion} maxLength={80} onChange={(e) => setExtra({ ...extra, descripcion: e.target.value })} placeholder="Para qué es" className={`${campo} flex-1 min-w-[10rem]`} />
          <button disabled={!extra.puertos} onClick={() => { setConf({ ...conf, extras: [...conf.extras, extra] }); setExtra({ ...extra, puertos: "", descripcion: "" }); }} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Añadir</button>
        </div>
      </div>

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">Bloqueos manuales</h2>
        {conf.bloqueados.map((b, i) => (
          <div key={b.red} className="flex items-center gap-3 text-sm">
            <span className="font-mono">{b.red}</span><span className="text-ms-gray-60">{b.motivo}</span>
            <button onClick={() => setConf({ ...conf, bloqueados: conf.bloqueados.filter((_, j) => j !== i) })} className="text-ms-red text-xs hover:underline ml-auto">Quitar</button>
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <input value={bloqueo.red} onChange={(e) => setBloqueo({ ...bloqueo, red: e.target.value })} placeholder="IP o red" className={`${campo} w-48`} />
          <input value={bloqueo.motivo} maxLength={80} onChange={(e) => setBloqueo({ ...bloqueo, motivo: e.target.value })} placeholder="Motivo" className={`${campo} flex-1 min-w-[10rem]`} />
          <button disabled={!bloqueo.red} onClick={() => { setConf({ ...conf, bloqueados: [...conf.bloqueados, bloqueo] }); setBloqueo({ red: "", motivo: "" }); }} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Añadir</button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button onClick={aplicar} disabled={ocupado || !!est.pendiente_hasta} className="px-5 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">{ocupado ? "Aplicando…" : "Aplicar cambios"}</button>
        <span className="text-xs text-ms-gray-60">Se aplican a prueba durante 60 segundos.</span>
      </div>

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">Bloqueadas automáticamente (fail2ban)</h2>
        {est.fail2ban.map((j) => (
          <div key={j.jaula} className="text-sm">
            <div className="flex justify-between"><span>{NOMBRE_JAULA[j.jaula] || j.jaula}</span><span className="text-xs text-ms-gray-60">{j.bloqueadas.length} ahora · {j.total} en total</span></div>
            {j.bloqueadas.map((ip) => (
              <div key={ip} className="flex items-center gap-3 ml-4 text-xs"><span className="font-mono">{ip}</span>
                <button onClick={() => desbloquear(j.jaula, ip)} className="text-ms-blue hover:underline">Desbloquear</button></div>
            ))}
          </div>
        ))}
      </div>

      <div className={caja}>
        <h2 className="font-semibold text-ms-gray-130">Programas escuchando en el servidor</h2>
        <div className="flex flex-wrap gap-2">
          {est.escuchando.map((p) => {
            const por = puertoCubierto(conf, est.servicios, p.protocolo, p.puerto);
            return <span key={`${p.protocolo}${p.puerto}`} title={por ? `Abierto por: ${por}` : "Escucha, pero el cortafuegos no lo deja pasar"}
              className={`px-2 py-0.5 rounded text-xs font-mono ${por ? "bg-green-50 text-ms-green" : "bg-ms-gray-20 text-ms-gray-60"}`}>{p.protocolo}/{p.puerto}</span>;
          })}
        </div>
        <p className="text-xs text-ms-gray-60">En verde, accesibles desde fuera; en gris, protegidos por el cortafuegos.</p>
      </div>
    </div>
  );
}
