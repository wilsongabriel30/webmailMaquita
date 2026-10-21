// Pestaña «Copias»: copias del sitio que controlas tú (archivos y bases de datos en un solo .tar.gz).
// Son aparte de los respaldos del servidor. Cuentan para el espacio en disco del dominio.
import { api } from '../api.js';
import { el } from '../ui.js';
import { barraUso, confirmar, descargar, enRutaSitio, hacer, mensajes, tamano } from './sitio_comun.js';
import { boton, poner } from './sitio_piezas.js';

export async function pestanaCopias(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/copias`;
  const msj = mensajes();
  const raiz = el('div');
  const cargar = async () => pintar(await api.get(ruta));
  const pintar = (datos) => {
    const copias = datos.copias || [], tope = datos.tope || 5, espacio = datos.espacio || {};
    const crear = boton('Crear una copia ahora', 'boton', async (b) => {
      const r = await hacer(msj, b, 'Haciendo la copia (archivos y bases; puede tardar varios minutos)…', () => api.post(ruta));
      if (r) { await cargar(); msj.ok('Copia creada.'); }
    });
    if (copias.length >= tope) crear.disabled = true;
    poner(raiz,
      el('p', { clase: 'ayuda' }, `Hasta ${tope} copias por sitio. Cada una trae la carpeta pública, la aplicación y un volcado de cada base de datos, y se puede abrir en cualquier equipo.`),
      espacio.disco_mb ? barraUso('Espacio del dominio (con las copias)', espacio.ocupado_mb || 0, espacio.disco_mb, 'mb') : null,
      el('div', { clase: 'fila espacio' }, crear, copias.length >= tope ? el('span', { clase: 'ayuda' }, 'Llegaste al máximo: borra una para crear otra.') : null),
      msj.nodo,
      el('div', { clase: 'caja tabla-marco' }, el('table', null,
        el('thead', null, el('tr', null, ['Fecha', 'Motivo', 'Tamaño', ''].map(t => el('th', null, t)))),
        el('tbody', null, copias.length ? copias.map(c => el('tr', null,
          el('td', null, c.fecha || c.id),
          el('td', null, c.motivo || 'manual', (c.bases || []).length ? el('div', { clase: 'ayuda' }, `${c.bases.length} base(s) de datos`) : null),
          el('td', null, tamano(c.bytes)),
          el('td', { clase: 'acciones' },
            boton('Descargar', 'enlace', (b) => hacer(msj, b, 'Preparando la descarga…', () => descargar(() => api.post(`${ruta}/${c.id}/descargar`)))),
            boton('Restaurar', 'enlace', async (b) => {
              if (!await confirmar('Restaurar la copia', `El sitio volverá a como estaba el ${c.fecha || c.id}, archivos y bases. Antes se hace una copia del estado actual, por si acaso.`, 'Restaurar', true)) return;
              const r = await hacer(msj, b, 'Restaurando (puede tardar varios minutos)…', () => api.post(`${ruta}/${c.id}/restaurar`));
              if (r) {
                await cargar();
                msj.ok('Copia restaurada.' + ((r.enlaces_omitidos || []).length ? ` Se omitieron ${r.enlaces_omitidos.length} enlace(s) que salían del sitio.` : ''));
              }
            }),
            boton('Borrar', 'enlace peligro', async (b) => {
              if (!await confirmar('Borrar la copia', `La copia del ${c.fecha || c.id} se borrará para siempre.`, 'Borrar', true)) return;
              if (await hacer(msj, b, 'Borrando…', () => api.del(`${ruta}/${c.id}`))) { await cargar(); msj.ok('Copia borrada.'); }
            })))) : el('tr', null, el('td', { colspan: '4', clase: 'vacio' }, 'Todavía no hay copias.'))))));
  };
  await cargar();
  return raiz;
}
