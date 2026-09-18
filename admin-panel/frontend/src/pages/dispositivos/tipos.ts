export interface Depreciacion {
  meses_transcurridos: number; vida_util_meses: number;
  depreciacion_acumulada: number; valor_en_libros: number; totalmente_depreciado: boolean;
}
export interface Equipo {
  id: number; id_instalacion: string; modo: "propietario" | "limitado";
  estado: "activo" | "revocado" | "perdido" | "baja";
  fabricante?: string; modelo?: string; serie?: string; imei?: string; android?: string; version_app?: string;
  nombre: string; custodio_email?: string; custodio_nombre?: string; centro_costo?: string; sede?: string;
  fecha_compra?: string; valor_compra?: number; vida_util_meses: number; factura_ref?: string; notas?: string;
  enrolado_en: string; ultimo_contacto?: string; ultima_ip?: string; bateria?: number; cargando?: boolean;
  almacenamiento_libre?: number; almacenamiento_total?: number; red?: string; play_protect?: boolean;
  revocado_en?: string; revocado_motivo?: string; depreciacion?: Depreciacion | null;
  ubicacion_autorizada?: boolean; politica_firmada_en?: string;
  perdido_en?: string; perdido_motivo?: string; perdido_mensaje?: string; perdido_telefono?: string;
  carpeta_respaldo?: string;
}
export interface Evento { id: number; tipo: string; detalle: Record<string, unknown>; recibido_en: string; visto_por?: string; visto_en?: string }
export interface Latido { recibido_en: string; ip?: string; datos: Record<string, unknown> }
export interface MensajeEquipo { id: number; titulo: string; nivel: string; creado_en: string; entregado_en?: string; leido_en?: string }

export const fechaHora = (v?: string) => (v ? new Date(v).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—");
export const gigas = (b?: number) => (b || b === 0 ? `${(b / 1073741824).toFixed(1)} GB` : "—");
export const dinero = (n?: number) => (n || n === 0 ? n.toLocaleString("es-EC", { style: "currency", currency: "USD" }) : "—");

/** Hace cuánto reportó: texto y si ya es preocupante (más de un día). */
export function haceCuanto(v?: string): { texto: string; alerta: boolean } {
  if (!v) return { texto: "nunca", alerta: true };
  const min = Math.max(0, Math.round((Date.now() - new Date(v).getTime()) / 60000));
  if (min < 60) return { texto: `hace ${min} min`, alerta: false };
  if (min < 1440) return { texto: `hace ${Math.round(min / 60)} h`, alerta: false };
  return { texto: `hace ${Math.round(min / 1440)} d`, alerta: true };
}

export const EVENTOS_GRAVES = ["admin_desactivado", "desinstalacion_intento", "sim_cambiada"];
export const NOMBRE_EVENTO: Record<string, string> = {
  enrolado: "Equipo enrolado", arranque: "Arranque del teléfono",
  admin_desactivado: "Quitaron a la app como administradora del dispositivo",
  desinstalacion_intento: "Intento de desinstalar la app", permiso_revocado: "Permiso revocado",
  sim_cambiada: "Cambio de SIM", otro: "Otro",
};
