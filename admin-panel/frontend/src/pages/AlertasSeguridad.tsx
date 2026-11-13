import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { EnviosMasivos, type Envio } from "../components/EnviosMasivos";

interface Direccion { ip: string; pais: string; intentos: number; ultimo: string; servicios: string[]; bloqueada: boolean; }
interface Ataque {
  cuenta: string; direcciones: Direccion[]; intentos: number; paises: string[]; ultimo: string;
  gravedad: "alta" | "media" | "resuelta"; que_pasa: string; sugerencia: string; accion: string;
  existe: boolean; protegida: boolean; se_puede_proteger: boolean;
}
interface Respuesta { horas: number; ataques: Ataque[]; envios?: Envio[]; inicios_riesgosos: number; inicios_riesgosos_altos: number; anomalias: number; pendientes: number; }

const GRAVEDAD: Record<string, { clase: string; texto: string }> = {
  alta: { clase: "bg-red-100 text-red-700", texto: "ATAQUE" },
  media: { clase: "bg-amber-100 text-amber-800", texto: "REVISAR" },
  resuelta: { clase: "bg-green-100 text-green-700", texto: "PROTEGIDA" },
};
const fecha = (t: string) => new Date(t).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" });
const nombres = (() => { try { return new Intl.DisplayNames(["es"], { type: "region" }); } catch { return null; } })();
const pais = (c: string) => { if (!c) return "país desconocido"; if (c.toUpperCase() === "LAN") return "red interna"; try { return nombres?.of(c.toUpperCase()) || c; } catch { return c; } };

