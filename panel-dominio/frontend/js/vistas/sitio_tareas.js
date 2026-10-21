// Pestaña «Tareas»: trabajos de cron del sitio (una orden a una hora), con su última salida.
import { api } from '../api.js';
import { el, campo, lista } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes } from './sitio_comun.js';

const COMUNES = [
  ['Cada 5 minutos', '*/5 * * * *'], ['Una vez por hora', '0 * * * *'], ['Dos veces al día', '0 0,12 * * *'],
  ['Una vez al día (3:00)', '0 3 * * *'], ['Una vez a la semana (domingo 3:00)', '0 3 * * 0'], ['El día 1 de cada mes (3:00)', '0 3 1 * *'],
];

export async function pestanaTareas(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/tareas`;
  let datos = await api.get(ruta);
  const raiz = el('div');
  const msj = mensajes();
  const salida = el('div');
  const cuerpo = el('tbody');
  const limpio = (t) => ({ id: t.id, horario: t.horario, orden: t.orden, descripcion: t.descripcion || '', activo: !!t.activo });

  const guardar = async (boton, nueva) => {
    const r = await hacer(msj, boton, 'Guardando…', () => api.put(ruta, { trabajos: nueva.map(limpio) }));
    if (r) { datos = r; pintar(); msj.ok('Guardado.'); }
    return !!r;
  };
  const enlace = (texto, fn, peligro) => { const b = el('button', { clase: 'enlace' + (peligro ? ' peligro' : ''), type: 'button' }, texto); b.addEventListener('click', () => fn(b)); return b; };
  const pintar = () => {
    const trabajos = datos.trabajos || [];
    cuerpo.replaceChildren(...(trabajos.length ? trabajos.map(t => el('tr', null,
      el('td', null, el('code', null, t.horario)),
      el('td', null, el('code', null, t.orden), t.descripcion ? el('div', { clase: 'ayuda' }, t.descripcion) : null),
      el('td', null, t.en_curso ? 'ejecutándose…' : t.ultima ? `${t.ultima}: ${t.resultado || ''}` : 'sin ejecutar',
        !t.activo ? el('div', { clase: 'ayuda' }, 'en pausa') : t.siguiente ? el('div', { clase: 'ayuda' }, 'próxima: ' + t.siguiente) : null),
      el('td', { clase: 'acciones' },
        enlace('Ejecutar ahora', (b) => hacer(msj, b, 'Lanzando…', () => api.post(`${ruta}/${t.id}/ejecutar`)).then(r => { if (r) msj.ok('Lanzado. Mira la salida en unos segundos.'); })),
        enlace('Salida', async (b) => {
          const r = await hacer(msj, b, 'Cargando la salida…', () => api.get(`${ruta}/${t.id}/registro`));
          if (r) salida.replaceChildren(el('h2', null, 'Salida del trabajo'), el('pre', { clase: 'salida' }, r.registro || '(sin salida todavía)'));
        }),
        enlace(t.activo ? 'Pausar' : 'Activar', (b) => guardar(b, trabajos.map(x => (x.id === t.id ? { ...x, activo: !x.activo } : x)))),
        enlace('Quitar', async (b) => { if (await confirmar('Quitar trabajo', '¿Quitar este trabajo de cron?', 'Quitar', true)) guardar(b, trabajos.filter(x => x.id !== t.id)); }, true))))
      : [el('tr', null, el('td', { colspan: '4', clase: 'vacio' }, 'Sin trabajos de cron.'))]));
  };

  const comun = lista('Horario', [{ valor: '', texto: 'Elegir uno común…' }, ...COMUNES.map(([t, h]) => ({ valor: h, texto: `${t} (${h})` }))]);
  const horario = campo('Horario cron (minuto hora día mes día-de-la-semana)', { type: 'text', valor: '0 3 * * *', maxlength: 100 });
  comun.entrada.addEventListener('change', () => { if (comun.entrada.value) horario.entrada.value = comun.entrada.value; });
  const orden = campo('Orden', { type: 'text', maxlength: 1000, placeholder: `p. ej. ${datos.php || 'php'} ${datos.carpeta || 'publico'}/cron.php` });
  const descripcion = campo('Descripción (opcional)', { type: 'text', maxlength: 80 });
  const agregar = el('button', { clase: 'boton', type: 'submit' }, 'Agregar');
  pintar();
  raiz.append(
    el('h2', null, 'Trabajos de cron'),
    el('p', { clase: 'ayuda' }, 'Ejecutan una orden o un script a la hora indicada, con el usuario del sitio y desde su carpeta. Cada ejecución dura como máximo una hora.'),
    el('div', { clase: 'tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Horario', 'Orden', 'Última / próxima', ''].map(t => el('th', null, t)))), cuerpo)),
    msj.nodo, salida,
    el('form', { alSubmit: async (e) => {
      e.preventDefault();
      if (!orden.entrada.value.trim()) { msj.error('Escribe la orden.'); return; }
      const nuevo = { horario: horario.entrada.value.trim(), orden: orden.entrada.value.trim(), descripcion: descripcion.entrada.value.trim(), activo: true };
      if (await guardar(agregar, [...(datos.trabajos || []), nuevo])) { orden.entrada.value = ''; descripcion.entrada.value = ''; }
    } }, el('h2', null, 'Agregar un trabajo'), el('div', { clase: 'rejilla' }, comun.nodo, horario.nodo), orden.nodo, descripcion.nodo,
      el('p', { clase: 'ayuda' }, '«*» = todos, «*/15» = cada 15, «1-5» = de lunes a viernes; día de la semana 0 = domingo.'),
      el('div', { clase: 'pie-form' }, agregar)));
  return raiz;
}
