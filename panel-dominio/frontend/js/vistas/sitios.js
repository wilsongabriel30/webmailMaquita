// «Mi sitio web»: lista de sitios de tus dominios, cuotas con su uso y sitio nuevo.
// Rutas: #sitios · #sitios/<sitio> · #sitios/<sitio>/<pestaña> · #sitios/dns/<dominio>
import { api } from '../api.js';
import { el, agregar, aviso, campo, casilla, lista, ventana } from '../ui.js';
import { barraUso, dominioDe, irA, megas, nombreApp } from './sitio_comun.js';
import { vistaFichaSitio } from './sitio_ficha.js';
import { vistaZona } from './sitio_zona.js';

const NO_INSTALADO = 'Los sitios web no están instalados en este servidor';

export async function vistaSitios(sesion) {
  const partes = location.hash.slice(1).split('/').slice(1).map(decodeURIComponent);
  try {
    if (partes[0] === 'dns' && partes[1]) return await vistaZona(partes[1]);
    if (partes[0]) return await vistaFichaSitio(partes[0], partes[1] || '', sesion);
    return await vistaLista(sesion);
  } catch (e) {
    if (e.message !== NO_INSTALADO) throw e;
    return el('div', null, el('h1', null, 'Mi sitio web'),
      aviso('nota', 'Este servidor todavía no ofrece sitios web. Si tu organización necesita uno, pídelo al administrador general.'));
  }
}

function tarjetaDominio(d, dns) {
  const c = d.cuota || {}, u = d.uso || {};
  return el('section', { clase: 'caja', 'aria-label': 'Cuota de ' + d.dominio },
    el('h2', null, d.dominio),
    barraUso('Sitios', u.sitios || 0, c.max_sitios || 0),
    barraUso('Espacio en disco', u.disco_mb || 0, c.disco_mb || 0, 'mb'),
    barraUso('Bases de datos', u.bases_mb || 0, c.bases_mb || 0, 'mb'),
    dns ? el('p', { clase: 'ayuda' }, el('a', { href: '#sitios/dns/' + encodeURIComponent(d.dominio) }, 'Registros DNS de la zona')) : null);
}

function formularioNuevo(dominios, alCrear) {
  const elegir = lista('Dominio', dominios.map(d => ({ valor: d.dominio, texto: d.dominio })));
  const sub = campo('Subdominio (opcional)', { type: 'text', maxlength: 60, placeholder: 'p. ej. blog', autocomplete: 'off' },
    'Vacío: el sitio es el propio dominio. Con «blog», el sitio será blog.<tu dominio>.');
  const www = casilla('Publicar también con www.', true);
  const vista = el('p', { clase: 'ayuda' });
  const nombre = () => {
    const s = sub.entrada.value.trim().toLowerCase().replace(/\.+$/, '');
    return s ? `${s}.${elegir.entrada.value}` : elegir.entrada.value;
  };
  const pintar = () => { vista.textContent = 'Se creará: ' + nombre(); };
  sub.entrada.addEventListener('input', pintar);
  elegir.entrada.addEventListener('change', pintar);
  pintar();
  ventana('Nuevo sitio web', el('div', null, elegir.nodo, sub.nodo, www.nodo, vista,
    el('p', { clase: 'ayuda' }, 'Antes de pedir HTTPS, el nombre debe apuntar en el DNS a este servidor.')),
  'Crear sitio', async () => {
    const sitio = nombre();
    await api.post('/sitios', { sitio, www: www.entrada.checked });
    alCrear(sitio);
  });
}

async function vistaLista(sesion, mensaje) {
  const r = await api.get('/sitios');
  const raiz = el('div');
  const bajas = new Set(r.solicitudes.map(s => s.objetivo));
  const conHueco = r.dominios.filter(d => !d.cuota || (d.uso || {}).sitios < d.cuota.max_sitios);
  const filas = r.sitios.map(s => el('tr', null,
    el('td', null, el('a', { href: '#sitios/' + encodeURIComponent(s.dominio) }, el('strong', null, s.dominio)),
      el('div', { clase: 'ayuda' }, [s.www ? `y www.${s.dominio}` : null,
        dominioDe(s.dominio, sesion.dominios) !== s.dominio ? 'de ' + dominioDe(s.dominio, sesion.dominios) : null].filter(Boolean).join(' · '))),
    el('td', null, nombreApp(s.app), s.app_pendiente ? el('div', { clase: 'ayuda' }, 'Falta terminar el instalador') : null),
    el('td', null, el('span', { clase: 'marca ' + (s.ssl ? 'si' : 'no') }, s.ssl ? 'HTTPS' : 'Sin HTTPS')),
    el('td', null, megas(s.ocupado_mb)),
    el('td', { clase: 'acciones' }, bajas.has(s.dominio) ? el('span', { clase: 'marca no' }, 'Baja pedida')
      : el('a', { clase: 'enlace', href: '#sitios/' + encodeURIComponent(s.dominio) }, 'Administrar'))));
  agregar(raiz,
    el('h1', null, 'Mi sitio web'),
    el('p', { clase: 'sub' }, 'Las páginas web de tu organización, cada una aislada del resto, con su aplicación, su HTTPS y sus bases de datos.'),
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'tarjetas' }, r.dominios.map(d => tarjetaDominio(d, r.dns))),
    el('div', { clase: 'fila espacio' }, el('h2', { clase: 'crece' }, 'Sitios'),
      conHueco.length ? el('button', { clase: 'boton', alClick: () => formularioNuevo(conHueco, (s) => irA(s, 'aplicacion')) }, 'Nuevo sitio')
        : el('span', { clase: 'ayuda' }, 'Llegaste al máximo de sitios de tus dominios. Para más, habla con el administrador general.')),
    el('div', { clase: 'caja tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Sitio', 'Aplicación', 'HTTPS', 'Espacio', ''].map(t => el('th', null, t)))),
      el('tbody', null, filas.length ? filas : el('tr', null, el('td', { colspan: '5', clase: 'vacio' }, 'Todavía no tienes sitios. Pulsa «Nuevo sitio».'))))));
  return raiz;
}
