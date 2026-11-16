// Recuperación entre servidores: qué se hace con los correos ya leídos cuando otro servidor pide
// retirarlos (16/11/2026). Antes solo se podía cambiar en el .env del correo.
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

// La misma regla que valida el servidor (admin-panel/backend/app/recuperacion_servidores/dominios.py).
const ES_DOMINIO = /^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

interface Solicitud {
  fecha: string; remitente: string; message_id: string; ip: string | null; dominio: string | null;
  destinatario: string | null; resultado: string | null; leido: boolean | null; retirado: boolean;
}
interface Datos {
  retirar_leidos: boolean;
  dominios_confianza: string[];
  origen: "panel" | "archivo";
  actualizado: string | null;
  por: string;
  dominios_propios: string[];
  solicitudes: Solicitud[];
}

function Toggle({ on, onClick, title }: { on: boolean; onClick: () => void; title?: string }) {
  return (
    <button onClick={onClick} title={title} className={`relative w-11 h-6 rounded-full transition shrink-0 ${on ? "bg-[#0078d4]" : "bg-ms-gray-40"}`}>
      <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition ${on ? "translate-x-5" : ""}`} />
    </button>
  );
}

function fecha(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}

function textoResultado(s: Solicitud): string {
  if (s.retirado) return s.leido ? "Retirado (ya lo había leído)" : "Retirado";
  const r = s.resultado || "";
  if (r.startsWith("leido_no_retirado")) return "No retirado: ya lo había leído";
  if (r.startsWith("fuera_de_plazo")) return "No retirado: fuera de plazo";
  return "No retirado";
}

export function RecuperacionServidores() {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [nuevo, setNuevo] = useState("");
  const [errorNuevo, setErrorNuevo] = useState("");

  const cargar = () =>
    api.get<Datos>("/recuperacion-servidores").then(setDatos).catch(() => {}).finally(() => setCargando(false));
  useEffect(() => { cargar(); }, []);

  const agregar = () => {
    if (!datos) return;
    const partes = nuevo.split(/[\s,;]+/).map((d) => d.trim().toLowerCase().replace(/^@/, "")).filter(Boolean);
    const lista = [...datos.dominios_confianza];
    const rechazados: string[] = [];
    for (const d of partes.map((p) => p.replace(/\.$/, ""))) {
      if (!ES_DOMINIO.test(d)) rechazados.push(d);
      else if (!lista.includes(d)) lista.push(d);
    }
    setDatos({ ...datos, dominios_confianza: lista });
    // Lo que no es un dominio no entra en la lista: se queda en el campo para corregirlo.
    setNuevo(rechazados.join(" "));
    setErrorNuevo(rechazados.length
      ? `No parece un dominio: ${rechazados.map((r) => `«${r}»`).join(", ")}. Escriba solo el dominio, por ejemplo socio.org.`
      : "");
  };

  const guardar = async () => {
    if (!datos) return;
    setGuardando(true); setMsg(null);
    try {
      await api.post("/recuperacion-servidores", {
        retirar_leidos: datos.retirar_leidos,
        dominios_confianza: datos.dominios_confianza,
      });
      setMsg({ ok: true, text: "Cambios guardados. Rigen desde la siguiente solicitud, sin reiniciar nada." });
      await cargar();
    } catch (e) {
      const detalle = (e as { message?: string })?.message;
      setMsg({ ok: false, text: detalle || "No se pudo guardar." });
    }
    setGuardando(false);
  };

  if (cargando) return <div className="p-6 text-ms-gray-110">Cargando…</div>;
  if (!datos) return <div className="p-6 text-red-700">No se pudo cargar la configuración.</div>;

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Recuperación entre servidores"
          items={[
            { titulo: "Qué es", desc: "«Recuperar mensaje» retira un correo enviado por error del buzón del destinatario. Entre servidores distintos que usan esta suite, el servidor del remitente se lo pide al del destinatario. Aquí se decide qué hace ESTE servidor cuando el pedido llega de otro." },
            { titulo: "Correos ya leídos", desc: "Por defecto no se retira un correo que la persona ya leyó: se queda en su buzón y recibe el aviso de «enviado por error». Lo no leído se retira siempre, dentro del plazo." },
            { titulo: "Dominios de confianza", desc: "A los dominios de esta lista sí se les permite retirar correos ya leídos. Se compara el dominio del remitente, que este servidor ya autenticó al recibir el correo." },
            { titulo: "Dentro de este servidor", desc: "Entre los dominios alojados aquí no cambia nada: la recuperación funciona igual aunque el correo se haya leído." },
            { titulo: "Registro", desc: "Toda solicitud confirmada de otro servidor queda anotada, se retire o no, aunque a la persona no se le muestre nada." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-130 mb-1">Recuperación entre servidores</h1>
      <p className="text-sm text-ms-gray-110 mb-2">Qué hace este servidor cuando otro servidor pide retirar un correo que una persona de aquí ya leyó.</p>
      <p className="text-xs text-ms-gray-110 mb-6">
        {datos.origen === "panel"
          ? <>Configurado desde el panel{datos.por ? <> por <b>{datos.por}</b></> : null}{datos.actualizado ? <> el {fecha(datos.actualizado)}</> : null}.</>
          : <>Todavía no se ha guardado nada desde el panel: se muestran los valores del archivo de configuración del correo. Al guardar, manda lo que quede aquí.</>}
      </p>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-ms-gray-130">Retirar correos ya leídos a pedido de cualquier servidor</h2>
            <p className="text-sm text-ms-gray-110">Desactivado (recomendado): un correo ya leído no se retira, salvo que venga de un dominio de confianza. Activado: se retira aunque se haya leído, lo pida quien lo pida.</p>
          </div>
          <Toggle on={datos.retirar_leidos} onClick={() => setDatos({ ...datos, retirar_leidos: !datos.retirar_leidos })}
            title="Activado: cualquier servidor compatible puede retirar correos ya leídos de los buzones de este servidor, dentro del plazo. Se aplica al pulsar Guardar cambios." />
        </div>
      </div>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-6">
        <h2 className="font-semibold text-ms-gray-130">Dominios de confianza</h2>
        <p className="text-sm text-ms-gray-110">A estos dominios sí se les permite retirar correos ya leídos{datos.retirar_leidos ? " (ahora mismo se permite a todos; la lista se usará si desactiva la opción de arriba)" : ""}.</p>
        <div className="flex flex-wrap gap-1 mt-3">
          {datos.dominios_confianza.length === 0 && <span className="text-xs text-ms-gray-110 italic">Ninguno: a ningún otro servidor se le retiran correos ya leídos.</span>}
          {datos.dominios_confianza.map((d) => (
            <span key={d} className="px-2 py-0.5 bg-blue-50 text-blue-800 rounded text-xs flex items-center gap-1">
              {d}
              <button onClick={() => setDatos({ ...datos, dominios_confianza: datos.dominios_confianza.filter((x) => x !== d) })}
                title={`Quita «${d}» de los dominios de confianza. Se aplica al pulsar Guardar cambios.`}
                className="text-blue-500 hover:text-red-600 font-bold">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <input value={nuevo} onChange={(e) => { setNuevo(e.target.value); setErrorNuevo(""); }} aria-invalid={!!errorNuevo} onKeyDown={(e) => { if (e.key === "Enter") agregar(); }}
            placeholder="agregar dominio (ej. socio.org); puede pegar varios separados por coma"
            title="Escriba solo el dominio, sin @ ni nombre de persona. Puede pegar varios separados por coma o espacio."
            className={`px-2 py-1 border rounded text-sm flex-1 ${errorNuevo ? "border-red-500" : "border-ms-gray-30"}`} />
          <button onClick={agregar} title="Agrega el dominio a la lista. El cambio se aplica al pulsar Guardar cambios."
            className="px-3 py-1 bg-ms-gray-20 rounded text-sm">Agregar</button>
        </div>
        {errorNuevo && <p role="alert" className="mt-1 text-xs text-red-600">{errorNuevo}</p>}
        {datos.dominios_propios.length > 0 && (
          <p className="mt-3 text-xs text-ms-gray-110">Los dominios alojados en este servidor ({datos.dominios_propios.join(", ")}) no hace falta ponerlos: entre ellos la recuperación ya funciona.</p>
        )}
      </div>

      {msg && <div className={`mb-3 text-sm ${msg.ok ? "text-green-700" : "text-red-700"}`}>{msg.text}</div>}
      <button onClick={guardar} disabled={guardando} title="Guarda la política. El correo la aplica en la siguiente solicitud, sin reiniciar nada." className="px-5 py-2 bg-[#0078d4] text-white rounded font-medium disabled:opacity-50">
        {guardando ? "Guardando…" : "Guardar cambios"}
      </button>

      <h2 className="font-semibold text-ms-gray-130 mt-8 mb-1">Solicitudes recibidas de otros servidores</h2>
      <p className="text-sm text-ms-gray-110 mb-3">Las últimas {datos.solicitudes.length || ""} solicitudes confirmadas, se haya retirado el correo o no.</p>
      {datos.solicitudes.length === 0 ? (
        <p className="text-sm text-ms-gray-110 italic">Todavía no hay solicitudes registradas.</p>
      ) : (
        <div className="overflow-x-auto border border-ms-gray-30 rounded-lg">
          <table className="w-full text-xs">
            <thead className="bg-ms-gray-10 text-ms-gray-110 text-left">
              <tr><th className="px-3 py-2">Fecha</th><th className="px-3 py-2">Pidió</th><th className="px-3 py-2">Buzón de aquí</th><th className="px-3 py-2">Resultado</th><th className="px-3 py-2">Desde</th></tr>
            </thead>
            <tbody>
              {datos.solicitudes.map((s, i) => (
                <tr key={i} className="border-t border-ms-gray-20" title={`Message-ID: ${s.message_id}`}>
                  <td className="px-3 py-2 whitespace-nowrap">{fecha(s.fecha)}</td>
                  <td className="px-3 py-2">{s.remitente}</td>
                  <td className="px-3 py-2">{s.destinatario || "—"}</td>
                  <td className={`px-3 py-2 ${s.retirado ? "text-green-700" : "text-ms-gray-130"}`}>{textoResultado(s)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{s.ip || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
