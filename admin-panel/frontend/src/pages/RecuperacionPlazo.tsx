// Plazo para recuperar correos enviados: cuánto tiempo se puede retirar un correo del buzón del
// destinatario, según lo haya leído o no (19/11/2026). Antes solo estaba en el .env del correo.
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Datos {
  minutos_leidos: number;
  minutos_sin_leer: number;
  origen: "panel" | "archivo";
  actualizado: string | null;
  por: string;
  maximo: number;
}

const LEIDOS: [number, string][] = [
  [0, "No se recuperan (como el Outlook clásico)"],
  [30, "30 minutos"], [60, "1 hora"], [120, "2 horas"], [240, "4 horas"], [1440, "24 horas"],
];
const SIN_LEER: [number, string][] = [
  [0, "Sin límite de tiempo"],
  [60, "1 hora"], [1440, "24 horas"], [2880, "48 horas"], [4320, "72 horas"], [10080, "7 días"],
];

function textoMinutos(m: number): string {
  if (m % 1440 === 0) return m === 1440 ? "24 horas" : `${m / 1440} días`;
  if (m % 60 === 0) return m === 60 ? "1 hora" : `${m / 60} horas`;
  return `${m} minutos`;
}

/** Las opciones habituales y, si el valor guardado no es una de ellas, también ese valor. */
function opciones(base: [number, string][], actual: number): [number, string][] {
  return base.some(([v]) => v === actual) ? base : [...base, [actual, textoMinutos(actual)]];
}

function fecha(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}

export function RecuperacionPlazo() {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const cargar = () =>
    api.get<Datos>("/recuperacion-plazo").then(setDatos).catch(() => {}).finally(() => setCargando(false));
  useEffect(() => { cargar(); }, []);

  if (cargando) return <div className="p-6 text-ms-gray-110">Cargando…</div>;
  if (!datos) return <div className="p-6 text-red-700">No se pudo cargar la configuración.</div>;

  const incoherente = datos.minutos_sin_leer > 0 && datos.minutos_leidos > datos.minutos_sin_leer;

  const guardar = async () => {
    setGuardando(true); setMsg(null);
    try {
      await api.post("/recuperacion-plazo", {
        minutos_leidos: datos.minutos_leidos,
        minutos_sin_leer: datos.minutos_sin_leer,
      });
      setMsg({ ok: true, text: "Cambios guardados. Rigen desde la siguiente recuperación, sin reiniciar nada." });
      await cargar();
    } catch (e) {
      const detalle = (e as { message?: string })?.message;
      setMsg({ ok: false, text: detalle || "No se pudo guardar." });
    }
    setGuardando(false);
  };

  const campo = "mt-2 px-2 py-1.5 border border-ms-gray-30 rounded text-sm bg-white min-w-[280px]";
  return (
    <div className="p-6 max-w-4xl">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Plazo para recuperar correos"
          items={[
            { titulo: "Qué es", desc: "«Recuperar mensaje» retira un correo enviado por error del buzón del destinatario, esté en la carpeta que esté. Aquí se decide durante cuánto tiempo puede hacerlo quien lo envió." },
            { titulo: "Correos sin leer", desc: "Mientras nadie lo haya abierto no hay nada comunicado que proteger. Lo habitual es dejarlo sin límite: un correo enviado por error un viernes se puede retirar el lunes." },
            { titulo: "Correos ya leídos", desc: "Un correo leído ya es una constancia (una instrucción, una aprobación). Por eso su plazo es corto, o se puede impedir del todo." },
            { titulo: "Destinatarios de fuera", desc: "De un destinatario de otro servidor no se sabe si lo leyó: se le aplica el plazo de los correos ya leídos." },
            { titulo: "Registro", desc: "Cada recuperación queda en la auditoría del correo, y cada cambio de esta regla en la auditoría del panel." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-130 mb-1">Plazo para recuperar correos</h1>
      <p className="text-sm text-ms-gray-110 mb-2">Durante cuánto tiempo se puede retirar un correo enviado por error del buzón de quien lo recibió.</p>
      <p className="text-xs text-ms-gray-110 mb-6">
        {datos.origen === "panel"
          ? <>Configurado desde el panel{datos.por ? <> por <b>{datos.por}</b></> : null}{datos.actualizado ? <> el {fecha(datos.actualizado)}</> : null}.</>
          : <>Todavía no se ha guardado nada desde el panel: se muestran los valores que rigen ahora. Al guardar, manda lo que quede aquí.</>}
      </p>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-4">
        <h2 className="font-semibold text-ms-gray-130">Si el destinatario todavía no lo ha leído</h2>
        <p className="text-sm text-ms-gray-110">Recomendado: sin límite de tiempo.</p>
        <select className={campo} value={datos.minutos_sin_leer} aria-label="Plazo para correos sin leer"
          title="Durante cuánto tiempo se puede recuperar un correo que nadie ha abierto. Se aplica al pulsar Guardar cambios."
          onChange={(e) => setDatos({ ...datos, minutos_sin_leer: Number(e.target.value) })}>
          {opciones(SIN_LEER, datos.minutos_sin_leer).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </div>

      <div className="border border-ms-gray-30 rounded-lg p-4 mb-6">
        <h2 className="font-semibold text-ms-gray-130">Si el destinatario ya lo leyó</h2>
        <p className="text-sm text-ms-gray-110">Recomendado: 1 hora. Con «No se recuperan», un correo ya leído se queda en el buzón del destinatario.</p>
        <select className={campo} value={datos.minutos_leidos} aria-label="Plazo para correos ya leídos"
          title="Durante cuánto tiempo se puede recuperar un correo que el destinatario ya abrió. Se aplica al pulsar Guardar cambios."
          onChange={(e) => setDatos({ ...datos, minutos_leidos: Number(e.target.value) })}>
          {opciones(LEIDOS, datos.minutos_leidos).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
        {incoherente && <p role="alert" className="mt-2 text-xs text-red-600">El plazo de los correos ya leídos no puede ser mayor que el de los correos sin leer.</p>}
      </div>

      {msg && <div className={`mb-3 text-sm ${msg.ok ? "text-green-700" : "text-red-700"}`}>{msg.text}</div>}
      <button onClick={guardar} disabled={guardando || incoherente} title="Guarda la regla. El correo la aplica en la siguiente recuperación, sin reiniciar nada." className="px-5 py-2 bg-[#0078d4] text-white rounded font-medium disabled:opacity-50">
        {guardando ? "Guardando…" : "Guardar cambios"}
      </button>
    </div>
  );
}
