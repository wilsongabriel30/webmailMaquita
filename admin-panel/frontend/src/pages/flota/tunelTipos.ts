// Túnel de soporte (T-120): tipos y textos compartidos por la ficha del equipo y la auditoría.

export interface AjustesTunel {
  host_fuera: string; host_red: string; puerto_ssh: number; usuario: string; puerto_min: number; puerto_max: number;
  minutos_min: number; minutos_max: number; minutos_def: number; duraciones: number[]; horas_validez: number; automatico: boolean;
}
export type Situacion = "solicitado" | "abriendo" | "abierto" | "cierre_solicitado" | "cerrado" | "caducada" | "no_abierto";
export interface Tunel {
  orden_id: string; equipo_id: string; nombre: string; estado: string; motivo: string; emitida_por: string; emitida_en: string;
  caduca_en: string; resultado_en?: string | null; registro?: string; ip_panel?: string | null; situacion: Situacion;
  parametros: { host?: string; puerto_remoto?: number; minutos?: number; modo?: string; clave_en_orden?: boolean; clave_huella?: string; clave_eliminada_en?: string };
  abierto_en?: string | null; expira_en?: string | null; cerrado_en?: string | null; cierre?: string | null; duracion_s?: number | null;
  cierre_por?: string | null; cierre_motivo?: string | null; cierre_estado?: string | null;
}
export interface EstadoTunel { tunel: Tunel | null; puerto_asignado: number | null; puerto_sugerido: number; ajustes: AjustesTunel }

export const SITUACION: Record<Situacion, string> = {
  solicitado: "Solicitado: esperando al equipo", abriendo: "El equipo lo está abriendo", abierto: "Abierto",
  cierre_solicitado: "Abierto: cierre solicitado", cerrado: "Cerrado", caducada: "No se abrió: el equipo no recogió la orden a tiempo",
  no_abierto: "No se abrió",
};
export const COLOR_SITUACION: Record<Situacion, string> = {
  solicitado: "text-amber-700", abriendo: "text-amber-700", abierto: "text-green-700", cierre_solicitado: "text-green-700",
  cerrado: "text-ms-gray-90", caducada: "text-red-700", no_abierto: "text-red-700",
};
export const CIERRE: Record<string, string> = {
  "automático": "Se cerró solo al cumplirse el tiempo", "orden de cierre": "Cerrado desde el panel", "nueva apertura": "Lo reemplazó una apertura nueva",
};

export function duracion(segundos?: number | null): string {
  if (segundos == null) return "—";
  const h = Math.floor(segundos / 3600), m = Math.floor((segundos % 3600) / 60), s = segundos % 60;
  return h ? `${h} h ${m} min` : m ? `${m} min ${s} s` : `${s} s`;
}
