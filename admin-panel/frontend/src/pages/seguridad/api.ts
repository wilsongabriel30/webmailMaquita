/* Tipos y llamadas de Seguridad → Tableros (backend: admin-panel/backend/app/seguridad/). */

export interface Rango { desde: string; hasta: string }

export interface PuntoFlujo {
  t: string; recibidos: number; enviados: number; rebotados: number; diferidos: number; rechazados: number;
  rechazados_filtro: number; analizados: number; spam_rechazado: number; spam_marcado: number; spam_aplazado: number;
  en_cola: number;
}
export interface Flujo { paso: string; serie: PuntoFlujo[]; totales: Partial<Record<keyof PuntoFlujo, number>>; cola_actual: number | null }

export interface PuntoAcceso { t: string; servicio: string; ok: number; fallos: number }
export interface TopIp { ip: string; pais: string; fallos: number; ok: number; cuentas: number; servicios: string[]; ultima: string }
export interface TopCuenta { cuenta: string; fallos: number; ok: number; ips: number; paises: number; ultima: string }
export interface Accesos {
  paso: string; serie: PuntoAcceso[];
  por_servicio: { servicio: string; ok: number; fallos: number }[];
  por_pais: { pais: string; ok: number; fallos: number }[];
  top_ips: TopIp[]; top_cuentas: TopCuenta[];
}

type Filas = Record<string, any>[] | null;
export interface Cumplimiento {
  busquedas: Filas; exportaciones: Filas; politicas: Filas; acciones: Filas; recientes: Filas; webmail: Filas;
  retenciones: { activas: number; puestas: number; liberadas: number } | null;
}

export interface Alerta {
  id: number; regla: string; severidad: "baja" | "media" | "alta"; cuenta: string; ip: string; pais: string;
  servicio: string; descripcion: string; detalles: Record<string, unknown>; repeticiones: number;
  estado: "abierta" | "reconocida" | "cerrada"; resolucion: string | null; nota: string | null;
  creada: string; ultima_vez: string; avisada: boolean; escalada_en: string | null;
  reconocida_por: string | null; reconocida_en: string | null; cerrada_por: string | null; cerrada_en: string | null;
}

export interface Resumen {
  correo_24h: { recibidos: number; enviados: number; rechazados: number; spam: number };
  accesos_24h: { ok: number; fallos: number };
  cola: number | null; alertas_abiertas: number; alertas_altas: number;
  recolector: { ultima: string | null; resumen: { errores?: string[]; duracion_ms?: number; fuentes?: Record<string, unknown> } | null };
}

export interface ConfigTableros {
  retencion_dias: number; retencion_detalle_dias: number; zona_horaria: string; zona_efectiva?: string;
  regla_pais_nuevo: boolean; regla_fallos_y_exito: boolean; regla_hora_inusual: boolean; regla_muchas_cuentas_ip: boolean;
  umbral_fallos: number; ventana_fallos_min: number; umbral_cuentas_ip: number; hora_min_historial: number;
  hora_porcentaje_max: number; avisos: boolean; aviso_severidad_minima: "baja" | "media" | "alta";
  avisos_por_hora: number; escalar_tras_horas: number;
}

export interface EstadoWazuh {
  instalado: boolean; activo?: boolean; estado?: string; conectado?: boolean; ultimo_contacto?: string;
  manager?: string; version?: string; bloque_propio?: boolean;
}

export function consulta(r: Rango, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams({ desde: r.desde, hasta: r.hasta, ...extra });
  return p.toString();
}

/* Descarga con el vale de sesión en la cabecera (un <a href> no lo enviaría). */
async function traer(ruta: string): Promise<Blob> {
  const token = localStorage.getItem("admin_token") || "";
  const res = await fetch(`/api${ruta}`, { headers: { "X-Admin-Token": token } });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.blob();
}

export async function descargar(ruta: string, nombre: string): Promise<void> {
  const url = URL.createObjectURL(await traer(ruta));
  const a = document.createElement("a");
  a.href = url; a.download = nombre; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/* Informe imprimible: se carga en un marco oculto y se abre el diálogo de impresión («Guardar como PDF»). */
export async function imprimir(ruta: string): Promise<void> {
  const html = await (await traer(ruta)).text();
  const marco = document.createElement("iframe");
  marco.style.position = "fixed"; marco.style.width = "0"; marco.style.height = "0"; marco.style.border = "0";
  marco.setAttribute("sandbox", "allow-modals allow-same-origin");
  document.body.appendChild(marco);
  marco.srcdoc = html;
  marco.onload = () => {
    marco.contentWindow?.focus();
    marco.contentWindow?.print();
    setTimeout(() => marco.remove(), 60000);
  };
}
