import { useState } from "react";
import { NavLink, useParams } from "react-router-dom";
import { useAuth } from "../../api/auth";
import { SectionHelp } from "../../components/SectionHelp";
import type { Resumen } from "./api";
import { Ajustes } from "./Ajustes";
import { Anomalias } from "./Anomalias";
import { Cumplimiento } from "./Cumplimiento";
import { EstadoWazuh } from "./EstadoWazuh";
import { FlujoCorreo } from "./FlujoCorreo";
import { InicioSesion } from "./InicioSesion";
import { Informes } from "./Informes";
import { Kpi, SelectorRango, fecha, rangoInicial, useDatos } from "./comunes";

const PESTANAS = [
  { id: "flujo", titulo: "Flujo de correo" },
  { id: "accesos", titulo: "Inicios de sesión" },
  { id: "cumplimiento", titulo: "Cumplimiento" },
  { id: "anomalias", titulo: "Anomalías" },
  { id: "informes", titulo: "Informes" },
  { id: "wazuh", titulo: "Wazuh" },
  { id: "ajustes", titulo: "Ajustes" },
];

/* Seguridad → Tableros: cabecera con las cifras de 24 h y una pestaña por tablero. */
export function Tableros() {
  const { tablero = "flujo" } = useParams();
  const { user } = useAuth();
  const [rango, setRango] = useState(rangoInicial);
  const { datos: res } = useDatos<Resumen>("/seguridad/resumen");
  const operador = user?.role === "superadmin" || user?.role === "admin";
  const conRango = ["flujo", "accesos", "cumplimiento", "informes"].includes(tablero);
  const errores = res?.recolector.resumen?.errores || [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-ms-gray-130">Tableros de seguridad</h1>
        <SectionHelp titulo="Tableros de seguridad" items={[
          { titulo: "De dónde salen los datos", desc: "Un recolector (temporizador cada 5 minutos) lee lo nuevo de los registros de Postfix y Dovecot (o del diario de systemd), del acceso de ActiveSync, de la auditoría del webmail y del panel y de las estadísticas de Rspamd, y guarda totales por hora. Las pantallas no leen registros: cargan rápido aunque haya meses de datos." },
          { titulo: "Inicios de sesión", desc: "Correctos y fallidos por servicio (webmail, IMAP, POP3, SMTP, ActiveSync y este panel) y por país con la base GeoIP local (ninguna IP sale del servidor). Los accesos internos del webmail y de ActiveSync a IMAP no se cuentan dos veces." },
          { titulo: "Anomalías", desc: "Reglas simples y explicables: país nuevo para la cuenta, varios fallos seguidos de un acceso correcto, hora inusual (webmail y panel) y muchas cuentas desde una misma IP. Las altas se avisan por correo; si nadie las reconoce, se escalan." },
          { titulo: "Reconocer y cerrar", desc: "Reconocer indica que alguien la está mirando (deja de escalar). Cerrar exige decir si se resolvió o si fue un falso positivo (con el motivo). Todo queda en la auditoría." },
          { titulo: "Informes", desc: "CSV de cada tablero y un informe completo imprimible para guardar como PDF, para auditorías de cumplimiento." },
          { titulo: "Wazuh", desc: "Opcional: el agente Wazuh puede enviar estos eventos, los de maquita-sudo, los vigilantes y la integridad de los archivos de configuración a un manager Wazuh (con OpenSearch) en otra máquina." },
        ]} />
      </div>

      {res && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <Kpi titulo="Entregados (24 h)" valor={res.correo_24h.recibidos} />
          <Kpi titulo="Enviados (24 h)" valor={res.correo_24h.enviados} />
          <Kpi titulo="Rechazados (24 h)" valor={res.correo_24h.rechazados} tono="text-ms-red" />
          <Kpi titulo="Spam (24 h)" valor={res.correo_24h.spam} tono="text-ms-orange" />
          <Kpi titulo="Accesos fallidos (24 h)" valor={res.accesos_24h.fallos} tono="text-ms-red" />
          <Kpi titulo="En cola" valor={res.cola} />
          <Kpi titulo="Alertas abiertas" valor={res.alertas_abiertas} tono={res.alertas_altas ? "text-ms-red" : undefined}
            ayuda={`${res.alertas_altas} de severidad alta`} />
        </div>
      )}
      <p className="text-xs text-ms-gray-90">
        Última pasada del recolector: {res?.recolector.ultima ? fecha(res.recolector.ultima) : "todavía ninguna (¿está activo maquita-seguridad-recolector.timer?)"}
        {errores.length > 0 && <span className="text-ms-red"> · {errores.join(" · ")}</span>}
      </p>

      <div className="flex flex-wrap gap-1 border-b border-ms-gray-30">
        {PESTANAS.map((p) => (
          <NavLink key={p.id} to={`/seguridad/tableros/${p.id}`}
            className={() => `px-3 py-2 text-sm -mb-px border-b-2 ${tablero === p.id ? "border-ms-blue text-ms-blue font-medium" : "border-transparent text-ms-gray-90 hover:text-ms-gray-130"}`}>
            {p.titulo}
          </NavLink>
        ))}
      </div>
      {conRango && <SelectorRango rango={rango} cambiar={setRango} />}

      {tablero === "flujo" && <FlujoCorreo rango={rango} />}
      {tablero === "accesos" && <InicioSesion rango={rango} />}
      {tablero === "cumplimiento" && <Cumplimiento rango={rango} />}
      {tablero === "anomalias" && <Anomalias puedeActuar={operador} />}
      {tablero === "informes" && <Informes rango={rango} />}
      {tablero === "wazuh" && <EstadoWazuh />}
      {tablero === "ajustes" && <Ajustes esSuperadmin={user?.role === "superadmin"} />}
    </div>
  );
}