export function AlertasSeguridad() {
  const [d, setD] = useState<Respuesta | null>(null);
  const [ocupada, setOcupada] = useState("");
  const [abierta, setAbierta] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const cargar = () => api.get<Respuesta>("/alertas-seguridad").then(setD).catch((e: any) => setMsg({ ok: false, text: e?.message || "No se pudieron cargar las alertas" }));
  useEffect(() => { cargar(); }, []);

  const proteger = async (a: Ataque) => {
    if (!window.confirm(`Cerrar IMAP, POP3 y SMTP de ${a.cuenta}.\n\n${a.sugerencia}\n\nEl webmail sigue funcionando. El cambio es inmediato y se puede deshacer en «Cuentas solo webmail».`)) return;
    setOcupada(a.cuenta);
    try {
      await api.put(`/solo-webmail/${encodeURIComponent(a.cuenta)}`, { activo: true, motivo: `Intentos de adivinar la contraseña desde ${a.direcciones.length} direcciones` });
      setMsg({ ok: true, text: `${a.cuenta} quedó protegida: desde fuera su contraseña ya no sirve.` });
      await cargar();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "No se pudo proteger la cuenta" }); }
    setOcupada("");
  };

  if (!d) return <div className="p-6 text-sm text-ms-gray-110">{msg ? msg.text : "Cargando…"}</div>;
  const porRevisar = d.ataques.filter((a) => a.gravedad === "media").length;
  const envios = d.envios || [];
  const nada = d.ataques.length === 0 && envios.length === 0 && d.inicios_riesgosos === 0 && d.anomalias === 0;

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Alertas de seguridad</h1>
        <SectionHelp titulo="Alertas de seguridad" items={[
          { titulo: "Qué es esta sección", desc: "Lo que necesita su atención hoy, en una sola pantalla: cuentas cuya contraseña alguien intenta adivinar, cuentas bloqueadas por escribir a muchas personas, inicios de sesión riesgosos y anomalías abiertas." },
          { titulo: "Intentos de adivinar contraseñas", desc: "Una cuenta aparece cuando tres o más direcciones distintas fallaron su contraseña y ninguna de ellas ha entrado nunca. Es el ataque lento: pocos intentos desde muchos sitios." },
          { titulo: "Qué hace el botón", desc: "«Cerrar IMAP y SMTP» deja la cuenta como solo webmail: desde fuera la contraseña deja de servir aunque la adivinen. Es inmediato y se deshace en «Cuentas solo webmail»." },
          { titulo: "Antes de pulsarlo", desc: "Lea la sugerencia: si la persona usa Outlook o celular, esos equipos dejarán de funcionar hasta que cree una contraseña de aplicación." },
          { titulo: "Cuentas bloqueadas por escribir a muchas personas", desc: "El sistema desactiva una cuenta que envía a demasiados destinatarios en pocos minutos, porque así actúa una cuenta robada. Si fue un envío normal a una lista de la casa, «Es correcto» le da permiso para escribir a esa lista y reactiva la cuenta. Los permisos concedidos se ven y se quitan aquí mismo." },
          { titulo: "Dar permiso por adelantado", desc: "En «Permisos para escribir a listas» escriba el correo de la persona, elija la lista y pulse «Dar permiso». Hágalo antes de que envíe: así no se le bloquea. Sirve para jefaturas o áreas que escriben a listas grandes. Se puede quitar cuando ya no haga falta." },
          { titulo: "Direcciones bloqueadas", desc: "Las direcciones de fuera del país se bloquean solas en el cortafuegos; aquí se indica cuáles ya lo están." },
        ]} />
      </div>
      <p className="text-sm text-ms-gray-110 mb-4">Un vistazo diario basta: aquí está lo ocurrido en las últimas {d.horas} horas y la acción que se sugiere en cada caso.</p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-[#d13438]">{d.ataques.filter((a) => a.gravedad === "alta").length}</div><div className="text-xs text-ms-gray-110">Cuentas atacadas sin proteger{porRevisar ? ` · ${porRevisar} por revisar` : ""}</div></div>
        <Link to="/risky-logins" className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center hover:border-ms-blue"><div className="text-2xl font-bold text-ms-gray-160">{d.inicios_riesgosos}</div><div className="text-xs text-ms-gray-110">Inicios de sesión riesgosos pendientes{d.inicios_riesgosos_altos ? ` (${d.inicios_riesgosos_altos} de riesgo alto)` : ""} — ver</div></Link>
        <Link to="/seguridad/tableros" className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center hover:border-ms-blue"><div className="text-2xl font-bold text-ms-gray-160">{d.anomalias}</div><div className="text-xs text-ms-gray-110">Anomalías abiertas — ver</div></Link>
      </div>

      {nada && <div className="bg-white border border-ms-gray-30 rounded-lg p-5 text-sm text-ms-gray-130">Sin alertas: nadie está intentando adivinar contraseñas y no hay nada pendiente de revisar.</div>}

      <EnviosMasivos envios={envios} alCambiar={cargar} avisar={(ok, text) => setMsg({ ok, text })} />

      {d.ataques.length > 0 && <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Intentos de adivinar contraseñas</h2>}
      <div className="space-y-3">
        {d.ataques.map((a) => (
          <div key={a.cuenta} className="bg-white border border-ms-gray-30 rounded-lg p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs rounded px-2 py-0.5 ${GRAVEDAD[a.gravedad]?.clase}`}>{GRAVEDAD[a.gravedad]?.texto}</span>
                  <span className="text-sm font-semibold text-ms-gray-160">{a.cuenta}</span>
                  <span className="text-xs text-ms-gray-110">último intento hacia {fecha(a.ultimo)} · desde {a.paises.map(pais).join(", ") || "país desconocido"}</span>
                </div>
                <p className="text-sm text-ms-gray-130 mt-2">{a.que_pasa}</p>
                <p className="text-sm text-ms-gray-160 mt-1"><b>Sugerencia:</b> {a.sugerencia}</p>
              </div>
              {a.accion === "proteger" && a.se_puede_proteger && (
                <button onClick={() => proteger(a)} disabled={ocupada === a.cuenta} className="shrink-0 px-3 py-2 bg-red-600 text-white rounded text-xs disabled:opacity-50" title="Deja la cuenta como solo webmail: desde fuera la contraseña deja de servir. Pide confirmación.">Cerrar IMAP y SMTP</button>
              )}
            </div>
            <button onClick={() => setAbierta(abierta === a.cuenta ? "" : a.cuenta)} aria-expanded={abierta === a.cuenta} className="text-xs text-ms-blue mt-2">{abierta === a.cuenta ? "Ocultar" : "Ver"} las {a.direcciones.length} direcciones</button>
            {abierta === a.cuenta && (
              <table className="w-full text-xs mt-2">
                <thead><tr className="text-left text-ms-gray-110"><th className="py-1">Dirección</th><th>País</th><th>Intentos</th><th>Por</th><th>Último</th><th>Estado</th></tr></thead>
                <tbody>{a.direcciones.map((x) => (
                  <tr key={x.ip} className="border-t border-ms-gray-10"><td className="py-1 font-mono">{x.ip}</td><td>{pais(x.pais)}</td><td>{x.intentos}</td><td>{x.servicios.join(", ").toUpperCase()}</td><td>{fecha(x.ultimo)}</td><td>{x.bloqueada ? "Bloqueada" : "Sin bloquear"}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
