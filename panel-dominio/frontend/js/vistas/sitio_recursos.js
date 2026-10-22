// Pestaña «CPU y memoria»: lo que gasta el sitio (su PHP, sus tareas y su aplicación propia) en las últimas 24 horas,
// medido cada 5 minutos en el servidor. 100 % de CPU es un núcleo entero.
import { api } from '../api.js';
import { el, aviso } from '../ui.js';
import { enRutaSitio } from './sitio_comun.js';
import { grafico } from './grafico.js';

const cifra = (v, unidad) => (typeof v === 'number' ? `${v.toLocaleString('es', { maximumFractionDigits: 1 })} ${unidad}` : '—');

export async function pestanaRecursos(ctx) {
  const r = await api.get(`/sitios/${enRutaSitio(ctx.sitio)}/recursos`);
  const puntos = r.puntos || [], res = r.resumen || {}, lim = r.limites || {};
  const cuerpo = !r.instalado
    ? aviso('nota', 'La medición de CPU y memoria todavía no está activa en este servidor. Pídesela al administrador general.')
    : !puntos.length ? aviso('nota', 'Todavía no hay mediciones: la primera llega en unos 5 minutos.')
      : el('div', null,
        el('h2', null, 'CPU'), grafico('CPU', puntos.map(p => [p[0], p[1]]), '%', lim.app_cpu || null),
        el('h2', null, 'Memoria'), grafico('Memoria', puntos.map(p => [p[0], p[2]]), 'MB', lim.app_memoria_mb || null));
  return el('div', null,
    el('p', { clase: 'ayuda' }, 'Lo que gastan el PHP del sitio, sus tareas programadas y su aplicación Node.js o Python, medido cada 5 minutos. 100 % de CPU es un núcleo entero del servidor; la memoria es la que le toca al sitio de la que comparte con los demás.'),
    cuerpo,
    puntos.length ? el('div', { clase: 'tarjetas' },
      el('div', { clase: 'caja' }, el('div', { clase: 'ayuda' }, 'CPU media / máxima'), el('div', { clase: 'cifra' }, `${cifra(res.cpu_media, '%')} / ${cifra(res.cpu_maxima, '%')}`)),
      el('div', { clase: 'caja' }, el('div', { clase: 'ayuda' }, 'Memoria media / máxima'), el('div', { clase: 'cifra' }, `${cifra(res.memoria_media_mb, 'MB')} / ${cifra(res.memoria_maxima_mb, 'MB')}`))) : null,
    el('h2', null, 'Límites de este sitio'),
    el('ul', { clase: 'miembros' },
      el('li', null, el('span', null, 'Procesos de PHP a la vez'), el('strong', null, String(lim.php_procesos || '—'))),
      el('li', null, el('span', null, 'Memoria por proceso de PHP'), el('strong', null, cifra(lim.php_memoria_mb, 'MB'))),
      lim.app_memoria_mb ? el('li', null, el('span', null, 'Memoria de la aplicación propia'), el('strong', null, cifra(lim.app_memoria_mb, 'MB'))) : null,
      lim.app_cpu ? el('li', null, el('span', null, 'CPU de la aplicación propia'), el('strong', null, cifra(lim.app_cpu, '%'))) : null),
    el('p', { clase: 'ayuda' }, 'Si el sitio se acerca a menudo a sus límites, conviene revisar la aplicación (caché, tareas, complementos) o pedir más al administrador general.'));
}
