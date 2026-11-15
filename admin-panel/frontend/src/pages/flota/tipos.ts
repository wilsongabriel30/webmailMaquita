// Flota Maquita (T-88): tipos compartidos de la consola de equipos Windows.
import type { AjustesTunel } from "./tunelTipos";

export interface EquipoFlota {
  equipo_id: string | null; nombre: string; etiqueta?: string; estado?: "activo" | "retirado"; enrolado: boolean;
  version_app?: string; windows?: string; enrolado_en?: string; ultimo_sondeo?: string; ultima_ip?: string; inventario_en?: string;
  retirado_en?: string; motivo_retiro?: string; visto_en?: string; usuario?: string; version_tel?: string; ip_tel?: string;
  windows_tel?: string; ssh: string; ssh_en?: string; ssh_detalle?: string; ordenes_vivas: number;
  semaforo_agente: Semaforo; semaforo_app: Semaforo;
}
export type Semaforo = "verde" | "amarillo" | "rojo" | "gris";
export interface Totales { enrolados: number; agente_hoy: number; sin_enrolar: number; retirados: number; ssh_activo: number }

export interface Orden {
  orden_id: string; equipo_id: string; nombre?: string; tipo: string; parametros: Record<string, unknown>; estado: string;
  motivo: string; emitida_por: string; emitida_en: string; caduca_en: string; entregas: number; entregada_en?: string;
  resultado_en?: string; registro?: string; datos?: unknown; anulada_por?: string; caducada: boolean;
}
export interface TipoOrden { tipo: string; fase: number; nombre: string; desc: string; acciones: string[]; habilitado: boolean; dedicada?: boolean }
export interface Catalogo { tipos: TipoOrden[]; kid: string; firma_disponible: boolean; clave_publica?: string; tunel?: AjustesTunel }
export interface Asiento { id: number; momento: string; equipo_id?: string; nombre?: string; orden_id?: string; actor: string; accion: string; detalle?: unknown; ip: string }

export const fechaHora = (v?: string | null) => v ? new Date(v).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "—";

export const COLOR: Record<Semaforo, string> = { verde: "bg-green-500", amarillo: "bg-amber-400", rojo: "bg-red-500", gris: "bg-gray-300" };

export const ESTADO_ORDEN: Record<string, string> = {
  pendiente: "Pendiente", entregada: "Entregada", recibida: "Recibida", ejecutando: "Ejecutando", ok: "Correcta",
  error: "Con error", rechazada: "Rechazada por el equipo", anulada: "Anulada",
};

export const estadoOrden = (o: Orden) => o.caducada ? "Caducada sin respuesta" : ESTADO_ORDEN[o.estado] || o.estado;
