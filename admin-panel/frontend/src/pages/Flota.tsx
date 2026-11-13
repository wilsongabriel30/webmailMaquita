import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { CodigosAlta } from "./flota/CodigosAlta";
import { EmitirOrden } from "./flota/EmitirOrden";
import { FichaEquipo } from "./flota/FichaEquipo";
import { Inventario } from "./flota/Inventario";
import { TablaOrdenes } from "./flota/TablaOrdenes";
import { TablaRegistro } from "./flota/TablaRegistro";
import { Asiento, Catalogo, EquipoFlota, Orden, Totales } from "./flota/tipos";
import { AuditoriaTunel } from "./flota/AuditoriaTunel";

// Flota Maquita (T-88): consola de los equipos Windows propios de la Fundación. La app la app de escritorio es
// el agente: se enrola con un código de un uso, sondea sus órdenes firmadas cada 15 min y devuelve el
// resultado. Solo superadmin/admin.

type Pestana = "inventario" | "ordenes" | "tunel" | "codigos" | "registro";

export function Flota() {
  const [pestana, setPestana] = useState<Pestana>("inventario");
  const [equipos, setEquipos] = useState<EquipoFlota[]>([]);
  const [totales, setTotales] = useState<Totales | null>(null);
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [ordenes, setOrdenes] = useState<Orden[]>([]);
  const [registro, setRegistro] = useState<Asiento[]>([]);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [emitir, setEmitir] = useState<string[] | null>(null);
  const [error, setError] = useState("");

  const cargar = () => Promise.all([
    api.get<{ equipos: EquipoFlota[]; totales: Totales }>("/flota/equipos").then((r) => { setEquipos(r.equipos); setTotales(r.totales); }),
    api.get<{ ordenes: Orden[] }>("/flota/ordenes?limite=300").then((r) => setOrdenes(r.ordenes)),
    api.get<{ registro: Asiento[] }>("/flota/registro?limite=500").then((r) => setRegistro(r.registro)),
  ]).catch((e) => setError(e.message));
  useEffect(() => {
    api.get<Catalogo>("/flota/catalogo").then(setCatalogo).catch((e) => setError(e.message));
    cargar(); const t = setInterval(cargar, 60000); return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div><h1 className="text-xl font-semibold text-ms-gray-130">Flota · equipos Windows</h1>
          <p className="text-sm text-ms-gray-60">Equipos propios con la app de escritorio: inventario, órdenes firmadas y registro de cada acción.</p></div>
        <div className="flex items-center gap-3">
          <button disabled={!catalogo} onClick={() => setEmitir([])} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-40">Emitir orden</button>
          <SectionHelp titulo="Flota de equipos" items={[
            { titulo: "Solo equipos propios", desc: "Un equipo entra a la flota únicamente con un código de alta de un solo uso creado aquí por Tecnología. Sin código, la app funciona igual pero el equipo no recibe órdenes. Los equipos personales no se enrolan." },
            { titulo: "Cómo llegan las órdenes", desc: "El equipo pregunta al servidor cada 15 minutos desde su tarea de sistema (no se abren puertos en los equipos). Cada orden va firmada con la clave de Flota del servidor; el equipo rechaza cualquier orden sin firma válida, de otro equipo o caducada." },
            { titulo: "Fases", desc: "Fase 1 (activa): comprobar conexión, inventario y forzar la actualización de Teams. Fase 3 (candado de USB, cámara y micrófono): bloqueada hasta el visto bueno de protección de datos y el aviso al personal; entonces exige escribir CONFIRMO en cada orden. Nunca se captura imagen ni sonido: solo se enciende o apaga el permiso del dispositivo." },
            { titulo: "Túnel de soporte", desc: "Para atender un equipo que está fuera de la red (un hotel, datos del celular). Desde la ficha del equipo se le pide que abra, por unos minutos, una conexión de salida hacia el servidor de túneles; se cierra sola. Exige motivo y escribir CONFIRMO, y para entrar al equipo sigue haciendo falta la llave de soporte. La pestaña «Túnel de soporte» muestra quién abrió cada uno, cuándo y cuánto duró." },
            { titulo: "SSH de soporte", desc: "Las llaves van dentro del instalador. Aquí solo se muestra el estado que reporta la telemetría de cada equipo." },
            { titulo: "Registro", desc: "Toda acción (códigos, órdenes, entregas, resultados, retiros) queda en un registro que no se puede editar ni borrar, con quién la hizo, cuándo y desde dónde." },
          ]} />
        </div>
      </div>
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      {catalogo && !catalogo.firma_disponible && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">Falta la clave de firma de Flota en el servidor: no se pueden emitir órdenes.</div>}
      {totales && <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {([["Equipos gestionados", totales.enrolados], ["Agente visto en 24 h", totales.agente_hoy], ["Con Teams sin enrolar", totales.sin_enrolar],
          ["SSH de soporte activo", totales.ssh_activo], ["Retirados", totales.retirados]] as [string, number][]).map(([t, n]) => (
          <div key={t} className="rounded-lg border p-3 bg-white border-ms-gray-30"><div className="text-2xl font-semibold">{n}</div><div className="text-xs text-ms-gray-60">{t}</div></div>))}
      </div>}
      <div className="flex gap-1 border-b border-ms-gray-30">
        {([["inventario", "Inventario"], ["ordenes", "Órdenes"], ["tunel", "Túnel de soporte"], ["codigos", "Códigos de alta"], ["registro", "Registro"]] as [Pestana, string][]).map(([k, t]) => (
          <button key={k} onClick={() => { setPestana(k); setAbierto(null); }}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${pestana === k ? "border-ms-blue text-ms-blue font-medium" : "border-transparent text-ms-gray-90 hover:text-ms-gray-130"}`}>{t}</button>))}
      </div>
      {pestana === "inventario" && (abierto
        ? <FichaEquipo id={abierto} firmaDisponible={!!catalogo?.firma_disponible} onCerrar={() => setAbierto(null)} onOrden={setEmitir} onCambio={cargar} />
        : <Inventario equipos={equipos} onAbrir={setAbierto} onOrden={setEmitir} />)}
      {pestana === "ordenes" && <TablaOrdenes ordenes={ordenes} conEquipo onCambio={cargar} />}
      {pestana === "tunel" && <AuditoriaTunel />}
      {pestana === "codigos" && <CodigosAlta />}
      {pestana === "registro" && <TablaRegistro registro={registro} conEquipo />}
      {emitir && catalogo && <EmitirOrden catalogo={catalogo} equipos={equipos} seleccion={emitir}
        onCerrar={() => setEmitir(null)} onHecho={() => { setEmitir(null); setPestana("ordenes"); setAbierto(null); cargar(); }} />}
    </div>
  );
}
