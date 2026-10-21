// Tarjeta «Mi sitio web» del inicio. Se pide aparte y después del resto: revisar las aplicaciones
// es lento y el inicio no debe esperarlo. Si el servidor no ofrece sitios, no aparece.
import { api } from '../api.js';
import { el } from '../ui.js';

const NOMBRE = { wordpress: 'WordPress', joomla: 'Joomla', paquete: 'Paquete propio', propia: 'Aplicación propia' };

function linea(s) {
  const app = s.app ? (NOMBRE[s.app] || s.app) + (s.version ? ' ' + s.version : '') : 'Sin aplicación';
  const act = s.actualizaciones === null || s.actualizaciones === undefined ? null
    : s.actualizaciones > 0 ? el('span', { clase: 'marca no' }, s.actualizaciones === 1 ? '1 actualización' : `${s.actualizaciones} actualizaciones`) : el('span', { clase: 'marca si' }, 'Al día');
  return el('li', null,
    el('div', null, el('a', { href: '#sitios/' + encodeURIComponent(s.sitio) }, el('strong', null, s.sitio)),
      el('div', { clase: 'ayuda' }, app + (s.app_pendiente ? ' · falta terminar el instalador' : ''))),
    el('span', null, el('span', { clase: 'marca ' + (s.https ? 'si' : 'no') }, s.https ? 'HTTPS' : 'Sin HTTPS'), ' ', act));
}

export function tarjetaSitio() {
  const caja = el('section', { clase: 'caja', 'aria-label': 'Mi sitio web', hidden: true });
  api.get('/sitios/resumen').then(r => {
    if (!r.instalado) return;
    caja.replaceChildren(el('h2', null, 'Mi sitio web'),
      r.sitios.length ? el('ul', { clase: 'miembros' }, r.sitios.map(linea))
        : el('p', null, 'Todavía no tienes una página web en este servidor. ', el('a', { href: '#sitios' }, 'Crear mi sitio')));
    caja.hidden = false;
  }).catch(() => { /* la tarjeta es un extra: si falla, el inicio sigue igual */ });
  return caja;
}
