// Pestaña «Aplicación»: instalar del catálogo (software libre) o, si ya hay una, entrar,
// contraseña nueva del administrador, revisar y actualizar.
import { api } from '../api.js';
import { el, campo, lista } from '../ui.js';
import { abrirFuera, confirmar, enRutaSitio, hacer, irA, mensajes, nombreApp, unaVez } from './sitio_comun.js';

function datosInstalada(r, nombre) {
  if (r.asistente) {
    unaVez(`${nombre}: termina la instalación`, [
      { etiqueta: 'Abre el instalador', valor: r.asistente },
      { etiqueta: 'Servidor de la base', valor: r.bd_servidor || 'localhost' },
      { etiqueta: 'Base de datos', valor: r.base_datos },
      { etiqueta: 'Usuario de la base', valor: r.bd_usuario },
      { etiqueta: 'Contraseña de la base', valor: r.bd_clave, secreto: true },
    ], 'Sigue el instalador de la aplicación con estos datos y crea allí tu administrador. Al terminar, vuelve aquí y pulsa «Terminar instalación». La contraseña no se vuelve a mostrar.');
    return;
  }
  unaVez(`${nombre} instalado`, [
    { etiqueta: 'Administración', valor: r.url_admin },
    { etiqueta: 'Usuario', valor: r.admin_usuario },
    { etiqueta: 'Contraseña', valor: r.admin_clave, secreto: true },
    { etiqueta: 'Base de datos', valor: r.base_datos },
  ], 'Guarda estos datos ahora: la contraseña no se vuelve a mostrar. Cámbiala al entrar por primera vez.');
}

async function instalar(ctx) {
  const { aplicaciones = [] } = await api.get('/sitios/catalogo');
  const msj = mensajes();
  let elegida = aplicaciones[0] ? aplicaciones[0].id : '';
  const rejilla = el('div', { clase: 'catalogo', role: 'radiogroup', 'aria-label': 'Aplicaciones' });
  const buscar = el('input', { type: 'search', placeholder: `Buscar entre ${aplicaciones.length} aplicaciones`, 'aria-label': 'Buscar aplicación' });
  const categorias = [...new Set(aplicaciones.map(a => a.categoria).filter(Boolean))].sort();
  const cat = lista('Categoría', [{ valor: '', texto: 'Todas' }, ...categorias.map(c => ({ valor: c, texto: c }))]);
  const pintar = () => {
    const t = buscar.value.trim().toLowerCase();
    const visibles = aplicaciones.filter(a => (!cat.entrada.value || a.categoria === cat.entrada.value)
      && (!t || `${a.nombre} ${a.descripcion} ${a.categoria}`.toLowerCase().includes(t)));
    rejilla.replaceChildren(...(visibles.length ? visibles.map(a => {
      const radio = el('input', { type: 'radio', name: 'app', value: a.id, alChange: () => { elegida = a.id; } });
      radio.checked = a.id === elegida;
      return el('label', { clase: 'opcion' }, radio, ' ', el('strong', null, a.nombre), ' ', el('span', { clase: 'ayuda' }, `(${a.licencia || 'libre'})`),
        el('span', { clase: 'ayuda bloque' }, (a.categoria || '') + (a.modo === 'asistente' ? ' · se termina en su asistente' : '')),
        el('span', { clase: 'bloque' }, a.descripcion || ''));
    }) : [el('p', { clase: 'ayuda' }, 'Ninguna aplicación coincide.')]));
  };
  buscar.addEventListener('input', pintar);
  cat.entrada.addEventListener('change', pintar);
  pintar();
  const titulo = campo('Nombre del sitio', { type: 'text', maxlength: 100, required: true });
  const correo = campo('Correo del administrador de la aplicación', { type: 'email', required: true, autocomplete: 'email' });
  const boton = el('button', { clase: 'boton', type: 'submit' }, 'Instalar');
  return el('form', { alSubmit: async (e) => {
    e.preventDefault();
    const app = aplicaciones.find(a => a.id === elegida);
    if (!app) { msj.error('Elige una aplicación.'); return; }
    const r = await hacer(msj, boton, `Instalando ${app.nombre}: descarga, verificación e instalación. Puede tardar varios minutos; no cierres esta página.`,
      () => api.post(`/sitios/${enRutaSitio(ctx.sitio)}/app`, { aplicacion: app.id, titulo: titulo.entrada.value.trim(), correo: correo.entrada.value.trim() }));
    if (r) { datosInstalada(r, app.nombre); ctx.recargar(); }
  } },
    el('h2', null, 'Instalar una aplicación'),
    el('p', { clase: 'ayuda' }, 'Todo es software libre, descargado de su origen oficial y verificado antes de instalarlo. El sitio debe estar vacío.'),
    el('div', { clase: 'fila' }, el('div', { clase: 'crece' }, buscar), cat.nodo),
    rejilla,
    el('div', { clase: 'rejilla' }, titulo.nodo, correo.nodo),
    msj.nodo,
    el('div', { clase: 'pie-form' }, el('button', { clase: 'boton claro', type: 'button', alClick: () => irA(ctx.sitio, 'paquete') }, 'Tengo mi propio paquete'), boton));
}

