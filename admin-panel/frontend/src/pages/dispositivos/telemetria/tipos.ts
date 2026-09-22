// Tipos y ayudas del portal de telemetría (telemetría del equipo, nunca de la persona).

export interface AlertaCorta { tipo: string; desde: string }
export interface EquipoFlota {
  id: number; nombre: string; fabricante?: string; modelo?: string; custodio_email?: string; custodio_nombre?: string;
  sede?: string; centro_costo?: string; estado: string; modo: "propietario" | "limitado"; ultimo_contacto?: string;
  bateria?: number; cargando?: boolean; almacenamiento_libre?: number; almacenamiento_total?: number; almacenamiento_pct?: number | null;
  red?: string; version_app?: string; version_atrasada: boolean; android?: string; play_protect?: boolean | null; admin_activo?: boolean | null;
  semaforo: "verde" | "amarillo" | "rojo"; eventos_rojos_7d: number; eventos_sin_revisar: number; urgentes_sin_acuse: number;
  alertas_abiertas: number; alertas?: AlertaCorta[] | null;
}
export interface Flota { publicada: { versionName?: string; versionCode?: number; fecha?: string }; totales: { equipos: number; reportando_hoy: number; rojo: number; con_alertas: number }; equipos: EquipoFlota[] }

export interface Alerta {
  id: number; equipo_id: number; tipo: string; detalle: Record<string, any>; desde: string; hasta?: string; avisada_en?: string;
  nombre?: string; fabricante?: string; modelo?: string; custodio_nombre?: string; custodio_email?: string; sede?: string;
}
export interface ConfigAlertas {
  activo: boolean; sin_reportar_horas: number; bateria_pct: number; bateria_horas: number; almacenamiento_pct: number;
  version_atrasada_dias: number; acuse_horas: number; correo_ti: string; resumen_diario_para: string; resumen_hora: string;
}

export const NOMBRE_ALERTA: Record<string, string> = {
  sin_reportar: "Sin reportar", bateria_baja: "Batería baja sostenida", almacenamiento_bajo: "Almacenamiento casi lleno",
  version_atrasada: "App desactualizada", admin_desactivado: "Quitaron a la app como administradora",
  desinstalacion_intento: "Intento de desinstalar la app", sim_cambiada: "Cambio de SIM", play_protect_apagado: "Play Protect apagado",
  mensaje_sin_acuse: "Mensaje urgente sin acuse",
};

export const COLOR_SEMAFORO: Record<string, string> = { verde: "bg-green-500", amarillo: "bg-amber-400", rojo: "bg-red-500" };

export function describirAlerta(a: Alerta): string {
  const d = a.detalle || {};
  switch (a.tipo) {
    case "sin_reportar": return `sin reportar desde ${d.ultimo_contacto ? fechaCorta(d.ultimo_contacto) : "nunca"} (más de ${d.horas} h)`;
    case "bateria_baja": return `batería en ${d.bateria} % sin cargar por más de ${d.horas} h`;
    case "almacenamiento_bajo": return `queda ${d.libre_pct} % libre (${d.libre_gb} GB)`;
    case "version_atrasada": return `tiene ${d.tiene}, publicada ${d.publicada} hace ${d.dias} días`;
    case "mensaje_sin_acuse": return `mensaje urgente sin acuse desde ${fechaCorta(d.desde)}`;
    case "play_protect_apagado": return "Google Play Protect apagado";
    default: return `evento de seguridad el ${fechaCorta(d.ultimo)}, pendiente de revisar`;
  }
}

export const fechaCorta = (v?: string) => (v ? new Date(v).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—");
export const gb = (b?: number | null) => (b || b === 0 ? `${(b / 1073741824).toFixed(1)} GB` : "—");

/** Descarga un GET autenticado como archivo (el CSV de la flota). */
export async function descargar(path: string, nombre: string) {
  const token = localStorage.getItem("admin_token");
  const r = await fetch(`/api${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a"); a.href = url; a.download = nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function rolActual(): string {
  try { return JSON.parse(localStorage.getItem("admin_user") || "{}").role || "viewer"; } catch { return "viewer"; }
}
