// Pestaña «Cortafuegos» (v1.11): cortafuegos de aplicaciones web del sitio con las reglas OWASP CRS completas.
// Modo, nivel de paranoia, exclusiones por regla (en todo el sitio o en una ruta) y los últimos bloqueos.
import { api } from '../api.js';
import { el, aviso, campo, lista } from '../ui.js';
import { enRutaSitio, hacer, mensajes } from './sitio_comun.js';
import { bloque, boton, poner } from './sitio_piezas.js';

const MODOS = [
  { valor: 'bloquear', texto: 'Bloquear los ataques (recomendado)' },
  { valor: 'detectar', texto: 'Solo detectar (anota, no bloquea)' },
  { valor: 'apagado', texto: 'Apagado' },
];
const PARANOIA = [
  { valor: '1', texto: '1: lo normal, pocos falsos positivos' },
  { valor: '2', texto: '2: más estricto, puede bloquear usos legítimos' },
];
const PERFIL = { wordpress: 'WordPress', joomla: 'Joomla', aplicacion: 'aplicación del catálogo', general: 'general' };

export async function pestanaCortafuegos(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/cortafuegos`;
  const datos = await api.get(ruta);
  const msj = mensajes();
  const exclusiones = (datos.exclusiones || []).map(e => ({ regla: e.regla, ruta: e.ruta || null }));
  const modo = lista('Modo', MODOS);
  modo.entrada.value = datos.modo || 'bloquear';
  const paranoia = lista('Nivel de paranoia', PARANOIA);
  paranoia.entrada.value = String(datos.paranoia || 1);
  const listaNodo = el('div');
  const maximo = datos.maximo || 50;

  const pintarLista = () => poner(listaNodo, exclusiones.length
    ? el('ul', { clase: 'miembros' }, exclusiones.map((e, i) => el('li', null,
      el('div', null, el('code', null, String(e.regla)), ' ', el('span', { clase: 'ayuda' }, e.ruta ? 'solo en ' + e.ruta : 'en todo el sitio')),
      boton('Quitar', 'enlace peligro', () => { exclusiones.splice(i, 1); pintarLista(); msj.ok('Quitada de la lista. Guarda para aplicarlo.'); }))))
    : el('p', { clase: 'ayuda' }, 'Ninguna exclusión.'));
  const agregarExclusion = (regla, rutaExcl) => {
    if (exclusiones.length >= maximo) { msj.error(`Se admiten hasta ${maximo} exclusiones.`); return false; }
    if (exclusiones.some(e => e.regla === regla && (e.ruta || null) === (rutaExcl || null))) { msj.ok('Esa exclusión ya está en la lista.'); return false; }
    exclusiones.push({ regla, ruta: rutaExcl || null });
    pintarLista();
    msj.ok(`Regla ${regla} añadida a la lista. Guarda para aplicarlo.`);
    return true;
  };
  pintarLista();

  const regla = campo('Número de regla', { type: 'number', min: 900000, max: 999999, inputmode: 'numeric' }, 'De 6 cifras (9xxxxx), como sale en los bloqueos.');
  const rutaCampo = campo('Solo en esta ruta (opcional)', { type: 'text', maxlength: 200, placeholder: '/wp-admin/admin-ajax.php' },
    'Vacío: en todo el sitio. Empieza por «/».');
  const anadir = boton('Añadir a la lista', 'boton claro', null, 'submit');
  const guardar = boton('Guardar el cortafuegos', 'boton', async (b) => {
    const r = await hacer(msj, b, 'Aplicando (se comprueba nginx antes)…', () => api.put(ruta, {
      modo: modo.entrada.value, paranoia: Number(paranoia.entrada.value), exclusiones }));
    if (r) msj.ok('Cortafuegos guardado y aplicado.');
  });

  const sucesos = el('div', null, el('p', { clase: 'cargando' }, 'Cargando…'));
  const cargarSucesos = () => api.get(`${ruta}/bloqueos?cuantos=50`).then((r) => poner(sucesos,
    (r.sucesos || []).length ? el('ul', { clase: 'miembros' }, r.sucesos.map(s => el('li', null,
      el('div', { clase: 'crece' },
        el('strong', null, s.accion === 'bloqueado' ? 'Bloqueado' : 'Detectado'), ' ',
        el('span', { clase: 'ayuda' }, [s.fecha, s.ip, s.metodo, s.codigo].filter(Boolean).join(' · ')),
        el('div', null, el('code', null, s.ruta || '/')),
        (s.reglas || []).map(x => el('div', { clase: 'fila' },
          el('span', { clase: 'crece' }, el('code', null, String(x.id)), ' ', x.mensaje || ''),
          boton('Excluir esta regla', 'enlace', () => agregarExclusion(x.id, s.ruta && s.ruta !== '/' ? s.ruta : null))))))))
      : el('p', { clase: 'ayuda' }, 'Sin bloqueos ni detecciones recientes.')))
    .catch((e) => poner(sucesos, aviso('error', e.message)));
  cargarSucesos();

  return el('div', null,
    el('h2', null, 'Cortafuegos de aplicaciones web'),
    el('p', null, 'Filtra los ataques habituales (inyección SQL, XSS, inclusión de archivos, escáneres) con las reglas OWASP CRS completas, ',
      `con las excepciones de serie para ${PERFIL[datos.perfil] || datos.perfil || 'este sitio'}.`),
    el('div', { clase: 'rejilla' }, modo.nodo, paranoia.nodo),
    el('h2', null, 'Exclusiones'),
    el('p', { clase: 'ayuda' }, 'Si una regla bloquea algo legítimo del sitio, exclúyela aquí (mejor solo en su ruta). Para dejar de bloquear todo, usa «Solo detectar».'),
    listaNodo,
    el('form', { alSubmit: (e) => {
      e.preventDefault();
      const n = Number(regla.entrada.value);
      const r = rutaCampo.entrada.value.trim();
      if (!Number.isInteger(n) || n < 900000 || n > 999999) { msj.error('Escribe el número de una regla de CRS (9xxxxx).'); return; }
      if (r && !/^\/[A-Za-z0-9._~/-]{0,200}$/.test(r)) { msj.error('La ruta empieza por «/» y solo lleva letras sin tilde, números y . _ ~ / -'); return; }
      if (agregarExclusion(n, r)) { regla.entrada.value = ''; rutaCampo.entrada.value = ''; }
    } }, el('div', { clase: 'rejilla' }, regla.nodo, rutaCampo.nodo), el('div', { clase: 'pie-form' }, anadir)),
    el('div', { clase: 'pie-form' }, guardar),
    msj.nodo,
    bloque('Últimos bloqueos y detecciones', 'Sin la consulta ni los datos enviados: pueden llevar contraseñas o datos personales.',
      el('div', { clase: 'pie-form' }, boton('Actualizar', 'boton claro', () => cargarSucesos())), sucesos));
}
