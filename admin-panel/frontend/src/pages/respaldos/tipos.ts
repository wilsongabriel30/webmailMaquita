export interface Resultado {
  inicio?: string; motivo?: string; estado?: string; error?: string; instantanea?: string; bases?: number;
  archivos?: number; nuevo_mb?: number; total_mb?: number; externo?: string; duracion_s?: number;
}
export interface Instantanea { id: string; fecha: string; etiquetas: string[] }
export interface Config {
  automatico: boolean;
  conservar: { diarios: number; semanales: number; mensuales: number };
  destino: { tipo: string; url: string };
}
export interface Estado {
  config: Config; en_curso: boolean; ultimo: Resultado | null; ultimo_correcto: Resultado | null;
  comprobacion: { estado: string; error?: string; fecha_comprobacion?: string; fecha?: string; prueba_base_correo?: string } | null;
  restauracion: { tipo: string; objeto: string; instantanea: string; estado: string; error?: string; carpeta?: string; mensajes?: number; inicio?: string; fin?: string } | null;
  instantaneas: Instantanea[]; sitios: string[]; disco_libre_gb: number;
}
export const caja = "bg-white rounded border border-ms-gray-30 p-5 space-y-3";
export const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";
