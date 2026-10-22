// Pestaña «Dominios»: alias del sitio, otros nombres de tus dominios que muestran el mismo sitio (p. ej. el dominio
// .com y el .org de la organización). Se guarda la lista entera; si el sitio tiene HTTPS, el certificado se amplía.
import { api } from '../api.js';
import { el, aviso, campo } from '../ui.js';
import { confirmar, dominioDe, enRutaSitio, hacer, mensajes } from './sitio_comun.js';

export async function pestanaDominios(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/alias`;
  const msj = mensajes();
  let alias = [...(ctx.s.alias || [])];
  const sinHttps = new Set(ctx.s.alias_sin_https || []);
  const listaNodo = el('ul', { clase: 'miembros' });
  const nuevo = campo('Otro nombre', { type: 'text', maxlength: 200, placeholder: 'p. ej. tienda.' + (ctx.estado.dominio || 'tu-dominio'), autocomplete: 'off' },
    'Uno de tus dominios o un subdominio suyo. Antes, apúntalo en el DNS a este servidor.');
  const dominios = (ctx.sesion && ctx.sesion.dominios) || [ctx.estado.dominio].filter(Boolean);

  const guardar = async (lista, boton, texto) => {
    const r = await hacer(msj, boton, ctx.s.ssl ? 'Guardando y ampliando el certificado (puede tardar un minuto)…' : 'Guardando…',
      () => api.put(ruta, { alias: lista }));
    if (!r) return false;
    alias = r.alias || lista;
    (r.alias_sin_https || []).forEach(a => sinHttps.add(a));
    pintar();
    msj.ok(texto + ((r.alias_sin_https || []).length ? ' Algunos todavía no apuntan aquí: quedan sin HTTPS hasta que vuelvas a guardar.' : ''));
    return true;
  };
  const pintar = () => listaNodo.replaceChildren(...(alias.length ? alias.map(a => {
    const quitar = el('button', { clase: 'enlace peligro', type: 'button' }, 'Quitar');
    quitar.addEventListener('click', async () => {
      if (!await confirmar('Quitar alias', `¿Dejar de mostrar el sitio en ${a}?`, 'Quitar', true)) return;
      guardar(alias.filter(x => x !== a), quitar, `${a} ya no muestra el sitio.`);
    });
    return el('li', null, el('div', null, el('a', { href: `http://${a}`, target: '_blank', rel: 'noopener noreferrer' }, a),
      ctx.s.ssl ? el('span', { clase: 'marca ' + (sinHttps.has(a) ? 'aviso-marca' : 'si') }, sinHttps.has(a) ? 'Sin HTTPS' : 'HTTPS') : null), quitar);
  }) : [el('li', null, el('span', { clase: 'ayuda' }, 'El sitio no tiene alias.'))]));
  pintar();
  const agregar = el('button', { clase: 'boton', type: 'submit' }, 'Añadir');
  return el('div', null,
    el('h2', null, 'Alias de dominio'),
    el('p', { clase: 'ayuda' }, `Los alias muestran el mismo contenido que ${ctx.sitio}${ctx.s.www ? ' (también con www.)' : ''}. Hasta 10 por sitio.`),
    listaNodo,
    el('form', { clase: 'fila espacio', alSubmit: (e) => {
      e.preventDefault();
      const nombre = nuevo.entrada.value.trim().toLowerCase().replace(/^www\./, '').replace(/\.+$/, '');
      if (!nombre) return;
      if (!dominioDe(nombre, dominios)) { msj.error(`${nombre} no es de tus dominios (${dominios.join(', ')}).`); return; }
      if (alias.includes(nombre) || nombre === ctx.sitio) { msj.error('Ese nombre ya muestra este sitio.'); return; }
      guardar([...alias, nombre], agregar, `${nombre} ya muestra el sitio.`).then((ok) => { if (ok) nuevo.entrada.value = ''; });
    } }, el('div', { clase: 'crece' }, nuevo.nodo), agregar),
    msj.nodo,
    aviso('nota', 'Los nombres del correo (mail., webmail., autodiscover.…) y los que ya usa otro sitio no pueden ser alias.'));
}