function revision(r) {
  const p = r.actualizaciones;
  const pendientes = p ? [...(p.nucleo || []).map(x => 'Núcleo: ' + x), ...(p.complementos || []).map(x => 'Complemento: ' + x), ...(p.temas || []).map(x => 'Tema: ' + x)] : null;
  return el('ul', { clase: 'miembros' },
    el('li', null, el('strong', null, 'Versión'), el('span', null, r.version || '—')),
    pendientes ? el('li', null, el('strong', null, 'Actualizaciones'), pendientes.length
      ? el('span', { clase: 'marca no' }, pendientes.length + ' pendientes') : el('span', { clase: 'marca si' }, 'Todo al día')) : null,
    pendientes && pendientes.length ? el('li', null, el('span', { clase: 'ayuda' }, pendientes.join(' · '))) : null,
    r.integridad_nucleo ? el('li', null, el('strong', null, 'Archivos del núcleo'),
      el('span', { clase: 'marca ' + (r.integridad_nucleo === 'correcta' ? 'si' : 'no') }, r.integridad_nucleo === 'correcta' ? 'Sin alteraciones' : r.integridad_nucleo)) : null,
    r.detalle ? el('li', null, el('code', { clase: 'registro' }, r.detalle)) : null);
}

function instalada(ctx) {
  const { s, sitio } = ctx;
  const ruta = `/sitios/${enRutaSitio(sitio)}`;
  const msj = mensajes();
  const resultado = el('div');
  const boton = (texto, fn, clase) => { const b = el('button', { clase: clase || 'boton claro', type: 'button' }, texto); b.addEventListener('click', () => fn(b)); return b; };
  const acciones = [
    s.app === 'wordpress' ? boton('Entrar al escritorio', (b) => hacer(msj, b, 'Preparando el acceso…', () => abrirFuera(() => api.post(ruta + '/entrar'))), 'boton') : null,
    s.app !== 'wordpress' && s.app_admin && /^https?:\/\//.test(s.app_admin) ? el('a', { clase: 'boton', href: s.app_admin, target: '_blank', rel: 'noopener noreferrer' }, 'Administrar') : null,
    s.app_pendiente ? boton('Terminar instalación', async (b) => {
      if (!await confirmar('Terminar instalación', `¿Ya terminaste el instalador de ${nombreApp(s.app)}? Se cerrará el instalador web.`, 'Sí, cerrarlo')) return;
      if (await hacer(msj, b, 'Cerrando el instalador…', () => api.post(ruta + '/terminar')) !== undefined) ctx.recargar();
    }, 'boton') : null,
    s.app !== 'paquete' && !s.app_pendiente ? boton('Nueva contraseña', async (b) => {
      if (!await confirmar('Nueva contraseña', `Se generará una contraseña nueva para el administrador de ${sitio}. La anterior deja de valer.`, 'Generar')) return;
      const r = await hacer(msj, b, 'Generando la contraseña…', () => api.post(ruta + '/clave-admin'));
      if (r) unaVez('Nueva contraseña del administrador', [{ etiqueta: 'Administración', valor: r.url_admin }, { etiqueta: 'Usuario', valor: r.usuario }, { etiqueta: 'Contraseña', valor: r.clave, secreto: true }]);
    }) : null,
    s.app !== 'paquete' ? boton('Revisar', async (b) => {
      const r = await hacer(msj, b, 'Revisando versión, actualizaciones e integridad (hasta un par de minutos)…', () => api.post(ruta + '/revisar'));
      if (r) resultado.replaceChildren(revision(r));
    }) : null,
    s.app !== 'paquete' ? boton('Actualizar ahora', async (b) => {
      if (!await confirmar('Actualizar', 'Se actualizarán el núcleo, los complementos y los temas. Puede tardar unos minutos.', 'Actualizar')) return;
      const r = await hacer(msj, b, 'Actualizando (puede tardar unos minutos)…', () => api.post(ruta + '/actualizar'));
      if (r) { resultado.replaceChildren(revision(r)); msj.ok('Actualización terminada.'); }
    }) : null,
  ];
  return el('div', null,
    el('h2', null, nombreApp(s.app)),
    s.aviso_url ? el('p', { clase: 'aviso nota' }, s.aviso_url) : null,
    el('div', { clase: 'fila' }, acciones),
    el('p', { clase: 'ayuda' }, s.app === 'wordpress' ? '«Entrar» abre el escritorio sin contraseña con un enlace de un solo uso que vence en 60 segundos.' : ''),
    msj.nodo, resultado,
    el('p', { clase: 'ayuda' }, 'Protecciones activas: cortafuegos de aplicación, límite de intentos de entrada y bloqueo automático de direcciones atacantes.'));
}

export async function pestanaAplicacion(ctx) {
  if (ctx.s.app === 'propia') {
    return el('p', { clase: 'aviso nota' }, 'Este sitio corre una aplicación propia (su propio código): se administra en la pestaña «Node.js y Python».');
  }
  return ctx.s.app ? instalada(ctx) : instalar(ctx);
}
