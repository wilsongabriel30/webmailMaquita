// Pestaña «Visitas y registros»: estadísticas de 30 días (GoAccess), disponibilidad (comprobación cada 5 minutos)
// y las últimas líneas de los registros de errores y accesos. Todo se consulta; nada cambia el sitio.
import { api } from '../api.js';
import { el, aviso, campo, lista } from '../ui.js';
import { descargar, enRutaSitio, hacer, mensajes, tamano } from './sitio_comun.js';
import { bloque, boton } from './sitio_piezas.js';

const numero = (n) => Number(n || 0).toLocaleString('es');

export async function pestanaDatos(ctx) {
  const base = `/sitios/${enRutaSitio(ctx.sitio)}`;
  const [est, disp] = await Promise.all([api.get(base + '/estadisticas'), api.get(base + '/disponibilidad')]);
  return el('div', null, visitas(base, est), disponibilidad(disp), registros(base));
}

function visitas(base, est) {
  const msj = mensajes();
  const r = est.resumen || {}, t = r.totales || {};
  const dias = (r.dias || []).slice().reverse();
  const generar = boton('Generar ahora', 'boton claro', async (b) => {
    if (await hacer(msj, b, 'Generando (puede tardar unos minutos)…', () => api.post(base + '/estadisticas/generar'))) {
      msj.ok('Listo. Vuelve a abrir la pestaña para ver las cifras nuevas.');
    }
  });
  const informe = boton('Ver el informe completo', 'boton claro', (b) => hacer(msj, b, 'Preparando el informe…',
    () => descargar(() => api.post(base + '/estadisticas/informe'), true)));
  return el('section', { clase: 'caja', 'aria-label': 'Visitas' },
    el('h2', null, 'Visitas de los últimos 30 días'),
    est.goaccess === false ? aviso('nota', 'El servidor todavía no tiene GoAccess: el resumen funciona, el informe completo no.') : null,
    est.resumen ? el('div', { clase: 'tarjetas' },
      [['Visitas', numero(t.visitas)], ['Páginas vistas', numero(t.paginas)], ['Solicitudes', numero(t.solicitudes)], ['Tráfico', tamano(t.bytes)]]
        .map(([k, v]) => el('div', { clase: 'caja' }, el('div', { clase: 'ayuda' }, k), el('div', { clase: 'cifra' }, v))))
      : el('p', { clase: 'ayuda' }, 'Todavía no hay estadísticas: se calculan cada noche (o pulsa «Generar ahora»).'),
    dias.length ? el('details', null, el('summary', null, 'Día por día'), el('div', { clase: 'tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Día', 'Visitas', 'Páginas', 'Tráfico'].map(x => el('th', null, x)))),
      el('tbody', null, dias.map(d => el('tr', null, el('td', null, d.fecha), el('td', null, numero(d.visitas)),
        el('td', null, numero(d.paginas)), el('td', null, tamano(d.bytes)))))))) : null,
    el('p', { clase: 'ayuda' }, 'Las visitas no cuentan los robots conocidos. El informe completo se abre aparte, aislado del portal.'),
    el('div', { clase: 'fila espacio' }, generar, est.informe ? informe : null), msj.nodo);
}

function disponibilidad(d) {
  const historial = (d.historial || []).slice(-24).reverse();
  return bloque('Disponibilidad ' + (d.caido ? '(caído)' : d.ultima ? '(en línea)' : ''),
    'El servidor pide la portada cada 5 minutos y avisa por correo si deja de responder o si el certificado está por caducar.',
    d.caido ? aviso('error', `El sitio no responde desde ${d.caido_desde || 'hace un rato'}.`) : null,
    el('p', null, d.porcentaje === null || d.porcentaje === undefined ? 'Todavía no hay comprobaciones.' : `${d.porcentaje} % de las comprobaciones recientes salieron bien.`),
    el('p', { clase: 'ayuda' }, 'Avisos a: ' + (d.destinatarios || []).join(', ')),
    historial.length ? el('div', { clase: 'tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Hora', 'Resultado', 'Tiempo', 'Certificado'].map(x => el('th', null, x)))),
      el('tbody', null, historial.map(h => el('tr', null, el('td', null, h.hora || ''),
        el('td', null, el('span', { clase: 'marca ' + (h.ok ? 'si' : 'no') }, h.ok ? `bien (${h.codigo || ''})` : h.motivo || `fallo ${h.codigo || ''}`)),
        el('td', null, h.ms ? `${h.ms} ms` : ''), el('td', null, h.dias_certificado === null || h.dias_certificado === undefined ? '' : `${h.dias_certificado} días`)))))) : null,
    (d.avisos || []).length ? el('details', null, el('summary', null, `Avisos enviados (${d.avisos.length})`),
      el('ul', { clase: 'miembros' }, d.avisos.slice(-20).reverse().map(a => el('li', null, `${a.dia || ''} ${a.hora || ''}`, el('span', null, a.asunto || ''))))) : null);
}

function registros(base) {
  const msj = mensajes();
  const tipo = lista('Registro', [{ valor: 'error', texto: 'Errores del servidor web' }, { valor: 'acceso', texto: 'Accesos (visitas)' }, { valor: 'php', texto: 'Errores de PHP' }]);
  const lineas = lista('Líneas', ['100', '200', '500', '1000'].map(v => ({ valor: v, texto: `Últimas ${v}` })));
  lineas.entrada.value = '200';
  const filtro = campo('Que contenga (opcional)', { type: 'text', maxlength: 100, placeholder: 'p. ej. wp-login o 404' });
  const salida = el('div');
  const ver = boton('Ver', 'boton', null, 'submit');
  return bloque('Registros', 'Las últimas líneas de los registros del sitio, para encontrar un error o un acceso concreto.',
    el('form', { alSubmit: async (e) => {
      e.preventDefault();
      const consulta = new URLSearchParams({ lineas: lineas.entrada.value, filtro: filtro.entrada.value.trim() });
      const r = await hacer(msj, ver, 'Leyendo…', () => api.get(`${base}/registros/${tipo.entrada.value}?${consulta}`));
      if (!r) return;
      salida.replaceChildren(!r.existe ? el('p', { clase: 'ayuda' }, 'Ese registro todavía no existe (nadie ha entrado o no ha habido errores).')
        : el('pre', { clase: 'salida' }, (r.lineas || []).join('\n') || '(sin líneas que coincidan)'));
    } }, el('div', { clase: 'rejilla' }, tipo.nodo, lineas.nodo, filtro.nodo), el('div', { clase: 'pie-form' }, ver)),
    msj.nodo, salida);
}
