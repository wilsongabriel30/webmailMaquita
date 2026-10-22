import type { EstadoWazuh as Datos } from "./api";
import { Seccion, useDatos } from "./comunes";

/* Tarjeta del agente Wazuh (opcional, con manager externo: docs/WAZUH.md). */
export function EstadoWazuh() {
  const { datos, error, cargando } = useDatos<Datos>("/seguridad/wazuh");
  return (
    <Seccion titulo="Wazuh (SIEM externo, opcional)">
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {cargando && <p className="text-sm text-ms-gray-60">Consultando el agente…</p>}
      {datos && !datos.instalado && (
        <div className="text-sm text-ms-gray-90 space-y-1">
          <p>El agente Wazuh no está instalado en este servidor. Es opcional: estos tableros funcionan sin él.</p>
          <p>Para enviar los eventos a un manager Wazuh (con OpenSearch) en otra máquina:</p>
          <pre className="bg-ms-gray-10 border border-ms-gray-30 rounded p-2 text-xs overflow-x-auto">sudo WAZUH_MANAGER=siem.example.org WAZUH_REGISTRATION_PASSWORD='…' bash deploy/webmail/instalar-app.sh wazuh</pre>
          <p className="text-xs">Cómo montar el manager: docs/WAZUH.md.</p>
        </div>
      )}
      {datos?.instalado && (
        <div className="text-sm space-y-1">
          <p className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${datos.conectado ? "bg-ms-green" : "bg-ms-red"}`} />
            <b>{datos.conectado ? "Conectado" : datos.activo ? `No conectado (${datos.estado})` : "Agente detenido"}</b>
            {datos.manager && <span className="text-ms-gray-90">al manager {datos.manager}</span>}
          </p>
          <p className="text-xs text-ms-gray-90">
            Versión {datos.version || "?"} · último contacto: {datos.ultimo_contacto || "—"} · bloque propio en ossec.conf: {datos.bloque_propio ? "sí" : "no (vuelva a ejecutar instalar-app.sh wazuh)"}
          </p>
          {!datos.conectado && <p className="text-xs text-ms-red">Compruebe que el manager acepta conexiones en 1514/TCP (eventos) y 1515/TCP (registro) y la clave de registro. Registro: /var/ossec/logs/ossec.log.</p>}
        </div>
      )}
    </Seccion>
  );
}
