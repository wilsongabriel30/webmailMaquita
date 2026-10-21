// Pestaña «Archivos»: administrador de archivos de la carpeta pública del sitio. Listar, subir, descargar,
// carpeta nueva, renombrar o mover, copiar, borrar (a la papelera, 30 días), comprimir, descomprimir y permisos.
// Todo lo hace el servidor con el usuario del sitio y sin salir de su carpeta. La papelera está en
// sitio_archivos_papelera.js.
import { api } from '../api.js';
import { el, aviso, campo, casilla, lista, ventana } from '../ui.js';
import { confirmar, descargar, enRutaSitio, hacer, mensajes, tamano } from './sitio_comun.js';
import { papelera } from './sitio_archivos_papelera.js';
import { boton, poner } from './sitio_piezas.js';

const MODOS = [['644', 'Lectura para todos (644)'], ['640', 'De serie del sitio (640)'], ['600', 'Solo el dueño (600)'],
  ['755', 'Carpeta o programa, lectura para todos (755)'], ['750', 'Carpeta de serie del sitio (750)'], ['700', 'Carpeta solo del dueño (700)']];
const unir = (carpeta, nombre) => (carpeta === '.' ? nombre : `${carpeta}/${nombre}`);
const esComprimido = (n) => /\.(zip|tar\.gz|tgz)$/i.test(n);

