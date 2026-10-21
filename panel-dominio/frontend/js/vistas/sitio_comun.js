// Piezas que comparten las vistas de «Mi sitio web».
import { el, aviso } from '../ui.js';

export const NOMBRE_APP = { wordpress: 'WordPress', joomla: 'Joomla', paquete: 'Paquete propio', propia: 'Aplicación propia' };
export const nombreApp = (id) => NOMBRE_APP[id] || id || 'Sin aplicación';
export const enRutaSitio = (sitio) => encodeURIComponent(sitio);
export const irA = (...partes) => { location.hash = '#' + ['sitios', ...partes].map(encodeURIComponent).join('/'); };

/** El dominio asignado al que pertenece un sitio (el más largo, como en el servidor). */
export function dominioDe(sitio, dominios) {
  return dominios.filter(d => sitio === d || sitio.endsWith('.' + d)).sort((a, b) => b.length - a.length)[0] || null;
}

/** Zona de mensajes de una pestaña: espera, bien o error, siempre en el mismo sitio. */
export function mensajes() {
  const nodo = el('div', { 'aria-live': 'polite' });
  const poner = (tipo, texto) => nodo.replaceChildren(texto ? (tipo === 'espera' ? el('p', { clase: 'aviso nota' }, texto) : aviso(tipo, texto)) : '');
  return { nodo, espera: (t) => poner('espera', t), ok: (t) => poner('ok', t), error: (t) => poner('error', t), limpiar: () => poner('ok', '') };
}

/** Ejecuta `fn` con el botón desactivado y un aviso de espera; los errores se muestran, no se lanzan. */
export async function hacer(msj, boton, espera, fn) {
  if (boton) boton.disabled = true;
  msj.espera(espera);
  try { const r = await fn(); msj.limpiar(); return r; }
  catch (e) { msj.error(e.message); return undefined; }
  finally { if (boton) boton.disabled = false; }
}

const esEnlace = (url) => typeof url === 'string' && /^https?:\/\//.test(url);

/** Abre en otra pestaña el enlace de un solo uso que devuelve `pedir`. La pestaña se abre ANTES
 *  de pedirlo: si se abre después de esperar, el navegador la bloquea. */
export async function abrirFuera(pedir) {
  const pestana = window.open('about:blank', '_blank');
  try {
    const r = await pedir();
    if (!esEnlace(r.url)) throw new Error('El servidor no devolvió un enlace válido');
    if (pestana) { pestana.opener = null; pestana.location.href = r.url; } else { location.href = r.url; }
    return r;
  } catch (e) { if (pestana) pestana.close(); throw e; }
}

async function copiar(texto, boton) {
  try { await navigator.clipboard.writeText(texto); boton.textContent = 'Copiado'; }
  catch { boton.textContent = 'Selecciónalo y cópialo a mano'; }
  setTimeout(() => { boton.textContent = 'Copiar'; }, 2500);
}

/** Datos que se muestran UNA sola vez (contraseñas): ventana con botón de copiar en cada uno.
 *  items: [{ etiqueta, valor, secreto }] */
export function unaVez(titulo, items, nota) {
  const cerrar = () => velo.remove();
  const filas = items.filter(i => i.valor !== undefined && i.valor !== null && i.valor !== '').map(i => {
    const boton = el('button', { clase: 'enlace', type: 'button' }, 'Copiar');
    boton.addEventListener('click', () => copiar(String(i.valor), boton));
    return el('li', null, el('div', null, el('strong', null, i.etiqueta),
      esEnlace(i.valor) && !i.secreto ? el('a', { href: i.valor, target: '_blank', rel: 'noopener noreferrer', clase: 'dato' }, i.valor)
        : el('code', { clase: 'dato' + (i.secreto ? ' secreto' : '') }, String(i.valor))), boton);
  });
  const caja = el('div', { clase: 'caja' },
    el('h1', null, titulo),
    aviso('nota', nota || 'Guarda estos datos ahora: la contraseña no se vuelve a mostrar.'),
    el('ul', { clase: 'miembros' }, filas),
    el('div', { clase: 'pie-form' }, el('button', { clase: 'boton', type: 'button', alClick: cerrar }, 'Ya los guardé')));
  const velo = el('div', { clase: 'velo', role: 'dialog', 'aria-modal': 'true', 'aria-label': titulo,
    alKeydown: (e) => { if (e.key === 'Escape') cerrar(); } }, caja);
  document.body.append(velo);
  caja.querySelector('button').focus();
}

/** Pregunta de sí o no sin bloquear la página (confirm() se ve mal en el teléfono). */
export function confirmar(titulo, texto, boton, peligro) {
  return new Promise((resolver) => {
    const cerrar = (si) => { velo.remove(); resolver(si); };
    const caja = el('div', { clase: 'caja' }, el('h1', null, titulo), el('p', null, texto),
      el('div', { clase: 'pie-form' },
        el('button', { clase: 'boton claro', type: 'button', alClick: () => cerrar(false) }, 'Cancelar'),
        el('button', { clase: 'boton' + (peligro ? ' peligro' : ''), type: 'button', alClick: () => cerrar(true) }, boton)));
    const velo = el('div', { clase: 'velo', role: 'dialog', 'aria-modal': 'true', 'aria-label': titulo,
      alKeydown: (e) => { if (e.key === 'Escape') cerrar(false); } }, caja);
    document.body.append(velo);
    caja.querySelector('.boton:not(.claro)').focus();
  });
}

export const megas = (mb) => (mb >= 1024 ? (mb / 1024).toLocaleString('es', { maximumFractionDigits: 1 }) + ' GB' : Math.round(mb || 0) + ' MB');

/** Barra de uso «usado de total», con aviso al acercarse al tope. */
export function barraUso(etiqueta, usado, total, unidad) {
  const pct = total > 0 ? Math.min(100, Math.round((usado / total) * 100)) : 0;
  const texto = unidad === 'mb' ? `${megas(usado)} de ${megas(total)}` : `${usado} de ${total}`;
  return el('div', { clase: 'uso' },
    el('div', { clase: 'uso-texto' }, el('span', null, etiqueta), el('span', null, texto)),
    // <progress> y no un div con style=: la política de seguridad del portal no admite estilos en línea.
    el('progress', { clase: pct >= 90 ? 'lleno' : '', max: '100', value: String(pct), 'aria-label': etiqueta }, pct + ' %'));
}
