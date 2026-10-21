// Ficha de un sitio: cabecera con su estado y pestañas. Cada pestaña pide lo suyo al abrirse,
// así la ficha carga con una sola petición aunque la conexión sea lenta.
import { api } from '../api.js';
import { el, aviso } from '../ui.js';
import { barraUso, enRutaSitio, megas, nombreApp } from './sitio_comun.js';
import { pestanaAplicacion } from './sitio_aplicacion.js';
import { pestanaHttps, pestanaFtp } from './sitio_conexion.js';
import { pestanaTareas } from './sitio_tareas.js';
import { pestanaBases } from './sitio_bases.js';
import { pestanaArchivos, pestanaPhp } from './sitio_avanzado.js';
import { pestanaPaquete } from './sitio_paquete.js';
import { pestanaBaja } from './sitio_baja.js';

const PESTANAS = [
  ['aplicacion', 'Aplicación', pestanaAplicacion], ['https', 'HTTPS', pestanaHttps], ['ftp', 'FTP', pestanaFtp],
  ['tareas', 'Tareas', pestanaTareas], ['bases', 'Bases de datos', pestanaBases], ['archivos', 'Archivos', pestanaArchivos],
  ['php', 'PHP', pestanaPhp], ['paquete', 'Subir y migrar', pestanaPaquete], ['baja', 'Pedir la baja', pestanaBaja],
];

export async function vistaFichaSitio(sitio, pestana) {
  const estado = await api.get(`/sitios/${enRutaSitio(sitio)}/estado`);
  const s = estado.sitio;
  const actual = PESTANAS.find(([id]) => id === pestana) || PESTANAS[0];
  const ctx = { sitio, estado, s, recargar: () => window.dispatchEvent(new Event('hashchange')) };
  const cuerpo = el('section', { clase: 'caja', 'aria-label': actual[1] }, el('p', { clase: 'cargando' }, 'Cargando…'));
  const raiz = el('div', null,
    el('p', { clase: 'migas' }, el('a', { href: '#sitios' }, 'Mi sitio web'), ' › ', sitio),
    el('div', { clase: 'fila' },
      el('div', { clase: 'crece' },
        el('h1', null, el('a', { href: `${s.ssl ? 'https' : 'http'}://${sitio}`, target: '_blank', rel: 'noopener noreferrer' }, sitio)),
        el('p', { clase: 'ayuda' }, [nombreApp(s.app), s.php ? 'PHP ' + s.php : null, megas(s.ocupado_mb) + ' ocupados', s.creado ? 'desde ' + s.creado : null]
          .filter(Boolean).join(' · '))),
      el('span', { clase: 'marca ' + (s.ssl ? 'si' : 'no') }, s.ssl ? 'HTTPS activo' : 'Sin HTTPS'),
      el('span', { clase: 'marca ' + (s.ftp ? 'si' : 'aviso-marca') }, s.ftp ? 'FTP activo' : 'FTP apagado')),
    estado.baja_pendiente ? aviso('nota', 'Pediste la baja de este sitio. Sigue publicado hasta que el administrador general la confirme.') : null,
    estado.uso && estado.cuota ? el('details', { clase: 'caja' }, el('summary', null, 'Cuota de ' + estado.dominio),
      barraUso('Espacio en disco', estado.uso.disco_mb || 0, estado.cuota.disco_mb || 0, 'mb'),
      barraUso('Bases de datos', estado.uso.bases_mb || 0, estado.cuota.bases_mb || 0, 'mb')) : null,
    el('nav', { clase: 'pestanas', 'aria-label': 'Partes del sitio' },
      PESTANAS.map(([id, texto]) => el('a', { href: `#sitios/${encodeURIComponent(sitio)}/${id}`, clase: id === actual[0] ? 'activa' : '',
        'aria-current': id === actual[0] ? 'page' : null }, texto)),
      estado.dns ? el('a', { href: '#sitios/dns/' + encodeURIComponent(estado.dominio) }, 'DNS de la zona') : null),
    cuerpo);
  try { cuerpo.replaceChildren(await actual[2](ctx)); }
  catch (e) { cuerpo.replaceChildren(aviso('error', e.message)); }
  return raiz;
}
