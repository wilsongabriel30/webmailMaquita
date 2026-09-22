import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { Codigos } from "./dispositivos/Codigos";
import { Equipos } from "./dispositivos/Equipos";
import { FichaEquipo } from "./dispositivos/FichaEquipo";
import { Mensajes } from "./dispositivos/Mensajes";
import { Flota } from "./dispositivos/telemetria/Flota";
import { FichaTelemetria } from "./dispositivos/telemetria/FichaTelemetria";
import { Alertas } from "./dispositivos/telemetria/Alertas";
import { Equipo } from "./dispositivos/tipos";

// Teléfonos institucionales (fase 1): inventario y asignación, último estado que reporta cada
// equipo, mensajes urgentes con acuse y códigos de enrolamiento. Los teléfonos hablan con el
// webmail (/api/dispositivos); aquí se administra.

interface Resumen { activos: number; sin_contacto: number; perdidos: number; limitados: number; eventos_sin_revisar: number }
type Pestana = "equipos" | "telemetria" | "alertas" | "mensajes" | "codigos";

export function Dispositivos() {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [res, setRes] = useState<Resumen | null>(null);
  const [pestana, setPestana] = useState<Pestana>("equipos");
  const [abierto, setAbierto] = useState<number | null>(null);
  const [error, setError] = useState("");

  const cargar = () => Promise.all([
    api.get<{ equipos: Equipo[] }>("/dispositivos/equipos").then((r) => setEquipos(r.equipos)),
    api.get<Resumen>("/dispositivos/resumen").then(setRes),
  ]).catch((e) => setError(e.message));
  useEffect(() => { cargar(); const t = setInterval(cargar, 60000); return () => clearInterval(t); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div><h1 className="text-xl font-semibold text-ms-gray-130">Teléfonos institucionales</h1>
          <p className="text-sm text-ms-gray-60">Inventario, estado y mensajes urgentes de los celulares de la organización.</p></div>
        <SectionHelp titulo="Teléfonos institucionales" items={[
          { titulo: "Cómo entra un teléfono", desc: "Se instala la app Maquita y se escribe un código de enrolamiento creado aquí. Sin código vigente no se activa la gestión. Equipo nuevo o restaurado de fábrica: control completo. Teléfono ya en uso: modo limitado (la persona puede quitar permisos o desinstalar; si lo hace, queda un evento)." },
          { titulo: "Qué reporta", desc: "Cada 15 minutos: batería, almacenamiento, red, versión de Android y de la app, Play Protect. No se leen mensajes, fotos ni contenido." },
          { titulo: "Inventario", desc: "Nombre, custodio, centro de costo, sede, IMEI, serie, factura, fecha y valor de compra. La depreciación se calcula en línea recta con la vida útil indicada (36 meses por defecto)." },
          { titulo: "Pérdida o robo", desc: "Al declarar un equipo perdido se le pide su posición, reporta cada 5 minutos y, si tiene control completo, se bloquea con un mensaje y un teléfono de contacto. Los demás teléfonos de la organización avisan si lo detectan cerca por Bluetooth. El borrado remoto es solo para superadministradores." },
          { titulo: "Ubicación y privacidad", desc: "La ubicación periódica solo se guarda si el custodio firmó la política de uso (se activa por equipo con la fecha de firma) o si el equipo está perdido. Cada consulta de ubicación pide un motivo y queda en la auditoría. Se conserva 90 días." },
          { titulo: "Respaldos", desc: "Cada noche, con Wi-Fi y cargando, el teléfono sube solo lo que cambió: fotos, videos, documentos, contactos, llamadas, SMS y la copia local de WhatsApp. Se guardan cifrados; el panel ve fechas, tamaños y totales, nunca el contenido ni los nombres. Para pasar los datos a un teléfono nuevo se autoriza la restauración desde la ficha del equipo nuevo, con motivo. Antes de reasignar o restablecer un equipo, pida el respaldo de cierre." },
          { titulo: "Mensajes urgentes", desc: "Llegan al teléfono en su siguiente reporte, a pantalla completa, y exigen tocar «Leído». Aquí se ve quién lo leyó y cuándo." },
          { titulo: "Aplicaciones", desc: "El teléfono envía su lista de apps; el servidor la cruza con las reglas (lista de bloqueo, instaladores de confianza, permisos de riesgo como accesibilidad o superposición) y avisa al custodio para desinstalar. En equipos con control completo se puede desinstalar a distancia. Play Protect debe estar activo." },
          { titulo: "Reasignación", desc: "Un teléfono pasa de una persona a otra (jefe → subordinado → técnico) sin dejar de funcionar; cada cambio queda en el historial de custodia y puede pedir el respaldo de cierre del custodio anterior. El destino del respaldo en el almacén se fija por equipo antes del primer respaldo." },
          { titulo: "Telemetría y alertas", desc: "La pestaña «Telemetría» muestra el estado técnico de cada equipo (contacto, batería, almacenamiento, red, versiones, administración, Play Protect, eventos y acuses) con gráficas por equipo, y se puede exportar a CSV. Un trabajo del servidor evalúa cada 15 minutos y avisa por correo a Tecnología (y un resumen diario a dirección) según los umbrales de la pestaña «Alertas». Dirección puede ver todo con una cuenta de rol lector (viewer) sin poder mandar comandos ni retirar equipos." },
          { titulo: "Auditoría", desc: "Códigos, ediciones, bajas, mensajes, reglas de apps y reasignaciones quedan en la auditoría del panel." },
        ]} />
      </div>
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      {res && <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {([["Activos", res.activos, false], ["Sin reportar en 24 h", res.sin_contacto, res.sin_contacto > 0], ["Perdidos o robados", res.perdidos, res.perdidos > 0],
          ["En modo limitado", res.limitados, false], ["Eventos por revisar", res.eventos_sin_revisar, res.eventos_sin_revisar > 0]] as [string, number, boolean][]).map(([t, n, alerta]) => (
          <div key={t} className={`rounded-lg border p-3 ${alerta ? "bg-red-50 border-red-200" : "bg-white border-ms-gray-30"}`}>
            <div className="text-2xl font-semibold">{n}</div><div className="text-xs text-ms-gray-60">{t}</div></div>))}
      </div>}
      <div className="flex gap-1 border-b border-ms-gray-30">
        {([["equipos", "Equipos"], ["telemetria", "Telemetría"], ["alertas", "Alertas"], ["mensajes", "Mensajes urgentes"], ["codigos", "Códigos de enrolamiento"]] as [Pestana, string][]).map(([k, t]) => (
          <button key={k} onClick={() => { setPestana(k); setAbierto(null); }}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${pestana === k ? "border-ms-blue text-ms-blue font-medium" : "border-transparent text-ms-gray-90 hover:text-ms-gray-130"}`}>{t}</button>))}
      </div>
      {pestana === "equipos" && (abierto ? <FichaEquipo id={abierto} onCerrar={() => setAbierto(null)} onCambio={cargar} /> : <Equipos equipos={equipos} onAbrir={setAbierto} />)}
      {pestana === "telemetria" && (abierto ? <FichaTelemetria id={abierto} onCerrar={() => setAbierto(null)} /> : <Flota onAbrir={setAbierto} />)}
      {pestana === "alertas" && <Alertas onAbrir={(id) => { setPestana("telemetria"); setAbierto(id); }} />}
      {pestana === "mensajes" && <Mensajes equipos={equipos} />}
      {pestana === "codigos" && <Codigos />}
    </div>
  );
}
