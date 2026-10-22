import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { ConfigTableros } from "./api";
import { Seccion, useDatos } from "./comunes";

const entrada = "w-24 px-2 py-1 border border-ms-gray-30 rounded text-sm";

/* Ajustes de los tableros: retención, reglas de anomalía y avisos. Solo superadmin puede guardar. */
export function Ajustes({ esSuperadmin }: { esSuperadmin: boolean }) {
  const { datos, error } = useDatos<ConfigTableros>("/seguridad/config");
  const [cfg, setCfg] = useState<ConfigTableros | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  useEffect(() => { if (datos) setCfg(datos); }, [datos]);
  if (error) return <p className="text-sm text-ms-red">{error}</p>;
  if (!cfg) return <p className="text-sm text-ms-gray-60">Cargando…</p>;

  const num = (k: keyof ConfigTableros, titulo: string, ayuda: string) => (
    <label className="flex items-center justify-between gap-3 py-1" title={ayuda}>
      <span className="text-sm">{titulo}</span>
      <input type="number" value={cfg[k] as number} disabled={!esSuperadmin} className={entrada}
        onChange={(e) => setCfg({ ...cfg, [k]: Number(e.target.value) })} />
    </label>
  );
  const si = (k: keyof ConfigTableros, titulo: string, ayuda: string) => (
    <label className="flex items-start gap-2 py-1" title={ayuda}>
      <input type="checkbox" checked={cfg[k] as boolean} disabled={!esSuperadmin} className="mt-1"
        onChange={(e) => setCfg({ ...cfg, [k]: e.target.checked })} />
      <span className="text-sm">{titulo}<span className="block text-xs text-ms-gray-90">{ayuda}</span></span>
    </label>
  );
  const guardar = async () => {
    setMsg(null);
    try {
      const { zona_efectiva: _z, ...cuerpo } = cfg;
      const r = await api.put<ConfigTableros>("/seguridad/config", cuerpo);
      setCfg({ ...cfg, ...r }); setMsg({ ok: true, texto: "Configuración guardada (queda en la auditoría)." });
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
  };

  return (
    <div className="space-y-4 max-w-4xl">
      {!esSuperadmin && <p className="text-xs text-ms-gray-90">Solo un superadministrador puede cambiar estos ajustes.</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Seccion titulo="Reglas de anomalía">
          {si("regla_pais_nuevo", "País nuevo", "Acceso correcto desde un país del que la cuenta nunca había entrado (la primera vez solo aprende).")}
          {si("regla_fallos_y_exito", "Fallos seguidos de acceso", "Varios intentos fallidos y luego uno correcto: la clave pudo ser adivinada.")}
          {num("umbral_fallos", "Fallos mínimos", "Cuántos fallos dentro de la ventana disparan la regla.")}
          {num("ventana_fallos_min", "Ventana (minutos)", "Tiempo en el que se cuentan los fallos.")}
          {si("regla_hora_inusual", "Hora inusual (webmail y panel)", "Entrada desde fuera de la red interna a una hora en la que la cuenta casi nunca entra.")}
          {num("hora_min_historial", "Historial mínimo (accesos)", "Accesos necesarios de una cuenta antes de juzgar sus horas.")}
          {num("hora_porcentaje_max", "Porcentaje máximo a esa hora", "Por debajo de este % de sus accesos (± 1 h) se considera inusual.")}
          {si("regla_muchas_cuentas_ip", "Muchas cuentas desde una IP", "Una IP prueba muchas cuentas distintas en una hora (diccionario o rociado de claves).")}
          {num("umbral_cuentas_ip", "Cuentas mínimas por IP", "Cuentas distintas en la última hora.")}
        </Seccion>
        <div className="space-y-4">
          <Seccion titulo="Avisos y escalamiento">
            {si("avisos", "Avisar por correo", "Con los vigilantes del servidor (lib-avisos.sh): ORG_CORREOS_AVISOS o el aviso de Protección de salida.")}
            <label className="flex items-center justify-between gap-3 py-1">
              <span className="text-sm">Severidad mínima del aviso</span>
              <select value={cfg.aviso_severidad_minima} disabled={!esSuperadmin} className="px-2 py-1 border border-ms-gray-30 rounded text-sm"
                onChange={(e) => setCfg({ ...cfg, aviso_severidad_minima: e.target.value as ConfigTableros["aviso_severidad_minima"] })}>
                <option value="alta">Alta</option><option value="media">Media</option><option value="baja">Baja</option>
              </select>
            </label>
            {num("avisos_por_hora", "Avisos por hora (máximo)", "Para no inundar el buzón de TI; lo demás queda en el panel.")}
            {num("escalar_tras_horas", "Escalar tras (horas)", "Una alerta alta sin reconocer se vuelve a avisar como ESCALADA (también a ORG_CORREOS_ESCALAMIENTO). 0 = sin escalamiento.")}
          </Seccion>
          <Seccion titulo="Retención y zona horaria">
            {num("retencion_dias", "Retención de resúmenes (días)", "Totales por hora y alertas cerradas.")}
            {num("retencion_detalle_dias", "Retención del detalle (días)", "Detalle por cuenta e IP (para los «top» y las reglas).")}
            <label className="flex items-center justify-between gap-3 py-1" title="Vacío: la del servidor. Ejemplo: America/Guayaquil">
              <span className="text-sm">Zona horaria <span className="text-xs text-ms-gray-90">(ahora: {cfg.zona_efectiva})</span></span>
              <input value={cfg.zona_horaria} disabled={!esSuperadmin} placeholder="la del servidor" className="w-44 px-2 py-1 border border-ms-gray-30 rounded text-sm"
                onChange={(e) => setCfg({ ...cfg, zona_horaria: e.target.value })} />
            </label>
          </Seccion>
        </div>
      </div>
      {esSuperadmin && <button onClick={guardar} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Guardar</button>}
      {msg && <p className={`text-sm ${msg.ok ? "text-ms-green" : "text-ms-red"}`}>{msg.texto}</p>}
    </div>
  );
}