export async function pestanaGestor(ctx) {
  const base = `/sitios/${enRutaSitio(ctx.sitio)}/archivos`;
  const msj = mensajes();
  const raiz = el('div');
  const marcados = new Set();
  let ruta = '.';

  const abrir = async (nueva) => {
    const datos = await hacer(msj, null, 'Cargando…', () => api.get(`${base}?ruta=${encodeURIComponent(nueva)}`));
    if (!datos) return;
    ruta = datos.ruta || nueva;
    marcados.clear();
    pintar(datos);
  };
  const recargar = () => abrir(ruta);
  // Hace la operación y, si sale bien, vuelve a listar la carpeta y deja el aviso.
  const operar = async (b, espera, fn, bien) => {
    const r = await hacer(msj, b, espera, fn);
    if (r) { await recargar(); msj.ok(bien); }
    return r;
  };
  const pedirRuta = (titulo, etiqueta, inicial, textoBoton, fn) => {
    const c = campo(etiqueta, { type: 'text', maxlength: 1000, valor: inicial, required: true }, 'Ruta dentro de la carpeta pública, p. ej. imagenes/logo.png');
    ventana(titulo, c.nodo, textoBoton, async () => { await fn(c.entrada.value.trim()); });
  };
  // Para las ventanas: si falla, el error se ve dentro de la ventana (que sigue abierta); si sale bien, se relista.
  const enVentana = (fn, bien) => async (valor) => { await fn(valor); await recargar(); msj.ok(bien); };

  const acciones = (e) => {
    const r = unir(ruta, e.nombre);
    return el('td', { clase: 'acciones' },
      e.tipo === 'archivo' ? boton('Descargar', 'enlace', (b) => hacer(msj, b, 'Preparando la descarga…', () => descargar(() => api.post(base + '/descargar', { ruta: r })))) : null,
      e.tipo === 'archivo' && esComprimido(e.nombre) ? boton('Descomprimir', 'enlace', () => pedirRuta('Descomprimir', 'Carpeta de destino', ruta, 'Descomprimir',
        enVentana((d) => api.post(base + '/descomprimir', { origen: r, destino: d }), 'Descomprimido.'))) : null,
      boton('Renombrar o mover', 'enlace', () => pedirRuta('Renombrar o mover', 'Nueva ruta', r, 'Mover',
        enVentana((d) => api.post(base + '/mover', { origen: r, destino: d }), 'Movido.'))),
      e.tipo !== 'enlace' ? boton('Copiar', 'enlace', () => pedirRuta('Copiar', 'Ruta de la copia', r + (e.tipo === 'carpeta' ? '-copia' : ''), 'Copiar',
        enVentana((d) => api.post(base + '/copiar', { origen: r, destino: d }), 'Copiado.'))) : null,
      e.tipo !== 'enlace' ? boton('Permisos', 'enlace', () => {
        const m = lista('Permisos', MODOS.map(([valor, texto]) => ({ valor, texto })));
        m.entrada.value = MODOS.some(([v]) => v === e.permisos) ? e.permisos : '644';
        ventana(`Permisos de ${e.nombre}`, m.nodo, 'Cambiar', () => enVentana(() => api.post(base + '/permisos', { ruta: r, modo: m.entrada.value }), 'Permisos cambiados.')());
      }) : null,
      boton('Borrar', 'enlace peligro', async (b) => {
        if (await confirmar('Borrar', `«${e.nombre}» irá a la papelera del sitio, de donde se puede recuperar durante 30 días.`, 'Borrar', true)) {
          operar(b, 'Borrando…', () => api.post(base + '/borrar', { ruta: r }), `«${e.nombre}» está en la papelera.`);
        }
      }));
  };

  const migas = () => {
    const partes = ruta === '.' ? [] : ruta.split('/');
    return el('p', { clase: 'migas' }, boton('publico', 'enlace', () => abrir('.')),
      partes.map((p, i) => [' / ', i === partes.length - 1 ? el('strong', null, p) : boton(p, 'enlace', () => abrir(partes.slice(0, i + 1).join('/')))]));
  };

  const subir = () => {
    const entrada = el('input', { type: 'file', multiple: true, 'aria-label': 'Archivos que se suben' });
    const reemplazar = casilla('Reemplazar si ya existe', false);
    const avance = el('progress', { max: '100', value: '0', hidden: true });
    const enviar = boton('Subir', 'boton', async (b) => {
      const archivos = [...entrada.files];
      if (!archivos.length) { msj.error('Elige uno o más archivos.'); return; }
      avance.hidden = false;
      for (const [i, f] of archivos.entries()) {
        const consulta = new URLSearchParams({ nombre: f.name, carpeta: ruta, reemplazar: reemplazar.entrada.checked ? '1' : '0' });
        const r = await hacer(msj, b, `Subiendo ${f.name} (${i + 1} de ${archivos.length})…`,
          () => api.subirGrande(`${base}/subir?${consulta}`, f, (pct) => { avance.value = String(pct); }));
        if (!r) { avance.hidden = true; return; }
      }
      avance.hidden = true;
      await recargar();
      msj.ok(archivos.length === 1 ? 'Archivo subido.' : `${archivos.length} archivos subidos.`);
    });
    return el('details', { clase: 'caja' }, el('summary', null, 'Subir archivos'),
      el('p', { clase: 'ayuda' }, 'Hasta 512 MB cada uno; para más, usa FTP o SFTP. Cuenta para el espacio del dominio.'),
      entrada, reemplazar.nodo, avance, el('div', { clase: 'pie-form' }, enviar));
  };

  const herramientas = () => el('div', { clase: 'fila' },
    boton('Carpeta nueva', 'boton claro', () => {
      const c = campo('Nombre', { type: 'text', maxlength: 255, required: true });
      ventana('Carpeta nueva', c.nodo, 'Crear', () => enVentana(() => api.post(base + '/carpeta', { ruta: unir(ruta, c.entrada.value.trim()) }), 'Carpeta creada.')());
    }),
    boton('Comprimir lo marcado', 'boton claro', () => {
      if (!marcados.size) { msj.error('Marca primero lo que quieres comprimir.'); return; }
      const c = campo('Nombre del .zip', { type: 'text', maxlength: 255, required: true, valor: 'archivos.zip' });
      ventana(`Comprimir ${marcados.size} elemento(s)`, c.nodo, 'Comprimir',
        () => enVentana(() => api.post(base + '/comprimir', { rutas: [...marcados], destino: unir(ruta, c.entrada.value.trim()) }), 'Comprimido.')());
    }),
    boton('Papelera', 'boton claro', () => papelera(base, msj, recargar)),
    boton('Actualizar', 'enlace', () => recargar()));

  const pintar = (datos) => {
    const entradas = datos.entradas || [];
    const filas = entradas.map(e => {
      const r = unir(ruta, e.nombre);
      const marca = el('input', { type: 'checkbox', 'aria-label': 'Marcar ' + e.nombre });
      marca.addEventListener('change', () => { if (marca.checked) marcados.add(r); else marcados.delete(r); });
      return el('tr', null,
        el('td', null, marca),
        el('td', null, e.tipo === 'carpeta' ? boton(e.nombre + '/', 'enlace', () => abrir(r)) : el('span', null, e.nombre),
          e.tipo === 'enlace' ? el('div', { clase: 'ayuda' }, e.fuera ? 'enlace que sale del sitio (no se sigue)' : `enlace a ${e.apunta_a || ''}`) : null),
        el('td', null, e.tipo === 'archivo' ? tamano(e.bytes) : ''),
        el('td', null, e.modificado || ''),
        el('td', null, el('code', null, e.permisos || '')),
        acciones(e));
    });
    poner(raiz,
      el('p', { clase: 'ayuda' }, 'La carpeta pública es lo que se ve en la web. Lo que borras va a la papelera del sitio.'),
      migas(), herramientas(), msj.nodo, subir(),
      datos.recortado ? aviso('nota', 'La carpeta tiene muchos elementos: se muestran los primeros 5000.') : null,
      el('div', { clase: 'caja tabla-marco' }, el('table', null,
        el('thead', null, el('tr', null, ['', 'Nombre', 'Tamaño', 'Modificado', 'Permisos', ''].map(t => el('th', null, t)))),
        el('tbody', null, filas.length ? filas : el('tr', null, el('td', { colspan: '6', clase: 'vacio' }, 'Carpeta vacía.'))))));
  };

  const inicial = await api.get(`${base}?ruta=.`);
  ruta = inicial.ruta || '.';
  pintar(inicial);
  return raiz;
}
