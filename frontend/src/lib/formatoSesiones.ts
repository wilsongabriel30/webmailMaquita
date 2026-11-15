/**
 * formatoSesiones.ts — Utilidades compartidas para las vistas de sesiones abiertas.
 *
 * Las usan «Sesiones abiertas» de la persona (settings/CerrarSesiones.tsx) y la vista de
 * administración de Tecnología (admin/SesionesAdmin.tsx): tipo de sesión, iconos por clase de
 * dispositivo y el «último uso» en lenguaje humano. Se mantiene aparte para no repetir código
 * y para que cada vista quede pequeña (código modular).
 */

/** Sesión viva tal como la entrega GET /api/auth/sesiones y GET /api/admin/sesiones. */
export interface Sesion {
  sid: string;
  tipo: string;
  dispositivo: string;
  ip: string;
  creada: number;
  vence: number;
  actual: boolean;
  nombre: string;
  clase: 'navegador' | 'app_movil' | 'app_escritorio' | 'otro';
  ultimo_uso: number;
  equipo_id: string;
  equipo_nombre: string;
  equipo_aproximado: boolean;
  ubicacion: string | null;
}

export const TIPOS_SESION: Record<string, string> = {
  normal: 'Sesión',
  impersonate: 'Acceso de administración',
  service: 'Servicio',
};

export const CLASES_SESION: Record<string, string> = {
  navegador: 'Navegador web',
  app_movil: 'Aplicación móvil',
  app_escritorio: 'Aplicación de escritorio',
  otro: 'Otro dispositivo',
};

/** Trazo SVG (heroicons, viewBox 0 0 24 24) para el icono según la clase de dispositivo. */
export function iconoClase(clase: string): string {
  switch (clase) {
    case 'navegador':
      return 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9';
    case 'app_movil':
      return 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z';
    case 'app_escritorio':
      return 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z';
    default:
      return 'M9.879 7.519C11.05 6.494 12.95 6.494 14.121 7.519c1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z';
  }
}

const HORA = { hour: '2-digit', minute: '2-digit', hour12: false } as const;

/**
 * «Último uso» en lenguaje humano, tratando de usted:
 * «hace unos segundos», «hace 5 minutos», «hace 2 horas», «ayer a las 15:30»,
 * «hace 3 días», y para lo más antiguo la fecha corta.
 */
export function ultimoUsoHumano(epochSegundos: number, ahora: Date = new Date()): string {
  if (!epochSegundos) return 'sin registro';
  const fecha = new Date(epochSegundos * 1000);
  const segundos = Math.round((ahora.getTime() - fecha.getTime()) / 1000);
  if (segundos < 0) return 'ahora mismo';
  if (segundos < 45) return 'hace unos segundos';
  const minutos = Math.round(segundos / 60);
  if (minutos < 60) return minutos === 1 ? 'hace 1 minuto' : `hace ${minutos} minutos`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return horas === 1 ? 'hace 1 hora' : `hace ${horas} horas`;

  const inicioHoy = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate()).getTime();
  const inicioFecha = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate()).getTime();
  const dias = Math.round((inicioHoy - inicioFecha) / 86400000);
  if (dias === 1) return `ayer a las ${fecha.toLocaleTimeString('es-EC', HORA)}`;
  if (dias < 7) return `hace ${dias} días`;
  if (fecha.getFullYear() === ahora.getFullYear()) {
    return fecha.toLocaleDateString('es-EC', { day: 'numeric', month: 'short' }).replace('.', '');
  }
  return fecha.toLocaleDateString('es-EC', { day: 'numeric', month: 'short', year: 'numeric' }).replace('.', '');
}

/** Fecha y hora absolutas, para tooltips y detalles. */
export function fechaHora(epochSegundos: number): string {
  if (!epochSegundos) return '';
  return new Date(epochSegundos * 1000).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' });
}
